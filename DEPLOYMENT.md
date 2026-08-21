# NetDash — deployment guide

Repository: [lobrzut/netdash](https://github.com/lobrzut/netdash) · wersja: **1.3.158**

> **Zalecane wdrożenie:** **Dockge na Ubuntu VM (Proxmox)** — nie QNAP. VM **2 GB RAM** wystarczy dla samego NetDash. QNAP: deprecated — **[DEPRECATION-QNAP.md](DEPRECATION-QNAP.md)** → **[dockge/README.md](dockge/README.md)**.

## Najprostsze ścieżki (bez git na serwerze)

| Cel | Co zrobić |
|-----|-----------|
| **Linux + Docker** | `curl -fsSL https://raw.githubusercontent.com/lobrzut/netdash/main/deploy/docker-simple/install.sh \| bash` |
| **Dockge / Proxmox VM** | Clone do `/opt/stacks/netdash` → `dockge/compose.yaml` — **[dockge/README.md](dockge/README.md)** · szybki start: `bash dockge/deploy-balanced.sh` |
| **QNAP (legacy)** | **Deprecated** — archiwum: [deploy/qnap/](deploy/qnap/) · [DEPRECATION-QNAP.md](DEPRECATION-QNAP.md) |
| **Windows Docker Desktop** | `irm …/deploy/docker-simple/install.ps1 \| iex` — patrz **[deploy/docker-simple/](deploy/docker-simple/)** |

Obraz: `ghcr.io/lobrzut/netdash:latest` (GHCR, bez budowania lokalnie).

---

## Profile uruchomienia

| Profile | Target | Start command | URL |
|---------|--------|---------------|-----|
| **Local / dev** | Windows, Linux bare metal | `python run.py`, `start.ps1`, `start.sh` | http://localhost:18787 |
| **Server / Docker** | Linux homelab server | `deploy/docker-simple/install.sh` lub `docker compose up -d` | http://&lt;server-ip&gt;:18787 |

### Port (`NETDASH_LISTEN_PORT`)

Domyślnie **18787** — poza typowymi portami homelab i **bez kolizji z Readarr (8787)**. Aplikacja **nie** czyta `NETDASH_PORT` (stary env jest odrzucany w entrypoint).

| Sytuacja | Co zrobić |
|----------|-----------|
| Nowa instalacja | Nic — użyj `http://<host>:18787` |
| Upgrade z wersji ≤1.3.72 (było 8787) | Ustaw `NETDASH_LISTEN_PORT=8787` w `.env` tymczasowo **lub** zmień zakładkę na `:18787` i zrestartuj kontener |
| Własny port | `NETDASH_LISTEN_PORT=<port>` w `.env` + healthcheck w compose na ten sam port |

---

## Deploy from GitHub (clone — opcjonalnie)

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
# Default login (first start, empty DB): admin / changeme

# 4. Start
docker compose up -d --build
docker compose ps          # Status should be "healthy"
curl -s http://127.0.0.1:18787/api/health

# 5. Open in browser
# http://<server-ip>:18787
# Login: admin / changeme (or values from .env on first start)
# **MUST** change password after first login: Settings → Password
```

Data persists in `./data/netdash.db` (bind mount `./data:/app/data`).

### Słaby sprzęt (homelab — RPi, stary PC, N100, VM 2 GB)

Filozofia projektu: **działa na słabym sprzęcie**. VM **2 GB RAM** wystarczy dla NetDash solo. `dockge/compose.yaml` ustawia:

- `NETDASH_DISCOVERY_POLICY=on_demand` + `NETDASH_DISCOVERY_ENABLED=false` (brak TCP w tle)
- `NETDASH_SCAN_SAFE_MODE=true` (throttling IPS-friendly; ręczny skan nadal może objąć `/24`)
- `mem_limit: 512M`, `cpu_count: 1`

Skan: **[docs/SCANNING.md](docs/SCANNING.md)**.

| Zmienna | Zalecenie na słabym hoście |
|---------|----------------------------|
| `NETDASH_DISCOVERY_POLICY` | `on_demand` — przycisk **Skanuj sieć**, nie ciągły skaner |
| `NETDASH_SCAN_SAFE_MODE` | `true` (domyślnie) — nie wyłączaj na współdzielonym VLAN |
| `NETDASH_SCAN_CIDR` | LAN, np. `192.168.1.0/24`; `/28` tylko gdy chcesz ostrożny podzbiór |
| Pełny skan w UI | Dozwolony (v1.3.151+); safe mode tylko ogranicza równoległość i porty |

Weryfikacja po deployu:

```bash
curl -s http://127.0.0.1:18787/api/health | jq '{version, scan_safe_mode, resource_profile}'
```

### Pre-built image (GHCR) — zalecane

Użyj **[deploy/docker-simple/](deploy/docker-simple/)** — compose bez `build:`, tylko pull z GHCR.

Auto-update (opcjonalnie): Watchtower w `dockge/compose.yaml` — obraz **`nickfedor/watchtower:1.7.1`** (fork dla Docker 29+, API 1.44+). Starsze compose (`docker-compose.yml`, QNAP) mogą nadal używać `containrrr/watchtower`.

**QNAP:** deprecated — **[DEPRECATION-QNAP.md](DEPRECATION-QNAP.md)** · archiwum: [deploy/qnap/](deploy/qnap/).

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
   nano .env   # NETDASH_SECRET_KEY (default login admin/changeme — change after deploy)
   ```
3. **Dockge UI** → ⋮ → **Scan Stacks Folder** → open stack **netdash** → **Deploy**
4. Open **http://&lt;server-ip&gt;:18787** and change the default password after login.

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
curl -s http://127.0.0.1:18787/api/health          # {"ok":true,"version":"1.3.158",...}
docker inspect netdash --format='RestartCount={{.RestartCount}}'
docker compose ps                                  # healthy
```

Simulate auto-restart:

```bash
docker stop netdash && sleep 35 && curl -s http://127.0.0.1:18787/api/health
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

→ http://localhost:18787 (LAN: http://&lt;your-pc-ip&gt;:18787)

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
# Required: NETDASH_SECRET_KEY (default login admin/changeme — change after first login)
docker compose up -d --build
docker compose ps
```

→ http://&lt;server-ip&gt;:18787

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
| `deploy/docker-simple/docker-compose.yml` | — | ✓ GHCR-only (bez git) |
| `docker-compose.yml` | — | ✓ repo root (build + GHCR) |
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
