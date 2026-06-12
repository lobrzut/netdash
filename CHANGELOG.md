# Changelog

## v1.3.109

- **NUCLEAR — jeden klik „Skanuj sieć”**: `#scan-btn` i `#empty-scan-btn` od razu wołają `oneClickScan()` → `POST /api/scan` (bez modala CIDR i bez confirm). CIDR: Ustawienia → `scan_cidr_default` → `NETDASH_SCAN_CIDR` (`env_scan_cidr`) → `192.168.1.0/24`. Toast „Skan uruchomiony: {cidr}”, pasek postępu natychmiast.
- **Opcje skanu…**: link otwiera zaawansowany modal (CIDR + pełny skan + opcjonalny confirm dla power userów).
- **Logi**: `POST /api/scan/ui-attempt` przy każdej próbie ze UI (`ui-one-click` / `ui-advanced`); usunięty workaround long-press.
- **Obraz**: `ghcr.io/lobrzut/netdash:1.3.109`.

## v1.3.108

- **Fix krytyczny — POST /api/scan po „Kontynuuj skan”**: `closeModal('scan-confirm-modal')` wołał `pendingScanStart(false)` zanim promise się rozwiązał (wyścig z handlerem OK / backdrop). Teraz `resolvePendingScanStart(true)` + `closeModal(..., { scanConfirmOk: true })` — confirm nie jest anulowany przy zamykaniu po akceptacji.
- **Debug**: `console.log('[NetDash] scan: …')` na każdym kroku (klik przycisku, modal CIDR, confirm, POST).
- **Fallback**: przytrzymaj ~0,8 s „Skanuj sieć” na Serwisach — bezpośredni POST z domyślnym CIDR (pomija confirm).
- **UI**: `z-index` na `.modal-content` — klik w przyciski modala nie trafia w backdrop.
- **Obraz**: `ghcr.io/lobrzut/netdash:1.3.108`.

## v1.3.107

- **Fix krytyczny QNAP — zły CIDR 172.x**: modal skanu domyślnie wybierał sieć Docker (172.16–172.31), więc POST `/api/scan` szedł z `172.x.0/24` zamiast `NETDASH_SCAN_CIDR` (192.168.1.0/24) — skan „nic nie znajdował”. UI preferuje teraz `env_scan_cidr`; serwer ignoruje Docker-internal CIDR gdy ustawiony `NETDASH_SCAN_CIDR`.
- **Szybki skan (quick_scan)**: na Docker bridge / `scan_safe_mode` — gateway, ARP, znane hosty z bazy, pierwsze /32 adresy; mniejsze obciążenie NAS.
- **UI skanu**: toast przy starcie i po sukcesie; natychmiastowy polling postępu; wznowienie skanu po F5; anulowanie confirm wraca do modala CIDR.
- **Logi serwera**: `Scan N started/completed`, odrzucenia 409/400, śmierć taska w tle.
- **Obraz**: `ghcr.io/lobrzut/netdash:1.3.107`.

## v1.3.106

- **Fix sesji F5 (QNAP) — root cause**: serwer brał **pierwsze** cookie nawet gdy było nieważne, ignorując poprawny Bearer z `localStorage`; `get_current_user` próbuje teraz Bearer → cookie → legacy, aż znajdzie ważny JWT.
- **Boot**: `restoreSession()` od razu wysyła Bearer z `localStorage` (razem z cookie), nie czyści tokena przy timeout/5xx — tylko przy 401; ponowienie po timeout.
- **Skan — jeden modal naraz**: modal CIDR zamyka się przed potwierdzeniem; anulowanie confirm wraca do wyboru CIDR (koniec „kręcenia” między oknami).
- **Obraz**: `ghcr.io/lobrzut/netdash:1.3.106`.

## v1.3.105

- **Fix krytyczny — modal „Kontynuuj skan”**: kliknięcie potwierdzenia wywoływało `closeModal` przed `pendingScanStart(true)`, więc skan był anulowany i **POST /api/scan nigdy nie szedł** (regresja z v1.3.104 po zamianie `confirm()` na modal).
- **Błędy skanu po polsku**: toast przy wygaśnięciu sesji (401), odrzuceniu przez serwer i utracie połączenia podczas pollingu postępu.
- **Obraz**: `ghcr.io/lobrzut/netdash:1.3.105`.

## v1.3.104

- **Skan sieci — wybór CIDR**: przycisk „Skanuj sieć” otwiera modal z listą wykrytych sieci (`/api/network` → `detected_cidrs`: /24, /28, NETDASH_SCAN_CIDR, ustawienia), podglądem wyboru i opcją „Własny wpis”.
- **Potwierdzenie skanu**: zamiast natywnego `confirm()` — modal w aplikacji z checkboxem „Nie pokazuj ponownie” (`localStorage: netdash_scan_confirm_skip`).
- **Baner trybu bezpiecznego**: przycisk „Ukryj” (`localStorage: netdash_scan_safe_banner_dismiss`) — nie pokazuje się przy każdym wejściu na Serwisy.
- **Ustawienia → Skanowanie**: domyślne CIDR z pól ustawień jest domyślnym wyborem w modalu skanu.
- **Obraz**: `ghcr.io/lobrzut/netdash:1.3.104`.

## v1.3.103

- **Fix krytyczny UI (`scan_safe_mode`)**: Pulpit i Serwisy nie crashują gdy `/api/network` zawiedzie — domyślny profil `scan_safe_mode=true`, bezpieczne wartości sieci; koniec czerwonego banera „Cannot read properties of null”.
- **Fix dialogu „Zaloguj się” (QNAP :5001)**: przeglądarka nie ładuje już faviconów z adresów LAN / login-gated (`<img src>` na karcie serwisu). Niebezpieczne `icon_url` są zastępowane ikoną marki (CDN) lub presetem; health check HTTP pomija serwisy z `has_login` (tylko ping).
- **Compose (QNAP)**: czysty minimalny YAML — bez `version`, `mem_limit`, `deploy.resources` ani `cpus` (żadnych fałszywych ostrzeżeń IDE/Schema Store). Limit RAM 512 MB: komentarz w compose + **Container Station → Resource → Memory limit** (patrz README).
- **README (QNAP)**: sekcja limitu RAM tylko przez UI CS; wyjaśnienie żółtych trójkątów IDE vs QNAP.
- **Obraz**: `ghcr.io/lobrzut/netdash:1.3.103`.

## v1.3.102

- **Compose (QNAP)**: własny schemat IDE `deploy/qnap/qnap-compose.schema.json` (Compose 2.4: `mem_limit` bez ostrzeżeń yaml-language-server). Modeline + `.vscode/settings.json` używają **URL GitHub** (nie `./` ani ścieżki względem repo). `yaml.schemaStore.enable: false` + globy absolutne (`C:/opt/netdash/...`) — inaczej przy workspace `brain-client` Schema Store narzuca `docker-compose.json` (v3+, bez `mem_limit`).
- **Obraz**: `ghcr.io/lobrzut/netdash:1.3.102`.

## v1.3.101

- **Compose (QNAP)**: usunięto `cpus` (schemastore `docker-compose.json` nadal flaguje to pole mimo Compose 2.4). Zostaje `mem_limit: 512m`; opcjonalny limit CPU ręcznie w Container Station UI.
- **Obraz**: `ghcr.io/lobrzut/netdash:1.3.101`.

## v1.3.100

- **Compose (QNAP)**: usunięto `cpu_quota`/`cpu_period` (fałszywe ostrzeżenia yaml-language-server przy schemastore). Zamiast tego `cpus: 1.0` + `mem_limit: 512m` (Compose 2.4, schemat `json.schemastore.org/docker-compose.json`).
- **Obraz**: `ghcr.io/lobrzut/netdash:1.3.100`.

## v1.3.99

- **Compose (QNAP)**: schemat IDE zmieniony z compose-spec na `json.schemastore.org/docker-compose.json` (Compose 2.4: `mem_limit`, `cpu_quota`, `cpu_period` bez ostrzeżeń yaml-language-server).
- **README**: sekcja Acknowledgements (Homer, GPTWOL).
- **Obraz**: `ghcr.io/lobrzut/netdash:1.3.99`.

## v1.3.98

- **Compose (QNAP)**: `yaml-language-server` schema override + `.vscode/settings.json` — walidacja względem compose-spec (pola Compose 2.4). `cpus` zastąpione przez `cpu_quota`/`cpu_period` (= 1 rdzeń) — zero fałszywych ostrzeżeń IDE; limity nadal działają na QNAP CS.
- **Obraz**: `ghcr.io/lobrzut/netdash:1.3.98`.

## v1.3.97

- **Compose**: QNAP — `version: "2.4"` + `mem_limit`/`cpus` (bez `deploy`; CS ignoruje deploy, schemat 2.4 bez ostrzeżeń IDE). Pozostałe compose — tylko `deploy.resources.limits` (Compose v2+).
- **Obraz**: `ghcr.io/lobrzut/netdash:1.3.97`.

## v1.3.96

- **Compose**: poprawka limitów zasobów — `cpus: 1.0` (niezgodne ze schematem Compose v3) zastąpione przez `cpu_count: 1` + `deploy.resources.limits` (Docker Compose v2/v3); `mem_limit: 512m` zostaje dla QNAP Container Station / Dockge / docker run.
- **Obraz**: `ghcr.io/lobrzut/netdash:1.3.96`.

## v1.3.95

- **Filozofia projektu**: słaby sprzęt homelab (RPi, stary PC, N100, NAS, QNAP) — nie tylko QNAP. Safe mode i limity zasobów są domyślne **w całym projekcie**.
- **Kod**: komunikaty skanu/health bez hardcoded „QNAP” w logice safe mode; ogólne „słaby sprzęt” / „Docker bridge”.
- **UI (i18n)**: ostrzeżenia profilu skanu — „słaby serwer” zamiast QNAP-first; docker scan hint uniwersalny.
- **Dokumentacja**: README i DEPLOYMENT — homelab weak hardware jako domyślne założenie projektu.
- **Obraz**: `ghcr.io/lobrzut/netdash:1.3.95`.

## v1.3.94

- **Słaby sprzęt (domyślnie)**: `NETDASH_SCAN_SAFE_MODE=true` w kodzie i we wszystkich compose — nie tylko QNAP. `mem_limit: 512m`, `cpus: 1.0` w docker-simple, root compose, Dockge, dev.
- **Health**: `/api/health` zwraca `resource_profile` (`safe` / `normal`); mniejsza równoległość health checków w safe mode; opóźniony pierwszy health check przy starcie (30 s).
- **UI**: Ustawienia → Skanowanie — profil (Bezpieczny / Normalny / Agresywny), ostrzeżenia; pełny skan wymaga potwierdzenia.
- **Dokumentacja**: README i DEPLOYMENT — sekcja „Słaby sprzęt” (CIDR /28, env vars).
- **Obraz**: `ghcr.io/lobrzut/netdash:1.3.94`.

## v1.3.93

- **Fix krytyczny QNAP (crash NAS przy skanie)**: `NETDASH_SCAN_SAFE_MODE=true` domyślnie w compose QNAP — niska równoległość (8), krótka lista portów, opóźnienia między partiami, limit hostów (64), twardy timeout (300 s). Pełny skan zablokowany w safe mode.
- **Skan**: batch processing zamiast 254 równoległych zadań TCP; `mem_limit: 512m` i `cpus: 1.0` w compose QNAP.
- **UI**: potwierdzenie przed skanem na słabym sprzęcie; baner trybu bezpiecznego; „Failed to fetch” → czytelny komunikat po polsku.
- **API**: `/api/health` i `/api/network` zwracają `scan_safe_mode`.
- **Obraz**: `ghcr.io/lobrzut/netdash:1.3.93`.

## v1.3.92

- **Skan (UI)**: usunięty przycisk „Skanuj sieć” z Pulpitu (`#scan-btn-home`); skan jednym kliknięciem tylko na zakładce Serwisy (`#scan-btn`, `#empty-scan-btn`) — `POST /api/scan` + pasek postępu.
- **Fix**: nagłówek Serwisów otwierał modal zamiast startować skan (regresja v1.3.91).
- **Obraz**: `ghcr.io/lobrzut/netdash:1.3.92`.

## v1.3.91

- **Fix sesji QNAP (F5) — root cause**: v1.3.89+ nie czytał tokena z localStorage przy starcie, a cookie `netdash_session` czasem nie wraca na HTTP — boot teraz próbuje cookie, potem Bearer z localStorage; `/api/auth/me` odświeża cookie przy sukcesie.
- **Boot równoległy**: `/api/health` i `/api/auth/me` równolegle — szybsze ładowanie, zawsze widać auth/me w logach.
- **Cache JS**: `Cache-Control: no-cache` na `app.js`, `i18n.js`, `style.css` — koniec starego JS po aktualizacji obrazu.
- **Skan**: przyciski Pulpit/pusty stan uruchamiają `POST /api/scan` od razu (bez drugiego kliknięcia w modalu); stare joby `running` po restarcie oznaczane jako failed.
- **QNAP compose**: `NETDASH_COOKIE_SECURE: "false"` jawnie; obraz `1.3.91`.
- **Logi**: `GET /api/auth/me OK user=… cookie=… bearer=…` przy każdym udanym odświeżeniu sesji.

## v1.3.90

- **Fix „Ładowanie sesji…” (QNAP)**: `GET /api/auth/me` ma timeout 5 s — po błędzie/timeout natychmiast ekran logowania (bez wiecznego spinnera).
- **Boot**: `try/finally` gwarantuje wyjście z `boot-view` → zawsze logowanie lub dashboard; timeout także na `/api/health`.
- **Logi**: klient `console.warn` przy timeout/błędzie sesji; serwer loguje `GET /api/auth/me: brak cookie sesji` przy 401 bez cookie.
- **Obraz**: `ghcr.io/lobrzut/netdash:1.3.90`.

## v1.3.89

- **Fix sesji QNAP (F5)**: ekran „Ładowanie sesji…” do czasu `GET /api/auth/me`; brak odczytu starego tokena z localStorage przy starcie; przy 401 retry cookie-only i `restoreSession()` zamiast natychmiastowego wylogowania.
- **Serwer**: log `Session cookie set for user X` przy logowaniu i `/api/auth/me`.
- **QNAP compose domyślnie bridge**: `docker-compose.full.yml` i `docker-compose.yml` używają `ports: 18787:18787` zamiast `network_mode: host` (host nie skanuje LAN na QNAP).
- **Test skanu**: przycisk **Ustawienia → Skanowanie → Test skanu sieci** + `POST /api/network/scan-test` (ping, CIDR, docker bridge) — wpis w logach kontenera.
- **Obraz**: `ghcr.io/lobrzut/netdash:1.3.89`.

## v1.3.88

- **QNAP entrypoint (impossible to miss)**: banner `NetDash entrypoint v1.3.88`, `LISTEN_PORT=18787 (8787 blocked)` w pierwszych liniach logu — łatwa diagnoza starego obrazu GHCR bez entrypoint.
- **QNAP compose.full.yml**: obraz przypięty `ghcr.io/lobrzut/netdash:1.3.87` (nie `:latest` — unika cache CS ze starym 8787).

## v1.3.87

- **Fix skanu QNAP (UI)**: przycisk „Skanuj sieć” widoczny na Pulpicie i w pustym stanie Serwisów; delegacja zdarzeń `#scan-start` — zawsze wysyła `POST /api/scan`; czerwony baner `#scan-error` gdy start skanu się nie powiedzie.
- **Sesja**: `GET /api/auth/me` zwraca `access_token` i odświeża cookie — po F5 brak ponownego `POST /api/auth/login`.
- **Serwer**: log `POST /api/scan body=...` przy każdym starcie skanu; `resolve_scan_cidrs` preferuje `NETDASH_SCAN_CIDR` gdy brak CIDR w UI.
- **QNAP compose**: obraz `1.3.87`.

## v1.3.86

- **Fix sesji QNAP (odświeżanie)**: cookie `netdash_session` (`HttpOnly`, `Path=/`, `SameSite=Lax`, `Secure=false` na HTTP); nowy endpoint `GET /api/auth/me` — frontend sprawdza sesję przed ekranem logowania (bez ponownego `POST /api/auth/login` po F5).
- **Migracja cookie**: odczyt starego `netdash_token` do czasu ponownego logowania; `NETDASH_COOKIE_SECURE=false` domyślnie (QNAP HTTP).
- **Skan sieci**: log serwera `Network scan started CIDR=...`; komunikat w `error_message` gdy ping ICMP niedostępny (QNAP).

## v1.3.85

- **QNAP skan sieci (fix)**: gdy ICMP ping jest zablokowany (typowe na QNAP Docker), skan automatycznie przechodzi na **TCP discovery** całej podsieci CIDR (porty 80, 443, 22, 445, 8080, …) zamiast zwracać pusty wynik.
- **API skanu**: `error_message` w `ScanJob` / `/api/scan/{id}` — czytelne błędy (brak CIDR, brak NET_RAW, timeout); walidacja przed startem gdy kontener w sieci Docker bez CIDR.
- **`/api/network`**: pole `ping_available` — UI wie, czy ping działa.
- **Ustawienia → Skanowanie**: `scan_cidr_default` wypełniane z `NETDASH_SCAN_CIDR` przy pierwszym starcie.
- **UI Serwisy**: baner gdy ostatni skan pusty; toast z konkretnym komunikatem; CIDR wstępnie w modalu skanu.
- **QNAP compose**: obraz `1.3.85`; `docker-compose.bridge.yml` oznaczony jako zalecany gdy host mode nie skanuje LAN.

## v1.3.84

- **QNAP port nuclear fix**: aplikacja **nigdy** nie binduje **8787** — `resolve_listen_port()` czyta wyłącznie `NETDASH_LISTEN_PORT`; `NETDASH_PORT` jest całkowicie ignorowany. `entrypoint.sh` zawsze ustawia `NETDASH_LISTEN_PORT=18787` i `unset NETDASH_PORT`. Log startowy: `LISTEN_PORT=18787 (8787 blocked)`.
- **compose.full.yml**: obraz przypięty `ghcr.io/lobrzut/netdash:1.3.84` (do czasu Pull przez użytkownika).

## v1.3.83

- **Portal — aktualizacje (fix QNAP)**: przycisk „Aktualizuj teraz” zawsze widoczny gdy jest nowa wersja; bez docker.sock otwiera modal z instrukcją Watchtower / Pull w Container Station i „Sprawdź ponownie” (polling GitHub).
- **Modal postępu**: potwierdzenie bez `confirm()`, overlay „Aktualizacja w toku…”, kroki pull/restart, polling `/api/health` co 2,5 s do wykrycia nowej wersji; blokada double-click i zamknięcia podczas aktualizacji.
- **API**: czytelniejszy komunikat 503 gdy brak docker.sock; i18n pl/en/de/uk dla nowych stringów.

## v1.3.82

- **QNAP auto-update (fix)**: `docker-compose.full.yml` używa obrazu `:latest` zamiast przypiętego semver — Watchtower może pobierać nowe wersje. Literały env Watchtower (QNAP CS ignoruje `${VAR:-default}`), `WATCHTOWER_INCLUDE_STOPPED=true`.
- **Portal — O projekcie**: poprawiony tekst o Watchtower (bez mylącego „profil auto-update”); komunikat gdy nowsza wersja jest na GitHub, ale „Aktualizuj teraz” niedostępne (brak docker.sock na QNAP).
- **Dokumentacja**: sekcja rozwiązywania problemów auto-update w `deploy/qnap/README.md` i `docs/QNAP.md`.

## v1.3.81

- **Fix sesji QNAP (odświeżanie strony)**: stabilny `NETDASH_SECRET_KEY` z `/app/data/.secret` (entrypoint zawsze preferuje plik na wolumenie; Python też ładuje `.secret`). Ciasteczko sesji `HttpOnly` z `Secure=false` na HTTP, `SameSite=Lax`, ważność 7 dni; `/api/auth/logout` czyści cookie.
- **Health**: `/api/health` zwraca `secret_key_stable: true` gdy klucz wczytany z pliku `.secret`.
- **QNAP skan sieci**: compose ma twardy `NETDASH_SCAN_CIDR: "192.168.1.0/24"` (CS ignoruje `${VAR:-default}`); obraz `1.3.81`.
- **QNAP bridge compose**: `deploy/qnap/docker-compose.bridge.yml` — tryb bridge + port `18787:18787` gdy `network_mode: host` nie skanuje LAN.
- **UI**: baner ostrzeżenia na zakładce Serwisy gdy kontener w sieci Docker bez skonfigurowanego CIDR.
- **Dokumentacja QNAP**: rozszerzona sekcja troubleshooting skanu sieci i sesji (PL).

## v1.3.80

- **Fix QNAP login (definitive)**: `_sync_admin_password_from_env` nie wymaga już obecności `NETDASH_DEFAULT_ADMIN_PASSWORD` w `os.environ` — używa wartości z Settings (domyślnie `changeme`). Puste stringi z Container Station są normalizowane do domyślnych.
- **Entrypoint**: auto-generacja `NETDASH_SECRET_KEY` do `/app/data/.secret` gdy brak w env (homelab bez ręcznej konfiguracji CS).
- **QNAP compose**: twarde literały `admin` / `changeme` / `sync=true` (CS ignoruje `${VAR:-default}`); obraz `1.3.80`.
- **Health**: `/api/health` zwraca `admin_ready`, `secret_key_configured`.
- **Login**: porównanie nazwy użytkownika bez rozróżniania wielkości liter.
- **Startup log**: `Admin bootstrap: ... admin_ready=true/false`.

## v1.3.79

- **Post-deploy login (homelab)**: przy starcie kontenera, gdy `NETDASH_DEFAULT_ADMIN_PASSWORD` jest w env i `NETDASH_SYNC_ADMIN_PASSWORD=true` (domyślnie), aplikacja tworzy użytkownika admin (jeśli brak) i **synchronizuje hash hasła** z env — działa `admin`/`changeme` po każdym deployu, także ze starym wolumenem SQLite.
- **Compose**: `NETDASH_DEFAULT_ADMIN_PASSWORD:-changeme`, `NETDASH_SYNC_ADMIN_PASSWORD:-true` w QNAP, docker-simple i głównym compose; obraz QNAP `1.3.79`.
- **Dokumentacja QNAP**: sync vs ręczna zmiana hasła; `NETDASH_SYNC_ADMIN_PASSWORD=false` po ustawieniu własnego hasła.

## v1.3.78

- **Reset hasła admina (QNAP / homelab)**: `NETDASH_RESET_ADMIN_PASSWORD` — jednorazowy reset przy starcie (bcrypt, log ostrzeżenia; usuń zmienną po zalogowaniu). Skrypt `scripts/reset-admin-password.py` w obrazie Docker (`docker exec`) lub offline na `netdash.db`.
- **QNAP README**: sekcja „Nie mogę się zalogować” — File Station, stara baza, `admin`/`changeme` tylko przy pustej DB.

## v1.3.77

- **Port QNAP fix (definitive)**: aplikacja nasłuchuje wyłącznie na `NETDASH_LISTEN_PORT` (domyślnie **18787**). Stare `NETDASH_PORT=8787` z Container Station jest **ignorowane** (log ostrzeżenia) i **usuwane** w `entrypoint.sh` przed startem — koniec crash loop z Readarr.
- **QNAP compose**: obraz przypięty do `ghcr.io/lobrzut/netdash:1.3.77` (nie `:latest` — unika cache CS).
- **Wszystkie compose**: `NETDASH_LISTEN_PORT: "18787"` na stałe (bez `${NETDASH_PORT:-…}`).
- **Dockerfile**: `ENV NETDASH_LISTEN_PORT=18787`, `entrypoint.sh`, healthcheck na 18787.

## v1.3.76

- **QNAP compose**: `NETDASH_PORT` ustawiony na stałe na **18787** w `deploy/qnap/docker-compose.yml` i `docker-compose.full.yml` — stara zmienna `NETDASH_PORT=8787` w Container Station nie nadpisuje już portu przez `${NETDASH_PORT:-18787}`.
- **Dokumentacja QNAP**: rozszerzona sekcja „wciąż nasłuchuje na 8787” — kroki CS bez SSH (usuń aplikację, pull, ponowny import).

## v1.3.75

- **Domyślne logowanie `admin` / `changeme`** — jak w innych homelab stackach; dotyczy tylko **nowych** instalacji bez użytkowników w bazie. Istniejące hasła bez zmian.
- **Bootstrap** (`init_db`): konto admin tworzone tylko gdy baza nie ma żadnych użytkowników.
- **install.sh / install.ps1** (docker-simple i deploy): bez pytania o hasło — `changeme` w `.env` lub pomijanie gdy `.env` już istnieje; generowany tylko `NETDASH_SECRET_KEY`.
- **Dokumentacja**: przypomnienie o **obowiązkowej zmianie hasła** po pierwszym logowaniu (Ustawienia → Hasło).

## v1.3.74

- **Fix**: składnia `HEALTHCHECK` w Dockerfile (`CMD-SHELL` → `CMD sh -c`) — blokowała build obrazu GHCR.

## v1.3.73

- **Domyślny port 18787** (`NETDASH_PORT`): unika kolizji z **Readarr (8787)** i typowymi portami homelab (80, 443, 3000, 5000, 8080, 8096, 8989…). Wszystkie compose, healthchecki i `run.py` respektują zmienną środowiskową.
- **Migracja z 8787**: istniejące instalacje — dodaj `NETDASH_PORT=8787` w `.env` do czasu zmiany zakładki, albo usuń i przejdź na `http://<host>:18787`.
- **Skaner LAN**: rozpoznaje NetDash na porcie 18787 (8787 oznaczony jako legacy).

## v1.3.72

- **Auto-aktualizacja (QNAP / Docker)**: GitHub Actions publikuje obraz na `ghcr.io/lobrzut/netdash` przy tagu `v*`. Compose: `image` + opcjonalny profil **Watchtower** (`docker compose --profile auto-update up -d`). Etykieta `watchtower.enable` tylko na NetDash — brak auto-update bez świadomego włączenia.
- **Ustawienia → O projekcie — Sprawdź aktualizacje**: `GET /api/updates/check` (GitHub Releases API), status wersji, link do changelogu. Opcjonalnie **Aktualizuj teraz** (`POST /api/updates/apply`) przy `NETDASH_UPDATE_APPLY_ENABLED` + montowany `docker.sock` (dokumentacja ryzyk w `docs/QNAP.md`).
- **Dokumentacja**: `docs/QNAP.md` (Container Station, GHCR, Watchtower, PL), rozszerzony `DEPLOYMENT.md`.

## v1.3.71

- **Pulpit — fix nachodzenia ★ na ikonę**: w układach Kompaktowy (duży) i Średni pasek akcji jest z powrotem w prawym górnym rogu (★ po lewej w grupie przycisków, edycja/notatki/WoL po prawej) — bez nachodzenia na ikonę serwisu. Kompaktowy bez zmian (pasek rozwija się na dole).

## v1.3.70

- **Ustawienia → Pulpit — fix listy motywów**: przeglądarka mogła trzymać w cache stary `index.html` (bez `?v=`), przez co w selectcie widać było tylko jedną opcję (np. „Kompaktowy (duży)”) mimo że serwer serwuje 5 układów. `syncDashboardLayoutSelect()` odbudowuje opcje z JS przy starcie i otwarciu ustawień; `Cache-Control: no-cache` na `/` + meta tag.

## v1.3.69

- **Pulpit — układ Kompaktowy (mniejszy)**: zmniejszone kafelki (~178px × min. 48px, ikona 32px) z rozwijanym paskiem akcji na dole przy hover — więcej serwisów na ekranie przy zachowaniu czytelności.
- **Pulpit — nowy układ Kompaktowy (duży)**: rozmiar kafelków jak poprzedni Kompaktowy v1.3.68 (~210px × min. 60px, ikona 38px), stała wysokość karty — akcje (★, edycja, notatki, WoL, sleep) w prawym górnym rogu na hover (jak Średni), bez rozszerzania kafelka w dół. Piąty motyw w Ustawienia → Pulpit. i18n pl/en/de/uk.
- **Pulpit — gwiazdka odpięcia po lewej**: w układach Kompaktowy, Kompaktowy (duży) i Średni przycisk ★ jest po lewej stronie paska akcji (edycja, notatki, WoL, sleep po prawej) — `space-between` zamiast grupowania wszystkich ikon po prawej.

## v1.3.68

- **Pulpit — układ Kompaktowy**: przywrócony pasek akcji rozwijany w dół na hover (★, edycja, notatki, WoL, sleep) — karta płynnie rośnie pod treścią zamiast nachodzić w prawym górnym rogu. Zachowane ulepszenia v1.3.64+: większe kafelki (~210px), siatka `auto-fill`, 2-liniowe etykiety, lepszy padding. Układ Średni bez zmian (akcje w rogu).

## v1.3.67

- **Nagłówek — porządek akcji**: selektor języka (PL/EN/DE/UA) przeniesiony z paska głównego do Ustawień → Język. Przycisk ustawień to sama ikona ⚙ obok „Wyloguj” (tooltip i `aria-label` z i18n). Stała szerokość slotu „Skanuj sieć” / „+ Dodaj” — przełączanie Pulpit ↔ Serwisy nie przesuwa ikon po prawej.

## v1.3.66

- **Pulpit — układ Średni (polish)**: większe mini-karty w grupach kategorii (~200px+, min. 68px) — ikona 38px, nazwa (13px semibold, 2 linie) i port jako podtytuł w pionowym stosie. Siatka `auto-fill` wypełnia szerokość pudełka kategorii (bez pustych 2×2 i pojedynczych „dziur”). Akcje (★, edycja, notatki, WoL, sleep) w prawym górnym rogu na hover — bez nachodzenia na port/nazwę. Delikatniejsza ramka przypiętych (akcent kategorii na hover zamiast stałej zielonej). Lepszy padding/nagłówki sekcji (WEB, INNE, API…). Dedup pinów rozszerzony o `host:port` (np. podwójny Portainer/AI-SIEM/RDP).

## v1.3.65

- **Pulpit — Klasyczny (mały)**: wyraźnie większe ikony na przypiętych kartach (27px → 40px, ten sam rozmiar co Klasyczny) — powiększony kontener, glyph 14px, status-dot 7px. Siatka kart min. 7.5rem (mobile 6.25rem), lekko większy padding/gap w górnej strefie. Nazwa, URL i stopka bez zmian hierarchii.

## v1.3.64

- **Pulpit — układ Kompaktowy (mini-karty)**: wyraźnie większe kafelki przypiętych serwisów (~210px+, min. 60px wysokości) — ikona 38px, czytelna nazwa (13px, semibold) i port jako podtytuł. Siatka `auto-fill` wypełnia szerokość wiersza zamiast zostawiać pustą przestrzeń po prawej. Akcje (★, edycja, notatki, WoL, sleep) w prawym górnym rogu na hover (Homer/Dashy) — bez rozszerzania karty w dół. Lepsze wyrównanie etykiet kategorii z wierszem kafelków.

## v1.3.63

- **Pulpit — układ Kompaktowy (polish)**: większe chipy przypiętych serwisów (152–184px × min. 48px) z czytelniejszą etykietą (2 linie, 12px), lepszym paddingiem i wyrównaniem ikony. Pasek akcji (★, edycja, notatki, WoL, sleep) w dedykowanym wierszu pod treścią — bez nachodzenia na ikonę/nazwę. Szersze etykiety kategorii (2 linie), wyrównanie wierszy `flex-start`.

## v1.3.62

- **Pulpit — scroll (fix v3)**: naprawione trwałe blokowanie przewijania po zamknięciu modala — `closeIconPopover()` było wywoływane bez definicji (ReferenceError), więc `unlockPageScroll` nigdy nie działał i `body` zostawało z `position: fixed`. Blokada oparta na liczbie widocznych `.modal` w DOM (zamiast refcount), `reconcilePageScrollLock` przy starcie i `pageshow`. Jeden scrollport: `html { overflow-y: scroll }`, bez drugiego na `body`.

## v1.3.61

- **Pulpit — scroll (fix v2)**: jeden scrollport na `html` (`overflow-y: scroll`, bez `!important`); `body` rośnie z treścią (`overflow-y: visible`, `height: auto`). Usunięte `overflow-y: auto` z `html, body` (v1.3.58 zdjęło flex-trap, ale drugi scrollport na `body` nadal blokował kółko przy 17+ pinach / 8 kategoriach). Jawne `overflow: visible` / `max-height: none` na łańcuchu `#app` → `#dashboard-view` → `.main` → `.pinned-section` + guard `[data-theme]`. Układ Średni: `height: 100%` / `stretch` → `auto` / `start`. Klasyczny/Średni: max 3 kolumny grup od 1280px. Sticky header: `isolation: isolate`.
- **Pulpit — dedup pinów**: `dedupePinnedServices` przez `normalizeUrlCompareKey` (jak duplikat URL w modalu) — jeden wpis na ten sam endpoint (np. podwójny AI-SIEM).

## v1.3.60

- **Pulpit — Klasyczny (mały)**: powiększenie układu `classic-sm` z ~50% do ~63% wymiarów Klasycznego (ikona 27px, karta min. 116px, czcionki/paddingi/watermark proporcjonalnie). Zachowany pionowy układ Homer i aspect 22:19.

## v1.3.59

- **Język — dropdown (fix)**: natywne opcje select (PL/EN/DE/UA) niewidoczne na białym popupie OS — `color-scheme: dark|light` per motyw, `option { background, color }` dla wszystkich `select` i `.lang-select`. Etykieta UK → UA w nagłówku.

## v1.3.58

- **Pulpit — scroll (fix)**: usunięty flex-column trap na `#dashboard-view` oraz `overflow-x: hidden` na `#app` / `#dashboard-view` (CSS wymuszał `overflow-y: auto` na kontenerze o wysokości viewportu — kółko myszy nie przewijało dokumentu). Przewijanie strony działa przy 8+ grupach kategorii.
- **Pulpit — układ Średni (polish)**: stała wysokość mini-kart (52px), wyrównanie ikona+nazwa+port, większe odstępy grup, etykiety kategorii z ellipsis+tooltip, pasek akcji na hover wyśrodkowany po prawej (bez nachodzenia na ★), padding przy hover pod gwiazdkę.

## v1.3.57

- **Pulpit — ★ odpinanie (fix)**: większy inset gwiazdki od krawędzi karty/chipa (`0.5rem`), przycisk 24px — nie nachodzi na zaokrąglony róg ani border przy `overflow: hidden`. Classic-sm i compact — proporcjonalnie mniejszy przycisk/inset; compact — padding przy hover pod ★.

## v1.3.56

- **Pulpit — ★ odpinanie**: gwiazdka w lewym górnym rogu karty/chipa na hover (classic, classic-sm, medium, compact). Badge AUTO/LOGIN pozostają po prawej; compact — dodatkowy padding przy hover, żeby nie nachodzić na ikonę.

## v1.3.55

- **Pulpit — scroll**: naprawione blokowanie przewijania pionowego przy wielu przypiętych kategoriach/serwisach (`overflow-y: visible` na `#dashboard-view` / `#app`, `flex: 1 0 auto` na `.main`). Modal ustawień bez zmian.
- **Pulpit — WoL/SOL na przypiętych**: przyciski ✎ 📝 ⚡ 💤 na hover w classic, classic-sm, medium i compact (jak na kartach Serwisy). Istniejące API + toast.
- **Pulpit — ★ odpinanie**: gwiazdka w prawym górnym rogu na hover (fix `position: relative` nadpisującego `absolute`), z-index nad watermarkiem; compact — osobny corner ★, akcje na dole chipa.

## v1.3.54

- **Pulpit — motyw Klasyczny (mały)**: czwarty układ `classic-sm` — ta sama struktura co Klasyczny (pionowe karty w grupach, watermark, URL, kategoria, uptime), wymiary ~50% (ikona 20px, karta min. 88px). Ustawienia → Wygląd → Pulpit. i18n pl/en/de/uk.

## v1.3.53

- **Pulpit — sekcja przypiętych**: nagłówek „Przypięte serwisy” zawsze widoczny (także przy pustej liście), licznik pinów, pusta karta z CTA do Serwisów. Szersze etykiety kategorii w układzie kompaktowym (bez obcinania „DASHBO…”, „DEVELO…”); tooltip na pełnej nazwie.
- **Serwisy — duplikat URL**: ostrzeżenie w modalu dodawania/edycji, gdy ten sam URL jest już przypisany do innego serwisu (np. drugi Portainer). i18n pl/en/de/uk.
- **PWA (lekko)**: `manifest.json`, `theme-color`, ikona SVG — możliwość „Zainstaluj aplikację” w przeglądarce.
- **Docs**: `DEPLOYMENT.md` — wersja zsynchronizowana z `config.py`.

## v1.3.52

- **Dashboard — 3 motywy pulpitu**: **Klasyczny** (Homer-style pionowe karty w grupach kategorii: ikona, nazwa, URL, kategoria, uptime, watermark), **Średni** (poziome mini-karty ~58px: ikona + nazwa + port, subtelne grupy), **Kompaktowy** (gęste chipy w wierszach). Ustawienia → Wygląd → Pulpit → **Motyw pulpitu** z podglądem na żywo. Domyślny: Średni. Migracja DB: `large`→classic, `normal`→medium, `compact` bez zmian.
- **Odpinanie (★)**: przycisk w prawym górnym rogu karty/chipa na hover — nie blokuje kliknięcia w serwis. Toast po odpięciu. i18n pl/en/de/uk.

## v1.3.51

- **Dashboard — przypięte serwisy (ultra-kompakt)**: dedykowane chipy `.pinned-chip` (~40×140px) zamiast kart serwisowych — wiersz kategorii (10px muted label) + inline chipy (32px ikona, nazwa, port tylko na hover). Bez badge PIN/auto/login, bez zielonej ramki pinned. Dedup po host:port:url. `data-pinned-size="compact"` wymuszony zawsze. ~200px wysokości dla ~11 pinów.

## v1.3.50

- **Dashboard — przypięte serwisy (fix)**: Homer-style — wiersz kategorii + poziome chipy (~56px), nie siatka wysokich kart w 5 kolumnach. Selektory `#pinned-container .service-card--pinned` po bazowym `.service-card` (cascade fix). Usunięty `aspect-ratio` na przypiętych. Migracja DB: `pinned_card_size` large/normal → compact. `body data-pinned-size="compact"` w HTML przed JS.

## v1.3.49

- **Service modal — upload icon (fix)**: „Wgraj z pliku” as primary action opens native OS file picker reliably (`sr-file-input` instead of `display:none`). URL field moved to collapsed „lub podaj URL”; uploaded icons show preview + filename only (not raw `/uploads/icons/…` in the main field). Identify favicon URLs stay in collapsed section. Same pattern for Settings → Favicon upload. i18n pl/en/de/uk.

## v1.3.48

- **Dashboard — kompaktowe przypięte serwisy**: karty w poziomie (ikona + nazwa + port), max ~58px wysokości; ukryty URL (tooltip na nazwie), bez kategorii/uptime w grupie. Mniejsze badge, watermark i panele grup (`minmax(14rem)`). Pin, hover-akcje i grupowanie bez zmian.
- **Settings → Wygląd → Pulpit — rozmiar przypiętych kart**: Kompaktowy (domyślny) | Normalny | Duży. `pinned_card_size` w bazie; `body[data-pinned-size]`; podgląd na żywo. Lista Serwisy bez zmian. i18n pl/en/de/uk.

## v1.3.47

- **Service modal — upload icon file**: „Wgraj plik” / Upload icon button in add/edit modals (Wygląd). Uploads PNG/JPEG/WebP/SVG (max 2 MB) via `POST /api/services/upload-icon`; preview and `icon_url` update immediately; filename/thumbnail shown for uploaded icons. Works alongside preset grid and URL field. Auth + mime/size validation. i18n pl/en/de/uk.

## v1.3.46

- **Dashboard — przypięte serwisy w grupach kategorii**: karty przypięte na pulpicie są zgrupowane w większe panele (Homer/Dashy) z dyskretną etykietą kategorii serwisu (DevOps, Web, Inne…). Grupy układają się w siatce na desktopie i jednej kolumnie na mobile. Pin, akcje kart i watermark bez zmian.

## v1.3.45

- **Serwisy — filtr dostępności (Wszystkie | Online | Offline)**: osobny pasek obok dostępu; Offline usunięty z paska dostępu (zostaje Przypięte ★). Klik „Wszystkie” w dostępie resetuje filtr Online/Offline; przy aktywnym Online/Offline pigułka dostępu „Wszystkie” jest przyciemniona. Liczniki wzajemnie wykluczające: online + offline + nieznane = wszystkie. i18n pl/en/de/uk.

## v1.3.44

- **Service modal icon picker (inline)**: always-visible visual grid with search, category tabs, and emoji/SVG tiles in add/edit modals — replaces hidden popover and old text `<select>`. Recent icons (localStorage), keyboard arrows + Enter, selected-state highlight, live preview. i18n pl/en/de/uk.

## v1.3.43

- **Settings modal width (fix)**: dialog now truly uses `min(1200px, 96vw)` — overrides the base `.modal-content` `max-width: 440px` that kept v1.3.39 at ~440px. Sidebar stays 200px; content pane ~960px+. Two-column fields get a higher min width; fixed height and mobile layout (≤768px) unchanged.

## v1.3.42

- **Serwisy — filtry Offline + Przypięte ★ (jeden pasek)**: Wszystkie | Z logowaniem | Publiczne | WoL | Offline | Przypięte ★ w jednym segmented control. Offline = `serviceHealthState` offline/error; Przypięte = `pinned === true`. Liczniki kombinowalne z kategorią/siecią/wyszukiwaniem. i18n pl/en/de/uk.

## v1.3.41

- **Logo NetDash**: dopracowany SVG crosshair (ciemny zaokrąglony kwadrat, neonowy zielony celownik z delikatnym glow). Ten sam plik w nagłówku, faviconie i domyślnym watermarku kart serwisów. `use_custom_logo` pozostaje wyłączone — bez logo HELLUK.

## v1.3.40

- **Serwisy — filtry Offline i Przypięte ★**: pasek filtrów dostępu rozszerzony do Wszystkie | Z logowaniem | Publiczne | WoL | Offline | Przypięte ★. Offline = `is_online === false` lub błąd health (nie login-gated); Przypięte = `pinned === true`. Liczniki na pigułkach, kombinowalne z kategorią i siecią. i18n pl/en/de/uk.

## v1.3.39

- **Settings modal width**: dialog widened to `min(960px, 95vw)`; sidebar fixed at 200px so the content pane gets more room. Fixed height unchanged; mobile layout below 640px unchanged.

## v1.3.38

- **Multi-network scanning**: Settings → Scanning and the scan modal accept multiple CIDR ranges (one per line or comma-separated), e.g. `192.168.1.0/24, 192.168.0.0/24, 10.0.0.0/24`. Backend validates and scans all listed subnets; ARP scan covers all configured networks.
- **Settings → Scanning scroll fix**: extra bottom padding on the scan tab so “Usuń nieaktywne po (dni)” and its hint are fully visible when scrolled.
- i18n pl/en/de/uk for multi-CIDR labels and hints.

## v1.3.37

- **Modal form UX**: single-column layouts in narrow modals, section headers, `settings.optional` hint pattern, unified `.modal-form` / `.form-grid` across API key, note, service add/edit, and service-notes modals. i18n pl/en/de/uk.

## v1.3.36

- **Service modal icon picker**: clickable icon preview opens an anchored popover palette (search, category tabs, visual grid) in add and edit modals; replaces the separate preset field. i18n pl/en/de/uk.

## v1.3.35

- **Settings modal readability**: input/select padding and flex-safe widths (no text clip), bottom scroll padding, visible dark-theme scrollbar, consistent accordion spacing, two-column fields stack on narrow widths.

## v1.3.35

- Fix **dashboard pinned service cards** overflow: ellipsis on name/URL/category, `.service-body` flex column with `min-height: 0` / `gap`, taller pinned aspect ratio (22:19), no text overlap with watermark or uptime.

## v1.3.33

- **Dashboard pinned services** reuse the same Homer-style card layout as Serwisy (badges, icon, name, URL, category, uptime, watermark) via `.service-card--pinned` / `.services-grid--pinned`, scaled down with matching aspect ratio.

## v1.3.32

- Fix service card **× delete button** positioning (exclude from flex `position: relative` rule); 28px top-right hit target, hover-only.
- Fix **watermark** intermittent load: `loading="eager"`, onerror fallback icon_url → preset → letter → globe.

## v1.3.31

- Redesigned **Settings → About**: hero layout, version badge, GitHub chip, read-only author card, tech stack chips.
- Editable author/description in **General → Branding**; Save hidden on read-only tabs (About, Backup, Account).
- Build date set at Docker deploy (`NETDASH_BUILD_DATE`); i18n pl/en/de/uk for About strings.

## v1.3.30

- Fix service card **delete (×) button**: was pulled into flex flow by `position: relative` on card children — now anchored top-right with 28px hit target, hover-only like other actions; DELETE `/api/services/{id}` unchanged.
- Fix intermittent **card watermark**: eager load + onerror fallback chain (icon_url → preset icon → name letter → globe).
- In-app **toast notifications** (success / error / info) replace native `alert()` dialogs; WoL/SOL success shows green toast with ✓.
- `confirm()` kept only for destructive actions (delete service/key/note, sleep, backup import).
- Uptime: preserve raw `is_online` from API; green dot when `is_online === true` even if `last_checked` is old; amber only for genuinely unchecked/stale services.
- HTTP health: explicit online for 401/403/redirects; hide stale “checked ago” label on online cards when check is older than 2× interval.

## v1.3.27

- Fix uptime dots showing amber/stale for reachable services (Proxmox, GPTWOL, login-gated apps).
- Treat HTTP 401/403 and redirects as **online**; only 5xx / connection failures mark offline.
- Self-signed HTTPS already probed with `verify=False`; startup + background health loop logs and runs immediately.
- Sanitize percent-encoded URL bytes artifacts (`b%27next=/%27` → `?next=/`).
- Frontend refreshes service status from DB between health-check cycles.

## v1.3.26

- Enriched **Add service** modal: sections, icon preview + preset/URL, category datalist, description, pin/login toggles, Identyfikuj button (shared logic with edit modal).
- `POST /api/services` accepts `icon_url`; manually added services marked `customized`.

## v1.3.25

- Uptime indicators on service cards; Homer-inspired card polish; empty-state improvements; Homer YAML import.
