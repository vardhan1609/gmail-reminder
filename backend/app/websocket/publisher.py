"""
Event Publisher for WebSockets.
Handles transactionally-safe event publishing, payload sanitization, durable outbox persistence
(for resync and cluster distribution), and thread-safe dispatch across async and worker threads.
"""
from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from sqlalchemy.orm import Session

import app.database.session as session_module
from app.models.db_models import AppEventModel
from app.utils.logger import get_logger
from app.websocket.manager import connection_manager
from app.websocket.metrics import ws_metrics
from app.websocket.schemas import EventType, WebSocketEnvelope, sanitize_payload

logger = get_logger(__name__)

# Captured main asyncio event loop for threadsafe cross-thread scheduling
_main_loop: Optional[asyncio.AbstractEventLoop] = None


def set_main_event_loop(loop: asyncio.AbstractEventLoop) -> None:
    """Store the main FastAPI asyncio event loop for background thread publishing."""
    global _main_loop
    _main_loop = loop


def get_main_event_loop() -> Optional[asyncio.AbstractEventLoop]:
    """Retrieve the main asyncio loop."""
    global _main_loop
    return _main_loop


class EventPublisher:
    """
    Central event publishing gateway.
    Ensures:
    1. Payloads are strictly sanitized (no secrets or sensitive email bodies).
    2. Events are persisted to the database outbox for recovery and resync.
    3. Events are safely dispatched to connected WebSockets of the target user.
    """

    @staticmethod
    def _persist_to_outbox(
        user_id: str,
        event_type: str,
        event_id: str,
        sanitized_data: Dict[str, Any],
        db: Optional[Session] = None,
    ) -> None:
        """Persists the event to the durable AppEventModel table."""
        should_close = False
        session = db
        if session is None:
            session = session_module.SessionLocal()
            should_close = True

        try:
            event_record = AppEventModel(
                user_id=user_id,
                event_type=event_type,
                event_id=event_id,
                payload=json.dumps(sanitized_data),
                created_at=datetime.now(timezone.utc),
            )
            session.add(event_record)
            session.commit()
        except Exception as exc:
            session.rollback()
            logger.error("Failed to persist event %s to outbox: %s", event_type, exc)
        finally:
            if should_close:
                session.close()

    @classmethod
    def publish_event(
        cls,
        user_id: Optional[str],
        event: str | EventType,
        data: Dict[str, Any],
        db: Optional[Session] = None,
    ) -> Optional[WebSocketEnvelope]:
        """
        Publishes a real-time event to an authenticated user.
        Thread-safe: can be called from synchronous background threads or asynchronous endpoints.
        """
        if not user_id:
            logger.debug("publish_event called without user_id; event %s skipped", event)
            return None

        event_str = event.value if isinstance(event, EventType) else str(event)
        clean_data = sanitize_payload(data)

        envelope = WebSocketEnvelope(
            event=event_str,
            data=clean_data,
        )

        ws_metrics.inc_events_published()

        # 1. Persist to outbox for client resync & crash durability
        cls._persist_to_outbox(user_id, event_str, envelope.event_id, clean_data, db=db)

        # 2. Dispatch to active WebSockets for this user
        cls._dispatch(user_id, envelope)

        logger.debug("Published %s [event_id=%s] to user %s", event_str, envelope.event_id, user_id)
        return envelope

    @classmethod
    def _dispatch(cls, user_id: str, envelope: WebSocketEnvelope) -> None:
        """Dispatches the envelope across async or worker thread boundaries."""
        # Check if we are currently inside a running asyncio event loop
        try:
            current_loop = asyncio.get_running_loop()
            if current_loop.is_running():
                current_loop.create_task(connection_manager.send_to_user(user_id, envelope))
                return
        except RuntimeError:
            pass

        # We are in a background worker thread: use the registered main loop
        target_loop = get_main_event_loop()
        if target_loop and target_loop.is_running():
            try:
                asyncio.run_coroutine_threadsafe(
                    connection_manager.send_to_user(user_id, envelope),
                    target_loop,
                )
            except Exception as exc:
                logger.error("Failed to schedule threadsafe event delivery: %s", exc)
        else:
            logger.debug("No active asyncio loop available to dispatch WebSocket event")


# Helper alias for direct import
publish_event = EventPublisher.publish_event
