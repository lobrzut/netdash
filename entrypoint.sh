#!/bin/sh
set -e

ENTRYPOINT_VERSION="1.3.162"

echo "================================================================"
echo " NetDash entrypoint v${ENTRYPOINT_VERSION}"
echo " LISTEN_PORT=18787 (8787 blocked — Readarr conflict)"
echo "================================================================"

# QNAP may persist a stale NETDASH_PORT=8787 (Readarr conflict).
# Nuclear fix: always 18787; NETDASH_PORT is never read by the app.
if [ -n "${NETDASH_PORT:-}" ]; then
  echo "NetDash entrypoint: WARNING — unsetting stale NETDASH_PORT=${NETDASH_PORT}"
fi
unset NETDASH_PORT
export NETDASH_LISTEN_PORT=18787
echo "NetDash entrypoint: LISTEN_PORT=18787 (8787 blocked)"

# Homelab: persist NETDASH_SECRET_KEY on the data volume (/app/data/.secret).
SECRET_FILE="/app/data/.secret"
umask 077
mkdir -p /app/data

if [ -f "$SECRET_FILE" ]; then
  NETDASH_SECRET_KEY="$(tr -d '\r\n' < "$SECRET_FILE")"
  export NETDASH_SECRET_KEY
  echo "NetDash entrypoint: loaded NETDASH_SECRET_KEY from /app/data/.secret"
elif [ -n "${NETDASH_SECRET_KEY:-}" ]; then
  printf '%s' "$NETDASH_SECRET_KEY" > "$SECRET_FILE"
  echo "NetDash entrypoint: saved NETDASH_SECRET_KEY from env to /app/data/.secret"
else
  NETDASH_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
  export NETDASH_SECRET_KEY
  printf '%s' "$NETDASH_SECRET_KEY" > "$SECRET_FILE"
  echo "NetDash entrypoint: WARNING — generated NETDASH_SECRET_KEY to /app/data/.secret"
fi

echo "NetDash entrypoint: starting python run.py on port 18787"
exec python run.py
