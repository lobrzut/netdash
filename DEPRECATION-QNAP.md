# Deprecation: NetDash on QNAP NAS

**Status:** deprecated as of 2026-07 · **Recommended replacement:** Linux VM (e.g. Ubuntu on Proxmox) with Docker + [Dockge](https://github.com/louislam/dockge) and [`dockge/compose.yaml`](dockge/compose.yaml).

The QNAP-specific deployment path (`deploy/qnap/`, Container Station import URLs, `docs/QNAP.md`) is **no longer maintained** for production use. Files remain in the repository for reference and for users who already run NetDash on QNAP and need troubleshooting notes.

---

## Summary (why we are abandoning QNAP)

| Issue | What happens on QNAP | On a standard Linux Docker host |
|-------|----------------------|----------------------------------|
| **Host instability** | Full LAN scans spike CPU/RAM and can freeze or reboot the NAS — limits in compose do not protect the **host kernel** | `network_mode: host` + real `NET_RAW`; container limits match host capacity |
| **Incomplete port discovery** | Safe mode + `weak` profile scan only a **subset** of ports per cycle; `/24` is split into `/28` chunks (~40 min for full sweep) | `normal` / `strong` profile scans the full CIDR every few minutes; optional `NETDASH_SCAN_ALL_PORTS` on capable hosts (v1.3.140+) |
| **Container Station limits** | Compose **cannot be edited** after import — every fix requires delete + reimport | Dockge / `docker compose` — edit `.env` and redeploy in seconds |
| **`network_mode: host` semantics** | QNAP Docker does not expose the LAN the same way as bare Linux; bridge fallback loses LAN scan unless you tune CIDR manually | Native host networking — ping, ARP, and TCP discovery work as designed |
| **Operational cost** | Watchtower + adaptive discovery + health checks compete with NAS I/O (RAID, SMB, backups) | Dedicated small VM (2 vCPU / 2 GB RAM) isolates NetDash from storage workloads |

---

## Technical background (from the codebase)

### 1. Resource usage can “kill” the QNAP

NetDash intentionally throttles scans on weak hardware, but QNAP still sits in the worst case:

- Official QNAP compose sets `NETDASH_SCAN_SAFE_MODE=true` and `NETDASH_DISCOVERY_PROFILE=auto`, which resolves to profile **`weak`** on low-RAM hosts (`app/discovery_pipeline.py`).
- Even with Docker `mem_limit: 512M`, the comment in `app/scanner.py` states that the **QNAP kernel can OOM or crash on TCP floods** — traffic is generated on the host network stack, not only inside the cgroup.
- Adaptive discovery runs on an interval (default 300 s on weak) and probes multiple ports per live host with parallel workers (`tcp_parallel=8`, `port_parallel=4` on weak).

On a NAS that also serves files, runs backups, and hosts other containers, a discovery cycle can cause UI freezes, SSH drops, or an unplanned reboot.

### 2. Not all ports are scanned (by design on weak / safe mode)

This is **not a bug** on QNAP — it is the **intended trade-off** to keep the NAS alive:

| Mode | Ports used for discovery | Scan scope |
|------|--------------------------|------------|
| **Safe / weak (QNAP default)** | `SAFE_WEB_PORTS`: 80, 443, 8080, 5000, 18787 · primary TCP list trimmed · manual “aggressive” scan still chunked | `/24` → **16× `/28` chunks**; 2 chunks per 5 min cycle → **~40 minutes** to cover one `/24` |
| **Normal / strong (Linux server)** | Full `TCP_DISCOVERY_PRIMARY_PORTS` and `WEB_PORTS`; full CIDR each cycle | Entire `NETDASH_SCAN_CIDR` every 2–3 minutes |
| **popular / all_listed (v1.3.153+)** | ~45 homelab ports (or ~190 `all_listed`) on **live** hosts only | Works with `NETDASH_SCAN_SAFE_MODE=true` (IPS-friendly). Still **not recommended on QNAP** — use a Linux VM + on-demand scan |

Services on uncommon ports (e.g. custom high ports, some game servers, non-standard admin UIs) may **not appear until their `/28` chunk is scanned**, or may **never appear** if only safe ports are probed in automatic discovery.

### 3. QNAP-specific operational problems

Documented in `deploy/qnap/README.md` and `docs/QNAP.md`:

- **Container Station** does not allow editing compose after deploy — configuration drift is painful.
- **Host vs bridge networking** — if host mode fails to see the LAN, the workaround (`docker-compose.bridge.yml`) breaks native scanning unless `NETDASH_SCAN_CIDR` is set and you accept bridge limitations.
- **Port 8787 crash loops** — legacy images conflict with Readarr; recovery requires full application delete + reimport.
- **Remote discovery agent** (`deploy/agent/`) was added as a workaround (dashboard on QNAP, scanner on another host) — adds moving parts and API credentials to manage.

### 4. Brain / project history

Vault notes (`2026-06-08` NetDash session) record early homelab work at `C:\opt\netdash` and GitHub `lobrzut/netdash`, with QNAP/homelab split (`.150` NAS vs `.201` server). The architecture evolved toward **dashboard on capable Linux** and away from running heavy discovery on the NAS — QNAP deprecation formalizes that direction.

---

## Recommended deployment path

**Target:** Ubuntu Server VM on Proxmox (or any Linux host with Docker).

1. Create VM: 2 vCPU, 2 GB RAM, 8–16 GB disk, bridged NIC to LAN.
2. Install Docker + Dockge (or use existing Dockge host).
3. Deploy stack from this repository:

```bash
git clone https://github.com/lobrzut/netdash.git /opt/stacks/netdash
cd /opt/stacks/netdash
cp .env.example .env
# edit NETDASH_SECRET_KEY; keep SCAN_SAFE_MODE=true; discovery defaults to on_demand
docker compose -f dockge/compose.yaml up -d
```

4. Open `http://<vm-ip>:18787` → login `admin` / `changeme` → change password.

Full steps: **[dockge/README.md](dockge/README.md)** · **[DEPLOYMENT.md](DEPLOYMENT.md)**

### Optional: keep QNAP as dashboard-only (legacy)

If you must keep the UI on QNAP temporarily:

```env
NETDASH_SCAN_DISABLED=true
```

Run [`deploy/agent/`](deploy/agent/) on the Proxmox VM or homelab server (`network_mode: host`) to push discovery results to `POST /api/discovery/import`. This is more complex than running NetDash entirely on the VM.

---

## What happens to QNAP files in this repo

| Path | Status |
|------|--------|
| `deploy/qnap/*` | **Frozen** — no new features; critical security fixes only |
| `docs/QNAP.md` | **Historical** — points here |
| `deploy/qnap/README.md` | **Banner added** — directs to Dockge / Linux |
| `dockge/compose.yaml` | **Supported** — primary compose for homelab |

---

## Migration checklist (QNAP → Proxmox VM)

1. **Backup** QNAP data: `/share/Container/netdash/data/` (SQLite `netdash.db`, `uploads/`, `.secret`).
2. **Stop** NetDash application in Container Station (and Watchtower if running).
3. **Deploy** on Ubuntu VM with `dockge/compose.yaml`.
4. **Copy** backed-up `data/` to `/opt/stacks/netdash/data/` on the VM.
5. **Set CIDR** in Settings → Scanning if not `192.168.1.0/24`.
6. On a dedicated VM with spare CPU, consider `NETDASH_SCAN_SAFE_MODE=false` in `.env` for faster, fuller scans.
7. **Verify** `curl http://<vm-ip>:18787/api/health` → `scan_safe_mode`, `resource_profile`.
8. **Remove** QNAP stack when satisfied.

---

## References

- [`app/scanner.py`](app/scanner.py) — `SAFE_WEB_PORTS`, QNAP OOM comment
- [`app/discovery_pipeline.py`](app/discovery_pipeline.py) — `weak` profile, `/28` chunk rotation
- [`deploy/qnap/README.md`](deploy/qnap/README.md) — original QNAP one-shot import
- [`dockge/README.md`](dockge/README.md) — supported Dockge deployment
