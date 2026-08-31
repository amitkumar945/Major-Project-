"""
OTP confidentiality and the list-pagination contract.

The central rule: a verification code may only ever appear in an API response
in a genuinely non-production environment. Returning one in production hands
anybody who knows an address the ability to reset that account's password, so
the flag alone is not enough - `config.is_otp_dev_mode` also requires the
process not to be in production.
"""

import pytest

from config import Config, TestConfig, is_otp_dev_mode


class _Env:
    """Minimal stand-in for a config object."""

    def __init__(self, **values):
        self.__dict__.update(values)


def _env(**overrides):
    base = {"OTP_DEV_MODE": True, "IS_TEST": False, "DEBUG": False, "FLASK_ENV": "production"}
    base.update(overrides)
    return _Env(**base)


# ------------------------------------------------------- the environment gate


def test_the_flag_is_ignored_in_production():
    assert is_otp_dev_mode(_env(OTP_DEV_MODE=True)) is False


def test_the_flag_is_honoured_under_debug():
    assert is_otp_dev_mode(_env(DEBUG=True)) is True


def test_the_flag_is_honoured_in_a_development_env():
    assert is_otp_dev_mode(_env(FLASK_ENV="development")) is True


def test_dev_mode_is_off_when_the_flag_is_off():
    assert is_otp_dev_mode(_env(OTP_DEV_MODE=False, DEBUG=True)) is False


def test_the_test_configuration_keeps_dev_mode():
    """So the suite can still read codes out of responses."""
    assert is_otp_dev_mode(TestConfig) is True


def test_the_shipped_default_is_off():
    """An operator who never sets the key must not get the leaky behaviour."""
    import os

    if os.environ.get("OTP_DEV_MODE"):
        pytest.skip("OTP_DEV_MODE is set in this environment's .env")
    assert Config.OTP_DEV_MODE is False


# ------------------------------------------------------- no leak in production


@pytest.fixture
def production_client(app):
    """The app with dev mode neutralised, as on a deployed server."""
    app.config["IS_TEST"] = False
    app.config["FLASK_ENV"] = "production"
    app.config["DEBUG"] = False
    yield app.test_client()
    app.config["IS_TEST"] = True
    app.config["FLASK_ENV"] = "test"


def test_forgot_password_never_returns_a_code_in_production(production_client):
    response = production_client.post(
        "/api/auth/forgot-password", json={"email": "student@dsvv.ac.in"}
    )
    assert "otp" not in response.get_json()["data"]
    assert "devMode" not in response.get_json()["data"]


def test_forgot_password_cannot_be_used_to_discover_accounts(production_client):
    """Registered and unregistered addresses must be indistinguishable."""
    known = production_client.post(
        "/api/auth/forgot-password", json={"email": "student@dsvv.ac.in"}
    ).get_json()
    unknown = production_client.post(
        "/api/auth/forgot-password", json={"email": "no-such-person@dsvv.ac.in"}
    ).get_json()

    assert known == unknown


def test_send_otp_never_returns_a_code_in_production(production_client):
    response = production_client.post(
        "/api/auth/send-otp", json={"email": "student@dsvv.ac.in", "purpose": "verify_email"}
    )
    assert "otp" not in (response.get_json().get("data") or {})


def test_admin_settings_reports_the_effective_mode(production_client, client, auth, admin_token):
    """Not the raw flag - an admin must not be told codes are being returned
    when they are not, or the reverse."""
    response = production_client.get("/api/admin/settings", headers=auth(admin_token))
    assert response.get_json()["data"]["otp"]["devMode"] is False


# ------------------------------------------------------- lifecycle still holds


def test_a_code_is_still_returned_in_development(client):
    response = client.post("/api/auth/forgot-password", json={"email": "student@dsvv.ac.in"})
    assert response.get_json()["data"].get("otp")


def test_a_code_cannot_be_used_twice(client):
    otp = client.post(
        "/api/auth/forgot-password", json={"email": "student@dsvv.ac.in"}
    ).get_json()["data"]["otp"]

    first = client.post(
        "/api/auth/reset-password",
        json={"email": "student@dsvv.ac.in", "otp": otp, "newPassword": "Passw0rd!New"},
    )
    assert first.status_code == 200

    second = client.post(
        "/api/auth/reset-password",
        json={"email": "student@dsvv.ac.in", "otp": otp, "newPassword": "Passw0rd!Again"},
    )
    assert second.status_code >= 400


def test_an_expired_code_is_rejected(client):
    from datetime import timedelta

    from database import otps
    from utils.helpers import utcnow

    otp = client.post(
        "/api/auth/forgot-password", json={"email": "student@dsvv.ac.in"}
    ).get_json()["data"]["otp"]

    otps().update_one(
        {"email": "student@dsvv.ac.in", "purpose": "password_reset"},
        {"$set": {"expiresAt": utcnow() - timedelta(seconds=30)}},
    )

    response = client.post(
        "/api/auth/reset-password",
        json={"email": "student@dsvv.ac.in", "otp": otp, "newPassword": "Passw0rd!New"},
    )
    assert response.status_code >= 400


def test_repeated_wrong_codes_are_cut_off(client):
    client.post("/api/auth/forgot-password", json={"email": "student@dsvv.ac.in"})

    statuses = [
        client.post(
            "/api/auth/verify-otp",
            json={"email": "student@dsvv.ac.in", "otp": "000000", "purpose": "password_reset"},
        ).status_code
        for _ in range(8)
    ]
    assert 429 in statuses


# ------------------------------------------------------------ list pagination


LIST_PATHS = ["/api/officers", "/api/notifications", "/api/departments", "/api/feedback"]


@pytest.mark.parametrize("path", LIST_PATHS)
def test_list_endpoints_still_return_a_bare_array(path, client, auth, admin_token):
    """The website spreads and maps these directly - changing the default
    shape would break live pages."""
    data = client.get(path, headers=auth(admin_token)).get_json()["data"]
    assert isinstance(data, list)


@pytest.mark.parametrize("path", LIST_PATHS)
def test_list_endpoints_paginate_when_asked(path, client, auth, admin_token):
    data = client.get(path + "?page=1&pageSize=2", headers=auth(admin_token)).get_json()["data"]
    assert {"items", "total", "page", "pageSize", "totalPages"} <= set(data)
    assert len(data["items"]) <= 2


def test_an_oversized_page_is_clamped(client, auth, admin_token):
    data = client.get("/api/complaints?pageSize=999999", headers=auth(admin_token)).get_json()["data"]
    assert data["pageSize"] <= 100


def test_the_dashboard_bulk_read_still_works(client, auth, admin_token):
    """The charts ask for every row; capping them would silently truncate."""
    data = client.get("/api/complaints?pageSize=10000", headers=auth(admin_token)).get_json()["data"]
    assert data["pageSize"] == 10000


def test_a_non_numeric_page_size_does_not_crash(client, auth, admin_token):
    response = client.get("/api/complaints?pageSize=abc&page=xyz", headers=auth(admin_token))
    assert response.status_code == 200
