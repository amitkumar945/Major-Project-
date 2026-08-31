"""
Mobile device registration for push notifications.

    POST   /api/devices/register    register (or refresh) this device's token
    DELETE /api/devices/register    remove a device by token
    GET    /api/devices             the caller's own devices, tokens masked

Every route requires a signed-in user and is scoped to that user, so one
account can never see or delete another's registrations.
"""

from flask import Blueprint, request

from services import device_service
from utils.jwt_utils import current_user, jwt_required
from utils.responses import success, validation_error

bp = Blueprint("devices", __name__, url_prefix="/api/devices")


def _token_from_request() -> str:
    """Accept the token from the JSON body or the query string.

    DELETE with a body is awkward in some HTTP clients, so `?token=` is
    allowed too. A push token is not a credential for this API - it only
    identifies a device, and the route is authenticated either way.
    """
    values = request.get_json(silent=True) or {}
    return str(
        values.get("token")
        or values.get("deviceToken")
        or values.get("fcmToken")
        or request.args.get("token")
        or ""
    ).strip()


@bp.post("/register")
@jwt_required
def register_device():
    """Register this device for push.

    Request:  {"token": "<fcm token>", "platform": "android|ios|web",
               "deviceName": "Pixel 8"}
    Auth:     Bearer access token (required)
    Response: {"success": true, "data": {device with a MASKED token}}
    Errors:   401 not signed in
              422 token missing
              400 token malformed or unknown platform
    """
    values = request.get_json(silent=True) or {}
    token = _token_from_request()

    if not token:
        return validation_error({"token": "A device token is required"})

    device = device_service.register(
        current_user(),
        token,
        platform=values.get("platform", ""),
        device_name=values.get("deviceName") or values.get("device_name") or "",
    )
    return success(device, "Device registered for notifications.", 201)


@bp.delete("/register")
@jwt_required
def unregister_device():
    """Remove this device so it stops receiving push.

    Request:  {"token": "<fcm token>"}  (or ?token=)
    Auth:     Bearer access token (required)
    Response: {"success": true, "data": {"removed": true|false}}
    """
    token = _token_from_request()
    if not token:
        return validation_error({"token": "A device token is required"})

    removed = device_service.unregister(current_user(), token)
    return success(
        {"removed": removed},
        "Device removed." if removed else "That device was not registered to this account.",
    )


@bp.get("")
@jwt_required
def list_devices():
    """The caller's own registered devices. Tokens are masked."""
    return success(device_service.list_for_user(current_user()["id"]))
