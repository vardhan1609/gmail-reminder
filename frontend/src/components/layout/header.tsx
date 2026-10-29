"use client";

import { useState, useEffect } from "react";
import { RefreshCw, CheckCircle2, AlertTriangle, ShieldCheck, Wifi, WifiOff } from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import { useRealtime } from "@/components/providers/realtime-provider";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ThemeToggle } from "@/components/ui/theme-toggle";

export function Header({ title, description }: { title: string; description?: string }) {
  const { user } = useAuth();
  const { connectionState, reconnect, subscribe } = useRealtime();
  const [syncing, setSyncing] = useState(false);
  const [syncMsg, setSyncMsg] = useState<string | null>(null);

  // Subscribe to real-time Gmail sync events
  useEffect(() => {
    const unsubStarted = subscribe("gmail.sync.started", () => {
      setSyncing(true);
      setSyncMsg("Syncing mailbox...");
    });
    const unsubCompleted = subscribe("gmail.sync.completed", (data: any) => {
      setSyncing(false);
      setSyncMsg(`Sync complete (${data.new_messages_count || 0} new)`);
      setTimeout(() => setSyncMsg(null), 4000);
    });
    const unsubFailed = subscribe("gmail.sync.failed", (data: any) => {
      setSyncing(false);
      setSyncMsg(data.error ? `Sync error: ${data.error}` : "Sync failed");
      setTimeout(() => setSyncMsg(null), 4000);
    });

    return () => {
      unsubStarted();
      unsubCompleted();
      unsubFailed();
    };
  }, [subscribe]);

  const handleManualSync = async () => {
    setSyncing(true);
    setSyncMsg(null);
    try {
      const res = await api.triggerSync();
      setSyncMsg(res.message);
      setTimeout(() => setSyncMsg(null), 4000);
    } catch (err: any) {
      setSyncMsg(err.detail || "Sync failed");
      setTimeout(() => setSyncMsg(null), 4000);
    } finally {
      setSyncing(false);
    }
  };

  return (
    <header className="h-16 border-b border-slate-200 dark:border-slate-800 bg-white dark:bg-[#111827] px-8 flex items-center justify-between sticky top-0 z-10 transition-colors">
      <div>
        <h2 className="text-xl font-bold text-slate-900 dark:text-slate-100 leading-tight">{title}</h2>
        {description && <p className="text-xs text-slate-500 dark:text-slate-400">{description}</p>}
      </div>

      <div className="flex items-center gap-3">
        {/* Real-time Connection Indicator */}
        <div className="flex items-center">
          {connectionState === "connected" ? (
            <span
              className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium bg-emerald-50 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800/60"
              title="Real-time WebSocket connected"
            >
              <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
              Live
            </span>
          ) : connectionState === "reconnecting" ? (
            <span
              className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium bg-amber-50 dark:bg-amber-950/60 text-amber-700 dark:text-amber-300 border border-amber-200 dark:border-amber-800/60"
              title="Attempting to restore WebSocket connection"
            >
              <span className="h-2 w-2 rounded-full bg-amber-500 animate-pulse" />
              Reconnecting
            </span>
          ) : connectionState === "connecting" ? (
            <span
              className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 border border-slate-200 dark:border-slate-700"
            >
              <span className="h-2 w-2 rounded-full bg-slate-400" />
              Connecting
            </span>
          ) : (
            <button
              onClick={reconnect}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400 border border-slate-200 dark:border-slate-700 hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors"
              title="Real-time updates disconnected. Click to reconnect."
            >
              <WifiOff className="h-3 w-3" />
              Offline
            </button>
          )}
        </div>

        {syncMsg && (
          <span className="text-xs font-medium text-slate-600 dark:text-slate-300 bg-slate-100 dark:bg-slate-800 px-2.5 py-1 rounded-md animate-in fade-in">
            {syncMsg}
          </span>
        )}

        {/* Sync button */}
        <Button
          variant="outline"
          size="sm"
          onClick={handleManualSync}
          loading={syncing}
          className="gap-2 text-xs"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${syncing ? "animate-spin" : ""}`} />
          Sync Mailbox
        </Button>

        {/* Theme Switcher Toggle */}
        <ThemeToggle variant="compact" />

        {/* User security badges */}
        <div className="flex items-center gap-2">
          {user?.is_verified ? (
            <Badge variant="success" className="gap-1 text-[11px]">
              <CheckCircle2 className="h-3 w-3" /> Verified
            </Badge>
          ) : (
            <Badge variant="warning" className="gap-1 text-[11px]">
              <AlertTriangle className="h-3 w-3" /> Unverified
            </Badge>
          )}

          {user?.mfa_enabled && (
            <Badge variant="secondary" className="gap-1 text-[11px] text-blue-700 dark:text-blue-300 bg-blue-50 dark:bg-blue-950/60 border border-blue-200 dark:border-blue-900/50">
              <ShieldCheck className="h-3 w-3" /> 2FA Active
            </Badge>
          )}
        </div>
      </div>
    </header>
  );
}

