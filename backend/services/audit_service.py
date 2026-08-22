"""
Audit logging.

Every consequential action is recorded: who did it, what they did, which
complaint it touched and when. Writes are best-effort - an audit failure must
never abort the operation the user asked for.
"""

import logging

from flask import request

from database import audit_logs
from utils.helpers import iso, uid, utcnow

logger = logging.getLogger(__name__)

# Action names used across the system.
LOGIN = "login"
LOGIN_FAILED = "login_failed"
LOGOUT = "logout"
REGISTER = "register"
PASSWORD_CHANGED = "password_changed"
OTP_SENT = "otp_sent"
OTP_VERIFIED = "otp_verified"
COMPLAINT_CREATED = "complaint_created"
STATUS_CHANGED = "status_changed"
COMPLAINT_ASSIGNED = "complaint_assigned"
COMPLAINT_REASSIGNED = "complaint_reassigned"
REMARK_ADDED = "remark_added"
COMPLAINT_RESOLVED = "complaint_resolved"
COMPLAINT_CLOSED = "complaint_closed"
COMPLAINT_REOPENED = "complaint_reopened"
COMPLAINT_ESCALATED = "complaint_escalated"
PRIORITY_CHANGED = "priority_changed"
FEEDBACK_SUBMITTED = "feedback_submitted"
FILE_UPLOADED = "file_uploaded"
ADMIN_CHANGE = "admin_change"


def client_ip() -> str:
    """Caller IP, honouring one proxy hop."""
    if not request:
        return ""
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or ""


def log(action: str, user: dict = None, description: str = "", complaint_id: str = None, meta: dict = None) -> None:
    """Record one audit entry. Swallows its own errors by design."""
    try:
        entry = {
            "id": uid("LOG", 10),
            "action": action,
            "userId": (user or {}).get("id"),
            "userName": (user or {}).get("name"),
            "userEmail": (user or {}).get("email"),
            "role": (user or {}).get("role"),
            "complaintId": complaint_id,
            "description": description,
            "meta": meta or {},
            "at": iso(utcnow()),
        }
        try:
            entry["ip"] = client_ip()
            entry["userAgent"] = (request.headers.get("User-Agent", "")[:200]) if request else ""
        except RuntimeError:
            entry["ip"] = ""  # outside a request context (e.g. the scheduler)
            entry["userAgent"] = ""

        audit_logs().insert_one(entry)
    except Exception as exc:
        logger.warning("Audit log failed for action=%s: %s", action, exc)


def get_logs(filters: dict = None, page: int = 1, page_size: int = 50) -> dict:
    """Paginated audit trail for the admin screens."""
    filters = filters or {}
    query = {}

    if filters.get("action"):
        query["action"] = filters["action"]
    if filters.get("userId"):
        query["userId"] = filters["userId"]
    if filters.get("complaintId"):
        query["complaintId"] = filters["complaintId"]
    if filters.get("role"):
        query["role"] = filters["role"]

    total = audit_logs().count_documents(query)
    page_size = max(1, min(page_size, 200))
    total_pages = max((total + page_size - 1) // page_size, 1)
    page = max(1, min(page, total_pages))

    cursor = (
        audit_logs()
        .find(query, {"_id": 0})
        .sort("at", -1)
        .skip((page - 1) * page_size)
        .limit(page_size)
    )

    return {
        "items": list(cursor),
        "total": total,
        "page": page,
        "pageSize": page_size,
        "totalPages": total_pages,
    }
