# API Reference

The FastAPI backend exposes RESTful endpoints on port `8000`.

Interactive OpenAPI documentation is available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

---

## Authentication

Administrative endpoints under `/api/v1/*` require an API Key when `API_KEY` is configured in `.env`.
Pass the key in the HTTP header:
```http
X-API-Key: your-api-key
```
Or via Bearer token:
```http
Authorization: Bearer your-api-key
```

---

## 1. System Health & Readiness

### `GET /health`
Returns high-level system health, active destination readiness, and pending reminders count.
- **Auth:** None (Public)
- **Response (200 OK):**
```json
{
  "status": "ok",
  "time": "2026-10-29T14:45:00Z",
  "version": "2.0.0",
  "destinations": [
    {
      "id": "dest-uuid",
      "name": "Class Group",
      "type": "telegram",
      "ready": true
    }
  ],
  "pending_reminders": 2
}
```

### `GET /ready`
Readiness probe verifying database connectivity, token storage, and messaging bridges.
- **Auth:** None (Public)
- **Response (200 OK or 503 Service Unavailable):**
```json
{
  "ready": true,
  "checks": {
    "database": true,
    "tokens_storage": true,
    "telegram": true,
    "whatsapp": true
  },
  "timestamp": "2026-10-29T14:45:00Z"
}
```

---

## 2. Google OAuth 2.0

### `GET /auth/google/login`
Initiates Google OAuth flow and redirects caller to Google's consent screen.
- **Auth:** None (Public)

### `GET /auth/google/callback?code={code}`
Handles OAuth redirection, securely encrypts and stores access/refresh tokens, registers the mailbox account, and redirects to dashboard.
- **Auth:** None (Public)

---

## 3. Email Management (V1)

### `GET /api/v1/emails`
List processed email records with pagination and filters.
- **Auth:** `X-API-Key`
- **Query Parameters:**
  - `limit` (int, default 50, max 100)
  - `skip` (int, default 0)
  - `category` (string, optional)
  - `sender` (string, optional)
- **Response (200 OK):**
```json
{
  "emails": [
    {
      "id": "email-uuid",
      "gmail_message_id": "18928abc123",
      "gmail_thread_id": "thread-123",
      "sender": "prof.smith@uni.edu",
      "subject": "CS500 Homework 2 Due Date",
      "received_at": "2026-10-29T10:00:00Z",
      "category": "Academics and assignments",
      "extracted_deadline": "2026-11-05T23:59:00Z",
      "confidence_score": 0.95,
      "ambiguous_date": false,
      "plain_body": "Submission deadline is 5 Nov 2026 at 11:59 PM.",
      "processing_status": "completed",
      "created_at": "2026-10-29T10:05:00Z"
    }
  ],
  "total": 1,
  "limit": 50,
  "skip": 0
}
```

### `GET /api/v1/emails/{id}`
Retrieve a single authorized email record.
- **Auth:** `X-API-Key`

### `POST /api/v1/sync`
Trigger an immediate email synchronization across active accounts.
- **Auth:** `X-API-Key`
- **Response (200 OK):**
```json
{
  "status": "triggered",
  "message": "Email synchronization scheduled for 1 active account(s)."
}
```

---

## 4. Reminders (V1)

### `GET /api/v1/reminders`
List scheduled and sent reminders.
- **Auth:** `X-API-Key`
- **Query Parameters:**
  - `status` (string, optional: `pending`, `sent`, `failed`)
  - `limit` (int, default 50)
  - `skip` (int, default 0)

### `POST /api/v1/reminders/{id}/resend`
Force immediate retry/resend of a reminder.
- **Auth:** `X-API-Key`
- **Response (200 OK):**
```json
{
  "id": "reminder-uuid",
  "status": "sent",
  "message": "Reminder delivered successfully"
}
```

---

## 5. Notifications (V1)

### `POST /api/v1/notifications/test`
Send a manual test notification to verify channel delivery.
- **Auth:** `X-API-Key`
- **Request Body:**
```json
{
  "channel": "telegram",
  "destination_id": "-100123456789",
  "message": "🔔 Test notification from Gmail Reminder System"
}
```
- **Response (200 OK):**
```json
{
  "status": "sent",
  "channel": "telegram",
  "destination_id": "-100123456789"
}
```

### `GET /api/v1/notifications`
View delivery audit log and history.
- **Auth:** `X-API-Key`
- **Query Parameters:**
  - `channel` (optional)
  - `status` (optional)

---

## 6. Configuration (V1)

### `GET /api/v1/config`
View non-secret system settings. Credentials and tokens are redacted.
- **Auth:** `X-API-Key`
- **Response (200 OK):**
```json
{
  "google_client_id_configured": true,
  "google_redirect_uri": "http://127.0.0.1:8000/auth/google/callback",
  "poll_interval_seconds": 120,
  "historical_sync_days": 7,
  "dry_run": false,
  "notification_mode": "immediate",
  "digest_interval_minutes": 60,
  "privacy_mode": false,
  "notification_cutoff_hours": 24,
  "gmail_include_labels": ["INBOX"],
  "gmail_exclude_labels": ["SENT", "SPAM", "TRASH"],
  "whatsapp_provider": "webjs",
  "whatsapp_configured": true,
  "telegram_configured": true,
  "llm_provider_configured": null,
  "reminder_offsets_minutes": [1440, 360, 60]
}
```
