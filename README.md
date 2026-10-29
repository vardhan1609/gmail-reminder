# Gmail → WhatsApp & Telegram Notification System (Multi-User Web App)

A production-grade, multi-user web application and background automation platform that connects to university Google Workspace or personal Gmail accounts using OAuth 2.0, continuously monitors all incoming emails, extracts useful categories and verified deadlines, and delivers notifications through both **WhatsApp** and **Telegram**.

Includes a complete **Next.js (React + TypeScript + Tailwind CSS)** responsive frontend, **Argon2id** password hashing, **RFC 6238 TOTP Multi-Factor Authentication (2FA)** with single-use recovery codes, strict user-tenant isolation (IDOR protection), server-managed HttpOnly sessions, Alembic database migrations, and 100% passing automated test suites.

---

## Key Features

### 1. Multi-User Architecture & Security
- **Independent User Accounts:** Register with email and strong password validation (Argon2id hashing).
- **Email Verification:** Single-use cryptographic verification tokens with expiration.
- **Two-Factor Authentication (TOTP):** Compatible with standard authenticator apps (Google Authenticator, Authy, 1Password) with dynamic QR code generation and 10 hashed single-use recovery backup codes.
- **Session Management:** Opaque 256-bit session tokens stored via SHA-256 hashes in the database and delivered in secure `HttpOnly`, `SameSite=Lax` cookies.
- **Strict Data Isolation & IDOR Prevention:** Every mailbox connection, email record, deadline reminder, and notification destination is user-owned and protected by server-side authorization checks.
- **Password Recovery:** Expiring reset tokens with replay prevention and complete session invalidation upon password updates.

### 2. Next.js Frontend Application
- **Modern Stack:** Next.js 14, React 18, TypeScript, Tailwind CSS, Lucide icons.
- **Responsive Layout:** Desktop, tablet, and mobile layouts with loading skeletons, empty states, error retry states, and confirmation dialogs.
- **Complete Route Architecture:**
  - Public: `/`, `/signup`, `/login`, `/verify-email`, `/forgot-password`, `/reset-password`, `/mfa/challenge`, `/mfa/recovery`
  - Authenticated: `/dashboard`, `/dashboard/emails`, `/dashboard/reminders`, `/dashboard/notifications`, `/dashboard/integrations`, `/dashboard/settings`, `/dashboard/security`, `/dashboard/sessions`

### 3. Inclusive Email Processing & Multi-Channel Delivery
- **All 11 Categories Supported:** Academics & Assignments, Examinations & Results, Placements & Internships, Fees & Payments, Meetings & Events, Personal Messages, Bills & Receipts, Travel & Bookings, Newsletters & Promotions, Security Alerts, and Other.
- **Deadline Extraction & Reminders:** Distinguishes explicit deadlines from event and email dates, with automated reminder schedules (24h, 6h, 1h). Ambiguous dates are flagged for review.
- **Dual Independent Channels:** Independent WhatsApp and Telegram adapters with failure isolation, idempotency keys, and exponential backoff retry.
- **Notification Safeguards:** Historical import cutoff (`NOTIFICATION_CUTOFF_HOURS`) to prevent notification storms, and configurable `Privacy Mode` to protect email bodies in group chats.

---

## Architecture Overview

```
Google Workspace Gmail (OAuth 2.0)
       |
       v
 Gmail API Connector (History API + Fallback)
       |
       v
 Email Normalization & Deduplication (MIME + HTML Sanitizer)
       |
       v
 Email Processing Pipeline (11 Categories + Deadline Extractor)
       |
       v
 Database (PostgreSQL / SQLite with Alembic Migrations)
       |
       +---> Multi-Tenant Auth & Sessions (Argon2id + TOTP MFA)
       |
       v
 Reminder Scheduler & Background Worker
    |                     |
    v                     v
WhatsApp Adapter      Telegram Bot Adapter
    |                     |
Configured Recipient   Configured Telegram Group/Chat

       ^
       | REST API (HttpOnly Cookies / Bearer)
Next.js Responsive Web App (Dashboard, Emails, Reminders, Security, Integrations)
```

---

## Automated Test Verification

All 74 backend tests pass with a 100% pass rate:
- **Specification E2E Scenarios (20/20 passed)**: Category classifications, dead-letter fallbacks, HTML sanitization, prompt injection defense, worker restarts, rate limiting.
- **Integration Tests (17/17 passed)**: Gmail history sync, pagination, OAuth flow, multi-offset reminders, Telegram/WhatsApp adapters.
- **Unit Tests (31/31 passed)**: MIME parsers, date timezones, regex deadline extractors, token redaction, idempotent deliverers.
- **Security & Multi-Tenant Tests (6/6 passed)**: Password strength enforcement, email verification token replay, failed login throttling, TOTP MFA challenge & single-use recovery codes, IDOR and cross-tenant resource isolation.

Frontend production build (`npm run build`) generates all 16 static and dynamic routes cleanly with 0 TypeScript or compilation errors.

---

## Quick Start & Deployment

### 1. Environment Configuration
```bash
cp .env.example .env
```
Fill in your Google OAuth credentials (`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`), Telegram Bot Token, and secret keys.

### 2. Run with Docker Compose (Recommended)
```bash
docker compose up --build
```
This boots:
- PostgreSQL 16 database (`port 5432`)
- FastAPI Backend (`port 8000`)
- Next.js Web App (`port 3000`)

Access the web application at `http://localhost:3000`.

### 3. Run Locally for Development

**Backend:**
```bash
cd backend
python -m pip install -r requirements.txt
python -m alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

# Install dependencies
pip install -r requirements.txt

# Apply database migrations
alembic upgrade head

# Run server
uvicorn app.main:app --reload --port 8000
```
- Open Dashboard: `http://localhost:8000/dashboard`
- Interactive API Docs: `http://localhost:8000/docs`

### 3. Docker Compose Setup
```bash
docker compose up --build -d
```

---

## Automated Tests

Run the complete test suite (68 tests covering Unit, Integration, and all 20 End-to-End Scenarios):

```bash
cd backend

# Run all tests
pytest

# Run unit tests only
pytest tests/unit

# Run integration tests only
pytest tests/integration

# Run 20 E2E scenarios only
pytest tests/e2e
```

---

## Telegram Bot Setup
1. Create a bot using [`@BotFather`](https://t.me/BotFather) and set `TELEGRAM_BOT_TOKEN` in `.env`.
2. Add your bot to your target Telegram group.
3. Supported bot commands:
   - `/start` — Welcome message
   - `/help` — Command guide and group instructions
   - `/status` — Check system readiness and connectivity
   - `/test` — Verify delivery to your chat

---

## Documentation Links

- [Setup Guide](docs/setup-guide.md): Google Cloud OAuth setup, university Workspace policies, Telegram and WhatsApp guides, troubleshooting.
- [API Reference](docs/api-reference.md): Complete REST endpoint documentation, schemas, and authentication headers.
- [Architecture Details](docs/architecture.md): Detailed component workflows and data models.
