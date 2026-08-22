"""
Admin-only routes: analytics, SLA control, audit log and system status.

Everything here is behind @role_required("admin").
"""

from flask import Blueprint, current_app, request

from constants import ROLE_ADMIN
from services import analytics_service, audit_service, escalation_service
from utils.helpers import to_int
from utils.jwt_utils import current_user, role_required
from utils.responses import success

bp = Blueprint("admin", __name__, url_prefix="/api/admin")


@bp.get("/dashboard")
@role_required(ROLE_ADMIN)
def dashboard():
    """Headline metrics plus the four dashboard charts, in one call."""
    charts = analytics_service.dashboard_charts()
    return success(
        {
            "metrics": analytics_service.key_metrics(analytics_service._scoped()),
            **charts,
            "sla": escalation_service.get_sla_report(),
        }
    )


@bp.get("/audit-logs")
@role_required(ROLE_ADMIN)
def audit_logs():
    return success(
        audit_service.get_logs(
            filters={
                "action": request.args.get("action", ""),
                "userId": request.args.get("userId", ""),
                "complaintId": request.args.get("complaintId", ""),
                "role": request.args.get("role", ""),
            },
            page=to_int(request.args.get("page"), 1),
            page_size=to_int(request.args.get("pageSize"), 50),
        )
    )


@bp.post("/sla-check")
@role_required(ROLE_ADMIN)
def run_sla_check():
    """Run the SLA sweep on demand: escalate breaches, warn on due-soon."""
    result = escalation_service.run_sla_check()
    audit_service.log(
        audit_service.ADMIN_CHANGE, current_user(),
        f"SLA check run: {result['escalated']} escalated, {result['warned']} warned.",
    )
    return success(result, f"SLA check complete. {result['escalated']} complaint(s) escalated.")


@bp.get("/sla")
@role_required(ROLE_ADMIN)
def sla_report():
    return success(escalation_service.get_sla_report())


@bp.post("/reset-data")
@role_required(ROLE_ADMIN)
def reset_data():
    """Delete every complaint, notification, rating and assignment.

    DESTRUCTIVE and irreversible. User accounts and departments are kept, so
    the system stays usable afterwards. Requires an explicit `confirm: true`
    in the body so it can never fire on a stray request.
    """
    from database import assignments, complaints, feedback, notifications

    values = request.get_json(silent=True) or {}
    if values.get("confirm") is not True:
        return (
            {
                "success": False,
                "message": 'This action deletes all complaint data. Send {"confirm": true} to proceed.',
                "error": {"confirmationRequired": True},
            },
            400,
        )

    removed = {
        "complaints": complaints().delete_many({}).deleted_count,
        "notifications": notifications().delete_many({}).deleted_count,
        "feedback": feedback().delete_many({}).deleted_count,
        "assignments": assignments().delete_many({}).deleted_count,
    }

    audit_service.log(
        audit_service.ADMIN_CHANGE,
        current_user(),
        f"All complaint data deleted: {removed}.",
        meta=removed,
    )
    return success(removed, "All complaint data has been deleted.")


@bp.get("/settings")
@role_required(ROLE_ADMIN)
def settings():
    """Non-secret configuration the admin settings screen displays.

    Deliberately excludes MONGO_URI and JWT_SECRET_KEY.
    """
    from constants import ESCALATION_LEVELS, PRIORITY_SLA_DAYS

    return success(
        {
            "slaDays": PRIORITY_SLA_DAYS,
            "escalationLevels": ESCALATION_LEVELS,
            "upload": {
                "maxFileSizeMB": round(current_app.config["MAX_FILE_SIZE"] / (1024 * 1024)),
                "maxFiles": current_app.config["MAX_FILES_PER_REQUEST"],
            },
            "otp": {
                "expirySeconds": current_app.config["OTP_EXPIRY"],
                "devMode": current_app.config["OTP_DEV_MODE"],
                "requiredForRegister": current_app.config["OTP_REQUIRED_FOR_REGISTER"],
            },
            "ocr": {
                "enabled": current_app.config["OCR_ENABLED"],
                "engine": current_app.config["OCR_ENGINE"],
            },
            "ai": {"modelTrained": False, "method": "rule-based"},
        }
    )
