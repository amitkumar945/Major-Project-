"""
Serving uploaded files.

Evidence and resolution proof can identify a complainant, so downloads are
authenticated and authorised: only the complainant, the handling officer, the
department's officers and an admin can fetch a complaint's files.
"""

from flask import Blueprint, current_app, send_file

from database import complaints
from services import complaint_service
from utils.file_utils import resolve_upload_path
from utils.jwt_utils import current_user, jwt_required
from utils.responses import error

bp = Blueprint("files", __name__, url_prefix="/api/files")


@bp.get("/<path:relative_path>")
@jwt_required
def serve_file(relative_path):
    """Return one stored file after checking the caller may see it."""
    url = f"/api/files/{relative_path}"

    # Find the complaint this file belongs to, via evidence or resolution proof.
    complaint = complaints().find_one(
        {"$or": [{"evidence.url": url}, {"resolution.proof.url": url}]},
        {"_id": 0},
    )

    if complaint:
        if not complaint_service.can_view(complaint, current_user()):
            return error("You do not have permission to view this file.", 403)
    # A file with no complaint (e.g. a standalone OCR upload) stays
    # authenticated-only, which the decorator already enforces.

    absolute = resolve_upload_path(relative_path, current_app.config["UPLOAD_FOLDER"])
    # Never inline: an uploaded HTML/SVG rendered on this origin could run script.
    return send_file(absolute, as_attachment=False, download_name=absolute.name, conditional=True)
