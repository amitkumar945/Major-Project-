"""
Complaint lifecycle: create, query, track, update, resolve, escalate, feedback.

Complaint documents are stored in exactly the shape the frontend already
renders - same field names, same nested `submittedBy` / `assignedOfficer` /
`evidence` / `timeline` / `resolution` / `feedback` objects - so no page or
component needed changing.

Every state change appends a timeline entry (the complaint history the brief
asks for) and writes an audit log.
"""

from constants import (
    ACTIVE_STATUSES,
    CLOSED_STATUSES,
    PRIORITY_MEDIUM,
    ROLE_ADMIN,
    ROLE_OFFICER,
    STATUS_ASSIGNED,
    STATUS_CLOSED,
    STATUS_ESCALATED,
    STATUS_REOPENED,
    STATUS_RESOLVED,
    STATUS_SUBMITTED,
)
from database import complaints, feedback as feedback_collection, next_sequence
from services import ai_service, assignment_service, audit_service, notification_service
from utils.helpers import (
    calculate_deadline,
    clean_document,
    complaint_reference,
    count_by,
    days_until,
    escalation_authority,
    escalation_level_for_overdue,
    iso,
    uid,
    utcnow,
)
from utils.responses import ApiException

PROJECTION = {"_id": 0}

# The seven canonical stages, mirroring `utils/complaintTimeline.js`.
TIMELINE_STAGES = [
    {"key": "submitted", "label": "Complaint Submitted",
     "description": "Grievance registered on the portal and reference number generated."},
    {"key": "classified", "label": "AI Classified",
     "description": "Department, priority and duplicate probability predicted automatically."},
    {"key": "department", "label": "Assigned to Department",
     "description": "Routed to the responsible department for action."},
    {"key": "officer", "label": "Officer Assigned",
     "description": "A department officer took ownership of the complaint."},
    {"key": "started", "label": "Work Started",
     "description": "Field work or repair has begun on site."},
    {"key": "resolution", "label": "Resolution Submitted",
     "description": "Officer submitted the resolution report and proof of work."},
    {"key": "resolved", "label": "Resolved",
     "description": "Complaint closed and the complainant notified for feedback."},
]


def _timeline_entry(label: str, description: str, actor: str, variant: str = None, key: str = "update") -> dict:
    entry = {
        "id": uid("tl"),
        "key": key,
        "label": label,
        "description": description,
        "actor": actor,
        "at": iso(utcnow()),
        "state": "done",
    }
    if variant:
        entry["variant"] = variant
    return entry


def _initial_timeline(complaint: dict) -> list:
    """Timeline for a brand-new complaint: the stages already completed at
    submission are marked done, the rest stay pending so the UI greys them."""
    reached = 3 if complaint.get("assignedOfficer") else 2  # officer vs department
    now = iso(utcnow())
    officer_name = (complaint.get("assignedOfficer") or {}).get("name")

    actors = {
        "submitted": complaint["submittedBy"]["name"],
        "classified": "AI Classification Engine",
        "department": "Grievance Redressal Cell",
        "officer": officer_name or "Department Head",
        "started": officer_name or "Department Officer",
        "resolution": officer_name or "Department Officer",
        "resolved": "Grievance Redressal Cell",
    }

    entries = []
    for index, stage in enumerate(TIMELINE_STAGES):
        done = index <= reached
        entries.append(
            {
                "id": f"{complaint['id']}-{stage['key']}",
                "key": stage["key"],
                "label": stage["label"],
                "description": stage["description"],
                "actor": actors[stage["key"]],
                "at": now if done else None,
                "state": "done" if index < reached else "current" if index == reached else "pending",
            }
        )
    return entries


def _get(complaint_id: str) -> dict:
    complaint = complaints().find_one({"id": complaint_id}, PROJECTION)
    if not complaint:
        raise ApiException(f"Complaint {complaint_id} was not found.", 404)
    return complaint


def _patch(complaint_id: str, patch: dict, timeline_entry: dict = None) -> dict:
    """Apply an update and optionally append one timeline entry, atomically."""
    update = {"$set": {**patch, "updatedAt": iso(utcnow())}}
    if timeline_entry:
        update["$push"] = {"timeline": timeline_entry}

    result = complaints().find_one_and_update(
        {"id": complaint_id}, update, projection=PROJECTION, return_document=True
    )
    if not result:
        raise ApiException(f"Complaint {complaint_id} was not found.", 404)
    return clean_document(result)


def _decorate(complaint: dict) -> dict:
    """Add the derived fields the UI shows but the database does not store."""
    if not complaint:
        return complaint

    if complaint.get("status") in ACTIVE_STATUSES and complaint.get("deadline"):
        remaining = days_until(complaint["deadline"])
        complaint["daysOverdue"] = abs(remaining) if remaining < 0 else 0
    else:
        complaint["daysOverdue"] = complaint.get("daysOverdue", 0)
    return complaint


def _normalise_location(location) -> dict:
    """Store coordinates as numbers, whatever the transport delivered.

    Multipart submissions send every field as a string, so without this the
    same complaint would persist `"29.9457"` from the form path and `29.9457`
    from the JSON path - which breaks map rendering and any geo query.
    """
    if not isinstance(location, dict):
        return {}

    clean = dict(location)
    for key in ("latitude", "longitude", "accuracy"):
        value = clean.get(key)
        if value in (None, ""):
            clean[key] = None
            continue
        try:
            clean[key] = float(value)
        except (TypeError, ValueError):
            clean[key] = None

    for key in ("address", "block"):
        clean[key] = str(clean.get(key) or "").strip()

    return clean


def can_view(complaint: dict, user: dict) -> bool:
    """A student sees only their own complaints; an officer sees their queue
    and their department's; an admin sees everything."""
    role = user.get("role")
    if role == ROLE_ADMIN:
        return True
    if role == ROLE_OFFICER:
        return (
            (complaint.get("assignedOfficer") or {}).get("id") == user["id"]
            or complaint.get("department") == user.get("department")
        )
    return (complaint.get("submittedBy") or {}).get("id") == user["id"]


# --------------------------------------------------------------- creation


def create_complaint(payload: dict, user: dict, evidence: list = None) -> dict:
    """Register a complaint: classify it, set the deadline, auto-assign, notify."""
    title = (payload.get("title") or "").strip()
    description = (payload.get("description") or "").strip()
    category = (payload.get("category") or "").strip()

    # Run the analysis server-side. The client may send its own `ai` block, but
    # the server's result is what gets stored - a client cannot pick its own
    # priority and shorten its SLA.
    try:
        analysis = ai_service.analyse(title=title, description=description, category=category)
    except ApiException:
        # Text too short for analysis: fall back to the submitted values rather
        # than refusing a complaint the validators already accepted.
        analysis = None

    department = (
        (analysis or {}).get("department")
        or payload.get("department")
        or "Nirman Vibhag"
    )
    priority = (analysis or {}).get("priority") or payload.get("priority") or PRIORITY_MEDIUM

    submitted_at = iso(utcnow())
    reference = complaint_reference(next_sequence(f"complaint_{utcnow().year}"))

    complaint = {
        "id": reference,
        "title": title,
        "description": description,
        "category": category,
        "department": department,
        "priority": priority,
        "status": STATUS_SUBMITTED,
        "submittedBy": {
            "id": user["id"],
            "name": user.get("name", ""),
            "userId": user.get("userId", ""),
            "email": user.get("email", ""),
            "userType": user.get("userType", "Student"),
            "hostel": user.get("hostel", "—"),
        },
        "assignedOfficer": None,
        "location": _normalise_location(payload.get("location")),
        "evidence": evidence or [],
        "ai": analysis,
        "submittedAt": submitted_at,
        "updatedAt": submitted_at,
        "deadline": calculate_deadline(submitted_at, priority),
        "resolvedAt": None,
        "escalationLevel": 0,
        "escalationAuthority": None,
        "daysOverdue": 0,
        "remarks": [],
        "resolution": None,
        "feedback": None,
    }

    # Auto-assign to the least-loaded officer in the department.
    officer = assignment_service.auto_assign(complaint)
    if officer:
        complaint["assignedOfficer"] = officer
        complaint["status"] = STATUS_ASSIGNED

    complaint["timeline"] = _initial_timeline(complaint)

    complaints().insert_one(complaint)
    stored = clean_document(complaint)

    if officer:
        assignment_service.record_assignment(reference, officer, actor=user, reason="Automatic assignment on submission.")

    notification_service.complaint_submitted(stored)
    audit_service.log(
        audit_service.COMPLAINT_CREATED, user,
        f"Complaint {reference} registered for {department} ({priority} priority).",
        complaint_id=reference,
    )
    return _decorate(stored)


# ---------------------------------------------------------------- queries


def get_complaints(options: dict, user: dict = None) -> dict:
    """Filter, sort and paginate - same options the frontend already sends."""
    options = options or {}
    query = {}

    # Scope first, so a student can never widen their own view with filters.
    if user and user.get("role") == "student":
        query["submittedBy.id"] = user["id"]
    elif options.get("userId"):
        query["submittedBy.id"] = options["userId"]

    if options.get("officerId"):
        query["assignedOfficer.id"] = options["officerId"]
    if options.get("department"):
        query["department"] = options["department"]
    if options.get("priority"):
        query["priority"] = options["priority"]
    if options.get("status"):
        query["status"] = options["status"]
    if options.get("category"):
        query["category"] = options["category"]
    if options.get("onlyActive"):
        query["status"] = {"$in": ACTIVE_STATUSES}

    date_filter = {}
    if options.get("dateFrom"):
        date_filter["$gte"] = f"{str(options['dateFrom'])[:10]}T00:00:00.000Z"
    if options.get("dateTo"):
        date_filter["$lte"] = f"{str(options['dateTo'])[:10]}T23:59:59.999Z"
    if date_filter:
        query["submittedAt"] = date_filter

    search = (options.get("search") or "").strip()
    if search:
        # Regex rather than $text: the frontend searches ids and names too, and
        # escaping keeps user input from being interpreted as a pattern.
        import re

        pattern = re.escape(search)
        query["$or"] = [
            {"id": {"$regex": pattern, "$options": "i"}},
            {"title": {"$regex": pattern, "$options": "i"}},
            {"description": {"$regex": pattern, "$options": "i"}},
            {"department": {"$regex": pattern, "$options": "i"}},
            {"category": {"$regex": pattern, "$options": "i"}},
            {"submittedBy.name": {"$regex": pattern, "$options": "i"}},
            {"assignedOfficer.name": {"$regex": pattern, "$options": "i"}},
        ]

    sort_by = options.get("sortBy") or "submittedAt"
    direction = -1 if (options.get("sortDir") or "desc") == "desc" else 1

    page_size = max(1, min(int(options.get("pageSize") or 10), 10000))
    total = complaints().count_documents(query)
    total_pages = max((total + page_size - 1) // page_size, 1)
    page = max(1, min(int(options.get("page") or 1), total_pages))

    cursor = (
        complaints()
        .find(query, PROJECTION)
        .sort(sort_by, direction)
        .skip((page - 1) * page_size)
        .limit(page_size)
    )

    return {
        "items": [_decorate(item) for item in cursor],
        "total": total,
        "page": page,
        "pageSize": page_size,
        "totalPages": total_pages,
    }


def get_complaint(complaint_id: str, user: dict = None) -> dict:
    complaint = _get(complaint_id)
    if user and not can_view(complaint, user):
        raise ApiException("You do not have permission to view this complaint.", 403)
    return _decorate(clean_document(complaint))


def track(reference_id: str) -> dict:
    """Public tracking. Returns a reduced view - no contact details, no remarks."""
    reference = (reference_id or "").strip().upper()
    complaint = complaints().find_one({"id": reference}, PROJECTION)
    if not complaint:
        raise ApiException(
            "No complaint found with this reference number. Please check and try again.", 404
        )

    complaint = _decorate(clean_document(complaint))
    return {
        "id": complaint["id"],
        "title": complaint["title"],
        "description": complaint["description"],
        "category": complaint.get("category"),
        "department": complaint.get("department"),
        "priority": complaint.get("priority"),
        "status": complaint.get("status"),
        "submittedAt": complaint.get("submittedAt"),
        "updatedAt": complaint.get("updatedAt"),
        "deadline": complaint.get("deadline"),
        "resolvedAt": complaint.get("resolvedAt"),
        "daysOverdue": complaint.get("daysOverdue", 0),
        "escalationLevel": complaint.get("escalationLevel", 0),
        "timeline": complaint.get("timeline", []),
        # Only the complainant's display name, never their email or hostel.
        "submittedBy": {"name": (complaint.get("submittedBy") or {}).get("name", "")},
        "assignedOfficer": (
            {
                "name": complaint["assignedOfficer"].get("name", ""),
                "designation": complaint["assignedOfficer"].get("designation", ""),
                "department": complaint["assignedOfficer"].get("department", ""),
            }
            if complaint.get("assignedOfficer")
            else None
        ),
        "resolution": (
            {
                "notes": complaint["resolution"].get("notes"),
                "completedAt": complaint["resolution"].get("completedAt"),
                "completedBy": complaint["resolution"].get("completedBy"),
            }
            if complaint.get("resolution")
            else None
        ),
        # Where the issue is, so the public tracker can show it on the map.
        # The GPS accuracy radius is withheld: it describes the reporter's
        # device rather than the complaint, and this view is unauthenticated.
        "location": (
            {
                "latitude": (complaint.get("location") or {}).get("latitude"),
                "longitude": (complaint.get("location") or {}).get("longitude"),
                "address": (complaint.get("location") or {}).get("address", ""),
                "block": (complaint.get("location") or {}).get("block", ""),
            }
            if (complaint.get("location") or {}).get("latitude") is not None
            else {}
        ),
    }


def get_statistics(scope: dict = None) -> dict:
    """Dashboard counters - the exact keys `getStatistics()` returned."""
    scope = scope or {}
    query = {}
    if scope.get("userId"):
        query["submittedBy.id"] = scope["userId"]
    if scope.get("officerId"):
        query["assignedOfficer.id"] = scope["officerId"]
    if scope.get("department"):
        query["department"] = scope["department"]

    items = [_decorate(item) for item in complaints().find(query, PROJECTION)]
    by_status = count_by(items, "status")

    overdue = sum(
        1 for item in items
        if item.get("status") in ACTIVE_STATUSES and days_until(item.get("deadline")) < 0
    )

    return {
        "total": len(items),
        "submitted": by_status.get("Submitted", 0),
        "underReview": by_status.get("Under Review", 0),
        "assigned": by_status.get("Assigned", 0),
        "accepted": by_status.get("Accepted", 0),
        "pending": by_status.get("Submitted", 0) + by_status.get("Under Review", 0) + by_status.get("Pending", 0),
        "inProgress": by_status.get("In Progress", 0) + by_status.get("Accepted", 0),
        "resolved": by_status.get("Resolved", 0) + by_status.get("Closed", 0),
        "reopened": by_status.get("Reopened", 0),
        "escalated": by_status.get("Escalated", 0),
        "overdue": overdue,
        "byStatus": by_status,
        "byDepartment": count_by(items, "department"),
        "byPriority": count_by(items, "priority"),
        "list": items,
    }


# ----------------------------------------------------------------- writes


def update_status(complaint_id: str, status: str, actor: dict, note: str = "") -> dict:
    current = _get(complaint_id)
    if not can_view(current, actor):
        raise ApiException("You do not have permission to update this complaint.", 403)

    patch = {"status": status}
    if status == STATUS_RESOLVED:
        patch["resolvedAt"] = iso(utcnow())

    entry = _timeline_entry(
        f"Status changed to {status}",
        note or f'The complaint status was updated to "{status}".',
        actor.get("name", "Department Officer"),
        variant="success" if status == STATUS_RESOLVED else None,
    )

    updated = _patch(complaint_id, patch, entry)
    notification_service.status_changed(updated, status, actor.get("name", ""))
    audit_service.log(
        audit_service.STATUS_CHANGED, actor,
        f"Status of {complaint_id} changed from '{current['status']}' to '{status}'.",
        complaint_id=complaint_id, meta={"from": current["status"], "to": status},
    )
    return _decorate(updated)


def add_remark(complaint_id: str, message: str, actor: dict) -> dict:
    current = _get(complaint_id)
    if not can_view(current, actor):
        raise ApiException("You do not have permission to comment on this complaint.", 403)

    remark = {
        "id": uid("rm"),
        "author": actor.get("name", ""),
        "authorId": actor.get("id"),
        "role": actor.get("role", ""),
        "message": message.strip(),
        "at": iso(utcnow()),
    }

    result = complaints().find_one_and_update(
        {"id": complaint_id},
        {"$push": {"remarks": remark}, "$set": {"updatedAt": remark["at"]}},
        projection=PROJECTION,
        return_document=True,
    )

    # Tell the other party there is a new remark.
    if actor.get("role") in (ROLE_OFFICER, ROLE_ADMIN):
        notification_service.create(
            result["submittedBy"]["id"], "status_changed", "New remark on your complaint",
            f"{actor.get('name')} commented on {complaint_id}.", complaint_id,
        )
    elif result.get("assignedOfficer"):
        notification_service.create(
            result["assignedOfficer"]["id"], "status_changed", "New remark from the complainant",
            f"{actor.get('name')} commented on {complaint_id}.", complaint_id,
        )

    audit_service.log(audit_service.REMARK_ADDED, actor, f"Remark added to {complaint_id}.", complaint_id=complaint_id)
    return _decorate(clean_document(result))


def submit_resolution(complaint_id: str, notes: str, proof: list, actor: dict) -> dict:
    current = _get(complaint_id)
    if not can_view(current, actor):
        raise ApiException("You do not have permission to resolve this complaint.", 403)
    if current.get("status") in CLOSED_STATUSES:
        raise ApiException(f"This complaint is already {current['status'].lower()}.", 409)

    now = iso(utcnow())
    patch = {
        "status": STATUS_RESOLVED,
        "resolvedAt": now,
        "resolution": {
            "notes": notes.strip(),
            "proof": proof or [],
            "completedAt": now,
            "completedBy": actor.get("name", "Department Officer"),
            "completedById": actor.get("id"),
        },
    }

    update = {
        "$set": {**patch, "updatedAt": now},
        "$push": {
            "timeline": {
                "$each": [
                    _timeline_entry("Resolution Submitted", notes.strip(), actor.get("name", "Department Officer"), "success", "resolution"),
                    _timeline_entry("Resolved", "Complaint closed and complainant notified for feedback.", "Grievance Redressal Cell", "success", "resolved"),
                ]
            }
        },
    }
    result = complaints().find_one_and_update({"id": complaint_id}, update, projection=PROJECTION, return_document=True)
    updated = clean_document(result)

    notification_service.resolution_submitted(updated)
    audit_service.log(audit_service.COMPLAINT_RESOLVED, actor, f"Complaint {complaint_id} resolved.", complaint_id=complaint_id)
    return _decorate(updated)


def assign_officer(complaint_id: str, officer_id: str, actor: dict, reason: str = "") -> dict:
    current = _get(complaint_id)
    officer = assignment_service.officer_summary_by_id(officer_id)
    previous = (current.get("assignedOfficer") or {}).get("id")

    patch = {
        "assignedOfficer": officer,
        "department": officer["department"],
    }
    # Only move an open complaint to Assigned; a resolved one keeps its status.
    if current.get("status") in ACTIVE_STATUSES:
        patch["status"] = STATUS_ASSIGNED

    is_reassignment = bool(previous and previous != officer_id)
    entry = _timeline_entry(
        "Officer Reassigned" if is_reassignment else "Officer Assigned",
        f"{officer['name']} ({officer['designation']}) was assigned to this complaint."
        + (f" Reason: {reason}" if reason else ""),
        actor.get("name", "Administrator"),
        key="officer",
    )

    updated = _patch(complaint_id, patch, entry)
    assignment_service.record_assignment(complaint_id, officer, actor, reason, previous)
    notification_service.officer_assigned(updated, officer)
    audit_service.log(
        audit_service.COMPLAINT_REASSIGNED if is_reassignment else audit_service.COMPLAINT_ASSIGNED,
        actor, f"Complaint {complaint_id} assigned to {officer['name']}.",
        complaint_id=complaint_id, meta={"officerId": officer_id, "previousOfficerId": previous},
    )
    return _decorate(updated)


def change_priority(complaint_id: str, priority: str, actor: dict) -> dict:
    current = _get(complaint_id)
    entry = _timeline_entry(
        f"Priority changed to {priority}",
        "The resolution deadline was recalculated from the new priority.",
        actor.get("name", "Administrator"),
    )
    updated = _patch(
        complaint_id,
        {"priority": priority, "deadline": calculate_deadline(current["submittedAt"], priority)},
        entry,
    )
    audit_service.log(
        audit_service.PRIORITY_CHANGED, actor,
        f"Priority of {complaint_id} changed from '{current['priority']}' to '{priority}'.",
        complaint_id=complaint_id,
    )
    return _decorate(updated)


def update_deadline(complaint_id: str, deadline: str, actor: dict) -> dict:
    from utils.helpers import parse_iso

    parsed = parse_iso(deadline)
    if not parsed:
        raise ApiException("Enter a valid completion date.", 400)

    entry = _timeline_entry(
        "Estimated completion date updated",
        "New expected resolution date set by the handling officer.",
        actor.get("name", "Department Officer"),
    )
    updated = _patch(complaint_id, {"deadline": iso(parsed)}, entry)
    return _decorate(updated)


def escalate(complaint_id: str, actor: dict, reason: str = "") -> dict:
    current = _get(complaint_id)
    level = min((current.get("escalationLevel") or 0) + 1, 3)
    authority = escalation_authority(level)

    entry = _timeline_entry(
        f"Escalated to Level {level}",
        f"Complaint has been escalated to {authority}." + (f" {reason}" if reason else ""),
        actor.get("name", "Administrator"),
        variant="danger",
    )
    updated = _patch(
        complaint_id,
        {
            "status": STATUS_ESCALATED,
            "escalationLevel": level,
            "escalationAuthority": authority,
            "escalatedAt": iso(utcnow()),
            "escalationReason": reason or "Resolution deadline exceeded.",
        },
        entry,
    )

    notification_service.complaint_escalated(updated, level, authority)
    audit_service.log(
        audit_service.COMPLAINT_ESCALATED, actor,
        f"Complaint {complaint_id} escalated to level {level} ({authority}).",
        complaint_id=complaint_id,
    )
    return _decorate(updated)


def close_complaint(complaint_id: str, actor: dict) -> dict:
    entry = _timeline_entry(
        "Complaint Closed", "The grievance was closed by the administration.",
        actor.get("name", "Administrator"),
    )
    updated = _patch(complaint_id, {"status": STATUS_CLOSED, "closedAt": iso(utcnow())}, entry)
    audit_service.log(audit_service.COMPLAINT_CLOSED, actor, f"Complaint {complaint_id} closed.", complaint_id=complaint_id)
    return _decorate(updated)


def reopen(complaint_id: str, reason: str, actor: dict) -> dict:
    current = _get(complaint_id)

    # Only the complainant (or an admin) may reopen, and only once resolved.
    if actor.get("role") != ROLE_ADMIN and (current.get("submittedBy") or {}).get("id") != actor["id"]:
        raise ApiException("Only the complainant can reopen this complaint.", 403)
    if current.get("status") not in CLOSED_STATUSES:
        raise ApiException("Only a resolved or closed complaint can be reopened.", 409)

    entry = _timeline_entry(
        "Complaint Reopened",
        reason or "The complainant was not satisfied with the resolution.",
        actor.get("name", "Complainant"),
        variant="warning",
    )
    updated = _patch(
        complaint_id,
        {
            "status": STATUS_REOPENED,
            "resolvedAt": None,
            "deadline": calculate_deadline(iso(utcnow()), current.get("priority", PRIORITY_MEDIUM)),
            "reopenReason": reason,
            "reopenedAt": iso(utcnow()),
        },
        entry,
    )

    notification_service.complaint_reopened(updated, reason)
    audit_service.log(audit_service.COMPLAINT_REOPENED, actor, f"Complaint {complaint_id} reopened. {reason}".strip(), complaint_id=complaint_id)
    return _decorate(updated)


def submit_feedback(complaint_id: str, rating: int, comment: str, satisfied: bool, actor: dict) -> dict:
    current = _get(complaint_id)

    if (current.get("submittedBy") or {}).get("id") != actor["id"]:
        raise ApiException("Only the complainant can rate this complaint.", 403)
    if current.get("status") not in CLOSED_STATUSES:
        raise ApiException("You can only rate a complaint once it has been resolved.", 409)
    if current.get("feedback"):
        raise ApiException("You have already rated this complaint.", 409)

    now = iso(utcnow())
    entry_value = {
        "rating": int(rating),
        "comment": comment.strip(),
        "satisfied": bool(satisfied),
        "at": now,
    }

    timeline_entry = _timeline_entry(
        "Feedback Received",
        f"Complainant rated the resolution {rating} out of 5.",
        (current.get("submittedBy") or {}).get("name", "Complainant"),
        variant="success" if satisfied else "warning",
    )
    updated = _patch(complaint_id, {"feedback": entry_value}, timeline_entry)

    # Denormalised copy for the analytics screen.
    feedback_collection().replace_one(
        {"complaintId": complaint_id},
        {
            "id": f"FB-{complaint_id[-5:]}",
            "complaintId": complaint_id,
            "complaintTitle": current.get("title"),
            "department": current.get("department"),
            "officer": (current.get("assignedOfficer") or {}).get("name", "—"),
            "student": (current.get("submittedBy") or {}).get("name", ""),
            "studentId": (current.get("submittedBy") or {}).get("id"),
            **entry_value,
        },
        upsert=True,
    )

    if current.get("assignedOfficer"):
        notification_service.create(
            current["assignedOfficer"]["id"], "resolved", "Feedback received",
            f"The complainant rated {complaint_id} {rating}/5.", complaint_id,
        )

    audit_service.log(
        audit_service.FEEDBACK_SUBMITTED, actor,
        f"Feedback submitted for {complaint_id}: {rating}/5.", complaint_id=complaint_id,
    )
    return _decorate(updated)


def add_evidence(complaint_id: str, files: list, actor: dict) -> dict:
    """Attach more files to an existing complaint."""
    current = _get(complaint_id)
    if not can_view(current, actor):
        raise ApiException("You do not have permission to modify this complaint.", 403)

    result = complaints().find_one_and_update(
        {"id": complaint_id},
        {"$push": {"evidence": {"$each": files}}, "$set": {"updatedAt": iso(utcnow())}},
        projection=PROJECTION,
        return_document=True,
    )
    audit_service.log(
        audit_service.FILE_UPLOADED, actor,
        f"{len(files)} file(s) attached to {complaint_id}.", complaint_id=complaint_id,
    )
    return _decorate(clean_document(result))


def get_escalations() -> list:
    """Open complaints past their deadline, worst first."""
    items = complaints().find({"status": {"$in": ACTIVE_STATUSES}}, PROJECTION)

    overdue = []
    for complaint in items:
        remaining = days_until(complaint.get("deadline"))
        if remaining >= 0:
            continue
        days_overdue = abs(remaining)
        level = escalation_level_for_overdue(days_overdue)
        complaint = clean_document(complaint)
        complaint["daysOverdue"] = days_overdue
        complaint["escalationLevel"] = level
        complaint["escalationAuthority"] = escalation_authority(level)
        overdue.append(complaint)

    overdue.sort(key=lambda item: -item["daysOverdue"])
    return overdue
