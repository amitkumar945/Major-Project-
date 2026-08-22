"""
Shared pytest fixtures.

Every test runs against a separate database (`grievance_management_test`),
which is dropped and re-seeded for each test, so tests never interfere with the
development data or with each other.
"""

import os
import sys
from pathlib import Path

import pytest

# Make the backend package importable and select the test configuration before
# anything reads it.
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))
os.environ["APP_CONFIG"] = "test"
os.environ.setdefault("JWT_SECRET_KEY", "test-only-secret-not-for-production")


@pytest.fixture(scope="session")
def app():
    from app import create_app
    from config import TestConfig

    application = create_app(TestConfig)
    application.config["TESTING"] = True
    yield application

    # Tear the whole test database down at the end of the session.
    from database import get_client, get_db

    get_client().drop_database(get_db().name)


@pytest.fixture(autouse=True)
def clean_database(app):
    """Empty every collection and re-seed before each test."""
    from database import get_db
    import seed
    from utils import rate_limit

    database = get_db()
    for name in database.list_collection_names():
        database[name].delete_many({})

    with app.app_context():
        seed.run(verbose=False)

    rate_limit.reset()  # a previous test must not exhaust another's quota
    yield


@pytest.fixture
def client(app):
    return app.test_client()


# ------------------------------------------------------------------ helpers


def _token(client, email, password):
    response = client.post("/api/auth/login", json={"identifier": email, "password": password})
    assert response.status_code == 200, response.get_json()
    return response.get_json()["data"]["token"]


@pytest.fixture
def student_token(client):
    return _token(client, "student@dsvv.ac.in", "student123")


@pytest.fixture
def officer_token(client):
    """The Jal Kal Vibhag officer - water complaints route to them."""
    return _token(client, "pankaj.semwal@dsvv.ac.in", "officer123")


@pytest.fixture
def admin_token(client):
    return _token(client, "admin@dsvv.ac.in", "admin123")


@pytest.fixture
def auth():
    """Build an Authorization header: `auth(token)`."""
    return lambda token: {"Authorization": f"Bearer {token}"}


@pytest.fixture
def water_complaint():
    """A complaint that classifies to Jal Kal Vibhag with High priority."""
    return {
        "title": "Water leakage near Gayatri Bhavan hostel entrance",
        "description": (
            "A pipeline joint near the main entrance of Gayatri Bhavan has been "
            "leaking continuously for two days. Water has collected on the walkway "
            "and students are slipping while entering the hostel."
        ),
        "category": "Water",
        "location": {
            "latitude": 29.9457,
            "longitude": 78.1642,
            "address": "Gayatri Bhavan main entrance",
        },
    }


@pytest.fixture
def make_complaint(client, auth, student_token, water_complaint):
    """Create a complaint and return its document."""

    def _make(overrides=None):
        payload = {**water_complaint, **(overrides or {})}
        response = client.post("/api/complaints", json=payload, headers=auth(student_token))
        assert response.status_code == 201, response.get_json()
        return response.get_json()["data"]

    return _make
