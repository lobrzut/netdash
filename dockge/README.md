# NetDash on Dockge (Proxmox Ubuntu VM — recommended)

One-click deploy of [NetDash](https://github.com/lobrzut/netdash) via [Dockge](https://github.com/louislam/dockge) on a **Linux** Docker host. This replaces the deprecated [QNAP path](../DEPRECATION-QNAP.md).

## Proxmox Ubuntu VM — step by step

1. **Create VM** in Proxmox: Ubuntu Server 24.04 LTS, 2 vCPU, 2 GB RAM, 16 GB disk, bridged `vmbr0` to LAN.
2. **Install Docker** on the VM:

```bash
sudo apt update && sudo apt install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" | sudo tee /etc/apt/sources.list.d/docker.list
sudo apt update && sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
sudo usermod -aG docker $USER   # re-login
```

3. **Install Dockge** (optional but recommended):

```bash
sudo mkdir -p /opt/stacks /opt/dockge
cd /opt/dockge
curl -fsSL https://raw.githubusercontent.com/louislam/dockge/master/compose.yaml -o compose.yaml
sudo docker compose up -d
```

Dockge UI: `http://<vm-ip>:5001`

4. **Clone NetDash** into stacks directory:

```bash
git clone https://github.com/lobrzut/netdash.git /opt/stacks/netdash
cd /opt/stacks/netdash
cp .env.example .env
nano .env   # set NETDASH_SECRET_KEY (≥32 chars)
```

5. **Deploy** — Dockge → **Scan Stacks Folder** → stack **netdash** → **Deploy**, or CLI:

```bash
docker compose -f dockge/compose.yaml up -d
```

6. **Verify:** `curl -s http://127.0.0.1:18787/api/health` → open `http://<vm-ip>:18787`, login `admin` / `changeme`, change password.

7. **Tuning (dedicated VM):** keep `NETDASH_SCAN_SAFE_MODE=true` on shared VLANs. Set `NETDASH_SCAN_CIDR=192.168.1.0/24` in `.env` or **Settings → Automatic discovery**. Auto-discovery (`NETDASH_DISCOVERY_MODE=adaptive`, default in `dockge/compose.yaml`) scans in `/28` chunks with gradual all-port probing on live hosts. Manual scan via **Scan options** has hard limits — avoid `NETDASH_SCAN_SAFE_MODE=false` on `/24` unless you accept network load.

## 2 GB Proxmox VM — memory and discovery

On a **2 GB RAM** Ubuntu VM (OS + Docker + Dockge + NetDash), a **1024M** container limit together with **NETDASH_AUTO_DISCOVERY_ALL_PORTS=true** can push the host into **OOM** and kernel panics (observed on v1.3.141).

**Defaults in dockge/compose.yaml (v1.3.142+):** memory: 512M, NETDASH_AUTO_DISCOVERY_ALL_PORTS=false, NETDASH_DISCOVERY_MODE=adaptive.

Recommended .env on 2 GB hosts (see [.env.example](../.env.example) — *PROFIL 2 GB VM*):

- NETDASH_DISCOVERY_PROFILE=weak **or** NETDASH_DISCOVERY_INTERVAL=600
- Keep NETDASH_AUTO_DISCOVERY_ALL_PORTS=false unless you have more RAM
- NETDASH_SCAN_SAFE_MODE=true and a bounded NETDASH_SCAN_CIDR

After git pull, redeploy: docker compose -f dockge/compose.yaml up -d


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
| `NETDASH_DEFAULT_ADMIN_PASSWORD` | Default `changeme` — **change after first login** |

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
curl -s http://127.0.0.1:18787/api/health
docker compose -f /opt/stacks/netdash/docker-compose.yml ps
```

Open **http://&lt;server-ip&gt;:18787** — login **`admin` / `changeme`**, then **change the password** in Settings → Password.

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
| **Host network** | Required for LAN scan. Container listens on host port **18787** (`NETDASH_PORT`) directly — no `ports:` mapping. |
| **ports + host** | Never combine `network_mode: host` with `ports:` — Docker will refuse to start. |
| **Linux only** | `network_mode: host` on Docker Desktop (Windows/Mac) does not expose your LAN; use native `python run.py` or `docker-compose.dev.yml` with `NETDASH_SCAN_CIDR`. |
| **Data** | Bind mount `./data:/app/data` — SQLite `./data/netdash.db`, uploaded icons/logos `./data/uploads/`. Back up `/opt/stacks/netdash/data/`. |
| **Build date** | Optional in `.env`: `NETDASH_BUILD_DATE=2026-06-11` (About panel; passed as Docker build arg). |
| **Updates** | Watchtower runs with the stack (polls GHCR daily, updates NetDash via label). Manual: `docker compose pull && docker compose up -d`. Build from git: `git pull && docker compose up -d --build`. Set `WATCHTOWER_LABEL_ENABLE=false` on watchtower to update all containers on the host. QNAP: [docs/QNAP.md](../docs/QNAP.md). |
| **Secrets** | Never commit `.env`. Dockge stores compose on disk; keep `.env` gitignored. |

Full deployment guide: **[DEPLOYMENT.md](../DEPLOYMENT.md)**
