# Step-by-Step Setup Guide

Follow this guide to get Gmail Reminder running from scratch.

---

## 1. Google Cloud Console (for Gmail Polling)
1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project.
3. Search for **Gmail API** and click **Enable**.
4. Search for **Google Calendar API** and click **Enable**.
5. Configure the **OAuth Consent Screen**:
   - Select **External**.
   - Add your developer email.
   - Under **Scopes**, add `.../auth/gmail.readonly` and `.../auth/calendar.events`.
   - Add your test Google accounts under **Test users**.
6. Go to **Credentials**:
   - Click **Create Credentials** -> **OAuth client ID**.
   - Select **Web application** as the Application type.
   - Under **Authorized redirect URIs**, add `http://127.0.0.1:8000/accounts/gmail/callback`.
   - Copy your **Client ID** and **Client Secret** into your `.env` file.

---

## 2. Configuration (.env file)
Create a `.env` file in the project root:
```env
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
GOOGLE_REDIRECT_URI=http://127.0.0.1:8000/accounts/gmail/callback
MONGO_URI=mongodb://localhost:27017
MONGO_DB=gmail_reminder
SECRET_KEY=use-a-strong-random-key

# Choose LLM provider: "anthropic", "openai", "gemini", or "ollama"
LLM_PROVIDER=openai
OPENAI_API_KEY=your-openai-api-key
OPENAI_MODEL=gpt-4o-mini
```
*Note: Leave LLM configurations blank to run the system in a lightweight offline rule-based regex mode (free).*


---

## 3. Running with Docker Compose
The easiest way to run the entire stack is using Docker Compose. Ensure you have Docker installed.

From the root directory, run:
```bash
docker-compose up --build
```
This boots up:
- **MongoDB** on `localhost:27017`
- **FastAPI Backend** on `http://localhost:8000` (which automatically spawns and manages the **WhatsApp Bridge** process inside the container)

---

## 4. Manual Setup (No Docker)

### MongoDB
Ensure you have MongoDB running locally on port 27017.

### Running Backend & WhatsApp Bridge
The backend automatically manages the lifecycle of the WhatsApp bridge. You only need to run the backend:
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Or .venv\Scripts\activate on Windows
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```
*(The FastAPI backend automatically starts `node index.js` in the background inside `/whatsapp-bridge/` on port 3000, and streams its output into your terminal with a `[WhatsApp Bridge]` prefix. When you Ctrl+C to stop the backend, it cleanly kills the bridge).*

---

## 5. Setting Up WhatsApp
1. Navigate to the dashboard at `http://localhost:8000/dashboard`.
2. Click on the **WhatsApp Bridge** tab in the sidebar nav.
3. If using `whatsapp-web.js` mode, scan the QR code using your WhatsApp app (Settings -> Linked Devices -> Link a Device).
4. If using `Meta Cloud API`, switch the mode to Meta and enter your Phone Number ID and Business Access Token.
