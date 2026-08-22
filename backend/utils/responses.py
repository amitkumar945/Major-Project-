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
