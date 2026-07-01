# NetDash na QNAP przez Dockge — wdrożenie i aktualizacje

> **Status: deprecated.** New installs: **[DEPRECATION-QNAP.md](../DEPRECATION-QNAP.md)** — Linux VM (Proxmox) + **[dockge/compose.yaml](../dockge/compose.yaml)**.

Archive guide for **QNAP NAS** managed via **[Dockge](https://github.com/louislam/dockge)**. Repository: [lobrzut/netdash](https://github.com/lobrzut/netdash)

> **Container Station stays installed** — it provides the Docker engine. Dockge is a management layer on top (instead of Container Station GUI, which cannot edit compose after deploy).

Przykłady:
- **QNAP NAS:** `http://nas.local:18787`
- **Homelab Linux:** `http://192.168.1.201:18787`

Port nasłuchu domyślnie **18787** — unika kolizji z Readarr (**8787**). Na QNAP z Readarr **nie** używaj 8787.

---

## Wymagania

- QNAP z **Container Station** (silnik Dockera) i włączonym **SSH** (Panel sterowania → Telnet/SSH)
- Dostęp do internetu (pobieranie obrazu z `ghcr.io`)
- LAN — NetDash skanuje sieć w trybie **`network_mode: host`**

> **Host network na QNAP:** w czystym `docker compose` (przez Dockge) host mode daje prawdziwy dostęp do sieci hosta. Gdy skan nie widzi LAN, ustaw `NETDASH_SCAN_CIDR` w `.env` albo CIDR w panelu (Ustawienia → Skanowanie). Awaryjnie: [`docker-compose.bridge.yml`](../deploy/qnap/docker-compose.bridge.yml).

---

## 1. Postaw Dockge (raz)

Dockge to jeden kontener. Najprościej odpalić go **raz przez Container Station** (Create Application → wklej poniższe), potem zarządzasz już tylko z Dockge.

```yaml
services:
  dockge:
    image: louislam/dockge:1
    container_name: dockge
    restart: unless-stopped
    ports:
      - "5151:5001"          # 5000/5001 zajęte przez panel QTS — daj inny wolny port
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - /share/Container/dockge/data:/app/data
      # ścieżka MUSI być identyczna host:kontener (gotcha Dockge — patrz niżej)
      - /share/Container/dockge/stacks:/share/Container/dockge/stacks
    environment:
      - DOCKGE_STACKS_DIR=/share/Container/dockge/stacks
```

→ **Create → Start** → otwórz `http://<IP-QNAP>:5151` → załóż konto admina.

> **Gotcha Dockge:** katalog stacków musi mieć **tę samą ścieżkę** w hoście i kontenerze (`/share/Container/dockge/stacks` w obu) — inaczej zagnieżdżony `docker compose` nie znajdzie wolumenów.
>
> **Port:** `5000`/`5001` należą do panelu QTS — użyj innego (np. `5151`). Patrz też kolizja Readarr na `8787`.
>
> **docker.sock:** jeśli Dockge nie łączy się z Dockerem, sprawdź `ls -l /var/run/docker.sock` po SSH — na części QNAP socket jest pod ścieżką Container Station; podmień lewą stronę montażu.

---

## 2. Dodaj NetDash jako stack w Dockge

W Dockge: **+ Compose** → nazwa `netdash` → wklej:

```yaml
services:
  netdash:
    image: ghcr.io/lobrzut/netdash:latest
    container_name: netdash
    restart: always
    network_mode: host          # skan LAN (ping/ARP); BEZ sekcji ports:
    env_file: .env
    environment:
      NETDASH_LISTEN_PORT: "18787"
      NETDASH_DISCOVERY_MODE: "adaptive"
      NETDASH_SCAN_SAFE_MODE: "true"   # QNAP throttled; mocny NAS może dać false
    volumes:
      - ./data:/app/data
    cap_add:
      - NET_RAW
    labels:
      com.centurylinklabs.watchtower.enable: "true"
    healthcheck:
      test: ["CMD-SHELL", "curl -f http://127.0.0.1:18787/api/health || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s
```

Obok jest edytor **`.env`** tego stacka — wklej:

```env
NETDASH_SECRET_KEY=<losowy-min-32-znaki>
NETDASH_DEFAULT_ADMIN_USER=admin
NETDASH_DEFAULT_ADMIN_PASSWORD=changeme
```

Klucz wygeneruj po SSH: `openssl rand -base64 32`

→ **Save → Deploy**. (W host mode CIDR LAN-u wykrywa się sam; inaczej ustaw w Ustawienia → Skanowanie.)

---

## 3. Wejdź

`http://<IP-QNAP>:18787` → login `admin` / `changeme` → **zmień hasło** (Ustawienia → Hasło; zmiana w UI jest trwała po restarcie).

```bash
curl -s http://127.0.0.1:18787/api/health
```

---

## 4. Aktualizacje (zero reimportu)

- **Ręcznie (zalecane):** Dockge → stack `netdash` → **Update** (pull najnowszego obrazu + redeploy). Compose/`.env` edytujesz **kiedy chcesz** — to cała przewaga nad Container Station.
- **Automatycznie (Watchtower):** dodaj serwis `watchtower` do stacka (jak w [`deploy/qnap/docker-compose.full.yml`](../deploy/qnap/docker-compose.full.yml)) — co ~1 h podmienia `:latest`. Obraz musi być `:latest` (nie semver), inaczej digest się nie zmieni.

Dane w `./data` (SQLite + ikony) pozostają przy każdej aktualizacji. Backupuj `/share/Container/dockge/stacks/netdash/data/`.

---

## 5. Strojenie skanu (Dockge to umożliwia)

Throttle „safe mode" jest domyślnie ON, bo słaby NAS pada przy flood TCP na /24. Dzięki Dockge możesz **bezpiecznie sprawdzić sufit swojego sprzętu** — w `.env`:

```env
NETDASH_SCAN_SAFE_MODE=false
NETDASH_DISCOVERY_PROFILE=strong
```

→ Redeploy → odpal skan i patrz na NAS (CPU/RAM, responsywność QTS). Stabilnie → zostaw (pełny szybki skan, całe /24). NAS się dławi → wróć do `true`. Cofnięcie w Dockge to sekundy.

---

## Rozwiązywanie problemów

| Problem | Rozwiązanie |
|---|---|
| **Port 5001 zajęty** | To panel QTS (5000/5001). Daj Dockge inny port (np. `5151`). |
| **Crash loop / port 8787** | Stary `NETDASH_PORT=8787`. Entrypoint wymusza 18787 — w logach musi być `LISTEN_PORT=18787`. |
| **Skan nie widzi LAN** | Ustaw `NETDASH_SCAN_CIDR` w `.env` lub CIDR w Ustawienia → Skanowanie; awaryjnie `docker-compose.bridge.yml`. |
| **Nie mogę się zalogować** | `/api/health` → `admin_ready: true`. Domyślnie `admin`/`changeme`. |
| **Dockge nie łączy się z Dockerem** | Sprawdź ścieżkę `docker.sock` (patrz pkt 1). |

---

## Opcja zaawansowana: „Aktualizuj teraz" z portalu

**Ryzyko:** montowanie `/var/run/docker.sock` daje kontenerowi NetDash pełną kontrolę nad Dockerem na hoście. Na QNAP zwykle zbędne — Dockge/Watchtower wystarczą. Jeśli akceptujesz ryzyko: dodaj `- /var/run/docker.sock:/var/run/docker.sock` do `volumes:` i `NETDASH_UPDATE_APPLY_ENABLED=true` do `.env`, redeploy.

---

## Powiązane pliki

- [`dockge/compose.yaml`](../dockge/compose.yaml) — stack NetDash dla Dockge
- [`deploy/qnap/README.md`](../deploy/qnap/README.md) — krótki przewodnik QNAP/Dockge
- [`deploy/qnap/docker-compose.full.yml`](../deploy/qnap/docker-compose.full.yml) — NetDash + Watchtower
- [`deploy/qnap/docker-compose.bridge.yml`](../deploy/qnap/docker-compose.bridge.yml) — bridge mode (gdy host mode nie skanuje)
- [`DEPLOYMENT.md`](../DEPLOYMENT.md) — ogólny przewodnik wdrożenia
