"""
MongoDB connection using pymongo. Provides a database handle via get_db()
and ensures indexes are created on startup via init_db().
"""
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.database import Database
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

_client: MongoClient | None = None
_db: Database | None = None


def _get_client() -> MongoClient:
    global _client
    if _client is None:
        _client = MongoClient(
            settings.mongo_uri,
            serverSelectionTimeoutMS=5000,  # 5s timeout instead of hanging forever
        )
    return _client


def get_db() -> Database:
    """FastAPI dependency (or direct call) — returns the MongoDB database handle."""
    global _db
    if _db is None:
        _db = _get_client()[settings.mongo_db]
    return _db


def init_db():
    """Create indexes on all collections. Safe to call repeatedly —
    pymongo's create_index is idempotent. Gracefully handles MongoDB
    being unavailable on startup."""
    db = get_db()
    logger.info("Initializing MongoDB indexes on database '%s'", settings.mongo_db)

    try:
        # Quick connectivity check
        _get_client().admin.command("ping")
    except (ConnectionFailure, ServerSelectionTimeoutError) as exc:
        logger.warning(
            "MongoDB is not reachable at %s — indexes will be created on first successful connection. Error: %s",
            settings.mongo_uri, exc,
        )
        return

    # accounts
    db.accounts.create_index("email", unique=True)

    # emails — dedup on (account_id, gmail_id)
    db.emails.create_index(
        [("account_id", ASCENDING), ("gmail_id", ASCENDING)],
        unique=True, name="uq_account_gmail_id",
    )
    db.emails.create_index("dedup_key")
    db.emails.create_index("account_id")
    db.emails.create_index("category")
    db.emails.create_index([("created_at", DESCENDING)])

    # destinations
    db.destinations.create_index("type")
    db.destinations.create_index([("created_at", DESCENDING)])

    # reminders
    db.reminders.create_index([("status", ASCENDING), ("reminder_time", ASCENDING)])
    db.reminders.create_index([("reminder_time", ASCENDING)])

    # routing_rules
    db.routing_rules.create_index("account_id")
    db.routing_rules.create_index("category")
    db.routing_rules.create_index("destination_id")
    db.routing_rules.create_index([("created_at", DESCENDING)])

    # calendar_events
    db.calendar_events.create_index([("email_id", ASCENDING), ("provider", ASCENDING)])

    logger.info("MongoDB indexes created/verified")


def close_db():
    """Cleanly close the MongoDB connection."""
    global _client, _db
    if _client:
        _client.close()
        _client = None
        _db = None
