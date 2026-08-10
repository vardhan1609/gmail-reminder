# API Reference

The FastAPI backend exposes the following endpoints on port `8000`.

---

## Gmail Accounts

### `GET /accounts`
Returns all registered Gmail accounts.

**Response (200 OK):**
```json
[
  {
    "id": "60b9f0f9b6b7a213e4f3a9e1",
    "email": "example@gmail.com",
    "label": "Work Mailbox",
    "active": true,
    "calendar_sync_enabled": false,
    "created_at": "2026-08-01T12:00:00Z",
    "authenticated": true
  }
]
```

### `GET /accounts/gmail/login`
Redirects to Google OAuth page.

### `PATCH /accounts/{account_id}`
Updates account settings.

**Request Query Parameters:**
- `active` (boolean, optional)
- `calendar_sync_enabled` (boolean, optional)
- `label` (string, optional)

---

## Destinations

### `GET /destinations`
Lists all messaging destinations.

**Response (200 OK):**
```json
[
  {
    "id": "60b9f0f9b6b7a213e4f3a9e2",
    "type": "whatsapp",
    "name": "CS Group Chat",
    "target_id": "120363012345678901@g.us",
    "is_default": true,
    "active": true
  }
]
```

### `POST /destinations`
Creates a destination.

**Request Body:**
```json
{
  "type": "whatsapp",
  "name": "My Group Chat",
  "target_id": "120363012345678901@g.us",
  "is_default": false
}
```

---

## Routing Rules

### `GET /routing-rules`
Lists routing configuration rules.

### `POST /routing-rules`
Binds emails (optionally filtered by account/category) to a destination.

**Request Body:**
```json
{
  "destination_id": "60b9f0f9b6b7a213e4f3a9e2",
  "account_id": "60b9f0f9b6b7a213e4f3a9e1",
  "category": "Exam"
}
```

---

## Health Status

### `GET /health`
Returns system status.

**Response (200 OK):**
```json
{
  "status": "ok",
  "time": "2026-08-01T12:10:00Z",
  "destinations": [
    {
      "id": "60b9f0f9b6b7a213e4f3a9e2",
      "name": "CS Group Chat",
      "type": "whatsapp",
      "ready": true
    }
  ],
  "pending_reminders": 3
}
```
