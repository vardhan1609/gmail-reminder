# Complete Setup & Operations Guide

This guide walks you through setting up, configuring, running, and troubleshooting the Gmail-to-WhatsApp-and-Telegram notification system.

---

## 1. Google Cloud Console & Workspace Gmail Setup

### 1.1 Google Cloud Project Configuration
1. Navigate to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project (e.g., `gmail-reminder-system`).
3. In **APIs & Services** > **Library**, enable:
   - **Gmail API**
   - **Google Calendar API** (optional, for calendar synchronization)

### 1.2 OAuth Consent Screen
1. Go to **APIs & Services** > **OAuth consent screen**.
2. Select **External** (unless you are a Google Workspace Administrator configuring internal organization-only access).
3. Fill in the App name, User support email, and Developer contact information.
4. Under **Scopes**, add the minimum read-only scope:
   - `https://www.googleapis.com/auth/gmail.readonly`
   - Optional: `https://www.googleapis.com/auth/calendar.events`
5. Under **Test users**, add your university email address.

### 1.3 University Google Workspace Policy Notes
> [!IMPORTANT]
> **Admin Access & Policy Constraints:**
> - Many universities and academic institutions restrict third-party OAuth applications by default.
> - If your university has enabled "Block all third-party API access", you will see:
>   `Access blocked: Your institution's admin needs to review this app`
> - If this occurs:
>   1. You may request approval from your university IT helpdesk by providing the OAuth Client ID.
>   2. Alternatively, create the project using your personal Google account and add your student account as an authorized external test user if domain policies permit.
> - The application only requests **read-only** permission (`gmail.readonly`) to protect your mailbox security. It never requests send, modify, or delete privileges.

### 1.4 OAuth Credentials
1. Go to **APIs & Services** > **Credentials**.
2. Click **Create Credentials** > **OAuth client ID**.
3. Application type: **Web application**.
4. Name: `Gmail Reminder Backend`.
5. Under **Authorized redirect URIs**, add:
   - `http://127.0.0.1:8000/auth/google/callback`
   - `http://localhost:8000/auth/google/callback`
6. Click **Create** and copy your **Client ID** and **Client Secret**.

---

## 2. Messaging Channel Setup

### 2.1 Telegram Bot Configuration
1. Open Telegram and search for [`@BotFather`](https://t.me/BotFather).
2. Send `/newbot` and follow the prompts to choose a bot name and username (must end in `bot`).
3. Copy the HTTP API token provided by BotFather. Set this as `TELEGRAM_BOT_TOKEN` in `.env`.
4. **Group Integration:**
   - Create a Telegram group or open an existing group.
   - Add your bot to the group as a member.
   - Send `/status` or `/test` in the group chat.
   - To obtain the group's numerical chat ID:
     - Visit `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates` in your browser.
     - Look for `"chat":{"id": -100xxxxxxxxxx, ...}` in the JSON response.
     - Group chat IDs are negative numbers (e.g. `-100123456789`).
     - Set this as `TELEGRAM_CHAT_ID` or register it via `POST /destinations`.

### 2.2 WhatsApp Integration Options & Limitations

| Feature | `webjs` (whatsapp-web.js) | Meta Cloud API (`meta`) | `dry_run` |
|---|---|---|---|
| **Official Support** | ❌ Unofficial (Puppeteer automation) | ✅ Officially supported by Meta | ✅ Built-in simulation |
| **Group Messaging** | ✅ Supported (Any group you belong to) | ❌ 1:1 Messages only | ✅ Simulated |
| **Setup Process** | QR Code scan via WhatsApp mobile | Meta Developer App + Token | Zero setup |
| **Operational Risk** | Risk of session invalidation or rate limits | Requires verified Meta business account | Zero risk |

- **Local WebJS Mode:**
  1. Set `WHATSAPP_PROVIDER=webjs` in `.env`.
  2. Open the dashboard at `http://localhost:8000/dashboard`.
  3. Navigate to the **WhatsApp Bridge** tab.
  4. Scan the rendered QR code with your WhatsApp app (**Settings** > **Linked Devices** > **Link a Device**).
  5. The bridge session is persisted in `whatsapp-bridge/session`.
- **Meta Cloud API Mode:**
  1. Set `WHATSAPP_PROVIDER=meta` in `.env`.
  2. Provide `WHATSAPP_PHONE_NUMBER_ID` and `WHATSAPP_BUSINESS_TOKEN`.
- **Dry-Run Mode:**
  1. Set `DRY_RUN=true` or `WHATSAPP_PROVIDER=dry_run`.
  2. Messages are formatted, logged, and tracked in the database without hitting external networks.

---

## 3. Database & Migrations

The system uses **SQLAlchemy** supporting **SQLite** (default zero-dependency file) or **PostgreSQL**.

### Run Migrations
```bash
# From backend directory:
cd backend
alembic upgrade head
```

### Rollback Migration
```bash
cd backend
alembic downgrade -1
```

---

## 4. Local Development

### 4.1 Prerequisites
- Python 3.12+
- Node.js 20+ (for WhatsApp bridge, optional if in dry-run mode)

### 4.2 Installation & Startup
```bash
# 1. Clone repository and copy environment template
cp .env.example .env

# 2. Install backend dependencies
cd backend
pip install -r requirements.txt

# 3. Apply database migrations
alembic upgrade head

# 4. Start backend server
uvicorn app.main:app --reload --port 8000
```
Visit the unified dashboard at: `http://localhost:8000/dashboard`
Interactive API Documentation: `http://localhost:8000/docs`

---

## 5. Docker Deployment

### 5.1 Docker Compose (PostgreSQL + FastAPI + WhatsApp Bridge)
```bash
# Build and start all services
docker compose up --build -d

# Check logs
docker compose logs -f backend

# Stop services
docker compose down
```

---

## 6. Running Automated Tests

The test suite contains 68 comprehensive tests covering Unit, Integration, and all 20 End-to-End Scenarios:

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

## 7. Backup, Recovery & Maintenance

### 7.1 Data to Backup
1. **Database:**
   - SQLite: Backup `gmail_reminder.db`.
   - PostgreSQL: Run `pg_dump -U gmail_user gmail_reminder > backup.sql`.
2. **Encrypted Tokens:**
   - Backup `tokens/` directory.
3. **WhatsApp Session:**
   - Backup `whatsapp-bridge/session/` (if using webjs mode).

### 7.2 Recovery
1. Restore database file or run `psql -U gmail_user gmail_reminder < backup.sql`.
2. Restore `tokens/` directory ensuring `GOOGLE_TOKEN_ENCRYPTION_KEY` matches.
3. Start the application: `uvicorn app.main:app --port 8000`.

---

## 8. Troubleshooting Guide

| Issue | Root Cause | Solution |
|---|---|---|
| `OAuth code exchange failed: invalid_client` | Incorrect Client ID or Secret | Verify `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` in `.env`. |
| `Access blocked: authorization error` | Scopes not added or user not in test users | Add your email under **Test Users** in Google Cloud Console. |
| `Telegram rate limit (429)` | Too many messages sent in a short window | Scheduler automatically applies exponential backoff retry. |
| `Telegram 403 Forbidden` | Bot was blocked by user or kicked from group | Unblock the bot or re-add it to the Telegram group. |
| `WhatsApp bridge unreachable (502)` | Node.js process failed to start or port 3000 blocked | Ensure Node.js 20+ is installed; check `logs/app.log`. |
| `Expired historyId (404/400)` | Gmail history cursor expired after 30 days | Handled automatically: sync resets cursor and performs query fallback. |
| `No such table error` | Migrations not executed | Run `cd backend && alembic upgrade head`. |
