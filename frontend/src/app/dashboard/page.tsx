"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Inbox,
  Clock,
  Bell,
  Plug,
  ArrowUpRight,
  RefreshCw,
  AlertCircle,
  Calendar,
} from "lucide-react";
import { Header } from "@/components/layout/header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { api, EmailRecord, ReminderRecord, GmailConnection, NotificationIntegration } from "@/lib/api";
import { formatDate, formatDualDate } from "@/lib/utils";
import { useRealtime } from "@/components/providers/realtime-provider";

export default function DashboardOverviewPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [emails, setEmails] = useState<EmailRecord[]>([]);
  const [totalEmails, setTotalEmails] = useState(0);

  const [reminders, setReminders] = useState<ReminderRecord[]>([]);
  const [totalReminders, setTotalReminders] = useState(0);

  const [connections, setConnections] = useState<GmailConnection[]>([]);
  const [integrations, setIntegrations] = useState<NotificationIntegration[]>([]);

  const loadDashboardData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [emailRes, remRes, connRes, intRes] = await Promise.all([
        api.getEmails({ limit: 5 }),
        api.getReminders({ limit: 5 }),
        api.getGmailConnections(),
        api.getNotificationIntegrations(),
      ]);

      setEmails(emailRes.emails || []);
      setTotalEmails(emailRes.total || 0);

      setReminders(remRes.reminders || []);
      setTotalReminders(remRes.total || 0);

      setConnections(connRes || []);
      setIntegrations(intRes || []);
    } catch (err: any) {
      setError(err.detail || "Failed to load dashboard metrics.");
    } finally {
      setLoading(false);
    }
  };

  const { subscribe } = useRealtime();

  useEffect(() => {
    loadDashboardData();
  }, []);

  useEffect(() => {
    // 1. Listen for new incoming emails
    const unsubEmail = subscribe("email.received", (data: any) => {
      setEmails((prev) => {
        if (prev.some((e) => e.id === data.email_id)) return prev;
        const newEmail: EmailRecord = {
          id: data.email_id,
          account_id: null,
          gmail_message_id: data.email_id,
          gmail_thread_id: null,
          sender: data.sender,
          recipients: null,
          subject: data.subject,
          received_at: data.received_at,
          category: data.category || "Other",
          extracted_deadline: null,
          confidence_score: 1.0,
          ambiguous_date: false,
          plain_body: null,
          labels: null,
          processing_status: "completed",
          created_at: data.received_at,
          updated_at: data.received_at,
        };
        return [newEmail, ...prev.slice(0, 4)];
      });
      setTotalEmails((prev) => prev + 1);
    });

    // 2. Listen for email classification
    const unsubClassified = subscribe("email.classified", (data: any) => {
      setEmails((prev) =>
        prev.map((e) =>
          e.id === data.email_id
            ? {
                ...e,
                category: data.category,
                extracted_deadline: data.extracted_deadline,
                confidence_score: data.confidence_score,
              }
            : e
        )
      );
    });

    // 3. Listen for reminder created
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
        return [newRem, ...prev.slice(0, 4)];
      });
      setTotalReminders((prev) => prev + 1);
    });

    // 4. Listen for reminder updated
    const unsubReminderUpd = subscribe("reminder.updated", (data: any) => {
      setReminders((prev) =>
        prev.map((r) =>
          r.id === data.reminder_id
            ? { ...r, status: data.status, retry_count: data.retry_count ?? r.retry_count }
            : r
        )
      );
    });

    // 5. Catch up on sync completion
    const unsubSync = subscribe("gmail.sync.completed", () => {
      loadDashboardData();
    });

    return () => {
      unsubEmail();
      unsubClassified();
      unsubReminder();
      unsubReminderUpd();
      unsubSync();
    };
  }, [subscribe]);

  return (
    <div className="flex-1 flex flex-col">
      <Header
        title="Dashboard"
        description="Live summary of your monitored Gmail inboxes and automated notifications."
      />

      <main className="flex-1 p-8 space-y-8 max-w-7xl mx-auto w-full">
        {error && (
          <div className="flex items-center gap-2 p-4 text-sm text-destructive bg-destructive/10 border border-destructive/20 rounded-xl">
            <AlertCircle className="h-5 w-5 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Metrics Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
          {/* Card 1: Total Emails */}
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">Processed Emails</CardTitle>
              <Inbox className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              {loading ? (
                <Skeleton className="h-8 w-16" />
              ) : (
                <div className="text-2xl font-bold text-foreground">{totalEmails}</div>
              )}
              <p className="text-xs text-muted-foreground mt-1">Across all categories</p>
            </CardContent>
          </Card>

          {/* Card 2: Scheduled Reminders */}
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">Scheduled Reminders</CardTitle>
              <Clock className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              {loading ? (
                <Skeleton className="h-8 w-16" />
              ) : (
                <div className="text-2xl font-bold text-foreground">{totalReminders}</div>
              )}
              <p className="text-xs text-muted-foreground mt-1">Deadline notifications</p>
            </CardContent>
          </Card>

          {/* Card 3: Connected Inboxes */}
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">Gmail Accounts</CardTitle>
              <Plug className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              {loading ? (
                <Skeleton className="h-8 w-16" />
              ) : (
                <div className="text-2xl font-bold text-foreground">{connections.length}</div>
              )}
              <p className="text-xs text-muted-foreground mt-1">
                {connections.some((c) => c.active) ? "Active sync enabled" : "No accounts connected"}
              </p>
            </CardContent>
          </Card>

          {/* Card 4: Notification Channels */}
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">Alert Destinations</CardTitle>
              <Bell className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              {loading ? (
                <Skeleton className="h-8 w-16" />
              ) : (
                <div className="text-2xl font-bold text-foreground">{integrations.length}</div>
              )}
              <p className="text-xs text-muted-foreground mt-1">WhatsApp & Telegram</p>
            </CardContent>
          </Card>
        </div>

        {/* Content sections: Recent Emails & Active Reminders */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Recent Emails */}
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle>Recent Emails</CardTitle>
                <p className="text-xs text-muted-foreground">Latest synchronized messages</p>
              </div>
              <Link
                href="/dashboard/emails"
                className="text-xs font-semibold text-primary flex items-center hover:underline"
              >
                View all <ArrowUpRight className="h-3.5 w-3.5 ml-1" />
              </Link>
            </CardHeader>

            <CardContent>
              {loading ? (
                <div className="space-y-3">
                  <Skeleton className="h-14 w-full" />
                  <Skeleton className="h-14 w-full" />
                  <Skeleton className="h-14 w-full" />
                </div>
              ) : emails.length === 0 ? (
                <div className="text-center py-10 text-muted-foreground">
                  <Inbox className="h-8 w-8 mx-auto mb-2 opacity-40" />
                  <p className="text-sm">No emails synchronized yet.</p>
                  <p className="text-xs text-muted-foreground mt-1">
                    Connect your Gmail account in Integrations to start syncing.
                  </p>
                </div>
              ) : (
                <div className="divide-y divide-border">
                  {emails.map((e) => (
                    <div key={e.id} className="py-3 flex items-start justify-between gap-4">
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-semibold text-foreground truncate">{e.subject}</p>
                        <p className="text-xs text-muted-foreground truncate">From: {e.sender}</p>
                      </div>
                      <div className="flex flex-col items-end gap-1 shrink-0">
                        <Badge variant="outline" className="text-[10px]">
                          {e.category}
                        </Badge>
                        <span className="text-[10px] text-muted-foreground font-medium">
                          {formatDualDate(e.received_at || e.created_at)?.combined || formatDate(e.received_at || e.created_at)}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Upcoming Reminders */}
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle>Upcoming Reminders</CardTitle>
                <p className="text-xs text-muted-foreground">Deadlines extracted from your mailbox</p>
              </div>
              <Link
                href="/dashboard/reminders"
                className="text-xs font-semibold text-primary flex items-center hover:underline"
              >
                View all <ArrowUpRight className="h-3.5 w-3.5 ml-1" />
              </Link>
            </CardHeader>

            <CardContent>
              {loading ? (
                <div className="space-y-3">
                  <Skeleton className="h-14 w-full" />
                  <Skeleton className="h-14 w-full" />
                  <Skeleton className="h-14 w-full" />
                </div>
              ) : reminders.length === 0 ? (
                <div className="text-center py-10 text-muted-foreground">
                  <Calendar className="h-8 w-8 mx-auto mb-2 opacity-40" />
                  <p className="text-sm">No pending reminders.</p>
                  <p className="text-xs text-muted-foreground mt-1">
                    When emails with deadlines arrive, reminders will be automatically created here.
                  </p>
                </div>
              ) : (
                <div className="divide-y divide-border">
                  {reminders.map((r) => (
                    <div key={r.id} className="py-3 flex items-start justify-between gap-4">
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-medium text-foreground truncate">
                          {r.message.split("\n")[0].replace(/[⏰*]/g, "").trim()}
                        </p>
                        <p className="text-xs text-muted-foreground mt-0.5">
                          Scheduled: {formatDualDate(r.scheduled_at)?.combined || formatDate(r.scheduled_at)}
                        </p>
                      </div>
                      <Badge
                        variant={
                          r.status === "sent"
                            ? "success"
                            : r.status === "failed"
                            ? "destructive"
                            : "secondary"
                        }
                        className="text-[10px] capitalize"
                      >
                        {r.status}
                      </Badge>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </main>
    </div>
  );
}

