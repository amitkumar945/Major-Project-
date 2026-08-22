"""Registration, login, JWT verification, role authorisation and OTP."""

import uuid


def _email():
    return f"pytest.{uuid.uuid4().hex[:10]}@dsvv.ac.in"


def _registration(**overrides):
    return {
        "fullName": "Pytest Student",
        "userId": "MCA/2026/777",
        "email": _email(),
        "department": "MCA - Department of Computer Science",
        "password": "StrongPass123",
        **overrides,
    }


# ------------------------------------------------------------- registration


def test_register_creates_account_and_returns_token(client):
    response = client.post("/api/auth/register", json=_registration())
    body = response.get_json()

    assert response.status_code == 201
    assert body["success"] is True
    assert body["data"]["token"]
    assert body["data"]["user"]["role"] == "student"


def test_register_never_returns_the_password_hash(client):
    response = client.post("/api/auth/register", json=_registration())
    assert "passwordHash" not in response.get_data(as_text=True)
    assert "password" not in response.get_json()["data"]["user"]


def test_register_stores_a_bcrypt_hash_not_the_plain_password(client, app):
    values = _registration()
    client.post("/api/auth/register", json=values)

    with app.app_context():
        from database import users

        record = users().find_one({"email": values["email"].lower()})

    assert record["passwordHash"] != values["password"]
    assert record["passwordHash"].startswith("$2b$")


def test_register_rejects_invalid_input(client):
    response = client.post(
        "/api/auth/register",
        json={"fullName": "X", "email": "not-an-email", "password": "short"},
    )
    assert response.status_code == 422
    fields = response.get_json()["error"]["fields"]
    assert "email" in fields and "password" in fields


def test_register_rejects_a_duplicate_email(client):
    values = _registration()
    assert client.post("/api/auth/register", json=values).status_code == 201
    assert client.post("/api/auth/register", json=values).status_code == 409


def test_register_allocates_unique_ids_past_the_seeded_accounts(client):
    """Regression: the seeds occupy USR-1001.., so the counter must skip them."""
    ids = set()
    for _ in range(3):
        response = client.post("/api/auth/register", json=_registration())
        assert response.status_code == 201
        ids.add(response.get_json()["data"]["user"]["id"])

    assert len(ids) == 3
    assert not ids & {"USR-1001", "USR-1002", "USR-1003"}


def test_self_registration_cannot_claim_the_admin_role(client):
    response = client.post("/api/auth/register", json=_registration(role="admin"))
    assert response.status_code == 403


# -------------------------------------------------------------------- login


def test_login_succeeds_with_the_seeded_demo_account(client):
    response = client.post(
        "/api/auth/login", json={"identifier": "student@dsvv.ac.in", "password": "student123"}
    )
    assert response.status_code == 200
    assert response.get_json()["data"]["token"]


def test_login_rejects_a_wrong_password(client):
    response = client.post(
        "/api/auth/login", json={"identifier": "student@dsvv.ac.in", "password": "wrong-password"}
    )
    assert response.status_code == 401


def test_login_does_not_reveal_whether_an_email_exists(client):
    unknown = client.post(
        "/api/auth/login", json={"identifier": "nobody@dsvv.ac.in", "password": "whatever123"}
    )
    wrong = client.post(
        "/api/auth/login", json={"identifier": "student@dsvv.ac.in", "password": "whatever123"}
    )
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.get_json()["message"] == wrong.get_json()["message"]


def test_login_rejects_the_wrong_role(client):
    response = client.post(
        "/api/auth/login",
        json={"identifier": "student@dsvv.ac.in", "password": "student123", "role": "admin"},
    )
    assert response.status_code == 403


# ---------------------------------------------------------- JWT / authorisation


def test_protected_route_requires_a_token(client):
    assert client.get("/api/complaints/my").status_code == 401


def test_protected_route_rejects_a_malformed_token(client, auth):
    response = client.get("/api/complaints/my", headers=auth("not.a.real.token"))
    assert response.status_code == 401


def test_expired_token_is_rejected(client, app, auth):
    """A token whose `exp` has passed must not be accepted."""
    import jwt
    from datetime import datetime, timedelta, timezone

    past = datetime.now(timezone.utc) - timedelta(hours=1)
    expired = jwt.encode(
        {
            "sub": "USR-1001", "userId": "USR-1001", "role": "student",
            "iat": int((past - timedelta(hours=1)).timestamp()),
            "exp": int(past.timestamp()),
            "iss": app.config["JWT_ISSUER"],
        },
        app.config["JWT_SECRET_KEY"],
        algorithm=app.config["JWT_ALGORITHM"],
    )

    response = client.get("/api/complaints/my", headers=auth(expired))
    assert response.status_code == 401
    assert "expired" in response.get_json()["message"].lower()


def test_token_signed_with_another_key_is_rejected(client, app, auth):
    import jwt
    from datetime import datetime, timedelta, timezone

    forged = jwt.encode(
        {
            "sub": "ADM-3001", "userId": "ADM-3001", "role": "admin",
            "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
            "iss": app.config["JWT_ISSUER"],
        },
        "an-attackers-secret",
        algorithm="HS256",
    )
    assert client.get("/api/users", headers=auth(forged)).status_code == 401


def test_student_cannot_reach_an_admin_route(client, auth, student_token):
    assert client.get("/api/users", headers=auth(student_token)).status_code == 403


def test_officer_cannot_reach_an_admin_route(client, auth, officer_token):
    assert client.get("/api/users", headers=auth(officer_token)).status_code == 403


def test_admin_can_reach_the_admin_route(client, auth, admin_token):
    assert client.get("/api/users", headers=auth(admin_token)).status_code == 200


def test_deactivated_account_cannot_use_its_existing_token(client, auth, admin_token, app):
    """A token issued before deactivation must stop working immediately."""
    login = client.post(
        "/api/auth/login", json={"identifier": "aditya.nautiyal@dsvv.ac.in", "password": "student123"}
    )
    token = login.get_json()["data"]["token"]
    assert client.get("/api/complaints/my", headers=auth(token)).status_code == 200

    client.put("/api/users/USR-1003/status", json={}, headers=auth(admin_token))

    assert client.get("/api/complaints/my", headers=auth(token)).status_code == 403


# ---------------------------------------------------------------------- OTP


def test_otp_send_and_verify(client):
    email = "student@dsvv.ac.in"
    sent = client.post("/api/auth/send-otp", json={"email": email, "purpose": "verify_email"})
    assert sent.status_code == 200

    code = sent.get_json()["data"]["otp"]  # dev mode returns the code
    verified = client.post(
        "/api/auth/verify-otp", json={"email": email, "otp": code, "purpose": "verify_email"}
    )
    assert verified.status_code == 200
    assert verified.get_json()["data"]["verified"] is True


def test_otp_rejects_a_wrong_code(client):
    email = "student@dsvv.ac.in"
    client.post("/api/auth/send-otp", json={"email": email, "purpose": "verify_email"})

    response = client.post(
        "/api/auth/verify-otp", json={"email": email, "otp": "000000", "purpose": "verify_email"}
    )
    assert response.status_code == 400


def test_otp_is_stored_hashed_never_in_plain_text(client, app):
    email = "student@dsvv.ac.in"
    sent = client.post("/api/auth/send-otp", json={"email": email, "purpose": "verify_email"})
    code = sent.get_json()["data"]["otp"]

    with app.app_context():
        from database import otps

        record = otps().find_one({"email": email, "purpose": "verify_email"})

    assert "code" not in record
    assert record["codeHash"] != code
    assert len(record["codeHash"]) == 64  # sha256 hex


def test_otp_for_one_email_cannot_be_replayed_against_another(client):
    sent = client.post(
        "/api/auth/send-otp", json={"email": "student@dsvv.ac.in", "purpose": "verify_email"}
    )
    code = sent.get_json()["data"]["otp"]

    client.post("/api/auth/send-otp", json={"email": "admin@dsvv.ac.in", "purpose": "verify_email"})
    response = client.post(
        "/api/auth/verify-otp",
        json={"email": "admin@dsvv.ac.in", "otp": code, "purpose": "verify_email"},
    )
    assert response.status_code == 400


def test_otp_resend_returns_a_fresh_code(client):
    email = "student@dsvv.ac.in"
    client.post("/api/auth/send-otp", json={"email": email, "purpose": "verify_email"})
    response = client.post("/api/auth/resend-otp", json={"email": email, "purpose": "verify_email"})
    assert response.status_code in (200, 429)  # 429 when the cooldown is still active


# ------------------------------------------------------------------ profile


def test_change_password_then_sign_in_with_the_new_one(client, auth):
    values = _registration()
    token = client.post("/api/auth/register", json=values).get_json()["data"]["token"]

    changed = client.put(
        "/api/auth/password",
        json={"currentPassword": values["password"], "newPassword": "BrandNewPass456",
              "confirmPassword": "BrandNewPass456"},
        headers=auth(token),
    )
    assert changed.status_code == 200

    assert client.post(
        "/api/auth/login", json={"identifier": values["email"], "password": "BrandNewPass456"}
    ).status_code == 200
    assert client.post(
        "/api/auth/login", json={"identifier": values["email"], "password": values["password"]}
    ).status_code == 401


def test_change_password_rejects_a_wrong_current_password(client, auth, student_token):
    response = client.put(
        "/api/auth/password",
        json={"currentPassword": "definitely-wrong", "newPassword": "BrandNewPass456"},
        headers=auth(student_token),
    )
    assert response.status_code == 401


def test_profile_update_cannot_escalate_the_role(client, auth, student_token):
    response = client.put(
        "/api/auth/profile",
        json={"name": "Renamed Student", "role": "admin", "isActive": True},
        headers=auth(student_token),
    )
    assert response.status_code == 200
    assert response.get_json()["data"]["role"] == "student"
    assert response.get_json()["data"]["name"] == "Renamed Student"


def test_forgot_password_does_not_leak_whether_the_email_exists(client):
    known = client.post("/api/auth/forgot-password", json={"email": "student@dsvv.ac.in"})
    unknown = client.post("/api/auth/forgot-password", json={"email": "nobody@dsvv.ac.in"})

    assert known.status_code == unknown.status_code == 200
    assert known.get_json()["message"] == unknown.get_json()["message"]
