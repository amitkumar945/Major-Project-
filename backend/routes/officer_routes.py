"""
Officer routes: directory, workload, per-officer queues and admin management.
"""

from flask import Blueprint, request

from constants import ROLE_ADMIN, ROLE_OFFICER
from services import assignment_service, audit_service, auth_service, complaint_service
from utils.helpers import to_bool, to_int
from utils.jwt_utils import current_user, jwt_required, role_required
from utils.responses import ApiException, error, maybe_paginated, success, validation_error
from utils.validators import validate_officer

bp = Blueprint("officers", __name__, url_prefix="/api/officers")


@bp.get("")
@jwt_required
def list_officers():
    """Officer directory with live workload figures.

    Returns a bare array by default - the admin and complaint-details screens
    spread and sort it directly - or the standard paginated envelope when the
    caller sends `?page=` / `?pageSize=`.
    """
    officers = assignment_service.get_officers(
        department=request.args.get("department", ""),
        active_only=to_bool(request.args.get("activeOnly"), False),
        search=request.args.get("search", ""),
    )
    return success(maybe_paginated(officers, request.args))


@bp.get("/suggest")
@role_required(ROLE_ADMIN, ROLE_OFFICER)
def suggest():
    """The least-loaded active officer in a department."""
    department = request.args.get("department", "")
    if not department:
        return validation_error({"department": "Specify a department."})

    officer = assignment_service.suggest_officer(department)
    if not officer:
        return error(f"{department} has no active officer to assign.", 404)
    return success(officer)


@bp.get("/<officer_id>")
@jwt_required
def get_officer(officer_id):
    return success(assignment_service.get_officer(officer_id))


@bp.get("/<officer_id>/complaints")
@role_required(ROLE_ADMIN, ROLE_OFFICER)
def officer_complaints(officer_id):
    """One officer's queue. An officer may only read their own."""
    user = current_user()
    if user["role"] == ROLE_OFFICER and user["id"] != officer_id:
        return error("You can only view your own complaint queue.", 403)

    filters = {
        "officerId": officer_id,
        "status": request.args.get("status", ""),
        "priority": request.args.get("priority", ""),
        "search": request.args.get("search", ""),
        "onlyActive": to_bool(request.args.get("onlyActive"), False),
        "sortBy": request.args.get("sortBy", "submittedAt"),
        "sortDir": request.args.get("sortDir", "desc"),
        "page": to_int(request.args.get("page"), 1),
        "pageSize": to_int(request.args.get("pageSize"), 10),
    }
    return success(complaint_service.get_complaints(filters, user))


@bp.get("/<officer_id>/workload")
@role_required(ROLE_ADMIN, ROLE_OFFICER)
def workload(officer_id):
    officer = assignment_service.get_officer(officer_id)
    return success({"officerId": officer_id, "name": officer["name"], **officer["workload"]})


# ------------------------------------------------------------- admin actions


@bp.post("")
@role_required(ROLE_ADMIN)
def create_officer():
    """Create an officer account. A password is required so they can sign in."""
    values = request.get_json(silent=True) or {}

    errors = validate_officer(values)
    password = values.get("password") or ""
    if not password:
        errors["password"] = "Set an initial password for this officer"
    elif len(password) < 8:
        errors["password"] = "Password must be at least 8 characters"
    if errors:
        return validation_error(errors)

    officer = auth_service.register(
        {**values, "role": ROLE_OFFICER, "fullName": values.get("name"), "userId": values.get("employeeId")},
        created_by=current_user(),
    )
    return success(officer, "Officer account created.", 201)


@bp.put("/<officer_id>")
@role_required(ROLE_ADMIN)
def update_officer(officer_id):
    from database import users

    changes = request.get_json(silent=True) or {}
    allowed = ("name", "designation", "department", "mobile", "employeeId", "avatarColor")
    updates = {key: value for key, value in changes.items() if key in allowed}
    if not updates:
        return validation_error({"_": "There is nothing to update."})

    from utils.helpers import clean_document, iso, utcnow

    updates["updatedAt"] = iso(utcnow())
    result = users().find_one_and_update(
        {"id": officer_id, "role": ROLE_OFFICER},
        {"$set": updates},
        projection={"_id": 0, "passwordHash": 0},
        return_document=True,
    )
    if not result:
        return error("Officer not found.", 404)

    audit_service.log(audit_service.ADMIN_CHANGE, current_user(), f"Officer {officer_id} updated.")
    return success(clean_document(result), "Officer updated.")


@bp.put("/<officer_id>/status")
@role_required(ROLE_ADMIN)
def toggle_status(officer_id):
    """Activate or deactivate. Deactivation is refused while work is open -
    the same guard the frontend enforced."""
    officer = assignment_service.get_officer(officer_id)
    is_active = officer.get("isActive", True)

    if is_active:
        outstanding = assignment_service.active_workload(officer_id)
        if outstanding:
            return error(
                f"{officer['name']} has {outstanding} active complaint(s). "
                "Reassign them before deactivating this account.",
                409,
            )

    updated = auth_service.set_active(officer_id, not is_active, current_user())
    return success(updated, f"Officer {'activated' if not is_active else 'deactivated'}.")
