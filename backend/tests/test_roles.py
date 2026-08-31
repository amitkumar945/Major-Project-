"""
Role-based access control across the three roles.

The rules under test:

  * Student / Staff - self-registers, sees only their own complaints.
  * Department Officer - created by an admin only, sees only their own
    department's complaints, and can act on them.
  * Administrator - not publicly registerable, sees and reassigns everything.

The department-isolation tests are the important ones: a complaint routed to
Jal Kal Vibhag must be invisible to the Vidyut officer, in both directions and
for reads as well as writes.
"""

import pytest

# The seeded officers, one per department.
JALKAL_EMAIL = "pankaj.semwal@dsvv.ac.in"
VIDYUT_EMAIL = "naveen.painuli@dsvv.ac.in"


def _token(client, email, password):
    response = client.post(
        "/api/auth/login", json={"identifier": email, "password": password}
    )
    assert response.status_code == 200, response.get_json()
    return response.get_json()["data"]["token"]


@pytest.fixture
def jalkal_token(client):
    return _token(client, JALKAL_EMAIL, "officer123")


@pytest.fixture
def vidyut_token(client):
    return _token(client, VIDYUT_EMAIL, "officer123")


def _submit(client, auth, token, title, description, category):
    response = client.post(
        "/api/complaints",
        headers=auth(token),
        json={
            "title": title,
            "description": description,
            "category": category,
            "location": {
                "latitude": 29.99965,
                "longitude": 78.1946,
                "address": "Campus",
            },
        },
    )
    assert response.status_code == 201, response.get_json()
    return response.get_json()["data"]


@pytest.fixture
def water_case(client, auth, student_token):
    return _submit(
        client, auth, student_token,
        "Water supply is not working in the hostel",
        "The water supply has completely stopped in the hostel building since "
        "yesterday morning and the students have no water at all.",
        "Water",
    )


@pytest.fixture
def power_case(client, auth, student_token):
    return _submit(
        client, auth, student_token,
        "Electricity fan and light problem in the room",
        "The ceiling fan and the tube light in our room have stopped working "
        "completely since last night and the switchboard is warm.",
        "Electricity",
    )


# ------------------------------------------------------ department routing


def test_a_water_complaint_routes_to_jal_kal_vibhag(water_case):
    assert water_case["department"] == "Jal Kal Vibhag"


def test_an_electricity_complaint_routes_to_vidyut_vibhag(power_case):
    assert power_case["department"] == "Vidyut Vibhag"


def test_a_routed_complaint_is_assigned_to_an_officer_of_that_department(water_case):
    officer = water_case.get("assignedOfficer")
    assert officer, "the complaint should be auto-assigned on submission"
    assert officer["department"] == "Jal Kal Vibhag"


# --------------------------------------------------- department isolation


def test_an_officer_can_read_their_own_department_complaint(
    client, auth, jalkal_token, water_case
):
    response = client.get(f"/api/complaints/{water_case['id']}", headers=auth(jalkal_token))
    assert response.status_code == 200


def test_an_officer_cannot_read_another_departments_complaint(
    client, auth, jalkal_token, power_case
):
    response = client.get(f"/api/complaints/{power_case['id']}", headers=auth(jalkal_token))
    assert response.status_code == 403


def test_isolation_holds_in_the_other_direction_too(
    client, auth, vidyut_token, water_case
):
    response = client.get(f"/api/complaints/{water_case['id']}", headers=auth(vidyut_token))
    assert response.status_code == 403


def test_an_officer_cannot_change_another_departments_complaint(
    client, auth, jalkal_token, power_case
):
    response = client.put(
        f"/api/complaints/{power_case['id']}/status",
        headers=auth(jalkal_token),
        json={"status": "In Progress"},
    )
    assert response.status_code == 403


def test_an_officers_list_contains_only_their_own_department(
    client, auth, jalkal_token, water_case, power_case
):
    response = client.get("/api/complaints", headers=auth(jalkal_token))
    items = response.get_json()["data"]["items"]

    assert items, "the officer should see their own department's complaints"
    assert {item["department"] for item in items} == {"Jal Kal Vibhag"}


# ------------------------------------------------------- officer actions


def test_an_officer_can_work_their_own_departments_complaint(
    client, auth, jalkal_token, water_case
):
    complaint_id = water_case["id"]

    status = client.put(
        f"/api/complaints/{complaint_id}/status",
        headers=auth(jalkal_token),
        json={"status": "In Progress", "remark": "Plumber assigned"},
    )
    remark = client.post(
        f"/api/complaints/{complaint_id}/remarks",
        headers=auth(jalkal_token),
        json={"message": "Replacement valve ordered from the vendor"},
    )
    resolve = client.post(
        f"/api/complaints/{complaint_id}/resolve",
        headers=auth(jalkal_token),
        json={"notes": "Main pipeline valve replaced and supply tested."},
    )

    assert status.status_code == 200
    assert remark.status_code == 201
    assert resolve.status_code == 200


def test_an_officer_cannot_reassign_or_list_users(client, auth, jalkal_token, water_case):
    """Reassignment and the user directory are administrator-only."""
    reassign = client.post(
        f"/api/complaints/{water_case['id']}/assign",
        headers=auth(jalkal_token),
        json={"officerId": "OFF-2001"},
    )
    users = client.get("/api/users", headers=auth(jalkal_token))

    assert reassign.status_code == 403
    assert users.status_code == 403


# ------------------------------------------------------ student isolation


def test_a_student_sees_only_their_own_complaints(client, auth, student_token, water_case):
    items = client.get("/api/complaints", headers=auth(student_token)).get_json()["data"]["items"]
    me = client.get("/api/auth/me", headers=auth(student_token)).get_json()["data"]

    assert items
    assert {item["submittedBy"]["id"] for item in items} == {me["id"]}


def test_a_student_is_notified_as_their_complaint_progresses(
    client, auth, student_token, jalkal_token, water_case
):
    client.put(
        f"/api/complaints/{water_case['id']}/status",
        headers=auth(jalkal_token),
        json={"status": "In Progress"},
    )
    client.post(
        f"/api/complaints/{water_case['id']}/resolve",
        headers=auth(jalkal_token),
        json={"notes": "Main pipeline valve replaced and supply tested."},
    )

    payload = client.get("/api/notifications", headers=auth(student_token)).get_json()["data"]
    items = payload["items"] if isinstance(payload, dict) else payload

    assert any("resolved" in (item.get("title") or "").lower() for item in items)


# --------------------------------------------------- account creation rules


def _new_officer(**overrides):
    return {
        "name": "Er. Test Officer",
        "email": "new.officer@dsvv.ac.in",
        "password": "Passw0rd!",
        "department": "Vidyut Vibhag",
        "employeeId": "EMP-777",
        "designation": "Assistant Engineer",
        "mobile": "9876543210",
        **overrides,
    }


def test_an_admin_can_create_a_department_officer(client, auth, admin_token):
    response = client.post("/api/officers", headers=auth(admin_token), json=_new_officer())

    assert response.status_code == 201
    officer = response.get_json()["data"]
    assert officer["role"] == "officer"
    assert officer["department"] == "Vidyut Vibhag"
    assert "passwordHash" not in response.get_data(as_text=True)


def test_an_officer_created_by_the_admin_can_sign_in(client, auth, admin_token):
    client.post("/api/officers", headers=auth(admin_token), json=_new_officer())

    response = client.post(
        "/api/auth/login",
        json={
            "identifier": "new.officer@dsvv.ac.in",
            "password": "Passw0rd!",
            "role": "officer",
        },
    )
    assert response.status_code == 200


def test_a_student_cannot_create_an_officer(client, auth, student_token):
    response = client.post("/api/officers", headers=auth(student_token), json=_new_officer())
    assert response.status_code == 403


def test_an_officer_cannot_create_another_officer(client, auth, officer_token):
    response = client.post("/api/officers", headers=auth(officer_token), json=_new_officer())
    assert response.status_code == 403


def test_self_registration_cannot_claim_the_officer_role(client):
    """The public register endpoint always produces a student."""
    response = client.post(
        "/api/auth/register",
        json={
            "fullName": "Sneaky Person",
            "email": "sneaky@dsvv.ac.in",
            "password": "Passw0rd!",
            "userId": "SNK1",
            "department": "MCA",
            "role": "officer",
        },
    )
    assert response.status_code == 403


# ------------------------------------------------------- login role selector


def test_the_login_role_selector_cannot_grant_a_role(client):
    """Picking Administrator on the login form must not make a student one."""
    response = client.post(
        "/api/auth/login",
        json={"identifier": "student@dsvv.ac.in", "password": "student123", "role": "admin"},
    )
    assert response.status_code == 403


def test_the_session_carries_the_stored_role_not_the_requested_one(client):
    response = client.post(
        "/api/auth/login",
        json={"identifier": "student@dsvv.ac.in", "password": "student123", "role": "student"},
    )
    assert response.get_json()["data"]["user"]["role"] == "student"


# ------------------------------------------------------------ admin reach


def test_an_admin_sees_every_departments_complaints(
    client, auth, admin_token, water_case, power_case
):
    items = client.get("/api/complaints", headers=auth(admin_token)).get_json()["data"]["items"]
    departments = {item["department"] for item in items}

    assert {"Jal Kal Vibhag", "Vidyut Vibhag"} <= departments


def test_an_admin_can_reassign_a_complaint(client, auth, admin_token, water_case):
    payload = client.get(
        "/api/officers?department=Jal Kal Vibhag", headers=auth(admin_token)
    ).get_json()["data"]
    officers = payload["items"] if isinstance(payload, dict) else payload

    response = client.put(
        f"/api/complaints/{water_case['id']}/reassign",
        headers=auth(admin_token),
        json={"officerId": officers[0]["id"], "reason": "Workload balancing"},
    )
    assert response.status_code == 200


# ------------------------------------------- creating accounts from the UI


def test_the_officer_form_payload_creates_an_officer(client, auth, admin_token):
    """The exact fields the admin "Add officer" modal submits.

    The form originally had no password field while the endpoint required one,
    so every submission failed with a 422; this pins the contract.
    """
    response = client.post(
        "/api/officers",
        headers=auth(admin_token),
        json={
            "name": "Er. Test Officer",
            "employeeId": "EMP-777",
            "email": "form.officer@dsvv.ac.in",
            "department": "Vidyut Vibhag",
            "designation": "Assistant Engineer",
            "password": "Passw0rd!",
        },
    )
    assert response.status_code == 201, response.get_json()
    assert response.get_json()["data"]["role"] == "officer"


def test_creating_an_officer_without_a_password_is_rejected(client, auth, admin_token):
    response = client.post(
        "/api/officers",
        headers=auth(admin_token),
        json={
            "name": "Er. Test Officer",
            "employeeId": "EMP-778",
            "email": "nopass.officer@dsvv.ac.in",
            "department": "Vidyut Vibhag",
            "designation": "Assistant Engineer",
        },
    )
    assert response.status_code == 422
    assert "password" in response.get_json()["error"]["fields"]


def _admin_payload(**overrides):
    return {
        "fullName": "Dr. Second Admin",
        "userId": "DSVV/ADM/002",
        "email": "second.admin@dsvv.ac.in",
        "department": "Office of the Registrar",
        "password": "Passw0rd!",
        "role": "admin",
        **overrides,
    }


def test_an_admin_can_create_another_administrator(client, auth, admin_token):
    """The only route to a second admin - there is no public sign-up for one."""
    response = client.post("/api/users", headers=auth(admin_token), json=_admin_payload())

    assert response.status_code == 201, response.get_json()
    assert response.get_json()["data"]["role"] == "admin"


def test_the_new_administrator_can_sign_in_and_reach_admin_routes(
    client, auth, admin_token
):
    client.post("/api/users", headers=auth(admin_token), json=_admin_payload())

    login = client.post(
        "/api/auth/login",
        json={
            "identifier": "second.admin@dsvv.ac.in",
            "password": "Passw0rd!",
            "role": "admin",
        },
    )
    assert login.status_code == 200

    token = login.get_json()["data"]["token"]
    assert client.get("/api/admin/dashboard", headers=auth(token)).status_code == 200


def test_a_student_cannot_create_an_administrator(client, auth, student_token):
    response = client.post("/api/users", headers=auth(student_token), json=_admin_payload())
    assert response.status_code == 403


def test_an_officer_cannot_create_an_administrator(client, auth, officer_token):
    response = client.post("/api/users", headers=auth(officer_token), json=_admin_payload())
    assert response.status_code == 403
