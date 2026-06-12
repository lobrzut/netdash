#!/bin/sh
set -e
# QNAP Container Station may persist NETDASH_PORT=8787 (Readarr conflict).
# App listens on NETDASH_LISTEN_PORT only; drop stale NETDASH_PORT before start.
export NETDASH_LISTEN_PORT="${NETDASH_LISTEN_PORT:-18787}"
unset NETDASH_PORT
exec python run.py
