# Deploy NetDash to Linux server (PuTTY plink/pscp) - Windows helper
# Requires: BRAIN_SSH_HOST, BRAIN_SSH_PASSWORD, BRAIN_SSH_HOSTKEY
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Plink = "C:\Program Files\PuTTY\plink.exe"
$Pscp = "C:\Program Files\PuTTY\pscp.exe"
$RemoteDir = if ($env:NETDASH_REMOTE_DIR) { $env:NETDASH_REMOTE_DIR } else { "/opt/netdash" }

$Remote = if ($env:NETDASH_SSH_HOST) { $env:NETDASH_SSH_HOST } else { $env:BRAIN_SSH_HOST }
$Password = if ($env:NETDASH_SSH_PASSWORD) { $env:NETDASH_SSH_PASSWORD } else { $env:BRAIN_SSH_PASSWORD }
$HostKey = if ($env:NETDASH_SSH_HOSTKEY) { $env:NETDASH_SSH_HOSTKEY } else { $env:BRAIN_SSH_HOSTKEY }

if (-not $Remote -or -not $Password -or -not $HostKey) {
    Write-Error "Set NETDASH_SSH_HOST, NETDASH_SSH_PASSWORD, and NETDASH_SSH_HOSTKEY (or BRAIN_SSH_* aliases)."
}

function Invoke-Remote {
    param([string]$Command)
    & $Plink -batch -ssh $Remote -pw $Password -hostkey $HostKey $Command
    if ($LASTEXITCODE -ne 0) { throw "Remote command failed (exit $LASTEXITCODE)" }
}

Write-Host "Pre-flight on server..." -ForegroundColor Cyan
Invoke-Remote "mkdir -p ${RemoteDir}/data ${RemoteDir}/deploy"

$Items = @(
    "app", "deploy", "docker-compose.yml", "docker-compose.dev.yml", "Dockerfile",
    "requirements.txt", "run.py", "start.ps1", "start.sh", "README.md", "ROADMAP.md", "CHANGELOG.md", "DEPLOYMENT.md",
    "docs", "LICENSE", ".env.example"
)
foreach ($item in $Items) {
    $src = Join-Path $Root $item
    if (-not (Test-Path $src)) { continue }
    if ((Get-Item $src).PSIsContainer) {
        & $Pscp -batch -pw $Password -hostkey $HostKey -r $src "${Remote}:${RemoteDir}/"
    } else {
        & $Pscp -batch -pw $Password -hostkey $HostKey $src "${Remote}:${RemoteDir}/"
    }
    if ($LASTEXITCODE -ne 0) { throw "Upload failed: $item" }
}

if (-not $env:NETDASH_SKIP_REMOTE_UP) {
    Write-Host "Build and start on server..." -ForegroundColor Cyan
    $remoteScript = @'
set -euo pipefail
cd REMOTE_DIR_PLACEHOLDER
chmod +x deploy/netdash-watchdog.sh
if [ ! -f .env ]; then
  cp .env.example .env
  SECRET_KEY=$(openssl rand -base64 32 2>/dev/null | tr -d '/+=' | head -c 43)
  if [ -z "$SECRET_KEY" ]; then
    SECRET_KEY=$(head -c 48 /dev/urandom | base64 | tr -d '/+=' | head -c 43)
  fi
  sed -i "s/^NETDASH_SECRET_KEY=.*/NETDASH_SECRET_KEY=${SECRET_KEY}/" .env
  echo "Utworzono .env — login admin/changeme, zmien haslo po pierwszym logowaniu"
fi
export NETDASH_BUILD_DATE=$(date -u +%Y-%m-%d)
docker compose config >/dev/null
docker compose build
docker compose up -d --remove-orphans
echo "Waiting for health..."
ok=0
for i in $(seq 1 45); do
  PORT="\${NETDASH_LISTEN_PORT:-18787}"
  if curl -sf --max-time 5 "http://127.0.0.1:\${PORT}/api/health" >/dev/null 2>&1 || \
     docker exec netdash curl -sf --max-time 5 "http://127.0.0.1:\${PORT}/api/health" >/dev/null 2>&1; then
    ok=1
    break
  fi
  sleep 2
done
if [ "$ok" != "1" ]; then
  echo "ROLLBACK: health check failed after deploy" >&2
  docker compose logs --tail 40 netdash >&2 || true
  exit 1
fi
docker compose ps
curl -sf "http://127.0.0.1:\${NETDASH_LISTEN_PORT:-18787}/api/health"
if command -v systemctl >/dev/null 2>&1; then
  sudo cp deploy/netdash-watchdog.service deploy/netdash-watchdog.timer /etc/systemd/system/ 2>/dev/null || true
  sudo systemctl daemon-reload 2>/dev/null || true
  sudo systemctl enable --now netdash-watchdog.timer 2>/dev/null || true
fi
(crontab -l 2>/dev/null | grep -v netdash-watchdog; echo "*/5 * * * * NETDASH_DIR=REMOTE_DIR_PLACEHOLDER /opt/netdash/deploy/netdash-watchdog.sh >/dev/null 2>&1") | crontab - 2>/dev/null || true
'@ -replace 'REMOTE_DIR_PLACEHOLDER', $RemoteDir

    try {
        Invoke-Remote $remoteScript
    } catch {
        Write-Host "Deploy failed - check logs on server" -ForegroundColor Red
        throw
    }
}

Write-Host "Deployed to ${Remote}:${RemoteDir}" -ForegroundColor Green
Write-Host "Open: http://<server-ip>:18787 (or check remote health: curl http://127.0.0.1:18787/api/health)"
