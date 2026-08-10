# Gmail → WhatsApp/Telegram Group Reminder System

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)
[![Node.js 20](https://img.shields.io/badge/Node.js-20-green.svg)](https://nodejs.org/)
[![MongoDB 7](https://img.shields.io/badge/MongoDB-7-green.svg)](https://www.mongodb.com/)

A production-ready open-source system that monitors one or more university/organization Gmail inboxes, classifies incoming announcements, extracts deadlines, posts scheduled reminders into any number of WhatsApp/Telegram groups (routed by account and category), and optionally syncs deadlines to Google/Outlook Calendar.

---

## ⚠️ Read this before you deploy — WhatsApp API modes

This system supports **two WhatsApp integration modes** (set via `WHATSAPP_API_MODE` in `.env`):

### Mode 1: `webjs` — whatsapp-web.js (default)
Automates a real WhatsApp Web session. **The only way to post into groups.**
* **Violates WhatsApp's Terms of Service.** Automated accounts can be banned with no appeal process, and Meta doesn't publish exact detection triggers.
* Requires keeping a logged-in browser session alive continuously (QR-code pairing once, then persisted).
* Should be run on a number you can afford to lose — **not** your primary personal number.

### Mode 2: `meta` — WhatsApp Business Cloud API (official)
Uses the official Meta Graph API. **Fully ToS-compliant**, no ban risk.
* **Cannot post to groups** — only supports 1:1 business-initiated messages.
* Requires a [Meta Business account](https://business.facebook.com/) and a WhatsApp Business API app on the [Meta Developer Portal](https://developers.facebook.com/).
* Messages to users outside a 24-hour session window require pre-approved **message templates**.

*Note: Telegram groups have none of these problems. The Telegram Bot API supports group posting natively without session or ban risks. Telegram, WhatsApp (WebJS), and WhatsApp (Meta) are all supported side by side.*

---

## Monorepo Project Layout

```
gmail-reminder/
├── backend/            # Python FastAPI backend (app logic, parsing, schedule)
├── frontend/           # Static Admin Dashboard UI (HTML, CSS, JS)
├── whatsapp-bridge/    # Node.js express server managing WhatsApp sessions
├── docs/               # In-depth architectural & API references
├── docker-compose.yml  # Config to run the whole stack in one go
└── README.md           # This file
```

---

## Features

- **Multiple Gmail accounts:** Connect as many mailboxes as you want; each is polled independently with its own OAuth token.
- **Multiple WhatsApp/Telegram groups:** Routed by account and category combinations, with fan-out support and a default destination fallback.
- **Unified Control Panel:** A clean dashboard to check system health, pair WhatsApp via QR code, set up routing rules, and view reminder history.
- **Google Calendar sync:** Per-mailbox opt-in using the connected mailbox's token.
- **Outlook Calendar sync:** One shared calendar connection to push all deadline events to a Microsoft 365 or Outlook calendar.

---

## Setup & Running

For complete setup guides, check out:
- [System Architecture](docs/architecture.md)
- [Step-by-Step Setup Guide](docs/setup-guide.md)
- [API Reference](docs/api-reference.md)

### Quick Start with Docker

1. Setup Google OAuth Credentials (see [Setup Guide](docs/setup-guide.md)).
2. Run the interactive setup script to prepare local directories and copy configuration:
   - On Windows: Run `setup.bat`
   - On Linux/Mac: Run `./setup.sh`
   *(This copies `.env.example` to `.env` and initializes `tokens/` and `whatsapp-bridge/session/` folders).*

3. Run the stack:
   ```bash
   docker-compose up --build
   ```
4. Access the dashboard at `http://localhost:8000/dashboard`.

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
