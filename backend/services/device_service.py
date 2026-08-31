"""
Push-notification device registry for the mobile app.

One row per device token. A token belongs to whichever account most recently
registered it, which matters on a shared handset: signing in as a second user
must move the token rather than deliver the first user's grievance updates to
the new one.

Nothing here sends anything. `push_service` reads this registry and does the
delivery, so the in-app notification feed stays the source of truth and remains
completely unaffected when push is not configured.
"""

import logging

from database import devices
from utils.helpers import clean_document, iso, utcnow
from utils.responses import ApiException

logger = logging.getLogger(__name__)

PLATFORMS = ("android", "ios", "web")

# FCM tokens are ~160 chars; allow room without accepting unbounded input.
MAX_TOKEN_LENGTH = 512


def _clean_token(token) -> str:
    if not isinstance(token, str):
        raise ApiException("A device token is required.", 400)
    token = token.strip()
    if not token:
        raise ApiException("A device token is required.", 400)
    if len(token) > MAX_TOKEN_LENGTH:
        raise ApiException("That device token is not valid.", 400)
    return token


def register(user: dict, token: str, platform: str = "", device_name: str = "") -> dict:
    """Register (or re-register) one device for the signed-in user.

    Idempotent: registering the same token twice updates the existing row
    instead of creating a duplicate, so an app that re-registers on every
    launch - which is what FCM advises - does not grow the collection.
    """
    token = _clean_token(token)
    platform = (platform or "").strip().lower()
    if platform and platform not in PLATFORMS:
        raise ApiException(
            "Unknown platform '%s'. Expected one of: %s." % (platform, ", ".join(PLATFORMS)),
            400,
        )

    now = iso(utcnow())
    existing = devices().find_one({"token": token}, {"_id": 0, "userId": 1, "createdAt": 1})

    devices().update_one(
        {"token": token},
        {
            "$set": {
                # Re-assigns the token when a different account registers it,
                # so a shared phone never leaks the previous user's alerts.
                "userId": user["id"],
                "platform": platform or "unknown",
                "deviceName": (device_name or "")[:120],
                "updatedAt": now,
            },
            "$setOnInsert": {"token": token, "createdAt": now},
        },
        upsert=True,
    )

    if existing and existing.get("userId") != user["id"]:
        logger.info("Device token reassigned from %s to %s.", existing.get("userId"), user["id"])

    record = devices().find_one({"token": token}, {"_id": 0})
    return _safe(record)


def unregister(user: dict, token: str) -> bool:
    """Remove one device. Scoped to the owner, so a caller cannot delete
    somebody else's registration by guessing a token."""
    token = _clean_token(token)
    result = devices().delete_one({"token": token, "userId": user["id"]})
    return result.deleted_count > 0


def list_for_user(user_id: str) -> list:
    """Every device registered to one user, tokens masked."""
    return [_safe(d) for d in devices().find({"userId": user_id}, {"_id": 0}).sort("updatedAt", -1)]


def tokens_for_user(user_id: str) -> list:
    """Raw tokens, for the push sender only - never returned by an API."""
    return [d["token"] for d in devices().find({"userId": user_id}, {"_id": 0, "token": 1})]


def remove_tokens(tokens) -> int:
    """Drop tokens the push provider reported as permanently invalid."""
    if not tokens:
        return 0
    return devices().delete_many({"token": {"$in": list(tokens)}}).deleted_count


def _safe(record: dict) -> dict:
    """A device as the API may show it: the token is masked.

    Returning the full token would let anyone who reads one response impersonate
    that device to the push provider, so only enough to recognise it is kept.
    """
    if not record:
        return {}
    token = record.get("token", "")
    masked = ("…" + token[-6:]) if len(token) > 6 else "…"
    return clean_document({**record, "token": masked})
