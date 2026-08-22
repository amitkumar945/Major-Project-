"""
Authentication: registration, login, password hashing and profile updates.

Passwords are hashed with bcrypt and never stored, logged or returned. The
`passwordHash` field is projected out of every read, so no code path can leak
it by accident.
"""

import bcrypt
from pymongo.errors import DuplicateKeyError

from constants import ROLE_ADMIN, ROLE_OFFICER, ROLE_STUDENT, ROLES
from database import next_sequence, users
from services import audit_service
from utils.helpers import clean_document, iso, utcnow
from utils.responses import ApiException

# Never return these fields to a client.
SAFE_PROJECTION = {"_id": 0, "passwordHash": 0}

# bcrypt caps input at 72 bytes; longer passwords are silently truncated by the
# library, so reject them instead of accepting a password that is not fully checked.
MAX_PASSWORD_BYTES = 72


def hash_password(password: str) -> str:
    if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise ApiException("Password must be 72 bytes or fewer.", 400)
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    if not password or not password_hash:
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8")[:MAX_PASSWORD_BYTES], password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def normalise_email(email: str) -> str:
    return (email or "").strip().lower()


def _next_user_id(role: str) -> str:
    """Ids follow the frontend's convention: USR-1001 / OFF-2001 / ADM-3001.

    The counter can lag behind reality when accounts were inserted directly
    (the seed script writes fixed ids), so skip any id already taken rather
    than letting the unique index reject the insert.
    """
    prefix, base, counter = {
        ROLE_OFFICER: ("OFF", 2000, "officer_id"),
        ROLE_ADMIN: ("ADM", 3000, "admin_id"),
    }.get(role, ("USR", 1000, "user_id"))

    for _ in range(1000):
        candidate = f"{prefix}-{base + next_sequence(counter):04d}"
        if not users().find_one({"id": candidate}, {"_id": 1}):
            return candidate

    raise ApiException("Could not allocate a new account id.", 500)


def find_by_email(email: str, include_hash: bool = False) -> dict:
    projection = {"_id": 0} if include_hash else SAFE_PROJECTION
    return users().find_one({"email": normalise_email(email)}, projection)


def find_by_id(user_id: str) -> dict:
    return users().find_one({"id": user_id}, SAFE_PROJECTION)


def register(values: dict, created_by: dict = None) -> dict:
    """Create an account. Self-registration always produces a student; only an
    administrator can create officers or admins."""
    email = normalise_email(values.get("email"))
    role = (values.get("role") or ROLE_STUDENT).strip().lower()

    if role not in ROLES:
        raise ApiException("Unknown role.", 400)

    # Privilege guard: elevated roles require an authenticated admin.
    if role in (ROLE_OFFICER, ROLE_ADMIN):
        if not created_by or created_by.get("role") != ROLE_ADMIN:
            raise ApiException("Only an administrator can create officer or admin accounts.", 403)

    if find_by_email(email):
        raise ApiException("An account with this email address already exists.", 409)

    now = iso(utcnow())
    full_name = (values.get("fullName") or values.get("name") or "").strip()
    department = (values.get("department") or "").strip()

    user = {
        "id": _next_user_id(role),
        "role": role,
        "name": full_name,
        "userId": (values.get("userId") or "").strip(),
        "email": email,
        "mobile": (values.get("mobile") or values.get("phone") or "").strip(),
        "department": department,
        "course": (values.get("course") or department).strip(),
        "year": (values.get("year") or "—").strip(),
        "hostel": (values.get("hostel") or "—").strip(),
        "userType": (values.get("userType") or ("Officer" if role == ROLE_OFFICER else "Administrator" if role == ROLE_ADMIN else "Student")),
        "avatarColor": values.get("avatarColor") or "#4f46e5",
        "isActive": True,
        "emailVerified": bool(values.get("emailVerified", False)),
        "joinedAt": now,
        "passwordHash": hash_password(values.get("password") or ""),
    }

    if role == ROLE_OFFICER:
        user["employeeId"] = (values.get("employeeId") or "").strip()
        user["designation"] = (values.get("designation") or "").strip()
        user["stats"] = {"activeComplaints": 0, "resolved": 0, "avgResolutionDays": 0, "rating": 0}

    try:
        users().insert_one(user)
    except DuplicateKeyError as exc:
        # Report the field that actually collided - an id clash is a server
        # bug, not something the user can fix by changing their email.
        if "email" in str(exc):
            raise ApiException("An account with this email address already exists.", 409)
        raise ApiException("Could not create the account. Please try again.", 500)

    safe = clean_document({k: v for k, v in user.items() if k != "passwordHash"})
    audit_service.log(
        audit_service.REGISTER, safe, f"Account created with role '{role}'."
    )
    return safe


def authenticate(identifier: str, password: str, role: str = "") -> dict:
    """Verify credentials and return the user document without the hash."""
    account = find_by_email(identifier, include_hash=True)

    if not account:
        # Same message and timing cost for both failure modes, so the endpoint
        # cannot be used to discover which emails are registered.
        bcrypt.hashpw(b"timing-equaliser", bcrypt.gensalt(rounds=12))
        audit_service.log(
            audit_service.LOGIN_FAILED, None,
            f"Login attempt for unknown email '{normalise_email(identifier)}'.",
        )
        raise ApiException("Incorrect email or password.", 401)

    if not verify_password(password, account.get("passwordHash", "")):
        audit_service.log(
            audit_service.LOGIN_FAILED,
            clean_document({k: v for k, v in account.items() if k != "passwordHash"}),
            "Login attempt with an incorrect password.",
        )
        raise ApiException("Incorrect email or password.", 401)

    if account.get("isActive") is False:
        raise ApiException("Your account has been deactivated. Contact the administrator.", 403)

    if role and account.get("role") != role:
        raise ApiException(
            f"This account is not registered as a {role}. Please choose the correct login type.", 403
        )

    safe = clean_document({k: v for k, v in account.items() if k != "passwordHash"})
    users().update_one({"id": account["id"]}, {"$set": {"lastLoginAt": iso(utcnow())}})
    audit_service.log(audit_service.LOGIN, safe, "Signed in successfully.")
    return safe


def change_password(user_id: str, current_password: str, new_password: str) -> None:
    account = users().find_one({"id": user_id}, {"_id": 0})
    if not account:
        raise ApiException("Account not found.", 404)

    if not verify_password(current_password, account.get("passwordHash", "")):
        raise ApiException("Your current password is incorrect.", 401)

    users().update_one(
        {"id": user_id},
        {"$set": {"passwordHash": hash_password(new_password), "passwordChangedAt": iso(utcnow())}},
    )
    audit_service.log(
        audit_service.PASSWORD_CHANGED,
        clean_document({k: v for k, v in account.items() if k != "passwordHash"}),
        "Password changed.",
    )


def reset_password(email: str, new_password: str) -> None:
    """Set a new password after an OTP-verified reset. No current password needed."""
    account = find_by_email(email)
    if not account:
        raise ApiException("No account is registered with this email address.", 404)

    users().update_one(
        {"id": account["id"]},
        {"$set": {"passwordHash": hash_password(new_password), "passwordChangedAt": iso(utcnow())}},
    )
    audit_service.log(audit_service.PASSWORD_CHANGED, account, "Password reset via OTP.")


# Fields a user may change on their own profile. Anything else (role, isActive,
# email, id) is ignored, so a client cannot escalate its own privileges.
EDITABLE_PROFILE_FIELDS = (
    "name", "mobile", "department", "course", "year", "hostel", "avatarColor", "designation",
)


def update_profile(user_id: str, changes: dict) -> dict:
    updates = {
        key: (value.strip() if isinstance(value, str) else value)
        for key, value in (changes or {}).items()
        if key in EDITABLE_PROFILE_FIELDS
    }
    if not updates:
        raise ApiException("There is nothing to update.", 400)

    updates["updatedAt"] = iso(utcnow())
    result = users().find_one_and_update(
        {"id": user_id}, {"$set": updates}, projection=SAFE_PROJECTION, return_document=True
    )
    if not result:
        raise ApiException("Account not found.", 404)
    return clean_document(result)


def set_active(user_id: str, is_active: bool, actor: dict = None) -> dict:
    result = users().find_one_and_update(
        {"id": user_id},
        {"$set": {"isActive": bool(is_active), "updatedAt": iso(utcnow())}},
        projection=SAFE_PROJECTION,
        return_document=True,
    )
    if not result:
        raise ApiException("Account not found.", 404)

    audit_service.log(
        audit_service.ADMIN_CHANGE, actor,
        f"{'Activated' if is_active else 'Deactivated'} account {user_id}.",
        meta={"targetUserId": user_id},
    )
    return clean_document(result)
