"""
Refresh tokens for long-lived mobile sessions.

The website is unaffected by this module. It signs in, gets the same access
token it always did, and never asks for a refresh token. Only a client that
opts in - the Flutter app, by sending `"client": "mobile"` to /api/auth/login -
receives one.

Design notes:

* A refresh token is an opaque 256-bit random string, not a JWT. Nothing about
  the session is encoded in it, so it cannot be read or forged offline; it is
  only a lookup key for a server-side row that can be revoked at any moment.
  Access tokens stay stateless JWTs, so the hot path adds no database read.
* Only the SHA-256 hash is stored. A leaked database dump therefore does not
  hand over usable sessions. SHA-256 rather than bcrypt is right here: the
  token already carries full entropy, so there is nothing to brute force, and
  refresh happens often enough that a deliberately slow hash would hurt.
* Every refresh ROTATES the token: the old one is consumed and a new one
  issued. If a consumed token is presented again, that is either a stolen
  token or a broken client, and every session for that user is revoked. This
  is the standard reuse-detection response and it turns silent theft into a
  forced re-login the user can notice.
"""

import hashlib
import logging
import secrets
from datetime import timedelta

from flask import current_app

from database import refresh_tokens
from utils.helpers import iso, utcnow
from utils.responses import ApiException

logger = logging.getLogger(__name__)

# 32 bytes -> 43 url-safe characters. Well beyond guessing range.
TOKEN_BYTES = 32


def _config(key, default=None):
    return current_app.config.get(key, default)


def _hash(token: str) -> str:
    """Refresh tokens are stored hashed, never in the clear."""
    return hashlib.sha256((token or "").encode("utf-8")).hexdigest()


def issue(user: dict, device: str = "", user_agent: str = "") -> dict:
    """Create and store a refresh token. Returns the plaintext ONCE."""
    token = secrets.token_urlsafe(TOKEN_BYTES)
    now = utcnow()
    expires_at = now + timedelta(days=_config("REFRESH_TOKEN_DAYS", 30))

    refresh_tokens().insert_one(
        {
            "tokenHash": _hash(token),
            "userId": user["id"],
            "role": user.get("role", ""),
            "device": (device or "")[:120],
            "userAgent": (user_agent or "")[:200],
            "createdAt": iso(now),
            # TTL index on this field: Mongo deletes the row when it expires,
            # so an abandoned session cleans itself up.
            "expiresAt": expires_at,
            "revokedAt": None,
            "usedAt": None,
        }
    )

    return {"refreshToken": token, "refreshExpiresIn": int((expires_at - now).total_seconds())}


def _revoke_all_for_user(user_id: str, reason: str) -> int:
    result = refresh_tokens().update_many(
        {"userId": user_id, "revokedAt": None},
        {"$set": {"revokedAt": iso(utcnow()), "revokedReason": reason}},
    )
    return result.modified_count


def redeem(token: str) -> dict:
    """Exchange a refresh token for the user it belongs to, rotating it.

    Raises ApiException(401) for anything not currently valid. On reuse of an
    already-consumed token every session for that user is revoked.
    """
    if not token or not isinstance(token, str):
        raise ApiException("A refresh token is required.", 401)

    record = refresh_tokens().find_one({"tokenHash": _hash(token)})
    if not record:
        raise ApiException("Invalid or expired refresh token. Please sign in again.", 401)

    # Reuse of a rotated token: treat as compromise, not as a retry.
    if record.get("usedAt"):
        count = _revoke_all_for_user(record["userId"], "refresh-token-reuse")
        logger.warning(
            "Refresh token reuse detected for %s; revoked %d session(s).",
            record["userId"], count,
        )
        raise ApiException(
            "This session is no longer valid. Please sign in again.", 401
        )

    if record.get("revokedAt"):
        raise ApiException("This session has been signed out. Please sign in again.", 401)

    expires_at = record.get("expiresAt")
    if expires_at is not None:
        # Stored as a datetime for the TTL index; compare defensively.
        expiry = expires_at if hasattr(expires_at, "tzinfo") else None
        if expiry is not None:
            now = utcnow()
            reference = expiry if expiry.tzinfo else expiry.replace(tzinfo=now.tzinfo)
            if now > reference:
                raise ApiException("Your session has expired. Please sign in again.", 401)

    # The account may have been deleted or deactivated since sign-in.
    from services import auth_service

    user = auth_service.find_by_id(record["userId"])
    if not user:
        raise ApiException("Your account no longer exists.", 401)
    if user.get("isActive") is False:
        raise ApiException("Your account has been deactivated. Contact the administrator.", 403)

    # Consume this token, then hand out a fresh one (rotation).
    refresh_tokens().update_one(
        {"_id": record["_id"]}, {"$set": {"usedAt": iso(utcnow())}}
    )
    rotated = issue(user, device=record.get("device", ""), user_agent=record.get("userAgent", ""))

    return {"user": user, **rotated}


def revoke(token: str) -> bool:
    """Revoke one refresh token. Returns False when it was not found."""
    if not token:
        return False
    result = refresh_tokens().update_one(
        {"tokenHash": _hash(token), "revokedAt": None},
        {"$set": {"revokedAt": iso(utcnow()), "revokedReason": "logout"}},
    )
    return result.modified_count > 0


def revoke_all(user_id: str, reason: str = "logout-all") -> int:
    """Revoke every active refresh token for a user."""
    return _revoke_all_for_user(user_id, reason)
