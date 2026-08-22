"""
MongoDB connection and collection handles.

A single `MongoClient` is created per process and shared by every service.
`init_db()` is called once from the application factory; after that any module
can call `get_db()` or the `collection` helpers.
"""

from urllib.parse import urlparse

from pymongo import ASCENDING, DESCENDING, MongoClient, TEXT

_client: MongoClient = None
_db = None

# Every collection the system uses.
COLLECTIONS = (
    "users",
    "complaints",
    "departments",
    "officers",
    "assignments",
    "notifications",
    "feedback",
    "audit_logs",
    "otps",
    "counters",
)


def _database_name(uri: str, override: str = "") -> str:
    """Pull the database name out of the URI unless one was set explicitly."""
    if override:
        return override
    path = urlparse(uri).path.lstrip("/")
    return path or "grievance_management"


def init_db(config) -> "Database":
    """Connect to MongoDB, verify the connection and create the indexes."""
    global _client, _db

    _client = MongoClient(
        config.MONGO_URI,
        serverSelectionTimeoutMS=5000,
        tz_aware=False,
    )
    # Fail fast and loudly rather than at the first query.
    _client.admin.command("ping")

    _db = _client[_database_name(config.MONGO_URI, config.MONGO_DB_NAME)]
    _create_indexes(_db)
    return _db


def _create_indexes(db) -> None:
    """Indexes that back the queries the frontend actually makes."""
    db.users.create_index([("email", ASCENDING)], unique=True)
    db.users.create_index([("role", ASCENDING)])
    db.users.create_index([("id", ASCENDING)], unique=True)
    db.users.create_index([("department", ASCENDING)])

    db.complaints.create_index([("id", ASCENDING)], unique=True)
    db.complaints.create_index([("submittedBy.id", ASCENDING)])
    db.complaints.create_index([("assignedOfficer.id", ASCENDING)])
    db.complaints.create_index([("status", ASCENDING)])
    db.complaints.create_index([("department", ASCENDING)])
    db.complaints.create_index([("priority", ASCENDING)])
    db.complaints.create_index([("submittedAt", DESCENDING)])
    db.complaints.create_index([("deadline", ASCENDING)])
    # Powers the free-text `search` filter on the complaint tables.
    db.complaints.create_index(
        [("title", TEXT), ("description", TEXT)], name="complaint_text"
    )

    db.departments.create_index([("code", ASCENDING)], unique=True)
    db.departments.create_index([("name", ASCENDING)])

    db.notifications.create_index([("recipientId", ASCENDING), ("createdAt", DESCENDING)])
    db.notifications.create_index([("id", ASCENDING)], unique=True)
    db.notifications.create_index([("read", ASCENDING)])

    db.feedback.create_index([("complaintId", ASCENDING)], unique=True)
    db.feedback.create_index([("at", DESCENDING)])

    db.assignments.create_index([("complaintId", ASCENDING)])
    db.assignments.create_index([("officerId", ASCENDING)])
    db.assignments.create_index([("at", DESCENDING)])

    db.audit_logs.create_index([("at", DESCENDING)])
    db.audit_logs.create_index([("userId", ASCENDING)])
    db.audit_logs.create_index([("complaintId", ASCENDING)])
    db.audit_logs.create_index([("action", ASCENDING)])

    # OTPs expire on their own - Mongo removes the document at `expiresAt`.
    db.otps.create_index([("expiresAt", ASCENDING)], expireAfterSeconds=0)
    db.otps.create_index([("email", ASCENDING), ("purpose", ASCENDING)])


def get_db():
    if _db is None:
        raise RuntimeError("Database is not initialised. Call init_db() first.")
    return _db


def get_client() -> MongoClient:
    return _client


def close_db() -> None:
    global _client, _db
    if _client is not None:
        _client.close()
    _client, _db = None, None


# ------------------------------------------------------- collection helpers


def users():
    return get_db().users


def complaints():
    return get_db().complaints


def departments():
    return get_db().departments


def officers():
    """Officer profiles live in `users` (role='officer'); this collection keeps
    the department/workload records the admin officer screen manages."""
    return get_db().officers


def assignments():
    return get_db().assignments


def notifications():
    return get_db().notifications


def feedback():
    return get_db().feedback


def audit_logs():
    return get_db().audit_logs


def otps():
    return get_db().otps


def counters():
    return get_db().counters


def next_sequence(name: str) -> int:
    """Atomic counter used to build gap-free complaint reference numbers."""
    doc = counters().find_one_and_update(
        {"_id": name},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=True,
    )
    return int(doc["seq"])
