# NetDash

[![Version](https://img.shields.io/badge/version-1.3.149-blue)](app/config.py)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](requirements.txt)
[![Docker](https://img.shields.io/badge/docker-compose-blue.svg)](docker-compose.yml)

**A self-hosted homelab dashboard inspired by [Homer](https://github.com/bastienwirtz/homer), with automatic LAN service discovery.**

**Default NetDash port: 18787** — chosen to avoid conflicts with common homelab ports such as Readarr (8787).

> **Recommended deploy:** **Ubuntu VM on Proxmox + [Dockge](dockge/README.md)** — not QNAP. A **2 GB RAM** VM is sufficient for NetDash alone (512M container limit). QNAP is **deprecated** — see **[DEPRECATION-QNAP.md](DEPRECATION-QNAP.md)**.

## Quick start (Docker, no git)

Run this on any Linux host with Docker:

```bash
curl -fsSL https://raw.githubusercontent.com/lobrzut/netdash/main/deploy/docker-simple/install.sh | bash
```

Open **http://<server-ip>:18787** and sign in with **`admin` / `changeme`**, then change the password in **Settings → Password**.

> **Port note:** NetDash uses **18787** by default. Set `NETDASH_LISTEN_PORT` in `.env` to change it. If you are migrating an older install on 8787, set `NETDASH_LISTEN_PORT=8787`.

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

- **Two scan modes** — automatic adaptive background discovery vs on-demand manual scan (with Stop)
- Auto-discovery (ping, port scan, HTTP/HTTPS identification)
- **IPS-friendly / stealth probing** — spreads port probes per host over time to avoid Symantec SEP and similar endpoint IPS blocks (on by default)
- **Settings toggle** to disable automatic background discovery (manual add and manual scan still work)
- **Auto-remove stale services** — configurable offline days (`NETDASH_STALE_REMOVE_DAYS` or Settings → Scanning)
- Dark theme with configurable accent color
- JWT authentication and encrypted API key vault
- Per-service notes plus Wake-on-LAN / **Sleep-on-LAN** (install scripts auto-detect MAC per OS; pre-filled from discovery)
- **Mobile-friendly WOL/SOL** — tile action buttons tappable on touch devices
- 70+ brand icons via [Simple Icons](https://simpleicons.org/)
- Persistent online/offline health checks
- One-command Docker deployment
- i18n support: English, Polish, German, Ukrainian
- **Optional Brain stats tile** — live knowledge-base counts (notes, sessions, library, graph) from a `/stats` endpoint; **“Open dashboard”** link when Brain is online; off by default
- **Optional Network tile** — LAN/WAN info (public IP, ISP, country), link latency, discovery sparkline; off by default
- **Remote discovery agent** (v1.3.112): lightweight LAN scanner on a separate host pushing to `POST /api/discovery/import` (ideal for split deployments)

## Remote Discovery Agent

If NetDash runs on a low-power NAS (for example QNAP) without safe LAN scan access, disable local scanning and use a remote agent:

| Host | Role |
|------|------|
| QNAP `.150` | Dashboard only — `NETDASH_SCAN_DISABLED=true` |
| Homelab `.201` | `deploy/agent/docker-compose.yml` — `network_mode: host`, arp-scan |

See [`deploy/agent/README.md`](deploy/agent/README.md) and [`deploy/qnap/README.md`](deploy/qnap/README.md).

## What's new

### v1.3.149

- **IPS-friendly / stealth scanning** — probes one host gently (1 port at a time by default, randomized order, jittered delay) so Symantec SEP and similar endpoint IPS do not block NetDash's source IP for 600 s. Env: `NETDASH_IPS_FRIENDLY`, `NETDASH_PORT_PARALLEL_PER_HOST`, `NETDASH_PORTS_PER_HOST_DELAY`, `NETDASH_PORTS_PER_HOST_JITTER`, `NETDASH_SCAN_RANDOMIZE_PORTS` (all on by default). Increase `NETDASH_PORTS_PER_HOST_DELAY` if still blocked.

### v1.3.148

- **Mobile WOL/SOL tap fix** — tile action buttons (⚡ WOL, 💤 SOL, pin, edit, notes) are always visible and tappable on touch devices; taps no longer fall through to open the service.

### v1.3.147

- **Sleep-on-LAN install scripts** — auto-detect primary-interface MAC on Linux, Windows, and macOS; MAC from NetDash discovery is pre-filled when generating a script from a service.

### v1.3.146

- **Settings → Automatic discovery** — UI toggle to disable background network scanning without a container restart. Manual **Add service** and manual scan still work.

### v1.3.145

- **Brain tile** — discreet **“Open dashboard”** link in the tile header when Brain is online (URL derived from `brain_stats_url`).

### v1.3.144

- **Auto-remove inactive services** — `NETDASH_STALE_REMOVE_DAYS` (0 = off) or checkbox in **Settings → Scanning** removes auto-discovered offline entries after N days; pinned and manual entries are skipped.

### v1.3.143

- **Health check fixes** — local-IP services are probed like remote hosts; offline status after N consecutive failures (`NETDASH_HEALTH_OFFLINE_AFTER_FAILURES`).

### v1.3.142

- **`NETDASH_DISCOVERY_ENABLED` kill switch** — master off for background TCP discovery; auto-disabled on hosts with &lt;~2.1 GB RAM. Nuclear-safe **2 GB VM** defaults in `dockge/compose.yaml` (512M limit, discovery off, enrich off).
- **Watchtower** — `nickfedor/watchtower:1.7.1` in Dockge compose (Docker 29+ / API 1.44+). Balanced deploy: `bash dockge/deploy-balanced.sh`.

### v1.3.141

- **Two scan modes** — **automatic** (adaptive background, `/28` chunks, `NETDASH_AUTO_DISCOVERY_ALL_PORTS`) vs **manual** (Scan options button, hard limits, Stop). QNAP/Proxmox port probes fixed (8006, DSM 5000/5001/8080/8081).

### v1.3.140

- **Discover services on any port** — `NETDASH_AUTO_DISCOVERY_ALL_PORTS=true` (auto, gradual) or `NETDASH_SCAN_ALL_PORTS=true` (manual) deep-probes live hosts against ~190 service ports (`8123`, `32400`, `9090`, …).

### v1.3.137 to 1.3.139

- **Network tile polish** — link latency (Cloudflare / Google) replaced the category donut; the WAN line shows city + country; the tile fits the widget.
- **API vault & notes** — key cards no longer overlap in the narrow tile; notes are full-width list rows.

### v1.3.136

- **Stop a running network scan** — the scan bar now has a **Stop** button that cancels the background job.
- Network tile shows a real **country flag image** (emoji flags don't render on Windows); revealed API keys stay inside the card (scrollable).

### v1.3.134

- **Network tile** (off by default) — LAN IP / gateway / subnet, device online/total counts, **WAN public IP + ISP/country** (GeoIP) with flag, a services-by-category **donut** and a 7-day discovery **sparkline**.
- **"Update now" via the Watchtower HTTP API** — triggers an immediate pull + recreate without mounting `docker.sock` into the portal (safe on QNAP).

### v1.3.133

- **Optional Brain stats tile** (off by default) — point it at a Brain `/stats` endpoint (knowledge counts) in Settings → Appearance and it shows live numbers; served via the auth-gated `/api/brain/stats` proxy.

### v1.3.132

- Visible brand/icon **watermark on every tile** — pinned cards and emoji/letter tiles now included (no more blank backgrounds).

### v1.3.131 — security hardening

- Login **brute-force guard** (`429` + `Retry-After`, 5 attempts / 5 min per IP+user); UI-set password no longer overwritten on restart.
- Swagger `/docs` **off by default** (`NETDASH_DOCS_ENABLED=true` to enable).
- `python-jose` → **`PyJWT`** (CVE-2024-33663/33664); SSRF guard for cloud-metadata endpoints.

### Deployment

- **Recommended:** Proxmox Ubuntu VM + Dockge — **[dockge/README.md](dockge/README.md)** (2 GB RAM sufficient; balanced profile: `dockge/deploy-balanced.sh`).
- **QNAP:** deprecated — **[DEPRECATION-QNAP.md](DEPRECATION-QNAP.md)**.

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

NetDash has **two scan modes**:

| Mode | Trigger | Purpose |
|------|---------|---------|
| **Automatic discovery** | Background (`NETDASH_DISCOVERY_MODE=adaptive`) | Low-priority, throttled scan from **Settings → Automatic discovery** (or `NETDASH_SCAN_CIDR`). Rotates `/28` chunks; optional gradual all-port probe via `NETDASH_AUTO_DISCOVERY_ALL_PORTS` (off by default on 2 GB VMs). Disable entirely with `NETDASH_DISCOVERY_ENABLED=false`. |
| **Manual scan** | **Scan options** button | On-demand CIDR scan. Hard limits (`NETDASH_MANUAL_SCAN_MAX_HOSTS`, max `/24`). Optional `NETDASH_SCAN_ALL_PORTS=true` for full port list. **Stop** button cancels the job. |

1. Sign in.
2. For manual scan: click **Scan options**, pick a CIDR (e.g. `192.168.1.144/28`), confirm.
3. For automatic discovery: set CIDR in **Settings → Automatic discovery** and ensure `NETDASH_DISCOVERY_MODE=adaptive` (default in `dockge/compose.yaml`).
4. Services appear in real time.

> **Docker note:** without `network_mode: host`, the container scans its own bridge network (172.x), not your LAN. On Linux, `docker-compose.yml` uses `network_mode: host`. On Windows/macOS, disable host mode and set `NETDASH_SCAN_CIDR=192.168.1.0/24` in `.env` or in Settings → Automatic discovery.

### IPS-friendly scanning (Symantec SEP / endpoint IPS)

On LANs where workstations run Symantec Endpoint Protection or similar endpoint IPS, aggressive port scanning can trigger a **600 s block** on NetDash's source IP (`The client will block traffic from IP address … for the next 600 seconds`). This was most likely when deep-probing ~190 service ports on a single live host at once.

**IPS-friendly mode** (on by default) probes each host gently: limited per-host parallelism, randomized port order, and a jittered delay between probes to the same host. Cross-host parallelism is unchanged, so discovery stays effective. Health checks serialize probes to the same host too.

| Variable | Default | Purpose |
|----------|---------|---------|
| `NETDASH_IPS_FRIENDLY` | `true` | Master switch for gentle per-host probing |
| `NETDASH_PORT_PARALLEL_PER_HOST` | `1` | Max concurrent port probes to one host |
| `NETDASH_PORTS_PER_HOST_DELAY` | `0.3` | Seconds between probes to the same host |
| `NETDASH_PORTS_PER_HOST_JITTER` | `0.2` | Random extra delay (0…N s) per probe |
| `NETDASH_SCAN_RANDOMIZE_PORTS` | `true` | Randomize port order (avoids sequential scan signatures) |

If SEP still blocks NetDash, increase `NETDASH_PORTS_PER_HOST_DELAY` (e.g. `0.6`–`1.0`). Set `NETDASH_IPS_FRIENDLY=false` only on isolated lab networks where fast scanning matters more than IPS avoidance.

## Low-resource hardware profile (RPi, older PC, N100, 2 GB VM)

NetDash is designed to run on low-resource homelab hardware. A **2 GB Proxmox VM** is enough for NetDash solo (512M container limit in `dockge/compose.yaml`). Safe scan mode (`NETDASH_SCAN_SAFE_MODE=true`) is on by default with lower concurrency, a shorter port list, and host limits.

| Problem | Recommendation |
|---------|----------------|
| Host becomes unstable during scans | Keep safe mode enabled; use **automatic discovery** (chunked `/28`) instead of manual `/24` |
| Need full LAN coverage | Set `NETDASH_SCAN_CIDR=192.168.1.0/24` and `NETDASH_DISCOVERY_MODE=adaptive` — background scan covers the /24 over time |
| Manual scan on strong hardware | Keep `NETDASH_SCAN_SAFE_MODE=true` on shared VLANs; use `/28` manual scans or accept confirmation for `/24` |
| Scans are too slow on strong hardware | Tune `NETDASH_DISCOVERY_INTERVAL` or `NETDASH_DISCOVERY_PROFILE=strong` — do not disable chunking on weak hosts |
| Full port scan needed | `NETDASH_AUTO_DISCOVERY_ALL_PORTS=true` (auto, gradual — 4 GB+ VM) or `NETDASH_SCAN_ALL_PORTS=true` (manual only) |
| Discovery overloads weak host | `NETDASH_DISCOVERY_ENABLED=false` or use ultra-safe profile in `.env.example` |
| Symantec SEP / IPS blocks NetDash IP | IPS-friendly mode is on by default; increase `NETDASH_PORTS_PER_HOST_DELAY` (e.g. `0.6`–`1.0`) |
| Health checks consume too many resources | Increase health-check interval (for example 120s) or disable it |
| Stale offline services clutter the list | Enable auto-remove in **Settings → Scanning** or set `NETDASH_STALE_REMOVE_DAYS=7` |

Example `.env` for Proxmox VM 2 GB (balanced — or run `bash dockge/deploy-balanced.sh`):

```env
NETDASH_DISCOVERY_ENABLED=true
NETDASH_SCAN_SAFE_MODE=true
NETDASH_DISCOVERY_MODE=adaptive
NETDASH_SCAN_CIDR=192.168.1.0/24
NETDASH_AUTO_DISCOVERY_ALL_PORTS=false
NETDASH_AUTO_DISCOVERY_ALWAYS_CHUNK=true
```

Example `.env` for low-resource hosts:

```env
NETDASH_SCAN_SAFE_MODE=true
NETDASH_SCAN_CIDR=192.168.1.0/28
```

Check profile output: `curl -s http://127.0.0.1:18787/api/health` → `scan_safe_mode`, `resource_profile`, `auto_discovery_all_ports`.

Deployment details: **[DEPLOYMENT.md](DEPLOYMENT.md)** · Dockge: **[dockge/README.md](dockge/README.md)** · QNAP (deprecated): **[DEPRECATION-QNAP.md](DEPRECATION-QNAP.md)**.

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
| `NETDASH_SCAN_CIDR` | Networks for automatic discovery (and Docker bridge LAN override) |
| `NETDASH_DISCOVERY_ENABLED` | Master switch for background TCP discovery (`false` by default in Dockge compose); UI toggle in **Settings → Automatic discovery** when env is not locked |
| `NETDASH_DISCOVERY_MODE` | `adaptive` (background TCP discovery), `arp`, `local`, or `remote` |
| `NETDASH_SCAN_SAFE_MODE` | Safe manual scan limits (`true` by default) |
| `NETDASH_SCAN_ALL_PORTS` | Deep-probe live hosts on ~190 service ports during **manual** scan (`false` by default) |
| `NETDASH_AUTO_DISCOVERY_ALL_PORTS` | Gradual ~190-port probe on live hosts in auto mode (`false` by default on 2 GB VMs) |
| `NETDASH_AUTO_DISCOVERY_ALWAYS_CHUNK` | Never scan full /24 in one auto cycle (`true` by default) |
| `NETDASH_MANUAL_SCAN_MAX_HOSTS` | Hard cap for manual scan host count (default `128`) |
| `NETDASH_IPS_FRIENDLY` | Gentle per-host port probing to avoid endpoint IPS blocks (`true` by default) |
| `NETDASH_PORT_PARALLEL_PER_HOST` | Max concurrent port probes to one host when IPS-friendly (default `1`) |
| `NETDASH_PORTS_PER_HOST_DELAY` | Seconds between port probes to the same host (default `0.3`) |
| `NETDASH_PORTS_PER_HOST_JITTER` | Random extra delay per same-host probe (default `0.2`) |
| `NETDASH_SCAN_RANDOMIZE_PORTS` | Randomize port probe order (`true` by default) |
| `NETDASH_STALE_REMOVE_DAYS` | Auto-remove auto-discovered offline services after N days (`0` = off; UI in Settings → Scanning overrides when &gt; 0) |
| `NETDASH_HEALTH_OFFLINE_AFTER_FAILURES` | Mark service offline after N consecutive failed health probes (default `2`) |
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
├── dockge/           # Proxmox + Dockge (recommended)
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
