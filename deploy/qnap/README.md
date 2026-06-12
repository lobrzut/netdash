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
| `NETDASH_PORT` | `18787` (domyślnie — **nie** 8787 jeśli masz Readarr) |
| `NETDASH_SCAN_CIDR` | `192.168.1.0/24` (opcjonalnie, gdy skan LAN nie działa) |
| `NETDASH_PORT` | `18787` (domyślnie; unika Readarr **8787**) |

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

**Przyczyna:** port **8787** jest zajęty (często **Readarr** na tym samym QNAP). Stary compose lub ręczny import mógł uruchomić NetDash na 8787 — kontener startuje, pada, Container Station go restartuje w kółko.

**Naprawa (kolejność):**

1. **Container Station** → **Applications** — zostaw **jedną** aplikację `netdash`. Usuń duplikaty (np. `netdash-1`, drugi import tego samego compose).
2. **Containers** — zatrzymaj i usuń **wszystkie** kontenery o nazwie `netdash` (zostaw Readarr w spokoju).
3. Edytuj aplikację → **Environment**:
   - ustaw `NETDASH_PORT=18787` (lub usuń zmienną — domyślnie 18787 w obrazie ≥1.3.73),
   - **usuń** `NETDASH_PORT=8787` jeśli było.
4. **Pull** najnowszy obraz `ghcr.io/lobrzut/netdash:latest` → **Start**.
5. Sprawdź: `http://192.168.1.150:18787/api/health` → `{"ok":true,...}`.

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

### Stary obraz GHCR (wciąż nasłuchuje na 8787)

Compose z `NETDASH_PORT` działa dopiero z obrazem **≥ v1.3.73**. W CS: **Stop** → **Pull** → **Start**. W logach kontenera powinno być `Uvicorn running on http://0.0.0.0:18787`.

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
