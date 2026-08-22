"""
OCR pipeline for uploaded images.

    File -> validation -> OpenCV pre-processing -> OCR -> text -> NLP

OPTIONAL BY DESIGN. OpenCV and Tesseract/EasyOCR are heavy, platform-specific
dependencies, so every import is lazy and guarded. When they are missing, or
when OCR_ENABLED is false, `extract_text()` returns a result with
`enabled: False` and complaint submission continues untouched - the brief
requires that OCR never break the submission path.

Enable with:
    pip install opencv-python pytesseract
    (plus the Tesseract binary, and TESSERACT_CMD if it is not on PATH)
"""

import logging

logger = logging.getLogger(__name__)

# Formats worth running OCR on.
OCR_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}


def _load_cv2():
    try:
        import cv2  # noqa: PLC0415 - intentionally lazy
        return cv2
    except ImportError:
        return None


def _load_tesseract(cmd: str = ""):
    try:
        import pytesseract  # noqa: PLC0415
        if cmd:
            pytesseract.pytesseract.tesseract_cmd = cmd
        return pytesseract
    except ImportError:
        return None


def _load_easyocr():
    try:
        import easyocr  # noqa: PLC0415
        return easyocr
    except ImportError:
        return None


def is_available(engine: str = "tesseract", tesseract_cmd: str = "") -> dict:
    """Report which parts of the pipeline are installed, without raising."""
    cv2 = _load_cv2()
    status = {"opencv": cv2 is not None, "engine": engine, "engineAvailable": False}

    if engine == "easyocr":
        status["engineAvailable"] = _load_easyocr() is not None
    else:
        tess = _load_tesseract(tesseract_cmd)
        if tess is not None:
            try:
                tess.get_tesseract_version()
                status["engineAvailable"] = True
            except Exception as exc:  # binary missing even though the wrapper is installed
                status["engineError"] = str(exc)

    status["available"] = status["opencv"] and status["engineAvailable"]
    return status


def preprocess(image_path: str):
    """OpenCV clean-up that makes campus photos readable: greyscale, denoise,
    adaptive threshold, deskew. Returns None when OpenCV is unavailable."""
    cv2 = _load_cv2()
    if cv2 is None:
        return None

    import numpy as np

    image = cv2.imread(str(image_path))
    if image is None:
        return None

    grey = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Upscale small images - OCR accuracy drops sharply below ~1000px wide.
    height, width = grey.shape[:2]
    if width < 1000:
        scale = 1000 / width
        grey = cv2.resize(grey, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

    denoised = cv2.fastNlMeansDenoising(grey, None, h=10, templateWindowSize=7, searchWindowSize=21)
    thresholded = cv2.adaptiveThreshold(
        denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 11
    )

    # Deskew using the dominant text angle.
    coords = np.column_stack(np.where(thresholded < 255))
    if coords.size:
        angle = cv2.minAreaRect(coords)[-1]
        angle = -(90 + angle) if angle < -45 else -angle
        if abs(angle) > 0.5:  # ignore sub-degree noise
            h, w = thresholded.shape[:2]
            matrix = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
            thresholded = cv2.warpAffine(
                thresholded, matrix, (w, h),
                flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE,
            )

    return thresholded


def _run_tesseract(image, cmd: str) -> str:
    tess = _load_tesseract(cmd)
    if tess is None:
        return ""
    # PSM 6: assume a uniform block of text - right for signage and notices.
    return tess.image_to_string(image, config="--oem 3 --psm 6")


def _run_easyocr(image_path: str) -> str:
    easyocr = _load_easyocr()
    if easyocr is None:
        return ""
    reader = easyocr.Reader(["en"], gpu=False, verbose=False)
    return "\n".join(str(item[1]) for item in reader.readtext(str(image_path)))


def extract_text(image_path: str, engine: str = "tesseract", tesseract_cmd: str = "", enabled: bool = True) -> dict:
    """Run the pipeline over one image.

    Never raises: any failure is reported in the returned dict so the caller
    can carry on saving the complaint.
    """
    result = {"enabled": bool(enabled), "text": "", "success": False, "error": None, "engine": engine}

    if not enabled:
        result["error"] = "OCR is disabled (set OCR_ENABLED=true to turn it on)."
        return result

    status = is_available(engine, tesseract_cmd)
    if not status["available"]:
        missing = []
        if not status["opencv"]:
            missing.append("opencv-python")
        if not status["engineAvailable"]:
            missing.append("pytesseract + Tesseract binary" if engine == "tesseract" else "easyocr")
        result["error"] = f"OCR dependencies are not installed: {', '.join(missing)}."
        return result

    try:
        if engine == "easyocr":
            text = _run_easyocr(image_path)
        else:
            processed = preprocess(image_path)
            if processed is None:
                result["error"] = "The image could not be read."
                return result
            text = _run_tesseract(processed, tesseract_cmd)

        result["text"] = (text or "").strip()
        result["success"] = True
    except Exception as exc:  # never let OCR break complaint submission
        logger.warning("OCR failed for %s: %s", image_path, exc)
        result["error"] = f"OCR failed: {exc}"

    return result


def analyse_image(image_path: str, engine: str = "tesseract", tesseract_cmd: str = "", enabled: bool = True) -> dict:
    """Full chain: OCR the image, then run the extracted text through NLP,
    department classification and priority prediction."""
    from ai import classifier, priority as priority_module
    from ai.nlp_processor import process

    ocr = extract_text(image_path, engine, tesseract_cmd, enabled)
    if not ocr["success"] or not ocr["text"]:
        return {"ocr": ocr, "nlp": None, "department": None, "priority": None}

    processed = process(ocr["text"])
    return {
        "ocr": ocr,
        "nlp": {
            "cleaned": processed["cleaned"],
            "entities": processed["entities"],
            "tokenCount": processed["tokenCount"],
        },
        "department": classifier.classify(description=ocr["text"], processed=processed),
        "priority": priority_module.predict(description=ocr["text"], processed=processed),
    }
