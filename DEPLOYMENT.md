# NetDash — deployment guide

One codebase, two runtime profiles. Repository: [lobrzut/netdash](https://github.com/lobrzut/netdash)

| Profile | Target | Start command | URL |
|---------|--------|---------------|-----|
| **Local / dev** | Windows, Linux bare metal | `python run.py`, `start.ps1`, `start.sh` | http://localhost:8787 |
| **Server / Docker** | Linux homelab server | `docker compose up -d` | http://&lt;server-ip&gt;:8787 |

Application version: **1.3.66** (`app/config.py` → `VERSION`).

---

## Deploy from GitHub (fresh server)

Use this workflow to clone and run NetDash on a new Linux machine — same pattern as other homelab projects.

```bash
# 1. Prerequisites: Docker + Docker Compose v2, git
sudo apt update && sudo apt install -y git docker.io docker-compose-plugin
sudo usermod -aG docker $USER   # re-login if needed

# 2. Clone
sudo mkdir -p /opt/netdash
cd /opt/netdash
git clone https://github.com/lobrzut/netdash.git .

# 3. Configure secrets (never commit .env)
cp .env.example .env
nano .env
# Required:
#   NETDASH_SECRET_KEY=<random-string-at-least-32-chars>
#   NETDASH_DEFAULT_ADMIN_PASSWORD=<strong-password>

# 4. Start
docker compose up -d --build
docker compose ps          # Status should be "healthy"
curl -s http://127.0.0.1:8787/api/health

# 5. Open in browser
# http://<server-ip>:8787
# Login: NETDASH_DEFAULT_ADMIN_USER / NETDASH_DEFAULT_ADMIN_PASSWORD
# Then change password in Settings → Password
```

Data persists in `./data/netdash.db` (bind mount `./data:/app/data`).

---

## Deploy with Dockge

[Dockge](https://github.com/louislam/dockge) manages compose stacks from `/opt/stacks`. NetDash includes a Dockge-ready compose in [`dockge/`](dockge/).

**Requirements:** Linux Docker host (Dockge does not run on Windows). NetDash needs **`network_mode: host`** for LAN scanning — do not add a `ports:` section.

### Step-by-step (GitHub clone)

1. **Clone** into the Dockge stacks directory:
   ```bash
   git clone https://github.com/lobrzut/netdash.git /opt/stacks/netdash
   cd /opt/stacks/netdash
   ```
2. **Configure** secrets:
   ```bash
   cp .env.example .env
   nano .env   # NETDASH_SECRET_KEY, NETDASH_DEFAULT_ADMIN_PASSWORD
   ```
3. **Dockge UI** → ⋮ → **Scan Stacks Folder** → open stack **netdash** → **Deploy**
4. Open **http://&lt;server-ip&gt;:8787** and change the default password after login.

Dockge auto-detects `docker-compose.yml` at the repo root. Optional Dockge filename: `cp dockge/compose.yaml compose.yaml`.

### Alternative: new stack in Dockge UI

1. Dockge → **+ Compose** → name: `netdash`
2. Paste contents of [`dockge/compose.yaml`](dockge/compose.yaml)
3. Create `/opt/stacks/netdash/.env` from [`.env.example`](.env.example)
4. Clone the repo into `/opt/stacks/netdash/` so `build: .` resolves, then **Deploy**

Details and caveats: **[dockge/README.md](dockge/README.md)**

---

## Production stability

NetDash on a Linux server includes several resilience layers:

| Layer | Mechanism | Description |
|-------|-----------|-------------|
| Docker | `restart: always` | Container restarts after crash or Docker daemon restart |
| Healthcheck | `curl /api/health` every 30s | Docker marks container unhealthy if no response |
| Watchdog cron | every 5 min | `deploy/netdash-watchdog.sh` — if health fails → `docker compose up -d` |
| Systemd timer | optional | `netdash-watchdog.timer` — same as cron, independent layer |

### Common issues

1. **Invalid `docker-compose.yml`** — `network_mode: host` **cannot** coexist with a `ports:` section (Docker refuses to start). Use `deploy/install.ps1` for remote deploy — it validates compose before `up`.
2. **HTTPS errors in health check** — handled in `app/health.py` since v1.3.5.
3. **Host VM briefly offline** — unrelated to NetDash; watchdog restarts the container when the host returns.
4. **Memory pressure** — monitor `free -m` on small VMs; SQLite + scan jobs can spike RAM.

### Post-deploy verification

```bash
curl -s http://127.0.0.1:8787/api/health          # {"ok":true,"version":"1.3.18",...}
docker inspect netdash --format='RestartCount={{.RestartCount}}'
docker compose ps                                  # healthy
```

Simulate auto-restart:

```bash
docker stop netdash && sleep 35 && curl -s http://127.0.0.1:8787/api/health
# Container should return within ~30s (restart: always)
```

### Manual watchdog

```bash
/opt/netdash/deploy/netdash-watchdog.sh
sudo systemctl status netdash-watchdog.timer   # if installed
crontab -l | grep netdash
```

---

## Local development

### Windows

```powershell
git clone https://github.com/lobrzut/netdash.git
cd netdash
copy .env.example .env
# Optional: set NETDASH_SECRET_KEY and password (dev defaults in config.py work)
.\start.ps1
```

→ http://localhost:8787 (LAN: http://&lt;your-pc-ip&gt;:8787)

### Linux bare metal

```bash
git clone https://github.com/lobrzut/netdash.git
cd netdash
cp .env.example .env
pip install -r requirements.txt
./start.sh
```

### Network scan — local

On the host (Windows/Linux), NetDash **natively** scans the LAN (auto-detected /24 or CIDR in Settings). No `network_mode: host` or `NETDASH_SCAN_CIDR` needed — ping and ARP go directly from the machine's interface.

---

## Server (Docker / production)

```bash
cd /opt/netdash
cp .env.example .env
# Required: NETDASH_SECRET_KEY, NETDASH_DEFAULT_ADMIN_PASSWORD
docker compose up -d --build
docker compose ps
```

→ http://&lt;server-ip&gt;:8787

### Network scan — Docker

`docker-compose.yml` (Linux production) uses **`network_mode: host`** — the container shares the host network and scans `192.168.x.0/24` like a native app.

Without host mode (bridge, e.g. Docker Desktop on Windows/Mac):

- container sees `172.x`, not LAN;
- set in `.env`: `NETDASH_SCAN_CIDR=192.168.1.0/24` **or** CIDR in Settings → Scanning.

Test Docker locally (bridge):

```bash
docker compose -f docker-compose.dev.yml up -d --build
```

---

## Deploy from Windows to remote server

Requires [PuTTY](https://www.putty.org/) (`plink.exe`, `pscp.exe`).

```powershell
$env:NETDASH_SSH_HOST = "user@your-server"
$env:NETDASH_SSH_PASSWORD = "your-ssh-password"
$env:NETDASH_SSH_HOSTKEY = "ssh-ed25519 255 ..."
.\deploy\install.ps1
```

From Linux (rsync):

```bash
NETDASH_SSH_HOST=user@your-server ./deploy/install.sh
```

Environment variables (also supported as `BRAIN_SSH_*` for backward compatibility):

| Variable | Description |
|----------|-------------|
| `NETDASH_SSH_HOST` | `user@hostname` or `user@ip` |
| `NETDASH_SSH_PASSWORD` | SSH password (PuTTY deploy only) |
| `NETDASH_SSH_HOSTKEY` | Host key fingerprint for PuTTY |
| `NETDASH_REMOTE_DIR` | Remote path (default: `/opt/netdash`) |

---

## Files per profile

| File | Local | Server Docker |
|------|-------|---------------|
| `run.py` | ✓ | (in image) |
| `start.ps1` / `start.sh` | ✓ | — |
| `docker-compose.yml` | — | ✓ production (`network_mode: host`) |
| `dockge/compose.yaml` | — | ✓ Dockge stack (same as production) |
| `docker-compose.dev.yml` | optional (bridge test) | — |
| `.env` | local secrets (gitignored) | separate secrets on server |
| `data/netdash.db` | local database | volume `./data` |

---

## Security checklist (before git push)

```bash
git status
git check-ignore -v .env data/
```

**Never commit:** `.env`, `data/`, `*.db`, passwords, API keys from the vault, SSH private keys, deploy credential files.

Generate a secret key:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

GitHub profile tips: [docs/GITHUB_PROFILE.md](docs/GITHUB_PROFILE.md)
