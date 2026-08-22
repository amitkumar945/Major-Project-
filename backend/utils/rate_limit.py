"""
In-process rate limiting for the sensitive endpoints (login, register, OTP).

A fixed-window counter kept in memory: no Redis, no extra dependency, which
suits a single-process campus deployment. Behind multiple workers each process
would keep its own window - swap `_HITS` for Redis if that ever matters.
"""

import threading
import time
from functools import wraps

from flask import current_app, request

from utils.responses import error

# (bucket, client) -> [window_start, count]
_HITS = {}
_LOCK = threading.Lock()
# Drop expired entries once the table grows past this, so a long-running
# process cannot accumulate unbounded keys.
_CLEANUP_THRESHOLD = 1000


def _client_key() -> str:
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "unknown"


def _cleanup(now: float, window: int) -> None:
    expired = [key for key, value in _HITS.items() if now - value[0] > window * 2]
    for key in expired:
        _HITS.pop(key, None)


def check(bucket: str, limit: int, window: int) -> tuple:
    """Register a hit. Returns (allowed, seconds_until_reset)."""
    key = (bucket, _client_key())
    now = time.time()

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

            effective_window = window or current_app.config.get("RATE_LIMIT_WINDOW", 60)
            if limit is not None:
                effective_limit = limit
            elif bucket == "otp":
                effective_limit = current_app.config.get("RATE_LIMIT_OTP", 5)
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
