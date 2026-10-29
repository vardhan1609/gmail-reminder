"""
Google OAuth 2.0 authentication endpoints.
"""
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.database.db import get_db, get_db_session
from app.models.db_models import GmailConnectionModel, UserModel
from app.services.auth_service import validate_session
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
def google_callback(
    request: Request,
    code: str = Query(...),
    state: Optional[str] = Query(None),
    db=Depends(get_db),
    sql_session: Session = Depends(get_db_session),
):
    """Handles OAuth callback and persists encrypted token for both legacy and multi-user systems."""
    try:
        email, token_path = exchange_code_for_token(code)
    except Exception as exc:
        logger.error("OAuth code exchange failed: %s", exc)
        raise HTTPException(status_code=400, detail=f"OAuth exchange failed: {exc}")

    now = datetime.now(timezone.utc)

    # 1. Resolve user ID if available
    user_id = None
    if state and state.startswith("user_"):
        user_id = state[5:].strip()
    
    if not user_id:
        # Check session cookie from request
        raw_token = request.cookies.get(settings.session_cookie_name)
        if raw_token:
            sess = validate_session(sql_session, raw_token)
            if sess:
                user_id = sess[1].id

    if not user_id:
        # Try matching by user email
        matched_user = sql_session.query(UserModel).filter(UserModel.email == email.lower().strip()).first()
        if matched_user:
            user_id = matched_user.id
        else:
            # Fallback to single registered user if exists
            all_users = sql_session.query(UserModel).all()
            if len(all_users) == 1:
                user_id = all_users[0].id

    # 2. Persist in multi-user GmailConnectionModel
    if user_id:
        conn = (
            sql_session.query(GmailConnectionModel)
            .filter(
                GmailConnectionModel.user_id == user_id,
                GmailConnectionModel.email == email,
            )
            .first()
        )
        if not conn:
            conn = GmailConnectionModel(
                user_id=user_id,
                email=email,
                label="Primary Gmail",
                token_path=token_path,
                active=True,
                calendar_sync_enabled=True,
                created_at=now,
                updated_at=now,
            )
            sql_session.add(conn)
        else:
            conn.token_path = token_path
            conn.active = True
            conn.updated_at = now
        sql_session.commit()

    # 3. Upsert legacy account in DB
    existing = db.accounts.find_one({"email": email})
    if existing:
        db.accounts.update_one(
            {"email": email},
            {"$set": {
                "token_path": token_path,
                "active": True,
                "user_id": user_id,
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
            "user_id": user_id,
        })

    logger.info("Successfully connected Google account: %s (user: %s)", email, user_id)
    
    # Redirect to Next.js frontend if available, else fallback to local dashboard
    frontend_redirect = f"{settings.frontend_base_url}/dashboard/integrations?auth=success"
    return RedirectResponse(url=frontend_redirect)

