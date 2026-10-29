# Runbook: Monitoring and Health Checks

This runbook defines the observability strategy and monitoring procedures for the Gmail-to-WhatsApp-and-Telegram system.

---

## 1. Health & Readiness Endpoints

The backend provides built-in endpoints for container health probes and uptime monitoring:

| Endpoint | Purpose | Expected Status | Response |
| :--- | :--- | :--- | :--- |
| `GET /health` | Liveness check (process responsive) | `200 OK` | `{"status": "ok"}` |
| `GET /ready` | Readiness check (database and worker healthy) | `200 OK` | `{"status": "ready", "database": "connected"}` |

### Configuration with Uptime Robot / Better Uptime
1. Target: `https://api.yourdomain.com/ready`
2. Interval: 60 seconds
3. Expected Status Code: `200`
4. Alert Contacts: Email, Telegram alert webhook, or PagerDuty.

---

## 2. Docker Container Monitoring

On the VPS, verify container health:
```bash
# Check container status
docker ps --filter "name=gmail-reminder"

# Inspect resource consumption
docker stats gmail-reminder-backend gmail-reminder-postgres

# Follow backend logs
docker logs -f gmail-reminder-backend --tail 100
```

---

## 3. Key Metrics & Alert Thresholds

| Metric | Warning Threshold | Critical Threshold | Action Required |
| :--- | :--- | :--- | :--- |
| **API Error Rate (5xx)** | > 2% over 5 min | > 5% over 5 min | Check `/logs/app.log` for unhandled exceptions |
| **Failed Logins** | > 10 / min from single IP | > 30 / min | Rate-limiter auto-blocks; inspect `/api/v1/auth/login` |
| **Gmail Sync Failures** | 1 failure | 3 consecutive failures | Check token expiration / Google API quotas |
| **Telegram / WhatsApp Delivery Failures** | > 5 failures | > 15 failures | Inspect channel readiness and bridge connectivity |
| **Disk Space** | < 20% free | < 10% free | Prune rotated logs and run `docker system prune` |

---

## 4. Log Inspection

Application logs are structured in JSON format with sensitive information (OAuth tokens, passwords, Telegram bot tokens) automatically redacted.

```bash
# Filter error events in production logs
grep '"level": "ERROR"' /opt/gmail-reminder/logs/app.log | jq .

# Monitor real-time audit trail
docker exec gmail-reminder-backend tail -f logs/app.log
```

