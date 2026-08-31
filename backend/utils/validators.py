"""
Server-side validation.

These rules deliberately mirror `frontend/assets/js/utils/validators.js` so a
form that passes in the browser also passes here. Each validator returns a
`{field: message}` dict; empty means valid. The frontend already knows how to
render errors in that shape.
"""

import re

from constants import (
    CAMPUS_BOUNDS,
    CAMPUS_POLYGON,
    CATEGORIES,
    DEPARTMENT_NAMES,
    PRIORITY_LIST,
    ROLES,
    STATUS_LIST,
)

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]{2,}$")
# Indian mobile numbers, optionally with a +91 / 0 prefix.
MOBILE_RE = re.compile(r"^(?:\+?91[\-\s]?)?[0]?[6-9]\d{9}$")


def is_email(value: str) -> bool:
    return bool(EMAIL_RE.match((value or "").strip()))


def is_mobile(value: str) -> bool:
    return bool(MOBILE_RE.match((value or "").strip().replace(" ", "")))


def _text(values: dict, key: str) -> str:
    return str(values.get(key) or "").strip()


def validate_registration(values: dict) -> dict:
    errors = {}

    full_name = _text(values, "fullName") or _text(values, "name")
    if not full_name:
        errors["fullName"] = "Full name is required"
    elif len(full_name) < 3:
        errors["fullName"] = "Full name looks too short"

    if not _text(values, "userId"):
        errors["userId"] = "Student / Employee ID is required"

    email = _text(values, "email")
    if not email:
        errors["email"] = "Email address is required"
    elif not is_email(email):
        errors["email"] = "Enter a valid email address"

    if not _text(values, "department"):
        errors["department"] = "Please select your department or course"

    password = values.get("password") or ""
    if not password:
        errors["password"] = "Password is required"
    elif len(password) < 8:
        errors["password"] = "Password must be at least 8 characters"

    # Mobile is optional (the frontend is email-only), but must be valid if given.
    mobile = _text(values, "mobile") or _text(values, "phone")
    if mobile and not is_mobile(mobile):
        errors["mobile"] = "Enter a valid 10-digit mobile number"

    role = _text(values, "role")
    if role and role not in ROLES:
        errors["role"] = "Unknown role"

    return errors


def validate_login(values: dict) -> dict:
    errors = {}
    identifier = _text(values, "identifier") or _text(values, "email")
    if not identifier:
        errors["identifier"] = "Email address is required"
    elif not is_email(identifier):
        errors["identifier"] = "Enter a valid email address"

    if not values.get("password"):
        errors["password"] = "Password is required"
    elif len(values.get("password") or "") < 6:
        errors["password"] = "Password must be at least 6 characters"
    return errors


def validate_complaint(values: dict) -> dict:
    """Matches `validateComplaintDetails` plus the server-only checks."""
    errors = {}

    title = _text(values, "title")
    if not title:
        errors["title"] = "Complaint title is required"
    elif len(title) < 8:
        errors["title"] = "Title should be at least 8 characters"
    elif len(title) > 200:
        errors["title"] = "Title must be 200 characters or fewer"

    description = _text(values, "description")
    if not description:
        errors["description"] = "Please describe the problem"
    elif len(description) < 25:
        errors["description"] = (
            "Description should be at least 25 characters so it can be classified correctly"
        )
    elif len(description) > 5000:
        errors["description"] = "Description must be 5000 characters or fewer"

    category = _text(values, "category")
    if not category:
        errors["category"] = "Select a category"
    elif category not in CATEGORIES:
        errors["category"] = "Unknown category"

    department = _text(values, "department")
    if department and department not in DEPARTMENT_NAMES:
        errors["department"] = "Unknown department"

    priority = _text(values, "priority")
    if priority and priority not in PRIORITY_LIST:
        errors["priority"] = "Unknown priority"

    return errors


def point_in_polygon(lat: float, lng: float, polygon=CAMPUS_POLYGON) -> bool:
    """Ray-casting point-in-polygon test over (latitude, longitude) vertices.

    Standard even-odd rule: count how many polygon edges a ray cast east from
    the point crosses. An odd count means the point is inside. The campus is
    small enough that treating lat/lng as a flat plane costs nothing.
    """
    inside = False
    count = len(polygon)
    j = count - 1
    for i in range(count):
        lat_i, lng_i = polygon[i]
        lat_j, lng_j = polygon[j]
        # Does the edge straddle the point's latitude?
        if (lat_i > lat) != (lat_j > lat):
            # Longitude where the edge crosses that latitude.
            crossing = (lng_j - lng_i) * (lat - lat_i) / (lat_j - lat_i) + lng_i
            if lng < crossing:
                inside = not inside
        j = i
    return inside


def in_campus_bounds(lat: float, lng: float) -> bool:
    """Padded bounding-box test - the tolerant check used by validation.

    `point_in_polygon` is the exact outline; this box adds roughly 150 m of
    slack so ordinary GPS drift at the gate or along the boundary wall does not
    reject a genuine complaint.
    """
    return (
        CAMPUS_BOUNDS["minLatitude"] <= lat <= CAMPUS_BOUNDS["maxLatitude"]
        and CAMPUS_BOUNDS["minLongitude"] <= lng <= CAMPUS_BOUNDS["maxLongitude"]
    )


def validate_location(location) -> dict:
    """The frontend requires coordinates plus a landmark on step 3.

    Coordinates must also fall inside the DSVV campus: this is a campus
    grievance system, and the check lives here as well as in the browser so it
    cannot be skipped by calling the API directly.
    """
    errors = {}
    if not isinstance(location, dict):
        return {"location": "Capture or enter the complaint location"}

    lat, lng = location.get("latitude"), location.get("longitude")
    if lat is None or lng is None:
        errors["location"] = "Capture or enter the complaint location"
    else:
        try:
            lat, lng = float(lat), float(lng)
            if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
                errors["location"] = "Coordinates are out of range"
            elif not in_campus_bounds(lat, lng):
                errors["location"] = (
                    "Location must be inside the DSVV campus. "
                    "Move the pin to the correct spot on campus."
                )
        except (TypeError, ValueError):
            errors["location"] = "Coordinates must be numeric"

    if not str(location.get("address") or "").strip():
        errors["address"] = "Enter a landmark or building name"
    return errors


def validate_feedback(values: dict) -> dict:
    errors = {}
    rating = values.get("rating")
    if rating in (None, ""):
        errors["rating"] = "Please select a star rating"
    else:
        try:
            rating = int(rating)
            if rating < 1 or rating > 5:
                errors["rating"] = "Rating must be between 1 and 5"
        except (TypeError, ValueError):
            errors["rating"] = "Rating must be a number between 1 and 5"

    comment = _text(values, "comment")
    if not comment:
        errors["comment"] = "Please write a short comment"
    elif len(comment) < 10:
        errors["comment"] = "Comment should be at least 10 characters"
    return errors


def validate_status(status: str) -> dict:
    if not status:
        return {"status": "Status is required"}
    if status not in STATUS_LIST:
        return {"status": f"Unknown status. Expected one of: {', '.join(STATUS_LIST)}"}
    return {}


def validate_officer(values: dict) -> dict:
    errors = {}
    if not _text(values, "name"):
        errors["name"] = "Officer name is required"
    if not _text(values, "employeeId"):
        errors["employeeId"] = "Employee ID is required"

    email = _text(values, "email")
    if not email:
        errors["email"] = "Email is required"
    elif not is_email(email):
        errors["email"] = "Enter a valid email address"

    department = _text(values, "department")
    if not department:
        errors["department"] = "Assign a department"
    elif department not in DEPARTMENT_NAMES:
        errors["department"] = "Unknown department"

    if not _text(values, "designation"):
        errors["designation"] = "Designation is required"
    return errors


def validate_department(values: dict) -> dict:
    errors = {}
    if not _text(values, "name"):
        errors["name"] = "Department name is required"
    if not _text(values, "code"):
        errors["code"] = "Short code is required"
    if not _text(values, "head"):
        errors["head"] = "Department head is required"

    email = _text(values, "email")
    if not email:
        errors["email"] = "Contact email is required"
    elif not is_email(email):
        errors["email"] = "Enter a valid email address"
    return errors


def validate_password_change(values: dict) -> dict:
    errors = {}
    if not values.get("currentPassword"):
        errors["currentPassword"] = "Enter your current password"

    new_password = values.get("newPassword") or ""
    if not new_password:
        errors["newPassword"] = "Enter a new password"
    elif len(new_password) < 8:
        errors["newPassword"] = "New password must be at least 8 characters"
    elif new_password == values.get("currentPassword"):
        errors["newPassword"] = "New password must differ from the current one"

    if values.get("confirmPassword") is not None and values.get("confirmPassword") != new_password:
        errors["confirmPassword"] = "Passwords do not match"
    return errors


def validate_remark(values: dict) -> dict:
    errors = {}
    message = _text(values, "message")
    if not message:
        errors["message"] = "Remark cannot be empty"
    elif len(message) > 2000:
        errors["message"] = "Remark must be 2000 characters or fewer"
    return errors


def validate_resolution(values: dict) -> dict:
    errors = {}
    notes = _text(values, "notes")
    if not notes:
        errors["notes"] = "Resolution notes are required"
    elif len(notes) < 10:
        errors["notes"] = "Resolution notes should be at least 10 characters"
    return errors


def validate_otp_request(values: dict) -> dict:
    errors = {}
    email = _text(values, "email")
    if not email:
        errors["email"] = "Email address is required"
    elif not is_email(email):
        errors["email"] = "Enter a valid email address"
    return errors


def validate_otp_verify(values: dict) -> dict:
    errors = validate_otp_request(values)
    code = _text(values, "otp") or _text(values, "code")
    if not code:
        errors["otp"] = "Enter the verification code"
    elif not code.isdigit():
        errors["otp"] = "The verification code must contain only digits"
    return errors
