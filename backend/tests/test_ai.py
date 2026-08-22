"""Department classification, priority prediction, duplicates and NLP."""

import pytest

from ai import classifier, duplicate_detection
from ai import priority as priority_module
from ai.nlp_processor import process, stem


# ------------------------------------------------------ department routing


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Water is leaking from the pipeline near the hostel drain", "Jal Kal Vibhag"),
        ("The tap in the washroom is broken and sewage is overflowing", "Jal Kal Vibhag"),
        ("The ceiling fan and tube light are not working, wiring is loose", "Vidyut Vibhag"),
        ("There is a power cut and the electrical MCB keeps tripping", "Vidyut Vibhag"),
        ("The lab computer will not boot and the printer is offline", "MCA Lab / Computer Lab"),
        ("Wi-Fi router in the computer lab has no internet connection", "MCA Lab / Computer Lab"),
        ("A crack has appeared in the classroom wall and the plaster is falling", "Nirman Vibhag"),
        ("The wooden door hinge is broken and the furniture needs repair", "Nirman Vibhag"),
    ],
)
def test_classifier_routes_to_the_right_department(text, expected):
    assert classifier.classify(description=text)["department"] == expected


def test_classifier_returns_confidence_and_alternatives():
    result = classifier.classify(
        description="Water leaking from the pipeline near the hostel drainage line"
    )

    assert 0 <= result["confidence"] <= 1
    assert len(result["alternatives"]) == 3
    assert result["keywords"]


def test_classifier_falls_back_to_the_chosen_category():
    """With no recognisable keyword, the user's category decides."""
    result = classifier.classify(description="Something is wrong over there somehow", category="Electricity")

    assert result["department"] == "Vidyut Vibhag"
    assert result["source"] == "category-fallback"


def test_a_clear_complaint_scores_higher_than_a_vague_one():
    clear = classifier.classify(
        description="Water pipeline leakage and drainage overflow near the washroom tap"
    )
    vague = classifier.classify(description="There is some water issue somewhere")
    assert clear["confidence"] > vague["confidence"]


def test_classifier_never_claims_to_be_a_trained_model():
    assert classifier.classify(description="Water leaking from the pipe")["modelTrained"] is False


# ------------------------------------------------------------- priority


@pytest.mark.parametrize(
    "text,expected",
    [
        ("There is sparking from the exposed live wire, fire hazard", "Urgent"),
        ("A student received an electric shock, this is an emergency", "Urgent"),
        ("The water pipe is broken and no water is coming", "High"),
        ("The fan has stopped working completely", "High"),
        ("The wall paint looks slightly faded, a minor cosmetic request", "Low"),
    ],
)
def test_priority_prediction(text, expected):
    assert priority_module.predict(description=text)["priority"] == expected


def test_priority_gives_a_reason_and_sla():
    result = priority_module.predict(description="There is sparking from the live wire")

    assert result["reason"]
    assert result["triggers"]
    assert result["slaDays"] == 1  # Urgent -> 1 day


def test_widespread_impact_raises_the_priority():
    single = priority_module.predict(description="The light in my room flickers sometimes")
    many = priority_module.predict(
        description="The light flickers sometimes and it affects the entire hostel block"
    )
    order = ["Low", "Medium", "High", "Urgent"]
    assert order.index(many["priority"]) >= order.index(single["priority"])


def test_priority_defaults_to_medium():
    assert priority_module.predict(description="The notice board needs a new schedule")["priority"] == "Medium"


# ----------------------------------------------------------------- NLP


def test_cleaning_and_stopword_removal():
    result = process("The water IS leaking from the pipe!!! Please fix it.")

    assert "!!!" not in result["cleaned"]
    assert result["cleaned"] == result["cleaned"].lower()
    assert "the" not in result["contentTokens"]
    assert "please" not in result["contentTokens"]
    assert "water" in result["contentTokens"]


def test_stemming_collapses_word_forms():
    assert stem("leaking") == stem("leaks") == "leak"
    assert stem("leakage") == "leak"


def test_entity_extraction():
    entities = process("Water leaking in room no 214 of Gayatri Bhavan since 3 days")["entities"]

    assert "roomNumber" in entities
    assert "214" in entities["roomNumber"][0]
    assert "duration" in entities


def test_phrase_detection_keeps_multi_word_signals():
    assert "short circuit" in process("There was a short circuit in the panel")["phrases"]


# ------------------------------------------------------ duplicate detection


def test_identical_text_scores_as_a_duplicate():
    text = "Water leaking from the pipeline near Gayatri Bhavan hostel entrance"
    candidates = [{"id": "C-1", "title": text, "description": text, "department": "Jal Kal Vibhag", "status": "Submitted", "submittedAt": "2026-01-01T00:00:00.000Z"}]

    report = duplicate_detection.duplicate_report(text, text, "Jal Kal Vibhag", candidates)
    assert report["isDuplicate"] is True
    assert report["similarComplaintId"] == "C-1"
    assert report["similarityScore"] > 55


def test_unrelated_complaints_are_not_duplicates():
    candidates = [{
        "id": "C-2",
        "title": "Computer lab printer not working",
        "description": "The printer in the computer lab has run out of toner and will not print",
        "department": "MCA Lab / Computer Lab", "status": "Submitted",
        "submittedAt": "2026-01-01T00:00:00.000Z",
    }]

    report = duplicate_detection.duplicate_report(
        "Water leaking from the pipeline",
        "There is continuous water leakage from the underground pipeline near the hostel",
        "", candidates,
    )
    assert report["isDuplicate"] is False


def test_duplicate_check_excludes_the_complaint_itself():
    text = "Water leaking from the pipeline near the hostel entrance every morning"
    candidates = [{"id": "C-3", "title": text, "description": text, "department": "Jal Kal Vibhag", "status": "Submitted", "submittedAt": "2026-01-01T00:00:00.000Z"}]

    report = duplicate_detection.duplicate_report(text, text, "Jal Kal Vibhag", candidates, exclude_id="C-3")
    assert report["matches"] == []


def test_very_short_text_is_not_compared():
    assert duplicate_detection.find_duplicates("hi", "there", candidates=[{"id": "X", "title": "hi there", "description": "hi there"}]) == []


# ------------------------------------------------------------- AI endpoints


def test_classify_endpoint(client, auth, student_token):
    response = client.post(
        "/api/ai/classify",
        json={
            "title": "Water leakage near the hostel",
            "description": "A pipeline joint has been leaking continuously for two days near the entrance",
            "category": "Water",
        },
        headers=auth(student_token),
    )

    data = response.get_json()["data"]
    assert response.status_code == 200
    assert data["department"] == "Jal Kal Vibhag"
    assert data["suggestedOfficerId"]
    assert data["modelTrained"] is False


def test_classify_requires_authentication(client):
    assert client.post("/api/ai/classify", json={"description": "test"}).status_code == 401


def test_classify_rejects_text_that_is_too_short(client, auth, student_token):
    response = client.post(
        "/api/ai/classify", json={"title": "a", "description": "b"}, headers=auth(student_token)
    )
    assert response.status_code == 400


def test_duplicates_endpoint_finds_an_existing_complaint(client, auth, student_token, make_complaint, water_complaint):
    make_complaint()

    response = client.post(
        "/api/ai/duplicates",
        json={
            "title": water_complaint["title"],
            "description": water_complaint["description"],
            "department": "Jal Kal Vibhag",
        },
        headers=auth(student_token),
    )

    data = response.get_json()["data"]
    assert data["matches"]
    assert data["similarityScore"] > 0


def test_ai_status_endpoint_is_honest_about_the_model(client):
    data = client.get("/api/ai/status").get_json()["data"]

    assert data["classification"]["modelTrained"] is False
    assert data["priority"]["modelTrained"] is False
    assert "rule-based" in data["notice"].lower()


def test_ocr_reports_cleanly_when_disabled(client, auth, student_token):
    """OCR being off must not break the endpoint - it reports, never crashes."""
    import io

    response = client.post(
        "/api/ai/ocr",
        data={"file": (io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"\x00" * 200), "notice.png")},
        content_type="multipart/form-data",
        headers=auth(student_token),
    )

    assert response.status_code == 200
    ocr = response.get_json()["data"]["ocr"]
    assert ocr["success"] is False
    assert ocr["error"]  # explains that OCR is disabled or missing
