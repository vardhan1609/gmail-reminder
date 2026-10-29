"""
Google OAuth 2.0 authentication endpoints.
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse

from app.database.db import get_db
from app.services.gmail_service import build_auth_url, exchange_code_for_token
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/auth/google", tags=["Authentication"])


@router.get("/login")
def google_login():
    """Initiates Google OAuth 2.0 flow and redirects to consent screen."""
    try:
        auth_url, _state = build_auth_url()
        return RedirectResponse(auth_url)
    except Exception as exc:
        logger.error("Failed to generate Google auth URL: %s", exc)
        raise HTTPException(status_code=500, detail="Could not initiate Google OAuth flow")


@router.get("/callback")
def google_callback(code: str = Query(...), db=Depends(get_db)):
    """Handles OAuth callback and persists encrypted token."""
    try:
        email, token_path = exchange_code_for_token(code)
    except Exception as exc:
        logger.error("OAuth code exchange failed: %s", exc)
        raise HTTPException(status_code=400, detail=f"OAuth exchange failed: {exc}")

    # Upsert account in DB
    existing = db.accounts.find_one({"email": email})
    now = datetime.now(timezone.utc)
    if existing:
        db.accounts.update_one(
            {"email": email},
            {"$set": {
                "token_path": token_path,
                "active": True,
            }}
        )
    else:
        db.accounts.insert_one({
            "email": email,
            "label": "Primary Mailbox",
            "token_path": token_path,
            "active": True,
            "calendar_sync_enabled": False,
            "created_at": now,
        })

    logger.info("Successfully connected Google account: %s", email)
    return RedirectResponse(url="/dashboard?auth=success")

