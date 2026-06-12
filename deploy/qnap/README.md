# NetDash na QNAP — 5 minut, bez git

Obraz: `ghcr.io/lobrzut/netdash:latest` — pobierany z GitHub Container Registry. **Nie klonujesz repozytorium na NAS.**

Portal po starcie: `http://<IP-QNAP>:18787` (np. `http://192.168.1.150:18787` na QNAP)

> **Port 8787 = Readarr** — na wielu NAS (w tym QNAP) Readarr już zajmuje **8787**. NetDash od v1.3.77 używa **`NETDASH_LISTEN_PORT=18787`**; stary `NETDASH_PORT=8787` z CS jest ignorowany. **Nie dodawaj `NETDASH_PORT` w Container Station.**

> **QNAP musi używać bridge do skanu LAN (od v1.3.90)** — `network_mode: host` na QNAP **nie skanuje** urządzeń w Twojej sieci domowej. Domyślny `docker-compose.full.yml` ma `ports: 18787:18787` + **`NETDASH_SCAN_CIDR`** (np. `192.168.1.0/24`). Bez CIDR skan nie ma sensu.

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

**Opis ekranu:** po imporcie zobaczysz jeden serwis `netdash` z obrazem `ghcr.io/lobrzut/netdash:1.3.90`, mapowaniem portu **18787:18787** (bridge) i wolumenem `/share/Container/netdash/data`.

### Krok 3 — zmienne środowiskowe (minimalne)

Od **v1.3.80** compose ma **twarde domyślne** (`admin` / `changeme`) — Container Station **nie musi** mieć żadnych zmiennych, żeby zalogować się po pierwszym deployu.

| Zmienna | Wymagana? | Wartość |
|---------|-----------|---------|
| *(brak)* | nie | pierwszy start: login `admin` / `changeme` (tworzone automatycznie) |
| `NETDASH_SECRET_KEY` | opcjonalna | losowy ≥32 znaki; jeśli brak — entrypoint zapisze klucz w `/app/data/.secret` |
| `NETDASH_SCAN_CIDR` | **w compose od v1.3.81** | `192.168.1.0/24` (dostosuj do swojej podsieci) |
| `NETDASH_SYNC_ADMIN_PASSWORD` | w compose: `false` | restart **nie** nadpisuje hasła z SQLite; odzysk: `NETDASH_RESET_ADMIN_PASSWORD` |

> Compose na GitHub **main**: obraz **`ghcr.io/lobrzut/netdash:1.3.90`** w **docker-compose.full.yml** — **NIE `:latest`** (QNAP CS cache'uje stary obraz → crash 8787). Po imporcie: **Pull** `1.3.90` przed Start; w logach musi być `LISTEN_PORT=18787` i `NetDash entrypoint v1.3.90`. Compose jest już w trybie **bridge** (port `18787:18787`).

Opcjonalnie wygeneruj `NETDASH_SECRET_KEY` na PC:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

**Opis ekranu:** pierwszy start tworzy **`admin` / `changeme`**. Compose ma `NETDASH_SYNC_ADMIN_PASSWORD=false` — po zmianie hasła w Ustawienia → Hasło restart **nie** przywraca `changeme`.

### Krok 4 — start

1. **Start** / **Deploy**
2. Poczekaj na pobranie obrazu z GHCR (pierwszy raz ~1–2 min)
3. Otwórz w przeglądarce: `http://<IP-QNAP>:18787`
4. Zaloguj się (`admin` / `changeme`) → **Ustawienia** → **Hasło** → ustaw własne hasło

### Krok 5 — skan sieci LAN

Od **v1.3.81** compose ma już `NETDASH_SCAN_CIDR=192.168.1.0/24`. Jeśli Twoja sieć to np. `192.168.0.0/24`, zmień wartość w **Environment** Container Station.

**Gdzie jest przycisk skanu w portalu?**

1. Zaloguj się do `http://<IP-QNAP>:18787`
2. Kliknij zakładkę **Serwisy** (nie **Pulpit** — przycisk skanu jest ukryty na pulpicie)
3. W prawym górnym rogu: **Skanuj sieć** → modal z CIDR → **Rozpocznij skan**

Dodatkowo: **Ustawienia** → **Skanowanie** (domyślne CIDR, pełny skan) oraz **Zasilanie** → **Skan ARP** (MAC urządzeń).

---

## Skan sieci — nie działa / nie widać przycisku

### Nie widzę przycisku „Skanuj sieć”

| Przyczyna | Rozwiązanie |
|-----------|-------------|
| Jesteś na zakładce **Pulpit** | Przełącz na **Serwisy** — przycisk jest tylko tam |
| Nie jesteś zalogowany | Zaloguj się (`admin` / `changeme` na v1.3.81+) |

Skan **nie wymaga** dodatkowych uprawnień — wystarczy konto użytkownika.

### Skan się uruchamia, ale nie znajduje urządzeń

**Przyczyna:** Na QNAP `network_mode: host` często **nie daje** kontenerowi pełnego dostępu do LAN. Kontener widzi sieć Docker (`172.17.x.x`) zamiast Twojej sieci (`192.168.1.x`) i skanuje złą podsieć. **Od v1.3.90 domyślny compose używa bridge** — jeśli masz stary deploy z `host`, zaimportuj compose od nowa.

**Rozwiązanie 1 — CIDR (wymagane w bridge, od v1.3.81 w compose):**

```
NETDASH_SCAN_CIDR=192.168.1.0/24
```

(dostosuj do swojej podsieci — sprawdź IP QNAP w Panelu QTS)

W portalu: **Ustawienia** → **Skanowanie** → **Domyślne sieci (CIDR)** — to samo, ale zapisane w bazie.

**Rozwiązanie 2 — uprawnienia ping/ARP:**

Compose QNAP ma `cap_add: NET_RAW` (wymagane do ping i skanu ARP). Po imporcie compose sprawdź w logach kontenera, czy ping działa:

```bash
docker exec netdash ping -c 1 192.168.1.1
```

**Rozwiązanie 3 — tryb bridge (DOMYŚLNY od v1.3.90):**

Domyślny compose full już ma bridge. Alternatywny plik (bez Watchtower):

```
https://raw.githubusercontent.com/lobrzut/netdash/main/deploy/qnap/docker-compose.bridge.yml
```

1. **Container Station** → usuń starą aplikację `netdash` (dane w `/share/Container/netdash/data` zostają)
2. **Create Application** → Import from URL → wklej URL **docker-compose.full.yml** (zalecane) lub bridge powyżej
3. Sprawdź `NETDASH_SCAN_CIDR=192.168.1.0/24` (dostosuj do swojej sieci)
4. **Start** → portal: `http://<IP-QNAP>:18787` → **Ustawienia** → **Skanowanie** → **Test skanu sieci**
5. W logach kontenera szukaj: `POST /api/network/scan-test` i `POST /api/scan`

- Mapowanie portu `18787:18787` (zamiast `network_mode: host`)
- **`NETDASH_SCAN_CIDR` jest obowiązkowy** — bez niego skan nie ma sensu

**Weryfikacja po naprawie:**

1. `http://<IP-QNAP>:18787/api/health` → `"version":"1.3.90"`
2. Zaloguj → F5 — **bez** ponownego logowania (sesja cookie)
3. **Ustawienia** → **Skanowanie** → **Test skanu sieci** → `Gotowy do skanu: Tak`
4. **Serwisy** → **Skanuj sieć** → w logach: `POST /api/scan body=...`
5. Po skanie pojawią się karty urządzeń / serwisów

**Baner ostrzeżenia:** Na zakładce Serwisy, gdy kontener jest w sieci Docker bez CIDR, NetDash pokazuje żółty komunikat z instrukcją — ustaw CIDR i zrestartuj.

### Skan wywalił cały QNAP (v1.3.94+)

Starsze wersje mogły zawiesić cały NAS przy skanie `/24` (254 hosty × dziesiątki portów × wysoka równoległość TCP, szczególnie gdy ping ICMP jest zablokowany).

**Od v1.3.94+** safe mode i limity zasobów są domyślne **w całym projekcie NetDash** (każdy deploy, nie tylko QNAP): `NETDASH_SCAN_SAFE_MODE=true`, limit RAM **512 MB**. Na słabym sprzęcie użyj węższego CIDR (`/28`).

### Limit RAM (512 MB) w compose

Compose QNAP używa standardowego [Compose Specification](https://docs.docker.com/compose/compose-file/) — **bez** klucza `version` i **bez** legacy `mem_limit`:

```yaml
deploy:
  resources:
    limits:
      memory: 512M
```

**Docker Compose v2** (`docker compose`, bez myślnika) stosuje `deploy.resources.limits` na pojedynczym hoście — **bez trybu Swarm**. **Container Station 3.x** (QTS 5.1+) opiera się na Compose v2 i powinien zastosować ten limit przy imporcie YAML z GitHub.

**Stary Container Station (< 3.0) lub brak limitu po imporcie:** ustaw ręcznie w UI:

1. **Container Station** → aplikacja `netdash` → edycja kontenera `netdash`
2. Zakładka **Resource** (Zasoby)
3. **Memory limit** → **512 MB** → zapisz i zrestartuj kontener

Opcjonalny limit CPU: ta sama zakładka **Resource** → **CPU limit** (compose QNAP nie ustawia twardego limitu CPU).

| Parametr (safe mode) | Wartość |
|----------------------|---------|
| Równoległość | 8 połączeń |
| Porty (szybki skan) | 9 web + 2 host (zamiast ~50) |
| Max hostów | 64 |
| Timeout skanu | 300 s |
| Pełny skan | wyłączony |

**Odzyskiwanie po crashu:** wyłącz zasilanie QNAP na 30 s → włącz → Container Station → upewnij się, że NetDash ma obraz **1.3.97+** → Pull → Restart → skanuj tylko z **Serwisy** (nie Pulpit).

---

## Jeden plik z auto-update (zalecane)

NetDash + Watchtower w **jednym** compose — jeden import w Container Station, bez profili i bez drugiego pliku.

1. **Create** → **Create Application** → **Import from URL**
2. Wklej:

   ```
   https://raw.githubusercontent.com/lobrzut/netdash/main/deploy/qnap/docker-compose.full.yml
   ```

3. Ustaw zmienne środowiskowe (patrz Krok 3 powyżej) → **Create** → **Start**

**Opis ekranu:** zobaczysz **dwa** serwisy — `netdash` (portal na porcie **18787**) i `netdash-watchtower` (aktualizacja co 24 h). Oba muszą być **Running**.

**Ważne (od v1.3.82):** obraz NetDash w tym pliku to **`ghcr.io/lobrzut/netdash:latest`**. Watchtower **nie** aktualizuje kontenerów z przypiętym tagiem semver (np. `1.3.79`). Przypięcie digest (`@sha256:…`) zwiększa bezpieczeństwo, ale wyłącza auto-update.

Interwał sprawdzania: **86400 s** (24 h) — ustawione w compose (QNAP CS ignoruje `${VAR:-default}`).

### Auto-update nie działa — checklist

| Sprawdź | Oczekiwane |
|---------|------------|
| Liczba kontenerów | **2**: `netdash` + `netdash-watchtower` (oba Running) |
| Obraz NetDash | `ghcr.io/lobrzut/netdash:latest` (nie `1.3.x`) |
| Etykieta | `com.centurylinklabs.watchtower.enable=true` na netdash |
| Logi Watchtower | Container Station → `netdash-watchtower` → **Logs** — szukaj `Updated` / błędów pull |
| Portal „Masz najnowszą wersję” | To porównanie z GitHub API — **nie** oznacza, że Watchtower zadziałał. Wersja w stopce = faktyczny obraz kontenera. |

**Naprawa po starym deployu (np. v1.3.79 z przypiętym tagiem):**

1. Ponowny **Import from URL** compose full (lub edycja aplikacji: obraz → `:latest`).
2. **Recreate** / **Restart** obu kontenerów.
3. W logach `netdash-watchtower` potwierdź start i kolejny cykl (lub jednorazowo przez SSH — patrz `docs/QNAP.md`).

Przycisk **„Aktualizuj teraz”** w portalu na QNAP zwykle **nie** działa (brak `docker.sock` w kontenerze NetDash) — użyj Watchtower lub **Pull** w Container Station.

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

**Diagnoza w 5 sekund:** otwórz logi kontenera. **Brak** linii `NetDash entrypoint` i `LISTEN_PORT=18787` = **stary obraz GHCR** (sprzed v1.3.84, hardcoded 8787). Compose z `:latest` na QNAP często nie pobiera nowego warstwa — używaj przypiętego **`1.3.87`**.

**Przyczyna:** NetDash próbuje nasłuchiwać na **8787** zamiast **18787**. Najczęstsze źródła:

1. **Stary obraz w cache CS** — `:latest` wskazuje na warstwę sprzed entrypoint (brak `LISTEN_PORT=18787` w logu).
2. **Watchtower / reimport** odtworzył kontener ze starym obrazem.
3. **Dwa kontenery netdash** — duplikat aplikacji CS lub zombie.
4. **`NETDASH_PORT=8787` w CS** — stara zmienna w szablonie (v1.3.84+ ją ignoruje, ale stary obraz nie).

Port **8787** = **Readarr** na wielu QNAP → crash loop.

#### Pilna checklista (Container Station, bez SSH)

1. **SSH lub Terminal CS** (opcjonalnie): `docker ps -a | grep netdash` — musi być **JEDEN** kontener `netdash`. Jeśli dwa → usuń duplikat aplikacji CS.
2. **Applications** → **Stop** → **Delete Application** → zaznacz **Remove containers** (pełne usunięcie starego obrazu/env).
3. **Create Application** → **Import from URL**:
   ```
   https://raw.githubusercontent.com/lobrzut/netdash/main/deploy/qnap/docker-compose.full.yml
   ```
   Compose ma obraz **`ghcr.io/lobrzut/netdash:1.3.90`** (nie `:latest`).
4. **Environment** — nic nie dodawaj poza ewentualną zmianą `NETDASH_SCAN_CIDR`. **Nie dodawaj** `NETDASH_PORT`.
5. **Przed Start:** **Images** → **Pull** → `ghcr.io/lobrzut/netdash:1.3.90` (ręczny pull wymuszony).
6. **Start** → otwórz logi kontenera. **Pierwsze linie MUSZĄ zawierać:**
   - `NetDash entrypoint`
   - `LISTEN_PORT=18787 (8787 blocked)`
   - `Uvicorn running on http://0.0.0.0:18787`
7. Portal: `http://<IP-QNAP>:18787` (nie `:8787`).
8. Health: `http://<IP-QNAP>:18787/api/health` → `"version":"1.3.90"`.

**Jeśli log nadal pokazuje 8787 lub brak entrypoint** — powtórz kroki 1–6; CS trzyma cache obrazu mimo reimportu.

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
| Obraz | `ghcr.io/lobrzut/netdash:1.3.90` po **ręcznym Pull** |
| Compose URL | `docker-compose.full.yml` z GitHub **main** (pin `1.3.90`, bridge, nie `:latest`) |
| CS Environment | tylko SECRET_KEY / hasło; **brak** `NETDASH_PORT` |
| Log kontenera (pierwsze linie) | `NetDash entrypoint` + `LISTEN_PORT=18787` + `Uvicorn ... :18787` |
| URL w przeglądarce | `http://<IP-QNAP>:18787` |

Jeśli log nadal pokazuje `:8787` — usuń aplikację CS i zaimportuj compose od nowa (patrz sekcja crash loop powyżej).

### Jedna instancja — podsumowanie

| Element | Ile |
|---------|-----|
| Aplikacja CS `netdash` | **1** |
| Kontener `netdash` | **1** |
| Port hosta | **18787** (nie 8787 przy Readarr) |
| Watchtower | 0 lub 1 (`netdash-watchtower`) |

### Nie mogę się zalogować (`admin` / `changeme` nie działa)

Portal działa (`http://<IP-QNAP>:18787`), ale formularz logowania odrzuca hasło.

**Od v1.3.87 (zalecane):** compose ma `admin` / `changeme`, `NETDASH_SYNC_ADMIN_PASSWORD=false` i obraz `:latest`. Pierwszy start tworzy admina; kolejne restarty **nie** nadpisują hasła. Odzysk hasła: odkomentuj `NETDASH_RESET_ADMIN_PASSWORD` w compose.

**Stary deploy z `sync=true`:** jeśli restart przywraca `changeme`, zmień na `NETDASH_SYNC_ADMIN_PASSWORD=false` i zrestartuj (lub użyj `NETDASH_RESET_ADMIN_PASSWORD`).

**Co sprawdzić:**

| Element | Oczekiwane |
|---------|------------|
| Obraz | `ghcr.io/lobrzut/netdash:latest` (Pull w CS) |
| Health | `http://<IP>:18787/api/health` → `"admin_ready": true` |
| Login | `admin` / `changeme` (wielkość liter w loginie bez znaczenia) |

W logu kontenera po starcie (v1.3.80+): `Admin bootstrap: ... admin_ready=True`.

**Starsze wersje (< 1.3.80):** sync wymagał obecności env w kontenerze — patrz opcje poniżej.

**Opcja A — świeży start (bez SSH, File Station)** — tracisz ustawienia i listę usług w portalu:

1. **Container Station** → aplikacja `netdash` → **Stop**
2. **File Station** → folder **`Container`** → **`netdash`** → **`data`**
3. Usuń pliki:
   - `netdash.db`
   - `netdash.db-wal` i `netdash.db-shm` (jeśli są)
4. **Start** aplikacji w Container Station
5. Zaloguj się: **`admin`** / **`changeme`** → od razu **Ustawienia** → **Hasło**

**Opcja B — reset hasła bez kasowania danych (v1.3.78+, bez SSH):**

1. **Container Station** → edycja aplikacji `netdash` → **Environment**
2. Dodaj zmienną: `NETDASH_RESET_ADMIN_PASSWORD` = `changeme` (lub inne tymczasowe hasło)
3. **Restart** kontenera
4. Zaloguj się nowym hasłem
5. **Usuń** `NETDASH_RESET_ADMIN_PASSWORD` z Environment i zrestartuj ponownie
6. **Ustawienia** → **Hasło** → własne hasło

> Na obrazie **< 1.3.79** zaktualizuj do **1.3.79** (Pull / import compose) — sync hasła rozwiązuje problem bez kasowania bazy.

**Opcja C — reset skryptem (wymaga SSH lub terminala na NAS):**

```bash
# w kontenerze (zachowuje usługi i ustawienia)
docker exec netdash python /app/scripts/reset-admin-password.py --password changeme
docker restart netdash
```

Lub na hoście z dostępem do pliku bazy:

```bash
python scripts/reset-admin-password.py --db /share/Container/netdash/data/netdash.db --password changeme
```

**Nie pomaga zmiana `NETDASH_SECRET_KEY`** — dotyczy tokenów JWT po zalogowaniu, nie hasła w bazie. Po resecie wyczyść ciasteczka przeglądarki dla tego hosta, jeśli nadal widzisz dziwne błędy sesji.

### Ekran „Ładowanie sesji…” nie znika (wisi w nieskończoność)

**Przyczyna (v1.3.89):** `GET /api/auth/me` bez timeoutu — gdy brak cookie lub sieć wolna, fetch wisi, a ekran boot nigdy nie przechodzi do logowania.

**Naprawa od v1.3.90:** timeout 5 s → automatycznie ekran logowania; logi w konsoli przeglądarki (`[NetDash]`) i w kontenerze (`GET /api/auth/me: brak cookie sesji`).

**Obejście przed upgrade:** wyczyść ciasteczka dla `http://<IP-QNAP>:18787` (DevTools → Application → Cookies) i twarde odświeżenie **Ctrl+F5** (Safari: Cmd+Shift+R).

### Po odświeżeniu strony (F5) trzeba logować się od nowa

**Naprawa od v1.3.90:**

- Przy starcie strony: **„Ładowanie sesji…”** → `GET /api/auth/me` z cookie (bez starego tokena z localStorage).
- Przy logowaniu w logach kontenera: `Session cookie set for user admin`.
- `NETDASH_SYNC_ADMIN_PASSWORD=false` w compose — restart **nie** resetuje hasła do `changeme`.

**Starsze przyczyny (v1.3.80 i wcześniej):** nowy `NETDASH_SECRET_KEY` przy restarcie bez wolumenu `.secret` → nieważny JWT.

**Kroki dla użytkownika:**

1. **Pull** obrazu `ghcr.io/lobrzut/netdash:1.3.90` (lub ponowny import compose full).
2. Sprawdź wolumen: `/share/Container/netdash/data:/app/data`.
3. Po starcie w logach: `loaded NETDASH_SECRET_KEY from /app/data/.secret`.
4. Health: `http://<IP-QNAP>:18787/api/health` → `"version":"1.3.90"`, `"secret_key_stable": true`.
5. Zaloguj się raz → F5 — bez ponownego logowania.
6. W logach po logowaniu: `Session cookie set for user ...`.

**Jeśli `secret_key_stable` jest `false`:**

| Przyczyna | Rozwiązanie |
|-----------|-------------|
| Brak wolumenu `/app/data` | Dodaj mount w compose: `/share/Container/netdash/data:/app/data` |
| Folder `data` tylko do odczytu | W File Station nadaj uprawnienia zapisu dla użytkownika Dockera |
| Pierwszy start po upgrade | Zrestartuj kontener — plik `.secret` zostanie utworzony; potem `secret_key_stable: true` |
| Różne adresy URL (IP vs nazwa hosta) | Używaj **jednego** adresu (np. zawsze `http://192.168.1.150:18787`) — localStorage i cookie są per-origin |

**Nie ustawiaj** losowego `NETDASH_SECRET_KEY` w CS przy każdym deployu — entrypoint i tak preferuje plik `.secret` na wolumenie.

---

## Więcej szczegółów

- Pełny przewodnik (Watchtower, docker.sock, GitHub Actions): [`docs/QNAP.md`](../../docs/QNAP.md)
- Docker na zwykłym Linuxie: [`../docker-simple/`](../docker-simple/)
