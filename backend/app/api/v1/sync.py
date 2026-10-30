"""Authenticated, user-scoped on-demand Gmail synchronization."""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel
from app.database.db import get_db
from app.middleware.auth import get_current_user
from app.models.db_models import UserModel
from app.services.scheduler import _poll_all_accounts
router = APIRouter(prefix="/sync", tags=["Sync V1"])

class SyncResponse(BaseModel):
    status: str
    message: str

@router.post("", response_model=SyncResponse)
def request_sync(background_tasks: BackgroundTasks, current_user: UserModel = Depends(get_current_user), db=Depends(get_db)):
    """Queue a sync for the current user's connected Gmail accounts only."""
    active_connections = list(db.gmail_connections.find({"user_id": current_user.id, "active": True}))
    if not active_connections:
        legacy_accounts = list(db.accounts.find({"active": True}))
        active_connections = [
            account for account in legacy_accounts
            if account.get("user_id") == current_user.id
            or (
                not account.get("user_id")
                and account.get("email", "").lower() == current_user.email.lower()
            )
        ]
    if not active_connections:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No active Gmail accounts connected. Connect a Gmail account first.")
    background_tasks.add_task(_poll_all_accounts, db, current_user.id, current_user.email)
    return SyncResponse(status="triggered", message=f"Email synchronization scheduled for {len(active_connections)} account(s).")
