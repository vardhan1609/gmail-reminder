"use client";

import { useState } from "react";
import { RefreshCw, CheckCircle2, AlertTriangle, ShieldCheck } from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

export function Header({ title, description }: { title: string; description?: string }) {
  const { user } = useAuth();
  const [syncing, setSyncing] = useState(false);
  const [syncMsg, setSyncMsg] = useState<string | null>(null);

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
    <header className="h-16 border-b border-slate-200 bg-white px-8 flex items-center justify-between sticky top-0 z-10">
      <div>
        <h2 className="text-xl font-bold text-slate-900 leading-tight">{title}</h2>
        {description && <p className="text-xs text-slate-500">{description}</p>}
      </div>

      <div className="flex items-center gap-4">
        {syncMsg && (
          <span className="text-xs font-medium text-slate-600 bg-slate-100 px-2.5 py-1 rounded-md animate-in fade-in">
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
            <Badge variant="secondary" className="gap-1 text-[11px] text-blue-700 bg-blue-50">
              <ShieldCheck className="h-3 w-3" /> 2FA Active
            </Badge>
          )}
        </div>
      </div>
    </header>
  );
}

