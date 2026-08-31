"""
Notification service.

Notifications are stored in MongoDB in exactly the shape the frontend's
notification centre already renders:

    { id, recipientId, type, title, message, complaintId, createdAt, read }

Delivery is pluggable: `_deliver()` hands the notification to
`services.email_service` when MAIL_NOTIFICATIONS_ENABLED is on. Email is
best-effort - the in-app feed is the source of truth, so a mail failure is
logged and never breaks the complaint action that triggered it.
"""

import logging

from constants import NOTIFICATION_TYPES
from database import notifications
from utils.helpers import clean_document, iso, uid, utcnow

logger = logging.getLogger(__name__)


def _deliver(notification: dict) -> None:
    """Fan the notification out to email and mobile push.

    Best-effort by design: the notification is already stored and visible in the
    in-app feed, so a mail failure is logged and swallowed rather than rolling
    back a complaint update. OTP delivery is the opposite - see `otp_service`.

    The two channels are independent. Push is attempted before the mail block
    returns early, so turning mail off does not silently disable push as well.
    """
    logger.info(
        "Notification %s for %s: %s",
        notification["type"], notification["recipientId"], notification["title"],
    )

    from flask import current_app, has_app_context

    _push(notification)

    if not has_app_context() or not current_app.config.get("MAIL_NOTIFICATIONS_ENABLED"):
        return

    from services import email_service

    if not email_service.is_configured():
        return

    recipient = _recipient_email(notification["recipientId"])
    if not recipient:
        return

    try:
        email_service.send_notification_email(
            recipient,
            notification["title"],
            notification["message"],
            notification.get("complaintId") or "",
        )
    except email_service.EmailError as exc:
        logger.warning(
            "Notification email to user %s failed (%s): %s",
            notification["recipientId"], exc.reason, exc.message,
        )
    except Exception:
        logger.exception("Unexpected error while emailing notification %s.", notification["id"])


def _push(notification: dict) -> None:
    """Send the notification to the user's registered mobile devices.

    Silently does nothing when push is not configured, which is the default -
    so behaviour for the existing web-only deployment is unchanged.
    """
    try:
        from services import push_service

        if not push_service.is_configured():
            return

        push_service.send_to_user(
            notification["recipientId"],
            notification["title"],
            notification["message"],
            {
                "type": notification.get("type", ""),
                "complaintId": notification.get("complaintId") or "",
                "notificationId": notification.get("id", ""),
            },
        )
    except Exception:
        # Never let a push problem escape into the complaint workflow.
        logger.exception("Unexpected error while pushing notification %s.", notification.get("id"))


def _recipient_email(user_id: str) -> str:
    """Look up a recipient's address, tolerating a missing user."""
    try:
        from database import users

        user = users().find_one({"id": user_id}, {"_id": 0, "email": 1})
        return (user or {}).get("email", "")
    except Exception:
        logger.exception("Could not look up the email address for user %s.", user_id)
        return ""


def create(recipient_id: str, type_: str, title: str, message: str, complaint_id: str = None) -> dict:
    """Store one notification and hand it to the delivery hook."""
    if not recipient_id:
        return None

    notification = {
        "id": uid("NTF", 10),
        "recipientId": recipient_id,
        "type": type_,
        "title": title,
        "message": message,
        "complaintId": complaint_id,
        "createdAt": iso(utcnow()),
        "read": False,
    }

    notifications().insert_one(notification)
    _deliver(notification)
    return clean_document(notification)


def create_many(recipient_ids, type_: str, title: str, message: str, complaint_id: str = None) -> list:
    """Same notification to several people, skipping blanks and duplicates."""
    seen, created = set(), []
    for recipient_id in recipient_ids or []:
        if not recipient_id or recipient_id in seen:
            continue
        seen.add(recipient_id)
        result = create(recipient_id, type_, title, message, complaint_id)
        if result:
            created.append(result)
    return created


def get_for_user(user_id: str, unread_only: bool = False, type_: str = "", limit: int = 100) -> list:
    """The feed for one user, newest first - what `getNotifications()` returns."""
    query = {"recipientId": user_id}
    if unread_only:
        query["read"] = False
    if type_:
        query["type"] = type_

    cursor = notifications().find(query, {"_id": 0}).sort("createdAt", -1).limit(max(1, min(limit, 500)))
    return list(cursor)


def unread_count(user_id: str) -> int:
    return notifications().count_documents({"recipientId": user_id, "read": False})


def mark_read(notification_id: str, user_id: str) -> bool:
    """Mark one notification read. Scoped to the owner so a user cannot touch
    somebody else's feed."""
    result = notifications().update_one(
        {"id": notification_id, "recipientId": user_id}, {"$set": {"read": True}}
    )
    return result.matched_count > 0


def mark_unread(notification_id: str, user_id: str) -> bool:
    result = notifications().update_one(
        {"id": notification_id, "recipientId": user_id}, {"$set": {"read": False}}
    )
    return result.matched_count > 0


def mark_all_read(user_id: str) -> int:
    result = notifications().update_many(
        {"recipientId": user_id, "read": False}, {"$set": {"read": True}}
    )
    return result.modified_count


def delete(notification_id: str, user_id: str) -> bool:
    result = notifications().delete_one({"id": notification_id, "recipientId": user_id})
    return result.deleted_count > 0


# ------------------------------------------------- complaint event helpers
# One function per lifecycle event, so routes never hand-write message text.


def complaint_submitted(complaint: dict) -> None:
    create(
        complaint["submittedBy"]["id"],
        NOTIFICATION_TYPES["SUBMITTED"],
        "Complaint registered",
        f"Your complaint {complaint['id']} has been registered and sent to {complaint['department']}.",
        complaint["id"],
    )
    officer = complaint.get("assignedOfficer")
    if officer:
        create(
            officer["id"],
            NOTIFICATION_TYPES["ASSIGNED"],
            "New complaint assigned",
            f"{complaint['title']} ({complaint['priority']} priority) has been assigned to you.",
            complaint["id"],
        )


def officer_assigned(complaint: dict, officer: dict) -> None:
    create(
        officer["id"],
        NOTIFICATION_TYPES["OFFICER_ASSIGNED"],
        "Complaint assigned to you",
        f"{complaint['title']} has been assigned to you by the administration.",
        complaint["id"],
    )
    create(
        complaint["submittedBy"]["id"],
        NOTIFICATION_TYPES["OFFICER_ASSIGNED"],
        "Officer assigned",
        f"{officer['name']} is now handling your complaint {complaint['id']}.",
        complaint["id"],
    )


def status_changed(complaint: dict, status: str, actor_name: str = "") -> None:
    create(
        complaint["submittedBy"]["id"],
        NOTIFICATION_TYPES["STATUS_CHANGED"],
        f"Status updated to {status}",
        f"Your complaint {complaint['id']} is now marked \"{status}\".",
        complaint["id"],
    )


def resolution_submitted(complaint: dict) -> None:
    create(
        complaint["submittedBy"]["id"],
        NOTIFICATION_TYPES["RESOLVED"],
        "Complaint resolved",
        f"Your complaint {complaint['id']} has been resolved. Please rate the work.",
        complaint["id"],
    )
    create(
        complaint["submittedBy"]["id"],
        NOTIFICATION_TYPES["FEEDBACK_REQUESTED"],
        "Feedback requested",
        f"How satisfied are you with the resolution of {complaint['id']}?",
        complaint["id"],
    )


def complaint_reopened(complaint: dict, reason: str = "") -> None:
    officer = complaint.get("assignedOfficer")
    if officer:
        create(
            officer["id"],
            NOTIFICATION_TYPES["STATUS_CHANGED"],
            "Complaint reopened",
            f"{complaint['id']} was reopened by the complainant. {reason}".strip(),
            complaint["id"],
        )


def complaint_escalated(complaint: dict, level: int, authority: str) -> None:
    recipients = [complaint["submittedBy"]["id"]]
    if complaint.get("assignedOfficer"):
        recipients.append(complaint["assignedOfficer"]["id"])

    create_many(
        recipients,
        NOTIFICATION_TYPES["ESCALATED"],
        f"Complaint escalated to level {level}",
        f"{complaint['id']} has been escalated to {authority} after crossing its deadline.",
        complaint["id"],
    )


def deadline_approaching(complaint: dict, days_left: int) -> None:
    officer = complaint.get("assignedOfficer")
    if officer:
        create(
            officer["id"],
            NOTIFICATION_TYPES["DEADLINE_APPROACHING"],
            "Deadline approaching",
            f"{complaint['id']} is due in {days_left} day(s).",
            complaint["id"],
        )
