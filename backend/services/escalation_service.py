"""
SLA monitoring and automatic escalation.

Priority sets the deadline (Urgent 1 day, High 3, Medium 7, Low 14). Once a
deadline passes, the complaint escalates up a three-level ladder and everyone
involved is notified.

`run_sla_check()` is idempotent - re-running it does not re-escalate a
complaint that is already at the right level - so it is safe to call from a
scheduler, from the admin screen, or on every request in a small deployment.
"""

import logging

from constants import ACTIVE_STATUSES, ESCALATION_LEVELS, STATUS_ESCALATED
from database import complaints
from services import audit_service, notification_service
from utils.helpers import (
    clean_document,
    days_until,
    escalation_authority,
    escalation_level_for_overdue,
    iso,
    uid,
    utcnow,
)

logger = logging.getLogger(__name__)

# Warn the officer this many days before the deadline.
WARNING_DAYS = 1


def sla_status(complaint: dict) -> dict:
    """Where one complaint stands against its deadline."""
    if not complaint.get("deadline"):
        return {"state": "unknown", "days": 0}

    if complaint.get("status") not in ACTIVE_STATUSES:
        return {"state": "met", "days": 0}

    remaining = days_until(complaint["deadline"])
    if remaining < 0:
        return {"state": "breached", "days": abs(remaining)}
    if remaining <= WARNING_DAYS:
        return {"state": "due-soon", "days": remaining}
    return {"state": "on-track", "days": remaining}


def _escalate(complaint: dict, level: int, authority: str, days_overdue: int) -> dict:
    """Move one complaint up the ladder and record it."""
    entry = {
        "id": uid("tl"),
        "key": "escalated",
        "label": f"Escalated to Level {level}",
        "description": (
            f"Resolution deadline exceeded by {days_overdue} day(s); "
            f"the complaint moved to {authority}."
        ),
        "actor": "SLA Monitor",
        "at": iso(utcnow()),
        "state": "current",
        "variant": "danger",
    }

    updated = complaints().find_one_and_update(
        {"id": complaint["id"]},
        {
            "$set": {
                "status": STATUS_ESCALATED,
                "escalationLevel": level,
                "escalationAuthority": authority,
                "escalatedAt": iso(utcnow()),
                "escalationReason": f"SLA breached by {days_overdue} day(s).",
                "daysOverdue": days_overdue,
                "updatedAt": iso(utcnow()),
            },
            "$push": {"timeline": entry},
        },
        projection={"_id": 0},
        return_document=True,
    )
    result = clean_document(updated)

    notification_service.complaint_escalated(result, level, authority)
    audit_service.log(
        audit_service.COMPLAINT_ESCALATED,
        None,
        f"Automatic escalation: {complaint['id']} reached level {level} ({authority}).",
        complaint_id=complaint["id"],
        meta={"daysOverdue": days_overdue, "automatic": True},
    )
    return result


def run_sla_check(notify_due_soon: bool = True) -> dict:
    """Scan every open complaint, escalate the breached ones, warn on the rest.

    Returns a summary the admin screen can display.
    """
    checked = escalated = warned = 0
    escalated_ids = []

    for complaint in complaints().find({"status": {"$in": ACTIVE_STATUSES}}, {"_id": 0}):
        checked += 1
        state = sla_status(complaint)

        if state["state"] == "breached":
            days_overdue = state["days"]
            target_level = escalation_level_for_overdue(days_overdue)
            current_level = complaint.get("escalationLevel") or 0

            # Only act when the ladder says a *higher* level is due.
            if target_level > current_level:
                _escalate(complaint, target_level, escalation_authority(target_level), days_overdue)
                escalated += 1
                escalated_ids.append(complaint["id"])

        elif state["state"] == "due-soon" and notify_due_soon:
            # Warn once per complaint, not on every scan.
            if not complaint.get("deadlineWarningSent"):
                notification_service.deadline_approaching(complaint, state["days"])
                complaints().update_one(
                    {"id": complaint["id"]}, {"$set": {"deadlineWarningSent": True}}
                )
                warned += 1

    logger.info("SLA check: %s checked, %s escalated, %s warned.", checked, escalated, warned)
    return {
        "checked": checked,
        "escalated": escalated,
        "warned": warned,
        "escalatedIds": escalated_ids,
        "at": iso(utcnow()),
    }


def get_sla_report() -> dict:
    """SLA breakdown for the analytics dashboard."""
    open_complaints = list(complaints().find({"status": {"$in": ACTIVE_STATUSES}}, {"_id": 0}))
    closed_complaints = list(complaints().find({"status": {"$in": ["Resolved", "Closed"]}}, {"_id": 0}))

    buckets = {"on-track": 0, "due-soon": 0, "breached": 0}
    for complaint in open_complaints:
        state = sla_status(complaint)["state"]
        if state in buckets:
            buckets[state] += 1

    # Of the finished complaints, how many beat their deadline?
    met = 0
    for complaint in closed_complaints:
        resolved_at, deadline = complaint.get("resolvedAt"), complaint.get("deadline")
        if resolved_at and deadline and resolved_at <= deadline:
            met += 1

    total_closed = len(closed_complaints)
    return {
        "open": len(open_complaints),
        "onTrack": buckets["on-track"],
        "dueSoon": buckets["due-soon"],
        "breached": buckets["breached"],
        "closed": total_closed,
        "metDeadline": met,
        "missedDeadline": total_closed - met,
        "complianceRate": round((met / total_closed) * 100) if total_closed else 0,
        "levels": ESCALATION_LEVELS,
    }
