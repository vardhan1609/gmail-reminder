"use client";

import { useEffect, useState } from "react";
import { Smartphone, Monitor, ShieldCheck, Trash2, AlertCircle, CheckCircle2 } from "lucide-react";
import { Header } from "@/components/layout/header";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ConfirmDialog } from "@/components/ui/dialog";
import { api, SessionInfo } from "@/lib/api";
import { formatDate } from "@/lib/utils";

export default function SessionsPage() {
  const [sessions, setSessions] = useState<SessionInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Revoke Dialog State
  const [revokingId, setRevokingId] = useState<string | null>(null);
  const [revokeAllOpen, setRevokeAllOpen] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);

  const fetchSessions = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getSessions();
      setSessions(data || []);
    } catch (err: any) {
      setError(err.detail || "Failed to load active sessions.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSessions();
  }, []);

  const handleRevokeSingle = async () => {
    if (!revokingId) return;
    setActionLoading(true);
    try {
      await api.revokeSession(revokingId);
      setRevokingId(null);
      await fetchSessions();
      setSuccessMsg("Session revoked successfully.");
      setTimeout(() => setSuccessMsg(null), 3000);
    } catch (err: any) {
      setError(err.detail || "Failed to revoke session.");
    } finally {
      setActionLoading(false);
    }
  };

  const handleRevokeAllOther = async () => {
    setActionLoading(true);
    try {
      const res = await api.revokeAllSessions();
      setRevokeAllOpen(false);
      await fetchSessions();
      setSuccessMsg(res.message);
      setTimeout(() => setSuccessMsg(null), 4000);
    } catch (err: any) {
      setError(err.detail || "Failed to revoke all other sessions.");
    } finally {
      setActionLoading(false);
    }
  };

  return (
    <div className="flex-1 flex flex-col">
      <Header
        title="Active Sessions"
        description="Monitor and manage all devices currently logged in to your account."
      />

      <main className="flex-1 p-4 sm:p-6 lg:p-8 space-y-6 max-w-4xl mx-auto w-full">
        {error && (
          <div className="flex items-center gap-2 p-4 text-sm text-destructive bg-destructive/10 border border-destructive/20 rounded-xl">
            <AlertCircle className="h-5 w-5 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {successMsg && (
          <div className="flex items-center gap-2 p-4 text-sm text-emerald-800 dark:text-emerald-300 bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-900/50 rounded-xl">
            <CheckCircle2 className="h-5 w-5 shrink-0" />
            <span>{successMsg}</span>
          </div>
        )}

        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle>Session History</CardTitle>
              <CardDescription>
                Revoke any sessions you do not recognize or log out from other devices.
              </CardDescription>
            </div>
            {sessions.length > 1 && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setRevokeAllOpen(true)}
                className="text-destructive hover:bg-destructive/10 border-destructive/30 text-xs"
              >
                Log Out All Other Devices
              </Button>
            )}
          </CardHeader>

          <CardContent>
            {loading ? (
              <div className="space-y-4">
                <Skeleton className="h-16 w-full" />
                <Skeleton className="h-16 w-full" />
              </div>
            ) : sessions.length === 0 ? (
              <div className="text-center py-10 text-muted-foreground">
                <p>No active sessions found.</p>
              </div>
            ) : (
              <div className="divide-y divide-border">
                {sessions.map((s) => (
                  <div key={s.id} className="py-4 flex items-center justify-between gap-4">
                    <div className="flex items-start gap-3">
                      <div className="h-10 w-10 rounded-lg bg-muted text-muted-foreground flex items-center justify-center shrink-0">
                        {s.user_agent?.toLowerCase().includes("mobile") ? (
                          <Smartphone className="h-5 w-5" />
                        ) : (
                          <Monitor className="h-5 w-5" />
                        )}
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <p className="text-sm font-semibold text-foreground font-mono">
                            {s.ip_address || "Unknown IP"}
                          </p>
                          {s.is_current && (
                            <Badge variant="success" className="text-[10px]">
                              Current Session
                            </Badge>
                          )}
                          {s.is_mfa_completed && (
                            <Badge variant="outline" className="text-[10px] text-blue-700 bg-blue-50 border-blue-200">
                              MFA Verified
                            </Badge>
                          )}
                        </div>
                        <p className="text-xs text-slate-500 max-w-md truncate mt-0.5">
                          {s.user_agent || "Unknown Browser / Client"}
                        </p>
                        <p className="text-[11px] text-slate-400 mt-1">
                          Last Active: {formatDate(s.last_active_at)} • Signed In:{" "}
                          {formatDate(s.created_at)}
                        </p>
                      </div>
                    </div>

                    {!s.is_current && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setRevokingId(s.id)}
                        className="text-xs text-red-600 hover:text-red-700 hover:bg-red-50"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    )}
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </main>

      {/* Revoke Single Session Dialog */}
      <ConfirmDialog
        open={!!revokingId}
        onOpenChange={(open) => !open && setRevokingId(null)}
        title="Revoke Session"
        message="Are you sure you want to terminate this session? The device will be immediately signed out."
        confirmText="Revoke Session"
        variant="destructive"
        loading={actionLoading}
        onConfirm={handleRevokeSingle}
      />

      {/* Revoke All Other Sessions Dialog */}
      <ConfirmDialog
        open={revokeAllOpen}
        onOpenChange={setRevokeAllOpen}
        title="Log Out All Other Devices"
        message="Are you sure you want to log out all other active sessions? Only your current device will remain signed in."
        confirmText="Log Out Other Devices"
        variant="destructive"
        loading={actionLoading}
        onConfirm={handleRevokeAllOther}
      />
    </div>
  );
}

