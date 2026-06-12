# NetDash na QNAP — 5 minut, bez git

Obraz: `ghcr.io/lobrzut/netdash:latest` — pobierany z GitHub Container Registry. **Nie klonujesz repozytorium na NAS.**

Portal po starcie: `http://<IP-QNAP>:18787` (np. `http://192.168.1.150:18787` na QNAP)

> **Port 8787 = Readarr** — na wielu NAS (w tym QNAP) Readarr już zajmuje **8787**. NetDash od v1.3.73 domyślnie używa **18787** (`NETDASH_PORT`). **Nie ustawiaj `NETDASH_PORT=8787` na QNAP z Readarr.** Upgrade ze starego portu: zmień zakładkę na `:18787` i zrestartuj kontener.

---

## Szybka ścieżka (Container Station)

### Krok 1 — folder na NAS

W **File Station** lub przez SSH:

```bash
mkdir -p /share/Container/netdash/data
```

### Krok 2 — utwórz aplikację z compose

1. Otwórz **Container Station**
2. **Create** → **Create Application**
3. Wybierz **Import** → **Import from URL** (lub wklej plik compose)
4. Wklej URL compose:

   ```
   https://raw.githubusercontent.com/lobrzut/netdash/main/deploy/qnap/docker-compose.yml
   ```

   *(Ten sam URL jest w pliku [`compose.url`](compose.url).)*

5. Nazwa aplikacji: np. `netdash`
6. **Create**

**Opis ekranu:** po imporcie zobaczysz jeden serwis `netdash` z obrazem `ghcr.io/lobrzut/netdash:latest`, trybem sieci **host** i wolumenem `/share/Container/netdash/data`.

### Krok 3 — zmienne środowiskowe

W edycji aplikacji → **Environment** (lub w YAML przed utworzeniem) ustaw:

| Zmienna | Wartość |
|---------|---------|
| `NETDASH_SECRET_KEY` | losowy ciąg ≥32 znaków |
| `NETDASH_DEFAULT_ADMIN_PASSWORD` | `changeme` (domyślnie — **zmień po pierwszym logowaniu**) |
| `NETDASH_DEFAULT_ADMIN_USER` | `admin` (domyślnie) |
| `NETDASH_SCAN_CIDR` | `192.168.1.0/24` (opcjonalnie, gdy skan LAN nie działa) |

> **Nie dodawaj** `NETDASH_PORT=8787` w Container Station — port **18787** jest już w compose (≥ v1.3.76). Jeśli masz starą zmienną `NETDASH_PORT=8787`, **usuń ją** przed startem.

Wygeneruj klucz na PC:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

**Opis ekranu:** `NETDASH_SECRET_KEY` musi być losowy (≥32 znaki). Hasło domyślne `changeme` — **obowiązkowo zmień** w Ustawienia → Hasło po pierwszym logowaniu.

### Krok 4 — start

1. **Start** / **Deploy**
2. Poczekaj na pobranie obrazu z GHCR (pierwszy raz ~1–2 min)
3. Otwórz w przeglądarce: `http://<IP-QNAP>:18787`
4. Zaloguj się (`admin` / `changeme`) → **Ustawienia** → **Hasło** → ustaw własne hasło

### Krok 5 — skan sieci LAN (jeśli nie działa)

Na QNAP `network_mode: host` czasem nie skanuje całej sieci. Dodaj zmienną:

```
NETDASH_SCAN_CIDR=192.168.1.0/24
```

(dostosuj do swojej podsieci)

**Opis ekranu:** po dodaniu CIDR zrestartuj aplikację w Container Station — przycisk **Scan network** w portalu powinien znaleźć urządzenia w LAN.

---

## Jeden plik z auto-update (zalecane)

NetDash + Watchtower w **jednym** compose — jeden import w Container Station, bez profili i bez drugiego pliku.

1. **Create** → **Create Application** → **Import from URL**
2. Wklej:

   ```
   https://raw.githubusercontent.com/lobrzut/netdash/main/deploy/qnap/docker-compose.full.yml
   ```

3. Ustaw zmienne środowiskowe (patrz Krok 3 powyżej) → **Create** → **Start**

**Opis ekranu:** zobaczysz dwa serwisy — `netdash` (portal na porcie **18787**) i `netdash-watchtower` (aktualizacja co 24 h). To normalne.

Opcjonalna zmienna: `WATCHTOWER_POLL_INTERVAL=86400` (sekundy, domyślnie 24 h).

---

## Auto-aktualizacja (inne metody)

Watchtower co 24 h sprawdza nowy obraz i restartuje NetDash.

### Metoda A — SSH (profil)

```bash
cd /share/Container/netdash
# skopiuj compose z GitHub jeśli zarządzasz plikiem lokalnie
docker compose --profile auto-update up -d
```

### Metoda B — drugi plik compose (bez profilu)

Import dodatkowo:

```
https://raw.githubusercontent.com/lobrzut/netdash/main/deploy/qnap/docker-compose.autoupdate.yml
```

Lub w SSH:

```bash
docker compose -f docker-compose.yml -f docker-compose.autoupdate.yml up -d
```

**Opis ekranu:** pojawi się drugi kontener `netdash-watchtower` — to normalne. Aktualizuje tylko kontenery z etykietą watchtower (NetDash ma ją domyślnie).

Opcjonalna zmienna: `WATCHTOWER_POLL_INTERVAL=86400` (sekundy, domyślnie 24 h).

---

## Ręczna aktualizacja

W Container Station: **Stop** → **Pull** (lub w SSH):

```bash
docker compose pull && docker compose up -d
```

Dane w `/share/Container/netdash/data` zostają (SQLite, ikony).

---

## Alternatywa — pliki lokalne zamiast URL

Na PC pobierz:

- [`docker-compose.yml`](docker-compose.yml)
- utwórz `.env` z [`../docker-simple/.env.example`](../docker-simple/.env.example)

Skopiuj do `/share/Container/netdash/` przez File Station, potem **Import** → wskaż lokalny `docker-compose.yml`.

---

## Rozwiązywanie problemów (QNAP / Container Station)

### Crash loop: `Errno 98` / „Address already in use” na porcie 8787

**Przyczyna:** NetDash próbuje nasłuchiwać na **8787** zamiast **18787**. Najczęstsze źródła:

1. **Stary obraz GHCR** (sprzed v1.3.73) — domyślny port w kodzie to wtedy 8787.
2. **`NETDASH_PORT=8787` w Container Station** — stara zmienna środowiskowa nadpisuje compose (`${NETDASH_PORT:-18787}` w compose sprzed v1.3.76).
3. **Stary compose URL** — import sprzed zmiany portu; compose ≥ v1.3.76 ma port **18787** na stałe.
4. **Zombie kontener** — druga instancja NetDash lub duplikat aplikacji CS.

Port **8787** jest zajęty przez **Readarr** na wielu QNAP — kontener pada i CS go restartuje w kółko.

**Naprawa w Container Station (bez SSH):**

1. **Applications** → zatrzymaj aplikację `netdash`.
2. **Delete Application** → zaznacz **Remove containers** (usuwa stary kontener ze starym env).
3. **Create** → **Create Application** → **Import from URL** — wklej **świeży** compose:
   ```
   https://raw.githubusercontent.com/lobrzut/netdash/main/deploy/qnap/docker-compose.full.yml
   ```
4. **Environment** — ustaw tylko:
   | Zmienna | Wartość |
   |---------|---------|
   | `NETDASH_SECRET_KEY` | *(twój losowy klucz ≥32 znaków)* |
   | `NETDASH_DEFAULT_ADMIN_PASSWORD` | `changeme` |
   | `NETDASH_DEFAULT_ADMIN_USER` | `admin` |
   | `NETDASH_SCAN_CIDR` | `192.168.1.0/24` *(opcjonalnie)* |
   **Nie dodawaj** `NETDASH_PORT` — compose ustawia **18787**. **Usuń** `NETDASH_PORT=8787` jeśli widzisz w starym szablonie.
5. **Create** → **Start** — poczekaj na pobranie obrazu (`Pull`).
6. Otwórz: `http://192.168.1.150:18787` (nie `:8787`).
7. W logach kontenera powinno być: `Uvicorn running on http://0.0.0.0:18787`.

**Jeśli masz już działającą aplikację (bez pełnego reinstall):**

1. **Applications** — zostaw **jedną** aplikację `netdash`; usuń duplikaty.
2. Edytuj aplikację → **Environment** → **usuń** wiersz `NETDASH_PORT=8787` (lub całą zmienną `NETDASH_PORT`).
3. **Re-create** / **Update** compose z URL powyżej (CS powinien przeładować YAML).
4. **Stop** → **Pull** (`ghcr.io/lobrzut/netdash:latest`, obraz ≥ v1.3.76) → **Start**.
5. Sprawdź: `http://192.168.1.150:18787/api/health` → `{"ok":true,"version":"1.3.76",...}`.

Jeśli nadal błąd — przez SSH na QNAP:

```bash
# kto trzyma port (Readarr vs stary NetDash)
ss -tlnp | grep -E '8787|18787'
docker ps -a --filter name=netdash
docker rm -f netdash   # tylko gdy CS nie usuwa
```

### Duplikat aplikacji w Container Station

Import compose **dwa razy** tworzy dwie aplikacje z tym samym `container_name: netdash` — druga instancja nie wstanie lub będzie walczyć o port.

- Zostaw **jedną** aplikację.
- **Delete Application** przy duplikacie (opcjonalnie: zaznacz „Remove containers”).
- Ponowny import: jeden URL compose, nazwa `netdash`.

### Wciąż nasłuchuje na 8787 (po naprawie env)

| Sprawdź | Oczekiwane |
|---------|------------|
| Obraz | `ghcr.io/lobrzut/netdash:latest` po **Pull** (≥ v1.3.76) |
| Compose URL | `docker-compose.full.yml` z GitHub **main** (port `"18787"` na stałe) |
| CS Environment | **brak** `NETDASH_PORT=8787`; nie dodawaj `NETDASH_PORT` wcale |
| Log kontenera | `Uvicorn running on http://0.0.0.0:18787` |
| URL w przeglądarce | `http://<IP-QNAP>:18787` |

Jeśli log nadal pokazuje `:8787` — usuń aplikację CS i zaimportuj compose od nowa (patrz sekcja crash loop powyżej).

### Jedna instancja — podsumowanie

| Element | Ile |
|---------|-----|
| Aplikacja CS `netdash` | **1** |
| Kontener `netdash` | **1** |
| Port hosta | **18787** (nie 8787 przy Readarr) |
| Watchtower | 0 lub 1 (`netdash-watchtower`) |

---

## Więcej szczegółów

- Pełny przewodnik (Watchtower, docker.sock, GitHub Actions): [`docs/QNAP.md`](../../docs/QNAP.md)
- Docker na zwykłym Linuxie: [`../docker-simple/`](../docker-simple/)
