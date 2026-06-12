# NetDash

[![Version](https://img.shields.io/badge/version-1.3.76-blue)](app/config.py)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](requirements.txt)
[![Docker](https://img.shields.io/badge/docker-compose-blue.svg)](docker-compose.yml)

**Homelab dashboard inspired by [Homer](https://github.com/bastienwirtz/homer) — with automatic LAN service discovery.**

**NetDash = port 18787** — własny port serwisu; unika kolizji z Readarr (8787) i typowymi portami homelab/Docker/QNAP.

## Szybki start (Docker, bez git)

Na dowolnym **Linuxie z Dockerem** — trzy kroki:

```bash
curl -fsSL https://raw.githubusercontent.com/lobrzut/netdash/main/deploy/docker-simple/install.sh | bash
```

Otwórz **http://&lt;IP-serwera&gt;:18787** → login **`admin` / `changeme`** → **zmień hasło** w Ustawienia → Hasło.

> **Port:** domyślnie **18787** (unika kolizji z Readarr **8787**). Zmiana: `NETDASH_PORT` w `.env`. Stare instalacje na 8787: ustaw `NETDASH_PORT=8787` do migracji.

| Gdzie | Instrukcja |
|-------|------------|
| **Linux (Docker)** | [`deploy/docker-simple/`](deploy/docker-simple/) — `install.sh`, compose z GHCR |
| **QNAP NAS** | [`deploy/qnap/README.md`](deploy/qnap/README.md) — Container Station, import z URL |
| **Pełny przewodnik** | [DEPLOYMENT.md](DEPLOYMENT.md) |

Windows (Docker Desktop): `irm …/deploy/docker-simple/install.ps1 | iex` — patrz [deploy/docker-simple/](deploy/docker-simple/).

## Screenshots

Dark-theme homelab dashboard with pinned services, API key vault, notes, and network filters.

| Dashboard | Serwisy |
|-----------|---------|
| ![Dashboard — widgets and pinned services](docs/screenshots/dashboard.png) | ![Serwisy — filters and service cards](docs/screenshots/services.png) |

| Settings | Login |
|----------|-------|
| ![Settings — sidebar and general options](docs/screenshots/settings.png) | ![Login — JWT authentication](docs/screenshots/login.png) |

> **Screenshots use demo data only** (`*.demo.local`, `10.0.0.x`, masked keys like `sk-demo-…`). Regenerate: `NETDASH_DEMO_MODE=1 python scripts/capture_screenshots.py` (requires Playwright + running app on port 18787).

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

## What's new in v1.3.27

- Uptime dots stay green for login-gated and self-signed HTTPS services when reachable.
- Fixed stale amber status when checks were OK but timestamp looked old.

## What's new in v1.3.26

- **Add service modal** — icon preview, category suggestions, description, pin/login toggles, Identyfikuj (parity with edit modal)
- Sectioned layout with URL hint; POST `/api/services` accepts `icon_url`

## What's new in v1.3.25

- Uptime dots on cards: online / offline / stale / unknown / HTTP error + subtle „last seen” text
- Homer-inspired card polish: category color accent, stronger hover, watermark preserved
- Friendlier empty states (pinned CTA, search no-results + clear button)
- Debounced service search; faster pin toggle without full grid re-render
- **Homer YAML import** — Settings → Backup → Import Homer (config.yml)

See [ROADMAP.md](ROADMAP.md) for remaining gaps.

## Deploy from GitHub

Clone and run on any fresh Linux server (or locally):

```bash
git clone https://github.com/lobrzut/netdash.git
cd netdash
cp .env.example .env
# Edit .env — set NETDASH_SECRET_KEY (password defaults to changeme)
docker compose up -d --build
```

Open **http://localhost:18787** (or `http://<server-ip>:18787` on your LAN).

Default login: **`admin` / `changeme`** (or values from `.env` on first start when the DB has no users).  
**You must change the password** after first login (Settings → Password).

Full step-by-step guide: **[DEPLOYMENT.md](DEPLOYMENT.md)**

### Dockge (homelab)

On a Linux host with [Dockge](https://github.com/louislam/dockge):

```bash
git clone https://github.com/lobrzut/netdash.git /opt/stacks/netdash
cd /opt/stacks/netdash && cp .env.example .env   # edit secrets
```

Dockge → **Scan Stacks Folder** → deploy stack **netdash**.  

Compose file: **[dockge/compose.yaml](dockge/compose.yaml)** (alias [dockge/docker-compose.yml](dockge/docker-compose.yml)). Copy or symlink into the stack root if Dockge expects `compose.yaml` at repo root.

Requires `network_mode: host` (Linux only) for LAN scan — see **[dockge/README.md](dockge/README.md)**.

## Quick start

### Docker (recommended — no git)

```bash
curl -fsSL https://raw.githubusercontent.com/lobrzut/netdash/main/deploy/docker-simple/install.sh | bash
```

Lub ręcznie: [`deploy/docker-simple/docker-compose.yml`](deploy/docker-simple/docker-compose.yml) + [`.env.example`](deploy/docker-simple/.env.example) → `docker compose up -d`.

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
| **Local / dev** | `python run.py`, `start.ps1`, `start.sh` | http://localhost:18787 |
| **Server / Docker** | `docker compose up -d` (Linux, `network_mode: host`) | http://&lt;server-ip&gt;:18787 |

Details: **[DEPLOYMENT.md](DEPLOYMENT.md)** · prosty Docker: **[deploy/docker-simple/](deploy/docker-simple/)** · QNAP: **[deploy/qnap/](deploy/qnap/)** · SSH deploy: **[deploy/README.md](deploy/README.md)**

## Production on Linux

```bash
sudo mkdir -p /opt/netdash/data
cd /opt/netdash
git clone https://github.com/lobrzut/netdash.git .
cp .env.example .env
# Set NETDASH_SECRET_KEY (≥32 random chars); default login admin/changeme — change after deploy
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
| `NETDASH_DEFAULT_ADMIN_USER` | Default user (first start only, default `admin`) |
| `NETDASH_DEFAULT_ADMIN_PASSWORD` | Default password (default `changeme` — **change after first login**) |
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
├── deploy/
│   ├── docker-simple/  # GHCR-only compose + install.sh (bez git)
│   └── qnap/           # QNAP Container Station
├── dockge/           # Dockge stack compose + deploy guide
├── docker-compose.yml
├── Dockerfile
└── run.py
```

## Roadmap

- [x] Online/offline status + health check
- [x] Per-service notes + Wake-on-LAN
- [x] Homer YAML import (MVP)
- [ ] YAML export (Homer compatibility)
- [x] ARP scan for device discovery
- [ ] Multi-user support

## License

MIT — use in portfolio, homelab, or commercial projects.

---

*A modern Homer alternative with automatic network discovery.*
