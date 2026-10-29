"""
Sync API endpoints (v1).
"""
from typing import Optional
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel

from app.database.db import get_db
from app.middleware.auth import require_api_key
from app.services.scheduler import _poll_all_accounts

router = APIRouter(prefix="/sync", tags=["Sync V1"])


class SyncResponse(BaseModel):
    status: str
    message: str


@router.post("", response_model=SyncResponse, dependencies=[Depends(require_api_key)])
def request_sync(background_tasks: BackgroundTasks, db=Depends(get_db)):
    """Request on-demand email synchronization across connected accounts."""
    active_accounts = list(db.accounts.find({"active": True}))
    if not active_accounts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active Gmail accounts connected. Please authenticate an account first.",
        )

    # Dispatch sync in background task
    background_tasks.add_task(_poll_all_accounts, db)
    return SyncResponse(
        status="triggered",
        message=f"Email synchronization scheduled for {len(active_accounts)} active account(s).",
    )

