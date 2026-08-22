"""
User routes: the students/staff directory used by the admin screens.
"""

from flask import Blueprint, request

from constants import ROLE_ADMIN, ROLE_STUDENT
from services import auth_service, user_service
from utils.jwt_utils import current_user, jwt_required, role_required
from utils.responses import error, success

bp = Blueprint("users", __name__, url_prefix="/api/users")


@bp.get("")
@role_required(ROLE_ADMIN)
def list_users():
    return success(
        user_service.get_users(
            search=request.args.get("search", ""),
            user_type=request.args.get("userType", ""),
            department=request.args.get("department", ""),
            role=request.args.get("role", ROLE_STUDENT),
        )
    )


@bp.get("/summary")
@role_required(ROLE_ADMIN)
def summary():
    return success(user_service.get_summary())


@bp.get("/<user_id>")
@jwt_required
def get_user(user_id):
    """A user may read their own profile; only an admin may read anyone else's."""
    actor = current_user()
    if actor["id"] != user_id and actor["role"] != ROLE_ADMIN:
        return error("You do not have permission to view this profile.", 403)
    return success(user_service.get_user(user_id))


@bp.put("/<user_id>/status")
@role_required(ROLE_ADMIN)
def toggle_status(user_id):
    person = user_service.get_user(user_id)

    # An admin must not be able to lock themselves out.
    if person["id"] == current_user()["id"]:
        return error("You cannot deactivate your own account.", 409)

    updated = auth_service.set_active(user_id, not person.get("isActive", True), current_user())
    return success(updated, f"Account {'activated' if updated['isActive'] else 'deactivated'}.")


@bp.post("")
@role_required(ROLE_ADMIN)
def create_user():
    """Create a student/staff account from the admin screen."""
    from utils.validators import validate_registration
    from utils.responses import validation_error

    values = request.get_json(silent=True) or {}
    errors = validate_registration(values)
    if errors:
        return validation_error(errors)

    user = auth_service.register(values, created_by=current_user())
    return success(user, "Account created.", 201)
