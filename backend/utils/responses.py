"""
Consistent JSON envelope for every endpoint.

Success:  { "success": true,  "message": "...", "data": {...} }
Error:    { "success": false, "message": "...", "error": {...} }

`ApiException` lets any service raise a failure with the right HTTP status; the
app-level error handler turns it into the error envelope above.
"""

from flask import jsonify


class ApiException(Exception):
    """Raised by services; converted to an error response by the handler."""

    def __init__(self, message: str, status: int = 400, error: dict = None):
        super().__init__(message)
        self.message = message
        self.status = status
        self.error = error or {}


def success(data=None, message: str = "", status: int = 200):
    payload = {"success": True, "message": message, "data": data if data is not None else {}}
    return jsonify(payload), status


def error(message: str, status: int = 400, detail=None):
    payload = {"success": False, "message": message, "error": detail or {}}
    return jsonify(payload), status


def validation_error(errors: dict, message: str = "Please correct the highlighted fields."):
    """Field-level errors, in the same `{field: message}` shape the frontend
    validators already produce."""
    return error(message, 422, {"fields": errors})


# --------------------------------------------------------------- pagination

# Ceiling on how much one request may ask for. Low enough that a phone on a
# slow connection cannot be handed an unusable payload, and low enough that a
# single caller cannot pull the whole collection into memory. `/complaints`
# keeps its own historic ceiling for the CSV export path.
MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 20


def paginate(items: list, page=1, page_size=DEFAULT_PAGE_SIZE, max_page_size=MAX_PAGE_SIZE) -> dict:
    """Slice an in-memory list into the standard paginated envelope.

    Returns the same `{items, total, page, pageSize, totalPages}` shape the
    complaint list already uses, so a mobile client can parse every paginated
    endpoint with one model.
    """
    try:
        page_size = int(page_size or DEFAULT_PAGE_SIZE)
    except (TypeError, ValueError):
        page_size = DEFAULT_PAGE_SIZE
    try:
        page = int(page or 1)
    except (TypeError, ValueError):
        page = 1

    page_size = max(1, min(page_size, max_page_size))
    items = list(items or [])
    total = len(items)
    total_pages = max((total + page_size - 1) // page_size, 1)
    page = max(1, min(page, total_pages))
    start = (page - 1) * page_size

    return {
        "items": items[start:start + page_size],
        "total": total,
        "page": page,
        "pageSize": page_size,
        "totalPages": total_pages,
    }


def maybe_paginated(items: list, args, default_page_size=DEFAULT_PAGE_SIZE):
    """Paginate only when the caller asked for it.

    The website reads these endpoints as bare arrays - `[...officers].sort()`,
    `items.map(...)` - so changing the default shape would break live pages.
    A client that sends `?page=` or `?pageSize=` gets the paginated envelope
    instead; everyone else gets exactly the array they got before.
    """
    wants = args.get("page") is not None or args.get("pageSize") is not None
    if not wants:
        return list(items or [])
    return paginate(items, args.get("page", 1), args.get("pageSize", default_page_size))
