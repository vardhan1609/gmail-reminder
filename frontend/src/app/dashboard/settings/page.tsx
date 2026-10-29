"use client";

import { useEffect, useState } from "react";
import { Sliders, CheckCircle2, AlertCircle, Save } from "lucide-react";
import { Header } from "@/components/layout/header";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { api, NotificationPreferences } from "@/lib/api";

export default function SettingsPage() {
  const [prefs, setPrefs] = useState<NotificationPreferences | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const loadPreferences = async () => {
    setLoading(true);
    setError(null);
    try {
      const p = await api.getPreferences();
      setPrefs(p);
    } catch (err: any) {
      setError(err.detail || "Failed to load notification settings.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadPreferences();
  }, []);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!prefs) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await api.updatePreferences(prefs);
      setPrefs(updated);
      setSuccessMsg("Notification rules updated successfully.");
      setTimeout(() => setSuccessMsg(null), 4000);
    } catch (err: any) {
      setError(err.detail || "Failed to save settings.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex-1 flex flex-col">
      <Header
        title="Notification Rules & Settings"
        description="Configure delivery frequency, privacy safeguards, and reminder timing."
      />

      <main className="flex-1 p-8 space-y-6 max-w-4xl mx-auto w-full">
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

        {loading ? (
          <Card>
            <CardContent className="p-8 space-y-4">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </CardContent>
          </Card>
        ) : prefs ? (
          <form onSubmit={handleSave}>
            <Card>
              <CardHeader>
                <CardTitle>Delivery Mode</CardTitle>
                <CardDescription>
                  Choose how and when alerts are dispatched to your connected channels.
                </CardDescription>
              </CardHeader>

              <CardContent className="space-y-6">
                {/* Notification Mode Radio */}
                <div className="space-y-3">
                  <label className="text-sm font-semibold text-slate-800">Alert Mode</label>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    {[
                      {
                        value: "immediate",
                        label: "Immediate",
                        desc: "Send alerts in real time as soon as new emails arrive.",
                      },
                      {
                        value: "summary",
                        label: "Summary Digest",
                        desc: "Batch incoming emails and deliver periodically.",
                      },
                      {
                        value: "important_only",
                        label: "Important Only",
                        desc: "Only alert on exams, deadlines, fees, and security.",
                      },
                    ].map((mode) => (
                      <div
                        key={mode.value}
                        onClick={() =>
                          setPrefs({
                            ...prefs,
                            notification_mode: mode.value as any,
                          })
                        }
                        className={`p-4 rounded-xl border cursor-pointer transition-all ${
                          prefs.notification_mode === mode.value
                            ? "border-blue-600 bg-blue-50/50 shadow-sm"
                            : "border-slate-200 hover:border-slate-300"
                        }`}
                      >
                        <p className="font-semibold text-sm text-slate-900">{mode.label}</p>
                        <p className="text-xs text-slate-500 mt-1">{mode.desc}</p>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Digest Interval */}
                {prefs.notification_mode === "summary" && (
                  <div className="space-y-1">
                    <label className="text-xs font-semibold text-slate-700">
                      Digest Interval (Minutes)
                    </label>
                    <Input
                      type="number"
                      min={5}
                      max={1440}
                      value={prefs.digest_interval_minutes}
                      onChange={(e) =>
                        setPrefs({
                          ...prefs,
                          digest_interval_minutes: Number(e.target.value),
                        })
                      }
                      className="max-w-xs text-xs"
                    />
                    <p className="text-[11px] text-slate-500">
                      Minimum 5 minutes, default 60 minutes.
                    </p>
                  </div>
                )}

                {/* Notification Cutoff */}
                <div className="space-y-1">
                  <label className="text-xs font-semibold text-slate-700">
                    Safe Notification Cutoff (Hours)
                  </label>
                  <Input
                    type="number"
                    min={1}
                    max={168}
                    value={prefs.notification_cutoff_hours}
                    onChange={(e) =>
                      setPrefs({
                        ...prefs,
                        notification_cutoff_hours: Number(e.target.value),
                      })
                    }
                    className="max-w-xs text-xs"
                  />
                  <p className="text-[11px] text-slate-500">
                    Emails received older than this threshold will be synchronized into the database but will NOT trigger notification alerts, preventing spam storms during initial imports.
                  </p>
                </div>

                {/* Reminder Offsets */}
                <div className="space-y-1">
                  <label className="text-xs font-semibold text-slate-700">
                    Reminder Offsets (Minutes Before Deadline)
                  </label>
                  <Input
                    type="text"
                    value={prefs.reminder_offsets_min}
                    onChange={(e) =>
                      setPrefs({
                        ...prefs,
                        reminder_offsets_min: e.target.value,
                      })
                    }
                    className="max-w-xs text-xs font-mono"
                  />
                  <p className="text-[11px] text-slate-500">
                    Comma-separated list in minutes. For example: <code>1440,360,60</code> triggers reminders 24h, 6h, and 1h prior to deadline.
                  </p>
                </div>

                {/* Privacy Mode Toggle */}
                <div className="pt-4 border-t border-slate-100 flex items-center justify-between">
                  <div>
                    <p className="text-sm font-semibold text-slate-900">Privacy Mode</p>
                    <p className="text-xs text-slate-500">
                      Redact email bodies and show only sender, subject, and direct Gmail link. Recommended for public group chats.
                    </p>
                  </div>
                  <input
                    type="checkbox"
                    checked={prefs.privacy_mode}
                    onChange={(e) =>
                      setPrefs({
                        ...prefs,
                        privacy_mode: e.target.checked,
                      })
                    }
                    className="h-4 w-4 rounded text-blue-600 focus:ring-blue-500"
                  />
                </div>

                <div className="flex justify-end pt-4">
                  <Button type="submit" loading={saving} className="gap-2">
                    <Save className="h-4 w-4" /> Save Preferences
                  </Button>
                </div>
              </CardContent>
            </Card>
          </form>
        ) : null}
      </main>
    </div>
  );
}

