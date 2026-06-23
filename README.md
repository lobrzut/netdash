# NetDash

[![Version](https://img.shields.io/badge/version-1.3.133-blue)](app/config.py)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](requirements.txt)
[![Docker](https://img.shields.io/badge/docker-compose-blue.svg)](docker-compose.yml)

**A self-hosted homelab dashboard inspired by [Homer](https://github.com/bastienwirtz/homer), with automatic LAN service discovery.**

**Default NetDash port: 18787** — chosen to avoid conflicts with common homelab ports such as Readarr (8787).

## Quick start (Docker, no git)

Run this on any Linux host with Docker:

```bash
curl -fsSL https://raw.githubusercontent.com/lobrzut/netdash/main/deploy/docker-simple/install.sh | bash
```

Open **http://<server-ip>:18787** and sign in with **`admin` / `changeme`**, then change the password in **Settings → Password**.

> **Port note:** NetDash uses **18787** by default. Set `NETDASH_PORT` in `.env` to change it. If you are migrating an older install on 8787, set `NETDASH_PORT=8787`.

| Platform | Guide |
|----------|-------|
| **Linux (Docker)** | [`deploy/docker-simple/`](deploy/docker-simple/) — `install.sh`, GHCR-based compose |
| **QNAP NAS** | [`deploy/qnap/README.md`](deploy/qnap/README.md) — wdrożenie przez Dockge |
| **Full guide** | [DEPLOYMENT.md](DEPLOYMENT.md) |

Windows (Docker Desktop): `irm https://raw.githubusercontent.com/lobrzut/netdash/main/deploy/docker-simple/install.ps1 | iex` — see [deploy/docker-simple/](deploy/docker-simple/).

## Screenshots

Dark-theme homelab dashboard with pinned services, API key vault, notes, and network filters.

| Dashboard | Services |
|-----------|----------|
| ![Dashboard — widgets and pinned services](docs/screenshots/dashboard.png) | ![Services — filters and service cards](docs/screenshots/services.png) |

| Settings | Login |
|----------|-------|
| ![Settings — sidebar and general options](docs/screenshots/settings.png) | ![Login — JWT authentication](docs/screenshots/login.png) |

> **Screenshots use demo data only** (`*.demo.local`, `10.0.0.x`, masked keys like `sk-demo-…`). Regenerate with `NETDASH_DEMO_MODE=1 python scripts/capture_screenshots.py` (requires Playwright and a running app on port 18787).

## Why NetDash?

| Homer | NetDash |
|-------|---------|
| Manual YAML configuration | **Automatic network scanning** (CIDR / local /24) |
| Static service list | **Service detection and identification** (HTTP, title, favicon) |
| Icons from config | **70+ brand icons** (Jellyfin, Grafana, Plex, and more) + favicon fallback |
| No vault | **Encrypted API key vault** (Fernet) |
| No notes | **Notes widget** with markdown |
| — | **Visibility filters**: login required / public |
| — | **Widgets**: clock, stats, search |

## Features

- Auto-discovery (ping, port scan, HTTP/HTTPS identification)
- Dark theme with configurable accent color
- JWT authentication and encrypted API key vault
- Per-service notes plus Wake-on-LAN / Sleep-on-LAN
- 70+ brand icons via [Simple Icons](https://simpleicons.org/)
- Persistent online/offline health checks
- One-command Docker deployment
- i18n support: English, Polish, German, Ukrainian
- **Optional Brain stats tile** — live knowledge-base counts (notes, sessions, library, graph) from a `/stats` endpoint; off by default
- **Remote discovery agent** (v1.3.112): lightweight LAN scanner on a separate host pushing to `POST /api/discovery/import` (ideal for QNAP + homelab split deployments)

## Remote Discovery Agent

If NetDash runs on a low-power NAS (for example QNAP) without safe LAN scan access, disable local scanning and use a remote agent:

| Host | Role |
|------|------|
| QNAP `.150` | Dashboard only — `NETDASH_SCAN_DISABLED=true` |
| Homelab `.201` | `deploy/agent/docker-compose.yml` — `network_mode: host`, arp-scan |

See [`deploy/agent/README.md`](deploy/agent/README.md) and [`deploy/qnap/README.md`](deploy/qnap/README.md).

## What's new

### v1.3.133

- **Optional Brain stats tile** (off by default) — point it at a Brain `/stats` endpoint (knowledge counts) in Settings → Appearance and it shows live numbers; served via the auth-gated `/api/brain/stats` proxy.

### v1.3.132

- Visible brand/icon **watermark on every tile** — pinned cards and emoji/letter tiles now included (no more blank backgrounds).

### v1.3.131 — security hardening

- Login **brute-force guard** (`429` + `Retry-After`, 5 attempts / 5 min per IP+user); UI-set password no longer overwritten on restart.
- Swagger `/docs` **off by default** (`NETDASH_DOCS_ENABLED=true` to enable).
- `python-jose` → **`PyJWT`** (CVE-2024-33663/33664); SSRF guard for cloud-metadata endpoints.

### Deployment

- **QNAP via Dockge** (Container Station stays as the Docker engine) — see [`deploy/qnap/README.md`](deploy/qnap/README.md).

Full version history: **[CHANGELOG.md](CHANGELOG.md)**.

See [ROADMAP.md](ROADMAP.md) for remaining work.

## Deploy from GitHub

Clone and run on a fresh Linux server (or locally):

```bash
git clone https://github.com/lobrzut/netdash.git
cd netdash
cp .env.example .env
# Edit .env and set NETDASH_SECRET_KEY (password defaults to changeme)
docker compose up -d --build
```

Open **http://localhost:18787** (or `http://<server-ip>:18787` on your LAN).

Default login: **`admin` / `changeme`** (synced from env on container start when `NETDASH_SYNC_ADMIN_PASSWORD=true`).  
**Change the password immediately after first login** (Settings → Password).

Full deployment instructions: **[DEPLOYMENT.md](DEPLOYMENT.md)**.

### Dockge (homelab)

On a Linux host with [Dockge](https://github.com/louislam/dockge):

```bash
git clone https://github.com/lobrzut/netdash.git /opt/stacks/netdash
cd /opt/stacks/netdash && cp .env.example .env
```

In Dockge: **Scan Stacks Folder** → deploy stack **netdash**.

Compose file: **[dockge/compose.yaml](dockge/compose.yaml)** (alias [dockge/docker-compose.yml](dockge/docker-compose.yml)). Copy or symlink it into the expected stack root if required by your Dockge setup.

LAN scanning requires `network_mode: host` (Linux only) — see **[dockge/README.md](dockge/README.md)**.

## Development quick start

### Docker (recommended)

```bash
curl -fsSL https://raw.githubusercontent.com/lobrzut/netdash/main/deploy/docker-simple/install.sh | bash
```

Manual alternative: [`deploy/docker-simple/docker-compose.yml`](deploy/docker-simple/docker-compose.yml) + [`.env.example`](deploy/docker-simple/.env.example), then run `docker compose up -d`.

### Local Python development (3.12+)

```bash
git clone https://github.com/lobrzut/netdash.git
cd netdash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # optional for local dev; config.py defaults also work
python run.py
```

Shortcuts: Windows `.\start.ps1`, Linux `./start.sh`.

## Network scanning

1. Sign in.
2. Click **Scan network**.
3. Leave the field empty (local /24) or provide a CIDR, for example `192.168.1.0/24`.
4. Services appear in real time.

> **Docker note:** without `network_mode: host`, the container scans its own bridge network (172.x), not your LAN. On Linux, `docker-compose.yml` uses `network_mode: host`. On Windows/macOS, disable host mode and set `NETDASH_SCAN_CIDR=192.168.1.0/24` in `.env` or in Settings → Scanning.

## Low-resource hardware profile (RPi, older PC, N100, NAS, QNAP)

NetDash is designed to run on low-resource homelab hardware. By default, it enables safe scan mode (`NETDASH_SCAN_SAFE_MODE=true`) with lower concurrency, a shorter port list, and host limits. Official compose files also limit the container to **512 MB RAM** and **1 CPU**.

| Problem | Recommendation |
|---------|----------------|
| Host becomes unstable during scans | Keep safe mode enabled and use a smaller CIDR (`192.168.1.0/28` instead of `/24`) via `NETDASH_SCAN_CIDR` or Settings → Scanning |
| Scans are too slow on strong hardware | Set `NETDASH_SCAN_SAFE_MODE=false` in `.env`/compose and restart |
| Full port scan needed | Use only on strong hardware; UI requires explicit confirmation (Aggressive profile) |
| Health checks consume too many resources | Increase health-check interval (for example 120s) or disable it |

Example `.env` for low-resource hosts:

```env
NETDASH_SCAN_SAFE_MODE=true
NETDASH_SCAN_CIDR=192.168.1.0/28
```

Check profile output: `curl -s http://127.0.0.1:18787/api/health` → `scan_safe_mode`, `resource_profile`.

Deployment details: **[DEPLOYMENT.md](DEPLOYMENT.md)** · QNAP: **[deploy/qnap/README.md](deploy/qnap/README.md)**.

## Deployment profiles

| Profile | Run command | URL |
|---------|-------------|-----|
| **Local / dev** | `python run.py`, `start.ps1`, `start.sh` | http://localhost:18787 |
| **Server / Docker** | `docker compose up -d` (Linux, `network_mode: host`) | http://<server-ip>:18787 |

More options: **[DEPLOYMENT.md](DEPLOYMENT.md)** · simple Docker: **[deploy/docker-simple/](deploy/docker-simple/)** · QNAP: **[deploy/qnap/](deploy/qnap/)** · SSH deploy: **[deploy/README.md](deploy/README.md)**.

## Production on Linux

```bash
sudo mkdir -p /opt/netdash/data
cd /opt/netdash
git clone https://github.com/lobrzut/netdash.git .
cp .env.example .env
# Set NETDASH_SECRET_KEY (>=32 random chars); default login is admin/changeme
docker compose up -d --build
docker compose ps   # expected: healthy
```

SQLite path: `./data/netdash.db` (volume `./data:/app/data`).

### Deploy from Windows (SSH)

```powershell
$env:NETDASH_SSH_HOST = "user@your-server"
$env:NETDASH_SSH_PASSWORD = "your-ssh-password"
$env:NETDASH_SSH_HOSTKEY = "ssh-ed25519 255 ..."
.\deploy\install.ps1
```

Linux rsync option: `NETDASH_SSH_HOST=user@your-server ./deploy/install.sh`.

### systemd (without Docker)

```bash
sudo useradd -r -m netdash || true
cd /opt/netdash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env
sudo cp deploy/netdash.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now netdash
```

## Configuration

| Variable | Description |
|----------|-------------|
| `NETDASH_SECRET_KEY` | JWT signing key and API vault encryption key (**required** for Docker) |
| `NETDASH_DEFAULT_ADMIN_USER` | Default admin username (`admin`) |
| `NETDASH_DEFAULT_ADMIN_PASSWORD` | Admin password from env (`changeme` by default — change after first login) |
| `NETDASH_SYNC_ADMIN_PASSWORD` | Sync admin password from env on every start (`true` by default; set to `false` after changing in UI) |
| `NETDASH_SCAN_CIDR` | Override scan network (useful in Docker bridge mode) |
| `NETDASH_BUILD_DATE` | Optional build date for About panel |

See **[.env.example](.env.example)** for the full list.

## Stack

- **Backend:** FastAPI, SQLAlchemy, SQLite
- **Frontend:** Vanilla JavaScript (no Node.js build step)
- **Auth:** JWT + bcrypt
- **Vault:** Fernet (`cryptography`)

## Project structure

```text
netdash/
├── app/
│   ├── main.py       # API routes
│   ├── scanner.py    # Auto-discovery
│   ├── icons.py      # Brand icons
│   ├── vault.py      # Key encryption
│   └── static/       # Frontend
├── deploy/
│   ├── docker-simple/  # GHCR-only compose + install.sh
│   └── qnap/           # QNAP (Dockge)
├── dockge/           # Dockge compose stack + deployment guide
├── docker-compose.yml
├── Dockerfile
└── run.py
```

## Roadmap

- [x] Online/offline status and health checks
- [x] Per-service notes and Wake-on-LAN
- [x] Homer YAML import (MVP)
- [ ] YAML export (Homer compatibility)
- [x] ARP-based device discovery
- [ ] Multi-user support

## Acknowledgements

- **[Homer](https://github.com/bastienwirtz/homer)** (Apache-2.0) — UI inspiration and YAML import compatibility.
- **[GPTWOL](https://github.com/Misterbabou/gptwol)** (MIT, Misterbabou) — Wake/Sleep-on-LAN ideas and optional HTTP gateway integration (`gptwol_url` in settings). NetDash implements WoL/SOL and ARP discovery independently and is not a GPTWOL fork.

## License

MIT — suitable for portfolio, homelab, and commercial use.

---

*A modern Homer alternative with automatic network discovery.*
