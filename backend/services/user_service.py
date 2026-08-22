"""
User directory for the admin screens.

Students and staff are returned with their complaint counts attached, matching
what `getUsers()` produced. Password hashes are projected out everywhere.
"""

from constants import ACTIVE_STATUSES, ROLE_ADMIN, ROLE_OFFICER, ROLE_STUDENT
from database import complaints, users
from utils.helpers import clean_document
from utils.responses import ApiException

SAFE_PROJECTION = {"_id": 0, "passwordHash": 0}


def get_users(search: str = "", user_type: str = "", department: str = "", role: str = ROLE_STUDENT) -> list:
    """Directory with per-user complaint counters."""
    query = {}
    if role:
        query["role"] = role
    if user_type:
        query["userType"] = user_type
    if department:
        query["department"] = department

    people = list(users().find(query, SAFE_PROJECTION))

    # Counts for everyone in one aggregation.
    pipeline = [
        {
            "$group": {
                "_id": "$submittedBy.id",
                "complaintCount": {"$sum": 1},
                "activeComplaints": {"$sum": {"$cond": [{"$in": ["$status", ACTIVE_STATUSES]}, 1, 0]}},
                "lastComplaintAt": {"$max": "$submittedAt"},
            }
        }
    ]
    counts = {row["_id"]: row for row in complaints().aggregate(pipeline)}

    result = []
    for person in people:
        stats = counts.get(person["id"], {})
        person["complaintCount"] = stats.get("complaintCount", 0)
        person["activeComplaints"] = stats.get("activeComplaints", 0)
        person["lastComplaintAt"] = stats.get("lastComplaintAt")
        result.append(clean_document(person))

    if search.strip():
        term = search.strip().lower()
        result = [
            person for person in result
            if term in " ".join(
                str(person.get(field, "")) for field in ("name", "userId", "email", "department")
            ).lower()
        ]

    return result


def get_user(user_id: str) -> dict:
    person = users().find_one({"id": user_id}, SAFE_PROJECTION)
    if not person:
        raise ApiException("User not found.", 404)
    return clean_document(person)


def get_summary() -> dict:
    """Headline counts for the admin "Students & Staff" page."""
    return {
        "total": users().count_documents({}),
        "students": users().count_documents({"role": ROLE_STUDENT, "userType": "Student"}),
        "staff": users().count_documents({"role": ROLE_STUDENT, "userType": "Staff"}),
        "officers": users().count_documents({"role": ROLE_OFFICER}),
        "admins": users().count_documents({"role": ROLE_ADMIN}),
        "active": users().count_documents({"isActive": True}),
    }
