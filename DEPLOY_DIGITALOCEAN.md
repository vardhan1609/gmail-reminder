# Deploy Gmail Reminder to a DigitalOcean Droplet

This guide uses the repository's existing FastAPI, Next.js, PostgreSQL, and embedded WhatsApp bridge. It adds a separate production Compose file; the existing development `docker-compose.yml` is left unchanged.

## 1. Create the Droplet

Recommended starting point: Ubuntu 24.04 LTS, 4 vCPU, 8 GB RAM, and at least 100 GB SSD. The WhatsApp Web bridge uses Chromium and can be memory-intensive. A smaller Droplet is suitable only for initial testing.

Create DNS A records for `app.vuvg.in` and `api.vuvg.in`, both pointing to the Droplet IPv4 address. Allow inbound TCP 22, 80, and 443 in the DigitalOcean firewall. Do not expose PostgreSQL (5432), Redis (if added later), or the API port directly.

## 2. Install Docker

SSH into the Droplet and install Docker Engine plus the Compose plugin using Docker's official Ubuntu instructions:
https://docs.docker.com/engine/install/ubuntu/

Verify:
```bash
docker --version
docker compose version
```

## 3. Clone and configure

```bash
git clone https://github.com/vardhan1609/gmail-reminder.git
cd gmail-reminder
cp .env.production.example .env.production
```

Edit `.env.production`. Set both domains, a unique PostgreSQL password, a strong application secret, a valid Fernet key for `GOOGLE_TOKEN_ENCRYPTION_KEY`, and your provider credentials. Generate random secrets with `openssl rand -hex 32`. Generate the Fernet key using Python's `cryptography.fernet.Fernet.generate_key()`.

Replace every `vuvg.in` value with your actual domain. Do not commit `.env.production`.

## 4. Configure Google OAuth

In Google Cloud Console, add the production callback URI exactly as configured in `GOOGLE_REDIRECT_URI`:
`https://api.vuvg.in/auth/google/callback`\n\nFor Google account sign-in (separate from Gmail mailbox access), also register this authorized redirect URI:\n`https://api.vuvg.in/api/v1/auth/google-sso/callback`\n\nSet `GOOGLE_SSO_REDIRECT_URI` to that exact value in `.env.production`. Both redirect URIs can be registered on the same Google OAuth web client.

Add the frontend domain to the authorized JavaScript origins if your OAuth client configuration requires it. Ensure the consent screen and Gmail scopes have the verification status appropriate for your intended users.

## 5. Build and start

Wait until both DNS records resolve to the Droplet. Then:
```bash
docker compose --env-file .env.production -f docker-compose.prod.yml config
docker compose --env-file .env.production -f docker-compose.prod.yml build
docker compose --env-file .env.production -f docker-compose.prod.yml up -d postgres
docker compose --env-file .env.production -f docker-compose.prod.yml run --rm backend alembic upgrade head
docker compose --env-file .env.production -f docker-compose.prod.yml up -d
docker compose --env-file .env.production -f docker-compose.prod.yml ps
```

Caddy obtains and renews TLS certificates automatically. Check logs:
```bash
docker compose --env-file .env.production -f docker-compose.prod.yml logs -f caddy backend frontend
```

Test:
```bash
curl -fsS https://api.vuvg.in/health
```
If the health route differs in your deployed application, inspect the FastAPI route list and use its actual health endpoint.

## 6. Important production checks

- Confirm frontend API requests use the public API origin. `NEXT_PUBLIC_API_URL` is a Next.js build-time variable, so changing it requires rebuilding the frontend image.
- Confirm the API CORS allowlist includes only the production frontend origin.
- Confirm session cookies are Secure and HttpOnly and that OAuth tokens are encrypted at rest.
- The production Compose file does not publish PostgreSQL or the FastAPI port to the host.
- The backend currently starts its scheduler from the application lifecycle. Run only one backend replica until scheduling is moved to a dedicated singleton worker with distributed locking.
- The WhatsApp Web bridge is launched only when `WHATSAPP_PROVIDER=webjs`. With `WHATSAPP_PROVIDER=meta`, the backend sends through the official Meta Cloud API and does not start the browser bridge. Meta Cloud API destinations must be individual phone numbers in the format expected by Meta, not WhatsApp group IDs.
- The PostgreSQL container is attached only to an internal Docker network. The backend has a separate outbound-capable network for Google and notification APIs.
- Test a new account end-to-end: signup, verification, login, MFA enrollment and challenge, Gmail OAuth, sync, reminder creation, and each notification channel.
- Configure off-server encrypted PostgreSQL backups and test a restore before relying on the service.

## 7. Updating the deployment

After merging the reviewed pull request into `main`, update the Droplet:
```bash
git pull origin main
docker compose --env-file .env.production -f docker-compose.prod.yml build
docker compose --env-file .env.production -f docker-compose.prod.yml run --rm backend alembic upgrade head
docker compose --env-file .env.production -f docker-compose.prod.yml up -d
docker image prune -f
```

Do not use `docker compose down -v`: it deletes persistent volumes, including the database.


## Subscription billing configuration

Set monthly plan prices in integer paise (100 paise = INR 1) in `.env.production`:

```env
PAYMENT_CURRENCY=INR
BASIC_PLAN_PRICE_PAISE=0
PREMIUM_PLAN_PRICE_PAISE=YOUR_PREMIUM_PRICE_IN_PAISE
PAYMENT_PROVIDER=razorpay
RAZORPAY_KEY_ID=
RAZORPAY_KEY_SECRET=
RAZORPAY_WEBHOOK_SECRET=
CASHFREE_APP_ID=
CASHFREE_SECRET_KEY=
CASHFREE_WEBHOOK_SECRET=
CASHFREE_ENVIRONMENT=sandbox
```

Never commit gateway secrets. Configure the selected gateway webhook to:

- Razorpay: `https://api.vuvg.in/api/v1/billing/webhooks/razorpay`
- Cashfree: `https://api.vuvg.in/api/v1/billing/webhooks/cashfree`

Use the exact webhook signing secret in the matching environment variable. The backend validates webhook signatures before granting Premium access. Test with sandbox credentials first. Checkout currently uses monthly hosted payment links (manual renewal); automatic recurring mandates/subscriptions are not enabled yet.

Basic entitlements: 1 Gmail account, Telegram, Google Calendar, 100 notifications per calendar month. Premium: 4 Gmail accounts, Telegram, Google Calendar, WhatsApp, 500 notifications per calendar month.


## Admin account bootstrap

Register the intended administrator account normally, then promote that account once using a trusted database session:

```sql
UPDATE users SET is_admin = TRUE WHERE email = 'admin@example.com';
```

Replace the email with the verified account you control. Do not expose PostgreSQL publicly. The Admin navigation and APIs are restricted to accounts with `is_admin = TRUE`.
