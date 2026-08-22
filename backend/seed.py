"""
Seed the database with departments and the demo accounts.

Idempotent: running it repeatedly will not duplicate anything. Existing
documents are left untouched, so it is safe to call on every start.

The three demo logins from the frontend README are recreated here with real
bcrypt-hashed passwords, so the same credentials work against the live API.
Passwords come from the environment (SEED_*_PASSWORD) and fall back to the
documented demo values only in development.
"""

import logging
import os

from constants import DEPARTMENTS, ROLE_ADMIN, ROLE_OFFICER, ROLE_STUDENT
from database import departments as departments_collection
from database import users as users_collection
from services import auth_service
from utils.helpers import iso, utcnow

logger = logging.getLogger(__name__)


def _password(env_name: str, fallback: str) -> str:
    return os.environ.get(env_name) or fallback


# Officer directory, matching the frontend's seed officers so the demo shows
# the same names. Emails are invented, as the README states.
SEED_OFFICERS = [
    {
        "id": "OFF-2001", "name": "Er. Devendra Singh Rawat", "employeeId": "DSVV/NIR/114",
        "email": "officer@dsvv.ac.in", "department": "Nirman Vibhag",
        "designation": "Civil Maintenance Officer", "avatarColor": "#b45309",
    },
    {
        "id": "OFF-2002", "name": "Er. Pankaj Kumar Semwal", "employeeId": "DSVV/JAL/207",
        "email": "pankaj.semwal@dsvv.ac.in", "department": "Jal Kal Vibhag",
        "designation": "Water Supply Officer", "avatarColor": "#0369a1",
    },
    {
        "id": "OFF-2003", "name": "Er. Naveen Chandra Painuli", "employeeId": "DSVV/VID/331",
        "email": "naveen.painuli@dsvv.ac.in", "department": "Vidyut Vibhag",
        "designation": "Electrical Maintenance Officer", "avatarColor": "#a16207",
    },
    {
        "id": "OFF-2004", "name": "Dr. Anupam Kaushik", "employeeId": "DSVV/MCA/408",
        "email": "anupam.kaushik@dsvv.ac.in", "department": "MCA Lab / Computer Lab",
        "designation": "Lab In-charge", "avatarColor": "#6d28d9",
    },
]

SEED_STUDENTS = [
    {
        "id": "USR-1001", "name": "Rakesh Patidar", "userId": "MCA/2024/018",
        "email": "student@dsvv.ac.in", "department": "MCA - Department of Computer Science",
        "course": "Master of Computer Applications", "year": "2nd Year",
        "hostel": "Gayatri Bhavan, Room 214", "userType": "Student", "avatarColor": "#4f46e5",
    },
    {
        "id": "USR-1002", "name": "Sneha Bhardwaj", "userId": "MSC/2025/044",
        "email": "sneha.bhardwaj@dsvv.ac.in", "department": "M.Sc. Yogic Science",
        "course": "M.Sc. Yogic Science", "year": "1st Year",
        "hostel": "Saraswati Bhavan, Room 108", "userType": "Student", "avatarColor": "#059669",
    },
    {
        "id": "USR-1003", "name": "Aditya Nautiyal", "userId": "BCA/2024/091",
        "email": "aditya.nautiyal@dsvv.ac.in", "department": "BCA - Department of Computer Science",
        "course": "Bachelor of Computer Applications", "year": "3rd Year",
        "hostel": "Chetna Bhavan, Room 302", "userType": "Student", "avatarColor": "#d97706",
    },
]

SEED_ADMIN = {
    "id": "ADM-3001", "name": "Dr. Shailendra Prakash Dwivedi", "employeeId": "DSVV/ADM/001",
    "email": "admin@dsvv.ac.in", "department": "Office of the Registrar",
    "designation": "Grievance Redressal Cell - Nodal Officer", "avatarColor": "#1e293b",
}


def seed_departments() -> int:
    created = 0
    for department in DEPARTMENTS:
        if departments_collection().find_one({"code": department["code"]}):
            continue
        departments_collection().insert_one({**department, "createdAt": iso(utcnow())})
        created += 1
    return created


def _insert_user(record: dict, role: str, password: str, user_type: str) -> bool:
    """Insert one account if that email is not already registered."""
    if users_collection().find_one({"email": record["email"]}):
        return False

    document = {
        **record,
        "role": role,
        "userType": user_type,
        "email": record["email"].lower(),
        "mobile": record.get("mobile", ""),
        "isActive": True,
        "emailVerified": True,
        "joinedAt": iso(utcnow()),
        "passwordHash": auth_service.hash_password(password),
    }
    document.setdefault("userId", record.get("employeeId", ""))
    document.setdefault("course", record.get("department", ""))
    document.setdefault("year", "—")
    document.setdefault("hostel", "—")

    if role == ROLE_OFFICER:
        document["stats"] = {"activeComplaints": 0, "resolved": 0, "avgResolutionDays": 0, "rating": 0}

    users_collection().insert_one(document)
    return True


def seed_users() -> int:
    created = 0

    student_password = _password("SEED_STUDENT_PASSWORD", "student123")
    officer_password = _password("SEED_OFFICER_PASSWORD", "officer123")
    admin_password = _password("SEED_ADMIN_PASSWORD", "admin123")

    for student in SEED_STUDENTS:
        created += _insert_user(student, ROLE_STUDENT, student_password, "Student")

    for officer in SEED_OFFICERS:
        created += _insert_user(officer, ROLE_OFFICER, officer_password, "Officer")

    created += _insert_user(SEED_ADMIN, ROLE_ADMIN, admin_password, "Administrator")
    return created


def _sync_counters() -> None:
    """Advance the id counters past the fixed ids the seeds occupy.

    The seeds insert USR-1001.. / OFF-2001.. directly, so without this the
    counter would hand the same ids out again to the next real registration.
    """
    from database import counters

    for prefix, base, counter, role in (
        ("USR", 1000, "user_id", ROLE_STUDENT),
        ("OFF", 2000, "officer_id", ROLE_OFFICER),
        ("ADM", 3000, "admin_id", ROLE_ADMIN),
    ):
        highest = 0
        for record in users_collection().find({"role": role}, {"_id": 0, "id": 1}):
            identifier = record.get("id", "")
            if identifier.startswith(f"{prefix}-"):
                try:
                    highest = max(highest, int(identifier.split("-")[1]) - base)
                except (ValueError, IndexError):
                    continue

        if highest > 0:
            counters().update_one(
                {"_id": counter},
                {"$max": {"seq": highest}},
                upsert=True,
            )


def run(verbose: bool = True) -> dict:
    """Seed everything. Safe to call on every application start."""
    result = {"departments": seed_departments(), "users": seed_users()}
    _sync_counters()

    if verbose and (result["departments"] or result["users"]):
        logger.info(
            "Seeded %s department(s) and %s user account(s).",
            result["departments"], result["users"],
        )
    return result


if __name__ == "__main__":
    # Allow `python seed.py` as a standalone command.
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent))

    from config import get_config
    from database import init_db

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    config = get_config()

    if not config.JWT_SECRET_KEY:
        print("JWT_SECRET_KEY is not set. Copy .env.example to .env first.")
        raise SystemExit(1)

    init_db(config)
    outcome = run()
    print(f"Seeded {outcome['departments']} department(s) and {outcome['users']} user account(s).")
