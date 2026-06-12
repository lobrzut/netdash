#!/usr/bin/env bash
# NetDash remote discovery agent — one-liner install (homelab .201 → QNAP .150)
set -euo pipefail

NETDASH_URL="${NETDASH_URL:-http://192.168.1.150:18787}"
NETDASH_USER="${NETDASH_USER:-admin}"
NETDASH_PASSWORD="${NETDASH_PASSWORD:-changeme}"
SCAN_CIDR="${SCAN_CIDR:-192.168.1.0/24}"
INTERVAL="${INTERVAL:-600}"
REPO="${NETDASH_REPO:-https://github.com/lobrzut/netdash.git}"
INSTALL_DIR="${NETDASH_AGENT_DIR:-/opt/netdash-agent}"

echo "[netdash-agent] NetDash: ${NETDASH_URL}"
echo "[netdash-agent] Scan: ${SCAN_CIDR} every ${INTERVAL}s"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required. Install Docker first." >&2
  exit 1
fi

if [ ! -d "${INSTALL_DIR}/.git" ]; then
  git clone --depth 1 "${REPO}" "${INSTALL_DIR}"
else
  git -C "${INSTALL_DIR}" pull --ff-only
fi

cd "${INSTALL_DIR}/deploy/agent"
export NETDASH_URL NETDASH_USER NETDASH_PASSWORD SCAN_CIDR INTERVAL
docker compose up -d --build

echo "[netdash-agent] Started. Logs: docker logs -f netdash-agent"
echo "[netdash-agent] One-shot test: docker compose run --rm netdash-agent python3 /agent/netdash-agent.py --once"
