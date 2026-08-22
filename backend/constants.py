"""
Domain constants.

This module is the Python mirror of `frontend/assets/js/utils/constants.js`.
Every string here (status names, department names, priorities) must match the
frontend exactly, because the UI switches on these literal values.
"""

# ------------------------------------------------------------------- roles

ROLE_STUDENT = "student"
ROLE_OFFICER = "officer"
ROLE_ADMIN = "admin"

ROLES = (ROLE_STUDENT, ROLE_OFFICER, ROLE_ADMIN)

# The frontend register screen only ever creates students; officers and admins
# are created by an administrator.
SELF_REGISTER_ROLES = (ROLE_STUDENT,)

# ------------------------------------------------------------- departments

DEPARTMENT_CODES = {
    "NIRMAN": "Nirman Vibhag",
    "JALKAL": "Jal Kal Vibhag",
    "VIDYUT": "Vidyut Vibhag",
    "MCALAB": "MCA Lab / Computer Lab",
}

DEPARTMENT_NAMES = list(DEPARTMENT_CODES.values())

# Static identity of each department (matches constants.js DEPARTMENTS).
DEPARTMENTS = [
    {
        "code": "NIRMAN",
        "name": "Nirman Vibhag",
        "english": "Construction & Maintenance",
        "description": "Civil works, building repair, furniture, carpentry, painting and campus infrastructure upkeep.",
        "color": "amber",
        "head": "Er. Mahesh Chandra Joshi",
        "email": "nirman@dsvv.ac.in",
        "office": "Estate Office, Administrative Block, Ground Floor",
        "establishedYear": 2004,
        "isActive": True,
    },
    {
        "code": "JALKAL",
        "name": "Jal Kal Vibhag",
        "english": "Water & Sanitation",
        "description": "Water supply, plumbing, RO plants, drainage, sewage lines and campus sanitation.",
        "color": "sky",
        "head": "Er. Suresh Prasad Nautiyal",
        "email": "jalkal@dsvv.ac.in",
        "office": "Water Works Cell, Behind Annapurna Bhavan",
        "establishedYear": 2006,
        "isActive": True,
    },
    {
        "code": "VIDYUT",
        "name": "Vidyut Vibhag",
        "english": "Electricity & Power",
        "description": "Power supply, wiring, fans, lights, generators, street lights and electrical safety.",
        "color": "yellow",
        "head": "Er. Rakesh Kumar Bhatt",
        "email": "vidyut@dsvv.ac.in",
        "office": "Electrical Substation, Gate No. 2",
        "establishedYear": 2004,
        "isActive": True,
    },
    {
        "code": "MCALAB",
        "name": "MCA Lab / Computer Lab",
        "english": "Computing & Network",
        "description": "Lab computers, projectors, printers, LAN, Wi-Fi, software installation and lab support.",
        "color": "violet",
        "head": "Dr. Anupam Kaushik",
        "email": "computerlab@dsvv.ac.in",
        "office": "Department of Computer Science, Shantikunj Bhavan, 2nd Floor",
        "establishedYear": 2011,
        "isActive": True,
    },
]

# -------------------------------------------------------------- categories

CATEGORIES = [
    "Building",
    "Water",
    "Electricity",
    "Computer/Lab",
    "Hostel",
    "Classroom",
    "Other",
]

CATEGORY_DEPARTMENT_MAP = {
    "Building": "Nirman Vibhag",
    "Water": "Jal Kal Vibhag",
    "Electricity": "Vidyut Vibhag",
    "Computer/Lab": "MCA Lab / Computer Lab",
    "Hostel": "Nirman Vibhag",
    "Classroom": "Nirman Vibhag",
    "Other": "Nirman Vibhag",
}

# ------------------------------------------------------------------ status

STATUS_SUBMITTED = "Submitted"
STATUS_UNDER_REVIEW = "Under Review"
STATUS_ASSIGNED = "Assigned"
STATUS_ACCEPTED = "Accepted"
STATUS_IN_PROGRESS = "In Progress"
STATUS_PENDING = "Pending"
STATUS_RESOLVED = "Resolved"
STATUS_CLOSED = "Closed"
STATUS_REOPENED = "Reopened"
STATUS_ESCALATED = "Escalated"

STATUS_LIST = [
    STATUS_SUBMITTED,
    STATUS_UNDER_REVIEW,
    STATUS_ASSIGNED,
    STATUS_ACCEPTED,
    STATUS_IN_PROGRESS,
    STATUS_PENDING,
    STATUS_RESOLVED,
    STATUS_CLOSED,
    STATUS_REOPENED,
    STATUS_ESCALATED,
]

# Statuses that mean "the complaint is still open".
ACTIVE_STATUSES = [
    STATUS_SUBMITTED,
    STATUS_UNDER_REVIEW,
    STATUS_ASSIGNED,
    STATUS_ACCEPTED,
    STATUS_IN_PROGRESS,
    STATUS_PENDING,
    STATUS_REOPENED,
    STATUS_ESCALATED,
]

CLOSED_STATUSES = [STATUS_RESOLVED, STATUS_CLOSED]

# Status values a department officer is allowed to set.
OFFICER_STATUS_OPTIONS = [
    STATUS_ASSIGNED,
    STATUS_ACCEPTED,
    STATUS_IN_PROGRESS,
    STATUS_PENDING,
    STATUS_RESOLVED,
]

# ---------------------------------------------------------------- priority

PRIORITY_LOW = "Low"
PRIORITY_MEDIUM = "Medium"
PRIORITY_HIGH = "High"
PRIORITY_URGENT = "Urgent"

PRIORITY_LIST = [PRIORITY_LOW, PRIORITY_MEDIUM, PRIORITY_HIGH, PRIORITY_URGENT]

# Service-level agreement in days, used to compute the resolution deadline.
PRIORITY_SLA_DAYS = {
    PRIORITY_URGENT: 1,
    PRIORITY_HIGH: 3,
    PRIORITY_MEDIUM: 7,
    PRIORITY_LOW: 14,
}

# --------------------------------------------------------------- escalation

ESCALATION_LEVELS = [
    {"level": 1, "authority": "Department Officer", "afterDays": 0},
    {"level": 2, "authority": "Department Head", "afterDays": 2},
    {"level": 3, "authority": "Admin / Higher Authority", "afterDays": 5},
]

# ------------------------------------------------------------ notifications

NOTIFICATION_TYPES = {
    "SUBMITTED": "submitted",
    "ASSIGNED": "assigned",
    "STATUS_CHANGED": "status_changed",
    "OFFICER_ASSIGNED": "officer_assigned",
    "RESOLUTION_SUBMITTED": "resolution_submitted",
    "RESOLVED": "resolved",
    "DEADLINE_APPROACHING": "deadline_approaching",
    "ESCALATED": "escalated",
    "FEEDBACK_REQUESTED": "feedback_requested",
}

# ---------------------------------------------------------------- uploads

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "pdf", "doc", "docx"}

# Extension -> the MIME types that are genuinely acceptable for it.
ALLOWED_MIME_TYPES = {
    "png": {"image/png"},
    "jpg": {"image/jpeg"},
    "jpeg": {"image/jpeg"},
    "webp": {"image/webp"},
    "pdf": {"application/pdf"},
    "doc": {"application/msword", "application/x-ole-storage"},
    "docx": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/zip",
    },
}

# Magic-number signatures, so a renamed .exe cannot pass as a .png.
FILE_SIGNATURES = {
    "png": [b"\x89PNG\r\n\x1a\n"],
    "jpg": [b"\xff\xd8\xff"],
    "jpeg": [b"\xff\xd8\xff"],
    "webp": [b"RIFF"],
    "pdf": [b"%PDF-"],
    "doc": [b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"],
    "docx": [b"PK\x03\x04"],
}

# `kind` label the frontend uses on evidence objects.
EXTENSION_KIND = {
    "png": "image",
    "jpg": "image",
    "jpeg": "image",
    "webp": "image",
    "pdf": "pdf",
    "doc": "doc",
    "docx": "doc",
}

# ------------------------------------------------------------------- misc

UNIVERSITY_SHORT = "DSVV"
APP_NAME = "Grievance Management System"
CAMPUS_CENTER = {"latitude": 29.9457, "longitude": 78.1642}
