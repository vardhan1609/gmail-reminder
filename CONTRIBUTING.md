# Contributing to Gmail Reminder

Thank you for your interest in contributing to Gmail Reminder! We welcome contributions from everyone.

This project is organized as a monorepo containing:
- `/backend`: Python FastAPI app, scheduling logic, and MongoDB integration.
- `/frontend`: Responsive dashboard UI served directly by the backend.
- `/whatsapp-bridge`: Node.js Express app driving the `whatsapp-web.js` browser session or proxying to Meta.

---

## Quick Start for Development

### 1. Prerequisites
- **Python 3.12+**
- **Node.js 20+**
- **MongoDB** running locally or via Docker.
- **Google Cloud Console account** with a configured OAuth client ID.

### 2. Setup Database
Ensure MongoDB is running locally. By default, it expects to find it on `localhost:27017` with database `gmail_reminder`.

### 3. Setup Backend
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Or `.venv\Scripts\activate` on Windows
pip install -r requirements.txt
cp ../.env.example .env    # Edit values accordingly
python -m uvicorn app.main:app --reload --port 8000
```

### 4. Setup WhatsApp Bridge
```bash
cd whatsapp-bridge
npm install
npm run dev
```

---

## Coding Standards

### Backend (Python)
- Use standard type hints wherever possible.
- Lint and format your code using `ruff` or `black`.
- Keep business logic isolated within `/backend/app/services/`.

### Frontend
- Keep the design clean, responsive, and using the established dark glassmorphism system.
- Avoid using heavy JS frameworks; stick to lightweight vanilla Javascript with standard CSS variables.

### Git workflow
1. Fork the repository and create your branch from `main`.
2. Commit your changes with clear, descriptive commit messages.
3. Submit a Pull Request. Explain what changes were made, why, and how to verify them.

Thank you for helping make Gmail Reminder better!
