"use client";

import React, { createContext, useContext, useState, useEffect } from "react";
import {
  useRealtimeConnection,
  UseRealtimeConnectionReturn,
} from "@/lib/use-realtime-connection";
import { useAuth } from "@/lib/auth-context";
import { WebSocketEnvelope } from "@/types/websocket";
import { CheckCircle2, AlertCircle, Clock, Mail, Bell, RefreshCw } from "lucide-react";

interface ToastNotification {
  id: string;
  title: string;
  message: string;
  type: "info" | "success" | "warning" | "error";
  icon?: React.ReactNode;
}

interface RealtimeContextType extends UseRealtimeConnectionReturn {
  toasts: ToastNotification[];
  removeToast: (id: string) => void;
}

const RealtimeContext = createContext<RealtimeContextType | null>(null);

export function RealtimeProvider({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  const [toasts, setToasts] = useState<ToastNotification[]>([]);

  const addToast = (toast: Omit<ToastNotification, "id">) => {
    const id = Math.random().toString(36).substring(2, 9);
    setToasts((prev) => [...prev.slice(-4), { ...toast, id }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 5000);
  };

  const removeToast = (id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  const realtime = useRealtimeConnection({
    enabled: !!user,
    onEvent: (envelope: WebSocketEnvelope) => {
      const { event, data } = envelope;

      switch (event) {
        case "email.received":
          addToast({
            title: "New Email Processed",
            message: `${data.subject || "No Subject"} (from ${data.sender || "unknown"})`,
            type: "info",
            icon: <Mail className="h-4 w-4 text-blue-500" />,
          });
          break;

        case "reminder.created":
          addToast({
            title: "Reminder Scheduled",
            message: data.message_preview || "Deadline reminder registered",
            type: "success",
            icon: <Clock className="h-4 w-4 text-emerald-500" />,
          });
          break;

        case "reminder.due_soon":
          addToast({
            title: "Upcoming Deadline",
            message: `Reminder approaching for ${data.subject || "scheduled item"} (${data.minutes_remaining}m left)`,
            type: "warning",
            icon: <AlertCircle className="h-4 w-4 text-amber-500" />,
          });
          break;

        case "gmail.sync.completed":
          addToast({
            title: "Gmail Sync Completed",
            message: `${data.new_messages_count || 0} new message(s) synchronized.`,
            type: "success",
            icon: <RefreshCw className="h-4 w-4 text-emerald-500" />,
          });
          break;

        case "gmail.sync.failed":
          addToast({
            title: "Gmail Sync Issue",
            message: data.error || "Failed to synchronize mailbox.",
            type: "error",
            icon: <AlertCircle className="h-4 w-4 text-rose-500" />,
          });
          break;

        case "notification.sent":
          addToast({
            title: "Notification Sent",
            message: `Delivered via ${data.channel?.toUpperCase() || "messaging channel"}.`,
            type: "info",
            icon: <Bell className="h-4 w-4 text-indigo-500" />,
          });
          break;

        case "notification.failed":
          addToast({
            title: "Notification Delivery Failed",
            message: `Could not deliver via ${data.channel || "channel"}: ${data.error || "Error"}`,
            type: "error",
            icon: <AlertCircle className="h-4 w-4 text-rose-500" />,
          });
          break;
      }
    },
  });

  return (
    <RealtimeContext.Provider value={{ ...realtime, toasts, removeToast }}>
      {children}

      {/* Floating real-time toasts container */}
      <div className="fixed bottom-5 right-5 z-50 flex flex-col gap-2 max-w-sm pointer-events-none">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className={`pointer-events-auto p-3.5 rounded-xl border shadow-lg flex items-start gap-3 transition-all animate-in slide-in-from-bottom-5 fade-in duration-200 ${
              toast.type === "error"
                ? "border-rose-200 dark:border-rose-900/60 text-rose-900 dark:text-rose-200 bg-white dark:bg-slate-900"
                : toast.type === "warning"
                ? "border-amber-200 dark:border-amber-900/60 text-amber-900 dark:text-amber-200 bg-white dark:bg-slate-900"
                : toast.type === "success"
                ? "border-emerald-200 dark:border-emerald-900/60 text-emerald-900 dark:text-emerald-200 bg-white dark:bg-slate-900"
                : "border-border text-foreground bg-card"
            }`}
          >
            <div className="mt-0.5 shrink-0">{toast.icon}</div>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-semibold leading-tight">{toast.title}</p>
              <p className="text-[11px] text-muted-foreground truncate mt-0.5">{toast.message}</p>
            </div>
            <button
              onClick={() => removeToast(toast.id)}
              className="text-muted-foreground hover:text-foreground text-xs px-1"
            >
              ×
            </button>
          </div>
        ))}
      </div>
    </RealtimeContext.Provider>
  );
}

export function useRealtime(): RealtimeContextType {
  const context = useContext(RealtimeContext);
  if (!context) {
    throw new Error("useRealtime must be used within a RealtimeProvider");
  }
  return context;
}
