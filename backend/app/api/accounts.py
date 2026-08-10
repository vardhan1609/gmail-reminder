from datetime import datetime
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from pymongo.database import Database

from app.database.db import get_db
from app.services.gmail_service import build_auth_url, exchange_code_for_token
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/accounts", tags=["Accounts"])


@router.get("")
def list_accounts(db: Database = Depends(get_db)):
    """List all connected accounts."""
    accounts = list(db.accounts.find())
    for a in accounts:
        a["id"] = str(a.pop("_id"))
        # Check token file existence for authentication status
        import os
        a["authenticated"] = os.path.exists(a.get("token_path", ""))
    return accounts


@router.get("/gmail/login")
def gmail_login():
    """Start OAuth flow."""
    auth_url = build_auth_url()
    return RedirectResponse(auth_url)


@router.get("/gmail/callback")
def gmail_callback(code: str, db: Database = Depends(get_db)):
    """Callback target for Google OAuth redirection."""
    try:
        email, token_path = exchange_code_for_token(code)
    except Exception as exc:
        logger.error("OAuth callback processing failed: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc))

    # Save to MongoDB
    db.accounts.update_one(
        {"email": email},
        {
            "$set": {
                "token_path": token_path,
                "active": True,
            },
            "$setOnInsert": {
                "created_at": datetime.utcnow() if "datetime" in globals() else None
            }
        },
        upsert=True
    )
    return RedirectResponse("/dashboard")


@router.patch("/{account_id}")
def update_account(
    account_id: str,
    active: bool = Query(None),
    calendar_sync_enabled: bool = Query(None),
    label: str = Query(None),
    db: Database = Depends(get_db)
):
    """Modify account attributes."""
    if not ObjectId.is_valid(account_id):
        raise HTTPException(status_code=400, detail="Invalid account ID format")

    update_fields = {}
    if active is not None:
        update_fields["active"] = active
    if calendar_sync_enabled is not None:
        update_fields["calendar_sync_enabled"] = calendar_sync_enabled
    if label is not None:
        update_fields["label"] = label

    if not update_fields:
        raise HTTPException(status_code=400, detail="No fields provided for update")

    res = db.accounts.update_one(
        {"_id": ObjectId(account_id)},
        {"$set": update_fields}
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Account not found")

    return {"status": "updated"}


@router.delete("/{account_id}")
def delete_account(account_id: str, db: Database = Depends(get_db)):
    """Delete an account connection."""
    if not ObjectId.is_valid(account_id):
        raise HTTPException(status_code=400, detail="Invalid account ID format")

    # Clean up token file if exists
    account = db.accounts.find_one({"_id": ObjectId(account_id)})
    if account and account.get("token_path"):
        import os
        if os.path.exists(account["token_path"]):
            try:
                os.remove(account["token_path"])
            except Exception as exc:
                logger.warning("Failed to remove token file %s: %s", account["token_path"], exc)

    res = db.accounts.delete_one({"_id": ObjectId(account_id)})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Account not found")

    return {"status": "deleted"}
