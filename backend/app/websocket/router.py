"""
WebSocket Router for Real-time Dashboard Updates.
Implements:
- /api/v1/ws: Authenticated WebSocket endpoint with Origin allowlisting and rate limiting.
- /api/v1/ws/resync: State recovery endpoint for reconnected clients.
- /api/v1/ws/metrics: Real-time connection and event metrics.
"""
from __future__ import annotations

import asyncio
import json
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional
from urllib.parse import urlparse

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from sqlalchemy.orm import Session

from app.config import settings
import app.database.session as session_module
from app.middleware.auth import get_current_user
from app.models.db_models import AppEventModel, UserModel
from app.services.auth_service import validate_session
from app.utils.logger import get_logger
from app.websocket.manager import connection_manager
from app.websocket.metrics import ws_metrics
from app.websocket.schemas import (
    ConnectionEstablishedData,
    EventType,
    WebSocketEnvelope,
)

logger = get_logger(__name__)

router = APIRouter(tags=["WebSockets"])

# Limits & Protections
MAX_MESSAGE_BYTES = 65536  # 64 KB
MAX_CLIENT_MESSAGES_PER_MINUTE = 30
ORIGIN_REGEX = re.compile(r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$", re.IGNORECASE)


def is_origin_allowed(origin: Optional[str]) -> bool:
    """
    Validates the WebSocket Origin against explicit settings and localhost patterns
    to prevent Cross-Site WebSocket Hijacking (CSWSH).
    """
    if not origin:
        # In non-browser test environments or direct clients Origin may be absent
        return True

    clean_origin = origin.rstrip("/").lower()

    # Check explicit allowlist
    for allowed in settings.cors_allowed_origins:
        if clean_origin == allowed.rstrip("/").lower():
            return True

    # Check localhost regex pattern
    if ORIGIN_REGEX.match(clean_origin):
        return True

    return False


def extract_ws_token(websocket: WebSocket) -> Optional[str]:
    """
    Extracts raw session token from:
    1. HttpOnly session cookie (primary)
    2. Sec-WebSocket-Protocol or Authorization header
    3. Query parameter 'token'
    """
    # 1. Cookie
    cookie_token = websocket.cookies.get(settings.session_cookie_name)
    if cookie_token:
        return cookie_token

    # Check raw Cookie header if not parsed in websocket.cookies
    cookie_header = websocket.headers.get("cookie")
    if cookie_header:
        for part in cookie_header.split(";"):
            if "=" in part:
                k, v = part.strip().split("=", 1)
                if k.strip() == settings.session_cookie_name:
                    return v.strip()

    # 2. Authorization header
    auth_header = websocket.headers.get("authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header.split(" ", 1)[1].strip()

    # 3. Query string fallback
    query_token = websocket.query_params.get("token")
    if query_token:
        return query_token

    return None


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    Primary authenticated WebSocket endpoint for real-time dashboard updates.
    Validates Origin, checks session authentication, enforces connection limits,
    and handles live events.
    """
    origin = websocket.headers.get("origin")
    if not is_origin_allowed(origin):
        logger.warning("Rejected WebSocket connection with unauthorized Origin: %s", origin)
        await websocket.close(code=1008, reason="Origin not allowed")
        return

    token = extract_ws_token(websocket)
    if not token:
        logger.warning("Rejected unauthenticated WebSocket connection: missing session token")
        await websocket.close(code=4401, reason="Authentication required")
        return

    # Validate session against database
    db = session_module.SessionLocal()
    try:
        session_result = validate_session(db, token)
        if not session_result:
            logger.warning("Rejected WebSocket connection: invalid or expired session")
            await websocket.close(code=4401, reason="Invalid or expired session")
            return

        session_obj, user = session_result
        if not session_obj.is_mfa_completed:
            logger.warning("Rejected WebSocket connection: MFA challenge pending for user %s", user.id)
            await websocket.close(code=1008, reason="MFA challenge required")
            return

        user_id = user.id
    finally:
        db.close()

    # Accept WebSocket connection
    await websocket.accept()

    # Register in ConnectionManager
    connected = await connection_manager.connect(websocket, user_id)
    if not connected:
        await websocket.close(code=1008, reason="Connection limit exceeded")
        return

    conn_id = uuid.uuid4().hex[:12]
    now_utc = datetime.now(timezone.utc).isoformat()

    # Send connection.established handshake event
    welcome_envelope = WebSocketEnvelope(
        event=EventType.CONNECTION_ESTABLISHED.value,
        data=ConnectionEstablishedData(
            user_id=user_id,
            connection_id=conn_id,
            connected_at=now_utc,
            heartbeat_interval_seconds=30,
        ).model_dump(),
    )
    await websocket.send_text(welcome_envelope.model_dump_json())

    # Rate limiting trackers
    message_timestamps: List[float] = []

    try:
        while True:
            # Receive raw text message with frame inspection
            data_text = await websocket.receive_text()

            if len(data_text.encode("utf-8")) > MAX_MESSAGE_BYTES:
                logger.warning("Client message exceeded maximum frame size (%d bytes)", len(data_text))
                await websocket.close(code=1009, reason="Message too large")
                break

            now = time.time()
            message_timestamps = [t for t in message_timestamps if now - t < 60]
            if len(message_timestamps) >= MAX_CLIENT_MESSAGES_PER_MINUTE:
                ws_metrics.inc_rate_limit_hits()
                logger.warning("Client exceeded message rate limit (%d/min)", MAX_CLIENT_MESSAGES_PER_MINUTE)
                err_resp = WebSocketEnvelope(
                    event=EventType.SYSTEM_ERROR.value,
                    data={"error_code": "RATE_LIMITED", "message": "Message rate limit exceeded. Please slow down."},
                )
                await websocket.send_text(err_resp.model_dump_json())
                continue

            message_timestamps.append(now)

            # Safely parse JSON client message
            try:
                msg_json = json.loads(data_text)
                msg_type = msg_json.get("type", "").lower()
            except Exception:
                msg_type = "invalid"

            if msg_type == "ping":
                # Heartbeat reply
                await websocket.send_text(json.dumps({
                    "type": "pong",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }))
            elif msg_type == "subscribe":
                # Acknowledgment of active subscription
                await websocket.send_text(json.dumps({
                    "type": "subscribed",
                    "events": [e.value for e in EventType],
                }))
            else:
                # Disallow arbitrary client commands
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": "Unsupported client command. Use REST APIs for mutations.",
                }))

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected for user %s", user_id)
    except Exception as exc:
        logger.debug("WebSocket connection terminated for user %s: %s", user_id, exc)
    finally:
        await connection_manager.disconnect(websocket, user_id)


# ─── Resynchronization & Metrics REST Endpoints ───

@router.get("/ws/resync")
def resync_events(
    since: Optional[str] = Query(None, description="ISO-8601 UTC timestamp to fetch events after"),
    limit: int = Query(50, ge=1, le=200, description="Max events to return"),
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(session_module.get_db_session),
):
    """
    Resynchronization API: Fetches missed events for the authenticated user since a given timestamp.
    Used by the frontend hook to recover state after temporary network disconnection.
    """
    query = db.query(AppEventModel).filter(AppEventModel.user_id == current_user.id)

    if since:
        try:
            from dateutil import parser as dtparser
            parsed_since = dtparser.parse(since)
            if parsed_since.tzinfo is None:
                parsed_since = parsed_since.replace(tzinfo=timezone.utc)
            query = query.filter(AppEventModel.created_at >= parsed_since)
        except Exception:
            pass

    events = (
        query.order_by(AppEventModel.created_at.asc())
        .limit(limit)
        .all()
    )

    return {
        "user_id": current_user.id,
        "count": len(events),
        "events": [
            {
                "event": e.event_type,
                "event_id": e.event_id,
                "timestamp": e.created_at.isoformat() if e.created_at else None,
                "data": json.loads(e.payload) if e.payload else {},
            }
            for e in events
        ],
    }


@router.get("/ws/metrics")
def get_websocket_metrics(
    current_user: UserModel = Depends(get_current_user),
):
    """Returns operational WebSocket metrics."""
    metrics = ws_metrics.get_metrics()
    metrics["user_active_connections"] = connection_manager.get_user_connection_count(current_user.id)
    return metrics
