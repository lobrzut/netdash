# NetDash na QNAP Container Station — wdrożenie i auto-aktualizacja

Przewodnik dla **QNAP NAS** z **Container Station** (Linux Docker). Repozytorium: [lobrzut/netdash](https://github.com/lobrzut/netdash)

Domyślny przykład serwera: `http://192.168.1.201:8787`

---

## Architektura auto-aktualizacji

```mermaid
flowchart LR
  GH[GitHub Release v*] --> GHA[GitHub Actions]
  GHA --> GHCR[ghcr.io/lobrzut/netdash]
  GHCR --> WT[Watchtower opcjonalnie]
  GHCR --> CS[Container Station pull]
  WT --> ND[NetDash container]
  CS --> ND
  ND --> UI[Portal: Sprawdź aktualizacje]
  GH --> UI
```

| Warstwa | Rola |
|---------|------|
| **GitHub Actions** | Po tagu `v*` buduje obraz i publikuje na GHCR |
| **GHCR** | Gotowy obraz — bez `git` na QNAP |
| **Watchtower** (profil `auto-update`) | Co 24 h sprawdza nowy obraz i restartuje NetDash (tylko z etykietą) |
| **Portal NetDash** | Ustawienia → O projekcie → **Sprawdź aktualizacje** (GitHub API) |
| **Aktualizuj teraz** (opcjonalnie) | Wymaga montowania `docker.sock` — tylko dla zaawansowanych |

**Bezpieczeństwo:** automatyczna aktualizacja obrazu **nie jest włączona domyślnie**. Watchtower uruchamiasz świadomie profilem `auto-update`. Przycisk „Aktualizuj teraz” wymaga jawnej konfiguracji i montowania gniazda Docker (ryzyko — patrz niżej).

---

## Wymagania

- QNAP z Container Station 2.x+
- Dostęp do internetu (pobieranie obrazu z `ghcr.io`)
- Sieć LAN — NetDash skanuje sieć w trybie **`network_mode: host`** (jak na Linuxie)

> **Uwaga:** `network_mode: host` na QNAP działa inaczej niż na czystym Linuxie — w wielu modelach kontener nasłuchuje na porcie hosta (8787). Jeśli skan LAN nie działa, ustaw w `.env`: `NETDASH_SCAN_CIDR=192.168.1.0/24`.

---

## Wdrożenie początkowe (bez git na NAS)

### 1. Przygotuj folder na QNAP

Przez SSH lub File Station utwórz katalog, np.:

```bash
mkdir -p /share/Container/netdash/data
cd /share/Container/netdash
```

### 2. Pliki compose i `.env`

Skopiuj z repozytorium GitHub (na PC):

- `docker-compose.yml`
- `.env.example` → `.env`

Na QNAP w `.env` ustaw minimum:

```env
NETDASH_SECRET_KEY=<losowy-klucz-min-32-znakow>
NETDASH_DEFAULT_ADMIN_PASSWORD=<silne-haslo>
NETDASH_IMAGE_TAG=latest
```

Opcjonalnie sieć skanowania:

```env
NETDASH_SCAN_CIDR=192.168.1.0/24
```

### 3. Container Station — utwórz aplikację

1. **Container Station** → **Create** → **Create Application**
2. **Import** → wskaż `docker-compose.yml` z folderu `/share/Container/netdash`
3. Upewnij się, że wolumen `./data` wskazuje na `/share/Container/netdash/data`
4. **Create** / **Start**

Alternatywa: w Dockge na innym hoście — patrz [DEPLOYMENT.md](../DEPLOYMENT.md).

### 4. Pierwsze uruchomienie obrazu z GHCR

Jeśli na QNAP nie ma lokalnego builda, w SSH (w katalogu stacka):

```bash
docker compose pull
docker compose up -d
```

Obraz: `ghcr.io/lobrzut/netdash:latest`

### 5. Weryfikacja

```bash
curl -s http://127.0.0.1:8787/api/health
```

W przeglądarce: `http://192.168.1.201:8787` → zaloguj się → **Ustawienia** → **O projekcie** → **Sprawdź aktualizacje**.

---

## Auto-aktualizacja — Watchtower (zalecane na QNAP)

Watchtower jest w `docker-compose.yml` w profilu **`auto-update`** — domyślnie **nie startuje**.

### Włączenie

W SSH w katalogu stacka:

```bash
docker compose --profile auto-update up -d
```

Zmienne (opcjonalnie w `.env`):

```env
WATCHTOWER_POLL_INTERVAL=86400
```

Domyślnie: sprawdzanie co **24 godziny**. Tylko kontenery z etykietą `com.centurylinklabs.watchtower.enable=true` (NetDash ma ją w compose).

### Ręczne jednorazowe odświeżenie (bez czekania)

```bash
docker run --rm \
  -v /var/run/docker.sock:/var/run/docker.sock \
  containrrr/watchtower:1.7.1 \
  --run-once --cleanup netdash
```

### Wyłączenie auto-aktualizacji

```bash
docker compose stop netdash-watchtower
docker compose rm -f netdash-watchtower
```

---

## Aktualizacja ręczna (bez Watchtower)

```bash
cd /share/Container/netdash
docker compose pull
docker compose up -d
```

Dane w `./data` (SQLite, ikony) pozostają.

---

## Portal — Sprawdź aktualizacje

W **Ustawienia → O projekcie**:

- **Sprawdź aktualizacje** — porównuje wersję z GitHub Releases (`/releases/latest`)
- Link **Changelog** — strona release na GitHub
- Status: „Masz najnowszą wersję” lub „Dostępna vX.Y.Z”

Nie pobiera ani nie restartuje kontenera — tylko informuje. Do faktycznej aktualizacji użyj Watchtower lub `docker compose pull`.

---

## Opcja zaawansowana: „Aktualizuj teraz” z portalu

**Ryzyko:** montowanie `/var/run/docker.sock` daje kontenerowi NetDash pełną kontrolę nad Dockerem na hoście.

Włączenie tylko jeśli akceptujesz to ryzyko:

1. W `docker-compose.yml` odkomentuj:

   ```yaml
   volumes:
     - ./data:/app/data
     - /var/run/docker.sock:/var/run/docker.sock
   ```

2. W `.env`:

   ```env
   NETDASH_UPDATE_APPLY_ENABLED=true
   ```

3. `docker compose up -d`

W portalu pojawi się **Aktualizuj teraz** (gdy dostępna nowsza wersja) — pobiera obraz z GHCR i restartuje kontener `netdash`.

---

## GitHub Actions i GHCR

Przy każdym tagu `v*` (np. `v1.3.72`) workflow `.github/workflows/docker-publish.yml`:

- buduje obraz Docker,
- publikuje `ghcr.io/lobrzut/netdash:latest` oraz `ghcr.io/lobrzut/netdash:1.3.72`.

Pierwszy raz obraz musi powstać z release na GitHub — dopiero wtedy `docker compose pull` na QNAP ma skąd pobrać.

---

## Ograniczenia

| Temat | Opis |
|-------|------|
| **Brak git na QNAP** | Używaj obrazu GHCR, nie `git pull` |
| **Host network na QNAP** | Skan LAN może wymagać `NETDASH_SCAN_CIDR` |
| **GHCR prywatny** | Domyślnie pakiet publiczny; przy prywatnym — `docker login ghcr.io` na NAS |
| **Watchtower** | Restartuje kontener bez pytania — włącz świadomie |
| **docker.sock** | Pełne uprawnienia do hosta — unikaj jeśli nie musisz |
| **Watchdog** | `deploy/netdash-watchdog.sh` restartuje przy awarii health — to nie aktualizacja wersji |

---

## Powiązane pliki

- [`docker-compose.yml`](../docker-compose.yml) — NetDash + Watchtower (profil)
- [`dockge/compose.yaml`](../dockge/compose.yaml) — ten sam stack dla Dockge
- [`DEPLOYMENT.md`](../DEPLOYMENT.md) — ogólny przewodnik wdrożenia
- [`deploy/netdash-watchdog.sh`](../deploy/netdash-watchdog.sh) — odzyskiwanie po awarii (nie update)
