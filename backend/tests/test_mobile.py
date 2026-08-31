"""
Mobile session support: refresh tokens and push-device registration.

The rule these tests exist to protect is that the WEBSITE is unaffected. A web
login must keep returning exactly `{user, token, issuedAt}` with the 12-hour
token it always had; only a client that identifies as mobile gets the short
access token and a refresh token.
"""

import hashlib
from datetime import timedelta

import jwt as pyjwt
import pytest

from database import devices, refresh_tokens
from utils.helpers import utcnow


def _login(client, email="student@dsvv.ac.in", password="student123", mobile=False):
    body = {"identifier": email, "password": password}
    if mobile:
        body["client"] = "mobile"
    response = client.post("/api/auth/login", json=body)
    assert response.status_code == 200, response.get_json()
    return response.get_json()["data"]


def _claims(token):
    return pyjwt.decode(token, options={"verify_signature": False})


# ------------------------------------------------------- the web is unchanged


def test_a_web_login_gets_no_refresh_token(client):
    session = _login(client)
    assert "refreshToken" not in session
    assert set(session) == {"user", "token", "issuedAt"}


def test_a_web_access_token_keeps_its_original_lifetime(client, app):
    session = _login(client)
    claims = _claims(session["token"])
    hours = (claims["exp"] - claims["iat"]) / 3600
    assert round(hours) == app.config["JWT_EXPIRY_HOURS"]


def test_web_logout_still_works_without_a_body(client):
    session = _login(client)
    response = client.post(
        "/api/auth/logout", headers={"Authorization": "Bearer " + session["token"]}
    )
    assert response.status_code == 200


# ------------------------------------------------------------ mobile sessions


def test_a_mobile_login_returns_a_refresh_token(client):
    session = _login(client, mobile=True)
    assert session["refreshToken"]
    assert session["refreshExpiresIn"] > 0
    # The web keys are still all present - added to, never replaced.
    assert {"user", "token", "issuedAt"} <= set(session)


def test_the_mobile_access_token_is_short_lived(client, app):
    session = _login(client, mobile=True)
    claims = _claims(session["token"])
    minutes = (claims["exp"] - claims["iat"]) / 60
    assert round(minutes) == app.config["MOBILE_ACCESS_TOKEN_MINUTES"]


def test_the_x_client_type_header_also_selects_a_mobile_session(client):
    response = client.post(
        "/api/auth/login",
        json={"identifier": "student@dsvv.ac.in", "password": "student123"},
        headers={"X-Client-Type": "mobile"},
    )
    assert response.get_json()["data"]["refreshToken"]


def test_a_refresh_token_buys_a_working_access_token(client):
    session = _login(client, mobile=True)

    response = client.post("/api/auth/refresh", json={"refreshToken": session["refreshToken"]})
    assert response.status_code == 200

    refreshed = response.get_json()["data"]
    me = client.get("/api/auth/me", headers={"Authorization": "Bearer " + refreshed["token"]})
    assert me.status_code == 200


def test_refreshing_rotates_the_refresh_token(client):
    session = _login(client, mobile=True)
    refreshed = client.post(
        "/api/auth/refresh", json={"refreshToken": session["refreshToken"]}
    ).get_json()["data"]

    assert refreshed["refreshToken"] != session["refreshToken"]


def test_an_expired_access_token_can_be_exchanged_for_a_new_one(client, app):
    """The whole point of refresh: it works once the access token is dead."""
    session = _login(client, mobile=True)

    expired = pyjwt.encode(
        {**_claims(session["token"]), "exp": int(utcnow().timestamp()) - 60},
        app.config["JWT_SECRET_KEY"],
        algorithm="HS256",
    )
    assert client.get("/api/auth/me", headers={"Authorization": "Bearer " + expired}).status_code == 401

    refreshed = client.post(
        "/api/auth/refresh", json={"refreshToken": session["refreshToken"]}
    ).get_json()["data"]
    assert client.get(
        "/api/auth/me", headers={"Authorization": "Bearer " + refreshed["token"]}
    ).status_code == 200


def test_a_used_refresh_token_is_rejected(client):
    session = _login(client, mobile=True)
    client.post("/api/auth/refresh", json={"refreshToken": session["refreshToken"]})

    again = client.post("/api/auth/refresh", json={"refreshToken": session["refreshToken"]})
    assert again.status_code == 401


def test_reuse_revokes_the_whole_chain(client):
    """Presenting a consumed token means it leaked; every session must die."""
    session = _login(client, mobile=True)
    rotated = client.post(
        "/api/auth/refresh", json={"refreshToken": session["refreshToken"]}
    ).get_json()["data"]

    client.post("/api/auth/refresh", json={"refreshToken": session["refreshToken"]})  # reuse

    assert client.post(
        "/api/auth/refresh", json={"refreshToken": rotated["refreshToken"]}
    ).status_code == 401


def test_an_unknown_refresh_token_is_rejected(client):
    assert client.post("/api/auth/refresh", json={"refreshToken": "nope"}).status_code == 401


def test_refresh_requires_a_token(client):
    assert client.post("/api/auth/refresh", json={}).status_code == 422


def test_an_expired_refresh_token_is_rejected(client):
    session = _login(client, mobile=True)
    refresh_tokens().update_one(
        {"tokenHash": hashlib.sha256(session["refreshToken"].encode()).hexdigest()},
        {"$set": {"expiresAt": utcnow() - timedelta(days=1)}},
    )
    assert client.post(
        "/api/auth/refresh", json={"refreshToken": session["refreshToken"]}
    ).status_code == 401


def test_logout_revokes_the_refresh_token(client):
    session = _login(client, mobile=True)
    client.post(
        "/api/auth/logout",
        headers={"Authorization": "Bearer " + session["token"]},
        json={"refreshToken": session["refreshToken"]},
    )
    assert client.post(
        "/api/auth/refresh", json={"refreshToken": session["refreshToken"]}
    ).status_code == 401


def test_a_deactivated_account_cannot_refresh(client, app):
    from database import users

    session = _login(client, mobile=True)
    users().update_one({"id": session["user"]["id"]}, {"$set": {"isActive": False}})

    assert client.post(
        "/api/auth/refresh", json={"refreshToken": session["refreshToken"]}
    ).status_code == 403


def test_the_stored_refresh_token_is_hashed_not_plaintext(client):
    session = _login(client, mobile=True)
    assert refresh_tokens().find_one({"tokenHash": session["refreshToken"]}) is None
    assert refresh_tokens().find_one(
        {"tokenHash": hashlib.sha256(session["refreshToken"].encode()).hexdigest()}
    )


# ------------------------------------------------------------ device registry


@pytest.fixture
def auth_header(client):
    return {"Authorization": "Bearer " + _login(client)["token"]}


def test_a_device_can_be_registered(client, auth_header):
    response = client.post(
        "/api/devices/register",
        headers=auth_header,
        json={"token": "fcm-aaa", "platform": "android", "deviceName": "Pixel 8"},
    )
    assert response.status_code == 201
    assert devices().count_documents({"token": "fcm-aaa"}) == 1


def test_the_response_never_contains_the_raw_token(client, auth_header):
    response = client.post(
        "/api/devices/register", headers=auth_header, json={"token": "fcm-secret-value"}
    )
    assert "fcm-secret-value" not in response.get_data(as_text=True)


def test_registering_the_same_device_twice_does_not_duplicate_it(client, auth_header):
    for _ in range(3):
        client.post("/api/devices/register", headers=auth_header, json={"token": "fcm-same"})
    assert devices().count_documents({"token": "fcm-same"}) == 1


def test_one_user_may_register_several_devices(client, auth_header):
    client.post("/api/devices/register", headers=auth_header, json={"token": "fcm-phone"})
    client.post("/api/devices/register", headers=auth_header, json={"token": "fcm-tablet"})

    listing = client.get("/api/devices", headers=auth_header).get_json()["data"]
    assert len(listing) == 2


def test_a_device_can_be_removed(client, auth_header):
    client.post("/api/devices/register", headers=auth_header, json={"token": "fcm-bye"})
    response = client.delete(
        "/api/devices/register", headers=auth_header, json={"token": "fcm-bye"}
    )
    assert response.get_json()["data"]["removed"] is True
    assert devices().count_documents({"token": "fcm-bye"}) == 0


def test_a_user_cannot_remove_another_users_device(client, auth_header):
    client.post("/api/devices/register", headers=auth_header, json={"token": "fcm-mine"})

    other = {"Authorization": "Bearer " + _login(client, "sneha.bhardwaj@dsvv.ac.in")["token"]}
    response = client.delete("/api/devices/register", headers=other, json={"token": "fcm-mine"})

    assert response.get_json()["data"]["removed"] is False
    assert devices().count_documents({"token": "fcm-mine"}) == 1


def test_a_shared_handset_moves_to_whoever_signed_in_last(client, auth_header):
    """Otherwise the new user would receive the previous user's grievances."""
    client.post("/api/devices/register", headers=auth_header, json={"token": "shared"})

    other_session = _login(client, "sneha.bhardwaj@dsvv.ac.in")
    client.post(
        "/api/devices/register",
        headers={"Authorization": "Bearer " + other_session["token"]},
        json={"token": "shared"},
    )

    assert devices().find_one({"token": "shared"})["userId"] == other_session["user"]["id"]


def test_device_registration_requires_authentication(client):
    assert client.post("/api/devices/register", json={"token": "x"}).status_code == 401


def test_device_registration_requires_a_token(client, auth_header):
    assert client.post("/api/devices/register", headers=auth_header, json={}).status_code == 422


def test_an_unknown_platform_is_rejected(client, auth_header):
    response = client.post(
        "/api/devices/register",
        headers=auth_header,
        json={"token": "fcm-x", "platform": "symbian"},
    )
    assert response.status_code == 400


def test_the_device_list_shows_only_your_own(client, auth_header):
    client.post("/api/devices/register", headers=auth_header, json={"token": "fcm-mine-2"})

    other = {"Authorization": "Bearer " + _login(client, "sneha.bhardwaj@dsvv.ac.in")["token"]}
    client.post("/api/devices/register", headers=other, json={"token": "fcm-theirs"})

    listing = client.get("/api/devices", headers=other).get_json()["data"]
    assert len(listing) == 1


def test_push_is_not_configured_by_default(app):
    """Push must be opt-in, so the existing deployment behaves as before."""
    from services import push_service

    with app.app_context():
        assert push_service.is_configured() is False
