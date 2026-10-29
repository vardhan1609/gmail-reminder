# Runbook: Security Incident Response & Key Rotation

This document outlines standard response procedures for compromised credentials, token revocation, key rotation, and communication outages.

---

## 1. Compromised Secrets Rotation

### 1.1 Rotate Telegram Bot Token
If the Telegram bot token is leaked:
1. Open Telegram and message `@BotFather`.
2. Send `/revoke` and select your alert bot.
3. Copy the newly generated token.
4. Update `.env` on your VPS:
   ```ini
   TELEGRAM_BOT_TOKEN=new_token_here
   ```
5. Restart backend:
   ```bash
   docker compose -f docker-compose.vps.yml restart backend
   ```

### 1.2 Rotate Google OAuth Client Secret
If the Google client secret is compromised:
1. Open [Google Cloud Console](https://console.cloud.google.com/) → **APIs & Services** → **Credentials**.
2. Click your OAuth 2.0 Web Client.
3. Click **Reset Secret**.
4. Update `.env` with the new `GOOGLE_CLIENT_SECRET`.
5. Restart the backend container.

### 1.3 Rotate `SECRET_KEY` & `GOOGLE_TOKEN_ENCRYPTION_KEY`
If application secret keys need to be refreshed:
1. Generate new keys:
   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```
2. Update `.env`.
3. Existing active sessions will be invalidated and users will need to re-authenticate (Argon2id password hashes remain secure).

---

## 2. Emergency Account Lockdown (Brute-Force Attack)

If an account experiences a coordinated brute-force attack:
1. The built-in rate limiter automatically blocks IP and email pairs exceeding 5 failed attempts for 15 minutes.
2. An administrator can immediately revoke all sessions for a user:
   ```bash
   docker compose exec backend python -c "
   from app.database.session import SessionLocal
   from app.models.db_models import UserSessionModel, UserModel
   with SessionLocal() as db:
       u = db.query(UserModel).filter(UserModel.email == 'target_user@example.com').first()
       if u:
           db.query(UserSessionModel).filter(UserSessionModel.user_id == u.id).delete()
           db.commit()
           print('All sessions revoked for user')
   "
   ```

---

## 3. WhatsApp Bridge Reconnect & Session Reset

If the WhatsApp Web.js session disconnects or is revoked on the phone:
1. Clear the stale session data:
   ```bash
   docker compose exec backend rm -rf /app/whatsapp-bridge/session/*
   ```
2. Restart the backend or bridge:
   ```bash
   docker compose -f docker-compose.vps.yml restart backend
   ```
3. Check the logs and scan the new QR code:
   ```bash
   docker logs -f gmail-reminder-backend | grep -i qr
   ```
