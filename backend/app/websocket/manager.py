"""
WebSocket Connection Manager.
Manages connection lifecycles, per-user connection multiplexing, backpressure-safe delivery,
and graceful disconnection handling.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List, Optional, Set
from fastapi import WebSocket, WebSocketDisconnect

from app.utils.logger import get_logger
from app.websocket.metrics import ws_metrics
from app.websocket.schemas import WebSocketEnvelope

logger = get_logger(__name__)

# Security & Concurrency limits
MAX_CONNECTIONS_PER_USER = 10
GLOBAL_MAX_CONNECTIONS = 2000
SEND_TIMEOUT_SECONDS = 2.0


class ConnectionManager:
    """
    Thread-safe connection manager maintaining mappings of user_id -> active WebSockets.
    Guarantees user-level event isolation: events are only dispatched to sockets owned
    by the intended user_id.
    """

    def __init__(self):
        # user_id -> Set of WebSocket instances
        self._user_connections: Dict[str, Set[WebSocket]] = {}
        # Lock for mutating the connections map
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, user_id: str) -> bool:
        """
        Registers an authenticated WebSocket for a specific user.
        Enforces per-user and global connection limits.
        """
        async with self._lock:
            # Check global limits
            current_total = sum(len(sockets) for sockets in self._user_connections.values())
            if current_total >= GLOBAL_MAX_CONNECTIONS:
                logger.warning("Global WebSocket connection limit reached (%d)", GLOBAL_MAX_CONNECTIONS)
                return False

            user_sockets = self._user_connections.setdefault(user_id, set())
            if len(user_sockets) >= MAX_CONNECTIONS_PER_USER:
                logger.warning("Per-user connection limit reached for user %s (%d)", user_id, MAX_CONNECTIONS_PER_USER)
                return False

            user_sockets.add(websocket)
            ws_metrics.inc_active_connections()
            logger.info("WebSocket connected for user %s (user sockets: %d)", user_id, len(user_sockets))
            return True

    async def disconnect(self, websocket: WebSocket, user_id: str) -> None:
        """Removes a WebSocket registration."""
        async with self._lock:
            user_sockets = self._user_connections.get(user_id)
            if user_sockets and websocket in user_sockets:
                user_sockets.remove(websocket)
                ws_metrics.dec_active_connections()
                if not user_sockets:
                    self._user_connections.pop(user_id, None)
                logger.info("WebSocket disconnected for user %s", user_id)

    async def disconnect_user(self, user_id: str, code: int = 1000, reason: str = "Session terminated") -> int:
        """
        Closes and removes all active WebSockets for a given user.
        Used on logout, account deactivation, or session revocation.
        """
        sockets_to_close: List[WebSocket] = []
        async with self._lock:
            user_sockets = self._user_connections.pop(user_id, None)
            if user_sockets:
                sockets_to_close = list(user_sockets)
                for _ in sockets_to_close:
                    ws_metrics.dec_active_connections()

        closed_count = 0
        for ws in sockets_to_close:
            try:
                await ws.close(code=code, reason=reason)
                closed_count += 1
            except Exception:
                pass
        if closed_count > 0:
            logger.info("Disconnected %d active WebSockets for user %s", closed_count, user_id)
        return closed_count

    async def send_to_user(self, user_id: str, envelope: WebSocketEnvelope) -> int:
        """
        Delivers an event envelope to all active sockets belonging to user_id.
        Applies a strict timeout per socket so slow or stalled clients cannot
        block other connections or the event loop.
        Returns the number of sockets successfully delivered to.
        """
        async with self._lock:
            sockets = list(self._user_connections.get(user_id, set()))

        if not sockets:
            return 0

        payload_text = envelope.model_dump_json()
        dead_sockets: List[WebSocket] = []
        delivered = 0

        async def _deliver_one(ws: WebSocket):
            nonlocal delivered
            try:
                await asyncio.wait_for(ws.send_text(payload_text), timeout=SEND_TIMEOUT_SECONDS)
                delivered += 1
            except (WebSocketDisconnect, RuntimeError, asyncio.TimeoutError) as exc:
                logger.debug("Socket send failed for user %s: %s", user_id, exc)
                dead_sockets.append(ws)
            except Exception as exc:
                logger.warning("Unexpected send error for user %s: %s", user_id, exc)
                dead_sockets.append(ws)

        # Send concurrently to all user's tabs/connections
        await asyncio.gather(*[_deliver_one(ws) for ws in sockets], return_exceptions=True)

        if dead_sockets:
            async with self._lock:
                user_sockets = self._user_connections.get(user_id)
                if user_sockets:
                    for dead in dead_sockets:
                        if dead in user_sockets:
                            user_sockets.remove(dead)
                            ws_metrics.dec_active_connections()
                    if not user_sockets:
                        self._user_connections.pop(user_id, None)

        if delivered > 0:
            ws_metrics.inc_events_delivered(delivered)
        if dead_sockets:
            ws_metrics.inc_send_failures(len(dead_sockets))

        return delivered

    def get_user_connection_count(self, user_id: str) -> int:
        return len(self._user_connections.get(user_id, set()))

    def get_total_connection_count(self) -> int:
        return sum(len(s) for s in self._user_connections.values())


# Global singleton manager instance
connection_manager = ConnectionManager()

