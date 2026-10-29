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
import { formatDate } from "@/lib/utils";

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

  useEffect(() => {
    fetchReminders();
  }, [statusFilter]);

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
        <div className="flex gap-2 p-1 bg-slate-200/60 rounded-lg w-fit text-xs font-semibold">
          {["all", "pending", "sent", "failed"].map((st) => (
            <button
              key={st}
              onClick={() => setStatusFilter(st)}
              className={`px-3 py-1.5 rounded-md capitalize transition-colors ${
                statusFilter === st
                  ? "bg-white text-slate-900 shadow-sm"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              {st}
            </button>
          ))}
        </div>

        {error && (
          <div className="flex items-center gap-2 p-4 text-sm text-red-700 bg-red-50 border border-red-200 rounded-xl">
            <AlertCircle className="h-5 w-5 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {actionMessage && (
          <div className="flex items-center gap-2 p-4 text-sm text-emerald-800 bg-emerald-50 border border-emerald-200 rounded-xl">
            <CheckCircle2 className="h-5 w-5 shrink-0" />
            <span>{actionMessage}</span>
          </div>
        )}

        <Card>
          <CardHeader className="py-4 px-6 border-b border-slate-100 flex flex-row items-center justify-between">
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
              <div className="text-center py-16 text-slate-500">
                <Clock className="h-10 w-10 mx-auto mb-3 opacity-30" />
                <p className="text-base font-medium">No reminders found.</p>
                <p className="text-xs text-slate-400 mt-1">
                  Emails containing detected deadlines will schedule reminders here.
                </p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="bg-slate-50 text-slate-600 font-medium text-xs border-b border-slate-200">
                    <tr>
                      <th className="py-3 px-6">Message Preview</th>
                      <th className="py-3 px-4">Scheduled For</th>
                      <th className="py-3 px-4">Status</th>
                      <th className="py-3 px-4">Retries</th>
                      <th className="py-3 px-4">Sent At</th>
                      <th className="py-3 px-6 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {reminders.map((r) => (
                      <tr key={r.id} className="hover:bg-slate-50 transition-colors">
                        <td className="py-3.5 px-6 font-medium text-slate-900 max-w-sm truncate">
                          {r.message.split("\n")[0].replace(/[⏰*]/g, "").trim()}
                        </td>
                        <td className="py-3.5 px-4 text-xs font-semibold text-slate-700">
                          {formatDate(r.scheduled_at)}
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
                          {r.sent_at ? formatDate(r.sent_at) : "—"}
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

