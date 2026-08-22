"""
Feedback routes.

Submitting feedback lives on the complaint (`POST /api/complaints/<id>/feedback`);
these endpoints read it back for the student's feedback page and the admin
analytics screen.
"""

from flask import Blueprint, request

from constants import ACTIVE_STATUSES, CLOSED_STATUSES, ROLE_ADMIN
from database import complaints, feedback as feedback_collection
from services import analytics_service
from utils.helpers import clean_document, to_int
from utils.jwt_utils import current_user, jwt_required, role_required
from utils.responses import success

bp = Blueprint("feedback", __name__, url_prefix="/api/feedback")


@bp.get("")
@role_required(ROLE_ADMIN)
def list_feedback():
    """Every rating - the analytics page's feedback table."""
    return success(analytics_service.feedback_entries(limit=to_int(request.args.get("limit"), 200)))


@bp.get("/my")
@jwt_required
def my_feedback():
    """Ratings this student has given, plus the complaints still awaiting one.

    Shapes match what `student/feedback.html` already renders.
    """
    user_id = current_user()["id"]

    given = list(feedback_collection().find({"studentId": user_id}, {"_id": 0}).sort("at", -1))

    pending = list(
        complaints().find(
            {
                "submittedBy.id": user_id,
                "status": {"$in": CLOSED_STATUSES},
                "feedback": None,
            },
            {"_id": 0},
        ).sort("resolvedAt", -1)
    )

    return success(
        {
            "given": clean_document(given),
            "pending": clean_document(pending),
            "givenCount": len(given),
            "pendingCount": len(pending),
        }
    )


@bp.get("/summary")
@role_required(ROLE_ADMIN)
def summary():
    """Average rating and the star distribution."""
    entries = analytics_service.feedback_entries(limit=10000)
    ratings = [entry.get("rating", 0) for entry in entries]

    return success(
        {
            "total": len(entries),
            "averageRating": round(sum(ratings) / len(ratings), 2) if ratings else 0,
            "satisfied": sum(1 for entry in entries if entry.get("satisfied")),
            "dissatisfied": sum(1 for entry in entries if not entry.get("satisfied")),
            "distribution": analytics_service.satisfaction_distribution(),
        }
    )


@bp.get("/complaint/<complaint_id>")
@jwt_required
def for_complaint(complaint_id):
    entry = feedback_collection().find_one({"complaintId": complaint_id}, {"_id": 0})
    return success(clean_document(entry) if entry else None)
