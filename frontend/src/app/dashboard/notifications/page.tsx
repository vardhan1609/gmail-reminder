"use client";

import { useEffect, useState } from "react";
import { Bell, Filter, AlertCircle, CheckCircle2 } from "lucide-react";
import { Header } from "@/components/layout/header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { api, NotificationDeliveryRecord } from "@/lib/api";
import { formatDate } from "@/lib/utils";

export default function NotificationsPage() {
  const [deliveries, setDeliveries] = useState<NotificationDeliveryRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [channelFilter, setChannelFilter] = useState<string>("all");
  const [statusFilter, setStatusFilter] = useState<string>("all");

  const fetchDeliveries = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.getNotifications({
        limit: 50,
        channel: channelFilter === "all" ? undefined : channelFilter,
        status: statusFilter === "all" ? undefined : statusFilter,
      });
      setDeliveries(res.deliveries || []);
      setTotal(res.total || 0);
    } catch (err: any) {
      setError(err.detail || "Failed to load notification history.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDeliveries();
  }, [channelFilter, statusFilter]);

  return (
    <div className="flex-1 flex flex-col">
      <Header
        title="Delivery History"
        description="Audit trail of all dispatched WhatsApp and Telegram notifications."
      />

      <main className="flex-1 p-8 space-y-6 max-w-7xl mx-auto w-full">
        {/* Filters */}
        <div className="flex flex-wrap gap-4 items-center justify-between bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <div className="flex items-center gap-3">
            <span className="text-xs font-semibold text-slate-700">Channel:</span>
            <select
              value={channelFilter}
              onChange={(e) => setChannelFilter(e.target.value)}
              className="text-xs border border-slate-200 rounded-md px-3 py-1.5 bg-white text-slate-700 focus:outline-none"
            >
              <option value="all">All Channels</option>
              <option value="telegram">Telegram</option>
              <option value="whatsapp">WhatsApp</option>
            </select>
          </div>

          <div className="flex items-center gap-3">
            <span className="text-xs font-semibold text-slate-700">Status:</span>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="text-xs border border-slate-200 rounded-md px-3 py-1.5 bg-white text-slate-700 focus:outline-none"
            >
              <option value="all">All Statuses</option>
              <option value="sent">Sent</option>
              <option value="failed">Failed</option>
            </select>
          </div>
        </div>

        {error && (
          <div className="flex items-center gap-2 p-4 text-sm text-red-700 bg-red-50 border border-red-200 rounded-xl">
            <AlertCircle className="h-5 w-5 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <Card>
          <CardHeader className="py-4 px-6 border-b border-slate-100 flex flex-row items-center justify-between">
            <CardTitle className="text-base font-semibold">
              Dispatched Alerts ({total})
            </CardTitle>
          </CardHeader>

          <CardContent className="p-0">
            {loading ? (
              <div className="p-6 space-y-4">
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-10 w-full" />
              </div>
            ) : deliveries.length === 0 ? (
              <div className="text-center py-16 text-slate-500">
                <Bell className="h-10 w-10 mx-auto mb-3 opacity-30" />
                <p className="text-base font-medium">No notification deliveries recorded.</p>
                <p className="text-xs text-slate-400 mt-1">
                  When new emails or reminders are dispatched, logs will appear here.
                </p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="bg-slate-50 text-slate-600 font-medium text-xs border-b border-slate-200">
                    <tr>
                      <th className="py-3 px-6">Channel</th>
                      <th className="py-3 px-4">Destination ID</th>
                      <th className="py-3 px-4">Type</th>
                      <th className="py-3 px-4">Status</th>
                      <th className="py-3 px-4">Attempts</th>
                      <th className="py-3 px-4">Sent At</th>
                      <th className="py-3 px-6 text-right">Details</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {deliveries.map((d) => (
                      <tr key={d.id} className="hover:bg-slate-50 transition-colors">
                        <td className="py-3.5 px-6 font-semibold capitalize text-slate-900 text-xs">
                          {d.channel}
                        </td>
                        <td className="py-3.5 px-4 font-mono text-xs text-slate-600">
                          {d.destination_id}
                        </td>
                        <td className="py-3.5 px-4 text-xs capitalize text-slate-700">
                          {d.notification_type}
                        </td>
                        <td className="py-3.5 px-4">
                          <Badge
                            variant={
                              d.status === "sent"
                                ? "success"
                                : d.status === "failed"
                                ? "destructive"
                                : "secondary"
                            }
                            className="capitalize text-[11px]"
                          >
                            {d.status}
                          </Badge>
                        </td>
                        <td className="py-3.5 px-4 text-xs text-slate-500">{d.attempts}</td>
                        <td className="py-3.5 px-4 text-xs text-slate-500">
                          {d.sent_at ? formatDate(d.sent_at) : "—"}
                        </td>
                        <td className="py-3.5 px-6 text-right text-xs">
                          {d.last_error ? (
                            <span className="text-red-500 truncate block max-w-xs" title={d.last_error}>
                              {d.last_error}
                            </span>
                          ) : (
                            <span className="text-emerald-600 font-medium">Delivered</span>
                          )}
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
    </div>
  );
}

