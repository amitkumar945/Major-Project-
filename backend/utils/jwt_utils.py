"""
JWT creation and the route decorators that protect endpoints.

`@jwt_required` verifies the bearer token and puts the claims on Flask's `g`;
`@role_required("admin")` additionally checks the role claim. Both return the
standard error envelope so the frontend's `ApiError` handling keeps working.
"""

from functools import wraps

import jwt
from flask import current_app, g, request

from utils.responses import error


def _config(key: str, default=None):
    return current_app.config.get(key, default)


def create_token(user: dict) -> str:
    """Sign a JWT carrying the user id, role and expiry."""
    from utils.helpers import utcnow
    from datetime import timedelta

    issued = utcnow()
    expires = issued + timedelta(hours=_config("JWT_EXPIRY_HOURS", 12))

    payload = {
        "sub": user["id"],
        "userId": user["id"],
        "role": user["role"],
        "email": user.get("email", ""),
        "name": user.get("name", ""),
        "iat": int(issued.timestamp()),
        "exp": int(expires.timestamp()),
        "iss": _config("JWT_ISSUER", "dsvv-gms"),
    }
    return jwt.encode(payload, _config("JWT_SECRET_KEY"), algorithm=_config("JWT_ALGORITHM", "HS256"))


def decode_token(token: str) -> dict:
    """Verify and decode. Raises jwt exceptions on failure."""
    return jwt.decode(
        token,
        _config("JWT_SECRET_KEY"),
        algorithms=[_config("JWT_ALGORITHM", "HS256")],
        issuer=_config("JWT_ISSUER", "dsvv-gms"),
    )


def extract_token() -> str:
    """Read the bearer token from the Authorization header."""
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        return header[7:].strip()
    return ""


def _authenticate():
    """Shared verification. Returns (claims, None) or (None, response)."""
    token = extract_token()
    if not token:
        return None, error("Authentication required. Please sign in.", 401)

    try:
        claims = decode_token(token)
    except jwt.ExpiredSignatureError:
        return None, error("Your session has expired. Please sign in again.", 401)
    except jwt.InvalidTokenError:
        return None, error("Invalid authentication token.", 401)

    # Reject tokens for users who were deleted or deactivated after signing in.
    from database import users as users_collection

    account = users_collection().find_one(
        {"id": claims.get("userId")}, {"_id": 0, "passwordHash": 0}
    )
    if not account:
        return None, error("Your account no longer exists.", 401)
    if account.get("isActive") is False:
        return None, error("Your account has been deactivated. Contact the administrator.", 403)

    g.claims = claims
    g.current_user = account
    return claims, None


def jwt_required(fn):
    """Protect a route: a valid, non-expired token is mandatory."""

    @wraps(fn)
    def wrapper(*args, **kwargs):
        _, failure = _authenticate()
        if failure:
            return failure
        return fn(*args, **kwargs)

    return wrapper


def role_required(*roles):
    """Protect a route and restrict it to the given role(s).

    Usage:  @role_required("admin")  /  @role_required("officer", "admin")
    """

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            claims, failure = _authenticate()
            if failure:
                return failure
            if claims.get("role") not in roles:
                return error(
                    "You do not have permission to perform this action.", 403
                )
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def optional_jwt(fn):
    """Attach the user when a token is present, but allow anonymous access.

    Used by public tracking, which shows less detail to anonymous visitors.
    """

    @wraps(fn)
    def wrapper(*args, **kwargs):
        g.claims = None
        g.current_user = None
        if extract_token():
            _authenticate()  # populates g on success, ignored on failure
        return fn(*args, **kwargs)

    return wrapper


def current_user() -> dict:
    """The signed-in user document, or None."""
    return getattr(g, "current_user", None)


def current_user_id() -> str:
    user = current_user()
    return user["id"] if user else None


def current_role() -> str:
    user = current_user()
    return user["role"] if user else None


def is_admin() -> bool:
    return current_role() == "admin"
