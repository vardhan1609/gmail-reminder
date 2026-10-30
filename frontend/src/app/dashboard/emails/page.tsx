"use client";

import { useEffect, useRef, useState } from "react";
import {
  Inbox,
  Search,
  Filter,
  Eye,
  ExternalLink,
  ChevronLeft,
  ChevronRight,
  AlertCircle,
  Calendar,
} from "lucide-react";
import { Header } from "@/components/layout/header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Dialog } from "@/components/ui/dialog";
import { api, EmailRecord } from "@/lib/api";
import { formatDate, formatDualDate } from "@/lib/utils";
import { useRealtime } from "@/components/providers/realtime-provider";

const CATEGORIES = [
  "All Categories",
  "Academics and assignments",
  "Examinations and results",
  "Placements and internships",
  "Fees and payments",
  "Meetings and events",
  "Personal messages",
  "Bills and receipts",
  "Travel and bookings",
  "Newsletters and promotions",
  "Security alerts",
  "Other",
];

export default function EmailsPage() {
  const [emails, setEmails] = useState<EmailRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters & Pagination
  const [searchTerm, setSearchTerm] = useState("");
  const [submittedSearch, setSubmittedSearch] = useState("");
  const [selectedCategory, setSelectedCategory] = useState("All Categories");
  const [page, setPage] = useState(0);
  const limit = 20;

  // Detail Modal
  const [selectedEmail, setSelectedEmail] = useState<EmailRecord | null>(null);

  const fetchEmails = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.getEmails({
        limit,
        skip: page * limit,
        category: selectedCategory === "All Categories" ? undefined : selectedCategory,
        search: submittedSearch || undefined,
      });
      setEmails(res.emails || []);
      setTotal(res.total || 0);
    } catch (err: any) {
      setError(err.detail || "Failed to load emails.");
    } finally {
      setLoading(false);
    }
  };

  const { subscribe, connectionState } = useRealtime();
  const hasConnectedRef = useRef(false);

  useEffect(() => {
    fetchEmails();
  }, [page, selectedCategory, submittedSearch]);

  useEffect(() => {
    if (connectionState === "connected") {
      if (hasConnectedRef.current) fetchEmails();
      hasConnectedRef.current = true;
    }
  }, [connectionState]);

  useEffect(() => {
    const unsubEmail = subscribe("email.received", (data: any) => {
      if (page === 0) {
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
          return [newEmail, ...prev];
        });
      }
      setTotal((t) => t + 1);
    });

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

    const unsubSync = subscribe("gmail.sync.completed", () => {
      fetchEmails();
    });

    return () => {
      unsubEmail();
      unsubClassified();
      unsubSync();
    };
  }, [subscribe, page, submittedSearch]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(0);
    setSubmittedSearch(searchTerm.trim());
  };

  const totalPages = Math.ceil(total / limit);

  return (
    <div className="flex-1 flex flex-col">
      <Header
        title="Emails"
        description="Processed emails classified across all 11 categories."
      />

      <main className="flex-1 p-4 sm:p-6 lg:p-8 space-y-6 max-w-7xl mx-auto w-full">
        {/* Filter bar */}
        <div className="flex flex-col sm:flex-row gap-4 justify-between items-center bg-card p-4 rounded-xl border border-border shadow-sm">
          <form onSubmit={handleSearchSubmit} className="flex gap-2 w-full sm:w-80">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                type="text"
                placeholder="Search by sender or subject..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-9 text-xs"
              />
            </div>
            <Button type="submit" size="sm" variant="secondary">
              Search
            </Button>
          </form>

          {/* Category Dropdown */}
          <div className="flex items-center gap-2 w-full sm:w-auto">
            <Filter className="h-4 w-4 text-muted-foreground" />
            <select
              value={selectedCategory}
              onChange={(e) => {
                setSelectedCategory(e.target.value);
                setPage(0);
              }}
              className="text-xs border border-input rounded-md px-3 py-2 bg-background text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
            >
              {CATEGORIES.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>
        </div>

        {error && (
          <div className="flex items-center gap-2 p-4 text-sm text-destructive bg-destructive/10 border border-destructive/20 rounded-xl">
            <AlertCircle className="h-5 w-5 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Emails Table */}
        <Card>
          <CardHeader className="py-4 px-6 border-b border-slate-100 flex flex-row items-center justify-between">
            <CardTitle className="text-base font-semibold">
              Mailbox Messages ({total})
            </CardTitle>
          </CardHeader>

          <CardContent className="p-0">
            {loading ? (
              <div className="p-6 space-y-4">
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-10 w-full" />
              </div>
            ) : emails.length === 0 ? (
              <div className="text-center py-16 text-slate-500">
                <Inbox className="h-10 w-10 mx-auto mb-3 opacity-30" />
                <p className="text-base font-medium">No emails found.</p>
                <p className="text-xs text-slate-400 mt-1">
                  Try clearing your search query or connect an active Gmail account.
                </p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="bg-slate-50 dark:bg-slate-900/60 text-muted-foreground font-medium text-xs border-b border-border">
                    <tr>
                      <th className="py-3 px-6">Subject</th>
                      <th className="py-3 px-4">Sender</th>
                      <th className="py-3 px-4">Category</th>
                      <th className="py-3 px-4">Deadline</th>
                      <th className="py-3 px-4">Received</th>
                      <th className="py-3 px-6 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {emails.map((e) => (
                      <tr key={e.id} className="hover:bg-muted/50 transition-colors">
                        <td className="py-3.5 px-6 font-medium text-foreground max-w-xs truncate">
                          {e.subject}
                        </td>
                        <td className="py-3.5 px-4 text-muted-foreground max-w-[200px] truncate text-xs">
                          {e.sender}
                        </td>
                        <td className="py-3.5 px-4">
                          <Badge variant="outline" className="text-[11px]">
                            {e.category}
                          </Badge>
                        </td>
                        <td className="py-3.5 px-4 text-xs">
                          {e.extracted_deadline ? (
                            <div>
                              <span className="flex items-center gap-1 text-emerald-700 font-medium">
                                <Calendar className="h-3.5 w-3.5 text-emerald-600 shrink-0" />
                                {formatDualDate(e.extracted_deadline)?.local || formatDate(e.extracted_deadline)}
                              </span>
                              <span className="text-[10px] text-slate-400 font-mono block pl-4.5">
                                {formatDualDate(e.extracted_deadline)?.utcTime || ""}
                              </span>
                            </div>
                          ) : (
                            <span className="text-slate-400">—</span>
                          )}
                        </td>
                        <td className="py-3.5 px-4 text-xs">
                          <span className="text-slate-700 font-medium block">
                            {formatDualDate(e.received_at || e.created_at)?.local || formatDate(e.received_at || e.created_at)}
                          </span>
                          <span className="text-[10px] text-slate-400 font-mono block">
                            {formatDualDate(e.received_at || e.created_at)?.utcTime || ""}
                          </span>
                        </td>
                        <td className="py-3.5 px-6 text-right">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setSelectedEmail(e)}
                            className="h-8 gap-1 text-xs"
                          >
                            <Eye className="h-3.5 w-3.5" /> View
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>

          {/* Pagination bar */}
          {totalPages > 1 && (
            <div className="py-3 px-6 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500">
              <span>
                Page {page + 1} of {totalPages} ({total} items)
              </span>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage((p) => Math.max(0, p - 1))}
                  disabled={page === 0 || loading}
                  className="h-7 px-2"
                >
                  <ChevronLeft className="h-3.5 w-3.5" /> Prev
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                  disabled={page >= totalPages - 1 || loading}
                  className="h-7 px-2"
                >
                  Next <ChevronRight className="h-3.5 w-3.5" />
                </Button>
              </div>
            </div>
          )}
        </Card>
      </main>

      {/* View Email Detail Modal */}
      <Dialog
        open={!!selectedEmail}
        onOpenChange={(open) => !open && setSelectedEmail(null)}
        title={selectedEmail?.subject || "Email Details"}
        description={`From: ${selectedEmail?.sender || "Unknown"}`}
      >
        {selectedEmail && (
          <div className="space-y-4 text-xs max-h-[70vh] overflow-y-auto">
            <div className="grid grid-cols-2 gap-3 p-3 bg-muted/40 border border-border rounded-lg">
              <div>
                <p className="text-muted-foreground font-semibold">Category</p>
                <p className="text-foreground font-medium">{selectedEmail.category}</p>
              </div>
              <div>
                <p className="text-muted-foreground font-semibold">Received At</p>
                <p className="text-foreground font-medium">
                  {formatDualDate(selectedEmail.received_at || selectedEmail.created_at)?.local || formatDate(selectedEmail.received_at || selectedEmail.created_at)}
                </p>
                <p className="text-[11px] text-muted-foreground font-mono mt-0.5">
                  {formatDualDate(selectedEmail.received_at || selectedEmail.created_at)?.utc || ""}
                </p>
              </div>
              {selectedEmail.extracted_deadline && (
                <div>
                  <p className="text-muted-foreground font-semibold">Extracted Deadline</p>
                  <p className="text-emerald-600 dark:text-emerald-400 font-medium">
                    {formatDualDate(selectedEmail.extracted_deadline)?.local || formatDate(selectedEmail.extracted_deadline)}
                  </p>
                  <p className="text-[11px] text-muted-foreground font-mono mt-0.5">
                    {formatDualDate(selectedEmail.extracted_deadline)?.utc || ""}
                  </p>
                </div>
              )}
              <div>
                <p className="text-muted-foreground font-semibold">Classification Confidence</p>
                <p className="text-foreground font-medium">
                  {(selectedEmail.confidence_score * 100).toFixed(0)}%
                </p>
              </div>
            </div>

            {/* Email Body */}
            <div>
              <p className="font-semibold text-foreground mb-1">Plain Text Body</p>
              <div className="p-3 bg-card border border-border rounded-lg whitespace-pre-wrap font-sans text-foreground max-h-60 overflow-y-auto leading-relaxed">
                {selectedEmail.plain_body || "(No body text extracted)"}
              </div>
            </div>

            <div className="pt-2 flex justify-between items-center">
              {selectedEmail.gmail_message_id && (
                <a
                  href={`https://mail.google.com/mail/u/0/#inbox/${selectedEmail.gmail_message_id}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1.5 text-blue-600 hover:underline font-medium"
                >
                  <ExternalLink className="h-3.5 w-3.5" /> Open in Gmail
                </a>
              )}
              <Button variant="outline" size="sm" onClick={() => setSelectedEmail(null)}>
                Close
              </Button>
            </div>
          </div>
        )}
      </Dialog>
    </div>
  );
}

