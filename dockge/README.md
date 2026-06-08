# NetDash on Dockge

One-click deploy of [NetDash](https://github.com/lobrzut/netdash) via [Dockge](https://github.com/louislam/dockge) on a **Linux** Docker host.

## Requirements

- Linux with Docker 20+ and Compose v2 (same as Dockge itself)
- Dockge running (default stacks dir: `/opt/stacks`, UI port `5001`)
- **`network_mode: host`** — NetDash must share the host network to scan your LAN (`192.168.x.0/24`). This does **not** work on Docker Desktop (Windows/Mac).

## Quick deploy from GitHub

### 1. Clone into Dockge stacks directory

```bash
git clone https://github.com/lobrzut/netdash.git /opt/stacks/netdash
cd /opt/stacks/netdash
```

### 2. Configure environment

```bash
cp .env.example .env
nano .env
```

Required in `.env`:

| Variable | Description |
|----------|-------------|
| `NETDASH_SECRET_KEY` | Random string, at least 32 characters |
| `NETDASH_DEFAULT_ADMIN_PASSWORD` | Strong admin password |

Generate a secret key:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 3. Register stack in Dockge

1. Open Dockge → **⋮** (top right) → **Scan Stacks Folder**
2. Stack **netdash** should appear (Dockge finds `docker-compose.yml` or `compose.yaml` at the stack root)
3. Open the stack → **Deploy** (or **Start**)

Optional: copy the Dockge-tuned compose filename:

```bash
cp dockge/compose.yaml compose.yaml
```

Both root `docker-compose.yml` and `dockge/compose.yaml` are equivalent; paths assume the **repository root** is the stack folder.

### 4. Verify

```bash
curl -s http://127.0.0.1:8787/api/health
docker compose -f /opt/stacks/netdash/docker-compose.yml ps
```

Open **http://&lt;server-ip&gt;:8787** — login with `NETDASH_DEFAULT_ADMIN_USER` / `NETDASH_DEFAULT_ADMIN_PASSWORD`, then change the password in Settings.

## Create stack from Dockge UI (paste compose)

If you prefer not to clone manually:

1. Dockge → **+ Compose** → name: `netdash`
2. Paste the contents of [`compose.yaml`](compose.yaml) from this folder
3. Save → create `.env` in `/opt/stacks/netdash/` from [`.env.example`](../.env.example)
4. **Deploy**

For a full git-backed stack, clone the repo into `/opt/stacks/netdash/` afterward so `build: .` and the Dockerfile resolve correctly.

## Compose files in this repo

| File | Use |
|------|-----|
| `/docker-compose.yml` | Production Linux (host network) — auto-detected after clone |
| `dockge/compose.yaml` | Same stack, Dockge-preferred filename + comments |
| `dockge/docker-compose.yml` | Alias; use `-f dockge/docker-compose.yml` only if stack cwd is repo root |
| `docker-compose.dev.yml` | Bridge mode for local testing (not for Dockge production) |

## Caveats

| Topic | Detail |
|-------|--------|
| **Host network** | Required for LAN scan. Container listens on host port **8787** directly — no `ports:` mapping. |
| **ports + host** | Never combine `network_mode: host` with `ports:` — Docker will refuse to start. |
| **Linux only** | `network_mode: host` on Docker Desktop (Windows/Mac) does not expose your LAN; use native `python run.py` or `docker-compose.dev.yml` with `NETDASH_SCAN_CIDR`. |
| **Data** | SQLite at `./data/netdash.db` (bind mount `./data:/app/data`). Back up `/opt/stacks/netdash/data/`. |
| **Updates** | `cd /opt/stacks/netdash && git pull &&` redeploy from Dockge or `docker compose up -d --build`. |
| **Secrets** | Never commit `.env`. Dockge stores compose on disk; keep `.env` gitignored. |

Full deployment guide: **[DEPLOYMENT.md](../DEPLOYMENT.md)**
