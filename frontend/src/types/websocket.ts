/**
 * TypeScript definitions for WebSocket real-time events, envelopes, and payloads.
 */

export type WebSocketConnectionState =
  | "connecting"
  | "connected"
  | "reconnecting"
  | "disconnected";

export type WebSocketEventType =
  | "connection.established"
  | "email.received"
  | "email.classified"
  | "reminder.created"
  | "reminder.updated"
  | "reminder.due_soon"
  | "notification.queued"
  | "notification.sent"
  | "notification.failed"
  | "gmail.sync.started"
  | "gmail.sync.completed"
  | "gmail.sync.failed"
  | "system.error";

export interface WebSocketEnvelope<T = any> {
  event: WebSocketEventType;
  event_id: string;
  timestamp: string;
  data: T;
}

export interface ConnectionEstablishedData {
  user_id: string;
  connection_id: string;
  connected_at: string;
  heartbeat_interval_seconds: number;
  supported_events: string[];
}

export interface EmailReceivedData {
  email_id: string;
  subject: string;
  sender: string;
  category?: string;
  received_at: string;
  has_deadline: boolean;
}

export interface EmailClassifiedData {
  email_id: string;
  category: string;
  confidence_score: number;
  extracted_deadline?: string | null;
}

export interface ReminderCreatedData {
  reminder_id: string;
  email_id: string;
  scheduled_at: string;
  message_preview?: string;
  status: "pending" | "sent" | "failed";
}

export interface ReminderUpdatedData {
  reminder_id: string;
  email_id?: string;
  scheduled_at?: string;
  status: "pending" | "sent" | "failed" | "cancelled";
  retry_count: number;
  last_error?: string | null;
}

export interface ReminderDueSoonData {
  reminder_id: string;
  email_id?: string;
  scheduled_at: string;
  minutes_remaining: number;
}

export interface NotificationQueuedData {
  notification_id: string;
  email_id?: string;
  channel: "telegram" | "whatsapp";
  notification_type: string;
}

export interface NotificationSentData {
  notification_id: string;
  email_id?: string;
  channel: "telegram" | "whatsapp";
  sent_at: string;
}

export interface NotificationFailedData {
  notification_id: string;
  email_id?: string;
  channel: "telegram" | "whatsapp";
  error: string;
}

export interface GmailSyncStartedData {
  account_id: string;
  email: string;
  started_at: string;
}

export interface GmailSyncCompletedData {
  account_id: string;
  email: string;
  new_messages_count: number;
  completed_at: string;
}

export interface GmailSyncFailedData {
  account_id: string;
  email: string;
  error: string;
  failed_at: string;
}

export interface SystemErrorData {
  error_code: string;
  message: string;
  timestamp: string;
}

