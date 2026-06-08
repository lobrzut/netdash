#!/usr/bin/env bash
# NetDash — uruchom / zrestartuj serwer (Linux bare metal)
set -euo pipefail

PORT=8787
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

if command -v fuser >/dev/null 2>&1; then
  fuser -k "${PORT}/tcp" 2>/dev/null || true
elif command -v lsof >/dev/null 2>&1; then
  lsof -ti:"${PORT}" | xargs -r kill -9 2>/dev/null || true
fi

sleep 1

if [[ -x "${ROOT}/.venv/bin/python" ]]; then
  PYTHON="${ROOT}/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON=python3
else
  PYTHON=python
fi

nohup "${PYTHON}" run.py > "${ROOT}/data/netdash.log" 2>&1 &
sleep 2

if curl -sf "http://127.0.0.1:${PORT}/api/health" >/dev/null; then
  VERSION=$(curl -sf "http://127.0.0.1:${PORT}/api/health" | "${PYTHON}" -c "import sys,json; print(json.load(sys.stdin).get('version','?'))" 2>/dev/null || echo "?")
  echo "NetDash OK v${VERSION} -> http://127.0.0.1:${PORT}"
else
  echo "NetDash nie odpowiada na porcie ${PORT}" >&2
  exit 1
fi
