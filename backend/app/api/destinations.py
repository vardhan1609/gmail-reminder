from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pymongo.database import Database

from app.database.db import get_db
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["Destinations & Routing"])


# ══════════════════════════════════════════════
#  Destinations (WhatsApp / Telegram Group targets)
# ══════════════════════════════════════════════

@router.get("/destinations")
def list_destinations(db: Database = Depends(get_db)):
    destinations = list(db.destinations.find())
    for d in destinations:
        d["id"] = str(d.pop("_id"))
    return destinations


@router.post("/destinations")
def create_destination(payload: dict, db: Database = Depends(get_db)):
    # Simple validation
    if not payload.get("type") or not payload.get("name") or not payload.get("target_id"):
        raise HTTPException(status_code=400, detail="Missing required destination fields")

    # If this is marked as default, clear others
    if payload.get("is_default"):
        db.destinations.update_many({}, {"$set": {"is_default": False}})

    db.destinations.insert_one(payload)
    return {"status": "created"}


@router.delete("/destinations/{destination_id}")
def delete_destination(destination_id: str, db: Database = Depends(get_db)):
    if not ObjectId.is_valid(destination_id):
        raise HTTPException(status_code=400, detail="Invalid destination ID format")

    res = db.destinations.delete_one({"_id": ObjectId(destination_id)})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Destination not found")

    # Cascade delete routing rules linked to this destination
    db.routing_rules.delete_many({"destination_id": destination_id})
    return {"status": "deleted"}


# ══════════════════════════════════════════════
#  Routing Rules
# ══════════════════════════════════════════════

@router.get("/routing-rules")
def list_routing_rules(db: Database = Depends(get_db)):
    rules = list(db.routing_rules.find())
    for r in rules:
        r["id"] = str(r.pop("_id"))
    return rules


@router.post("/routing-rules")
def create_routing_rule(payload: dict, db: Database = Depends(get_db)):
    dest_id = payload.get("destination_id")
    if not dest_id:
        raise HTTPException(status_code=400, detail="Missing destination_id")

    # Verify destination exists
    if not ObjectId.is_valid(dest_id) or not db.destinations.find_one({"_id": ObjectId(dest_id)}):
        raise HTTPException(status_code=400, detail="Linked destination does not exist")

    db.routing_rules.insert_one(payload)
    return {"status": "created"}


@router.delete("/routing-rules/{rule_id}")
def delete_routing_rule(rule_id: str, db: Database = Depends(get_db)):
    if not ObjectId.is_valid(rule_id):
        raise HTTPException(status_code=400, detail="Invalid rule ID format")

    res = db.routing_rules.delete_one({"_id": ObjectId(rule_id)})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Routing rule not found")

    return {"status": "deleted"}
