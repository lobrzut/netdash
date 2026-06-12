#!/bin/sh
set -e
# QNAP Container Station may persist NETDASH_PORT=8787 (Readarr conflict).
# App listens on NETDASH_LISTEN_PORT only; drop stale NETDASH_PORT before start.
export NETDASH_LISTEN_PORT="${NETDASH_LISTEN_PORT:-18787}"
unset NETDASH_PORT

# Homelab: persist NETDASH_SECRET_KEY on the data volume (/app/data/.secret).
SECRET_FILE="/app/data/.secret"
umask 077
mkdir -p /app/data

if [ -f "$SECRET_FILE" ]; then
  NETDASH_SECRET_KEY="$(tr -d '\r\n' < "$SECRET_FILE")"
  export NETDASH_SECRET_KEY
  echo "NetDash: loaded NETDASH_SECRET_KEY from /app/data/.secret"
elif [ -n "${NETDASH_SECRET_KEY:-}" ]; then
  printf '%s' "$NETDASH_SECRET_KEY" > "$SECRET_FILE"
  echo "NetDash: saved NETDASH_SECRET_KEY from env to /app/data/.secret"
else
  NETDASH_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
  export NETDASH_SECRET_KEY
  printf '%s' "$NETDASH_SECRET_KEY" > "$SECRET_FILE"
  echo "WARNING: NETDASH_SECRET_KEY was unset; generated and saved to /app/data/.secret"
fi

exec python run.py
