# How to scan (on demand)

NetDash is a **homelab dashboard** (Homer / Homepage style). LAN discovery is **optional and on demand** by default — not a continuous scanner.

Recommended policy: **`on_demand`**. No background TCP. You add tiles manually, or click **Scan network** when you want an inventory.

Full env list: [`.env.example`](../.env.example). Deploy: [`DEPLOYMENT.md`](../DEPLOYMENT.md).

## Three steps

1. **Set your LAN** — `NETDASH_SCAN_CIDR=192.168.1.0/24` in `.env`, or **Settings → Automatic discovery**.
2. **Keep policy on demand** — **Settings → Automatic discovery → Policy = On demand** (Dockge default).
3. **Scan when you need it** — **Scan network**. Prefer **Popular** ports. Use **Stop** if it runs too long.

Docker without `network_mode: host` scans the bridge (`172.x`), not your LAN — set CIDR or use host networking (Linux).

## Manual scan options

| Action | What it does |
|--------|----------------|
| **Basic** | Short safe list (~12 web/admin ports). Fastest, IPS-friendliest. |
| **Popular** (recommended) | ~45 homelab ports (*arr, Plex/Jellyfin, HA, Immich, qBittorrent `:6363`, …) on **live hosts only**. Works with safe mode. |
| **Targeted probe** | One `IP:port` (+ auto/http/https/tcp) → fingerprint → add/update. No full-network scan. |
| **all_listed** | `NETDASH_SCAN_PORT_PROFILE=all_listed` or `NETDASH_SCAN_ALL_PORTS=true` — ~190 curated service ports on live hosts. **Never 1–65535.** |

A `/24` job still runs as **one scan** but work is split into `/28` chunks so the UI stays responsive (`/api/health` answers during the scan). Timeout scales with hosts × ports (cap `NETDASH_MANUAL_SCAN_TIMEOUT_CAP`, default 7200 s). Partial results on timeout = success, not a red failure.

## Safe mode vs full CIDR

| Setting | Effect |
|---------|--------|
| `NETDASH_SCAN_SAFE_MODE=true` (default) | Low parallelism + IPS-friendly delays. **Does not** shrink a manual scan to `/28`. |
| `NETDASH_MANUAL_SCAN_ALLOW_FULL_CIDR=true` (default) | **Scan network** covers the CIDR from settings (typically `/24`). |
| `NETDASH_MANUAL_SCAN_ALLOW_FULL_CIDR=false` | Legacy: manual scan max `/28`. |

Keep safe mode **on** on shared VLANs (Symantec SEP, Windows IPS). Turning it off only speeds scans on isolated lab networks.

## Discovery policies

| Policy | Background | When to use |
|--------|------------|-------------|
| **`on_demand`** (default) | None | Homelab dashboard + button scan |
| **`off`** | None | Manual tiles only |
| **`passive`** | ARP table ~every 10 min | Host list without TCP |
| **`scheduled`** | One IPS-friendly cycle (`03:00` UTC or `24h`) | Nightly inventory |
| **`adaptive`** (legacy) | Continuous TCP in `/28` chunks | Old behaviour — may trigger SEP |

`NETDASH_DISCOVERY_ENABLED` is the kill switch for **background** policies (`scheduled` / `passive` / `adaptive`). Leave it `false` with `on_demand`.

## IPS / SEP

Endpoint IPS (e.g. Symantec SEP) can **block NetDash’s source IP for 600 s** if many distinct ports hit the same host quickly.

IPS-friendly mode is **on** by default: one port at a time per host, random order, jittered delay.

| Variable | Default |
|----------|---------|
| `NETDASH_IPS_FRIENDLY` | `true` |
| `NETDASH_PORT_PARALLEL_PER_HOST` | `1` |
| `NETDASH_PORTS_PER_HOST_DELAY` | `0.3` |
| `NETDASH_PORTS_PER_HOST_JITTER` | `0.2` |
| `NETDASH_SCAN_RANDOMIZE_PORTS` | `true` |

If SEP still blocks, raise `NETDASH_PORTS_PER_HOST_DELAY` to `0.6`–`1.0`. Set `NETDASH_IPS_FRIENDLY=false` only on isolated labs.

## Recommended `.env` (shared VLAN + SEP)

```env
NETDASH_SCAN_CIDR=192.168.1.0/24
NETDASH_DISCOVERY_POLICY=on_demand
NETDASH_DISCOVERY_ENABLED=false
NETDASH_IPS_FRIENDLY=true
NETDASH_SCAN_SAFE_MODE=true
NETDASH_SCAN_PORT_PROFILE=popular
```
