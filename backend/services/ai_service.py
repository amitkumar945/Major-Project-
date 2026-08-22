"""
AI orchestration.

Ties the rule-based modules in `ai/` to the database and returns the exact
payload the frontend's AI card expects. `analyse()` is the backend twin of the
old `analyseComplaint()` in complaintService.js - field for field.

WHAT THIS ACTUALLY IS: weighted keyword rules, keyword-based urgency scoring
and Jaccard text overlap. No model has been trained. Every response carries
`modelTrained: false` so the UI and the viva can state this honestly.
"""

from ai import classifier, duplicate_detection
from ai import priority as priority_module
from ai.nlp_processor import process
from constants import ACTIVE_STATUSES
from database import complaints
from services import assignment_service
from utils.responses import ApiException

# Only recent, still-open complaints are worth comparing against.
DUPLICATE_CANDIDATE_LIMIT = 300


def _candidates(department: str = "", exclude_id: str = None) -> list:
    """Complaints to compare a new submission against."""
    query = {}
    if department:
        query["department"] = department
    if exclude_id:
        query["id"] = {"$ne": exclude_id}

    cursor = (
        complaints()
        .find(query, {"_id": 0, "id": 1, "title": 1, "description": 1, "department": 1, "status": 1, "submittedAt": 1})
        .sort("submittedAt", -1)
        .limit(DUPLICATE_CANDIDATE_LIMIT)
    )
    return list(cursor)


def classify_department(title: str = "", description: str = "", category: str = "") -> dict:
    """Department prediction with confidence and alternatives."""
    return classifier.classify(title=title, description=description, category=category)


def predict_priority(title: str = "", description: str = "") -> dict:
    """Priority prediction with a reason and confidence."""
    return priority_module.predict(title=title, description=description)


def detect_duplicates(title: str = "", description: str = "", department: str = "", exclude_id: str = None) -> dict:
    """Duplicate report: is-duplicate, best match id and similarity score."""
    return duplicate_detection.duplicate_report(
        title=title,
        description=description,
        department=department,
        candidates=_candidates(department, exclude_id),
        exclude_id=exclude_id,
    )


def analyse(title: str = "", description: str = "", category: str = "", exclude_id: str = None) -> dict:
    """Full analysis for the complaint form's AI step.

    The returned keys match what `aiCard.js` renders and what `createComplaint`
    stores on `complaint.ai`, so the UI needs no changes.
    """
    text = f"{title} {description}".strip()
    processed = process(text)

    # The frontend refused to analyse very short text; keep that contract.
    if len(processed["tokens"]) < 4:
        raise ApiException("Please write a longer description before running the AI analysis.", 400)

    department_result = classifier.classify(title=title, description=description, category=category, processed=processed)
    priority_result = priority_module.predict(title=title, description=description, processed=processed)
    department = department_result["department"]

    duplicates = duplicate_detection.find_duplicates(
        title=title,
        description=description,
        department=department,
        candidates=_candidates(department, exclude_id),
        exclude_id=exclude_id,
    )
    duplicate_probability = round(duplicates[0]["similarity"] / 100, 2) if duplicates else 0.04

    # Smart assignment: the active officer in that department with the lightest load.
    suggested = assignment_service.suggest_officer(department)

    from utils.helpers import iso, utcnow

    return {
        # --- fields the existing frontend reads ---
        "department": department,
        "priority": priority_result["priority"],
        "confidence": department_result["confidence"],
        "duplicateProbability": duplicate_probability,
        "duplicates": duplicates,
        "suggestedOfficer": (suggested or {}).get("designation") or "Department Head",
        "suggestedOfficerId": (suggested or {}).get("id"),
        "suggestedOfficerName": (suggested or {}).get("name") or "Department Head",
        "keywords": department_result["keywords"],
        "alternatives": department_result["alternatives"],
        "analysedAt": iso(utcnow()),
        # --- extra detail the backend can now provide ---
        "priorityReason": priority_result["reason"],
        "priorityConfidence": priority_result["confidence"],
        "slaDays": priority_result["slaDays"],
        "entities": processed["entities"],
        "phrases": processed["phrases"],
        "classificationSource": department_result["source"],
        # Honest labelling - no trained model is involved.
        "method": "rule-based",
        "modelTrained": False,
    }


def active_complaint_count(officer_id: str) -> int:
    return complaints().count_documents(
        {"assignedOfficer.id": officer_id, "status": {"$in": ACTIVE_STATUSES}}
    )
