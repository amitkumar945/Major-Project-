"""
Secure upload handling.

Validation is layered, because any single check can be spoofed:

  1. filename          - sanitised with werkzeug's secure_filename
  2. extension         - must be on the allow-list
  3. declared MIME     - must be plausible for that extension
  4. magic number      - the first bytes must match the real format
  5. size              - enforced by reading the stream, not the header

Files land in `uploads/YYYY/MM/` with a random name; MongoDB stores only the
metadata and the relative path, never the bytes.
"""

import hashlib
import os
from pathlib import Path

from werkzeug.utils import secure_filename

from constants import (
    ALLOWED_EXTENSIONS,
    ALLOWED_MIME_TYPES,
    EXTENSION_KIND,
    FILE_SIGNATURES,
)
from utils.helpers import uid, utcnow
from utils.responses import ApiException


def extension_of(filename: str) -> str:
    return Path(filename or "").suffix.lower().lstrip(".")


def is_allowed_extension(filename: str) -> bool:
    return extension_of(filename) in ALLOWED_EXTENSIONS


def _read_head(stream, size: int = 8) -> bytes:
    position = stream.tell()
    stream.seek(0)
    head = stream.read(size)
    stream.seek(position)
    return head


def _stream_size(stream) -> int:
    position = stream.tell()
    stream.seek(0, os.SEEK_END)
    size = stream.tell()
    stream.seek(position)
    return size


def validate_file(storage, max_size: int) -> dict:
    """Run every check on one uploaded file. Raises ApiException on rejection.

    Returns the sanitised name, extension and size for the caller to save.
    """
    original = storage.filename or ""
    if not original.strip():
        raise ApiException("A file was uploaded without a filename.", 400)

    safe_name = secure_filename(original)
    if not safe_name:
        raise ApiException(f"'{original}' is not an acceptable file name.", 400)

    extension = extension_of(safe_name)
    if extension not in ALLOWED_EXTENSIONS:
        raise ApiException(
            f"'{original}' has an unsupported type. "
            f"Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}.",
            400,
        )

    size = _stream_size(storage.stream)
    if size == 0:
        raise ApiException(f"'{original}' is empty.", 400)
    if size > max_size:
        raise ApiException(
            f"'{original}' is {size / (1024 * 1024):.1f} MB. "
            f"The limit is {max_size / (1024 * 1024):.0f} MB per file.",
            413,
        )

    # The browser-declared MIME type must at least be plausible.
    declared = (storage.mimetype or "").lower()
    acceptable = ALLOWED_MIME_TYPES.get(extension, set())
    if declared and acceptable and declared not in acceptable:
        raise ApiException(
            f"'{original}' claims to be {declared}, which does not match a .{extension} file.",
            400,
        )

    # The real test: the bytes themselves.
    head = _read_head(storage.stream, 8)
    signatures = FILE_SIGNATURES.get(extension, [])
    if signatures and not any(head.startswith(sig) for sig in signatures):
        raise ApiException(
            f"'{original}' does not contain valid {extension.upper()} data. "
            "The file may be renamed or corrupted.",
            400,
        )

    return {"safeName": safe_name, "extension": extension, "size": size, "original": original}


def save_file(storage, upload_folder: str, max_size: int, subfolder: str = "") -> dict:
    """Validate then write one file to disk, returning its metadata document."""
    checked = validate_file(storage, max_size)
    extension = checked["extension"]

    now = utcnow()
    relative_dir = Path(subfolder or "") / f"{now.year:04d}" / f"{now.month:02d}"
    target_dir = Path(upload_folder) / relative_dir
    target_dir.mkdir(parents=True, exist_ok=True)

    # Random stored name: keeps the original out of the filesystem and stops
    # two users overwriting each other.
    stored_name = f"{uid('f', 12)}.{extension}"
    absolute = target_dir / stored_name

    storage.stream.seek(0)
    digest = hashlib.sha256()
    with open(absolute, "wb") as handle:
        while chunk := storage.stream.read(64 * 1024):
            digest.update(chunk)
            handle.write(chunk)

    relative_path = str(relative_dir / stored_name).replace("\\", "/")

    # Shape matches the `evidence` objects the frontend already renders.
    return {
        "id": uid("FILE"),
        "name": checked["original"],
        "kind": EXTENSION_KIND.get(extension, "doc"),
        "type": storage.mimetype or "",
        "size": checked["size"],
        "url": f"/api/files/{relative_path}",
        "path": relative_path,
        "checksum": digest.hexdigest(),
        "uploadedAt": now.isoformat(),
    }


def save_files(files, upload_folder: str, max_size: int, max_files: int, subfolder: str = "") -> list:
    """Validate and save a batch. Nothing is written unless every file passes,
    so a rejected upload never leaves half a set on disk."""
    files = [f for f in (files or []) if f and f.filename]
    if not files:
        return []
    if len(files) > max_files:
        raise ApiException(f"You can upload at most {max_files} files at a time.", 400)

    for storage in files:  # validate all first
        validate_file(storage, max_size)

    saved = []
    try:
        for storage in files:
            saved.append(save_file(storage, upload_folder, max_size, subfolder))
    except Exception:
        for item in saved:  # roll back partial writes
            delete_file(item.get("path"), upload_folder)
        raise
    return saved


def delete_file(relative_path: str, upload_folder: str) -> bool:
    """Remove a stored file, refusing to step outside the upload folder."""
    if not relative_path:
        return False
    root = Path(upload_folder).resolve()
    try:
        target = (root / relative_path).resolve()
        target.relative_to(root)  # raises if the path escapes the root
    except (ValueError, OSError):
        return False
    if target.is_file():
        target.unlink()
        return True
    return False


def resolve_upload_path(relative_path: str, upload_folder: str) -> Path:
    """Safely turn a stored relative path into an absolute one for serving."""
    root = Path(upload_folder).resolve()
    try:
        target = (root / relative_path).resolve()
        target.relative_to(root)
    except (ValueError, OSError):
        raise ApiException("Invalid file path.", 400)
    if not target.is_file():
        raise ApiException("File not found.", 404)
    return target
