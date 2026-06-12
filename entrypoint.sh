#!/bin/sh
set -e
# QNAP Container Station may persist NETDASH_PORT=8787 (Readarr conflict).
# App listens on NETDASH_LISTEN_PORT only; drop stale NETDASH_PORT before start.
export NETDASH_LISTEN_PORT="${NETDASH_LISTEN_PORT:-18787}"
unset NETDASH_PORT

# Homelab: auto-generate NETDASH_SECRET_KEY when CS does not pass it (persist in data volume).
if [ -z "${NETDASH_SECRET_KEY:-}" ]; then
  SECRET_FILE="/app/data/.secret"
  if [ -f "$SECRET_FILE" ]; then
    NETDASH_SECRET_KEY="$(tr -d '\r\n' < "$SECRET_FILE")"
    export NETDASH_SECRET_KEY
    echo "NetDash: loaded NETDASH_SECRET_KEY from /app/data/.secret"
  else
    NETDASH_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
    export NETDASH_SECRET_KEY
    umask 077
    printf '%s' "$NETDASH_SECRET_KEY" > "$SECRET_FILE"
    echo "WARNING: NETDASH_SECRET_KEY was unset; generated and saved to /app/data/.secret"
  fi
fi

exec python run.py
