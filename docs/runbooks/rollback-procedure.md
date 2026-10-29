# Runbook: Rollback Procedures

This runbook describes the emergency rollback procedures for the backend (VPS) and frontend (Vercel) services in the event of an unexpected release defect.

---

## 1. Frontend Rollback (Vercel)

Vercel provides zero-downtime, instantaneous deployment rollbacks without rebuilding:

1. Open your project in the [Vercel Dashboard](https://vercel.com/).
2. Navigate to the **Deployments** tab.
3. Locate the previous stable production deployment.
4. Click the three dots (`...`) on the right side of the stable deployment row.
5. Click **Instant Rollback**.
6. Confirm the rollback. The previous build will be instantly promoted to production traffic within seconds.

---

## 2. Backend Service Rollback (VPS)

If a new backend container version causes failures:

### 2.1 Revert to Previous Git Commit
```bash
cd /opt/gmail-reminder

# Inspect recent deployment commits
git log --oneline -n 5

# Check out the last known stable tag or commit
git checkout <PREVIOUS_STABLE_COMMIT_HASH>
```

### 2.2 Rollback Database Migration (If Required)
If the new release applied a schema migration that needs to be reverted:
```bash
# Check current migration revision
docker compose exec backend alembic current

# Downgrade one revision (or to a specific revision ID)
docker compose exec backend alembic downgrade -1

# Verify current revision after downgrade
docker compose exec backend alembic current
```

### 2.3 Rebuild & Restart Containers
```bash
docker compose -f docker-compose.vps.yml up -d --build
```

### 2.4 Verify Service Health
```bash
curl -I http://127.0.0.1:8000/ready
# Expected: HTTP/1.1 200 OK
```

---

## 3. Disaster Recovery: Database Restore

If data corruption occurred during a release, restore from the latest snapshot:

```bash
# 1. Stop background worker to prevent writes during restore
docker compose stop backend

# 2. Restore PostgreSQL database dump
cat /opt/gmail-reminder/backups/db_backup_LATEST.sql | docker compose exec -T postgres psql -U gmail_user -d gmail_reminder

# 3. Restart backend
docker compose start backend

# 4. Verify data integrity
curl http://127.0.0.1:8000/api/v1/health
```

