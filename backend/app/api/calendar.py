from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from pymongo.database import Database

from app.database.db import get_db
from app.services.outlook_calendar import build_auth_url as build_outlook_auth_url, complete_auth as complete_outlook_auth
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/calendar", tags=["Calendar Integration"])


@router.get("/outlook/login")
def outlook_login():
    """Start Microsoft Graph/Outlook OAuth flow."""
    auth_url = build_outlook_auth_url()
    return RedirectResponse(auth_url)


@router.get("/outlook/callback")
def outlook_callback(request: Request):
    """Callback target for Microsoft Graph authentication."""
    try:
        # Convert Request query params to a standard dict
        query_params = dict(request.query_params)
        email = complete_outlook_auth(query_params)
        logger.info("Outlook calendar connected successfully for account: %s", email)
    except Exception as exc:
        logger.error("Outlook OAuth callback processing failed: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc))

    return RedirectResponse("/dashboard")


@router.get("/sync-status")
def get_sync_status(db: Database = Depends(get_db)):
    """List calendar sync statuses for all processed deadlines."""
    events = list(db.calendar_events.find())
    for e in events:
        e["id"] = str(e.pop("_id"))
    return events
