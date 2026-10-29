"""
Pytest fixtures and configuration for Gmail Reminder Test Suite.
"""
import os
import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Ensure environment variables for testing
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SECRET_KEY"] = "test-secret-key-for-unit-testing"
os.environ["API_KEY"] = "test-api-key-12345"
os.environ["DRY_RUN"] = "true"
os.environ["LOG_LEVEL"] = "ERROR"

from app.config import settings
settings.database_url = "sqlite:///:memory:"
settings.api_key = "test-api-key-12345"
settings.dry_run = True

from app.database.session import Base
import app.database.session as session_module
import app.database.db as db_module

from sqlalchemy.pool import StaticPool

# Test in-memory engine and session
test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

# Patch session module
session_module.engine = test_engine
session_module.SessionLocal = TestSessionLocal
db_module.SessionLocal = TestSessionLocal

from app.main import app
from app.database.db import get_db, init_db


@pytest.fixture(autouse=True)
def setup_test_db():
    """Create fresh in-memory database tables for every test."""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def client():
    """FastAPI TestClient with in-memory database."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def auth_headers():
    return {"X-API-Key": "test-api-key-12345"}


@pytest.fixture
def sample_raw_email():
    return {
        "gmail_message_id": "msg_test_001",
        "gmail_id": "msg_test_001",
        "gmail_thread_id": "thread_test_001",
        "sender": "professor.smith@university.edu",
        "recipients": "student@university.edu",
        "subject": "CS101 Assignment 2 Deadline",
        "received_at": datetime.now(timezone.utc),
        "plain_text": "Please note the submission deadline for Assignment 2 is 15 Nov 2026 at 11:59 PM. Late submissions will not be accepted.",
        "html": "<p>Please note the submission deadline for Assignment 2 is <strong>15 Nov 2026 at 11:59 PM</strong>.</p>",
        "attachments": [
            {"filename": "assignment2.pdf", "mime_type": "application/pdf", "size": 102400}
        ],
        "labels": ["INBOX", "UNREAD"],
    }
