# NetDash na QNAP — 5 minut, bez git

Obraz: `ghcr.io/lobrzut/netdash:latest` — pobierany z GitHub Container Registry. **Nie klonujesz repozytorium na NAS.**

Portal po starcie: `http://<IP-QNAP>:8787` (np. `http://192.168.1.201:8787`)

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
| `NETDASH_DEFAULT_ADMIN_PASSWORD` | twoje hasło logowania |
| `NETDASH_DEFAULT_ADMIN_USER` | `admin` (opcjonalnie) |

Wygeneruj klucz na PC:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

**Opis ekranu:** pola `NETDASH_SECRET_KEY` i `NETDASH_DEFAULT_ADMIN_PASSWORD` muszą być wypełnione — bez nich kontener się nie uruchomi poprawnie.

### Krok 4 — start

1. **Start** / **Deploy**
2. Poczekaj na pobranie obrazu z GHCR (pierwszy raz ~1–2 min)
3. Otwórz w przeglądarce: `http://<IP-QNAP>:8787`
4. Zaloguj się → **Ustawienia** → zmień hasło

### Krok 5 — skan sieci LAN (jeśli nie działa)

Na QNAP `network_mode: host` czasem nie skanuje całej sieci. Dodaj zmienną:

```
NETDASH_SCAN_CIDR=192.168.1.0/24
```

(dostosuj do swojej podsieci)

**Opis ekranu:** po dodaniu CIDR zrestartuj aplikację w Container Station — przycisk **Scan network** w portalu powinien znaleźć urządzenia w LAN.

---

## Auto-aktualizacja (opcjonalnie, jeden krok)

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

## Więcej szczegółów

- Pełny przewodnik (Watchtower, docker.sock, GitHub Actions): [`docs/QNAP.md`](../../docs/QNAP.md)
- Docker na zwykłym Linuxie: [`../docker-simple/`](../docker-simple/)
