"""
Authentication routes: register, login, logout, OTP, profile, password.

The login/register responses return `{ user, token, issuedAt }` - the same
session object the frontend already writes to localStorage - so `session.js`
and `requireRole()` keep working unchanged.
"""

from flask import Blueprint, g, request

from constants import ROLE_STUDENT
from services import audit_service, auth_service, otp_service
from utils.helpers import iso, utcnow
from utils.jwt_utils import create_token, current_user, jwt_required
from utils.rate_limit import rate_limit
from utils.responses import ApiException, error, success, validation_error
from utils.validators import (
    validate_login,
    validate_otp_request,
    validate_otp_verify,
    validate_password_change,
    validate_registration,
)

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


def _session_payload(user: dict) -> dict:
    """The exact session shape the frontend stores."""
    return {"user": user, "token": create_token(user), "issuedAt": iso(utcnow())}


@bp.post("/register")
@rate_limit("auth")
def register():
    values = request.get_json(silent=True) or {}

    errors = validate_registration(values)
    if errors:
        return validation_error(errors)

    # Optional OTP gate, controlled by OTP_REQUIRED_FOR_REGISTER.
    from flask import current_app

    if current_app.config.get("OTP_REQUIRED_FOR_REGISTER"):
        if not otp_service.is_verified(values.get("email"), otp_service.PURPOSE_REGISTER):
            return error("Please verify your email address with the code we sent before registering.", 403)
        values["emailVerified"] = True

    # Self-registration is always a student; role escalation needs an admin token.
    requested_role = (values.get("role") or ROLE_STUDENT).strip().lower()
    actor = None
    if requested_role != ROLE_STUDENT:
        from utils.jwt_utils import extract_token, decode_token

        if extract_token():
            try:
                claims = decode_token(extract_token())
                actor = auth_service.find_by_id(claims.get("userId"))
            except Exception:
                actor = None

    user = auth_service.register(values, created_by=actor)

    if current_app.config.get("OTP_REQUIRED_FOR_REGISTER"):
        otp_service.clear(values.get("email"), otp_service.PURPOSE_REGISTER)

    return success(_session_payload(user), "Account created successfully.", 201)


@bp.post("/login")
@rate_limit("auth")
def login():
    values = request.get_json(silent=True) or {}

    errors = validate_login(values)
    if errors:
        return validation_error(errors)

    identifier = values.get("identifier") or values.get("email")
    user = auth_service.authenticate(identifier, values.get("password"), values.get("role", ""))
    return success(_session_payload(user), "Signed in successfully.")


@bp.post("/logout")
@jwt_required
def logout():
    # JWTs are stateless: the client discards the token. The event is logged so
    # the audit trail still shows the sign-out.
    audit_service.log(audit_service.LOGOUT, current_user(), "Signed out.")
    return success({"success": True}, "Signed out successfully.")


@bp.get("/me")
@jwt_required
def me():
    """Used to re-hydrate a session and to confirm a token is still valid."""
    return success(current_user())


@bp.put("/profile")
@jwt_required
def update_profile():
    changes = request.get_json(silent=True) or {}
    user = auth_service.update_profile(current_user()["id"], changes)
    return success(user, "Profile updated successfully.")


@bp.put("/password")
@jwt_required
def change_password():
    values = request.get_json(silent=True) or {}

    errors = validate_password_change(values)
    if errors:
        return validation_error(errors)

    auth_service.change_password(
        current_user()["id"], values.get("currentPassword"), values.get("newPassword")
    )
    return success({"success": True}, "Password changed successfully.")


# ---------------------------------------------------------------- OTP flow


@bp.post("/send-otp")
@rate_limit("otp")
def send_otp():
    values = request.get_json(silent=True) or {}

    errors = validate_otp_request(values)
    if errors:
        return validation_error(errors)

    purpose = (values.get("purpose") or otp_service.PURPOSE_VERIFY).strip()
    email = values.get("email")

    # For password reset the address must exist; for registration it must not.
    if purpose == otp_service.PURPOSE_RESET and not auth_service.find_by_email(email):
        return error("No account is registered with this email address.", 404)
    if purpose == otp_service.PURPOSE_REGISTER and auth_service.find_by_email(email):
        return error("An account with this email address already exists.", 409)

    result = otp_service.send_otp(email, purpose)
    audit_service.log(audit_service.OTP_SENT, None, f"OTP issued for {email} ({purpose}).")
    return success(result, "Verification code sent.")


@bp.post("/verify-otp")
@rate_limit("otp")
def verify_otp():
    values = request.get_json(silent=True) or {}

    errors = validate_otp_verify(values)
    if errors:
        return validation_error(errors)

    email = values.get("email")
    code = values.get("otp") or values.get("code")
    purpose = (values.get("purpose") or otp_service.PURPOSE_VERIFY).strip()

    otp_service.verify_otp(email, code, purpose)
    audit_service.log(audit_service.OTP_VERIFIED, None, f"OTP verified for {email} ({purpose}).")

    payload = {"verified": True, "email": email, "purpose": purpose}

    # A verified login OTP issues a session straight away.
    if purpose == otp_service.PURPOSE_LOGIN:
        user = auth_service.find_by_email(email)
        if not user:
            return error("No account is registered with this email address.", 404)
        otp_service.clear(email, purpose)
        payload.update(_session_payload(user))

    return success(payload, "Verification successful.")


@bp.post("/resend-otp")
@rate_limit("otp")
def resend_otp():
    values = request.get_json(silent=True) or {}

    errors = validate_otp_request(values)
    if errors:
        return validation_error(errors)

    purpose = (values.get("purpose") or otp_service.PURPOSE_VERIFY).strip()
    result = otp_service.send_otp(values.get("email"), purpose)
    return success(result, "A new verification code has been sent.")


# ------------------------------------------------------------ password reset


@bp.post("/forgot-password")
@rate_limit("auth")
def forgot_password():
    """Start a reset. Always reports success so the endpoint cannot be used to
    discover which email addresses are registered."""
    values = request.get_json(silent=True) or {}

    errors = validate_otp_request(values)
    if errors:
        return validation_error(errors)

    email = values.get("email")
    payload = {"emailSent": True}

    if auth_service.find_by_email(email):
        result = otp_service.send_otp(email, otp_service.PURPOSE_RESET)
        # Only surfaced in development mode.
        if result.get("otp"):
            payload["otp"] = result["otp"]
            payload["devMode"] = True
        payload["expiresIn"] = result.get("expiresIn")

    return success(payload, "If that address is registered, a reset code has been sent to it.")


@bp.post("/reset-password")
@rate_limit("auth")
def reset_password():
    """Finish a reset: verify the OTP, then set the new password."""
    values = request.get_json(silent=True) or {}

    errors = validate_otp_verify(values)
    new_password = values.get("newPassword") or values.get("password") or ""
    if not new_password:
        errors["newPassword"] = "Enter a new password"
    elif len(new_password) < 8:
        errors["newPassword"] = "Password must be at least 8 characters"
    if errors:
        return validation_error(errors)

    email = values.get("email")
    code = values.get("otp") or values.get("code")

    otp_service.verify_otp(email, code, otp_service.PURPOSE_RESET)
    auth_service.reset_password(email, new_password)
    otp_service.clear(email, otp_service.PURPOSE_RESET)

    return success({"success": True}, "Your password has been reset. Please sign in.")
