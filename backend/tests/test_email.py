"""
Email service and OTP delivery.

The central guarantee under test: an OTP endpoint must never answer "code sent"
for an email that was not actually accepted by the mail server. Every SMTP call
is faked with a stub connection, so the suite never opens a socket.
"""

import smtplib
import socket

import pytest

from services import email_service, otp_service
from utils.responses import ApiException

SENDER = "sender@example.com"
PASSWORD = "test-app-password-not-real"


# ------------------------------------------------------------------ helpers


class StubSMTP:
    """Stands in for smtplib.SMTP, recording what the service did with it."""

    def __init__(self, fail_on: str = "", refused: dict = None):
        self.fail_on = fail_on              # "login" | "send" | ""
        self.refused = refused or {}
        self.messages = []
        self.logins = []
        self.started_tls = False
        self.quit_called = False

    def ehlo(self, *args):
        return 250, b"ok"

    def starttls(self, *args, **kwargs):
        self.started_tls = True

    def login(self, username, password):
        self.logins.append(username)
        if self.fail_on == "login":
            raise smtplib.SMTPAuthenticationError(535, b"Invalid credentials")

    def send_message(self, message):
        if self.fail_on == "send":
            raise smtplib.SMTPException("send failed")
        self.messages.append(message)
        return self.refused

    def quit(self):
        self.quit_called = True

    def close(self):
        pass


@pytest.fixture
def mail_app(app):
    """The app with SMTP switched on and pointed at a stub."""
    original = {
        key: app.config.get(key)
        for key in (
            "MAIL_ENABLED", "MAIL_SERVER", "MAIL_PORT", "MAIL_USERNAME",
            "MAIL_PASSWORD", "MAIL_DEFAULT_SENDER", "MAIL_USE_TLS",
            "MAIL_USE_SSL", "MAIL_SUPPRESS_SEND", "OTP_DEV_MODE",
        )
    }
    app.config.update(
        MAIL_ENABLED=True,
        MAIL_SERVER="smtp.example.com",
        MAIL_PORT=587,
        MAIL_USERNAME=SENDER,
        MAIL_PASSWORD=PASSWORD,
        MAIL_DEFAULT_SENDER=SENDER,
        MAIL_USE_TLS=True,
        MAIL_USE_SSL=False,
        MAIL_SUPPRESS_SEND=False,
        OTP_DEV_MODE=False,
    )
    yield app
    app.config.update(original)


@pytest.fixture
def stub(monkeypatch):
    """Patch smtplib.SMTP so no socket is ever opened."""
    holder = {}

    def make(fail_on="", refused=None):
        connection = StubSMTP(fail_on=fail_on, refused=refused)
        holder["connection"] = connection
        monkeypatch.setattr(
            smtplib, "SMTP", lambda *args, **kwargs: connection
        )
        return connection

    holder["make"] = make
    return holder


# ------------------------------------------------------------ configuration


def test_is_configured_is_false_when_mail_is_disabled(app):
    with app.app_context():
        assert email_service.is_configured() is False


def test_is_configured_is_true_once_the_values_are_present(mail_app):
    with mail_app.app_context():
        assert email_service.is_configured() is True


def test_describe_config_never_returns_the_password(mail_app):
    with mail_app.app_context():
        info = email_service.describe_config()

    assert info["passwordSet"] is True
    assert PASSWORD not in str(info)
    assert "password" not in {key.lower() for key in info} - {"passwordset"}


def test_sender_falls_back_to_the_username(mail_app):
    mail_app.config["MAIL_DEFAULT_SENDER"] = ""
    with mail_app.app_context():
        assert email_service.describe_config()["sender"] == SENDER


# -------------------------------------------------------------- sending


def test_send_email_uses_starttls_and_authenticates(mail_app, stub):
    connection = stub["make"]()

    with mail_app.app_context():
        result = email_service.send_email("someone@example.com", "Subject", "Body")

    assert result["sent"] is True
    assert connection.started_tls is True
    assert connection.logins == [SENDER]
    assert connection.quit_called is True
    assert len(connection.messages) == 1


def test_sent_message_has_the_right_headers(mail_app, stub):
    connection = stub["make"]()

    with mail_app.app_context():
        email_service.send_email("someone@example.com", "Hello", "Body text")

    message = connection.messages[0]
    assert message["To"] == "someone@example.com"
    assert SENDER in message["From"]
    assert message["Subject"] == "Hello"


def test_an_invalid_address_is_rejected_before_connecting(mail_app, stub):
    stub["make"]()

    with mail_app.app_context():
        with pytest.raises(email_service.EmailError) as exc:
            email_service.send_email("not-an-email", "Subject", "Body")

    assert exc.value.reason == "recipient"


def test_authentication_failure_raises_without_leaking_the_password(mail_app, stub):
    stub["make"](fail_on="login")

    with mail_app.app_context():
        with pytest.raises(email_service.EmailError) as exc:
            email_service.send_email("someone@example.com", "Subject", "Body")

    assert exc.value.reason == "auth"
    assert PASSWORD not in str(exc.value)
    assert PASSWORD not in exc.value.message


def test_a_refused_recipient_is_reported_as_a_failure(mail_app, stub):
    stub["make"](refused={"someone@example.com": (550, b"No such user")})

    with mail_app.app_context():
        with pytest.raises(email_service.EmailError) as exc:
            email_service.send_email("someone@example.com", "Subject", "Body")

    assert exc.value.reason == "recipient"


def test_a_connection_timeout_is_reported_as_a_failure(mail_app, monkeypatch):
    def timeout(*args, **kwargs):
        raise socket.timeout("timed out")

    monkeypatch.setattr(smtplib, "SMTP", timeout)

    with mail_app.app_context():
        with pytest.raises(email_service.EmailError) as exc:
            email_service.send_email("someone@example.com", "Subject", "Body")

    assert exc.value.reason == "timeout"


def test_an_unreachable_server_is_reported_as_a_failure(mail_app, monkeypatch):
    def refuse(*args, **kwargs):
        raise OSError("connection refused")

    monkeypatch.setattr(smtplib, "SMTP", refuse)

    with mail_app.app_context():
        with pytest.raises(email_service.EmailError) as exc:
            email_service.send_email("someone@example.com", "Subject", "Body")

    assert exc.value.reason == "connect"


def test_suppress_send_runs_the_path_without_a_socket(mail_app):
    mail_app.config["MAIL_SUPPRESS_SEND"] = True

    with mail_app.app_context():
        result = email_service.send_email("someone@example.com", "Subject", "Body")

    assert result == {"sent": True, "suppressed": True, "recipient": "someone@example.com"}


def test_sending_while_disabled_raises_rather_than_silently_succeeding(app):
    with app.app_context():
        with pytest.raises(email_service.EmailError) as exc:
            email_service.send_email("someone@example.com", "Subject", "Body")

    assert exc.value.reason == "config"


# ------------------------------------------------------------- templates


def test_the_otp_email_carries_the_code_in_both_parts(mail_app, stub):
    connection = stub["make"]()

    with mail_app.app_context():
        email_service.send_otp_email("someone@example.com", "483920", "verify_email", 300)

    message = connection.messages[0]
    assert "483920" in message["Subject"]

    bodies = [
        part.get_payload(decode=True).decode()
        for part in message.walk()
        if part.get_content_type() in ("text/plain", "text/html")
    ]
    assert len(bodies) == 2
    assert all("483920" in body for body in bodies)


def test_the_notification_email_carries_the_complaint_reference(mail_app, stub):
    connection = stub["make"]()

    with mail_app.app_context():
        email_service.send_notification_email(
            "someone@example.com", "Status updated", "Now In Progress.", "CMP-2026-001"
        )

    message = connection.messages[0]
    assert "CMP-2026-001" in message["Subject"]


# ------------------------------------------------- OTP delivery guarantees


def test_send_otp_reports_delivered_when_smtp_accepts_it(mail_app, stub):
    connection = stub["make"]()

    with mail_app.app_context():
        result = otp_service.send_otp("delivery.ok@example.com", otp_service.PURPOSE_VERIFY)

    assert result["delivered"] is True
    # Once the code is really emailed it must not also travel in the response.
    assert "otp" not in result
    assert len(connection.messages) == 1


def test_send_otp_raises_when_delivery_fails_instead_of_reporting_success(mail_app, stub):
    """The original bug: the API answered 200 "Verification code sent." while
    nothing had been sent."""
    stub["make"](fail_on="login")

    with mail_app.app_context():
        with pytest.raises(ApiException) as exc:
            otp_service.send_otp("delivery.fails@example.com", otp_service.PURPOSE_VERIFY)

    assert exc.value.status >= 500
    assert exc.value.message == "Unable to send OTP email. Please try again later."
    assert PASSWORD not in str(exc.value.error)


def test_a_failed_send_leaves_no_otp_record_behind(mail_app, stub):
    stub["make"](fail_on="login")
    email = "no.record@example.com"

    with mail_app.app_context():
        from database import otps

        with pytest.raises(ApiException):
            otp_service.send_otp(email, otp_service.PURPOSE_VERIFY)

        assert otps().find_one({"email": email, "purpose": otp_service.PURPOSE_VERIFY}) is None


def test_send_otp_raises_when_smtp_is_unconfigured_and_dev_mode_is_off(app):
    app.config["OTP_DEV_MODE"] = False
    try:
        with app.app_context():
            with pytest.raises(ApiException) as exc:
                otp_service.send_otp("no.smtp@example.com", otp_service.PURPOSE_VERIFY)

        assert exc.value.status == 503
        assert exc.value.message == "Unable to send OTP email. Please try again later."
    finally:
        app.config["OTP_DEV_MODE"] = True


def test_dev_mode_still_returns_the_code_when_smtp_is_unconfigured(client):
    """The existing development flow must keep working untouched."""
    response = client.post(
        "/api/auth/send-otp", json={"email": "dev.mode@example.com", "purpose": "verify_email"}
    )

    body = response.get_json()
    assert response.status_code == 200
    assert body["data"]["delivered"] is False
    assert len(body["data"]["otp"]) == 6


# ---------------------------------------------------------------- routes


def test_the_api_reports_failure_when_the_otp_email_cannot_be_sent(mail_app, stub, client):
    stub["make"](fail_on="login")

    response = client.post(
        "/api/auth/send-otp", json={"email": "route.fail@example.com", "purpose": "verify_email"}
    )
    body = response.get_json()

    assert response.status_code >= 500
    assert body["success"] is False
    assert body["message"] == "Unable to send OTP email. Please try again later."

    serialized = str(body)
    assert PASSWORD not in serialized
    assert SENDER not in serialized
    assert "smtp.example.com" not in serialized


def test_the_api_confirms_the_email_when_it_really_was_sent(mail_app, stub, client):
    stub["make"]()

    response = client.post(
        "/api/auth/send-otp", json={"email": "route.ok@example.com", "purpose": "verify_email"}
    )
    body = response.get_json()

    assert response.status_code == 200
    assert body["data"]["delivered"] is True
    assert "otp" not in body["data"]
    assert "email" in body["message"].lower()


def test_forgot_password_hides_smtp_failure_so_it_stays_oracle_free(mail_app, stub, client):
    """A delivery failure must not reveal that an address is registered."""
    stub["make"](fail_on="login")

    known = client.post("/api/auth/forgot-password", json={"email": "student@dsvv.ac.in"})
    unknown = client.post("/api/auth/forgot-password", json={"email": "nobody@example.com"})

    assert known.status_code == unknown.status_code == 200
    assert known.get_json()["message"] == unknown.get_json()["message"]


def test_health_reports_email_status_without_any_secret(mail_app, client):
    body = client.get("/api/health").get_json()

    assert body["data"]["email"] is True
    assert PASSWORD not in str(body)


# --------------------------------------------------------- notifications


def test_a_notification_email_failure_never_breaks_the_notification(mail_app, stub):
    """The in-app feed is the source of truth; mail is best-effort."""
    stub["make"](fail_on="login")
    mail_app.config["MAIL_NOTIFICATIONS_ENABLED"] = True

    try:
        with mail_app.app_context():
            from services import auth_service, notification_service

            user = auth_service.find_by_email("student@dsvv.ac.in")
            result = notification_service.create(
                user["id"], "status_changed", "Status updated", "Now In Progress.", "CMP-1"
            )

        assert result is not None and result["id"]
    finally:
        mail_app.config["MAIL_NOTIFICATIONS_ENABLED"] = False


def test_notifications_are_not_emailed_unless_explicitly_enabled(mail_app, stub):
    connection = stub["make"]()

    with mail_app.app_context():
        from services import auth_service, notification_service

        user = auth_service.find_by_email("student@dsvv.ac.in")
        notification_service.create(user["id"], "status_changed", "Title", "Message", "CMP-1")

    assert connection.messages == []
