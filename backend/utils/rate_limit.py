"""Rate limiting for sensitive endpoints, with shared chatbot quotas."""

import hashlib
import logging
import threading
import time
from datetime import datetime, timezone
from functools import wraps

from flask import current_app, has_app_context, request
from pymongo import ReturnDocument

from utils.responses import error

# (bucket, client) -> [window_start, count]
_HITS = {}
_LOCK = threading.Lock()
logger = logging.getLogger(__name__)
# Drop expired entries once the table grows past this, so a long-running
# process cannot accumulate unbounded keys.
_CLEANUP_THRESHOLD = 1000


def _client_key() -> str:
    # ProxyFix, when explicitly enabled, has already selected a trusted hop.
    # Never consume X-Forwarded-For directly from an arbitrary client.
    return request.remote_addr or "unknown"


def _cleanup(now: float, window: int) -> None:
    expired = [key for key, value in _HITS.items() if now - value[0] > window * 2]
    for key in expired:
        _HITS.pop(key, None)


def check(bucket: str, limit: int, window: int, client_key: str = None) -> tuple:
    """Register a hit. Returns (allowed, seconds_until_reset)."""
    now = time.time()
    window = max(1, int(window))
    client = client_key or _client_key()

    # Mongo's atomic upsert is shared by all application workers. Hash the
    # client key so IP/mobile-derived identifiers are not stored in cleartext.
    shared_enabled = (
        has_app_context()
        and current_app.config.get("CHATBOT_SHARED_RATE_LIMIT", True)
        and bucket.startswith("chatbot")
    )
    if shared_enabled:
        window_start = int(now // window) * window
        window_end = window_start + window
        digest = hashlib.sha256(f"{bucket}:{client}".encode("utf-8")).hexdigest()
        document_id = f"{bucket}:{digest}:{window_start}"
        try:
            from database import rate_limit_windows

            record = rate_limit_windows().find_one_and_update(
                {"_id": document_id},
                {
                    "$inc": {"count": 1},
                    "$setOnInsert": {
                        "expiresAt": datetime.fromtimestamp(
                            window_end + 5, tz=timezone.utc
                        )
                    },
                },
                upsert=True,
                return_document=ReturnDocument.AFTER,
                projection={"count": 1},
            )
            count = int((record or {}).get("count", 0))
            if count > limit:
                return False, max(1, int(window_end - now) + 1)
            return True, 0
        except Exception as exc:
            # Keep the endpoint available if the shared counter store has a
            # transient failure; local limiting still provides a soft guard.
            logger.warning("Shared chatbot rate limit unavailable (%s)", type(exc).__name__)

    key = (bucket, client)

    with _LOCK:
        if len(_HITS) > _CLEANUP_THRESHOLD:
            _cleanup(now, window)

        start, count = _HITS.get(key, (now, 0))
        if now - start >= window:  # window expired, start a new one
            start, count = now, 0

        count += 1
        _HITS[key] = (start, count)

        if count > limit:
            return False, int(window - (now - start)) + 1
        return True, 0


def rate_limit(bucket: str = "default", limit: int = None, window: int = None):
    """Throttle a route.

    `bucket` selects the configured limit: "auth" or "otp"; anything else uses
    the auth limit unless an explicit `limit` is given.
    """

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not current_app.config.get("RATE_LIMIT_ENABLED", True):
                return fn(*args, **kwargs)

            if window is not None:
                effective_window = window
            elif bucket == "chatbot":
                effective_window = current_app.config.get("CHATBOT_RATE_WINDOW", 60)
            else:
                effective_window = current_app.config.get("RATE_LIMIT_WINDOW", 60)
            if limit is not None:
                effective_limit = limit
            elif bucket == "otp":
                effective_limit = current_app.config.get("RATE_LIMIT_OTP", 5)
            elif bucket == "chatbot":
                effective_limit = current_app.config.get("RATE_LIMIT_CHATBOT", 30)
            else:
                effective_limit = current_app.config.get("RATE_LIMIT_AUTH", 10)

            allowed, retry_after = check(bucket, effective_limit, effective_window)
            if not allowed:
                response, status = error(
                    f"Too many requests. Please try again in {retry_after} second(s).",
                    429,
                    {"retryAfter": retry_after},
                )
                response.headers["Retry-After"] = str(retry_after)
                return response, status

            return fn(*args, **kwargs)

        return wrapper

    return decorator


def reset() -> None:
    """Clear every counter - used by the test-suite."""
    with _LOCK:
        _HITS.clear()
