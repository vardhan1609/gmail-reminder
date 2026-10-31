from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.integrations import router as integrations_router
from app.api.v1.emails import router as emails_router
from app.api.v1.reminders import router as reminders_router
from app.api.v1.notifications import router as notifications_router
from app.api.v1.sync import router as sync_router
from app.api.v1.config import router as config_router
from app.api.v1.billing import router as billing_router
from app.websocket import ws_router

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(auth_router)
api_v1_router.include_router(integrations_router)
api_v1_router.include_router(sync_router)
api_v1_router.include_router(emails_router)
api_v1_router.include_router(reminders_router)
api_v1_router.include_router(notifications_router)
api_v1_router.include_router(config_router)
api_v1_router.include_router(billing_router)
api_v1_router.include_router(ws_router)

__all__ = ["api_v1_router"]

