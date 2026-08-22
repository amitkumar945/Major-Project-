"""
Department master data with live complaint counters.

Returns the same enriched shape `getDepartments()` produced: the static
department record plus officerCount, totalComplaints, resolvedComplaints,
pendingComplaints, escalatedComplaints and resolutionRate.
"""

from constants import CLOSED_STATUSES, ROLE_OFFICER, STATUS_ESCALATED
from database import complaints, departments, users
from services import audit_service
from utils.helpers import clean_document, iso, uid, utcnow
from utils.responses import ApiException

PROJECTION = {"_id": 0}


def _counters() -> dict:
    """One aggregation for every department's complaint counts."""
    pipeline = [
        {
            "$group": {
                "_id": "$department",
                "total": {"$sum": 1},
                "resolved": {"$sum": {"$cond": [{"$in": ["$status", CLOSED_STATUSES]}, 1, 0]}},
                "escalated": {"$sum": {"$cond": [{"$eq": ["$status", STATUS_ESCALATED]}, 1, 0]}},
            }
        }
    ]
    return {row["_id"]: row for row in complaints().aggregate(pipeline)}


def _officer_counts() -> dict:
    pipeline = [
        {"$match": {"role": ROLE_OFFICER, "isActive": True}},
        {"$group": {"_id": "$department", "count": {"$sum": 1}}},
    ]
    return {row["_id"]: row["count"] for row in users().aggregate(pipeline)}


def get_departments(active_only: bool = False) -> list:
    query = {"isActive": True} if active_only else {}
    records = list(departments().find(query, PROJECTION))

    counters = _counters()
    officer_counts = _officer_counts()

    result = []
    for department in records:
        stats = counters.get(department["name"], {})
        total = stats.get("total", 0)
        resolved = stats.get("resolved", 0)

        department["officerCount"] = officer_counts.get(department["name"], 0)
        department["totalComplaints"] = total
        department["resolvedComplaints"] = resolved
        department["pendingComplaints"] = total - resolved
        department["escalatedComplaints"] = stats.get("escalated", 0)
        department["resolutionRate"] = round(resolved / total * 100) if total else 0
        result.append(clean_document(department))

    return result


def get_by_code(code: str) -> dict:
    for department in get_departments():
        if department["code"] == (code or "").strip().upper():
            return department
    raise ApiException("Department not found.", 404)


def create_department(values: dict, actor: dict = None) -> dict:
    code = (values.get("code") or "").strip().upper()
    if departments().find_one({"code": code}):
        raise ApiException("A department with this code already exists.", 409)
    if departments().find_one({"name": (values.get("name") or "").strip()}):
        raise ApiException("A department with this name already exists.", 409)

    record = {
        "id": uid("DEP"),
        "code": code,
        "name": (values.get("name") or "").strip(),
        "english": (values.get("english") or "").strip(),
        "description": (values.get("description") or "").strip(),
        "head": (values.get("head") or "").strip(),
        "email": (values.get("email") or "").strip().lower(),
        "office": (values.get("office") or "").strip(),
        "color": values.get("color") or "slate",
        "establishedYear": values.get("establishedYear") or utcnow().year,
        "isActive": True,
        "createdAt": iso(utcnow()),
    }

    departments().insert_one(record)
    audit_service.log(audit_service.ADMIN_CHANGE, actor, f"Department '{record['name']}' created.")
    return clean_document(record)


# Fields an admin may edit. `code` is the key other records reference, so it is
# deliberately not editable.
EDITABLE_FIELDS = ("name", "english", "description", "head", "email", "office", "color", "establishedYear", "isActive")


def update_department(code: str, changes: dict, actor: dict = None) -> dict:
    updates = {k: v for k, v in (changes or {}).items() if k in EDITABLE_FIELDS}
    if not updates:
        raise ApiException("There is nothing to update.", 400)

    updates["updatedAt"] = iso(utcnow())
    result = departments().find_one_and_update(
        {"code": (code or "").strip().upper()}, {"$set": updates},
        projection=PROJECTION, return_document=True,
    )
    if not result:
        raise ApiException("Department not found.", 404)

    audit_service.log(audit_service.ADMIN_CHANGE, actor, f"Department '{result['name']}' updated.")
    return clean_document(result)


def delete_department(code: str, actor: dict = None) -> dict:
    code = (code or "").strip().upper()
    target = departments().find_one({"code": code}, PROJECTION)
    if not target:
        raise ApiException("Department not found.", 404)

    # Refuse while complaints still point at it - the same guard the frontend had.
    outstanding = complaints().count_documents({"department": target["name"]})
    if outstanding:
        raise ApiException(
            f"{target['name']} still has {outstanding} complaint(s). "
            "Reassign them before deleting the department.",
            409,
        )

    officer_count = users().count_documents({"role": ROLE_OFFICER, "department": target["name"]})
    if officer_count:
        raise ApiException(
            f"{target['name']} still has {officer_count} officer(s) assigned. "
            "Move them to another department first.",
            409,
        )

    departments().delete_one({"code": code})
    audit_service.log(audit_service.ADMIN_CHANGE, actor, f"Department '{target['name']}' deleted.")
    return {"success": True}


def toggle_active(code: str, actor: dict = None) -> dict:
    target = departments().find_one({"code": (code or "").strip().upper()}, PROJECTION)
    if not target:
        raise ApiException("Department not found.", 404)
    return update_department(code, {"isActive": not target.get("isActive", True)}, actor)
