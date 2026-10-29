"use client";

import { useEffect, useState } from "react";
import {
  Plug,
  Mail,
  Send,
  Trash2,
  Plus,
  CheckCircle2,
  AlertCircle,
  ExternalLink,
} from "lucide-react";
import { Header } from "@/components/layout/header";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Dialog, ConfirmDialog } from "@/components/ui/dialog";
import { api, GmailConnection, NotificationIntegration } from "@/lib/api";
import { formatDate } from "@/lib/utils";

export default function IntegrationsPage() {
  const [connections, setConnections] = useState<GmailConnection[]>([]);
  const [integrations, setIntegrations] = useState<NotificationIntegration[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Add Integration Modal
  const [addModalOpen, setAddModalOpen] = useState(false);
  const [destType, setDestType] = useState<"telegram" | "whatsapp">("telegram");
  const [destName, setDestName] = useState("");
  const [destTarget, setDestTarget] = useState("");
  const [destLoading, setDestLoading] = useState(false);

  // Test Destination State
  const [testingId, setTestingId] = useState<string | null>(null);

  // Delete Destination State
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [disconnectingGmailId, setDisconnectingGmailId] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [conns, dests] = await Promise.all([
        api.getGmailConnections(),
        api.getNotificationIntegrations(),
      ]);
      setConnections(conns || []);
      setIntegrations(dests || []);
    } catch (err: any) {
      setError(err.detail || "Failed to load integrations.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleConnectGmail = async () => {
    try {
      const { auth_url } = await api.getGmailAuthUrl();
      if (auth_url) {
        window.location.href = auth_url;
      }
    } catch (err: any) {
      setError(err.detail || "Failed to initiate Gmail OAuth.");
    }
  };

  const handleAddDestination = async (e: React.FormEvent) => {
    e.preventDefault();
    setDestLoading(true);
    setError(null);
    try {
      await api.createNotificationIntegration({
        type: destType,
        name: destName,
        target_id: destTarget,
      });
      setSuccessMsg(`Added ${destName} successfully.`);
      setAddModalOpen(false);
      setDestName("");
      setDestTarget("");
      await loadData();
      setTimeout(() => setSuccessMsg(null), 4000);
    } catch (err: any) {
      setError(err.detail || "Failed to add notification destination.");
    } finally {
      setDestLoading(false);
    }
  };

  const handleTestDestination = async (id: string) => {
    setTestingId(id);
    setError(null);
    try {
      const res = await api.testNotificationIntegration(id);
      setSuccessMsg(res.message);
      setTimeout(() => setSuccessMsg(null), 5000);
    } catch (err: any) {
      setError(err.detail || "Test notification failed.");
    } finally {
      setTestingId(null);
    }
  };

  const handleDeleteDestination = async () => {
    if (!deletingId) return;
    setActionLoading(true);
    try {
      await api.deleteNotificationIntegration(deletingId);
      setDeletingId(null);
      await loadData();
      setSuccessMsg("Destination removed.");
      setTimeout(() => setSuccessMsg(null), 3000);
    } catch (err: any) {
      setError(err.detail || "Failed to delete destination.");
    } finally {
      setActionLoading(false);
    }
  };

  const handleDisconnectGmail = async () => {
    if (!disconnectingGmailId) return;
    setActionLoading(true);
    try {
      await api.disconnectGmail(disconnectingGmailId);
      setDisconnectingGmailId(null);
      await loadData();
      setSuccessMsg("Gmail account disconnected.");
      setTimeout(() => setSuccessMsg(null), 3000);
    } catch (err: any) {
      setError(err.detail || "Failed to disconnect Gmail account.");
    } finally {
      setActionLoading(false);
    }
  };

  return (
    <div className="flex-1 flex flex-col">
      <Header
        title="Integrations"
        description="Manage your Gmail connections and messaging delivery channels."
      />

      <main className="flex-1 p-8 space-y-8 max-w-7xl mx-auto w-full">
        {error && (
          <div className="flex items-center gap-2 p-4 text-sm text-red-700 bg-red-50 border border-red-200 rounded-xl">
            <AlertCircle className="h-5 w-5 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {successMsg && (
          <div className="flex items-center gap-2 p-4 text-sm text-emerald-800 bg-emerald-50 border border-emerald-200 rounded-xl">
            <CheckCircle2 className="h-5 w-5 shrink-0" />
            <span>{successMsg}</span>
          </div>
        )}

        {/* Section 1: Gmail Account Connections */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle>Connected Gmail Accounts</CardTitle>
              <CardDescription>
                Connect your university Google Workspace or personal Gmail via secure OAuth 2.0.
              </CardDescription>
            </div>
            <Button onClick={handleConnectGmail} className="gap-2 shadow-sm">
              <Mail className="h-4 w-4" /> Connect Gmail Account
            </Button>
          </CardHeader>

          <CardContent>
            {loading ? (
              <div className="space-y-3">
                <Skeleton className="h-14 w-full" />
                <Skeleton className="h-14 w-full" />
              </div>
            ) : connections.length === 0 ? (
              <div className="text-center py-12 border border-dashed border-slate-200 rounded-xl bg-slate-50/50">
                <Mail className="h-8 w-8 mx-auto mb-2 text-slate-400" />
                <p className="text-sm font-semibold text-slate-800">No Gmail accounts connected yet</p>
                <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
                  Click the button above to authorize read-only mailbox monitoring.
                </p>
              </div>
            ) : (
              <div className="divide-y divide-slate-100">
                {connections.map((c) => (
                  <div key={c.id} className="py-4 flex items-center justify-between gap-4">
                    <div className="flex items-center gap-3">
                      <div className="h-10 w-10 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center font-bold">
                        <Mail className="h-5 w-5" />
                      </div>
                      <div>
                        <p className="text-sm font-semibold text-slate-900">{c.email}</p>
                        <p className="text-xs text-slate-500">
                          Status: {c.active ? "Synchronizing" : "Inactive"} • Connected:{" "}
                          {formatDate(c.created_at)}
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center gap-3">
                      <Badge variant={c.active ? "success" : "secondary"}>
                        {c.active ? "Active" : "Paused"}
                      </Badge>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setDisconnectingGmailId(c.id)}
                        className="text-xs text-red-600 hover:text-red-700 hover:bg-red-50 border-red-200"
                      >
                        Disconnect
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Section 2: Alert Destinations */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle>WhatsApp & Telegram Channels</CardTitle>
              <CardDescription>
                Configure target phone numbers and Telegram chat IDs for notification delivery.
              </CardDescription>
            </div>
            <Button variant="outline" onClick={() => setAddModalOpen(true)} className="gap-2">
              <Plus className="h-4 w-4" /> Add Destination
            </Button>
          </CardHeader>

          <CardContent>
            {loading ? (
              <div className="space-y-3">
                <Skeleton className="h-14 w-full" />
                <Skeleton className="h-14 w-full" />
              </div>
            ) : integrations.length === 0 ? (
              <div className="text-center py-12 border border-dashed border-slate-200 rounded-xl bg-slate-50/50">
                <Plug className="h-8 w-8 mx-auto mb-2 text-slate-400" />
                <p className="text-sm font-semibold text-slate-800">No alert channels configured</p>
                <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
                  Add a Telegram bot chat or WhatsApp destination to receive real-time notifications.
                </p>
              </div>
            ) : (
              <div className="divide-y divide-slate-100">
                {integrations.map((i) => (
                  <div key={i.id} className="py-4 flex items-center justify-between gap-4">
                    <div>
                      <div className="flex items-center gap-2">
                        <p className="text-sm font-semibold text-slate-900">{i.name}</p>
                        <Badge variant="outline" className="text-[10px] uppercase font-mono">
                          {i.type}
                        </Badge>
                        {i.is_default && (
                          <Badge variant="secondary" className="text-[10px]">
                            Default
                          </Badge>
                        )}
                      </div>
                      <p className="text-xs text-slate-500 font-mono mt-0.5">
                        Target ID: {i.target_id}
                      </p>
                    </div>

                    <div className="flex items-center gap-2">
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => handleTestDestination(i.id)}
                        loading={testingId === i.id}
                        className="text-xs gap-1.5"
                      >
                        <Send className="h-3 w-3" /> Test
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setDeletingId(i.id)}
                        className="text-xs text-red-600 hover:text-red-700 hover:bg-red-50"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </main>

      {/* Add Destination Modal */}
      <Dialog
        open={addModalOpen}
        onOpenChange={setAddModalOpen}
        title="Add Notification Channel"
        description="Choose channel type and enter recipient details."
      >
        <form onSubmit={handleAddDestination} className="space-y-4">
          <div className="space-y-1">
            <label className="text-xs font-semibold text-slate-700">Channel Type</label>
            <select
              value={destType}
              onChange={(e) => setDestType(e.target.value as "telegram" | "whatsapp")}
              className="w-full text-xs border border-slate-200 rounded-md p-2 bg-white"
            >
              <option value="telegram">Telegram Bot</option>
              <option value="whatsapp">WhatsApp</option>
            </select>
          </div>

          <div className="space-y-1">
            <label className="text-xs font-semibold text-slate-700">Display Name</label>
            <Input
              placeholder="e.g. My Personal Telegram"
              value={destName}
              onChange={(e) => setDestName(e.target.value)}
              required
            />
          </div>

          <div className="space-y-1">
            <label className="text-xs font-semibold text-slate-700">
              {destType === "telegram" ? "Telegram Chat ID" : "WhatsApp Phone Number"}
            </label>
            <Input
              placeholder={destType === "telegram" ? "e.g. 123456789 or -100123456789" : "e.g. +1234567890"}
              value={destTarget}
              onChange={(e) => setDestTarget(e.target.value)}
              required
            />
            <p className="text-[11px] text-slate-500 mt-1">
              {destType === "telegram"
                ? "Start a chat with your bot and send /start to get your chat ID."
                : "Enter phone number in international format with country code."}
            </p>
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => setAddModalOpen(false)}
              disabled={destLoading}
            >
              Cancel
            </Button>
            <Button type="submit" loading={destLoading}>
              Save Channel
            </Button>
          </div>
        </form>
      </Dialog>

      {/* Delete Confirmation */}
      <ConfirmDialog
        open={!!deletingId}
        onOpenChange={(open) => !open && setDeletingId(null)}
        title="Delete Notification Channel"
        message="Are you sure you want to delete this notification destination? Scheduled alerts will no longer be sent to it."
        confirmText="Delete Channel"
        variant="destructive"
        loading={actionLoading}
        onConfirm={handleDeleteDestination}
      />

      {/* Disconnect Gmail Confirmation */}
      <ConfirmDialog
        open={!!disconnectingGmailId}
        onOpenChange={(open) => !open && setDisconnectingGmailId(null)}
        title="Disconnect Gmail Account"
        message="Are you sure you want to disconnect this mailbox? Tokens will be revoked and removed from storage."
        confirmText="Disconnect Account"
        variant="destructive"
        loading={actionLoading}
        onConfirm={handleDisconnectGmail}
      />
    </div>
  );
}

