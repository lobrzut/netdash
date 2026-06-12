#!/usr/bin/env bash
# Deploy NetDash to a Linux server via rsync + docker compose.
# From Windows: set BRAIN_SSH_HOST, BRAIN_SSH_PASSWORD, BRAIN_SSH_HOSTKEY and run deploy/install.ps1
set -euo pipefail

REMOTE_HOST="${BRAIN_SSH_HOST:-${NETDASH_SSH_HOST:-}}"
REMOTE_DIR="${NETDASH_REMOTE_DIR:-/opt/netdash}"

if [[ -z "$REMOTE_HOST" ]]; then
  echo "Set NETDASH_SSH_HOST or BRAIN_SSH_HOST (e.g. user@your-server)" >&2
  exit 1
fi

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SSH_OPTS=(-o StrictHostKeyChecking=accept-new)

if [[ -n "${BRAIN_SSH_HOSTKEY:-}" ]]; then
  SSH_OPTS+=(-o "HostKeyAlgorithms=${BRAIN_SSH_HOSTKEY%% *}")
fi

echo "→ Syncing NetDash to ${REMOTE_HOST}:${REMOTE_DIR}"
ssh "${SSH_OPTS[@]}" "$REMOTE_HOST" "mkdir -p ${REMOTE_DIR}/data"

rsync -avz --delete \
  --exclude '.git' \
  --exclude 'data/' \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  --exclude '.env' \
  -e "ssh ${SSH_OPTS[*]}" \
  "$ROOT/" "${REMOTE_HOST}:${REMOTE_DIR}/"

echo "→ Building and starting container"
ssh "${SSH_OPTS[@]}" "$REMOTE_HOST" bash -s <<REMOTE
set -euo pipefail
cd ${REMOTE_DIR}
if [[ ! -f .env ]]; then
  cp .env.example .env
  if command -v openssl >/dev/null 2>&1; then
    SECRET_KEY="$(openssl rand -base64 32 | tr -d '/+=' | head -c 43)"
  else
    SECRET_KEY="$(head -c 48 /dev/urandom | base64 | tr -d '/+=' | head -c 43)"
  fi
  sed -i "s/^NETDASH_SECRET_KEY=.*/NETDASH_SECRET_KEY=${SECRET_KEY}/" .env
  echo "→ Utworzono .env (login: admin / changeme — zmień hasło po pierwszym logowaniu)"
fi
docker compose pull 2>/dev/null || true
docker compose build --pull
docker compose up -d
docker compose ps
echo "NetDash: http://\$(hostname -I | awk '{print \$1}'):\${NETDASH_PORT:-18787}"
REMOTE

echo "✓ Deploy complete"
