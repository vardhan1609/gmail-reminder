"""
Health and readiness endpoints.
"""
from datetime import datetime, timezone
from pathlib import Path
from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.config import settings
from app.database.db import get_db
from app.models.reminder import ReminderStatus
from app.schemas.health import HealthResponse, ReadyResponse, ReadinessChecks, DestinationHealth
from app.services import notifier

router = APIRouter(tags=["Health & Readiness"])


@router.get("/health", response_model=HealthResponse)
def health_check():
    """Application health endpoint."""
    db = get_db()
    try:
        destinations = list(db.destinations.find({"active": True}))
        dest_status = []
        for d in destinations:
            dest_id = str(d.get("id") or d.get("_id"))
            dest_status.append(
                DestinationHealth(
                    id=dest_id,
                    name=d.get("name", "Unnamed"),
                    type=d.get("type", "unknown"),
                    ready=notifier.destination_is_ready(d),
                )
            )

        pending_count = db.reminders.count_documents({"status": ReminderStatus.pending.value})
        return HealthResponse(
            status="ok",
            time=datetime.now(timezone.utc),
            destinations=dest_status,
            pending_reminders=pending_count,
        )
    except Exception as exc:
        return HealthResponse(
            status="degraded",
            time=datetime.now(timezone.utc),
            destinations=[],
            pending_reminders=0,
        )


@router.get("/ready", response_model=ReadyResponse)
def readiness_check():
    """Dependency readiness probe."""
    db = get_db()
    # Check DB
    db_ok = False
    try:
        db.emails.count_documents({})
        db_ok = True
    except Exception:
        db_ok = False

    # Check Tokens Directory
    tokens_dir = Path(settings.resolved_tokens_dir)
    tokens_ok = tokens_dir.exists() and tokens_dir.is_dir()

    # Check Telegram
    tg_ok = notifier.destination_is_ready({"type": "telegram"})

    # Check WhatsApp
    wa_ok = notifier.destination_is_ready({"type": "whatsapp"})

    is_ready = db_ok and tokens_ok
    status_code = status.HTTP_200_OK if is_ready else status.HTTP_503_SERVICE_UNAVAILABLE

    checks = ReadinessChecks(
        database=db_ok,
        tokens_storage=tokens_ok,
        telegram=tg_ok,
        whatsapp=wa_ok,
    )

    content = ReadyResponse(
        ready=is_ready,
        checks=checks,
        timestamp=datetime.now(timezone.utc),
    ).model_dump(mode="json")

    return JSONResponse(status_code=status_code, content=content)

