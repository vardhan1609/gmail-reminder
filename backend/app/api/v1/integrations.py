"""
Integrations and Notification Settings API Endpoints.
Handles Gmail OAuth per user, WhatsApp and Telegram notification destinations,
test message dispatching, and user notification preferences.
"""
from __future__ import annotations

import os
import hmac
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.database.db import get_db_session
from app.middleware.auth import get_current_user, verify_resource_ownership
from app.models.db_models import (
    AccountModel,
    GmailConnectionModel,
    NotificationIntegrationModel,
    NotificationPreferencesModel,
    SyncStateModel,
    UserModel,
)
from app.services.auth_service import log_audit_event
from app.services.gmail_service import build_auth_url, exchange_code_for_token
from app.services.notifier import send_to_channel, deliver_notification_idempotent
from app.services.billing import PLAN_CATALOG, get_active_subscription
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/integrations", tags=["Integrations & Preferences"])


# --- Schemas ---

class GmailConnectionResponse(BaseModel):
    id: str
    email: str
    label: Optional[str]
    active: bool
    history_id: Optional[str]
    last_sync_at: Optional[Any]
    last_sync_status: Optional[str]
    calendar_sync_enabled: bool
    created_at: Any

    class Config:
        from_attributes = True


class NotificationIntegrationCreate(BaseModel):
    type: str = Field(..., description="'telegram' or 'whatsapp'")
    name: str = Field(..., max_length=255)
    target_id: str = Field(..., description="Telegram Chat ID or WhatsApp Phone/JID")
    is_default: bool = True


class NotificationIntegrationResponse(BaseModel):
    id: str
    type: str
    name: str
    target_id: str
    is_default: bool
    is_active: bool
    created_at: Any

    class Config:
        from_attributes = True


class NotificationPreferencesUpdate(BaseModel):
    notification_mode: Optional[str] = Field(None, description="'immediate', 'summary', or 'important_only'")
    digest_interval_minutes: Optional[int] = Field(None, ge=5, le=1440)
    privacy_mode: Optional[bool] = None
    notification_cutoff_hours: Optional[int] = Field(None, ge=1, le=168)
    reminder_offsets_min: Optional[str] = None
    included_categories: Optional[str] = None
    theme_preference: Optional[str] = Field(None, description="'light', 'dark', or 'system'")


class NotificationPreferencesResponse(BaseModel):
    notification_mode: str
    digest_interval_minutes: int
    privacy_mode: bool
    notification_cutoff_hours: int
    reminder_offsets_min: str
    included_categories: str
    theme_preference: str = "system"

    class Config:
        from_attributes = True


# --- Gmail Connection Endpoints ---

@router.get("/gmail", response_model=List[GmailConnectionResponse])
def list_gmail_connections(
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """List connected Gmail accounts for the authenticated user."""
    connections = (
        db.query(GmailConnectionModel)
        .filter(GmailConnectionModel.user_id == current_user.id)
        .order_by(GmailConnectionModel.created_at.desc())
        .all()
    )
    # Do not auto-claim legacy records by email address. Legacy rows must be
    # migrated by an administrator after independent ownership verification.

    for c in connections:
        if not c.last_sync_at:
            st = db.query(SyncStateModel).filter(SyncStateModel.account_identifier == c.email).first()
            if st and st.last_successful_sync:
                c.last_sync_at = st.last_successful_sync
                c.last_sync_status = st.last_sync_status or "idle"

    return connections


@router.get("/gmail/auth-url")
def get_gmail_auth_url(
    response: Response,
    current_user: UserModel = Depends(get_current_user),
):
    """Generate a URL with a browser-bound, one-time CSRF state nonce."""
    oauth_state = secrets.token_urlsafe(32)
    response.set_cookie(
        key="gmail_oauth_state",
        value=oauth_state,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=600,
        path="/api/v1/integrations/gmail/callback",
    )
    auth_url, _ = build_auth_url(state=oauth_state)
    return {"auth_url": auth_url}


@router.get("/gmail/callback")
def handle_gmail_callback(
    request: Request,
    response: Response,
    code: str = Query(...),
    state: Optional[str] = Query(None),
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Handle OAuth redirect callback and persist user's Gmail connection."""
    expected_state = request.cookies.get("gmail_oauth_state", "")
    if not state or not expected_state or not hmac.compare_digest(state, expected_state):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OAuth state. Restart the Google connection flow.",
        )
    response.delete_cookie("gmail_oauth_state", path="/api/v1/integrations/gmail/callback")

    try:
        user_email, token_path = exchange_code_for_token(code)

        # Enforce the active plan's Gmail account allowance (reconnecting an existing account is allowed).
        conn = (
            db.query(GmailConnectionModel)
            .filter(
                GmailConnectionModel.user_id == current_user.id,
                GmailConnectionModel.email == user_email,
            )
            .first()
        )
        now = datetime.now(timezone.utc)
        if not conn:
            subscription = get_active_subscription(db, current_user.id)
            max_accounts = PLAN_CATALOG[subscription.plan_code]["gmail_accounts"]
            active_count = db.query(GmailConnectionModel).filter(
                GmailConnectionModel.user_id == current_user.id,
                GmailConnectionModel.active == True,
            ).count()
            if active_count >= max_accounts:
                try:
                    if token_path and os.path.exists(token_path):
                        os.remove(token_path)
                except OSError:
                    pass
                raise HTTPException(
                    status_code=403,
                    detail=f"{subscription.plan_code.title()} plan allows {max_accounts} connected Gmail account(s). Upgrade to add another mailbox.",
                )
            conn = GmailConnectionModel(
                user_id=current_user.id,
                email=user_email,
                label="Primary Gmail",
                token_path=token_path,
                active=True,
                calendar_sync_enabled=True,
                created_at=now,
                updated_at=now,
            )
            db.add(conn)
        else:
            conn.token_path = token_path
            conn.active = True
            conn.updated_at = now

        log_audit_event(
            db,
            event_type="gmail_connected",
            user_id=current_user.id,
            details={"email": user_email},
        )

        db.commit()
        db.refresh(conn)
        return {"message": f"Successfully connected {user_email}.", "connection_id": conn.id}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Gmail OAuth callback failed for user %s: %s", current_user.id, exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to connect Gmail account. Please restart the connection flow.",
        )


@router.delete("/gmail/{connection_id}")
def disconnect_gmail(
    connection_id: str,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Disconnect Gmail account, remove token, and deactivate connection."""
    conn = (
        db.query(GmailConnectionModel)
        .filter(
            GmailConnectionModel.id == connection_id,
            GmailConnectionModel.user_id == current_user.id,
        )
        .first()
    )
    if not conn:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gmail connection not found.",
        )

    # A repeated disconnect is safe: the authenticated user's resource is already absent.
    if not conn:
        return {"message": "Gmail account disconnected successfully."}

    token_path = conn.token_path
    connection_email = conn.email

    # Remove only this user's legacy row (or an unclaimed legacy row). Never
    # delete another tenant's account merely because it shares an email value.
    db.query(AccountModel).filter(
        (AccountModel.user_id == current_user.id)
        | (
            (AccountModel.user_id.is_(None))
            & (AccountModel.email == connection_email)
        )
    ).delete(synchronize_session=False)

    db.query(SyncStateModel).filter(
        SyncStateModel.account_identifier == connection_email
    ).delete(synchronize_session=False)

    db.delete(conn)
    log_audit_event(
        db,
        event_type="gmail_disconnected",
        user_id=current_user.id,
        details={"email": connection_email},
    )
    # Commit database cleanup before deleting the credential file. If the
    # transaction fails, the still-valid token remains available for retry.
    db.commit()

    if token_path and os.path.exists(token_path):
        try:
            os.remove(token_path)
        except OSError:
            logger.warning("Could not remove Gmail token file after disconnect for user %s", current_user.id)

    return {"message": "Gmail account disconnected successfully."}


# --- Notification Destination Endpoints ---

@router.get("/notifications", response_model=List[NotificationIntegrationResponse])
def list_notification_integrations(
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """List notification integrations for authenticated user."""
    integrations = (
        db.query(NotificationIntegrationModel)
        .filter(NotificationIntegrationModel.user_id == current_user.id)
        .order_by(NotificationIntegrationModel.created_at.desc())
        .all()
    )
    return integrations


@router.post("/notifications", response_model=NotificationIntegrationResponse, status_code=status.HTTP_201_CREATED)
def add_notification_integration(
    req: NotificationIntegrationCreate,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Add a new Telegram or WhatsApp delivery destination."""
    dest_type = req.type.lower().strip()
    if dest_type not in ("telegram", "whatsapp"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Integration type must be 'telegram' or 'whatsapp'.",
        )

    subscription = get_active_subscription(db, current_user.id)
    if dest_type in ("whatsapp", "whatsapp_meta") and not PLAN_CATALOG[subscription.plan_code]["whatsapp"]:
        raise HTTPException(status_code=403, detail="WhatsApp integration is available on the Premium plan. Upgrade to enable it.")

    now = datetime.now(timezone.utc)
    # If is_default is true, unmark existing defaults for that type
    if req.is_default:
        db.query(NotificationIntegrationModel).filter(
            NotificationIntegrationModel.user_id == current_user.id,
            NotificationIntegrationModel.type == dest_type,
        ).update({"is_default": False})

    integration = NotificationIntegrationModel(
        user_id=current_user.id,
        type=dest_type,
        name=req.name.strip(),
        target_id=req.target_id.strip(),
        is_default=req.is_default,
        is_active=True,
        created_at=now,
    )
    db.add(integration)
    log_audit_event(
        db,
        event_type="notification_integration_added",
        user_id=current_user.id,
        details={"type": dest_type, "name": req.name},
    )
    db.commit()
    db.refresh(integration)
    return integration


@router.delete("/notifications/{integration_id}")
def delete_notification_integration(
    integration_id: str,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Delete a notification integration."""
    integration = (
        db.query(NotificationIntegrationModel)
        .filter(
            NotificationIntegrationModel.id == integration_id,
            NotificationIntegrationModel.user_id == current_user.id,
        )
        .first()
    )
    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification integration not found.",
        )

    db.delete(integration)
    log_audit_event(
        db,
        event_type="notification_integration_deleted",
        user_id=current_user.id,
        details={"type": integration.type, "name": integration.name},
    )
    db.commit()
    return {"message": "Notification destination deleted."}


@router.post("/notifications/{integration_id}/test")
def test_notification_integration(
    integration_id: str,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Send a test message to verify Telegram or WhatsApp delivery."""
    integration = (
        db.query(NotificationIntegrationModel)
        .filter(
            NotificationIntegrationModel.id == integration_id,
            NotificationIntegrationModel.user_id == current_user.id,
        )
        .first()
    )
    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification integration not found.",
        )

    subscription = get_active_subscription(db, current_user.id)
    if integration.type in ("whatsapp", "whatsapp_meta") and not PLAN_CATALOG[subscription.plan_code]["whatsapp"]:
        raise HTTPException(status_code=403, detail="WhatsApp testing is available on the Premium plan.")

    test_text = (
        f"🔔 *Gmail-to-Chat Alert Test*\n\n"
        f"Hi {current_user.full_name or current_user.email}!\n"
        f"Your {integration.type.capitalize()} notification channel is properly configured and verified."
    )

    try:
        success, err = deliver_notification_idempotent(
            email_id=None,
            channel=integration.type,
            destination_id=integration.target_id,
            notification_type="test",
            message=test_text,
            idempotency_key=f"test_{integration.id}_{datetime.now(timezone.utc).timestamp()}",
            user_id=current_user.id,
        )
        if not success:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to deliver test message to {integration.type}: {err}",
            )
        return {"message": f"Test message dispatched successfully to {integration.name}."}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Test notification failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Test notification failed. Please retry later.",
        )


# --- Notification Preferences Endpoints ---

@router.get("/preferences", response_model=NotificationPreferencesResponse)
def get_notification_preferences(
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Get current user notification preferences."""
    prefs = (
        db.query(NotificationPreferencesModel)
        .filter(NotificationPreferencesModel.user_id == current_user.id)
        .first()
    )
    if not prefs:
        prefs = NotificationPreferencesModel(
            user_id=current_user.id,
            notification_mode="immediate",
            digest_interval_minutes=60,
            privacy_mode=False,
            notification_cutoff_hours=24,
            reminder_offsets_min="1440,360,60",
            included_categories="All",
        )
        db.add(prefs)
        db.commit()
        db.refresh(prefs)
    return prefs


@router.put("/preferences", response_model=NotificationPreferencesResponse)
def update_notification_preferences(
    req: NotificationPreferencesUpdate,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Update notification preferences for current user."""
    prefs = (
        db.query(NotificationPreferencesModel)
        .filter(NotificationPreferencesModel.user_id == current_user.id)
        .first()
    )
    if not prefs:
        prefs = NotificationPreferencesModel(user_id=current_user.id)
        db.add(prefs)

    if req.notification_mode is not None:
        if req.notification_mode not in ("immediate", "summary", "important_only"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid notification mode.",
            )
        prefs.notification_mode = req.notification_mode

    if req.digest_interval_minutes is not None:
        prefs.digest_interval_minutes = req.digest_interval_minutes

    if req.privacy_mode is not None:
        prefs.privacy_mode = req.privacy_mode

    if req.notification_cutoff_hours is not None:
        prefs.notification_cutoff_hours = req.notification_cutoff_hours

    if req.reminder_offsets_min is not None:
        prefs.reminder_offsets_min = req.reminder_offsets_min

    if req.included_categories is not None:
        prefs.included_categories = req.included_categories

    if req.theme_preference is not None:
        if req.theme_preference not in ("light", "dark", "system"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid theme preference. Must be 'light', 'dark', or 'system'.",
            )
        prefs.theme_preference = req.theme_preference

    db.commit()
    db.refresh(prefs)
    return prefs
