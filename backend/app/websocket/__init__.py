"""
WebSocket subsystem for real-time dashboard updates.
"""
from app.websocket.manager import connection_manager
from app.websocket.metrics import ws_metrics
from app.websocket.publisher import EventPublisher, publish_event, set_main_event_loop
from app.websocket.router import router as ws_router
from app.websocket.schemas import EventType, WebSocketEnvelope

__all__ = [
    "connection_manager",
    "ws_metrics",
    "EventPublisher",
    "publish_event",
    "set_main_event_loop",
    "ws_router",
    "EventType",
    "WebSocketEnvelope",
]

