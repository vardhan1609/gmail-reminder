"""
WebSocket Metrics tracking system.
Provides thread-safe operational metrics for monitoring real-time connection health,
event publication, and message delivery error rates.
"""
from __future__ import annotations

import threading
from typing import Any, Dict


class WebSocketMetrics:
    """Thread-safe metrics accumulator for the WebSocket subsystem."""

    def __init__(self):
        self._lock = threading.Lock()
        self._active_connections: int = 0
        self._total_connections: int = 0
        self._total_disconnections: int = 0
        self._events_published: int = 0
        self._events_delivered: int = 0
        self._send_failures: int = 0
        self._rate_limit_hits: int = 0

    def inc_active_connections(self) -> None:
        with self._lock:
            self._active_connections += 1
            self._total_connections += 1

    def dec_active_connections(self) -> None:
        with self._lock:
            if self._active_connections > 0:
                self._active_connections -= 1
            self._total_disconnections += 1

    def inc_events_published(self) -> None:
        with self._lock:
            self._events_published += 1

    def inc_events_delivered(self, count: int = 1) -> None:
        with self._lock:
            self._events_delivered += count

    def inc_send_failures(self, count: int = 1) -> None:
        with self._lock:
            self._send_failures += count

    def inc_rate_limit_hits(self) -> None:
        with self._lock:
            self._rate_limit_hits += 1

    def get_metrics(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "active_connections": self._active_connections,
                "total_connections": self._total_connections,
                "total_disconnections": self._total_disconnections,
                "events_published": self._events_published,
                "events_delivered": self._events_delivered,
                "send_failures": self._send_failures,
                "rate_limit_hits": self._rate_limit_hits,
            }

    def reset(self) -> None:
        """Reset counters for testing."""
        with self._lock:
            self._active_connections = 0
            self._total_connections = 0
            self._total_disconnections = 0
            self._events_published = 0
            self._events_delivered = 0
            self._send_failures = 0
            self._rate_limit_hits = 0


# Global singleton instance
ws_metrics = WebSocketMetrics()

