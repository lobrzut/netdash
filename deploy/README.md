# Deploy NetDash

Pełna dokumentacja: **[../DEPLOYMENT.md](../DEPLOYMENT.md)**.

## Szybki wybór

| Cel | Komenda / link |
|-----|----------------|
| **Linux Docker (bez git)** | [`docker-simple/install.sh`](docker-simple/install.sh) lub `curl …/install.sh \| bash` |
| **QNAP NAS** | **[qnap/README.md](qnap/README.md)** |
| Windows dev | `..\start.ps1` |
| Linux bare metal | `../start.sh` |
| Produkcja (clone repo) | `docker compose up -d` w `/opt/netdash` |
| Test Docker bridge | `docker compose -f docker-compose.dev.yml up` |

## Skrypty w tym katalogu

- **`install.ps1`** — rsync/deploy z Windows (PuTTY plink/pscp) na serwer Linux
- **`install.sh`** — rsync + `docker compose` z maszyny z SSH/rsync
- **`netdash.service`** — systemd (bez Dockera)

## Skan LAN

- **Lokalny Python:** skan `192.168.1.0/24` działa natywnie.
- **Docker produkcja:** `network_mode: host` w `docker-compose.yml` (Linux).
- **Docker bridge:** ustaw `NETDASH_SCAN_CIDR=192.168.1.0/24` w `.env`.
