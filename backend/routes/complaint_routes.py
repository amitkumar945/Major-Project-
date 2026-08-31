"""
Complaint routes: create, list, track, status, remarks, resolve, feedback,
reopen, assign, escalate and the AI endpoints.

Complaints arrive either as JSON or as multipart/form-data (when the five-step
form carries evidence files); `_payload()` handles both so the frontend can use
whichever it needs.
"""

import json

from flask import Blueprint, Response, current_app, request

from constants import (
    OFFICER_STATUS_OPTIONS,
    PRIORITY_LIST,
    ROLE_ADMIN,
    ROLE_OFFICER,
    ROLE_STUDENT,
)
from services import ai_service, complaint_service, export_service
from services.complaint_service import BULK_MAX_PAGE_SIZE
from utils.file_utils import save_files
from utils.helpers import to_bool, to_int
from utils.jwt_utils import (
    current_user,
    jwt_required,
    jwt_required_allow_query,
    role_required,
)
from utils.responses import ApiException, error, success, validation_error
from utils.validators import (
    validate_complaint,
    validate_feedback,
    validate_location,
    validate_remark,
    validate_resolution,
    validate_status,
)

bp = Blueprint("complaints", __name__, url_prefix="/api/complaints")


def _payload() -> dict:
    """Read the body as JSON, or as form fields when files are attached.

    In the multipart case the nested objects (`location`, `ai`) arrive as JSON
    strings, so they are decoded back into dictionaries here.
    """
    if request.content_type and "multipart/form-data" in request.content_type:
        values = dict(request.form)
        for key in ("location", "ai"):
            if isinstance(values.get(key), str):
                try:
                    values[key] = json.loads(values[key])
                except (ValueError, TypeError):
                    values[key] = {}
        return values
    return request.get_json(silent=True) or {}


def _csv_response(csv_text: str, download_name: str):
    """Wrap CSV text in a download response.

    The UTF-8 BOM makes Excel open accented characters correctly; without it
    names render as mojibake.
    """
    return Response(
        "﻿" + csv_text,
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{download_name}"'},
    )


def _filters() -> dict:
    """Query-string filters - the same names the frontend already sends."""
    args = request.args
    return {
        "search": args.get("search", ""),
        "department": args.get("department", ""),
        "priority": args.get("priority", ""),
        "status": args.get("status", ""),
        "category": args.get("category", ""),
        "dateFrom": args.get("dateFrom", ""),
        "dateTo": args.get("dateTo", ""),
        "userId": args.get("userId", ""),
        "officerId": args.get("officerId", ""),
        "onlyActive": to_bool(args.get("onlyActive"), False),
        "sortBy": args.get("sortBy", "submittedAt"),
        "sortDir": args.get("sortDir", "desc"),
        "page": to_int(args.get("page"), 1),
        "pageSize": to_int(args.get("pageSize"), 10),
        # The dashboards and charts read every matching row to compute their
        # aggregates, and have done so since before this cap existed. They ask
        # for it either with `?bulk=true` or with the exact page size the
        # existing `getAllComplaints()` helper sends.
        #
        # Matching that ONE value, rather than "anything large", is deliberate:
        # a `> 1000` test would let any caller opt itself out of the cap simply
        # by asking for more, which is precisely what the cap exists to stop.
        # Anything else above API_MAX_PAGE_SIZE is clamped down to it.
        #
        # Rows stay scoped by role either way, so this widens volume, never
        # visibility: a student asking for 10000 still gets only their own.
        "allow_bulk": to_bool(args.get("bulk"), False)
        or to_int(args.get("pageSize"), 10) == BULK_MAX_PAGE_SIZE,
    }


# ---------------------------------------------------------------- creation


@bp.post("")
@jwt_required
def create_complaint():
    user = current_user()
    values = _payload()

    errors = validate_complaint(values)
    location = values.get("location") or {}
    if location:
        errors.update(validate_location(location))
    if errors:
        return validation_error(errors)

    # Save evidence first: if a file is rejected, nothing is written to Mongo.
    evidence = []
    if request.files:
        evidence = save_files(
            request.files.getlist("files") or request.files.getlist("evidence"),
            current_app.config["UPLOAD_FOLDER"],
            current_app.config["MAX_FILE_SIZE"],
            current_app.config["MAX_FILES_PER_REQUEST"],
            subfolder="evidence",
        )

    complaint = complaint_service.create_complaint(values, user, evidence)
    return success(complaint, f"Complaint {complaint['id']} registered successfully.", 201)


# ----------------------------------------------------------------- reading


@bp.get("")
@jwt_required
def list_complaints():
    """Scoped automatically: a student only ever sees their own complaints."""
    user = current_user()
    filters = _filters()

    # An officer with no explicit filter gets their own queue.
    if user["role"] == ROLE_OFFICER and not filters["officerId"] and not filters["department"]:
        filters["officerId"] = user["id"]

    return success(complaint_service.get_complaints(filters, user))


@bp.get("/my")
@jwt_required
def my_complaints():
    """Complaints raised by the signed-in citizen."""
    user = current_user()
    filters = _filters()
    filters["userId"] = user["id"]
    return success(complaint_service.get_complaints(filters, user))


@bp.get("/assigned")
@role_required(ROLE_OFFICER, ROLE_ADMIN)
def assigned_complaints():
    """The signed-in officer's work queue."""
    filters = _filters()
    filters["officerId"] = current_user()["id"]
    return success(complaint_service.get_complaints(filters, current_user()))


@bp.get("/statistics")
@jwt_required
def statistics():
    """Dashboard counters, scoped to whoever is asking."""
    user = current_user()
    scope = {}
    if user["role"] == ROLE_STUDENT:
        scope["userId"] = user["id"]
    elif user["role"] == ROLE_OFFICER:
        scope["officerId"] = request.args.get("officerId") or user["id"]
        if request.args.get("department"):
            scope = {"department": request.args["department"]}
    else:
        if request.args.get("department"):
            scope["department"] = request.args["department"]

    return success(complaint_service.get_statistics(scope))


@bp.get("/export")
@jwt_required_allow_query
def export_complaints():
    """Download the current complaint list as CSV.

    Takes the same query-string filters as the list endpoint, so the file
    matches whatever is on screen. Scoping is enforced by `get_complaints`,
    which is handed the caller's own user - a student can only ever export
    their own complaints.

    The token may arrive as `?token=` because a browser download cannot set an
    Authorization header.
    """
    user = current_user()
    filters = _filters()

    if user["role"] == ROLE_OFFICER and not filters["officerId"] and not filters["department"]:
        filters["officerId"] = user["id"]
    elif user["role"] == ROLE_STUDENT:
        filters["userId"] = user["id"]

    csv_text = export_service.complaints_csv(filters, user)
    return _csv_response(csv_text, export_service.filename("complaints"))


@bp.get("/escalations")
@role_required(ROLE_ADMIN)
def escalations():
    return success(complaint_service.get_escalations())


@bp.get("/track/<reference_id>")
def track(reference_id):
    """Public - no token required. Returns a reduced view."""
    return success(complaint_service.track(reference_id))


@bp.get("/<complaint_id>")
@jwt_required
def get_complaint(complaint_id):
    return success(complaint_service.get_complaint(complaint_id, current_user()))


@bp.get("/<complaint_id>/history")
@jwt_required
def history(complaint_id):
    """The complaint's timeline plus its assignment history."""
    from services import assignment_service

    complaint = complaint_service.get_complaint(complaint_id, current_user())
    return success(
        {
            "timeline": complaint.get("timeline", []),
            "remarks": complaint.get("remarks", []),
            "assignments": assignment_service.assignment_history(complaint_id),
        }
    )


# ------------------------------------------------------------------ writes


@bp.put("/<complaint_id>/status")
@role_required(ROLE_OFFICER, ROLE_ADMIN)
def update_status(complaint_id):
    values = request.get_json(silent=True) or {}
    status = (values.get("status") or "").strip()

    errors = validate_status(status)
    if errors:
        return validation_error(errors)

    # An officer may only set the statuses the frontend offers them.
    user = current_user()
    if user["role"] == ROLE_OFFICER and status not in OFFICER_STATUS_OPTIONS:
        return error(
            f"An officer cannot set the status '{status}'. "
            f"Allowed: {', '.join(OFFICER_STATUS_OPTIONS)}.",
            403,
        )

    complaint = complaint_service.update_status(complaint_id, status, user, values.get("note", ""))
    return success(complaint, f"Status updated to {status}.")


@bp.post("/<complaint_id>/remarks")
@jwt_required
def add_remark(complaint_id):
    values = request.get_json(silent=True) or {}

    errors = validate_remark(values)
    if errors:
        return validation_error(errors)

    complaint = complaint_service.add_remark(complaint_id, values["message"], current_user())
    return success(complaint, "Remark added.", 201)


@bp.post("/<complaint_id>/resolve")
@role_required(ROLE_OFFICER, ROLE_ADMIN)
def resolve(complaint_id):
    values = _payload()

    errors = validate_resolution(values)
    if errors:
        return validation_error(errors)

    proof = []
    if request.files:
        proof = save_files(
            request.files.getlist("files") or request.files.getlist("proof"),
            current_app.config["UPLOAD_FOLDER"],
            current_app.config["MAX_FILE_SIZE"],
            current_app.config["MAX_FILES_PER_REQUEST"],
            subfolder="resolutions",
        )

    complaint = complaint_service.submit_resolution(complaint_id, values["notes"], proof, current_user())
    return success(complaint, "Resolution submitted. The complaint is now marked Resolved.")


@bp.post("/<complaint_id>/assign")
@role_required(ROLE_ADMIN)
def assign(complaint_id):
    values = request.get_json(silent=True) or {}
    officer_id = (values.get("officerId") or "").strip()
    if not officer_id:
        return validation_error({"officerId": "Select an officer to assign."})

    complaint = complaint_service.assign_officer(complaint_id, officer_id, current_user(), values.get("reason", ""))
    return success(complaint, "Complaint assigned successfully.")


@bp.put("/<complaint_id>/reassign")
@role_required(ROLE_ADMIN)
def reassign(complaint_id):
    values = request.get_json(silent=True) or {}
    officer_id = (values.get("officerId") or "").strip()
    if not officer_id:
        return validation_error({"officerId": "Select an officer to reassign to."})

    complaint = complaint_service.assign_officer(complaint_id, officer_id, current_user(), values.get("reason", ""))
    return success(complaint, "Complaint reassigned successfully.")


@bp.put("/<complaint_id>/priority")
@role_required(ROLE_ADMIN)
def change_priority(complaint_id):
    values = request.get_json(silent=True) or {}
    priority = (values.get("priority") or "").strip()
    if priority not in PRIORITY_LIST:
        return validation_error({"priority": f"Priority must be one of: {', '.join(PRIORITY_LIST)}"})

    complaint = complaint_service.change_priority(complaint_id, priority, current_user())
    return success(complaint, f"Priority changed to {priority}.")


@bp.put("/<complaint_id>/deadline")
@role_required(ROLE_OFFICER, ROLE_ADMIN)
def update_deadline(complaint_id):
    values = request.get_json(silent=True) or {}
    deadline = values.get("deadline")
    if not deadline:
        return validation_error({"deadline": "Enter the expected completion date."})

    complaint = complaint_service.update_deadline(complaint_id, deadline, current_user())
    return success(complaint, "Expected completion date updated.")


@bp.post("/<complaint_id>/escalate")
@role_required(ROLE_ADMIN)
def escalate(complaint_id):
    values = request.get_json(silent=True) or {}
    complaint = complaint_service.escalate(complaint_id, current_user(), values.get("reason", ""))
    return success(complaint, f"Complaint escalated to level {complaint.get('escalationLevel')}.")


@bp.post("/<complaint_id>/close")
@role_required(ROLE_ADMIN)
def close(complaint_id):
    complaint = complaint_service.close_complaint(complaint_id, current_user())
    return success(complaint, "Complaint closed.")


@bp.post("/<complaint_id>/reopen")
@jwt_required
def reopen(complaint_id):
    values = request.get_json(silent=True) or {}
    reason = (values.get("reason") or "").strip()
    if not reason:
        return validation_error({"reason": "Please tell us why you are reopening this complaint."})

    complaint = complaint_service.reopen(complaint_id, reason, current_user())
    return success(complaint, "Your complaint has been reopened.")


@bp.post("/<complaint_id>/feedback")
@jwt_required
def feedback(complaint_id):
    values = request.get_json(silent=True) or {}

    errors = validate_feedback(values)
    if errors:
        return validation_error(errors)

    rating = int(values["rating"])
    # Default `satisfied` from the rating when the client does not send it.
    satisfied = values.get("satisfied")
    satisfied = rating >= 3 if satisfied is None else to_bool(satisfied)

    complaint = complaint_service.submit_feedback(
        complaint_id, rating, values.get("comment", ""), satisfied, current_user()
    )
    return success(complaint, "Thank you for your feedback.", 201)


@bp.post("/<complaint_id>/evidence")
@jwt_required
def add_evidence(complaint_id):
    if not request.files:
        return validation_error({"files": "Attach at least one file."})

    files = save_files(
        request.files.getlist("files"),
        current_app.config["UPLOAD_FOLDER"],
        current_app.config["MAX_FILE_SIZE"],
        current_app.config["MAX_FILES_PER_REQUEST"],
        subfolder="evidence",
    )
    complaint = complaint_service.add_evidence(complaint_id, files, current_user())
    return success(complaint, f"{len(files)} file(s) attached.", 201)
