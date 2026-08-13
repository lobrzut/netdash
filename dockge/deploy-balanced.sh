#!/usr/bin/env bash
# NetDash — zbalansowany deploy na Proxmox VM (2 GB RAM, Dockge)
# Uruchom na VM: bash dockge/deploy-balanced.sh
set -euo pipefail

STACK_DIR="${NETDASH_STACK_DIR:-/opt/stacks/netdash}"
cd "$STACK_DIR"

if [ ! -f dockge/compose.yaml ]; then
  echo "Brak dockge/compose.yaml w $STACK_DIR" >&2
  exit 1
fi

if [ ! -f .env ]; then
  cp .env.example .env
  SECRET_KEY="$(openssl rand -base64 32 2>/dev/null | tr -d '/+=' | head -c 43 || head -c 48 /dev/urandom | base64 | tr -d '/+=' | head -c 43)"
  sed -i "s/^NETDASH_SECRET_KEY=.*/NETDASH_SECRET_KEY=${SECRET_KEY}/" .env
fi

# Zbalansowany profil — dashboard + skan na żądanie (bez ciągłego TCP)
apply_env() {
  local key="$1" val="$2"
  if grep -q "^${key}=" .env 2>/dev/null; then
    sed -i "s|^${key}=.*|${key}=${val}|" .env
  else
    echo "${key}=${val}" >> .env
  fi
}

apply_env NETDASH_SCAN_CIDR "192.168.1.0/24"
apply_env NETDASH_DISCOVERY_POLICY "on_demand"
apply_env NETDASH_DISCOVERY_ENABLED "false"
apply_env NETDASH_DISCOVERY_MODE "local"
apply_env NETDASH_DISCOVERY_PROFILE "weak"
apply_env NETDASH_STARTUP_ENRICH_ENABLED "false"
apply_env NETDASH_WEAK_DUAL_CHUNK "false"
apply_env NETDASH_AUTO_DISCOVERY_ALL_PORTS "false"
apply_env NETDASH_AUTO_DISCOVERY_ALWAYS_CHUNK "true"
apply_env NETDASH_SCAN_SAFE_MODE "true"
apply_env NETDASH_SCAN_PORT_PROFILE "popular"
apply_env NETDASH_IMAGE_TAG "latest"

echo "Pobieranie obrazu i start..."
docker compose -f dockge/compose.yaml pull netdash
docker compose -f dockge/compose.yaml up -d netdash

echo "Czekam na health (max 90 s)..."
for i in $(seq 1 30); do
  if curl -sf --max-time 5 http://127.0.0.1:18787/api/health >/dev/null 2>&1; then
    echo "OK:"
    curl -s http://127.0.0.1:18787/api/health
    exit 0
  fi
  sleep 3
done

echo "Health check nie przeszedł — logi:" >&2
docker compose -f dockge/compose.yaml logs --tail 30 netdash >&2
exit 1
