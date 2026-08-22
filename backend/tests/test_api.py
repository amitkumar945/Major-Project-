"""Officers, departments, notifications, analytics, SLA, audit and envelope."""


# ---------------------------------------------------------------- officers


def test_officer_directory_has_live_workload(client, auth, admin_token):
    officers = client.get("/api/officers", headers=auth(admin_token)).get_json()["data"]

    assert officers
    assert all("workload" in officer for officer in officers)
    assert all("passwordHash" not in officer for officer in officers)


def test_officer_suggestion_picks_the_lightest_load(client, auth, admin_token):
    response = client.get("/api/officers/suggest?department=Jal Kal Vibhag", headers=auth(admin_token))

    assert response.status_code == 200
    assert response.get_json()["data"]["department"] == "Jal Kal Vibhag"


def test_officer_cannot_read_another_officers_queue(client, auth, officer_token):
    response = client.get("/api/officers/OFF-2001/complaints", headers=auth(officer_token))
    assert response.status_code == 403


def test_deactivating_an_officer_with_open_work_is_refused(client, auth, admin_token, make_complaint):
    complaint = make_complaint()
    officer_id = complaint["assignedOfficer"]["id"]

    response = client.put(f"/api/officers/{officer_id}/status", json={}, headers=auth(admin_token))
    assert response.status_code == 409
    assert "reassign" in response.get_json()["message"].lower()


# -------------------------------------------------------------- departments


def test_department_list_is_public(client):
    response = client.get("/api/departments")
    data = response.get_json()["data"]

    assert response.status_code == 200
    assert len(data) == 4
    assert {d["name"] for d in data} == {
        "Nirman Vibhag", "Jal Kal Vibhag", "Vidyut Vibhag", "MCA Lab / Computer Lab",
    }


def test_department_counters_reflect_real_complaints(client, make_complaint):
    make_complaint()
    departments = client.get("/api/departments").get_json()["data"]
    jalkal = next(d for d in departments if d["name"] == "Jal Kal Vibhag")

    assert jalkal["totalComplaints"] >= 1
    assert "resolutionRate" in jalkal


def test_only_an_admin_can_create_a_department(client, auth, student_token):
    response = client.post(
        "/api/departments",
        json={"name": "Test Dept", "code": "TEST", "head": "X", "email": "t@dsvv.ac.in"},
        headers=auth(student_token),
    )
    assert response.status_code == 403


def test_admin_creates_and_deletes_a_department(client, auth, admin_token):
    created = client.post(
        "/api/departments",
        json={"name": "Transport Vibhag", "code": "TRANS", "head": "Mr. X",
              "email": "transport@dsvv.ac.in", "description": "Campus transport"},
        headers=auth(admin_token),
    )
    assert created.status_code == 201

    deleted = client.delete("/api/departments/TRANS", headers=auth(admin_token))
    assert deleted.status_code == 200


def test_a_department_with_complaints_cannot_be_deleted(client, auth, admin_token, make_complaint):
    make_complaint()
    response = client.delete("/api/departments/JALKAL", headers=auth(admin_token))

    assert response.status_code == 409
    assert "complaint" in response.get_json()["message"].lower()


# ------------------------------------------------------------ notifications


def test_submitting_a_complaint_notifies_the_student(client, auth, student_token, make_complaint):
    make_complaint()
    notifications = client.get("/api/notifications", headers=auth(student_token)).get_json()["data"]

    assert notifications
    assert any(n["type"] == "submitted" for n in notifications)


def test_submitting_a_complaint_notifies_the_officer(client, auth, officer_token, make_complaint):
    make_complaint()
    notifications = client.get("/api/notifications", headers=auth(officer_token)).get_json()["data"]
    assert any(n["type"] == "assigned" for n in notifications)


def test_resolution_notifies_the_complainant(client, auth, student_token, officer_token, make_complaint):
    complaint = make_complaint()
    client.post(
        f"/api/complaints/{complaint['id']}/resolve",
        json={"notes": "Replaced the damaged pipeline joint."},
        headers=auth(officer_token),
    )

    notifications = client.get("/api/notifications", headers=auth(student_token)).get_json()["data"]
    assert any(n["type"] == "resolved" for n in notifications)


def test_mark_read_and_read_all(client, auth, student_token, make_complaint):
    make_complaint()

    items = client.get("/api/notifications", headers=auth(student_token)).get_json()["data"]
    first = items[0]["id"]

    assert client.put(f"/api/notifications/{first}/read", json={}, headers=auth(student_token)).status_code == 200
    assert client.put("/api/notifications/read-all", json={}, headers=auth(student_token)).status_code == 200

    count = client.get("/api/notifications/unread-count", headers=auth(student_token)).get_json()["data"]["count"]
    assert count == 0


def test_a_user_cannot_read_another_users_notification(client, auth, student_token, officer_token, make_complaint):
    make_complaint()
    officer_items = client.get("/api/notifications", headers=auth(officer_token)).get_json()["data"]

    response = client.put(
        f"/api/notifications/{officer_items[0]['id']}/read", json={}, headers=auth(student_token)
    )
    assert response.status_code == 404


# ---------------------------------------------------------------- analytics


def test_analytics_overview_has_every_chart_dataset(client, auth, admin_token, make_complaint):
    make_complaint()
    data = client.get("/api/analytics/overview", headers=auth(admin_token)).get_json()["data"]

    for key in (
        "metrics", "byStatus", "byDepartment", "byPriority", "monthlyTrend",
        "resolutionTime", "officerPerformance", "departmentPerformance",
        "satisfaction", "weeklyLoad", "averageRating", "feedbackCount",
    ):
        assert key in data, f"missing {key}"


def test_chart_data_uses_the_name_value_shape(client, auth, admin_token, make_complaint):
    """`components/charts.js` draws [{name, value}] - the API must match."""
    make_complaint()
    data = client.get("/api/analytics/overview", headers=auth(admin_token)).get_json()["data"]

    for row in data["byDepartment"]:
        assert set(row) == {"name", "value"}
    for row in data["byPriority"]:
        assert set(row) == {"name", "value"}


def test_student_analytics_are_scoped_to_that_student(client, auth, student_token, make_complaint):
    make_complaint()
    data = client.get("/api/analytics/summary", headers=auth(student_token)).get_json()["data"]
    assert data["total"] >= 1


def test_students_cannot_read_the_admin_overview(client, auth, student_token):
    assert client.get("/api/analytics/overview", headers=auth(student_token)).status_code == 403


def test_monthly_trend_covers_twelve_months(client, auth, admin_token):
    data = client.get("/api/analytics/overview", headers=auth(admin_token)).get_json()["data"]
    assert len(data["monthlyTrend"]) == 12


def test_weekly_load_covers_seven_days(client, auth, admin_token):
    data = client.get("/api/analytics/overview", headers=auth(admin_token)).get_json()["data"]
    assert len(data["weeklyLoad"]) == 7


# --------------------------------------------------------------------- SLA


def test_sla_report(client, auth, admin_token, make_complaint):
    make_complaint()
    data = client.get("/api/admin/sla", headers=auth(admin_token)).get_json()["data"]

    assert "complianceRate" in data
    assert "breached" in data
    assert data["open"] >= 1


def test_sla_check_escalates_an_overdue_complaint(client, auth, admin_token, make_complaint, app):
    """Backdate a deadline, then confirm the sweep escalates it."""
    complaint = make_complaint()

    with app.app_context():
        from database import complaints
        from utils.helpers import iso, utcnow
        from datetime import timedelta

        complaints().update_one(
            {"id": complaint["id"]},
            {"$set": {"deadline": iso(utcnow() - timedelta(days=4))}},
        )

    result = client.post("/api/admin/sla-check", json={}, headers=auth(admin_token)).get_json()["data"]
    assert complaint["id"] in result["escalatedIds"]

    updated = client.get(f"/api/complaints/{complaint['id']}", headers=auth(admin_token)).get_json()["data"]
    assert updated["status"] == "Escalated"
    assert updated["escalationLevel"] >= 2


def test_escalations_list_shows_overdue_complaints(client, auth, admin_token, make_complaint, app):
    complaint = make_complaint()

    with app.app_context():
        from database import complaints
        from utils.helpers import iso, utcnow
        from datetime import timedelta

        complaints().update_one(
            {"id": complaint["id"]}, {"$set": {"deadline": iso(utcnow() - timedelta(days=3))}}
        )

    data = client.get("/api/complaints/escalations", headers=auth(admin_token)).get_json()["data"]
    assert any(item["id"] == complaint["id"] and item["daysOverdue"] >= 3 for item in data)


# --------------------------------------------------------------- audit log


def test_audit_log_records_the_key_actions(client, auth, admin_token, officer_token, make_complaint):
    complaint = make_complaint()
    client.put(
        f"/api/complaints/{complaint['id']}/status",
        json={"status": "In Progress"}, headers=auth(officer_token),
    )

    logs = client.get("/api/admin/audit-logs", headers=auth(admin_token)).get_json()["data"]
    actions = {entry["action"] for entry in logs["items"]}

    assert "complaint_created" in actions
    assert "status_changed" in actions
    assert "login" in actions


def test_audit_log_captures_who_did_what(client, auth, admin_token, make_complaint):
    make_complaint()
    logs = client.get("/api/admin/audit-logs?action=complaint_created", headers=auth(admin_token)).get_json()["data"]

    entry = logs["items"][0]
    assert entry["userId"]
    assert entry["role"] == "student"
    assert entry["at"]
    assert entry["complaintId"]


def test_students_cannot_read_the_audit_log(client, auth, student_token):
    assert client.get("/api/admin/audit-logs", headers=auth(student_token)).status_code == 403


# ------------------------------------------------------- response envelope


def test_success_envelope_shape(client):
    body = client.get("/api/departments").get_json()
    assert set(body) == {"success", "message", "data"}
    assert body["success"] is True


def test_error_envelope_shape(client):
    body = client.get("/api/complaints/my").get_json()
    assert set(body) == {"success", "message", "error"}
    assert body["success"] is False
    assert body["message"]


def test_unknown_api_path_returns_json_not_html(client):
    """The frontend catch-all must never swallow an unmatched API route."""
    response = client.get("/api/no-such-endpoint")

    assert response.status_code == 404
    assert response.is_json
    assert response.get_json()["success"] is False


def test_health_endpoint(client):
    body = client.get("/api/health").get_json()
    assert body["data"]["status"] == "ok"
    assert body["data"]["database"] is True


def test_no_response_ever_contains_a_password_hash(client, auth, admin_token, make_complaint):
    make_complaint()

    for path in ("/api/users", "/api/officers", "/api/complaints", "/api/departments"):
        text = client.get(path, headers=auth(admin_token)).get_data(as_text=True)
        assert "passwordHash" not in text
        assert "$2b$" not in text


def test_secrets_are_not_exposed_by_the_settings_endpoint(client, auth, admin_token):
    text = client.get("/api/admin/settings", headers=auth(admin_token)).get_data(as_text=True)

    assert "JWT_SECRET" not in text
    assert "MONGO_URI" not in text
    assert "mongodb://" not in text
