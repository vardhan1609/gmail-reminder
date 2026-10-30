"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import {
  WebSocketConnectionState,
  WebSocketEnvelope,
  WebSocketEventType,
} from "@/types/websocket";
import { getApiBase } from "@/lib/api";

export interface RealtimeConnectionOptions {
  enabled?: boolean;
  onEvent?: (envelope: WebSocketEnvelope) => void;
  onReconnect?: () => void;
}

export interface UseRealtimeConnectionReturn {
  connectionState: WebSocketConnectionState;
  lastEvent: WebSocketEnvelope | null;
  subscribe: <T = any>(
    event: WebSocketEventType,
    callback: (data: T, envelope: WebSocketEnvelope<T>) => void
  ) => () => void;
  subscribeAll: (callback: (envelope: WebSocketEnvelope) => void) => () => void;
  reconnect: () => void;
}

function getWebSocketUrl(): string {
  if (typeof window === "undefined") return "";
  const apiBase = getApiBase();
  // Transform http://... or https://... into ws://... or wss://...
  let wsUrl = apiBase.replace(/^http/, "ws");
  return `${wsUrl}/ws`;
}

export function useRealtimeConnection(
  options: RealtimeConnectionOptions = {}
): UseRealtimeConnectionReturn {
  const { enabled = true, onEvent, onReconnect } = options;

  const [connectionState, setConnectionState] =
    useState<WebSocketConnectionState>("disconnected");
  const [lastEvent, setLastEvent] = useState<WebSocketEnvelope | null>(null);
  const onEventRef = useRef(onEvent);
  const onReconnectRef = useRef(onReconnect);
  onEventRef.current = onEvent;
  onReconnectRef.current = onReconnect;

  const socketRef = useRef<WebSocket | null>(null);
  const retryCountRef = useRef(0);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const pingIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const isMountedRef = useRef(true);
  const hasEverConnectedRef = useRef(false);

  // Set of recently seen event_ids to prevent duplicate handling
  const seenEventIdsRef = useRef<Set<string>>(new Set());

  // Listeners map: event -> Set of callbacks
  const listenersRef = useRef<Map<string, Set<(data: any, env: any) => void>>>(
    new Map()
  );
  const allListenersRef = useRef<Set<(env: WebSocketEnvelope) => void>>(
    new Set()
  );

  const clearTimers = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    if (pingIntervalRef.current) {
      clearInterval(pingIntervalRef.current);
      pingIntervalRef.current = null;
    }
  }, []);

  const connect = useCallback(() => {
    if (!enabled || typeof window === "undefined") return;
    if (!navigator.onLine) { setConnectionState("disconnected"); return; }

    // Avoid duplicate connections if already open or connecting
    if (
      socketRef.current &&
      (socketRef.current.readyState === WebSocket.OPEN ||
        socketRef.current.readyState === WebSocket.CONNECTING)
    ) {
      return;
    }

    clearTimers();

    const wsUrl = getWebSocketUrl();
    if (!wsUrl) return;

    setConnectionState((prev) =>
      hasEverConnectedRef.current ? "reconnecting" : "connecting"
    );

    try {
      const ws = new WebSocket(wsUrl);
      socketRef.current = ws;

      ws.onopen = () => {
        if (!isMountedRef.current) {
          ws.close();
          return;
        }
        setConnectionState("connected");
        retryCountRef.current = 0;

        // If this is a re-connection, trigger the onReconnect callback for state catch-up
        if (hasEverConnectedRef.current && onReconnectRef.current) {
          try {
            onReconnectRef.current();
          } catch (e) {
            console.error("Error in onReconnect callback:", e);
          }
        }
        hasEverConnectedRef.current = true;

        // Keepalive heartbeat ping every 25 seconds
        pingIntervalRef.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: "ping" }));
          }
        }, 25000);
      };

      ws.onmessage = (event) => {
        if (!isMountedRef.current) return;
        try {
          const raw = JSON.parse(event.data);

          // Handle system pongs or command acks
          if (raw.type === "pong" || raw.type === "subscribed") {
            return;
          }

          // Validate envelope structure
          if (!raw.event || !raw.event_id) {
            return;
          }

          // Deduplicate events by event_id
          if (seenEventIdsRef.current.has(raw.event_id)) {
            return;
          }

          // Maintain maximum bounded memory for seen IDs
          if (seenEventIdsRef.current.size > 500) {
            const first = seenEventIdsRef.current.values().next().value;
            if (first) seenEventIdsRef.current.delete(first);
          }
          seenEventIdsRef.current.add(raw.event_id);

          const envelope = raw as WebSocketEnvelope;
          setLastEvent(envelope);

          // Global onEvent callback
          if (onEventRef.current) {
            try {
              onEventRef.current(envelope);
            } catch (err) {
              console.error("Error in onEvent handler:", err);
            }
          }

          // Trigger subscribers to this specific event
          const eventListeners = listenersRef.current.get(envelope.event);
          if (eventListeners) {
            eventListeners.forEach((cb) => {
              try {
                cb(envelope.data, envelope);
              } catch (err) {
                console.error(`Error in event listener for ${envelope.event}:`, err);
              }
            });
          }

          // Trigger all-event subscribers
          allListenersRef.current.forEach((cb) => {
            try {
              cb(envelope);
            } catch (err) {
              console.error("Error in global event listener:", err);
            }
          });
        } catch (err) {
          console.warn("Failed to parse incoming WebSocket message:", err);
        }
      };

      ws.onclose = (event) => {
        if (!isMountedRef.current) return;
        clearTimers();
        if (socketRef.current === ws) socketRef.current = null;
        if (event.code === 4401 || (event.code === 1008 && event.reason?.includes("MFA"))) {
          setConnectionState("disconnected");
          return;
        }
        if (!navigator.onLine) { setConnectionState("disconnected"); return; }
        setConnectionState("reconnecting");

        // Exponential backoff with jitter (1.0s, 1.5s, 2.25s ... capped at 15s)
        const count = retryCountRef.current;
        const baseDelay = Math.min(15000, 1000 * Math.pow(1.5, count));
        const jitter = baseDelay * (0.8 + Math.random() * 0.4); // ±20% jitter
        retryCountRef.current = count + 1;

        reconnectTimeoutRef.current = setTimeout(() => {
          if (isMountedRef.current && enabled) {
            connect();
          }
        }, jitter);
      };

      ws.onerror = () => {
        // ws.onclose handles state and backoff
      };
    } catch (err) {
      console.error("Failed to initialize WebSocket:", err);
      setConnectionState("disconnected");
    }
  }, [enabled, clearTimers]);

  useEffect(() => {
    isMountedRef.current = true;
    const handleOnline = () => { retryCountRef.current = 0; connect(); };
    const handleOffline = () => {
      clearTimers();
      if (socketRef.current) { const socket = socketRef.current; socketRef.current = null; socket.close(1000, "Browser is offline"); }
      setConnectionState("disconnected");
    };
    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);
    if (enabled) connect();
    return () => {
      isMountedRef.current = false;
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
      clearTimers();
      if (socketRef.current) { socketRef.current.close(1000, "Component unmounted"); socketRef.current = null; }
    };
  }, [enabled, connect, clearTimers]);

  const subscribe = useCallback(
    <T = any>(
      event: WebSocketEventType,
      callback: (data: T, envelope: WebSocketEnvelope<T>) => void
    ) => {
      if (!listenersRef.current.has(event)) {
        listenersRef.current.set(event, new Set());
      }
      listenersRef.current.get(event)!.add(callback);

      return () => {
        const listeners = listenersRef.current.get(event);
        if (listeners) {
          listeners.delete(callback);
          if (listeners.size === 0) {
            listenersRef.current.delete(event);
          }
        }
      };
    },
    []
  );

  const subscribeAll = useCallback(
    (callback: (envelope: WebSocketEnvelope) => void) => {
      allListenersRef.current.add(callback);
      return () => {
        allListenersRef.current.delete(callback);
      };
    },
    []
  );

  return {
    connectionState,
    lastEvent,
    subscribe,
    subscribeAll,
    reconnect: connect,
  };
}

