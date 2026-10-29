/**
 * Type-safe API client for Gmail Reminder backend.
 * Uses HTTP-only cookies (credentials: 'include') and handles response error unwrapping.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000/api/v1";

export interface User {
  id: string;
  email: string;
  full_name: string | null;
  is_verified: boolean;
  is_active: boolean;
  is_admin: boolean;
  mfa_enabled: boolean;
  created_at: string;
}

export interface SessionInfo {
  id: string;
  ip_address: string | null;
  user_agent: string | null;
  is_mfa_completed: boolean;
  is_current: boolean;
  expires_at: string;
  created_at: string;
  last_active_at: string;
}

export interface EmailRecord {
  id: string;
  account_id: string | null;
  gmail_message_id: string;
  gmail_thread_id: string | null;
  sender: string;
  recipients: string | null;
  subject: string;
  received_at: string | null;
  category: string;
  extracted_deadline: string | null;
  confidence_score: number;
  ambiguous_date: boolean;
  plain_body: string | null;
  labels: string | null;
  processing_status: string;
  created_at: string;
  updated_at: string;
}

export interface ReminderRecord {
  id: string;
  email_id: string;
  destination_id: string;
  message: string;
  scheduled_at: string;
  status: "pending" | "sent" | "failed" | "cancelled";
  retry_count: number;
  last_error: string | null;
  sent_at: string | null;
  created_at: string;
}

export interface NotificationDeliveryRecord {
  id: string;
  email_id: string | null;
  channel: string;
  destination_id: string;
  notification_type: string;
  idempotency_key: string;
  status: "pending" | "sent" | "failed";
  attempts: number;
  sent_at: string | null;
  last_error: string | null;
  created_at: string;
}

export interface GmailConnection {
  id: string;
  email: string;
  label: string | null;
  active: boolean;
  history_id: string | null;
  last_sync_at: string | null;
  last_sync_status: string | null;
  calendar_sync_enabled: boolean;
  created_at: string;
}

export interface NotificationIntegration {
  id: string;
  type: "telegram" | "whatsapp";
  name: string;
  target_id: string;
  is_default: boolean;
  is_active: boolean;
  created_at: string;
}

export interface NotificationPreferences {
  notification_mode: "immediate" | "summary" | "important_only";
  digest_interval_minutes: number;
  privacy_mode: boolean;
  notification_cutoff_hours: number;
  reminder_offsets_min: string;
  included_categories: string;
}

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = endpoint.startsWith("http") ? endpoint : `${API_BASE}${endpoint}`;
  const headers = new Headers(options.headers || {});

  if (!headers.has("Content-Type") && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(url, {
    ...options,
    headers,
    credentials: "include", // Transmit HttpOnly session cookie
  });

  if (!response.ok) {
    let errorDetail = "An unexpected error occurred.";
    try {
      const errJson = await response.json();
      errorDetail = errJson.detail || errJson.message || JSON.stringify(errJson);
    } catch {
      errorDetail = response.statusText || String(response.status);
    }
    throw new ApiError(response.status, errorDetail);
  }

  // Handle empty responses
  if (response.status === 204) {
    return {} as T;
  }

  try {
    return (await response.json()) as T;
  } catch {
    return {} as T;
  }
}

export const api = {
  // Auth
  register: (body: { email: string; password: string; full_name?: string }) =>
    request<{ message: string; user_id: string; verification_token?: string }>("/auth/register", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  login: (body: { email: string; password: string }) =>
    request<{ message: string; mfa_required: boolean; user?: User }>("/auth/login", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  logout: () =>
    request<{ message: string }>("/auth/logout", {
      method: "POST",
    }),

  getMe: () => request<User>("/auth/me"),

  verifyEmail: (token: string) =>
    request<{ message: string }>("/auth/verify-email", {
      method: "POST",
      body: JSON.stringify({ token }),
    }),

  forgotPassword: (email: string) =>
    request<{ message: string; reset_token?: string }>("/auth/forgot-password", {
      method: "POST",
      body: JSON.stringify({ email }),
    }),

  resetPassword: (body: { token: string; new_password: string }) =>
    request<{ message: string }>("/auth/reset-password", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  // MFA
  enrollMFA: () =>
    request<{ secret: string; provisioning_uri: string; qr_code: string }>("/auth/mfa/enroll", {
      method: "POST",
    }),

  confirmMFA: (code: string) =>
    request<{ message: string; recovery_codes: string[] }>("/auth/mfa/confirm", {
      method: "POST",
      body: JSON.stringify({ code }),
    }),

  challengeMFA: (code: string) =>
    request<{ message: string; user: User }>("/auth/mfa/challenge", {
      method: "POST",
      body: JSON.stringify({ code }),
    }),

  recoveryMFA: (recovery_code: string) =>
    request<{ message: string; user: User }>("/auth/mfa/recovery", {
      method: "POST",
      body: JSON.stringify({ recovery_code }),
    }),

  disableMFA: (password: string) =>
    request<{ message: string }>("/auth/mfa/disable", {
      method: "POST",
      body: JSON.stringify({ password }),
    }),

  // Sessions
  getSessions: () => request<SessionInfo[]>("/auth/sessions"),
  revokeSession: (id: string) =>
    request<{ message: string }>(`/auth/sessions/${id}`, { method: "DELETE" }),
  revokeAllSessions: () =>
    request<{ message: string }>("/auth/sessions/revoke-all", { method: "POST" }),

  // Emails
  getEmails: (params: { limit?: number; skip?: number; category?: string; sender?: string }) => {
    const q = new URLSearchParams();
    if (params.limit) q.set("limit", String(params.limit));
    if (params.skip) q.set("skip", String(params.skip));
    if (params.category) q.set("category", params.category);
    if (params.sender) q.set("sender", params.sender);
    return request<{ emails: EmailRecord[]; total: number; limit: number; skip: number }>(
      `/emails?${q.toString()}`
    );
  },
  getEmail: (id: string) => request<EmailRecord>(`/emails/${id}`),

  // Reminders
  getReminders: (params: { limit?: number; skip?: number; status?: string }) => {
    const q = new URLSearchParams();
    if (params.limit) q.set("limit", String(params.limit));
    if (params.skip) q.set("skip", String(params.skip));
    if (params.status) q.set("status", params.status);
    return request<{ reminders: ReminderRecord[]; total: number; limit: number; skip: number }>(
      `/reminders?${q.toString()}`
    );
  },
  resendReminder: (id: string) =>
    request<{ id: string; status: string; message: string }>(`/reminders/${id}/resend`, {
      method: "POST",
    }),

  // Notifications
  getNotifications: (params: { limit?: number; skip?: number; channel?: string; status?: string }) => {
    const q = new URLSearchParams();
    if (params.limit) q.set("limit", String(params.limit));
    if (params.skip) q.set("skip", String(params.skip));
    if (params.channel) q.set("channel", params.channel);
    if (params.status) q.set("status", params.status);
    return request<{ deliveries: NotificationDeliveryRecord[]; total: number; limit: number; skip: number }>(
      `/notifications?${q.toString()}`
    );
  },

  // Integrations
  getGmailConnections: () => request<GmailConnection[]>("/integrations/gmail"),
  getGmailAuthUrl: () => request<{ auth_url: string }>("/integrations/gmail/auth-url"),
  disconnectGmail: (id: string) =>
    request<{ message: string }>(`/integrations/gmail/${id}`, { method: "DELETE" }),
  triggerSync: () => request<{ status: string; message: string }>("/sync", { method: "POST" }),

  getNotificationIntegrations: () =>
    request<NotificationIntegration[]>("/integrations/notifications"),
  createNotificationIntegration: (body: {
    type: "telegram" | "whatsapp";
    name: string;
    target_id: string;
    is_default?: boolean;
  }) =>
    request<NotificationIntegration>("/integrations/notifications", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  deleteNotificationIntegration: (id: string) =>
    request<{ message: string }>(`/integrations/notifications/${id}`, { method: "DELETE" }),
  testNotificationIntegration: (id: string) =>
    request<{ message: string }>(`/integrations/notifications/${id}/test`, { method: "POST" }),

  getPreferences: () => request<NotificationPreferences>("/integrations/preferences"),
  updatePreferences: (body: Partial<NotificationPreferences>) =>
    request<NotificationPreferences>("/integrations/preferences", {
      method: "PUT",
      body: JSON.stringify(body),
    }),
};

