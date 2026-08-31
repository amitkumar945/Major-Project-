"""
OTP generation and verification.

Codes are hashed before storage (an OTP is a short-lived password), expire via
a MongoDB TTL index, and are limited by attempt count and resend cooldown.

DEVELOPMENT MODE: when dev mode is active the code is returned in the API
response so the flow can be exercised without a mail or SMS provider. That is
also the only situation in which a code ever leaves the server, and it is
gated by `config.is_otp_dev_mode`, which requires BOTH the OTP_DEV_MODE flag
and a non-production environment - a deployed server cannot leak codes by
misconfiguration alone. Wiring a real provider means setting MAIL_ENABLED=true
with real credentials; `_send()` is already implemented.

The code itself is never written to the logs in any mode.
"""

import hashlib
import hmac
import logging
import secrets

from flask import current_app

from database import otps
from utils.helpers import iso, utcnow
from utils.responses import ApiException
from datetime import timedelta

logger = logging.getLogger(__name__)

# What an OTP can authorise.
PURPOSE_REGISTER = "register"
PURPOSE_LOGIN = "login"
PURPOSE_RESET = "password_reset"
PURPOSE_VERIFY = "verify_email"

PURPOSES = (PURPOSE_REGISTER, PURPOSE_LOGIN, PURPOSE_RESET, PURPOSE_VERIFY)


def _config(key, default=None):
    return current_app.config.get(key, default)


def _dev_mode() -> bool:
    """Whether a code may travel back in the API response.

    Delegates to `config.is_otp_dev_mode`, which requires a non-production
    environment on top of the flag itself.
    """
    from config import is_otp_dev_mode

    return is_otp_dev_mode(current_app.config)


def _hash_code(code: str, email: str) -> str:
    """Hash the code with the JWT secret as key, bound to the email so a code
    issued for one address cannot be replayed against another."""
    secret = (_config("JWT_SECRET_KEY") or "").encode("utf-8")
    return hmac.new(secret, f"{email}:{code}".encode("utf-8"), hashlib.sha256).hexdigest()


def _generate_code(length: int) -> str:
    """Cryptographically secure numeric code (never `random`)."""
    return "".join(secrets.choice("0123456789") for _ in range(length))


def _send(email: str, code: str, purpose: str, expires_in: int = 300) -> bool:
    """Email the code, or say plainly that it was not sent.

    Returns True only when SMTP really accepted the message. When mail is not
    configured the caller falls back to dev mode; when mail IS configured but
    the send fails, this raises - answering 200 "Verification code sent." while
    nothing was sent is the one outcome that must never happen.
    """
    from services import email_service

    if not email_service.is_configured():
        logger.info("OTP for %s (%s) generated; no mail provider configured.", email, purpose)
        return False

    try:
        email_service.send_otp_email(email, code, purpose, expires_in)
        return True
    except email_service.EmailError as exc:
        # The exception carries SMTP detail, which can include the server
        # response - never the credentials, and never the code itself.
        logger.error("OTP email to %s failed (%s): %s", email, exc.reason, exc)
        # 503 when the server is misconfigured or unreachable, 502 when it
        # answered but refused - both are 5xx: the fault is ours, not the user's.
        status = 503 if exc.reason in ("config", "connect", "timeout") else 502
        raise ApiException("Unable to send OTP email. Please try again later.", status)


def send_otp(email: str, purpose: str = PURPOSE_VERIFY) -> dict:
    """Issue a code, replacing any outstanding one for this email+purpose."""
    if purpose not in PURPOSES:
        raise ApiException("Unknown OTP purpose.", 400)

    email = (email or "").strip().lower()
    now = utcnow()

    # Enforce the resend cooldown.
    existing = otps().find_one({"email": email, "purpose": purpose})
    if existing:
        last_sent = existing.get("sentAt")
        if last_sent:
            from utils.helpers import parse_iso

            elapsed = (now - parse_iso(last_sent)).total_seconds()
            cooldown = _config("OTP_RESEND_COOLDOWN", 30)
            if elapsed < cooldown:
                raise ApiException(
                    f"Please wait {int(cooldown - elapsed)} more second(s) before requesting another code.",
                    429,
                )

    code = _generate_code(_config("OTP_LENGTH", 6))
    expiry_seconds = _config("OTP_EXPIRY", 300)
    expires_at = now + timedelta(seconds=expiry_seconds)

    otps().replace_one(
        {"email": email, "purpose": purpose},
        {
            "email": email,
            "purpose": purpose,
            "codeHash": _hash_code(code, email),
            "attempts": 0,
            "verified": False,
            "sentAt": iso(now),
            # TTL index on this field deletes the document automatically.
            "expiresAt": expires_at,
        },
        upsert=True,
    )

    # NOT the raw flag: `is_otp_dev_mode` refuses to honour it in production,
    # so a stray OTP_DEV_MODE=true in a deployed .env cannot leak codes.
    dev_mode = _dev_mode()

    try:
        delivered = _send(email, code, purpose, expiry_seconds)
    except ApiException:
        # Delivery failed and there is no dev-mode fallback. Drop the record so
        # a code nobody can read is not left occupying the resend cooldown.
        otps().delete_one({"email": email, "purpose": purpose})
        raise

    if not delivered and not dev_mode:
        # Mail is unconfigured and dev mode is off: there is no way for the
        # user to ever learn this code, so fail loudly instead of pretending.
        otps().delete_one({"email": email, "purpose": purpose})
        raise ApiException("Unable to send OTP email. Please try again later.", 503)

    result = {
        "email": email,
        "purpose": purpose,
        "expiresIn": expiry_seconds,
        "delivered": delivered,
        "devMode": bool(dev_mode),
    }

    if dev_mode and not delivered:
        # Development convenience only. Once the code has really been emailed
        # it must not also travel back in the API response.
        result["otp"] = code
        result["notice"] = (
            "Development mode: the code is returned here because no email/SMS "
            "provider is configured. Set OTP_DEV_MODE=false in production."
        )
    return result


def verify_otp(email: str, code: str, purpose: str = PURPOSE_VERIFY, consume: bool = True) -> bool:
    """Check a code. Raises ApiException with the reason when it does not match."""
    email = (email or "").strip().lower()
    record = otps().find_one({"email": email, "purpose": purpose})

    if not record:
        raise ApiException("No verification code was requested for this address, or it has expired.", 400)

    from utils.helpers import parse_iso

    expires_at = record.get("expiresAt")
    if expires_at is not None:
        expiry = expires_at if hasattr(expires_at, "tzinfo") else parse_iso(expires_at)
        if expiry and utcnow() > (expiry if expiry.tzinfo else expiry.replace(tzinfo=utcnow().tzinfo)):
            otps().delete_one({"email": email, "purpose": purpose})
            raise ApiException("This verification code has expired. Please request a new one.", 400)

    max_attempts = _config("OTP_MAX_ATTEMPTS", 5)
    if record.get("attempts", 0) >= max_attempts:
        otps().delete_one({"email": email, "purpose": purpose})
        raise ApiException("Too many incorrect attempts. Please request a new code.", 429)

    # Constant-time comparison so a wrong code cannot be found by timing.
    if not hmac.compare_digest(record.get("codeHash", ""), _hash_code(str(code).strip(), email)):
        otps().update_one({"email": email, "purpose": purpose}, {"$inc": {"attempts": 1}})
        remaining = max_attempts - record.get("attempts", 0) - 1
        raise ApiException(
            f"Incorrect verification code. {max(remaining, 0)} attempt(s) remaining.", 400
        )

    if consume:
        # Mark verified rather than deleting: registration checks this flag
        # immediately afterwards.
        otps().update_one(
            {"email": email, "purpose": purpose},
            {"$set": {"verified": True, "verifiedAt": iso(utcnow())}},
        )
    return True


def is_verified(email: str, purpose: str) -> bool:
    """Was a code for this email+purpose verified and not yet used up?"""
    record = otps().find_one({"email": (email or "").strip().lower(), "purpose": purpose})
    return bool(record and record.get("verified"))


def clear(email: str, purpose: str = "") -> None:
    """Drop the OTP record once it has served its purpose."""
    query = {"email": (email or "").strip().lower()}
    if purpose:
        query["purpose"] = purpose
    otps().delete_many(query)
