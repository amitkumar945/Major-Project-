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
from datetime import timedelta

from constants import (
    DEPARTMENTS,
    PRIORITY_HIGH,
    PRIORITY_LOW,
    PRIORITY_MEDIUM,
    PRIORITY_URGENT,
    ROLE_ADMIN,
    ROLE_OFFICER,
    ROLE_STUDENT,
    STATUS_ASSIGNED,
    STATUS_CLOSED,
    STATUS_ESCALATED,
    STATUS_IN_PROGRESS,
    STATUS_PENDING,
    STATUS_RESOLVED,
    STATUS_SUBMITTED,
)
from database import assignments as assignments_collection
from database import complaints as complaints_collection
from database import departments as departments_collection
from database import feedback as feedback_collection
from database import users as users_collection
from services import auth_service
from utils.helpers import calculate_deadline, iso, utcnow

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

# These records exist solely for demonstrations and visual QA.  They are NOT
# loaded on application start: use `python seed.py --demo-data` when a local
# database needs a realistic, chartable dataset.  The dates are calculated at
# run time, which keeps the monthly and SLA views useful whenever the demo is
# installed.
DEMO_COMPLAINTS = [
    ("90001", "Water leakage outside Gayatri Bhavan", "A pipeline joint is leaking onto the hostel walkway.", "Water", "Jal Kal Vibhag", PRIORITY_HIGH, STATUS_RESOLVED, 320, 2, 5),
    ("90002", "Street lights are not working near Gate 2", "The approach road remains dark after evening classes.", "Electricity", "Vidyut Vibhag", PRIORITY_HIGH, STATUS_CLOSED, 278, 3, 4),
    ("90003", "Computer lab projector flickers during lectures", "Projector input cuts out repeatedly in the MCA laboratory.", "Computer/Lab", "MCA Lab / Computer Lab", PRIORITY_MEDIUM, STATUS_RESOLVED, 244, 4, 5),
    ("90004", "Broken washroom tap in Saraswati Bhavan", "The tap has been running continuously and wastes water.", "Water", "Jal Kal Vibhag", PRIORITY_MEDIUM, STATUS_RESOLVED, 208, 2, 4),
    ("90005", "Damaged classroom ceiling panel", "A ceiling panel is loose in the first-floor classroom.", "Building", "Nirman Vibhag", PRIORITY_HIGH, STATUS_CLOSED, 176, 3, 5),
    ("90006", "Wi-Fi unavailable in computer lab", "Students cannot access the campus network during practical sessions.", "Computer/Lab", "MCA Lab / Computer Lab", PRIORITY_MEDIUM, STATUS_RESOLVED, 146, 5, 4),
    ("90007", "Voltage fluctuation in hostel study room", "Fans and lights fluctuate frequently in the evening.", "Electricity", "Vidyut Vibhag", PRIORITY_URGENT, STATUS_RESOLVED, 113, 1, 5),
    ("90008", "Drainage blockage behind Annapurna Bhavan", "Standing water has accumulated after the recent rain.", "Water", "Jal Kal Vibhag", PRIORITY_HIGH, STATUS_CLOSED, 83, 2, 3),
    ("90009", "Library reading room fan needs repair", "The fan makes loud noise and stops after a few minutes.", "Building", "Nirman Vibhag", PRIORITY_LOW, STATUS_RESOLVED, 53, 6, 4),
    ("90010", "Network ports unavailable in MCA Lab", "Several workstations have no LAN connectivity for project work.", "Computer/Lab", "MCA Lab / Computer Lab", PRIORITY_HIGH, STATUS_IN_PROGRESS, 24, None, None),
    ("90011", "Water supply is irregular in Gayatri Bhavan", "Water pressure drops significantly during the morning peak.", "Water", "Jal Kal Vibhag", PRIORITY_HIGH, STATUS_PENDING, 15, None, None),
    ("90012", "Exposed wiring near administrative block", "A cable cover is broken close to a pedestrian path.", "Electricity", "Vidyut Vibhag", PRIORITY_URGENT, STATUS_ESCALATED, 10, None, None),
    ("90013", "Cracked pathway near meditation hall", "The uneven paving is causing students to trip during rain.", "Building", "Nirman Vibhag", PRIORITY_MEDIUM, STATUS_ASSIGNED, 6, None, None),
    ("90014", "Printer queue fails in computer laboratory", "The shared printer is showing an offline error for every user.", "Computer/Lab", "MCA Lab / Computer Lab", PRIORITY_LOW, STATUS_ASSIGNED, 3, None, None),
    ("90015", "Leaking drinking-water cooler near library", "Water is pooling below the cooler and needs attention.", "Water", "Jal Kal Vibhag", PRIORITY_MEDIUM, STATUS_SUBMITTED, 1, None, None),
]


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


def _demo_timeline(complaint_id: str, submitted_at: str, officer: dict, status: str, resolved_at: str = None) -> list:
    """A compact, frontend-compatible history for a demo complaint."""
    stages = [
        ("submitted", "Complaint Submitted", "Grievance registered on the portal."),
        ("classified", "AI Classified", "Department and priority were predicted automatically."),
        ("department", "Assigned to Department", "Routed to the responsible department."),
        ("officer", "Officer Assigned", "A department officer took ownership."),
    ]
    timeline = [
        {
            "id": f"{complaint_id}-{key}", "key": key, "label": label,
            "description": description,
            "actor": "AI Classification Engine" if key == "classified" else (officer["name"] if key == "officer" else "Grievance Redressal Cell"),
            "at": submitted_at, "state": "done",
        }
        for key, label, description in stages
    ]
    if status in {STATUS_IN_PROGRESS, STATUS_PENDING, STATUS_RESOLVED, STATUS_CLOSED}:
        timeline.append({
            "id": f"{complaint_id}-started", "key": "started", "label": "Work Started",
            "description": "The department started work on this issue.", "actor": officer["name"],
            "at": submitted_at, "state": "done",
        })
    if resolved_at:
        timeline.extend([
            {"id": f"{complaint_id}-resolution", "key": "resolution", "label": "Resolution Submitted",
             "description": "The officer submitted the completion report.", "actor": officer["name"], "at": resolved_at, "state": "done"},
            {"id": f"{complaint_id}-resolved", "key": "resolved", "label": "Resolved",
             "description": "The complaint was resolved and feedback was requested.", "actor": "Grievance Redressal Cell", "at": resolved_at, "state": "done"},
        ])
    return timeline


def seed_demo_data() -> int:
    """Insert an idempotent, representative complaint dataset for local demos.

    It covers every department, all priorities and a mix of active, resolved,
    closed and escalated work so the dashboards, lists and analytics charts all
    have meaningful values.  A fixed `isDemoFixture` marker makes the records
    easy to identify without changing how the application reads complaints.
    """
    students = list(users_collection().find({"role": ROLE_STUDENT}, {"_id": 0}))
    officers = list(users_collection().find({"role": ROLE_OFFICER}, {"_id": 0}))
    officer_by_department = {officer["department"]: officer for officer in officers}
    if not students or len(officer_by_department) != len(DEPARTMENTS):
        raise RuntimeError("Demo users and officers must be seeded before demo complaints.")

    created = 0
    now = utcnow()
    for index, (sequence, title, description, category, department, priority, status, age_days, resolution_days, rating) in enumerate(DEMO_COMPLAINTS):
        complaint_id = f"DSVV-GRV-{now.year}-{sequence}"
        if complaints_collection().find_one({"id": complaint_id}):
            continue

        student = students[index % len(students)]
        officer = officer_by_department[department]
        submitted_time = now - timedelta(days=age_days, hours=index % 6)
        submitted_at = iso(submitted_time)
        resolved_at = iso(submitted_time + timedelta(days=resolution_days)) if resolution_days else None
        deadline = calculate_deadline(submitted_at, priority)
        # Make the escalation view visibly useful rather than merely having an
        # escalated status whose deadline is still in the future.
        if status == STATUS_ESCALATED:
            deadline = iso(now - timedelta(days=4))

        feedback = None
        if rating:
            feedback = {
                "rating": rating,
                "comment": "The update was clear and the issue was handled promptly.",
                "satisfied": rating >= 4,
                "at": resolved_at,
            }

        complaint = {
            "id": complaint_id,
            "isDemoFixture": True,
            "title": title,
            "description": description,
            "category": category,
            "department": department,
            "priority": priority,
            "status": status,
            "submittedBy": {
                "id": student["id"], "name": student["name"], "userId": student.get("userId", ""),
                "email": student["email"], "userType": student.get("userType", "Student"),
                "hostel": student.get("hostel", "—"),
            },
            "assignedOfficer": {"id": officer["id"], "name": officer["name"], "department": department},
            "location": {"latitude": 29.99965 + index * 0.00008, "longitude": 78.1946 + index * 0.00006, "address": "DSVV Campus", "block": "Campus"},
            "evidence": [],
            "ai": {"department": department, "priority": priority, "modelTrained": False},
            "submittedAt": submitted_at,
            "updatedAt": resolved_at or submitted_at,
            "deadline": deadline,
            "resolvedAt": resolved_at,
            "escalationLevel": 2 if status == STATUS_ESCALATED else 0,
            "escalationAuthority": "Department Head" if status == STATUS_ESCALATED else None,
            "daysOverdue": 4 if status == STATUS_ESCALATED else 0,
            "remarks": [],
            "resolution": {"notes": "Work completed and the area was checked.", "at": resolved_at, "officer": officer["name"]} if resolved_at else None,
            "feedback": feedback,
            "timeline": _demo_timeline(complaint_id, submitted_at, officer, status, resolved_at),
        }
        complaints_collection().insert_one(complaint)
        assignments_collection().update_one(
            {"complaintId": complaint_id, "officerId": officer["id"]},
            {"$setOnInsert": {"complaintId": complaint_id, "officerId": officer["id"], "officerName": officer["name"], "at": submitted_at, "reason": "Demo data assignment."}},
            upsert=True,
        )
        if feedback:
            feedback_collection().update_one(
                {"complaintId": complaint_id},
                {"$setOnInsert": {"id": f"FB-{sequence}", "complaintId": complaint_id, "complaintTitle": title, "department": department, "officer": officer["name"], "student": student["name"], "studentId": student["id"], **feedback}},
                upsert=True,
            )
        created += 1
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


def run(verbose: bool = True, include_demo_data: bool = False) -> dict:
    """Seed everything. Safe to call on every application start."""
    result = {"departments": seed_departments(), "users": seed_users(), "demoComplaints": 0}
    if include_demo_data:
        result["demoComplaints"] = seed_demo_data()
    _sync_counters()

    if verbose and (result["departments"] or result["users"] or result["demoComplaints"]):
        logger.info(
            "Seeded %s department(s), %s user account(s) and %s demo complaint(s).",
            result["departments"], result["users"], result["demoComplaints"],
        )
    return result


if __name__ == "__main__":
    # Allow `python seed.py` as a standalone command.
    import argparse
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
    parser = argparse.ArgumentParser(description="Seed local database records.")
    parser.add_argument("--demo-data", action="store_true", help="also add representative complaints and feedback for UI demos")
    args = parser.parse_args()

    outcome = run(include_demo_data=args.demo_data)
    print(f"Seeded {outcome['departments']} department(s), {outcome['users']} user account(s) and {outcome['demoComplaints']} demo complaint(s).")
