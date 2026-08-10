from bson import ObjectId
from pymongo.database import Database

from app.utils.logger import get_logger

logger = get_logger(__name__)


def resolve_destinations(db: Database, account_id: str, category: str) -> list[dict]:
    """
    Finds matching Destinations for an email based on routing rules:
    - Match rules where rule.account_id == account_id AND rule.category == category
    - Match rules where rule.account_id == account_id AND rule.category is NULL
    - Match rules where rule.account_id is NULL AND rule.category == category
    - Fallback: Any active rule where account_id is NULL and category is NULL.
    - Fallback: The system default destination.
    """
    # 1. Specific rule (account + category)
    rules = list(db.routing_rules.find({
        "account_id": account_id,
        "category": category,
        "active": True
    }))

    # 2. Account-only rule
    if not rules:
        rules = list(db.routing_rules.find({
            "account_id": account_id,
            "category": {"$in": [None, ""]},
            "active": True
        }))

    # 3. Category-only rule
    if not rules:
        rules = list(db.routing_rules.find({
            "account_id": {"$in": [None, ""]},
            "category": category,
            "active": True
        }))

    # 4. Global fallback rules (no account, no category)
    if not rules:
        rules = list(db.routing_rules.find({
            "account_id": {"$in": [None, ""]},
            "category": {"$in": [None, ""]},
            "active": True
        }))

    destinations = []
    seen_dest_ids = set()

    for r in rules:
        dest_id = r.get("destination_id")
        if dest_id and dest_id not in seen_dest_ids:
            dest = db.destinations.find_one({"_id": ObjectId(dest_id), "active": True})
            if dest:
                destinations.append(dest)
                seen_dest_ids.add(dest_id)

    # 5. Last resort: Default destination
    if not destinations:
        default_dest = db.destinations.find_one({"is_default": True, "active": True})
        if default_dest:
            destinations.append(default_dest)

    return destinations
