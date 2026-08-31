"""
Push delivery to registered mobile devices.

Mirrors how `email_service` is used by the notification hook: best-effort, and
never able to break the action that produced the notification. The in-app feed
is stored first and remains the source of truth, so a failed or unconfigured
push changes nothing a user can see in the app's notification list.

CONFIGURATION (all from the environment - no credential is ever hardcoded):

    PUSH_ENABLED=false                     master switch, off by default
    FCM_PROJECT_ID=<firebase project id>
    FCM_CREDENTIALS_FILE=<abs path to the service-account JSON>

The service-account JSON must live OUTSIDE the repository and must not be
committed. When `PUSH_ENABLED` is false, or the credentials are absent, this
module reports "not configured" and does nothing - which is exactly the
behaviour before push existed.

Sending requires the `firebase-admin` package. It is deliberately NOT a hard
dependency: if it is not installed the backend still runs and every other
feature is unaffected.
"""

import logging

from flask import current_app, has_app_context

logger = logging.getLogger(__name__)


def _config(key, default=None):
    if not has_app_context():
        return default
    return current_app.config.get(key, default)


def is_configured() -> bool:
    """Whether a push could actually be delivered. Never raises."""
    if not _config("PUSH_ENABLED", False):
        return False
    if not (_config("FCM_CREDENTIALS_FILE", "") and _config("FCM_PROJECT_ID", "")):
        return False
    try:
        import firebase_admin  # noqa: F401
    except ImportError:
        return False
    return True


def describe_config() -> dict:
    """Non-secret view of the push setup, for the admin settings screen.

    Never includes the credentials path contents or any key material.
    """
    try:
        import firebase_admin  # noqa: F401
        sdk = True
    except ImportError:
        sdk = False

    return {
        "enabled": bool(_config("PUSH_ENABLED", False)),
        "projectConfigured": bool(_config("FCM_PROJECT_ID", "")),
        "credentialsConfigured": bool(_config("FCM_CREDENTIALS_FILE", "")),
        "sdkInstalled": sdk,
        "configured": is_configured(),
    }


_app_handle = None


def _firebase_app():
    """Initialise the Firebase app once per process."""
    global _app_handle
    if _app_handle is not None:
        return _app_handle

    import firebase_admin
    from firebase_admin import credentials

    cred = credentials.Certificate(_config("FCM_CREDENTIALS_FILE"))
    try:
        _app_handle = firebase_admin.initialize_app(
            cred, {"projectId": _config("FCM_PROJECT_ID")}, name="gms-push"
        )
    except ValueError:
        # Already initialised in this process.
        _app_handle = firebase_admin.get_app(name="gms-push")
    return _app_handle


def send_to_user(user_id: str, title: str, body: str, data: dict = None) -> dict:
    """Push one notification to every device a user has registered.

    Returns a small summary. Never raises: a push problem must not roll back
    the complaint update that triggered the notification.
    """
    result = {"attempted": 0, "sent": 0, "failed": 0, "skipped": True}

    if not is_configured():
        return result

    from services import device_service

    tokens = device_service.tokens_for_user(user_id)
    if not tokens:
        return result

    result["skipped"] = False
    result["attempted"] = len(tokens)

    try:
        from firebase_admin import messaging

        app_handle = _firebase_app()
        message = messaging.MulticastMessage(
            notification=messaging.Notification(title=title, body=body),
            # Data values must be strings for FCM.
            data={k: str(v) for k, v in (data or {}).items() if v is not None},
            tokens=tokens,
        )
        response = messaging.send_each_for_multicast(message, app=app_handle)
        result["sent"] = response.success_count
        result["failed"] = response.failure_count

        # Drop tokens the provider says are dead, so the registry does not rot.
        stale = []
        for token, single in zip(tokens, response.responses):
            if single.success:
                continue
            name = type(single.exception).__name__ if single.exception else ""
            if name in ("UnregisteredError", "SenderIdMismatchError", "InvalidArgumentError"):
                stale.append(token)
        if stale:
            removed = device_service.remove_tokens(stale)
            logger.info("Removed %d stale push token(s).", removed)

    except Exception as exc:
        # Best-effort by design - log and carry on.
        logger.error("Push delivery to %s failed: %s", user_id, exc)
        result["failed"] = result["attempted"]

    return result
