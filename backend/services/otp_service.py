"""
OTP generation and verification.

Codes are hashed before storage (an OTP is a short-lived password), expire via
a MongoDB TTL index, and are limited by attempt count and resend cooldown.

DEVELOPMENT MODE: when `OTP_DEV_MODE` is true the code is returned in the API
response so the flow can be exercised without a mail or SMS provider. That is
also the only situation in which a code ever leaves the server. Wiring a real
provider means implementing `_send()` and setting OTP_DEV_MODE=false.
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


def _hash_code(code: str, email: str) -> str:
    """Hash the code with the JWT secret as key, bound to the email so a code
    issued for one address cannot be replayed against another."""
    secret = (_config("JWT_SECRET_KEY") or "").encode("utf-8")
    return hmac.new(secret, f"{email}:{code}".encode("utf-8"), hashlib.sha256).hexdigest()


def _generate_code(length: int) -> str:
    """Cryptographically secure numeric code (never `random`)."""
    return "".join(secrets.choice("0123456789") for _ in range(length))


def _send(email: str, code: str, purpose: str) -> bool:
    """Delivery hook for a future email/SMS provider.

    Intentionally not implemented: no provider is configured, and the code must
    not be printed anywhere it could be harvested. In dev mode the route returns
    the code directly instead.
    """
    logger.info("OTP for %s (%s) generated; delivery provider not configured.", email, purpose)
    return False


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

    delivered = _send(email, code, purpose)
    dev_mode = _config("OTP_DEV_MODE", True)

    result = {
        "email": email,
        "purpose": purpose,
        "expiresIn": expiry_seconds,
        "delivered": delivered,
        "devMode": bool(dev_mode),
    }

    if dev_mode:
        # Development convenience only - never reached when OTP_DEV_MODE=false.
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
