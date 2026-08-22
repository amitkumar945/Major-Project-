"""
Officer assignment.

Automatic assignment picks the active officer in the target department with the
smallest live workload - the same rule the frontend's "smart assignment" used,
now computed from real complaint counts rather than seeded statistics.

Every assignment is also written to the `assignments` collection, which gives
the admin a history of who held a complaint and when.
"""

from constants import ACTIVE_STATUSES, ROLE_OFFICER
from database import assignments, complaints, users
from utils.helpers import clean_document, iso, uid, utcnow
from utils.responses import ApiException

OFFICER_PROJECTION = {"_id": 0, "passwordHash": 0}


def _officer_summary(officer: dict) -> dict:
    """The compact officer reference stored on a complaint document.

    Field-for-field what the frontend's `handler()` produced, so
    `complaint.assignedOfficer` renders unchanged.
    """
    if not officer:
        return None
    return {
        "id": officer["id"],
        "name": officer.get("name", ""),
        "designation": officer.get("designation", ""),
        "department": officer.get("department", ""),
        "email": officer.get("email", ""),
        "employeeId": officer.get("employeeId", ""),
    }


def active_workload(officer_id: str) -> int:
    """How many still-open complaints this officer currently holds."""
    return complaints().count_documents(
        {"assignedOfficer.id": officer_id, "status": {"$in": ACTIVE_STATUSES}}
    )


def get_officers(department: str = "", active_only: bool = False, search: str = "") -> list:
    """Officer directory with live workload figures attached."""
    query = {"role": ROLE_OFFICER}
    if department:
        query["department"] = department
    if active_only:
        query["isActive"] = True

    officers = list(users().find(query, OFFICER_PROJECTION))

    # One aggregation for every officer's counts, instead of N queries.
    pipeline = [
        {"$match": {"assignedOfficer.id": {"$ne": None}}},
        {
            "$group": {
                "_id": "$assignedOfficer.id",
                "assignedNow": {"$sum": 1},
                "active": {
                    "$sum": {"$cond": [{"$in": ["$status", ACTIVE_STATUSES]}, 1, 0]}
                },
                "resolved": {
                    "$sum": {"$cond": [{"$in": ["$status", ["Resolved", "Closed"]]}, 1, 0]}
                },
            }
        },
    ]
    counts = {row["_id"]: row for row in complaints().aggregate(pipeline)}

    result = []
    for officer in officers:
        stats = officer.get("stats") or {}
        live = counts.get(officer["id"], {})
        officer["workload"] = {
            "active": live.get("active", 0),
            "assignedNow": live.get("assignedNow", 0),
            "resolvedTotal": live.get("resolved", 0) + stats.get("resolved", 0),
            "avgResolutionDays": stats.get("avgResolutionDays", 0),
            "rating": stats.get("rating", 0),
        }
        result.append(clean_document(officer))

    if search.strip():
        term = search.strip().lower()
        result = [
            officer for officer in result
            if term in " ".join(
                str(officer.get(field, "")) for field in ("name", "employeeId", "email", "designation")
            ).lower()
        ]

    return result


def get_officer(officer_id: str) -> dict:
    officer = users().find_one({"id": officer_id, "role": ROLE_OFFICER}, OFFICER_PROJECTION)
    if not officer:
        raise ApiException("Officer not found.", 404)

    officer["workload"] = {
        "active": active_workload(officer_id),
        "assignedNow": complaints().count_documents({"assignedOfficer.id": officer_id}),
        "resolvedTotal": complaints().count_documents(
            {"assignedOfficer.id": officer_id, "status": {"$in": ["Resolved", "Closed"]}}
        ),
        "avgResolutionDays": (officer.get("stats") or {}).get("avgResolutionDays", 0),
        "rating": (officer.get("stats") or {}).get("rating", 0),
    }
    return clean_document(officer)


def suggest_officer(department: str) -> dict:
    """The active officer in `department` with the lightest live workload.

    Returns None when the department has no active officer, which the caller
    must handle - a complaint can legitimately arrive unassigned.
    """
    candidates = get_officers(department=department, active_only=True)
    if not candidates:
        return None
    return min(candidates, key=lambda officer: officer["workload"]["active"])


def auto_assign(complaint: dict) -> dict:
    """Choose an officer for a new complaint. Returns the summary or None."""
    officer = suggest_officer(complaint.get("department", ""))
    return _officer_summary(officer) if officer else None


def record_assignment(complaint_id: str, officer: dict, actor: dict = None, reason: str = "", previous_officer_id: str = None) -> dict:
    """Append to the assignment history collection."""
    entry = {
        "id": uid("ASG", 10),
        "complaintId": complaint_id,
        "officerId": (officer or {}).get("id"),
        "officerName": (officer or {}).get("name"),
        "department": (officer or {}).get("department"),
        "previousOfficerId": previous_officer_id,
        "assignedBy": (actor or {}).get("id"),
        "assignedByName": (actor or {}).get("name"),
        "assignedByRole": (actor or {}).get("role"),
        "reason": reason,
        "type": "reassignment" if previous_officer_id else "assignment",
        "at": iso(utcnow()),
    }
    assignments().insert_one(entry)
    return clean_document(entry)


def assignment_history(complaint_id: str) -> list:
    return list(assignments().find({"complaintId": complaint_id}, {"_id": 0}).sort("at", 1))


def officer_summary_by_id(officer_id: str) -> dict:
    """Look up an officer and return the compact complaint-facing summary."""
    officer = users().find_one({"id": officer_id, "role": ROLE_OFFICER}, OFFICER_PROJECTION)
    if not officer:
        raise ApiException("Selected officer was not found.", 404)
    if officer.get("isActive") is False:
        raise ApiException(f"{officer.get('name')} is deactivated and cannot take new complaints.", 409)
    return _officer_summary(officer)
