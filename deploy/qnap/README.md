# NetDash na QNAP — import raz, zero edycji YAML (v1.3.124)

> **Container Station nie pozwala edytować compose po deployu.** Użyj **jednego** URL poniżej — wszystko (discovery, Watchtower, auto-update) jest już w pliku.

## Jednorazowy deploy (3 kroki)

1. **Container Station** → **Create Application** → **Import from URL**
2. Wklej **ten jedyny URL**:

```
https://raw.githubusercontent.com/lobrzut/netdash/main/deploy/qnap/docker-compose.full.yml
```

3. **Create** → **Start** → otwórz `http://<IP-QNAP>:18787` → login **`admin`** / **`changeme`**

**Koniec.** Nie edytuj YAML. Nie rób ręcznego Pull przy aktualizacjach.

### Co jest w środku (bez Twojej konfiguracji)

| Element | Wartość |
|---------|---------|
| Obraz NetDash | `ghcr.io/lobrzut/netdash:latest` |
| Watchtower | co **1 h** (`WATCHTOWER_POLL_INTERVAL=3600`) |
| Discovery | adaptive (ping → ARP → porty), `network_mode: host` |
| Sieć | `NETDASH_SCAN_CIDR=192.168.1.0/24` (zmień w **Ustawienia → Skanowanie**, nie w YAML) |
| Hosty .200/.201 | `NETDASH_ARP_EXTRA_HOSTS` — domyślnie w compose |
| Portal | port **18787**, safe mode, startup defer |
| Kontenery | `netdash` + `netdash-watchtower` (oba **Running**) |

### Po pierwszym logowaniu (w portalu, nie w YAML)

1. **Ustawienia → Hasło** — zmień `changeme`
2. **Ustawienia → Skanowanie** — jeśli Twoja sieć to nie `192.168.1.0/24`, ustaw CIDR tutaj (zapis w SQLite, bez edycji compose)
3. Opcjonalnie: **Container Station → Resource** — RAM **512 MB**, CPU **50%**

### Auto-aktualizacja (Watchtower)

- GitHub Actions publikuje `:latest` + `:1.3.124` przy każdym tagu `v*`
- Watchtower co ~1 h sprawdza nowy digest `:latest` na GHCR i **sam** restartuje NetDash
- Portal pokazuje: *„Aktualizacja automatyczna przez Watchtower (co ~1 h)”* — przycisk „Aktualizuj teraz” nie działa na QNAP (brak docker.sock w kontenerze) i **nie jest potrzebny**
- Samo-aktualizacja z wnętrza kontenera bez docker.sock jest **niemożliwa** — Watchtower **jest** rozwiązaniem

### Gdy coś jest nie tak — tylko reimport od zera

Usuń aplikację w Container Station → **Import from URL** (ten sam link) → Start.  
Dane w `/share/Container/netdash/data` zostają (hasło, serwisy, ustawienia CIDR z portalu).

---

## Szczegóły techniczne

> Poniżej: troubleshooting, bridge mode, agent zdalny, historia wersji.

### Dlaczego `:latest`, a nie `1.3.124`?

Watchtower porównuje **digest tagu z compose**. Przypięty semver `1.3.123` nigdy nie „przeskoczy” na `1.3.124` automatycznie. Tag `:latest` jest nadpisywany przy każdym release — Watchtower widzi nowy obraz i restartuje.

### Checklist: auto-update nie działa

| Sprawdź | Oczekiwane |
|---------|------------|
| Liczba kontenerów | **2**: `netdash` + `netdash-watchtower` (oba Running) |
| Obraz NetDash | `ghcr.io/lobrzut/netdash:latest` (nie `1.3.x`) |
| Etykieta | `com.centurylinklabs.watchtower.enable=true` |
| Logi Watchtower | CS → `netdash-watchtower` → Logs → `Updated` |

### Inne pliki compose (nie dla QNAP one-shot)

| Plik | Kiedy |
|------|-------|
| `docker-compose.full.yml` | **Jedyny do importu na QNAP** |
| `docker-compose.yml` | SSH / ręczny deploy z pin semver |
| `docker-compose.bridge.yml` | Gdy host mode nie skanuje LAN |

---

## Krok 1 — NetDash na QNAP (.150)

1. **Container Station** → **Create Application** → **Import from URL**
2. URL z sekcji powyżej → **Start** → `http://192.168.1.150:18787`
3. Pasek: *„Discovery: ping N → arp +M MAC → … (profil: weak)”*

Domyślny compose: `network_mode: host`, adaptive discovery, `NETDASH_SCAN_CIDR=192.168.1.0/24`, `NETDASH_ARP_EXTRA_HOSTS=192.168.1.200,192.168.1.201`, `cap_add: NET_RAW, NET_ADMIN`.

> **Host mode:** brak `ports:` — portal na `http://<IP-QNAP>:18787` bezpośrednio.

## Opcjonalny agent (inny host)

Tylko gdy discovery ma działać z PC/VM, nie z QNAP:

```bash
curl -fsSL https://raw.githubusercontent.com/lobrzut/netdash/main/deploy/agent/install.sh | NETDASH_PASSWORD=twoje-haslo bash
```

Pełny przewodnik: [`docs/QNAP.md`](../../docs/QNAP.md)

---

## Rozwiązywanie problemów

### Nie widzę „Skanuj sieć”

Przełącz na zakładkę **Serwisy** (nie Pulpit). Zaloguj się jako `admin`.

### Skan nie znajduje urządzeń

Ustaw CIDR w **Ustawienia → Skanowanie** (nie w YAML). Na słabym NAS użyj `/28` zamiast `/24`. Jeśli host mode nie skanuje LAN — reimport z [`docker-compose.bridge.yml`](docker-compose.bridge.yml) (utrata Watchtower w jednym pliku; wtedy agent zdalny).

### Crash loop na porcie 8787

Stary obraz w cache CS. **Delete Application** → reimport URL z góry → Start. W logach musi być `LISTEN_PORT=18787`.

### Nie mogę się zalogować

Health: `/api/health` → `admin_ready: true`. Domyślnie `admin` / `changeme`. Hasło zmieniasz w portalu, nie w YAML.

