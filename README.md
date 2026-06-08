# NetDash

[![Version](https://img.shields.io/badge/version-1.3.18-blue)](app/config.py)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](requirements.txt)
[![Docker](https://img.shields.io/badge/docker-compose-blue.svg)](docker-compose.yml)

**Homelab dashboard inspired by [Homer](https://github.com/bastienwirtz/homer) — with automatic LAN service discovery.**

## Screenshots

Dark-theme homelab dashboard with pinned services, API key vault, notes, and network filters.

| Dashboard | Serwisy |
|-----------|---------|
| ![Dashboard — widgets and pinned services](docs/screenshots/dashboard.png) | ![Serwisy — filters and service cards](docs/screenshots/services.png) |

| Settings | Login |
|----------|-------|
| ![Settings — sidebar and general options](docs/screenshots/settings.png) | ![Login — JWT authentication](docs/screenshots/login.png) |

> **Screenshots use demo data only** (`*.demo.local`, `10.0.0.x`, masked keys like `sk-demo-…`). Regenerate: `NETDASH_DEMO_MODE=1 python scripts/capture_screenshots.py` (requires Playwright + running app on port 8787).

## Why NetDash?

| Homer | NetDash |
|-------|---------|
| Manual YAML config | **Auto network scan** (CIDR / local /24) |
| Static service list | **Detects and identifies** services (HTTP, title, favicon) |
| Icons from config | **70+ brand icons** (Jellyfin, Grafana, Plex…) + favicon |
| No vault | **Encrypted API key vault** (Fernet) |
| No notes | **Notes widget** with markdown |
| — | **Filter: login required / public** |
| — | **Widgets**: clock, stats, search |

## Features

- Auto-discovery — ping hosts, port scan, HTTP/HTTPS identification
- Dark theme with configurable accent color
- JWT login + encrypted API key vault
- Per-service notes, Wake-on-LAN / Sleep-on-LAN
- 70+ brand icons via [Simple Icons](https://simpleicons.org/)
- Online/offline health checks with persistent tiles
- Docker one-command deploy
- i18n: English, Polish, German, Ukrainian

## Deploy from GitHub

Clone and run on any fresh Linux server (or locally):

```bash
git clone https://github.com/lobrzut/netdash.git
cd netdash
cp .env.example .env
# Edit .env — set NETDASH_SECRET_KEY and NETDASH_DEFAULT_ADMIN_PASSWORD
docker compose up -d --build
```

Open **http://localhost:8787** (or `http://<server-ip>:8787` on your LAN).

Default login: values from `.env` → `NETDASH_DEFAULT_ADMIN_USER` / `NETDASH_DEFAULT_ADMIN_PASSWORD`.  
**Change the password** after first login (Settings → Password).

Full step-by-step guide: **[DEPLOYMENT.md](DEPLOYMENT.md)**

### Dockge (homelab)

On a Linux host with [Dockge](https://github.com/louislam/dockge):

```bash
git clone https://github.com/lobrzut/netdash.git /opt/stacks/netdash
cd /opt/stacks/netdash && cp .env.example .env   # edit secrets
```

Dockge → **Scan Stacks Folder** → deploy stack **netdash**.  
Requires `network_mode: host` (Linux only) for LAN scan — see **[dockge/README.md](dockge/README.md)**.

## Quick start

### Docker (recommended)

```bash
git clone https://github.com/lobrzut/netdash.git
cd netdash
cp .env.example .env
docker compose up -d
```

### Local Python dev (3.12+)

```bash
git clone https://github.com/lobrzut/netdash.git
cd netdash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # optional on dev — defaults in config.py work locally
python run.py
```

Windows shortcut: `.\start.ps1` · Linux: `./start.sh`

## Network scanning

1. Log in
2. Click **Scan network**
3. Leave empty (local /24) or enter a CIDR, e.g. `192.168.1.0/24`
4. Services appear in real time

> **Docker:** without `network_mode: host`, the container scans its bridge network (172.x), not your LAN. On Linux, `docker-compose.yml` uses `network_mode: host`. On Windows/Mac, comment out host mode and set `NETDASH_SCAN_CIDR=192.168.1.0/24` in `.env` or in Settings → Scanning.

## Deployment profiles

| Profile | How to run | URL |
|---------|------------|-----|
| **Local / dev** | `python run.py`, `start.ps1`, `start.sh` | http://localhost:8787 |
| **Server / Docker** | `docker compose up -d` (Linux, `network_mode: host`) | http://&lt;server-ip&gt;:8787 |

Details: **[DEPLOYMENT.md](DEPLOYMENT.md)** · deploy scripts: **[deploy/README.md](deploy/README.md)**

## Production on Linux

```bash
sudo mkdir -p /opt/netdash/data
cd /opt/netdash
git clone https://github.com/lobrzut/netdash.git .
cp .env.example .env
# Set NETDASH_SECRET_KEY (≥32 random chars) and NETDASH_DEFAULT_ADMIN_PASSWORD
docker compose up -d --build
docker compose ps   # expect: healthy
```

SQLite data: `./data/netdash.db` (volume `./data:/app/data`).

### Deploy from Windows (SSH)

```powershell
$env:NETDASH_SSH_HOST = "user@your-server"
$env:NETDASH_SSH_PASSWORD = "your-ssh-password"
$env:NETDASH_SSH_HOSTKEY = "ssh-ed25519 255 ..."
.\deploy\install.ps1
```

From Linux with rsync: `NETDASH_SSH_HOST=user@your-server ./deploy/install.sh`

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
| `NETDASH_SECRET_KEY` | JWT key + API vault encryption (**required** in Docker) |
| `NETDASH_DEFAULT_ADMIN_USER` | Default user (first start only) |
| `NETDASH_DEFAULT_ADMIN_PASSWORD` | Default password (**required** in Docker) |
| `NETDASH_SCAN_CIDR` | Override scan network (Docker bridge mode) |
| `NETDASH_BUILD_DATE` | Optional build date (About panel) |

See **[.env.example](.env.example)** for all variables.

## Stack

- **Backend:** FastAPI, SQLAlchemy, SQLite
- **Frontend:** Vanilla JS (no Node.js build step)
- **Auth:** JWT + bcrypt
- **Vault:** Fernet (cryptography)

## Project structure

```
netdash/
├── app/
│   ├── main.py       # API routes
│   ├── scanner.py    # Auto-discovery
│   ├── icons.py      # Brand icons
│   ├── vault.py      # Key encryption
│   └── static/       # Frontend
├── deploy/           # install scripts, systemd, watchdog
├── dockge/           # Dockge stack compose + deploy guide
├── docker-compose.yml
├── Dockerfile
└── run.py
```

## Roadmap

- [x] Online/offline status + health check
- [x] Per-service notes + Wake-on-LAN
- [ ] YAML import/export (Homer compatibility)
- [ ] ARP scan for device discovery
- [ ] Multi-user support

## License

MIT — use in portfolio, homelab, or commercial projects.

---

*A modern Homer alternative with automatic network discovery.*
