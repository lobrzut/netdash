#!/usr/bin/env bash
# NetDash — jedna komenda, bez git. Linux + Docker Compose v2.
#   curl -fsSL https://raw.githubusercontent.com/lobrzut/netdash/main/deploy/docker-simple/install.sh | bash
set -euo pipefail

INSTALL_DIR="${NETDASH_INSTALL_DIR:-/opt/netdash}"
REPO_RAW="https://raw.githubusercontent.com/lobrzut/netdash/main/deploy/docker-simple"

if ! command -v docker >/dev/null 2>&1; then
  echo "Brak Docker. Zainstaluj Docker i Docker Compose v2, potem uruchom ponownie." >&2
  exit 1
fi

mkdir -p "${INSTALL_DIR}/data"
cd "${INSTALL_DIR}"

echo "→ Pobieram pliki z GitHub..."
curl -fsSL "${REPO_RAW}/docker-compose.yml" -o docker-compose.yml
curl -fsSL "${REPO_RAW}/docker-compose.autoupdate.yml" -o docker-compose.autoupdate.yml
curl -fsSL "${REPO_RAW}/.env.example" -o .env.example

if [[ ! -f .env ]]; then
  echo ""
  read -rsp "Hasło administratora NetDash: " ADMIN_PASS
  echo ""
  if [[ -z "${ADMIN_PASS}" ]]; then
    echo "Hasło nie może być puste." >&2
    exit 1
  fi
  if command -v openssl >/dev/null 2>&1; then
    SECRET_KEY="$(openssl rand -base64 32 | tr -d '/+=' | head -c 43)"
  else
    SECRET_KEY="$(head -c 48 /dev/urandom | base64 | tr -d '/+=' | head -c 43)"
  fi
  cat > .env <<EOF
NETDASH_SECRET_KEY=${SECRET_KEY}
NETDASH_DEFAULT_ADMIN_PASSWORD=${ADMIN_PASS}
NETDASH_DEFAULT_ADMIN_USER=admin
EOF
  echo "→ Utworzono .env"
else
  echo "→ .env już istnieje — pomijam"
fi

echo "→ Pobieram obraz z GHCR..."
docker compose pull

echo "→ Uruchamiam NetDash..."
docker compose up -d

IP="$(hostname -I 2>/dev/null | awk '{print $1}' || echo '127.0.0.1')"
echo ""
echo "✓ NetDash działa → http://${IP}:8787"
echo "  Login: admin + hasło z .env"
echo "  Dane:  ${INSTALL_DIR}/data"
echo ""
echo "Auto-update (opcjonalnie):"
echo "  docker compose --profile auto-update up -d"
