"""
Integrations and Notification Settings API Endpoints.
Handles Gmail OAuth per user, WhatsApp and Telegram notification destinations,
test message dispatching, and user notification preferences.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.database.db import get_db_session
from app.middleware.auth import get_current_user, verify_resource_ownership
from app.models.db_models import (
    GmailConnectionModel,
    NotificationIntegrationModel,
    NotificationPreferencesModel,
    UserModel,
)
from app.services.auth_service import log_audit_event
from app.services.gmail_service import build_auth_url, exchange_code_for_token
from app.services.notifier import send_to_channel
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


class NotificationPreferencesResponse(BaseModel):
    notification_mode: str
    digest_interval_minutes: int
    privacy_mode: bool
    notification_cutoff_hours: int
    reminder_offsets_min: str
    included_categories: str

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
    return connections


@router.get("/gmail/auth-url")
def get_gmail_auth_url(
    current_user: UserModel = Depends(get_current_user),
):
    """Generate Google OAuth 2.0 authorization URL for this user."""
    auth_url, _state = build_auth_url(state=f"user_{current_user.id}")
    return {"auth_url": auth_url}


@router.get("/gmail/callback")
def handle_gmail_callback(
    code: str = Query(...),
    state: Optional[str] = Query(None),
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Handle OAuth redirect callback and persist user's Gmail connection."""
    try:
        user_email, token_path = exchange_code_for_token(code)

        # Upsert connection
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
    except Exception as exc:
        logger.error("Gmail OAuth callback failed for user %s: %s", current_user.id, exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to connect Gmail account: {str(exc)}",
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

    # Safely delete token file
    if conn.token_path and os.path.exists(conn.token_path):
        try:
            os.remove(conn.token_path)
        except OSError:
            pass

    db.delete(conn)
    log_audit_event(
        db,
        event_type="gmail_disconnected",
        user_id=current_user.id,
        details={"email": conn.email},
    )
    db.commit()
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

    test_text = (
        f"🔔 *Gmail-to-Chat Alert Test*\n\n"
        f"Hi {current_user.full_name or current_user.email}!\n"
        f"Your {integration.type.capitalize()} notification channel is properly configured and verified."
    )

    try:
        success, err = send_to_channel(
            channel=integration.type,
            target_id=integration.target_id,
            message=test_text,
        )
        if not success:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to deliver test message to {integration.type}: {err}",
            )
        return {"message": f"Test message dispatched successfully to {integration.name}."}
    except Exception as exc:
        logger.error("Test notification failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Test notification failed: {str(exc)}",
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

    db.commit()
    db.refresh(prefs)
    return prefs
