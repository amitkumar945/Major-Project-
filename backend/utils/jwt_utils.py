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


def create_token(user: dict, expires_in_minutes: int = None) -> str:
    """Sign a JWT carrying the user id, role and expiry.

    `expires_in_minutes` overrides the default lifetime; mobile sign-ins pass
    the shorter MOBILE_ACCESS_TOKEN_MINUTES because they also get a refresh
    token. Called without it - as every existing caller does - the behaviour
    is exactly what it was.
    """
    from utils.helpers import utcnow
    from datetime import timedelta

    issued = utcnow()
    if expires_in_minutes:
        expires = issued + timedelta(minutes=expires_in_minutes)
    else:
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


def extract_token(allow_query: bool = False) -> str:
    """Read the bearer token from the Authorization header.

    `allow_query` additionally accepts `?token=` (or `?access_token=`). That is
    opt-in per route because a token in a URL can leak through server logs,
    `Referer` headers and browser history. Only the file-download route enables
    it, and only because a browser cannot attach an `Authorization` header to
    an `<img src>` / `<a href>` request - see `routes/file_routes.py`.
    """
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        return header[7:].strip()

    if allow_query:
        return (
            request.args.get("token") or request.args.get("access_token") or ""
        ).strip()

    return ""


def _authenticate(allow_query_token: bool = False):
    """Shared verification. Returns (claims, None) or (None, response)."""
    token = extract_token(allow_query=allow_query_token)
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


def jwt_required_allow_query(fn):
    """Like `jwt_required`, but the token may also arrive as `?token=`.

    Strictly for GET routes a browser loads directly (images, downloads), where
    no `Authorization` header can be set. Authorisation is unchanged: the route
    still checks who may see the resource.
    """

    @wraps(fn)
    def wrapper(*args, **kwargs):
        _, failure = _authenticate(allow_query_token=True)
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
