"""
Analytics routes feeding the dashboard and analytics charts.

Data comes back in the `[{name, value}]` shape the existing SVG chart helpers
already consume, so `charts.js` needed no changes.
"""

from flask import Blueprint, Response, request

from constants import ROLE_ADMIN, ROLE_OFFICER, ROLE_STUDENT
from services import analytics_service, export_service
from utils.jwt_utils import (
    current_user,
    jwt_required,
    jwt_required_allow_query,
    role_required,
)
from utils.responses import success

bp = Blueprint("analytics", __name__, url_prefix="/api/analytics")


def _scope_for(user: dict) -> dict:
    """A student sees only their own numbers, an officer their own queue."""
    if user["role"] == ROLE_STUDENT:
        return {"userId": user["id"]}
    if user["role"] == ROLE_OFFICER:
        department = request.args.get("department")
        return {"department": department} if department else {"officerId": user["id"]}

    scope = {}
    if request.args.get("department"):
        scope["department"] = request.args["department"]
    if request.args.get("officerId"):
        scope["officerId"] = request.args["officerId"]
    return scope


@bp.get("/charts")
@jwt_required
def charts():
    """The three charts on every dashboard."""
    return success(analytics_service.dashboard_charts(_scope_for(current_user())))


@bp.get("/summary")
@jwt_required
def summary():
    """Headline metrics, scoped to the caller."""
    items = analytics_service._scoped(_scope_for(current_user()))
    return success(analytics_service.key_metrics(items))


@bp.get("/overview")
@role_required(ROLE_ADMIN)
def overview():
    """Everything the admin analytics page renders."""
    return success(analytics_service.analytics_overview())


@bp.get("/departments")
@jwt_required
def departments():
    items = analytics_service._scoped(_scope_for(current_user()))
    return success(
        {
            "distribution": analytics_service.department_distribution(items),
            "performance": analytics_service.department_performance(items),
            "resolutionTime": analytics_service.resolution_time_by_department(items),
        }
    )


@bp.get("/status")
@jwt_required
def status():
    items = analytics_service._scoped(_scope_for(current_user()))
    return success(analytics_service.status_distribution(items))


@bp.get("/priority")
@jwt_required
def priority():
    items = analytics_service._scoped(_scope_for(current_user()))
    return success(analytics_service.priority_distribution(items))


@bp.get("/officers")
@role_required(ROLE_ADMIN, ROLE_OFFICER)
def officers():
    return success(analytics_service.officer_performance())


@bp.get("/sla")
@role_required(ROLE_ADMIN)
def sla():
    return success(analytics_service.sla_report())


@bp.get("/trend")
@jwt_required
def trend():
    items = analytics_service._scoped(_scope_for(current_user()))
    return success(
        {
            "monthly": analytics_service.monthly_trend(items),
            "weekly": analytics_service.weekly_load(items),
        }
    )


@bp.get("/export")
@jwt_required_allow_query
def export_summary():
    """Download the headline analytics figures as CSV.

    Scoped exactly like the charts: a student exports their own numbers, an
    officer their queue, an admin the whole institution.
    """
    csv_text = export_service.analytics_csv(_scope_for(current_user()))
    return Response(
        "﻿" + csv_text,
        mimetype="text/csv",
        headers={
            "Content-Disposition":
                f'attachment; filename="{export_service.filename("analytics")}"'
        },
    )
