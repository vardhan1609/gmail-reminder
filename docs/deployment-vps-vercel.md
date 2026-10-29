# Production Deployment Guide: VPS + Vercel

This guide outlines how to deploy the **Gmail-to-WhatsApp-and-Telegram Notification System** with the Next.js frontend hosted on **Vercel** and the backend API, scheduler worker, WhatsApp bridge, and PostgreSQL database running on a **Linux VPS** (Ubuntu 22.04 / 24.04).

---

## Architecture

```
[User Browser]
      |
      +---> https://your-app.vercel.app (Next.js on Vercel Edge CDN)
      |         |
      |         | API Requests (HTTPS with SameSite=None, Secure Cookies)
      v         v
   https://api.yourdomain.com (Nginx Reverse Proxy on VPS)
                |
                +---> FastAPI Backend (:8000)
                |        +---> Gmail Monitoring Worker (continuous poll)
                |        +---> Reminder Scheduler
                |        +---> WhatsApp Bridge (:3000)
                |        +---> Telegram Dispatcher
                v
      PostgreSQL Database (:5432)
```

---

## 1. VPS Setup (Ubuntu 22.04/24.04)

### 1.1 Install Prerequisites
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git curl nginx certbot python3-certbot-nginx

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
```

### 1.2 Clone Repository & Configure Environment
```bash
git clone https://github.com/YOUR_USERNAME/gmail-reminder.git /opt/gmail-reminder
cd /opt/gmail-reminder
cp .env.example .env
nano .env
```

Set the required variables:
```ini
DATABASE_URL=postgresql://gmail_user:gmail_password@postgres:5432/gmail_reminder
SECRET_KEY=generate_with_python_secrets
GOOGLE_TOKEN_ENCRYPTION_KEY=generate_with_python_secrets
COOKIE_SECURE=true
COOKIE_SAMESITE=none
CORS_ALLOWED_ORIGINS=["https://your-app.vercel.app"]
FRONTEND_BASE_URL=https://your-app.vercel.app
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
GOOGLE_REDIRECT_URI=https://api.yourdomain.com/auth/google/callback
```

### 1.3 Start Backend Stack
```bash
docker compose -f docker-compose.vps.yml up -d --build
```

### 1.4 Configure Nginx Reverse Proxy with SSL
Create `/etc/nginx/sites-available/gmail-api`:
```nginx
server {
    server_name api.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable and obtain an SSL certificate:
```bash
sudo ln -s /etc/nginx/sites-available/gmail-api /etc/nginx/sites-enabled/
sudo certbot --nginx -d api.yourdomain.com
sudo systemctl restart nginx
```

---

## 2. Vercel Frontend Deployment

1. Push your repository to GitHub.
2. In the [Vercel Dashboard](https://vercel.com/dashboard), click **Add New** → **Project**.
3. Import your GitHub repository.
4. Set **Root Directory** to `frontend`.
5. Add the Environment Variable:
   - `NEXT_PUBLIC_API_URL` = `https://api.yourdomain.com/api/v1`
6. Click **Deploy**.

---

## 3. Google Cloud OAuth Update

In [Google Cloud Console](https://console.cloud.google.com/) under your OAuth 2.0 Client:
- **Authorized JavaScript origins:** `https://your-app.vercel.app`, `https://api.yourdomain.com`
- **Authorized redirect URIs:** `https://api.yourdomain.com/auth/google/callback`, `https://api.yourdomain.com/api/v1/integrations/gmail/callback`

