#!/usr/bin/env bash
# Invoked by GitHub Actions via SSM. No inbound SSH port is required.
set -euo pipefail

APP_DIR="/opt/gmail-reminder"
COMPOSE_FILE="docker-compose.prod.yml"
ENV_FILE=".env.production"
LOCK_FILE="/var/lock/gmail-reminder-deploy.lock"

exec 9>"${LOCK_FILE}"
flock -n 9 || { echo "Another deployment is running."; exit 1; }

if [[ ! -d "${APP_DIR}/.git" ]]; then
  echo "Missing checkout at ${APP_DIR}. Run ops/aws/bootstrap.sh first." >&2
  exit 1
fi
if [[ ! -f "${APP_DIR}/${ENV_FILE}" ]]; then
  echo "Missing ${APP_DIR}/${ENV_FILE}. Populate production secrets first." >&2
  exit 1
fi

cd "${APP_DIR}"
git fetch --prune origin main
git checkout main
git reset --hard origin/main

docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" config >/dev/null

# Keep the database up while migrations execute; never remove volumes.
docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" up -d postgres
docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" run --rm backend alembic upgrade head
docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" up -d --build --remove-orphans

# Basic container-state check. API health is checked separately after DNS/TLS setup.
sleep 10
if docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" ps --status running | grep -q 'gmail-reminder-backend'; then
  echo "Backend container is running."
else
  docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" ps
  docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" logs --tail=100 backend
  exit 1
fi

docker image prune -f
docker builder prune -f --filter 'until=168h'
docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" ps
