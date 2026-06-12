#!/usr/bin/env bash
# NetDash watchdog — restart container when /api/health fails.
set -euo pipefail

NETDASH_DIR="${NETDASH_DIR:-/opt/netdash}"
HEALTH_URL="${NETDASH_HEALTH_URL:-http://127.0.0.1:${NETDASH_LISTEN_PORT:-18787}/api/health}"
LOG_TAG="netdash-watchdog"

if curl -sf --max-time 10 "$HEALTH_URL" >/dev/null; then
  exit 0
fi

logger -t "$LOG_TAG" "Health check failed — restarting NetDash in ${NETDASH_DIR}"
cd "$NETDASH_DIR"
docker compose up -d --remove-orphans
sleep 5
if curl -sf --max-time 15 "$HEALTH_URL" >/dev/null; then
  logger -t "$LOG_TAG" "NetDash recovered after restart"
  exit 0
fi

logger -t "$LOG_TAG" "NetDash still unhealthy after restart"
exit 1
