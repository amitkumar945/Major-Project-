"""
AI / NLP routes.

`POST /api/ai/classify` is the endpoint the complaint form's AI step calls; it
returns the same object `analyseComplaint()` used to build in the browser.

Every response carries `modelTrained: false`, because these are rule-based
services and the brief explicitly forbids claiming otherwise.
"""

from flask import Blueprint, current_app, request

from ai import ocr_processor
from ai.nlp_processor import process
from services import ai_service
from utils.file_utils import save_file
from utils.jwt_utils import jwt_required
from utils.responses import success, validation_error

bp = Blueprint("ai", __name__, url_prefix="/api/ai")


@bp.post("/classify")
@jwt_required
def classify():
    """Full analysis: department, priority, duplicates and suggested officer."""
    values = request.get_json(silent=True) or {}
    result = ai_service.analyse(
        title=values.get("title", ""),
        description=values.get("description", ""),
        category=values.get("category", ""),
        exclude_id=values.get("excludeId"),
    )
    return success(result, "Analysis complete.")


@bp.post("/department")
@jwt_required
def predict_department():
    """Department prediction on its own."""
    values = request.get_json(silent=True) or {}
    return success(
        ai_service.classify_department(
            title=values.get("title", ""),
            description=values.get("description", ""),
            category=values.get("category", ""),
        )
    )


@bp.post("/priority")
@jwt_required
def predict_priority():
    """Priority prediction with the reason behind it."""
    values = request.get_json(silent=True) or {}
    return success(
        ai_service.predict_priority(
            title=values.get("title", ""), description=values.get("description", "")
        )
    )


@bp.post("/duplicates")
@jwt_required
def duplicates():
    """Duplicate check. Reports similarity - never rejects the complaint."""
    values = request.get_json(silent=True) or {}
    report = ai_service.detect_duplicates(
        title=values.get("title", ""),
        description=values.get("description", ""),
        department=values.get("department", ""),
        exclude_id=values.get("excludeId"),
    )
    # The frontend AI card reads a bare list, so return both shapes.
    return success({**report, "duplicates": report["matches"]})


@bp.post("/nlp")
@jwt_required
def nlp():
    """Expose the text pipeline itself: cleaning, tokens, stems, entities."""
    values = request.get_json(silent=True) or {}
    text = f"{values.get('title', '')} {values.get('description', '')}".strip()
    if not text:
        return validation_error({"description": "Provide some text to process."})

    processed = process(text)
    return success(
        {
            "cleaned": processed["cleaned"],
            "tokens": processed["tokens"],
            "contentTokens": processed["contentTokens"],
            "stems": processed["stems"],
            "phrases": processed["phrases"],
            "entities": processed["entities"],
            "tokenCount": processed["tokenCount"],
            "wordCount": processed["wordCount"],
            "method": "rule-based",
            "modelTrained": False,
        }
    )


@bp.get("/status")
def ai_status():
    """What the AI stack can actually do right now - useful for the viva."""
    ocr = ocr_processor.is_available(
        current_app.config.get("OCR_ENGINE", "tesseract"),
        current_app.config.get("TESSERACT_CMD", ""),
    )
    return success(
        {
            "classification": {"available": True, "method": "weighted-keyword-rules", "modelTrained": False},
            "priority": {"available": True, "method": "keyword-rules", "modelTrained": False},
            "duplicateDetection": {"available": True, "method": "jaccard-stem-overlap", "modelTrained": False},
            "nlp": {"available": True, "method": "rule-based cleaning/tokenising/stemming", "modelTrained": False},
            "ocr": {
                "enabled": current_app.config.get("OCR_ENABLED", False),
                "available": ocr["available"],
                "engine": ocr["engine"],
                "opencv": ocr["opencv"],
                "engineAvailable": ocr["engineAvailable"],
            },
            "notice": "All predictions are rule-based. No machine-learning model has been trained.",
        }
    )


@bp.post("/ocr")
@jwt_required
def ocr():
    """Run the OCR pipeline over an uploaded image.

    Returns a clear message rather than an error when OCR is switched off or
    its dependencies are missing - the brief requires OCR to be optional.
    """
    if not request.files:
        return validation_error({"file": "Attach an image to run OCR on."})

    storage = request.files.get("file") or next(iter(request.files.values()))
    saved = save_file(
        storage,
        current_app.config["UPLOAD_FOLDER"],
        current_app.config["MAX_FILE_SIZE"],
        subfolder="ocr",
    )

    from pathlib import Path

    absolute = Path(current_app.config["UPLOAD_FOLDER"]) / saved["path"]
    result = ocr_processor.analyse_image(
        str(absolute),
        engine=current_app.config.get("OCR_ENGINE", "tesseract"),
        tesseract_cmd=current_app.config.get("TESSERACT_CMD", ""),
        enabled=current_app.config.get("OCR_ENABLED", False),
    )

    return success({"file": saved, **result})
