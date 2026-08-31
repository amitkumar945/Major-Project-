"""
Department routes: master list with live counters, plus admin CRUD.

The list is public (the landing page shows the four departments to anonymous
visitors); every write requires an administrator.
"""

from flask import Blueprint, request

from constants import ROLE_ADMIN
from services import department_service
from utils.helpers import to_bool
from utils.jwt_utils import current_user, role_required
from utils.responses import maybe_paginated, success, validation_error
from utils.validators import validate_department

bp = Blueprint("departments", __name__, url_prefix="/api/departments")


@bp.get("")
def list_departments():
    """Public: the landing page renders this before anyone signs in.

    Bare array by default; paginated envelope on `?page=` / `?pageSize=`.
    """
    items = department_service.get_departments(
        active_only=to_bool(request.args.get("activeOnly"), False)
    )
    return success(maybe_paginated(items, request.args))


@bp.get("/<code>")
def get_department(code):
    return success(department_service.get_by_code(code))


@bp.post("")
@role_required(ROLE_ADMIN)
def create_department():
    values = request.get_json(silent=True) or {}

    errors = validate_department(values)
    if errors:
        return validation_error(errors)

    department = department_service.create_department(values, current_user())
    return success(department, "Department created.", 201)


@bp.put("/<code>")
@role_required(ROLE_ADMIN)
def update_department(code):
    changes = request.get_json(silent=True) or {}
    department = department_service.update_department(code, changes, current_user())
    return success(department, "Department updated.")


@bp.delete("/<code>")
@role_required(ROLE_ADMIN)
def delete_department(code):
    return success(department_service.delete_department(code, current_user()), "Department deleted.")


@bp.put("/<code>/status")
@role_required(ROLE_ADMIN)
def toggle_status(code):
    department = department_service.toggle_active(code, current_user())
    return success(department, f"Department {'activated' if department['isActive'] else 'deactivated'}.")
