"""
Notification routes.

Every endpoint is scoped to the signed-in user, so nobody can read or modify
another person's feed.
"""

from flask import Blueprint, request

from services import notification_service
from utils.helpers import to_bool, to_int
from utils.jwt_utils import current_user, jwt_required
from utils.responses import error, success

bp = Blueprint("notifications", __name__, url_prefix="/api/notifications")


@bp.get("")
@jwt_required
def list_notifications():
    return success(
        notification_service.get_for_user(
            current_user()["id"],
            unread_only=to_bool(request.args.get("unreadOnly"), False),
            type_=request.args.get("type", ""),
            limit=to_int(request.args.get("limit"), 100),
        )
    )


@bp.get("/unread-count")
@jwt_required
def unread_count():
    return success({"count": notification_service.unread_count(current_user()["id"])})


@bp.put("/read-all")
@jwt_required
def mark_all_read():
    """Registered before `/<id>/read` so "read-all" is never read as an id."""
    updated = notification_service.mark_all_read(current_user()["id"])
    return success({"success": True, "updated": updated}, "All notifications marked as read.")


@bp.put("/<notification_id>/read")
@jwt_required
def mark_read(notification_id):
    if not notification_service.mark_read(notification_id, current_user()["id"]):
        return error("Notification not found.", 404)
    return success({"success": True}, "Marked as read.")


@bp.put("/<notification_id>/unread")
@jwt_required
def mark_unread(notification_id):
    if not notification_service.mark_unread(notification_id, current_user()["id"]):
        return error("Notification not found.", 404)
    return success({"success": True}, "Marked as unread.")


@bp.delete("/<notification_id>")
@jwt_required
def delete_notification(notification_id):
    if not notification_service.delete(notification_id, current_user()["id"]):
        return error("Notification not found.", 404)
    return success({"success": True}, "Notification deleted.")
