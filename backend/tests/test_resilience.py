"""
Resilience of the complaint path when a *supporting* subsystem fails.

Classification, notifications and audit logging all hang off complaint
submission, but none of them is the point of it. A student pressing "Submit"
is handing over a grievance; losing that grievance because a keyword
classifier raised, or because the notifications collection was briefly
unreachable, is the worst failure this system can have.

So each test below breaks one subsystem and asserts the complaint still lands:
201 to the caller, a real document in the database, sensible fallback routing.

The scheduler tests cover the opposite guarantee - that the periodic SLA sweep
stays off unless it is explicitly switched on.
"""

import pytest

from database import complaints


def _break(monkeypatch, module, attribute, message):
    """Replace `module.attribute` with something that always raises."""

    def explode(*args, **kwargs):
        raise RuntimeError(message)

    monkeypatch.setattr(module, attribute, explode)


# --------------------------------------------------------------- AI failure


def test_complaint_survives_unexpected_ai_failure(client, auth, student_token, water_complaint, monkeypatch):
    """A crash inside the classifier must not cost the user their complaint.

    `ApiException` (text too short) was already handled. This covers everything
    else - a bug in a prediction module, a future ML model that throws, a
    database problem while gathering duplicate candidates.
    """
    from services import ai_service

    _break(monkeypatch, ai_service, "analyse", "simulated classifier crash")

    response = client.post("/api/complaints", json=water_complaint, headers=auth(student_token))

    assert response.status_code == 201, response.get_json()
    body = response.get_json()["data"]

    # Stored, with usable fallback routing rather than nothing at all.
    assert body["id"]
    assert body["department"]
    assert body["priority"]
    assert complaints().find_one({"id": body["id"]}) is not None


def test_ai_failure_falls_back_to_submitted_department(client, auth, student_token, water_complaint, monkeypatch):
    """With the classifier down, an explicitly supplied department is honoured."""
    from services import ai_service

    _break(monkeypatch, ai_service, "analyse", "simulated classifier crash")

    payload = {**water_complaint, "department": "Vidyut Vibhag", "priority": "Urgent"}
    response = client.post("/api/complaints", json=payload, headers=auth(student_token))

    assert response.status_code == 201, response.get_json()
    body = response.get_json()["data"]
    assert body["department"] == "Vidyut Vibhag"
    assert body["priority"] == "Urgent"


# ----------------------------------------------------- notification failure


def test_complaint_survives_notification_store_failure(client, auth, student_token, water_complaint, monkeypatch):
    """The complaint is already written when notifications are sent.

    Letting that failure escape would return 500 for a complaint that IS in the
    database, so the student would submit it again.
    """
    import services.notification_service as notification_service

    _break(monkeypatch, notification_service, "notifications", "notifications collection unavailable")

    response = client.post("/api/complaints", json=water_complaint, headers=auth(student_token))

    assert response.status_code == 201, response.get_json()
    assert complaints().find_one({"id": response.get_json()["data"]["id"]}) is not None


def test_notification_create_returns_none_instead_of_raising(app, monkeypatch):
    """`create()` reports failure by returning None, never by raising."""
    import services.notification_service as notification_service

    _break(monkeypatch, notification_service, "notifications", "collection unavailable")

    with app.app_context():
        assert notification_service.create("USR-1", "status", "Title", "Message", "CMP-1") is None


# ------------------------------------------------------------ audit failure


def test_complaint_survives_audit_log_failure(client, auth, student_token, water_complaint, monkeypatch):
    """Audit logging is best-effort and must not abort the user's action."""
    import services.audit_service as audit_service

    _break(monkeypatch, audit_service, "audit_logs", "audit collection unavailable")

    response = client.post("/api/complaints", json=water_complaint, headers=auth(student_token))

    assert response.status_code == 201, response.get_json()
    assert complaints().find_one({"id": response.get_json()["data"]["id"]}) is not None


def test_complaint_survives_every_support_system_failing(
    client, auth, student_token, water_complaint, monkeypatch
):
    """The worst case: classification, notifications and audit all down."""
    import services.audit_service as audit_service
    import services.notification_service as notification_service
    from services import ai_service

    _break(monkeypatch, ai_service, "analyse", "classifier down")
    _break(monkeypatch, notification_service, "notifications", "notifications down")
    _break(monkeypatch, audit_service, "audit_logs", "audit down")

    response = client.post("/api/complaints", json=water_complaint, headers=auth(student_token))

    assert response.status_code == 201, response.get_json()
    assert complaints().find_one({"id": response.get_json()["data"]["id"]}) is not None


# ---------------------------------------------------------- SLA scheduler


def test_sla_scheduler_is_off_by_default(app):
    """It must stay opt-in: an existing deployment gets no new background work."""
    from services import scheduler_service

    assert app.config.get("SLA_AUTO_CHECK") is False
    assert scheduler_service.start(app) is False
    assert scheduler_service._timer is None


def test_sla_scheduler_starts_and_stops_when_enabled(app):
    """When switched on it schedules a daemon timer, and stop() clears it."""
    from services import scheduler_service

    app.config["SLA_AUTO_CHECK"] = True
    app.config["SLA_CHECK_INTERVAL_MINUTES"] = 60
    try:
        assert scheduler_service.start(app) is True
        assert scheduler_service._timer is not None
        assert scheduler_service._timer.daemon is True
    finally:
        scheduler_service.stop()
        app.config["SLA_AUTO_CHECK"] = False

    assert scheduler_service._timer is None


def test_sla_sweep_escalates_an_overdue_complaint(app, make_complaint):
    """The job the scheduler runs really does escalate a breached complaint."""
    from services import scheduler_service

    complaint = make_complaint()
    complaints().update_one(
        {"id": complaint["id"]}, {"$set": {"deadline": "2020-01-01T00:00:00.000Z"}}
    )

    scheduler_service._run_once(app)

    updated = complaints().find_one({"id": complaint["id"]}, {"_id": 0})
    assert updated["escalationLevel"] > 0
    assert updated["status"] == "Escalated"


def test_sla_sweep_never_raises_when_the_check_fails(app, monkeypatch):
    """A failing sweep is logged, not propagated - the thread must survive it."""
    from services import escalation_service, scheduler_service

    _break(monkeypatch, escalation_service, "run_sla_check", "database unreachable")

    scheduler_service._run_once(app)  # must not raise
