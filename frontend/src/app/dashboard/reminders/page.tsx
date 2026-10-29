"use client";

import { useEffect, useState } from "react";
import { Clock, Send, RefreshCw, AlertCircle, CheckCircle2 } from "lucide-react";
import { Header } from "@/components/layout/header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ConfirmDialog } from "@/components/ui/dialog";
import { api, ReminderRecord } from "@/lib/api";
import { formatDate, formatDualDate } from "@/lib/utils";
import { useRealtime } from "@/components/providers/realtime-provider";

export default function RemindersPage() {
  const [reminders, setReminders] = useState<ReminderRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Status Filter
  const [statusFilter, setStatusFilter] = useState<string>("all");

  // Resend Dialog
  const [resendingId, setResendingId] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  const fetchReminders = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.getReminders({
        limit: 50,
        status: statusFilter === "all" ? undefined : statusFilter,
      });
      setReminders(res.reminders || []);
      setTotal(res.total || 0);
    } catch (err: any) {
      setError(err.detail || "Failed to load reminders.");
    } finally {
      setLoading(false);
    }
  };

  const { subscribe } = useRealtime();

  useEffect(() => {
    fetchReminders();
  }, [statusFilter]);

  useEffect(() => {
    const unsubReminder = subscribe("reminder.created", (data: any) => {
      setReminders((prev) => {
        if (prev.some((r) => r.id === data.reminder_id)) return prev;
        const newRem: ReminderRecord = {
          id: data.reminder_id,
          email_id: data.email_id,
          destination_id: "",
          message: data.message_preview || "Deadline Reminder",
          scheduled_at: data.scheduled_at,
          status: "pending",
          retry_count: 0,
          last_error: null,
          sent_at: null,
          created_at: new Date().toISOString(),
        };
        return [newRem, ...prev];
      });
      setTotal((t) => t + 1);
    });

    const unsubReminderUpd = subscribe("reminder.updated", (data: any) => {
      setReminders((prev) =>
        prev.map((r) =>
          r.id === data.reminder_id
            ? {
                ...r,
                status: data.status,
                retry_count: data.retry_count ?? r.retry_count,
                last_error: data.last_error ?? r.last_error,
              }
            : r
        )
      );
    });

    return () => {
      unsubReminder();
      unsubReminderUpd();
    };
  }, [subscribe]);

  const handleResend = async () => {
    if (!resendingId) return;
    setActionLoading(true);
    try {
      const res = await api.resendReminder(resendingId);
      setActionMessage(res.message);
      setResendingId(null);
      await fetchReminders();
      setTimeout(() => setActionMessage(null), 4000);
    } catch (err: any) {
      setError(err.detail || "Failed to resend reminder.");
    } finally {
      setActionLoading(false);
    }
  };

  return (
    <div className="flex-1 flex flex-col">
      <Header
        title="Reminders"
        description="Automated deadline reminders scheduled across your notification channels."
      />

      <main className="flex-1 p-8 space-y-6 max-w-7xl mx-auto w-full">
        {/* Status Filter Tabs */}
        <div className="flex gap-2 p-1 bg-muted/70 rounded-lg w-fit text-xs font-semibold">
          {["all", "pending", "sent", "failed"].map((st) => (
            <button
              key={st}
              onClick={() => setStatusFilter(st)}
              className={`px-3 py-1.5 rounded-md capitalize transition-colors ${
                statusFilter === st
                  ? "bg-card text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {st}
            </button>
          ))}
        </div>

        {error && (
          <div className="flex items-center gap-2 p-4 text-sm text-destructive bg-destructive/10 border border-destructive/20 rounded-xl">
            <AlertCircle className="h-5 w-5 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {actionMessage && (
          <div className="flex items-center gap-2 p-4 text-sm text-emerald-800 dark:text-emerald-300 bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-900/50 rounded-xl">
            <CheckCircle2 className="h-5 w-5 shrink-0" />
            <span>{actionMessage}</span>
          </div>
        )}

        <Card>
          <CardHeader className="py-4 px-6 border-b border-border flex flex-row items-center justify-between">
            <CardTitle className="text-base font-semibold">
              Reminder Schedule ({total})
            </CardTitle>
          </CardHeader>

          <CardContent className="p-0">
            {loading ? (
              <div className="p-6 space-y-4">
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-10 w-full" />
              </div>
            ) : reminders.length === 0 ? (
              <div className="text-center py-16 text-muted-foreground">
                <Clock className="h-10 w-10 mx-auto mb-3 opacity-30" />
                <p className="text-base font-medium">No reminders found.</p>
                <p className="text-xs text-muted-foreground mt-1">
                  Emails containing detected deadlines will schedule reminders here.
                </p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="bg-slate-50 dark:bg-slate-900/60 text-muted-foreground font-medium text-xs border-b border-border">
                    <tr>
                      <th className="py-3 px-6">Message Preview</th>
                      <th className="py-3 px-4">Scheduled For</th>
                      <th className="py-3 px-4">Status</th>
                      <th className="py-3 px-4">Retries</th>
                      <th className="py-3 px-4">Sent At</th>
                      <th className="py-3 px-6 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {reminders.map((r) => (
                      <tr key={r.id} className="hover:bg-muted/50 transition-colors">
                        <td className="py-3.5 px-6 font-medium text-foreground max-w-sm truncate">
                          {r.message.split("\n")[0].replace(/[⏰*]/g, "").trim()}
                        </td>
                        <td className="py-3.5 px-4 text-xs">
                          <span className="font-semibold text-foreground block">
                            {formatDualDate(r.scheduled_at)?.local || formatDate(r.scheduled_at)}
                          </span>
                          <span className="text-[10px] text-muted-foreground font-mono block">
                            {formatDualDate(r.scheduled_at)?.utcTime || ""}
                          </span>
                        </td>
                        <td className="py-3.5 px-4">
                          <Badge
                            variant={
                              r.status === "sent"
                                ? "success"
                                : r.status === "failed"
                                ? "destructive"
                                : "secondary"
                            }
                            className="capitalize text-[11px]"
                          >
                            {r.status}
                          </Badge>
                        </td>
                        <td className="py-3.5 px-4 text-xs text-slate-500">
                          {r.retry_count}
                        </td>
                        <td className="py-3.5 px-4 text-xs text-slate-500">
                          {r.sent_at ? (
                            <div>
                              <span className="block">{formatDualDate(r.sent_at)?.local || formatDate(r.sent_at)}</span>
                              <span className="text-[10px] text-slate-400 font-mono block">
                                {formatDualDate(r.sent_at)?.utcTime || ""}
                              </span>
                            </div>
                          ) : (
                            "—"
                          )}
                        </td>
                        <td className="py-3.5 px-6 text-right">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setResendingId(r.id)}
                            className="h-8 gap-1.5 text-xs"
                          >
                            <Send className="h-3 w-3" /> Resend
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>
      </main>

      {/* Confirmation Dialog for Resending */}
      <ConfirmDialog
        open={!!resendingId}
        onOpenChange={(open) => !open && setResendingId(null)}
        title="Resend Reminder"
        message="Are you sure you want to dispatch this reminder immediately to its configured destination?"
        confirmText="Send Now"
        variant="default"
        loading={actionLoading}
        onConfirm={handleResend}
      />
    </div>
  );
}

