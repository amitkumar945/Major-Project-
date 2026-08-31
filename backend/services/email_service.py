"""
SMTP email delivery.

One place where mail leaves the system, so OTP codes and notifications share
the same connection handling, error translation and logging.

Configuration comes from the environment (see `Config` and `.env.example`);
nothing is hard-coded and the password is never logged, echoed or returned in
an API response. `describe_config()` exists for exactly that reason: it reports
whether a password is present without revealing any part of it.

Two transports are supported, matching what mail providers offer:

    STARTTLS   MAIL_PORT=587, MAIL_USE_TLS=true    (Gmail's recommended port)
    implicit   MAIL_PORT=465, MAIL_USE_SSL=true

GMAIL: a normal account password will NOT work. Google requires an App
Password (16 characters, generated at https://myaccount.google.com/apppasswords
with 2-Step Verification enabled) for SMTP logins.
"""

import logging
import re
import smtplib
import socket
import ssl
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid

from flask import current_app

from utils.validators import is_email

logger = logging.getLogger(__name__)

# Never let a hung SMTP server hold a request open indefinitely.
DEFAULT_TIMEOUT = 15


class EmailError(Exception):
    """Delivery failed.

    `message` is safe to show a user; `reason` is a short machine-readable tag
    (`auth`, `connect`, `tls`, `timeout`, `recipient`, `config`, `unknown`) used
    for logging and tests. Neither ever carries credentials.
    """

    def __init__(self, message: str, reason: str = "unknown"):
        super().__init__(message)
        self.message = message
        self.reason = reason


def _config(key, default=None):
    return current_app.config.get(key, default)


# ------------------------------------------------------------------- config


def _app_password(value) -> str:
    """Normalise an SMTP password.

    Gmail displays a generated App Password in four space-separated groups and
    expects it without the spaces; other providers never allow spaces in a
    password either, so removing all whitespace is safe and prevents a
    copy-paste 535.
    """
    return re.sub(r"\s+", "", value or "")


def _sender_address() -> str:
    """The envelope sender: MAIL_DEFAULT_SENDER, else the SMTP username."""
    return (_config("MAIL_DEFAULT_SENDER") or _config("MAIL_USERNAME") or "").strip()


# Values shipped in `.env.example` as fill-me-in markers. A copied `.env` that
# still holds one of these is not configured, however "set" it looks: Gmail
# answers it with SMTP 535, which reads like a wrong password rather than an
# unfinished setup. Detecting them here turns that into a precise message.
_PLACEHOLDER_VALUES = {
    "your_email@gmail.com",
    "your-email@gmail.com",
    "you@example.com",
    "your_app_password",
    "your-app-password",
}


def is_placeholder(value: str) -> bool:
    """True when a setting still holds an `.env.example` marker."""
    return (value or "").strip().lower() in _PLACEHOLDER_VALUES


def placeholder_keys() -> list:
    """MAIL_* keys still holding an `.env.example` placeholder."""
    return [
        key
        for key in ("MAIL_USERNAME", "MAIL_PASSWORD", "MAIL_DEFAULT_SENDER")
        if is_placeholder(_config(key))
    ]


def is_configured() -> bool:
    """True when enough settings are present to attempt a send.

    A server and a sender are the minimum; username/password are optional
    because local relays and some internal servers accept unauthenticated mail.
    Placeholder credentials count as unconfigured - they can only ever fail.
    """
    if not _config("MAIL_ENABLED", False):
        return False
    if placeholder_keys():
        return False
    return bool(_config("MAIL_SERVER") and _sender_address())


def describe_config() -> dict:
    """Safe configuration summary for logs and the health endpoint.

    Reports only whether a password exists - never its value, length or hash.
    """
    return {
        "enabled": bool(_config("MAIL_ENABLED", False)),
        "configured": is_configured(),
        "server": _config("MAIL_SERVER") or None,
        "port": _config("MAIL_PORT"),
        "useTls": bool(_config("MAIL_USE_TLS", True)),
        "useSsl": bool(_config("MAIL_USE_SSL", False)),
        "username": _config("MAIL_USERNAME") or None,
        "sender": _sender_address() or None,
        "passwordSet": bool(_app_password(_config("MAIL_PASSWORD"))),
        "placeholders": placeholder_keys(),
        "suppressed": bool(_config("MAIL_SUPPRESS_SEND", False)),
    }


def log_config(logger_=None) -> None:
    """Log the configuration at startup, without secrets."""
    log = logger_ or logger
    info = describe_config()

    if not info["enabled"]:
        log.info("SMTP disabled (MAIL_ENABLED=false); no email will be sent.")
        return

    if info["placeholders"]:
        log.warning(
            "SMTP enabled but %s still hold the .env.example placeholder value(s). "
            "Put a real address in MAIL_USERNAME and a 16-character Gmail App Password "
            "in MAIL_PASSWORD (backend/.env), or set MAIL_ENABLED=false. "
            "Until then every send fails with SMTP 535.",
            " and ".join(info["placeholders"]),
        )
        return

    if not info["configured"]:
        log.warning(
            "SMTP enabled but incomplete: MAIL_SERVER=%s sender=%s. "
            "Set MAIL_SERVER, MAIL_USERNAME/MAIL_DEFAULT_SENDER and MAIL_PASSWORD in backend/.env.",
            info["server"] or "(unset)", info["sender"] or "(unset)",
        )
        return

    # Deliberately reports only *whether* a username/password exists.
    log.info("SMTP configuration loaded")
    log.info("  SMTP server: %s", info["server"])
    log.info("  SMTP port: %s (tls=%s ssl=%s)", info["port"], info["useTls"], info["useSsl"])
    log.info("  SMTP username configured: %s", "YES" if info["username"] else "NO")
    log.info("  SMTP password configured: %s", "YES" if info["passwordSet"] else "NO")
    log.info("  Sender: %s", info["sender"])


# -------------------------------------------------------------- connection


def _connect():
    """Open an authenticated SMTP connection.

    Raises EmailError with a user-safe message for every failure mode. The
    caller always closes the connection with `_close()`.
    """
    server = (_config("MAIL_SERVER") or "").strip()
    port = int(_config("MAIL_PORT") or 587)
    use_ssl = bool(_config("MAIL_USE_SSL", False))
    use_tls = bool(_config("MAIL_USE_TLS", True))
    username = (_config("MAIL_USERNAME") or "").strip()
    # Google shows App Passwords as "abcd efgh ijkl mnop"; pasted verbatim the
    # spaces make Gmail answer 535, which reads like a wrong password. Strip them.
    password = _app_password(_config("MAIL_PASSWORD"))
    timeout = int(_config("MAIL_TIMEOUT") or DEFAULT_TIMEOUT)

    if not server:
        raise EmailError("Email service is not configured.", "config")

    logger.info("Connecting to SMTP server %s:%s ...", server, port)

    try:
        if use_ssl:
            context = ssl.create_default_context()
            connection = smtplib.SMTP_SSL(server, port, timeout=timeout, context=context)
        else:
            connection = smtplib.SMTP(server, port, timeout=timeout)
            connection.ehlo()
            if use_tls:
                # STARTTLS upgrades the plaintext socket; without it the
                # password would cross the network in the clear.
                connection.starttls(context=ssl.create_default_context())
                connection.ehlo()
    except smtplib.SMTPNotSupportedError as exc:
        # Usually STARTTLS on a port that speaks implicit TLS (465) or vice versa.
        logger.error("SMTP TLS negotiation failed for %s:%s - %s", server, port, exc)
        raise EmailError(
            "Email service TLS configuration is incorrect. "
            "Check MAIL_PORT, MAIL_USE_TLS and MAIL_USE_SSL.",
            "tls",
        ) from exc
    except ssl.SSLError as exc:
        logger.error("SMTP SSL error for %s:%s - %s", server, port, exc)
        raise EmailError(
            "Could not establish a secure connection to the email server.", "tls"
        ) from exc
    except (socket.timeout, TimeoutError) as exc:
        logger.error("SMTP connection to %s:%s timed out after %ss.", server, port, timeout)
        raise EmailError("The email server did not respond in time.", "timeout") from exc
    except (smtplib.SMTPConnectError, socket.gaierror, OSError) as exc:
        logger.error("SMTP connection to %s:%s failed - %s", server, port, exc)
        raise EmailError("Could not connect to the email server.", "connect") from exc

    if username and password:
        try:
            connection.login(username, password)
            logger.info("SMTP authentication successful for %s.", username)
        except smtplib.SMTPAuthenticationError as exc:
            # Log the server's status code, never the credentials themselves.
            logger.error(
                "SMTP authentication failed for %s (code %s). For Gmail, use a 16-character "
                "App Password, not the account password.",
                username, getattr(exc, "smtp_code", "?"),
            )
            _close(connection)
            raise EmailError("Email service authentication failed.", "auth") from exc
        except smtplib.SMTPException as exc:
            logger.error("SMTP login error for %s - %s", username, type(exc).__name__)
            _close(connection)
            raise EmailError("Email service rejected the login.", "auth") from exc

    return connection


def _close(connection) -> None:
    """Close a connection without letting teardown mask a real error."""
    try:
        connection.quit()
    except Exception:
        try:
            connection.close()
        except Exception:
            pass


# -------------------------------------------------------------------- send


def _build_message(to: str, subject: str, body: str, html: str = "", sender: str = "") -> EmailMessage:
    """Assemble a plain-text message, adding an HTML alternative when given."""
    from_address = sender or _sender_address()
    display_name = _config("MAIL_SENDER_NAME") or ""

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = formataddr((display_name, from_address)) if display_name else from_address
    message["To"] = to
    message["Date"] = formatdate(localtime=True)
    # A well-formed Message-ID keeps spam filters happier.
    domain = from_address.split("@")[-1] if "@" in from_address else ""
    message["Message-ID"] = make_msgid(domain=domain) if domain else make_msgid()

    message.set_content(body)
    if html:
        message.add_alternative(html, subtype="html")
    return message


def send_email(to: str, subject: str, body: str, html: str = "") -> dict:
    """Send one email.

    Returns `{"sent": True, ...}` on success and raises `EmailError` on every
    failure, so a caller can never mistake a failed send for a delivered one.
    """
    to = (to or "").strip()

    if not is_email(to):
        raise EmailError("The email address is not valid.", "recipient")

    if not _config("MAIL_ENABLED", False):
        raise EmailError("Email service is disabled.", "config")

    if not is_configured():
        # Names the missing keys for the operator; the client only sees the
        # generic message the route substitutes.
        placeholders = placeholder_keys()
        if placeholders:
            logger.error(
                "Email service is not configured: %s still hold the .env.example "
                "placeholder value(s) in backend/.env. Gmail rejects these with SMTP 535.",
                ", ".join(placeholders),
            )
            raise EmailError("Email service is not configured.", "config")

        missing = [
            key for key in ("MAIL_SERVER", "MAIL_USERNAME", "MAIL_PASSWORD")
            if not _config(key)
        ]
        logger.error(
            "Email service is not configured. Missing or blank in backend/.env: %s",
            ", ".join(missing) or "MAIL_DEFAULT_SENDER",
        )
        raise EmailError("Email service is not configured.", "config")

    if _config("MAIL_SUPPRESS_SEND", False):
        # Testing switch: exercise the whole path without touching a network.
        logger.info("MAIL_SUPPRESS_SEND is on: pretending to send '%s' to %s.", subject, to)
        return {"sent": True, "suppressed": True, "recipient": to}

    message = _build_message(to, subject, body, html)
    connection = _connect()

    try:
        refused = connection.send_message(message)
        if refused:
            # Every recipient rejected - send_message reports them here.
            logger.error("SMTP server refused the recipient %s.", to)
            raise EmailError("The email address was rejected by the mail server.", "recipient")
    except EmailError:
        raise
    except smtplib.SMTPRecipientsRefused as exc:
        logger.error("SMTP recipients refused for %s.", to)
        raise EmailError("The email address was rejected by the mail server.", "recipient") from exc
    except smtplib.SMTPSenderRefused as exc:
        logger.error("SMTP sender refused by the server.")
        raise EmailError("The sender address was rejected by the mail server.", "config") from exc
    except (socket.timeout, TimeoutError) as exc:
        logger.error("SMTP send to %s timed out.", to)
        raise EmailError("The email server did not respond in time.", "timeout") from exc
    except smtplib.SMTPException as exc:
        logger.error("SMTP send failed for %s - %s", to, type(exc).__name__)
        raise EmailError("The email could not be sent.", "unknown") from exc
    except OSError as exc:
        logger.error("Network error while sending to %s - %s", to, type(exc).__name__)
        raise EmailError("Could not reach the email server.", "connect") from exc
    finally:
        _close(connection)

    logger.info("Email '%s' sent successfully to %s.", subject, to)
    return {"sent": True, "suppressed": False, "recipient": to}


def verify_connection() -> dict:
    """Open and close a connection without sending, to check the settings.

    Used by the admin SMTP-test endpoint so an operator can validate `.env`
    without emailing anybody.
    """
    if not is_configured():
        raise EmailError("Email service is not configured.", "config")

    connection = _connect()
    _close(connection)
    logger.info("SMTP connection verified successfully.")
    return {"verified": True, "server": _config("MAIL_SERVER"), "port": _config("MAIL_PORT")}


# ------------------------------------------------------------- templates
# Message bodies live here so routes and services never hand-write mail text.


def _brand() -> str:
    return _config("MAIL_SENDER_NAME") or "Grievance Management System"


def send_otp_email(to: str, code: str, purpose: str = "verify_email", expires_in: int = 300) -> dict:
    """Send a one-time verification code.

    The code appears only in the message body - never in a log line.
    """
    minutes = max(1, round((expires_in or 300) / 60))
    brand = _brand()

    reasons = {
        "register": "complete your registration",
        "login": "sign in to your account",
        "password_reset": "reset your password",
        "verify_email": "verify your email address",
    }
    reason = reasons.get(purpose, "verify your email address")

    subject = f"{code} is your {brand} verification code"

    body = (
        f"Use this code to {reason}:\n\n"
        f"    {code}\n\n"
        f"The code expires in {minutes} minute(s). Do not share it with anyone.\n\n"
        f"If you did not request this code, you can safely ignore this email.\n\n"
        f"-- {brand}"
    )

    html = f"""\
<html>
  <body style="margin:0;padding:24px;background:#f4f6f8;
               font-family:Segoe UI,Roboto,Helvetica,Arial,sans-serif;color:#1f2933">
    <div style="max-width:520px;margin:0 auto;background:#ffffff;border-radius:12px;
                padding:32px;border:1px solid #e4e7eb">
      <h1 style="margin:0 0 8px;font-size:20px;color:#1f2933">{brand}</h1>
      <p style="margin:0 0 24px;font-size:15px;color:#52606d">
        Use this code to {reason}.
      </p>
      <div style="font-size:32px;font-weight:700;letter-spacing:8px;text-align:center;
                  padding:18px;background:#f4f6f8;border-radius:10px;color:#1f2933">
        {code}
      </div>
      <p style="margin:24px 0 0;font-size:14px;color:#52606d">
        The code expires in <strong>{minutes} minute(s)</strong>. Do not share it with anyone.
      </p>
      <p style="margin:16px 0 0;font-size:13px;color:#7b8794">
        If you did not request this code, you can safely ignore this email.
      </p>
    </div>
  </body>
</html>"""

    # Deliberately logs the purpose and recipient only - never the code.
    logger.info("Sending OTP email to %s (%s).", to, purpose)
    return send_email(to, subject, body, html)


def send_notification_email(to: str, title: str, message: str, complaint_id: str = "") -> dict:
    """Send a grievance notification (status change, assignment, escalation)."""
    brand = _brand()
    subject = f"{title} - {complaint_id}" if complaint_id else f"{title} - {brand}"

    reference = f"\n\nReference: {complaint_id}" if complaint_id else ""
    body = f"{title}\n\n{message}{reference}\n\n-- {brand}"

    reference_html = (
        f'<p style="margin:16px 0 0;font-size:13px;color:#7b8794">Reference: '
        f"<strong>{complaint_id}</strong></p>"
        if complaint_id
        else ""
    )

    html = f"""\
<html>
  <body style="margin:0;padding:24px;background:#f4f6f8;
               font-family:Segoe UI,Roboto,Helvetica,Arial,sans-serif;color:#1f2933">
    <div style="max-width:520px;margin:0 auto;background:#ffffff;border-radius:12px;
                padding:32px;border:1px solid #e4e7eb">
      <h1 style="margin:0 0 8px;font-size:18px;color:#1f2933">{title}</h1>
      <p style="margin:0;font-size:15px;color:#52606d;line-height:1.6">{message}</p>
      {reference_html}
      <p style="margin:24px 0 0;font-size:13px;color:#7b8794">-- {brand}</p>
    </div>
  </body>
</html>"""

    return send_email(to, subject, body, html)
