# NetDash na QNAP — przez Dockge

> **DEPRECATED (2026-07):** QNAP deployment is no longer supported — high NAS load, incomplete port scans, Container Station limits. **Recommended:** Ubuntu VM on Proxmox + Dockge → **[DEPRECATION-QNAP.md](../../DEPRECATION-QNAP.md)** · **[dockge/README.md](../../dockge/README.md)**.

Deploying [NetDash](https://github.com/lobrzut/netdash) on **QNAP** via **[Dockge](https://github.com/louislam/dockge)** (archive / existing installs). Container Station remains the Docker engine; Dockge provides an editable compose UI.

> **Container Station cannot edit compose after deploy.** The steps below remain for existing installations and reference only.

Pełny przewodnik: **[docs/QNAP.md](../../docs/QNAP.md)**.

## Szybki start (3 kroki)

**1. Postaw Dockge raz** (Container Station → Create Application → wklej):
```yaml
services:
  dockge:
    image: louislam/dockge:1
    container_name: dockge
    restart: unless-stopped
    ports: ["5151:5001"]                 # 5000/5001 = panel QTS, daj inny port
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - /share/Container/dockge/data:/app/data
      - /share/Container/dockge/stacks:/share/Container/dockge/stacks   # host == kontener
    environment:
      - DOCKGE_STACKS_DIR=/share/Container/dockge/stacks
```
→ `http://<IP-QNAP>:5151` → konto admina.

**2. Dodaj stack `netdash`** w Dockge (+ Compose) — wklej [`docker-compose.full.yml`](docker-compose.full.yml) (NetDash + Watchtower) lub minimalny [`docker-compose.yml`](docker-compose.yml). W edytorze `.env` ustaw `NETDASH_SECRET_KEY` (`openssl rand -base64 32`) i `NETDASH_DEFAULT_ADMIN_PASSWORD`. → **Deploy**.

**3. Wejdź** `http://<IP-QNAP>:18787` → `admin` / `changeme` → zmień hasło.

## Pliki compose

| Plik | Zastosowanie |
|------|--------------|
| [`docker-compose.full.yml`](docker-compose.full.yml) | NetDash + Watchtower (auto-update) — zalecany |
| [`docker-compose.yml`](docker-compose.yml) | sam NetDash (bez Watchtower) |
| [`docker-compose.bridge.yml`](docker-compose.bridge.yml) | bridge mode, gdy host mode nie skanuje LAN |

> **Host network:** wymagany do skanu LAN. **Nigdy** nie łącz `network_mode: host` z `ports:` — Docker odmówi startu. Portal słucha na porcie hosta **18787**.

## Aktualizacje

- **Dockge → stack `netdash` → Update** (pull + redeploy), albo
- **Watchtower** (w `docker-compose.full.yml`) — co ~1 h podmienia `:latest`.

Dane w `./data` pozostają. Backupuj `/share/Container/dockge/stacks/netdash/data/`.

## Skan sieci — nie działa / nie widzę przycisku

- Host mode nie widzi LAN → ustaw `NETDASH_SCAN_CIDR` w `.env` lub CIDR w **Ustawienia → Skanowanie**, redeploy.
- Słaby NAS pełza po /28 → spróbuj `NETDASH_SCAN_SAFE_MODE=false` + `NETDASH_DISCOVERY_PROFILE=strong` i obserwuj NAS (Dockge cofa zmianę w sekundę).
- Dalej nic → [`docker-compose.bridge.yml`](docker-compose.bridge.yml).

## Rozwiązywanie problemów (QNAP / Dockge)

| Problem | Rozwiązanie |
|---|---|
| Port 5001 zajęty | panel QTS — daj Dockge inny port (5151) |
| Crash loop / `Errno 98` na 8787 | stary `NETDASH_PORT`; entrypoint wymusza 18787 (sprawdź log) |
| Readarr na 8787 | NetDash i tak słucha na 18787 — bez kolizji |
| Dockge bez połączenia z Dockerem | sprawdź ścieżkę `/var/run/docker.sock` |
