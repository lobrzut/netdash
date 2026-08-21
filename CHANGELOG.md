# Changelog

## v1.3.161

- **Pomnia service branding** — local `/static/pomnia-icon.png` for card icon + watermark (LAN favicons stay blocked; no more generic plug). Port `7865` / name `Pomnia` / `brain-core` mapped. Category hint: AI.
- **Image**: ghcr.io/lobrzut/netdash:1.3.161.

## v1.3.160

- **Fix: targeted probe hung on „Sprawdzanie…”** — UI polling no longer `await`s a full `POST /api/services/health-check` (100+ services + IPS delays held a browser HTTP slot for minutes and queued the probe). Refresh = `loadServices()` only; server `_health_check_loop` remains SoT.
- **Probe client timeout** — `Sprawdź i dodaj` aborts after 25s with a clear error instead of spinning forever; re-entry guard on the button.
- **Health-check API** — if a full pass is already running, return `{skipped: already_running}` immediately.
- **Image**: ghcr.io/lobrzut/netdash:1.3.160.

## v1.3.159

- **Pomnia tile labels** — search-appliance metrics: Index files / Chunks / Status / Uptime (PL: Pliki indeksu / Fragmenty / Status / Uptime). No more fake Notes / Sessions / Library / Code / Graph.
- **Honest redaction** — when Pomnia returns `index: null` (public or bad Bearer), NetDash shows `—` + hint instead of zeros.
- **Normalize helper** — `app/pomnia_stats.py` maps `index.files` / `index.chunks` / `uptimeSec` / `status` / `version` / `embed`.
- **Image**: ghcr.io/lobrzut/netdash:1.3.159.

## v1.3.158

- **Pomnia branding** — settings/tile labels Brain → Pomnia (PL: „Pokaż kafelkę Pomnia”, „URL statystyk Pomni”, „Token Pomni (Bearer)”).
- **Pomnia Bearer token** — new Settings field `brain_token` (password input); proxy `/api/brain/stats` sends `Authorization: Bearer …`. Fallback env: `NETDASH_POMNIA_TOKEN`, then legacy `NETDASH_BRAIN_TOKEN` / `POMNIA_STATS_TOKEN` (never commit tokens).
- **Pomnia `/healthz` + `/stats`** — normalize `index.files` / `index.chunks`; dashboard link strips `/healthz` as well as `/stats`.
- **Image**: ghcr.io/lobrzut/netdash:1.3.158.

## v1.3.157

- **Docs + pozycjonowanie** — pulpit homelab jak Homer/Homepage; discovery **na żądanie** (nie ciągły skaner LAN). README, Dockge, DEPLOYMENT, `.env.example` zsynchronizowane z v1.3.150–156.
- **[docs/SCANNING.md](docs/SCANNING.md)** — 3 kroki skanu, Popularne vs Podstawowe, ukierunkowany IP:port, safe mode vs pełny `/24`, SEP/IPS.
- **i18n** — tagline logowania nie obiecuje już automatycznego skanu TCP w tle.
- **Dockge** — `deploy-balanced.sh` i profil 2 GB: `on_demand` (wcześniej wymuszały legacy `adaptive` + tag `1.3.142`).
- **Watchtower** — `nickfedor/watchtower:1.7.1` także w root `docker-compose.yml` i `deploy/docker-simple`.
- Banner „co nowego” skrócony do aktualnego modelu skanu (wcześniej dump całej historii).
- **Obraz**: ghcr.io/lobrzut/netdash:1.3.157.

## v1.3.156

- **Fix: ręczne dodanie / probe nie gubi serwisu** — `POST /api/services` robi upsert po `(host, port)` zamiast tworzyć duplikat (np. URL z `/` vs bez). GET listy scala istniejące bliźniaki.
- **Fix: probe MultipleResultsFound** — przy dwóch wierszach na ten sam endpoint skan ukierunkowany kończył się HTTP 500; teraz wybiera keeper (customized → pinned → najstarszy) i usuwa resztę.
- **Probe = customized** — `POST /api/scan/probe?add` oznacza wiersz jako ręczny, więc `stale_remove` go nie kasuje.
- **UI** — po dodaniu/probe: toast, reset filtrów (kategoria/szukaj/offline), przejście do Serwisów (wcześniej sukces przy aktywnej innej kategorii = „nie ma na liście”).
- **Obraz**: ghcr.io/lobrzut/netdash:1.3.156.

## v1.3.155

- **Timeout skanu popularnego /24** — budżet = `hosty × porty × (delay+jitter+TCP)` + discovery + overhead; cap domyślnie **7200 s** (`NETDASH_MANUAL_SCAN_TIMEOUT_CAP`). Stary floor 1800 s urywał skan w trakcie fazy portów przy IPS-friendly.
- **Potwierdzenie** — popularne porty (~45) sondowane **tylko na żywych hostach** (faza ping/TCP discovery → faza portów); martwe IP z /24 nie dostają pełnej listy.
- **UI** — postęp „Porty na żywych hostach 12/30”; limit czasu z już zapisanymi wynikami = **sukces częściowy** (toast info), nie czerwony błąd „failed”.
- **Obraz**: ghcr.io/lobrzut/netdash:1.3.155.

## v1.3.154

- **Ukierunkowany skan** — w Opcjach skanu: IP + port (+ protokół auto/http/https/tcp) → POST /api/scan/probe → fingerprint (PORT_SIGNATURES / HTTP title, np. qBittorrent) → upsert do Serwisów. Bez skanu całej sieci.
- **Popularne porty (zalecane)** — radio Podstawowe / Popularne w modalu; jedno kliknięcie „Skanuj sieć” używa popularnych (~45: 6363, Immich, *arr, Plex/Jellyfin, HA…). Działa też przy NETDASH_SCAN_SAFE_MODE=true (IPS-friendly). **Nie** skanuje 1–65535. Stabilność skanu z v1.3.152 (chunki /28) bez zmian.
- **NETDASH_SCAN_PORT_PROFILE** — safe | popular | all_listed. NETDASH_SCAN_ALL_PORTS=true = all_listed.
- **Obraz**: ghcr.io/lobrzut/netdash:1.3.154.

## v1.3.153

- Popularne porty homelab w skanie ręcznym (działa też w safe mode / IPS-friendly).
- NETDASH_SCAN_PORT_PROFILE=safe|popular|all_listed; SERVICE_PORTS: +6363, 2283, 5055, 8334, 51820.
- Nie skanuje 1–65535. Pełny UI + ukierunkowany probe: **v1.3.154**.
- **Obraz**: ghcr.io/lobrzut/netdash:1.3.153.

## v1.3.152

- **Skan ręczny /24 nie zabija UI** — pełny CIDR nadal w jednym jobie, ale praca idzie **chunkami /28** z `asyncio.sleep(0)` między hostami; sync TCP/DNS zeszły z pętli zdarzeń; `/api/health` i poll skanu odpowiadają w trakcie skanu.
- **Timeout skalowany** — `NETDASH_MANUAL_SCAN_MAX_DURATION` (domyślnie 1800 s) + `NETDASH_MANUAL_SCAN_TIMEOUT_PER_HOST` (6 s), cap 3600 s — /24 nie urywa się na 900 s w fazie ports.
- **Progress** — częstszy heartbeat postępu (co ≤1.5 s); UI ma dłuższy retry (45 prób) i komunikat „serwer chwilowo zajęty” zamiast „czekam na kontener”.
- **Health check** — `asyncio.Lock` wokół pełnego przebiegu; POST `/api/services/health-check` pomija się gdy skan trwa (brak wyścigu StaleDataError z pętlą tła).
- **Fix** — `_known_ips = seen_ips` w `discovery_pipeline` (zamiast `|=`), żeby stare IP nie rosły w nieskończoność przy rotacji chunków.
- **Obraz**: `ghcr.io/lobrzut/netdash:1.3.152`.

## v1.3.151

- **Skan ręczny = pełny CIDR** — przy `on_demand` / `POST /api/scan` tryb bezpieczny **nie ucina już do /28** i nie blokuje `/24`. `NETDASH_SCAN_SAFE_MODE=true` nadal ogranicza równoległość i porty (IPS-friendly); pełny zakres bierze się z `NETDASH_SCAN_CIDR` / `scan_cidr_default` (domyślnie /24). Wyłączenie: `NETDASH_MANUAL_SCAN_ALLOW_FULL_CIDR=false`.
- **UI** — dialog skanu domyślnie pokazuje CIDR z ustawień (nie auto-wykryte /28 wokół IP hosta); /28 zostaje jako ostrożny preset. Soft warning + potwierdzenie dla /24 (nota SEP).
- **i18n** — komunikaty safe mode / discovery zgodne z polityką: przy `on_demand` nie twierdzą, że TCP discovery działa automatycznie w tle.
- **Obraz**: `ghcr.io/lobrzut/netdash:1.3.151`.

## v1.3.150

- **Polityka discovery** — nowy model zamiast ciągłego skanowania TCP: `off`, `on_demand` (zalecane), `scheduled`, `passive` (ARP), `adaptive` (legacy). Domyślnie **`on_demand`** w `dockge/compose.yaml`: brak skanu w tle, pełny skan przez przycisk **Skanuj sieć**.
- **Harmonogram** — `NETDASH_DISCOVERY_SCHEDULE=03:00` (UTC) lub `24h`: jeden pełny cykl IPS-friendly, potem cisza do następnego terminu.
- **Pasywne discovery** — odczyt tablicy ARP co `NETDASH_PASSIVE_INTERVAL` (domyślnie 600 s), bez sondowania portów TCP (przyjazne Symantec SEP).
- **UI** — Ustawienia → Automatyczne discovery: wybór polityki z opisem trade-offów; ostrzeżenie dla legacy adaptive.
- **Legacy** — `NETDASH_DISCOVERY_MODE=adaptive` mapuje na politykę `adaptive` gdy `NETDASH_DISCOVERY_POLICY` nie ustawiony.
- **Obraz**: `ghcr.io/lobrzut/netdash:1.3.150`.

## v1.3.149

- **Tryb IPS-friendly / stealth (anty-blokada Symantec SEP)**: IPS na komputerach w LAN (np. Symantec Endpoint Protection) blokowały źródłowe IP NetDash na 600 s (`The client will block traffic from IP address … for the next 600 seconds`), bo widziały wiele **różnych** portów sondowanych na **tym samym** hoście w krótkim oknie czasu. Największym wyzwalaczem było probowanie ~190 portów usług (`SCAN_ALL_PORTS` / `AUTO_DISCOVERY_ALL_PORTS`) na jednym żywym hoście naraz.
- **Root cause**: `scan_network` budował pary `(host, port)` w kolejności host-major i odpalał wszystko przez jeden globalny semafor — pierwszych ~32 równoległych sond trafiało w **jeden** host na 32 różnych portach jednocześnie. Analogicznie `discovery_pipeline._tier1_tcp_discovery` zbierał wszystkie porty hosta naraz.
- **Fix**: nowy `_probe_host_ports()` sonduje porty **jednego hosta** łagodnie — limit równoległości na host (domyślnie **1 port naraz**), **losowa kolejność** i **odstęp z jitterem** między sondami tego samego hosta. Skan wielu hostów równolegle działa dalej (każdy host łagodnie), więc discovery pozostaje skuteczne. Health check też serializuje sondy do tego samego hosta.
- **Nowe env (domyślnie ON)**: `NETDASH_IPS_FRIENDLY=true`, `NETDASH_PORT_PARALLEL_PER_HOST=1`, `NETDASH_PORTS_PER_HOST_DELAY=0.3`, `NETDASH_PORTS_PER_HOST_JITTER=0.2`, `NETDASH_SCAN_RANDOMIZE_PORTS=true`. Jeśli SEP nadal blokuje — zwiększ `PORTS_PER_HOST_DELAY` (np. 0.6–1.0). `NETDASH_IPS_FRIENDLY=false` przywraca stare, szybkie zachowanie.
- **Dlaczego łagodniejsze skanery nie wyzwalają IPS**: sondują mniej portów, dodają opóźnienia na host, losują kolejność albo robią ICMP/ARP-first — nie generują burzy wielu portów na jeden host w oknie detekcji. NetDash robi teraz to samo.
- **Obraz**: `ghcr.io/lobrzut/netdash:1.3.149`.

## v1.3.148

- **Mobile/dotyk — przyciski WOL/SOL na kaflach**: na smartfonie/tablecie stuknięcie w ikonę ⚡ (WOL) lub 💤 (SOL) na kaflu usługi otwierało usługę zamiast uruchamiać akcję. Pasek akcji kafla był pokazywany tylko na `:hover` (desktop), więc na ekranach dotykowych był niewidoczny/nietykalny, a tap „przechodził" do nawigacji kafla.
- **Fix (CSS)**: reguły odsłaniające paski akcji rozszerzone z `@media (hover: none)` na `@media (hover: none), (pointer: coarse)` — łapie też przeglądarki mobilne fałszywie zgłaszające obsługę hover. Dotyczy wszystkich układów pulpitu (siatka usług, przypięte: compact/compact-big/medium/classic). Dodatkowo `.service-actions` na dotyku dostaje `position: relative; z-index: 2`, aby przyciski były nad znakiem wodnym kafla (pewny hit-test).
- **Zachowanie na mobile**: przyciski WOL/SOL (oraz pin/edycja/notatki) są zawsze widoczne i klikalne; stuknięcie w nie uruchamia akcję i **nie** otwiera usługi (`stopPropagation`); stuknięcie w pozostałą część kafla nadal otwiera usługę. Desktop bez zmian (hover jak dotychczas).
- **Obraz**: `ghcr.io/lobrzut/netdash:1.3.148`.

## v1.3.147

- **Skrypty SOL (Linux/Windows/macOS)**: `AA:BB:CC:DD:EE:FF` w linii Usage to był tylko przykład — skrypty teraz **automatycznie wykrywają MAC** interfejsu domyślnego (Linux: `ip route get` → sysfs; Windows: adapter z domyślną bramą; macOS: `route get default` → `ifconfig`). Opcjonalny argument `[MAC-opcjonalny]` nadal nadpisuje wykrycie.
- **Skrypt z poziomu serwisu**: gdy NetDash zna MAC (ARP/discovery), jest **wbudowany w wygenerowany skrypt** zamiast placeholdera.
- **i18n**: zaktualizowane podpowiedzi w panelu skryptów SOL (pl/en).
- **Obraz**: `ghcr.io/lobrzut/netdash:1.3.147`.

## v1.3.146

- **Ustawienia → Automatyczne discovery**: przełącznik wyłączenia automatycznego skanowania sieci (bez restartu kontenera). Ręczne dodawanie serwisów (**Serwisy → Dodaj**) i skan ręczny nadal działają.
- **API**: `discovery_enabled` w `PATCH /api/settings`; `discovery_env_locked` gdy `NETDASH_DISCOVERY_ENABLED` w .env ma pierwszeństwo.
- **Obraz**: `ghcr.io/lobrzut/netdash:1.3.146`.

## v1.3.145

- **Kafelek Brain**: dyskretny link „Otwórz dashboard” w nagłówku kafelka — widoczny tylko gdy Brain jest online; URL wyliczany z `brain_stats_url` w ustawieniach (np. `…/stats` → baza UI).
- **API**: `/api/brain/stats` zwraca `dashboard_url` przy sukcesie.
- **Obraz**: `ghcr.io/lobrzut/netdash:1.3.145`.

## v1.3.144

- **Auto-usuwanie nieaktywnych serwisów**: `NETDASH_STALE_REMOVE_DAYS` (0 = wyłączone) lub checkbox w **Ustawienia → Skanowanie**. Po każdym cyklu health check usuwa auto-wykryte wpisy offline dłużej niż N dni (wg `last_seen`); pomija przypięte i ręczne.
- **UI**: checkbox + pole dni (domyślnie 7 po włączeniu w panelu).
- **Obraz**: `ghcr.io/lobrzut/netdash:1.3.144`.

## v1.3.143

- **Health check (LAN / porty)**: usĹ‚ugi na lokalnym IP nie sÄ… juĹĽ traktowane jako zawsze online â€” TCP/HTTP probe jak dla pozostaĹ‚ych hostĂłw.
- **Anti-flap**: `health_fail_streak` + `NETDASH_HEALTH_OFFLINE_AFTER_FAILURES` (domyĹ›lnie 2) â€” status offline dopiero po N kolejnych nieudanych sondach.
- **Skrypt**: `scripts/cleanup_stack_services.py` â€” usuwanie wpisĂłw po sĹ‚owach kluczowych usuniÄ™tego stacka (dry-run / `--apply`).
- **Obraz**: `ghcr.io/lobrzut/netdash:1.3.143`.

## v1.3.142

- **`NETDASH_DISCOVERY_ENABLED` Ă˘â‚¬â€ť kill switch**: master switch dla TCP discovery w tle; auto-off na hostach &lt;~2.1 GB RAM gdy env nie ustawiony. `dockge/compose.yaml` domyÄąâ€şlnie discovery **OFF** (`false`).
- **Profil weak (tuning)**: 4 TCP rÄ‚Ĺ‚wnolegle, interwaÄąâ€š 600 s, jeden `/28` na cykl (dual chunk tylko z `NETDASH_WEAK_DUAL_CHUNK=true`).
- **Nuclear-safe 2 GB VM**: limit kontenera **512M**, `NETDASH_AUTO_DISCOVERY_ALL_PORTS=false`, `NETDASH_STARTUP_ENRICH_ENABLED=false`, discovery odroczone (180 s / 300 s w compose). Profile w `.env.example`: ultra-safe, zbalansowany 2 GB, 4 GB+.
- **Watchtower (Docker 29+)**: `dockge/compose.yaml` uÄąÄ˝ywa `nickfedor/watchtower:1.7.1` (utrzymywany fork, Docker API 1.44+) zamiast zarchiwizowanego `containrrr/watchtower`.
- **CI**: fix Ruff F401 (nieuÄąÄ˝ywany import) Ă˘â‚¬â€ť blokowaÄąâ€š publikacjĂ„â„˘ obrazu GHCR.
- **Obraz**: `ghcr.io/lobrzut/netdash:1.3.142`.

## v1.3.141

- **Dwa tryby skanu**: **automatyczny** (`NETDASH_DISCOVERY_MODE=adaptive`, w tle, throttled, chunki `/28`) vs **rĂ„â„˘czny** (przycisk Ă˘â‚¬ĹľOpcje skanu", twarde limity). Osobne env: `NETDASH_AUTO_DISCOVERY_ALL_PORTS` (auto, stopniowo ~190 portÄ‚Ĺ‚w na ÄąÄ˝ywych hostach) vs `NETDASH_SCAN_ALL_PORTS` (tylko skan rĂ„â„˘czny).
- **Chunking**: `NETDASH_AUTO_DISCOVERY_ALWAYS_CHUNK=true` domyÄąâ€şlnie Ă˘â‚¬â€ť nigdy peÄąâ€šny `/24` w jednym cyklu auto.
- **Limity skanu rĂ„â„˘cznego**: `NETDASH_MANUAL_SCAN_MAX_HOSTS` (128), `NETDASH_MANUAL_SCAN_MIN_PREFIX` (24), przycisk **Zatrzymaj** w UI.
- **QNAP / Proxmox port fixes**: `SAFE_WEB_PORTS` i `TCP_DISCOVERY_PRIMARY_PORTS` rozszerzone o 5000/5001, **8006** (Proxmox), 8080/8081 (QNAP DSM), 873, 2049; fingerprinty QNAP w `SERVICE_PORTS` (5000, 5001, 8081, 49152).
- **UI i18n**: rozdzielenie trybÄ‚Ĺ‚w auto vs manual w panelu skanu (PL/EN/DE/UK).
- **Obraz**: `ghcr.io/lobrzut/netdash:1.3.141`.

## v1.3.140

- **Wykrywanie serwisÄ‚Ĺ‚w na nietypowych portach (`NETDASH_SCAN_ALL_PORTS=true`)**: dotĂ„â€¦d adaptive discovery sondowaÄąâ€šo hosty tylko po 11 portach (`TCP_DISCOVERY_PRIMARY_PORTS`), a tryb safe po ~6 Ă˘â‚¬â€ť serwis na np. `8123`, `32400`, `9090` nigdy nie byÄąâ€š znajdowany w tle. Teraz, gdy host zostanie wykryty jako ÄąÄ˝ywy, jest **gÄąâ€šĂ„â„˘boko sondowany po peÄąâ€šnej liÄąâ€şcie ~190 portÄ‚Ĺ‚w usÄąâ€šug** (`scanner.SERVICE_PORTS`). Tylko ÄąÄ˝ywe hosty (kilkadziesiĂ„â€¦t), bramkowane semaforem Ă˘â‚¬â€ť bez floodu sweepa /24, wiĂ„â„˘c bezpieczne na QNAP. DziaÄąâ€ša teÄąÄ˝ w skanie rĂ„â„˘cznym. W YAML-u QNAP wÄąâ€šĂ„â€¦czone domyÄąâ€şlnie. Zweryfikowane: skan znalazÄąâ€š usÄąâ€šugĂ„â„˘ na porcie 8123.
- **Obraz**: `ghcr.io/lobrzut/netdash:1.3.140`.

## v1.3.139

- **Kafelek SieĂ„â€ˇ mieÄąâ€şci siĂ„â„˘ w kaflu**: treÄąâ€şĂ„â€ˇ przekraczaÄąâ€ša `max-height: 360px` widgetu i dÄ‚Ĺ‚Äąâ€š (Ă˘â‚¬ĹľOstatni skan") byÄąâ€š ucinany. UsuniĂ„â„˘ty najsÄąâ€šabszy element Ă˘â‚¬â€ť sparkline Ă˘â‚¬ĹľWykryte Ă‚Â· 7 dni" (cienkie dane, zwykle jeden sÄąâ€šupek) Ă˘â‚¬â€ť zostaje LAN + WAN + latency + ostatni skan. Dodatkowo `.network-tile` przewija siĂ„â„˘, gdyby treÄąâ€şĂ„â€ˇ kiedyÄąâ€ş urosÄąâ€ša (zamiast ucinaĂ„â€ˇ stopkĂ„â„˘).
- **Obraz**: `ghcr.io/lobrzut/netdash:1.3.139`.

## v1.3.138

- **Kafelek SieĂ„â€ˇ Ă˘â‚¬â€ť latency zamiast donuta kategorii**: sekcja Ă˘â‚¬ĹľSerwisy wg kategorii" (donut + legenda, ktÄ‚Ĺ‚ra siĂ„â„˘ nie mieÄąâ€şciÄąâ€ša) zastĂ„â€¦piona **opÄ‚Ĺ‚ÄąĹźnieniem Äąâ€šĂ„â€¦cza** Ă˘â‚¬â€ť TCP do `1.1.1.1` (Cloudflare) i `8.8.8.8` (Google), z kolorowym wskaÄąĹźnikiem (zielony < 40 ms, ÄąÄ˝Ä‚Ĺ‚Äąâ€šty < 120 ms, czerwony wolno/brak). Mierzone serwerowo, cache 60 s, dziaÄąâ€ša nawet przy zablokowanym ICMP.
- **WAN Ă˘â‚¬â€ť miasto i kraj zamiast ISP**: pod publicznym IP pokazujemy teraz lokalizacjĂ„â„˘ (np. Ă˘â‚¬ĹľZurich, Switzerland") zamiast nazwy operatora.
- **Obraz**: `ghcr.io/lobrzut/netdash:1.3.138`.

## v1.3.137

- **Fix Ă˘â‚¬â€ť Sejf API w wĂ„â€¦skim widgecie**: karty kluczy byÄąâ€šy Äąâ€şciskane w pionie (`flex-shrink` w kontenerze o staÄąâ€šej wysokoÄąâ€şci) i ich treÄąâ€şĂ„â€ˇ nachodziÄąâ€ša na siebie. Teraz `flex-shrink: 0` (karty trzymajĂ„â€¦ wysokoÄąâ€şĂ„â€ˇ, lista siĂ„â„˘ przewija), a przyciski akcji zawijajĂ„â€¦ siĂ„â„˘ pod tekst klucza, gdy kolumna jest wĂ„â€¦ska. Maskowane kropki nie Äąâ€šamiĂ„â€¦ siĂ„â„˘ w Äąâ€şrodku.
- **Notatki jako wiersze**: kwadratowe kafelki Ă˘â€ â€™ peÄąâ€šnoszerokoÄąâ€şciowe wiersze (tytuÄąâ€š + 2 linie podglĂ„â€¦du), czytelniejsze w wĂ„â€¦skiej kolumnie. Subtelniejszy kolor tÄąâ€ša wg etykiety notatki.
- **Obraz**: `ghcr.io/lobrzut/netdash:1.3.137`.

## v1.3.136

- **Zatrzymanie skanu sieci**: pasek skanowania ma teraz przycisk **Zatrzymaj**. Anuluje task w tle (`POST /api/scan/{id}/cancel`), ustawia status `cancelled` i czyÄąâ€şci pasek. `_run_scan` obsÄąâ€šuguje `CancelledError`.
- **Kafelek SieĂ„â€ˇ Ă˘â‚¬â€ť prawdziwa flaga**: zamiast emoji (Windows pokazywaÄąâ€š Ă˘â‚¬ĹľCH" tekstem) uÄąÄ˝ywamy obrazka flagi z `flagcdn.com` wg kodu kraju, z fallbackiem do kodu literowego.
- **Sejf API Ă˘â‚¬â€ť podglĂ„â€¦d klucza**: odsÄąâ€šoniĂ„â„˘ty dÄąâ€šugi klucz nie wylewa siĂ„â„˘ juÄąÄ˝ z kafelka Ă˘â‚¬â€ť jest w ograniczonym, przewijanym boxie (`word-break` + `max-height`).
- **i18n**: klucze `scan.stop` / `scan.stopped` dla PL/EN/DE/UK.
- **Obraz**: `ghcr.io/lobrzut/netdash:1.3.136`.

## v1.3.135

- **Fix UI Ă˘â‚¬â€ť pole Ă˘â‚¬ĹľURL statystyk Brain"**: input byÄąâ€š wĂ„â€¦ski (domyÄąâ€şlna szerokoÄąâ€şĂ„â€ˇ) i ucinaÄąâ€š dÄąâ€šugie adresy (np. `Ă˘â‚¬Â¦7860/s`). Teraz peÄąâ€šna szerokoÄąâ€şĂ„â€ˇ panelu, czcionka mono Ă˘â‚¬â€ť widaĂ„â€ˇ caÄąâ€šy URL.
- **Obraz**: `ghcr.io/lobrzut/netdash:1.3.135`.

## v1.3.134

- **Kafelek Ă˘â‚¬ĹľSieĂ„â€ˇ" (opcjonalny, OFF domyÄąâ€şlnie)**: nowy widget pulpitu. Pokazuje **LAN IP / bramĂ„â„˘ / podsieĂ„â€ˇ**, licznik **urzĂ„â€¦dzeÄąâ€ž online/total**, **ostatni skan**, oraz **WAN**: publiczny IP + ISP + kraj/miasto (GeoIP `ip-api.com`, serwerowo, cache ~1h) z flagĂ„â€¦. Ă˘â‚¬ĹľFikuÄąâ€şne" staty: **donut** serwisÄ‚Ĺ‚w wg kategorii i **sparkline** wykrytych urzĂ„â€¦dzeÄąâ€ž / 7 dni. Serwer: `GET /api/network/info` (auth-gated, cache 60 s). WAN/GeoIP wyÄąâ€šĂ„â€¦czysz przez `NETDASH_NETWORK_WAN_LOOKUP=false`.
- **Ă˘â‚¬ĹľAktualizuj teraz" przez Watchtower HTTP API**: przycisk w panelu zleca update Watchtowerowi (`POST /v1/update`, Bearer) Ă˘â‚¬â€ť **bez montowania `docker.sock` do panelu**. Bezpieczne na QNAP. Ustaw `NETDASH_WATCHTOWER_API_URL` + `NETDASH_WATCHTOWER_API_TOKEN` (ten sam token co `WATCHTOWER_HTTP_API_TOKEN`). YAML QNAP zaktualizowany (port `127.0.0.1:8080`, `WATCHTOWER_HTTP_API_UPDATE`).
- **i18n**: klucze kafelka SieĂ„â€ˇ dla PL/EN/DE/UK.
- **Obraz**: `ghcr.io/lobrzut/netdash:1.3.134`.

## v1.3.133

- **Kafelek Brain (opcjonalny, OFF domyÄąâ€şlnie)**: oÄąÄ˝ywiony Ă˘â‚¬â€ť gdy ustawisz **URL statystyk Brain** (Ustawienia Ă˘â€ â€™ WyglĂ„â€¦d) wskazujĂ„â€¦cy na endpoint `/stats` zwracajĂ„â€¦cy liczby wiedzy (`notes`, `sessions`, `library_docs`, `code_files`, `graph_nodes`, `last_session_at`, `activity_7d`), kafelek pokazuje realne dane. Serwer proxuje i cache'uje (60 s) przez `GET /api/brain/stats` (auth-gated). DomyÄąâ€şlnie `show_brain=false`, wiĂ„â„˘c nic siĂ„â„˘ nie zmienia dla osÄ‚Ĺ‚b bez Brain.
- **i18n**: dodane tÄąâ€šumaczenia kafelka Brain dla EN/DE/UK (wczeÄąâ€şniej tylko PL).
- **Obraz**: `ghcr.io/lobrzut/netdash:1.3.133`.

## v1.3.132

- **UI Ă˘â‚¬â€ť watermark na wszystkich kafelkach**: przywrÄ‚Ĺ‚cony pochylony, dyfuzyjny watermark marki (`rotate(-8deg)` + miĂ„â„˘kka maska) dla logo. Emoji/litera nie znikajĂ„â€¦ juÄąÄ˝ w wygaszanym rogu Ă˘â‚¬â€ť dostajĂ„â€¦ ten sam skos bez maski, jako duÄąÄ˝y, lekko Ă˘â‚¬ĹľuciĂ„â„˘ty" glif. PrzypiĂ„â„˘te kafelki (classic / classic-sm / medium) miaÄąâ€šy krycie watermarku Äąâ€şciÄąâ€şniĂ„â„˘te do ~0.02Ă˘â‚¬â€ś0.05 Ă˘â‚¬â€ť odblokowane (Ä‚â€”0.95 / Ä‚â€”0.9 / Ä‚â€”0.75), wiĂ„â„˘c tÄąâ€šo widaĂ„â€ˇ teÄąÄ˝ w sekcji Ă˘â‚¬ĹľPrzypiĂ„â„˘te serwisy". Bazowe krycie podbite (0.10Ă˘â€ â€™0.13 / 0.06Ă˘â€ â€™0.11) dla cienkich logo (Portainer, n8n).
- **Obraz**: `ghcr.io/lobrzut/netdash:1.3.132`.

## v1.3.131

- **BezpieczeÄąâ€žstwo Ă˘â‚¬â€ť limit prÄ‚Ĺ‚b logowania**: `POST /api/auth/login` ma teraz in-memory brute-force guard (5 prÄ‚Ĺ‚b / 5 min na parĂ„â„˘ IP+login, odpowiedÄąĹź `429 Retry-After`). Reset po udanym logowaniu.
- **BezpieczeÄąâ€žstwo Ă˘â‚¬â€ť hasÄąâ€šo z UI trwaÄąâ€še**: zmiana hasÄąâ€ša w panelu ustawia flagĂ„â„˘ `app_settings.admin_password_user_set`; `NETDASH_SYNC_ADMIN_PASSWORD=true` nie nadpisuje juÄąÄ˝ hasÄąâ€ša przy restarcie. PowrÄ‚Ĺ‚t do hasÄąâ€ša z env nadal przez `NETDASH_RESET_ADMIN_PASSWORD`. Log ostrzega, gdy nadal dziaÄąâ€ša domyÄąâ€şlne `changeme`.
- **BezpieczeÄąâ€žstwo Ă˘â‚¬â€ť Swagger off**: `/docs`, `/redoc`, `/openapi.json` domyÄąâ€şlnie wyÄąâ€šĂ„â€¦czone (panel jest w LAN); wÄąâ€šĂ„â€¦cz `NETDASH_DOCS_ENABLED=true`.
- **BezpieczeÄąâ€žstwo Ă˘â‚¬â€ť guard SSRF**: serwerowe pobierania (favicon, health-check) blokujĂ„â€¦ endpointy metadanych chmurowych (`169.254.169.254`, `metadata.google.internal`, Ă˘â‚¬Â¦).
- **ZaleÄąÄ˝noÄąâ€şci**: migracja `python-jose` Ă˘â€ â€™ `PyJWT==2.10.1` (jose nie jest utrzymywany, CVE-2024-33663/33664); `cryptography` przypiĂ„â„˘te jawnie (`==44.0.0`, uÄąÄ˝ywane przez sejf API keys).
- **CI**: bramka `test` (ruff + pytest) przed buildem; obraz multi-arch `linux/amd64,linux/arm64`; cache `type=gha`.
- **Obraz**: `ghcr.io/lobrzut/netdash:1.3.131`.

## v1.3.130

- **Fix Ă˘â‚¬â€ť watermark ikon na kafelkach auto-wykrytych serwisÄ‚Ĺ‚w**: TCP discovery (v1.3.125+) tworzyÄąâ€šo wpisy bez `icon_url` Ă˘â‚¬â€ť kafelki pokazywaÄąâ€šy tylko generycznĂ„â€¦ ikonĂ„â„˘ CSS zamiast duÄąÄ˝ego watermarku marki. Po auto-create uruchamiane jest pobieranie favicon w tle (`/favicon.ico`, `<link rel=icon>`, cache w `/uploads/icons/`).
- **Fallback po porcie**: mapowanie port Ă˘â€ â€™ ikona marki (np. `:8006` Proxmox, `:9000` Portainer, `:9090` Prometheus) gdy HTTP title jest generyczny lub login-gated.
- **Enrich**: startup, rĂ„â„˘czny skan i cykl TCP discovery wywoÄąâ€šujĂ„â€¦ `enrich_service_icons` Ă˘â‚¬â€ť uzupeÄąâ€šnia brakujĂ„â€¦ce ikony dla wszystkich serwisÄ‚Ĺ‚w bez bezpiecznego `icon_url`.
- **Marki**: MeshCentral w mapowaniu; upsert nie nadpisuje istniejĂ„â€¦cego `icon_url` wartoÄąâ€şciĂ„â€¦ `null`.
- **Obraz**: `ghcr.io/lobrzut/netdash:1.3.130`.

## v1.3.129

- **Po aktualizacji Ă˘â‚¬â€ť banner Ă˘â‚¬Ĺľco nowegoĂ˘â‚¬ĹĄ**: przy pierwszym wejÄąâ€şciu po podbiciu wersji (gdy `version` > `netdash_last_seen_version` w localStorage) nieblokujĂ„â€¦cy pasek pod statusem discovery z tytuÄąâ€šem Ă˘â‚¬ĹľNetDash zaktualizowany do vX.Y.ZĂ˘â‚¬ĹĄ, 3Ă˘â‚¬â€ś5 punktÄ‚Ĺ‚w po polsku i przyciskiem Ă˘â‚¬ĹľOK, rozumiemĂ˘â‚¬ĹĄ.
- **API**: `GET /api/health` zwraca `whats_new: []` z `app/config.py` (Äąâ€šatwa aktualizacja przy kolejnym release).
- **Obraz**: `ghcr.io/lobrzut/netdash:1.3.129`.

## v1.3.128

- **Audyt release (2026-06-13)**: peÄąâ€šny przeglĂ„â€¦d v1.3.124Ă˘â‚¬â€śv1.3.127 Ă˘â‚¬â€ť `discovery_pipeline.py`, `main.py`, UI skanu (`app.js`), spÄ‚Ĺ‚jnoÄąâ€şĂ„â€ˇ wersji, `compose.full.yml` (`:latest`, Watchtower 3600 s), CI `:latest`, 24/24 testÄ‚Ĺ‚w, `node --check app.js`, importy OK.
- **Docs**: odÄąâ€şwieÄąÄ˝ono badge wersji w `README.md` i `DEPLOYMENT.md` (byÄąâ€šo `1.3.76`).
- **Watchtower**: po push tagu `v1.3.128` GHCR `:latest` aktualizuje siĂ„â„˘ w CI; QNAP z `compose.full` (`WATCHTOWER_POLL_INTERVAL=3600`) Ă˘â‚¬â€ť auto-restart NetDash w ciĂ„â€¦gu ~1 h.
- **Obraz**: `ghcr.io/lobrzut/netdash:1.3.128`.

## v1.3.127

- **UX Ă˘â‚¬â€ť ukryj niedostĂ„â„˘pne opcje skanu**: w trybie adaptive (QNAP) ukryte przyciski Ă˘â‚¬ĹľSkanuj sieĂ„â€ˇ" i Ă˘â‚¬ĹľOpcje skanuĂ˘â‚¬Â¦"; pasek statusu discovery + link do Ustawienia Ă˘â€ â€™ Skanowanie (CIDR).
- **Modal**: Ă˘â‚¬ĹľSkan rĂ„â„˘czny (zaawansowany)" z ostrzeÄąÄ˝eniem QNAP; ukryty Ă˘â‚¬ĹľPeÄąâ€šny skan" w safe mode; dropdown CIDR bez /24 gdy zablokowane.
- **Ustawienia Ă˘â€ â€™ Skanowanie**: gÄąâ€šÄ‚Ĺ‚wne miejsce na CIDR; ukryty peÄąâ€šny skan i test skanu w adaptive; sekcja zaawansowana tylko profil strong.
- **Komunikaty**: Ă˘â‚¬ĹľDiscovery automatyczne Ă˘â‚¬â€ť TCP w tle"; Ă˘â‚¬ĹľRĂ„â„˘czny skan tylko Docker (profil strong)".

## v1.3.126

- **Weak profile Ă˘â‚¬â€ť dual /28 per cycle**: kaÄąÄ˝dy cykl skanuje chunk rotowany (N) **oraz** chunk przeciwnej poÄąâ€šowy sieci `(N + 8) % 16` Ă˘â‚¬â€ť np. chunk 1+9/16 obejmuje `.0-.15` i `.128-.143` w jednym cyklu.
- **PeÄąâ€šny /24 w ~40 min** (8 cykli Ä‚â€” 5 min) zamiast ~80 min; **Proxmox `.200`** (chunk 13, `.192/28`) pierwszy skan TCP po **~11 min** zamiast ~65 min.
- **UI**: pasek statusu `Skan TCP: chunk 1+9/16, znaleziono Ă˘â‚¬Â¦` gdy skan dual.

## v1.3.125

- **TCP-first discovery** (`NETDASH_DISCOVERY_MODE=adaptive`): Tier 1 skanuje porty `[22, 80, 443, 8006, 8080, 3000, 5000, 8000, 8443, 9000]` Ă˘â‚¬â€ť dowolny otwarty port = host ÄąÄ˝ywy. Automatyczne tworzenie wpisÄ‚Ĺ‚w usÄąâ€šug (Proxmox :8006, QNAP :8080 itd.).
- **Bez hardcoded IP**: wystarczy `NETDASH_SCAN_CIDR` / CIDR w Ustawienia Ă˘â€ â€™ Skanowanie Ă˘â‚¬â€ť dziaÄąâ€ša na dowolnej adresacji.
- **ARP tylko jako enrichment** (MAC) Ă˘â‚¬â€ť nie blokuje wykrywania hostÄ‚Ĺ‚w bez ping/ARP (np. Proxmox bez ICMP).
- **Profil weak (QNAP)**: rotacja /28 co cykl (~16 chunkÄ‚Ĺ‚w /24 = peÄąâ€šna sieĂ„â€ˇ w ~80 min przy 5 min interwale); 8 rÄ‚Ĺ‚wnolegÄąâ€šych TCP, max 16 hostÄ‚Ĺ‚w/chunk.
- **UsuniĂ„â„˘to zaleÄąÄ˝noÄąâ€şĂ„â€ˇ od `NETDASH_ARP_EXTRA_HOSTS`** Ă˘â‚¬â€ť opcjonalny bonus, nie wymagany.
- **UI**: pasek statusu Ă˘â‚¬ĹľSkan TCP: chunk 3/16, znaleziono 12 serwisÄ‚Ĺ‚w" + i18n TCP-first.
- **Architektura**: README QNAP Ă˘â‚¬â€ť weak (chunk /28) vs strong (peÄąâ€šny /24 na serwerze Docker).

## v1.3.124

- **QNAP one-shot deploy**: `docker-compose.full.yml` Ă˘â‚¬â€ť jedyny plik do importu; komentarz Import raz, nie edytuj YAML. Obraz `:latest`, Watchtower co 1 h, wszystkie env w Äąâ€şrodku.
- **Portal Ă˘â‚¬â€ť modal aktualizacji**: przy `NETDASH_WATCHTOWER_ENABLED=true` komunikat Aktualizacja automatyczna przez Watchtower (co ~1 h); instrukcja rĂ„â„˘czna schowana w details.
- **README QNAP**: uproszczony do 3 krokÄ‚Ĺ‚w (import URL, start, gotowe); CIDR zmieniasz w Ustawienia Ă˘â€ â€™ Skanowanie (SQLite), nie w compose.
- **CI**: bez zmian Ă˘â‚¬â€ť workflow publikuje `:latest` oraz `:VERSION` przy kaÄąÄ˝dym tagu `v*`.
- **Obraz**: `ghcr.io/lobrzut/netdash:1.3.124`.

## v1.3.123

- **Fix wolny start QNAP (153+ serwisÄ‚Ĺ‚w)**: `init_db()` nie blokuje juÄąÄ˝ startu na `enrich_mac_addresses()` / `enrich_all_services()` (ping/ARP dla kaÄąÄ˝dego hosta) Ă˘â‚¬â€ť portal gotowy w kilka sekund, enrich w tle.
- **Health check w tle**: pierwszy przebieg odroczony (`NETDASH_STARTUP_HEALTH_DEFER`, domyÄąâ€şlnie `true` przy safe mode, 30 s); pĂ„â„˘tla health nie odpala siĂ„â„˘ od razu przy starcie.
- **Discovery odroczone**: pierwszy cykl adaptive/ARP po `NETDASH_DISCOVERY_STARTUP_DELAY` (domyÄąâ€şlnie 60 s) Ă˘â‚¬â€ť ping/arp-scan nie konkurujĂ„â€¦ z bootem.
- **Compose QNAP**: `start_period: 90s`, env defer w komentarzach; `/api/health` zwraca `startup_health_defer`, `discovery_startup_delay`.
- **Obraz**: `ghcr.io/lobrzut/netdash:1.3.123`.

## v1.3.122

- **Fix arp-scan on QNAP**: `--interval=100` (milliseconds, no suffix). BusyBox/QNAP `arp-scan` rejects `--interval=100ms` with `ERROR: "100m" is not a valid numeric value`.
- **EXTRA_HOSTS always probed**: `NETDASH_ARP_EXTRA_HOSTS` ping/TCP every cycle regardless of /28 rotation Ă˘â‚¬â€ť no longer filtered to the current chunk CIDR.
- **Weak-mode multi-chunk**: adaptive discovery scans the rotated /28 **and** any /28 containing extra hosts (e.g. `.144/28` + `.192/28` for `.200`/`.201` in one cycle).
- **Safer offline marking**: no mass-offline when arp-scan returns 0, when Ă˘â€°Â¤2 hosts found in a /28, or for hosts outside the scanned chunk(s).
- **UI cache bust**: `index.html` static assets bumped to `v=1.3.122` (fixes stale `app.js?v=1.3.119` in browser).
- **Obraz**: `ghcr.io/lobrzut/netdash:1.3.122`.

## v1.3.121

- **Hotfix: crash on startup** (`ModuleNotFoundError: app.discovery_pipeline`): v1.3.119 tagged `main.py` imports before `discovery_pipeline.py` was committed (fixed in v1.3.120). Users on `:1.3.119` could not start NetDash at all.
- **Graceful fallback**: if `discovery_pipeline` is missing from the image, app boots anyway and falls back to ARP discovery scheduler; `/api/health` reports `adaptive_discovery.available=false`.
- **Obraz**: `ghcr.io/lobrzut/netdash:1.3.121` Ă˘â‚¬â€ť **pull this if you are on 1.3.119**. v1.3.120 should already include the module; upgrade to 1.3.121 for the import guard.

## v1.3.120

- **Adaptive Tiered Discovery** (`NETDASH_DISCOVERY_MODE=adaptive` Ă˘â‚¬â€ť nowy domyÄąâ€şlny tryb QNAP): jeden scheduler koordynuje ping Ă˘â€ â€™ ARP Ă˘â€ â€™ lekki skan portÄ‚Ĺ‚w. Ping zawsze pierwszy (ICMP lub TCP :80), ARP tylko dla MAC / hostÄ‚Ĺ‚w bez ping, porty tylko dla nowych lub nieaktualnych (>24 h).
- **Profile sprzĂ„â„˘towe** (`NETDASH_DISCOVERY_PROFILE=auto|weak|normal|strong`): QNAP/sÄąâ€šabe maszyny Ă˘â‚¬â€ť interwaÄąâ€š 300 s, 8 rÄ‚Ĺ‚wnolegÄąâ€šych pingÄ‚Ĺ‚w, 1 host na raz przy portach, rotacja /28 zamiast floodu /24. Mocne Ă˘â‚¬â€ť krÄ‚Ĺ‚tsze interwaÄąâ€šy, 32 pingi, 4 porty rÄ‚Ĺ‚wnolegle.
- **ARP auto-skip**: gdy `arp-scan` zwraca 0 hostÄ‚Ĺ‚w 3Ä‚â€” z rzĂ„â„˘du Ă˘â‚¬â€ť discovery opiera siĂ„â„˘ na ping (bez masowego offline).
- **UI**: pasek statusu Ă˘â‚¬ĹľDiscovery: ping 42 Ă˘â€ â€™ arp +12 MAC Ă˘â€ â€™ 3 nowe porty (profil: weak)Ă˘â‚¬ĹĄ.
- **API**: `GET /api/discovery/status`, `POST /api/discovery/cycle`. Legacy `arp` i `remote` bez zmian.
- **Obraz**: `ghcr.io/lobrzut/netdash:1.3.120`.

## v1.3.119

- **Fix: serwisy OFFLINE mimo HTTP 200**: status online/offline usÄąâ€šug HTTP/TCP pochodzi wyÄąâ€šĂ„â€¦cznie z health checkera (`NETDASH_HEALTH_INTERVAL`, domyÄąâ€şlnie 120 s na QNAP). ARP discovery i `mark_missing_offline` aktualizujĂ„â€¦ tylko wpisy host-only (`protocol=host`, port 0) Ă˘â‚¬â€ť nie nadpisujĂ„â€¦ `is_online` na portach 3000/8000 itd.
- **Skan TCP**: `_finalize_scan` nie oznacza juÄąÄ˝ portowych usÄąâ€šug jako offline, gdy nie wykryto portu w skanie Ă˘â‚¬â€ť health check decyduje.
- **UI**: zielona kropka i badge offline na karcie serwisu = ostatni health check; karta hosta moÄąÄ˝e byĂ„â€ˇ offline przy dziaÄąâ€šajĂ„â€¦cych usÄąâ€šugach.
- **Obraz**: `ghcr.io/lobrzut/netdash:1.3.119`.

## v1.3.118

- **Fix ARP discovery returning 0 hosts on QNAP**: when `arp-scan` finds nothing, auto-fallback to `ip neigh`, rate-limited ping/TCP sweep, and quick-scan style discovery; log full `arp-scan` command and stderr.
- **Interface auto-detect**: `NETDASH_ARP_IFACE` or parse `ip route get <gateway>` (bond0/eth0) Ă˘â‚¬â€ť passed to `arp-scan -I`.
- **Explicit homelab hosts**: `NETDASH_ARP_EXTRA_HOSTS=192.168.1.200,192.168.1.201` probed every cycle via ping/TCP.
- **Safer offline marking**: only mark missing hosts offline when `arp-scan` itself returned hosts (fallback-only cycles no longer mass-offline).
- **Obraz**: `ghcr.io/lobrzut/netdash:1.3.118`.

## v1.3.117

- **ARP discovery on QNAP (WatchYourLAN / Pi.Alert style)**: `NETDASH_DISCOVERY_MODE=arp` Ă˘â‚¬â€ť background `arp-scan` every `NETDASH_ARP_INTERVAL` (default 300 s), rate-limited (`--interval=100ms --retry=1`), no TCP sweep during cycle. Optional light port probe for **new** hosts only (one at a time).
- **QNAP compose**: `network_mode: host` + `cap_add: NET_RAW, NET_ADMIN` Ă˘â‚¬â€ť discovery runs on NAS, no separate homelab agent required. Removed default `NETDASH_SCAN_DISABLED=true`.
- **UI**: status bar Ă˘â‚¬ĹľSkan ARP: ostatni cykl X min temu, Y hostÄ‚Ĺ‚wĂ˘â‚¬ĹĄ; one-click TCP scan hidden in ARP mode; advanced scan via Ă˘â‚¬ĹľOpcje skanuĂ˘â‚¬ĹĄ. Remote agent optional (collapsed in Settings).
- **Dockerfile**: `arp-scan` package installed.
- **API**: `GET /api/discovery/arp-status`, `POST /api/discovery/arp-cycle`.
- **Obraz**: `ghcr.io/lobrzut/netdash:1.3.117`.

## v1.3.116

- **Fix krytyczny QNAP Ă˘â‚¬â€ť wieczne Ă˘â‚¬ĹľÄąÂadowanie sesjiĂ˘â‚¬Â¦Ă˘â‚¬ĹĄ (v1.3.115)**: `finishBoot` Ă˘â€ â€™ `reconcilePageScrollLock` Ă˘â€ â€™ `countOpenModals` woÄąâ€šaÄąâ€šo `$$('.modal').filter(...)` Ă˘â‚¬â€ť `querySelectorAll` zwraca `NodeList` bez `.filter` w WebView QNAP Ă˘â€ â€™ `Uncaught TypeError: $$(...).filter is not a function`, boot padaÄąâ€š, spinner zostawaÄąâ€š. **`$$` zwraca teraz tablicĂ„â„˘** (`[...querySelectorAll]`); `finishBoot` w `try/catch`.
- **Boot**: uruchamia siĂ„â„˘ na poczĂ„â€¦tku `app.js` (watchdog nie blokowany przez pÄ‚Ĺ‚ÄąĹźniejsze event listenery). Inline `<script>` w `index.html`: 5 s fallback Ă˘â€ â€™ login; wczesny probe `GET /api/auth/me` (3 s).
- **`/api/auth/me` timeout**: 3 s; watchdog bootu: 5 s.
- **Obraz**: `ghcr.io/lobrzut/netdash:1.3.116`.

## v1.3.115

- **Fix krytyczny QNAP Ă˘â‚¬â€ť wieczne Ă˘â‚¬ĹľÄąÂadowanie sesjiĂ˘â‚¬Â¦Ă˘â‚¬ĹĄ**: regresja v1.3.114 Ă˘â‚¬â€ť bÄąâ€šĂ„â€¦d skÄąâ€šadni w `app.js` (uszkodzona funkcja `startHealthPolling`) powodowaÄąâ€š crash caÄąâ€šego JS przy parsowaniu; **zero** ÄąÄ˝Ă„â€¦daÄąâ€ž `GET /api/auth/me` w logach serwera. PrzywrÄ‚Ĺ‚cono `startHealthPolling`, watchdog 5 s na boot.
- **Entrypoint**: `ENTRYPOINT_VERSION` zsynchronizowany z `VERSION` (wczeÄąâ€şniej 1.3.92 vs 1.3.114 = mieszany obraz po czĂ„â„˘Äąâ€şciowym update).
- **Discovery UI**: defensywne `try/catch` Ă˘â‚¬â€ť stary backend bez pÄ‚Ĺ‚l discovery nie wywali bootu.
- **QNAP README**: sekcja o peÄąâ€šnym zastĂ„â€¦pieniu obrazu (usuÄąâ€ž kontener + pull `:1.3.115`), nie czĂ„â„˘Äąâ€şciowy update warstw.
- **Obraz**: `ghcr.io/lobrzut/netdash:1.3.115`.

## v1.3.114

- **Discovery bez klikania (QNAP)**: lokalny skan ukryty Ă˘â‚¬â€ť staÄąâ€šy pasek statusu Ă˘â‚¬ĹľDiscovery: ostatni import X min temu z homelab (N hostÄ‚Ĺ‚w)Ă˘â‚¬ĹĄ lub Ă˘â‚¬ĹľCzekam na agentaĂ˘â‚¬Â¦Ă˘â‚¬ĹĄ.
- **Agent domyÄąâ€şlnie co 10 min** (`INTERVAL=600`) Ă˘â‚¬â€ť wolno, ale automatycznie; peÄąâ€šny `/24` z `.201`.
- **Ustawienia Ă˘â€ â€™ Automatyczne discovery**: tylko status + jednorazowe polecenie install (schowane w `<details>`).
- **Env**: `NETDASH_DISCOVERY_MODE=remote`, `NETDASH_SCAN_DISABLED=true` w compose QNAP; `discovery_last_import_hosts` w API.
- **install.sh**: one-liner `curl | bash` dla homelab `.201`.
- **Obraz**: `ghcr.io/lobrzut/netdash:1.3.114`.

## v1.3.113

- **Compose QNAP**: usuniĂ„â„˘to `mem_limit`, `memswap_limit`, `cpus` ze wszystkich plikÄ‚Ĺ‚w Ă˘â‚¬â€ť limity RAM/CPU ustaw rĂ„â„˘cznie w Container Station Ă˘â€ â€™ Resource (512 MB, 50% CPU). Brak faÄąâ€šszywych ostrzeÄąÄ˝eÄąâ€ž IDE.
- **Obraz**: `ghcr.io/lobrzut/netdash:1.3.113`.

## v1.3.112

- **Remote discovery agent (NetAlertX SYNC pattern)**: `POST /api/discovery/import` Ă˘â‚¬â€ť merge hostÄ‚Ĺ‚w z agenta (IP/MAC/hostname, opcjonalne porty, mark offline).
- **Agent**: `scripts/netdash-agent.py` + `deploy/agent/` (Docker host network, arp-scan Ă˘â€ â€™ ip neigh Ă˘â€ â€™ ping).
- **Env**: `NETDASH_SCAN_DISABLED=true` Ă˘â‚¬â€ť wyÄąâ€šĂ„â€¦cza lokalny skan na dashboardzie (QNAP); baner + status ostatniego importu w UI.
- **Compose QNAP**: domyÄąâ€şlnie `NETDASH_SCAN_DISABLED=true` Ă˘â‚¬â€ť discovery z homelab agenta (.201).
- **Obraz**: `ghcr.io/lobrzut/netdash:1.3.112`.

## v1.3.111

- **Fix krytyczny QNAP Ă˘â‚¬â€ť /24 zabronione w safe mode**: `POST /api/scan` odrzuca CIDR szersze niÄąÄ˝ /28 (400). RAM limit kontenera nie chroni hosta przed przeciĂ„â€¦ÄąÄ˝eniem sieci/CPU.
- **Ultra-safe scan**: 2 rÄ‚Ĺ‚wnolegÄąâ€še sondy, 16 hostÄ‚Ĺ‚w, chunk 4, opÄ‚Ĺ‚ÄąĹźnienie 0,4 s, sekwencyjny skan portÄ‚Ĺ‚w, bez ARP w safe mode, 5 portÄ‚Ĺ‚w web + SSH.
- **Env**: `NETDASH_SCAN_SAFE_MAX_HOSTS`, `NETDASH_SCAN_CHUNK_SIZE`, `NETDASH_SCAN_BATCH_DELAY`, `NETDASH_SCAN_SAFE_BLOCK_WIDE`.
- **UI**: baner QNAP, blokada one-click na /24, confirm przed skanem, polling 6 s.
- **Compose QNAP**: `mem_limit: 512m`, `cpus: 0.5`, domyÄąâ€şlne `192.168.1.144/28`.
- **Obraz**: `ghcr.io/lobrzut/netdash:1.3.111`.

## v1.3.110

- **Fix krytyczny QNAP OOM**: bez limitu RAM skan `/24` moÄąÄ˝e crashowaĂ„â€ˇ caÄąâ€šy NAS. Compose QNAP: `mem_limit: 768m`, domyÄąâ€şlne CIDR `192.168.1.144/28`, ostrzeÄąÄ˝enia w README.
- **Safe mode agresywniejszy**: rÄ‚Ĺ‚wnolegÄąâ€šoÄąâ€şĂ„â€ˇ 4, batch 8, max 32 hosty, identify 3, timeout 240 s; `/24` Ă˘â€ â€™ max 2Ä‚â€” `/28` (kotwica DHCP ~.144); wymuszony `quick_scan`.
- **Backend**: health-check w tle wstrzymany podczas skanu; pominiĂ„â„˘cie ARP enrich po skanie w safe mode.
- **UI skanu**: polling 3 s + backoff (do 10 prÄ‚Ĺ‚b), `loadServices()` zamiast `loadDashboard()`, brak czerwonego banera poÄąâ€šĂ„â€¦czenia przy chwilowej utracie kontenera; health polling wstrzymany w trakcie skanu.
- **Obraz**: `ghcr.io/lobrzut/netdash:1.3.110`.

## v1.3.109

- **NUCLEAR Ă˘â‚¬â€ť jeden klik Ă˘â‚¬ĹľSkanuj sieĂ„â€ˇĂ˘â‚¬ĹĄ**: `#scan-btn` i `#empty-scan-btn` od razu woÄąâ€šajĂ„â€¦ `oneClickScan()` Ă˘â€ â€™ `POST /api/scan` (bez modala CIDR i bez confirm). CIDR: Ustawienia Ă˘â€ â€™ `scan_cidr_default` Ă˘â€ â€™ `NETDASH_SCAN_CIDR` (`env_scan_cidr`) Ă˘â€ â€™ `192.168.1.0/24`. Toast Ă˘â‚¬ĹľSkan uruchomiony: {cidr}Ă˘â‚¬ĹĄ, pasek postĂ„â„˘pu natychmiast.
- **Opcje skanuĂ˘â‚¬Â¦**: link otwiera zaawansowany modal (CIDR + peÄąâ€šny skan + opcjonalny confirm dla power userÄ‚Ĺ‚w).
- **Logi**: `POST /api/scan/ui-attempt` przy kaÄąÄ˝dej prÄ‚Ĺ‚bie ze UI (`ui-one-click` / `ui-advanced`); usuniĂ„â„˘ty workaround long-press.
- **Obraz**: `ghcr.io/lobrzut/netdash:1.3.109`.

## v1.3.108

- **Fix krytyczny Ă˘â‚¬â€ť POST /api/scan po Ă˘â‚¬ĹľKontynuuj skanĂ˘â‚¬ĹĄ**: `closeModal('scan-confirm-modal')` woÄąâ€šaÄąâ€š `pendingScanStart(false)` zanim promise siĂ„â„˘ rozwiĂ„â€¦zaÄąâ€š (wyÄąâ€şcig z handlerem OK / backdrop). Teraz `resolvePendingScanStart(true)` + `closeModal(..., { scanConfirmOk: true })` Ă˘â‚¬â€ť confirm nie jest anulowany przy zamykaniu po akceptacji.
- **Debug**: `console.log('[NetDash] scan: Ă˘â‚¬Â¦')` na kaÄąÄ˝dym kroku (klik przycisku, modal CIDR, confirm, POST).
- **Fallback**: przytrzymaj ~0,8 s Ă˘â‚¬ĹľSkanuj sieĂ„â€ˇĂ˘â‚¬ĹĄ na Serwisach Ă˘â‚¬â€ť bezpoÄąâ€şredni POST z domyÄąâ€şlnym CIDR (pomija confirm).
- **UI**: `z-index` na `.modal-content` Ă˘â‚¬â€ť klik w przyciski modala nie trafia w backdrop.
- **Obraz**: `ghcr.io/lobrzut/netdash:1.3.108`.

## v1.3.107

- **Fix krytyczny QNAP Ă˘â‚¬â€ť zÄąâ€šy CIDR 172.x**: modal skanu domyÄąâ€şlnie wybieraÄąâ€š sieĂ„â€ˇ Docker (172.16Ă˘â‚¬â€ś172.31), wiĂ„â„˘c POST `/api/scan` szedÄąâ€š z `172.x.0/24` zamiast `NETDASH_SCAN_CIDR` (192.168.1.0/24) Ă˘â‚¬â€ť skan Ă˘â‚¬Ĺľnic nie znajdowaÄąâ€šĂ˘â‚¬ĹĄ. UI preferuje teraz `env_scan_cidr`; serwer ignoruje Docker-internal CIDR gdy ustawiony `NETDASH_SCAN_CIDR`.
- **Szybki skan (quick_scan)**: na Docker bridge / `scan_safe_mode` Ă˘â‚¬â€ť gateway, ARP, znane hosty z bazy, pierwsze /32 adresy; mniejsze obciĂ„â€¦ÄąÄ˝enie NAS.
- **UI skanu**: toast przy starcie i po sukcesie; natychmiastowy polling postĂ„â„˘pu; wznowienie skanu po F5; anulowanie confirm wraca do modala CIDR.
- **Logi serwera**: `Scan N started/completed`, odrzucenia 409/400, Äąâ€şmierĂ„â€ˇ taska w tle.
- **Obraz**: `ghcr.io/lobrzut/netdash:1.3.107`.

## v1.3.106

- **Fix sesji F5 (QNAP) Ă˘â‚¬â€ť root cause**: serwer braÄąâ€š **pierwsze** cookie nawet gdy byÄąâ€šo niewaÄąÄ˝ne, ignorujĂ„â€¦c poprawny Bearer z `localStorage`; `get_current_user` prÄ‚Ĺ‚buje teraz Bearer Ă˘â€ â€™ cookie Ă˘â€ â€™ legacy, aÄąÄ˝ znajdzie waÄąÄ˝ny JWT.
- **Boot**: `restoreSession()` od razu wysyÄąâ€ša Bearer z `localStorage` (razem z cookie), nie czyÄąâ€şci tokena przy timeout/5xx Ă˘â‚¬â€ť tylko przy 401; ponowienie po timeout.
- **Skan Ă˘â‚¬â€ť jeden modal naraz**: modal CIDR zamyka siĂ„â„˘ przed potwierdzeniem; anulowanie confirm wraca do wyboru CIDR (koniec Ă˘â‚¬ĹľkrĂ„â„˘ceniaĂ˘â‚¬ĹĄ miĂ„â„˘dzy oknami).
- **Obraz**: `ghcr.io/lobrzut/netdash:1.3.106`.

## v1.3.105

- **Fix krytyczny Ă˘â‚¬â€ť modal Ă˘â‚¬ĹľKontynuuj skanĂ˘â‚¬ĹĄ**: klikniĂ„â„˘cie potwierdzenia wywoÄąâ€šywaÄąâ€šo `closeModal` przed `pendingScanStart(true)`, wiĂ„â„˘c skan byÄąâ€š anulowany i **POST /api/scan nigdy nie szedÄąâ€š** (regresja z v1.3.104 po zamianie `confirm()` na modal).
- **BÄąâ€šĂ„â„˘dy skanu po polsku**: toast przy wygaÄąâ€şniĂ„â„˘ciu sesji (401), odrzuceniu przez serwer i utracie poÄąâ€šĂ„â€¦czenia podczas pollingu postĂ„â„˘pu.
- **Obraz**: `ghcr.io/lobrzut/netdash:1.3.105`.

## v1.3.104

- **Skan sieci Ă˘â‚¬â€ť wybÄ‚Ĺ‚r CIDR**: przycisk Ă˘â‚¬ĹľSkanuj sieĂ„â€ˇĂ˘â‚¬ĹĄ otwiera modal z listĂ„â€¦ wykrytych sieci (`/api/network` Ă˘â€ â€™ `detected_cidrs`: /24, /28, NETDASH_SCAN_CIDR, ustawienia), podglĂ„â€¦dem wyboru i opcjĂ„â€¦ Ă˘â‚¬ĹľWÄąâ€šasny wpisĂ˘â‚¬ĹĄ.
- **Potwierdzenie skanu**: zamiast natywnego `confirm()` Ă˘â‚¬â€ť modal w aplikacji z checkboxem Ă˘â‚¬ĹľNie pokazuj ponownieĂ˘â‚¬ĹĄ (`localStorage: netdash_scan_confirm_skip`).
- **Baner trybu bezpiecznego**: przycisk Ă˘â‚¬ĹľUkryjĂ˘â‚¬ĹĄ (`localStorage: netdash_scan_safe_banner_dismiss`) Ă˘â‚¬â€ť nie pokazuje siĂ„â„˘ przy kaÄąÄ˝dym wejÄąâ€şciu na Serwisy.
- **Ustawienia Ă˘â€ â€™ Skanowanie**: domyÄąâ€şlne CIDR z pÄ‚Ĺ‚l ustawieÄąâ€ž jest domyÄąâ€şlnym wyborem w modalu skanu.
- **Obraz**: `ghcr.io/lobrzut/netdash:1.3.104`.

## v1.3.103

- **Fix krytyczny UI (`scan_safe_mode`)**: Pulpit i Serwisy nie crashujĂ„â€¦ gdy `/api/network` zawiedzie Ă˘â‚¬â€ť domyÄąâ€şlny profil `scan_safe_mode=true`, bezpieczne wartoÄąâ€şci sieci; koniec czerwonego banera Ă˘â‚¬ĹľCannot read properties of nullĂ˘â‚¬ĹĄ.
- **Fix dialogu Ă˘â‚¬ĹľZaloguj siĂ„â„˘Ă˘â‚¬ĹĄ (QNAP :5001)**: przeglĂ„â€¦darka nie Äąâ€šaduje juÄąÄ˝ faviconÄ‚Ĺ‚w z adresÄ‚Ĺ‚w LAN / login-gated (`<img src>` na karcie serwisu). Niebezpieczne `icon_url` sĂ„â€¦ zastĂ„â„˘powane ikonĂ„â€¦ marki (CDN) lub presetem; health check HTTP pomija serwisy z `has_login` (tylko ping).
- **Compose (QNAP)**: czysty minimalny YAML Ă˘â‚¬â€ť bez `version`, `mem_limit`, `deploy.resources` ani `cpus` (ÄąÄ˝adnych faÄąâ€šszywych ostrzeÄąÄ˝eÄąâ€ž IDE/Schema Store). Limit RAM 512 MB: komentarz w compose + **Container Station Ă˘â€ â€™ Resource Ă˘â€ â€™ Memory limit** (patrz README).
- **README (QNAP)**: sekcja limitu RAM tylko przez UI CS; wyjaÄąâ€şnienie ÄąÄ˝Ä‚Ĺ‚Äąâ€štych trÄ‚Ĺ‚jkĂ„â€¦tÄ‚Ĺ‚w IDE vs QNAP.
- **Obraz**: `ghcr.io/lobrzut/netdash:1.3.103`.

## v1.3.102

- **Compose (QNAP)**: wÄąâ€šasny schemat IDE `deploy/qnap/qnap-compose.schema.json` (Compose 2.4: `mem_limit` bez ostrzeÄąÄ˝eÄąâ€ž yaml-language-server). Modeline + `.vscode/settings.json` uÄąÄ˝ywajĂ„â€¦ **URL GitHub** (nie `./` ani Äąâ€şcieÄąÄ˝ki wzglĂ„â„˘dem repo). `yaml.schemaStore.enable: false` + globy absolutne (`C:/opt/netdash/...`) Ă˘â‚¬â€ť inaczej przy workspace `brain-client` Schema Store narzuca `docker-compose.json` (v3+, bez `mem_limit`).
- **Obraz**: `ghcr.io/lobrzut/netdash:1.3.102`.

## v1.3.101

- **Compose (QNAP)**: usuniĂ„â„˘to `cpus` (schemastore `docker-compose.json` nadal flaguje to pole mimo Compose 2.4). Zostaje `mem_limit: 512m`; opcjonalny limit CPU rĂ„â„˘cznie w Container Station UI.
- **Obraz**: `ghcr.io/lobrzut/netdash:1.3.101`.

## v1.3.100

- **Compose (QNAP)**: usuniĂ„â„˘to `cpu_quota`/`cpu_period` (faÄąâ€šszywe ostrzeÄąÄ˝enia yaml-language-server przy schemastore). Zamiast tego `cpus: 1.0` + `mem_limit: 512m` (Compose 2.4, schemat `json.schemastore.org/docker-compose.json`).
- **Obraz**: `ghcr.io/lobrzut/netdash:1.3.100`.

## v1.3.99

- **Compose (QNAP)**: schemat IDE zmieniony z compose-spec na `json.schemastore.org/docker-compose.json` (Compose 2.4: `mem_limit`, `cpu_quota`, `cpu_period` bez ostrzeÄąÄ˝eÄąâ€ž yaml-language-server).
- **README**: sekcja Acknowledgements (Homer, GPTWOL).
- **Obraz**: `ghcr.io/lobrzut/netdash:1.3.99`.

## v1.3.98

- **Compose (QNAP)**: `yaml-language-server` schema override + `.vscode/settings.json` Ă˘â‚¬â€ť walidacja wzglĂ„â„˘dem compose-spec (pola Compose 2.4). `cpus` zastĂ„â€¦pione przez `cpu_quota`/`cpu_period` (= 1 rdzeÄąâ€ž) Ă˘â‚¬â€ť zero faÄąâ€šszywych ostrzeÄąÄ˝eÄąâ€ž IDE; limity nadal dziaÄąâ€šajĂ„â€¦ na QNAP CS.
- **Obraz**: `ghcr.io/lobrzut/netdash:1.3.98`.

## v1.3.97

- **Compose**: QNAP Ă˘â‚¬â€ť `version: "2.4"` + `mem_limit`/`cpus` (bez `deploy`; CS ignoruje deploy, schemat 2.4 bez ostrzeÄąÄ˝eÄąâ€ž IDE). PozostaÄąâ€še compose Ă˘â‚¬â€ť tylko `deploy.resources.limits` (Compose v2+).
- **Obraz**: `ghcr.io/lobrzut/netdash:1.3.97`.

## v1.3.96

- **Compose**: poprawka limitÄ‚Ĺ‚w zasobÄ‚Ĺ‚w Ă˘â‚¬â€ť `cpus: 1.0` (niezgodne ze schematem Compose v3) zastĂ„â€¦pione przez `cpu_count: 1` + `deploy.resources.limits` (Docker Compose v2/v3); `mem_limit: 512m` zostaje dla QNAP Container Station / Dockge / docker run.
- **Obraz**: `ghcr.io/lobrzut/netdash:1.3.96`.

## v1.3.95

- **Filozofia projektu**: sÄąâ€šaby sprzĂ„â„˘t homelab (RPi, stary PC, N100, NAS, QNAP) Ă˘â‚¬â€ť nie tylko QNAP. Safe mode i limity zasobÄ‚Ĺ‚w sĂ„â€¦ domyÄąâ€şlne **w caÄąâ€šym projekcie**.
- **Kod**: komunikaty skanu/health bez hardcoded Ă˘â‚¬ĹľQNAPĂ˘â‚¬ĹĄ w logice safe mode; ogÄ‚Ĺ‚lne Ă˘â‚¬ĹľsÄąâ€šaby sprzĂ„â„˘tĂ˘â‚¬ĹĄ / Ă˘â‚¬ĹľDocker bridgeĂ˘â‚¬ĹĄ.
- **UI (i18n)**: ostrzeÄąÄ˝enia profilu skanu Ă˘â‚¬â€ť Ă˘â‚¬ĹľsÄąâ€šaby serwerĂ˘â‚¬ĹĄ zamiast QNAP-first; docker scan hint uniwersalny.
- **Dokumentacja**: README i DEPLOYMENT Ă˘â‚¬â€ť homelab weak hardware jako domyÄąâ€şlne zaÄąâ€šoÄąÄ˝enie projektu.
- **Obraz**: `ghcr.io/lobrzut/netdash:1.3.95`.

## v1.3.94

- **SÄąâ€šaby sprzĂ„â„˘t (domyÄąâ€şlnie)**: `NETDASH_SCAN_SAFE_MODE=true` w kodzie i we wszystkich compose Ă˘â‚¬â€ť nie tylko QNAP. `mem_limit: 512m`, `cpus: 1.0` w docker-simple, root compose, Dockge, dev.
- **Health**: `/api/health` zwraca `resource_profile` (`safe` / `normal`); mniejsza rÄ‚Ĺ‚wnolegÄąâ€šoÄąâ€şĂ„â€ˇ health checkÄ‚Ĺ‚w w safe mode; opÄ‚Ĺ‚ÄąĹźniony pierwszy health check przy starcie (30 s).
- **UI**: Ustawienia Ă˘â€ â€™ Skanowanie Ă˘â‚¬â€ť profil (Bezpieczny / Normalny / Agresywny), ostrzeÄąÄ˝enia; peÄąâ€šny skan wymaga potwierdzenia.
- **Dokumentacja**: README i DEPLOYMENT Ă˘â‚¬â€ť sekcja Ă˘â‚¬ĹľSÄąâ€šaby sprzĂ„â„˘tĂ˘â‚¬ĹĄ (CIDR /28, env vars).
- **Obraz**: `ghcr.io/lobrzut/netdash:1.3.94`.

## v1.3.93

- **Fix krytyczny QNAP (crash NAS przy skanie)**: `NETDASH_SCAN_SAFE_MODE=true` domyÄąâ€şlnie w compose QNAP Ă˘â‚¬â€ť niska rÄ‚Ĺ‚wnolegÄąâ€šoÄąâ€şĂ„â€ˇ (8), krÄ‚Ĺ‚tka lista portÄ‚Ĺ‚w, opÄ‚Ĺ‚ÄąĹźnienia miĂ„â„˘dzy partiami, limit hostÄ‚Ĺ‚w (64), twardy timeout (300 s). PeÄąâ€šny skan zablokowany w safe mode.
- **Skan**: batch processing zamiast 254 rÄ‚Ĺ‚wnolegÄąâ€šych zadaÄąâ€ž TCP; `mem_limit: 512m` i `cpus: 1.0` w compose QNAP.
- **UI**: potwierdzenie przed skanem na sÄąâ€šabym sprzĂ„â„˘cie; baner trybu bezpiecznego; Ă˘â‚¬ĹľFailed to fetchĂ˘â‚¬ĹĄ Ă˘â€ â€™ czytelny komunikat po polsku.
- **API**: `/api/health` i `/api/network` zwracajĂ„â€¦ `scan_safe_mode`.
- **Obraz**: `ghcr.io/lobrzut/netdash:1.3.93`.

## v1.3.92

- **Skan (UI)**: usuniĂ„â„˘ty przycisk Ă˘â‚¬ĹľSkanuj sieĂ„â€ˇĂ˘â‚¬ĹĄ z Pulpitu (`#scan-btn-home`); skan jednym klikniĂ„â„˘ciem tylko na zakÄąâ€šadce Serwisy (`#scan-btn`, `#empty-scan-btn`) Ă˘â‚¬â€ť `POST /api/scan` + pasek postĂ„â„˘pu.
- **Fix**: nagÄąâ€šÄ‚Ĺ‚wek SerwisÄ‚Ĺ‚w otwieraÄąâ€š modal zamiast startowaĂ„â€ˇ skan (regresja v1.3.91).
- **Obraz**: `ghcr.io/lobrzut/netdash:1.3.92`.

## v1.3.91

- **Fix sesji QNAP (F5) Ă˘â‚¬â€ť root cause**: v1.3.89+ nie czytaÄąâ€š tokena z localStorage przy starcie, a cookie `netdash_session` czasem nie wraca na HTTP Ă˘â‚¬â€ť boot teraz prÄ‚Ĺ‚buje cookie, potem Bearer z localStorage; `/api/auth/me` odÄąâ€şwieÄąÄ˝a cookie przy sukcesie.
- **Boot rÄ‚Ĺ‚wnolegÄąâ€šy**: `/api/health` i `/api/auth/me` rÄ‚Ĺ‚wnolegle Ă˘â‚¬â€ť szybsze Äąâ€šadowanie, zawsze widaĂ„â€ˇ auth/me w logach.
- **Cache JS**: `Cache-Control: no-cache` na `app.js`, `i18n.js`, `style.css` Ă˘â‚¬â€ť koniec starego JS po aktualizacji obrazu.
- **Skan**: przyciski Pulpit/pusty stan uruchamiajĂ„â€¦ `POST /api/scan` od razu (bez drugiego klikniĂ„â„˘cia w modalu); stare joby `running` po restarcie oznaczane jako failed.
- **QNAP compose**: `NETDASH_COOKIE_SECURE: "false"` jawnie; obraz `1.3.91`.
- **Logi**: `GET /api/auth/me OK user=Ă˘â‚¬Â¦ cookie=Ă˘â‚¬Â¦ bearer=Ă˘â‚¬Â¦` przy kaÄąÄ˝dym udanym odÄąâ€şwieÄąÄ˝eniu sesji.

## v1.3.90

- **Fix Ă˘â‚¬ĹľÄąÂadowanie sesjiĂ˘â‚¬Â¦Ă˘â‚¬ĹĄ (QNAP)**: `GET /api/auth/me` ma timeout 5 s Ă˘â‚¬â€ť po bÄąâ€šĂ„â„˘dzie/timeout natychmiast ekran logowania (bez wiecznego spinnera).
- **Boot**: `try/finally` gwarantuje wyjÄąâ€şcie z `boot-view` Ă˘â€ â€™ zawsze logowanie lub dashboard; timeout takÄąÄ˝e na `/api/health`.
- **Logi**: klient `console.warn` przy timeout/bÄąâ€šĂ„â„˘dzie sesji; serwer loguje `GET /api/auth/me: brak cookie sesji` przy 401 bez cookie.
- **Obraz**: `ghcr.io/lobrzut/netdash:1.3.90`.

## v1.3.89

- **Fix sesji QNAP (F5)**: ekran Ă˘â‚¬ĹľÄąÂadowanie sesjiĂ˘â‚¬Â¦Ă˘â‚¬ĹĄ do czasu `GET /api/auth/me`; brak odczytu starego tokena z localStorage przy starcie; przy 401 retry cookie-only i `restoreSession()` zamiast natychmiastowego wylogowania.
- **Serwer**: log `Session cookie set for user X` przy logowaniu i `/api/auth/me`.
- **QNAP compose domyÄąâ€şlnie bridge**: `docker-compose.full.yml` i `docker-compose.yml` uÄąÄ˝ywajĂ„â€¦ `ports: 18787:18787` zamiast `network_mode: host` (host nie skanuje LAN na QNAP).
- **Test skanu**: przycisk **Ustawienia Ă˘â€ â€™ Skanowanie Ă˘â€ â€™ Test skanu sieci** + `POST /api/network/scan-test` (ping, CIDR, docker bridge) Ă˘â‚¬â€ť wpis w logach kontenera.
- **Obraz**: `ghcr.io/lobrzut/netdash:1.3.89`.

## v1.3.88

- **QNAP entrypoint (impossible to miss)**: banner `NetDash entrypoint v1.3.88`, `LISTEN_PORT=18787 (8787 blocked)` w pierwszych liniach logu Ă˘â‚¬â€ť Äąâ€šatwa diagnoza starego obrazu GHCR bez entrypoint.
- **QNAP compose.full.yml**: obraz przypiĂ„â„˘ty `ghcr.io/lobrzut/netdash:1.3.87` (nie `:latest` Ă˘â‚¬â€ť unika cache CS ze starym 8787).

## v1.3.87

- **Fix skanu QNAP (UI)**: przycisk Ă˘â‚¬ĹľSkanuj sieĂ„â€ˇĂ˘â‚¬ĹĄ widoczny na Pulpicie i w pustym stanie SerwisÄ‚Ĺ‚w; delegacja zdarzeÄąâ€ž `#scan-start` Ă˘â‚¬â€ť zawsze wysyÄąâ€ša `POST /api/scan`; czerwony baner `#scan-error` gdy start skanu siĂ„â„˘ nie powiedzie.
- **Sesja**: `GET /api/auth/me` zwraca `access_token` i odÄąâ€şwieÄąÄ˝a cookie Ă˘â‚¬â€ť po F5 brak ponownego `POST /api/auth/login`.
- **Serwer**: log `POST /api/scan body=...` przy kaÄąÄ˝dym starcie skanu; `resolve_scan_cidrs` preferuje `NETDASH_SCAN_CIDR` gdy brak CIDR w UI.
- **QNAP compose**: obraz `1.3.87`.

## v1.3.86

- **Fix sesji QNAP (odÄąâ€şwieÄąÄ˝anie)**: cookie `netdash_session` (`HttpOnly`, `Path=/`, `SameSite=Lax`, `Secure=false` na HTTP); nowy endpoint `GET /api/auth/me` Ă˘â‚¬â€ť frontend sprawdza sesjĂ„â„˘ przed ekranem logowania (bez ponownego `POST /api/auth/login` po F5).
- **Migracja cookie**: odczyt starego `netdash_token` do czasu ponownego logowania; `NETDASH_COOKIE_SECURE=false` domyÄąâ€şlnie (QNAP HTTP).
- **Skan sieci**: log serwera `Network scan started CIDR=...`; komunikat w `error_message` gdy ping ICMP niedostĂ„â„˘pny (QNAP).

## v1.3.85

- **QNAP skan sieci (fix)**: gdy ICMP ping jest zablokowany (typowe na QNAP Docker), skan automatycznie przechodzi na **TCP discovery** caÄąâ€šej podsieci CIDR (porty 80, 443, 22, 445, 8080, Ă˘â‚¬Â¦) zamiast zwracaĂ„â€ˇ pusty wynik.
- **API skanu**: `error_message` w `ScanJob` / `/api/scan/{id}` Ă˘â‚¬â€ť czytelne bÄąâ€šĂ„â„˘dy (brak CIDR, brak NET_RAW, timeout); walidacja przed startem gdy kontener w sieci Docker bez CIDR.
- **`/api/network`**: pole `ping_available` Ă˘â‚¬â€ť UI wie, czy ping dziaÄąâ€ša.
- **Ustawienia Ă˘â€ â€™ Skanowanie**: `scan_cidr_default` wypeÄąâ€šniane z `NETDASH_SCAN_CIDR` przy pierwszym starcie.
- **UI Serwisy**: baner gdy ostatni skan pusty; toast z konkretnym komunikatem; CIDR wstĂ„â„˘pnie w modalu skanu.
- **QNAP compose**: obraz `1.3.85`; `docker-compose.bridge.yml` oznaczony jako zalecany gdy host mode nie skanuje LAN.

## v1.3.84

- **QNAP port nuclear fix**: aplikacja **nigdy** nie binduje **8787** Ă˘â‚¬â€ť `resolve_listen_port()` czyta wyÄąâ€šĂ„â€¦cznie `NETDASH_LISTEN_PORT`; `NETDASH_PORT` jest caÄąâ€škowicie ignorowany. `entrypoint.sh` zawsze ustawia `NETDASH_LISTEN_PORT=18787` i `unset NETDASH_PORT`. Log startowy: `LISTEN_PORT=18787 (8787 blocked)`.
- **compose.full.yml**: obraz przypiĂ„â„˘ty `ghcr.io/lobrzut/netdash:1.3.84` (do czasu Pull przez uÄąÄ˝ytkownika).

## v1.3.83

- **Portal Ă˘â‚¬â€ť aktualizacje (fix QNAP)**: przycisk Ă˘â‚¬ĹľAktualizuj terazĂ˘â‚¬ĹĄ zawsze widoczny gdy jest nowa wersja; bez docker.sock otwiera modal z instrukcjĂ„â€¦ Watchtower / Pull w Container Station i Ă˘â‚¬ĹľSprawdÄąĹź ponownieĂ˘â‚¬ĹĄ (polling GitHub).
- **Modal postĂ„â„˘pu**: potwierdzenie bez `confirm()`, overlay Ă˘â‚¬ĹľAktualizacja w tokuĂ˘â‚¬Â¦Ă˘â‚¬ĹĄ, kroki pull/restart, polling `/api/health` co 2,5 s do wykrycia nowej wersji; blokada double-click i zamkniĂ„â„˘cia podczas aktualizacji.
- **API**: czytelniejszy komunikat 503 gdy brak docker.sock; i18n pl/en/de/uk dla nowych stringÄ‚Ĺ‚w.

## v1.3.82

- **QNAP auto-update (fix)**: `docker-compose.full.yml` uÄąÄ˝ywa obrazu `:latest` zamiast przypiĂ„â„˘tego semver Ă˘â‚¬â€ť Watchtower moÄąÄ˝e pobieraĂ„â€ˇ nowe wersje. LiteraÄąâ€šy env Watchtower (QNAP CS ignoruje `${VAR:-default}`), `WATCHTOWER_INCLUDE_STOPPED=true`.
- **Portal Ă˘â‚¬â€ť O projekcie**: poprawiony tekst o Watchtower (bez mylĂ„â€¦cego Ă˘â‚¬Ĺľprofil auto-updateĂ˘â‚¬ĹĄ); komunikat gdy nowsza wersja jest na GitHub, ale Ă˘â‚¬ĹľAktualizuj terazĂ˘â‚¬ĹĄ niedostĂ„â„˘pne (brak docker.sock na QNAP).
- **Dokumentacja**: sekcja rozwiĂ„â€¦zywania problemÄ‚Ĺ‚w auto-update w `deploy/qnap/README.md` i `docs/QNAP.md`.

## v1.3.81

- **Fix sesji QNAP (odÄąâ€şwieÄąÄ˝anie strony)**: stabilny `NETDASH_SECRET_KEY` z `/app/data/.secret` (entrypoint zawsze preferuje plik na wolumenie; Python teÄąÄ˝ Äąâ€šaduje `.secret`). Ciasteczko sesji `HttpOnly` z `Secure=false` na HTTP, `SameSite=Lax`, waÄąÄ˝noÄąâ€şĂ„â€ˇ 7 dni; `/api/auth/logout` czyÄąâ€şci cookie.
- **Health**: `/api/health` zwraca `secret_key_stable: true` gdy klucz wczytany z pliku `.secret`.
- **QNAP skan sieci**: compose ma twardy `NETDASH_SCAN_CIDR: "192.168.1.0/24"` (CS ignoruje `${VAR:-default}`); obraz `1.3.81`.
- **QNAP bridge compose**: `deploy/qnap/docker-compose.bridge.yml` Ă˘â‚¬â€ť tryb bridge + port `18787:18787` gdy `network_mode: host` nie skanuje LAN.
- **UI**: baner ostrzeÄąÄ˝enia na zakÄąâ€šadce Serwisy gdy kontener w sieci Docker bez skonfigurowanego CIDR.
- **Dokumentacja QNAP**: rozszerzona sekcja troubleshooting skanu sieci i sesji (PL).

## v1.3.80

- **Fix QNAP login (definitive)**: `_sync_admin_password_from_env` nie wymaga juÄąÄ˝ obecnoÄąâ€şci `NETDASH_DEFAULT_ADMIN_PASSWORD` w `os.environ` Ă˘â‚¬â€ť uÄąÄ˝ywa wartoÄąâ€şci z Settings (domyÄąâ€şlnie `changeme`). Puste stringi z Container Station sĂ„â€¦ normalizowane do domyÄąâ€şlnych.
- **Entrypoint**: auto-generacja `NETDASH_SECRET_KEY` do `/app/data/.secret` gdy brak w env (homelab bez rĂ„â„˘cznej konfiguracji CS).
- **QNAP compose**: twarde literaÄąâ€šy `admin` / `changeme` / `sync=true` (CS ignoruje `${VAR:-default}`); obraz `1.3.80`.
- **Health**: `/api/health` zwraca `admin_ready`, `secret_key_configured`.
- **Login**: porÄ‚Ĺ‚wnanie nazwy uÄąÄ˝ytkownika bez rozrÄ‚Ĺ‚ÄąÄ˝niania wielkoÄąâ€şci liter.
- **Startup log**: `Admin bootstrap: ... admin_ready=true/false`.

## v1.3.79

- **Post-deploy login (homelab)**: przy starcie kontenera, gdy `NETDASH_DEFAULT_ADMIN_PASSWORD` jest w env i `NETDASH_SYNC_ADMIN_PASSWORD=true` (domyÄąâ€şlnie), aplikacja tworzy uÄąÄ˝ytkownika admin (jeÄąâ€şli brak) i **synchronizuje hash hasÄąâ€ša** z env Ă˘â‚¬â€ť dziaÄąâ€ša `admin`/`changeme` po kaÄąÄ˝dym deployu, takÄąÄ˝e ze starym wolumenem SQLite.
- **Compose**: `NETDASH_DEFAULT_ADMIN_PASSWORD:-changeme`, `NETDASH_SYNC_ADMIN_PASSWORD:-true` w QNAP, docker-simple i gÄąâ€šÄ‚Ĺ‚wnym compose; obraz QNAP `1.3.79`.
- **Dokumentacja QNAP**: sync vs rĂ„â„˘czna zmiana hasÄąâ€ša; `NETDASH_SYNC_ADMIN_PASSWORD=false` po ustawieniu wÄąâ€šasnego hasÄąâ€ša.

## v1.3.78

- **Reset hasÄąâ€ša admina (QNAP / homelab)**: `NETDASH_RESET_ADMIN_PASSWORD` Ă˘â‚¬â€ť jednorazowy reset przy starcie (bcrypt, log ostrzeÄąÄ˝enia; usuÄąâ€ž zmiennĂ„â€¦ po zalogowaniu). Skrypt `scripts/reset-admin-password.py` w obrazie Docker (`docker exec`) lub offline na `netdash.db`.
- **QNAP README**: sekcja Ă˘â‚¬ĹľNie mogĂ„â„˘ siĂ„â„˘ zalogowaĂ„â€ˇĂ˘â‚¬ĹĄ Ă˘â‚¬â€ť File Station, stara baza, `admin`/`changeme` tylko przy pustej DB.

## v1.3.77

- **Port QNAP fix (definitive)**: aplikacja nasÄąâ€šuchuje wyÄąâ€šĂ„â€¦cznie na `NETDASH_LISTEN_PORT` (domyÄąâ€şlnie **18787**). Stare `NETDASH_PORT=8787` z Container Station jest **ignorowane** (log ostrzeÄąÄ˝enia) i **usuwane** w `entrypoint.sh` przed startem Ă˘â‚¬â€ť koniec crash loop z Readarr.
- **QNAP compose**: obraz przypiĂ„â„˘ty do `ghcr.io/lobrzut/netdash:1.3.77` (nie `:latest` Ă˘â‚¬â€ť unika cache CS).
- **Wszystkie compose**: `NETDASH_LISTEN_PORT: "18787"` na staÄąâ€še (bez `${NETDASH_PORT:-Ă˘â‚¬Â¦}`).
- **Dockerfile**: `ENV NETDASH_LISTEN_PORT=18787`, `entrypoint.sh`, healthcheck na 18787.

## v1.3.76

- **QNAP compose**: `NETDASH_PORT` ustawiony na staÄąâ€še na **18787** w `deploy/qnap/docker-compose.yml` i `docker-compose.full.yml` Ă˘â‚¬â€ť stara zmienna `NETDASH_PORT=8787` w Container Station nie nadpisuje juÄąÄ˝ portu przez `${NETDASH_PORT:-18787}`.
- **Dokumentacja QNAP**: rozszerzona sekcja Ă˘â‚¬ĹľwciĂ„â€¦ÄąÄ˝ nasÄąâ€šuchuje na 8787Ă˘â‚¬ĹĄ Ă˘â‚¬â€ť kroki CS bez SSH (usuÄąâ€ž aplikacjĂ„â„˘, pull, ponowny import).

## v1.3.75

- **DomyÄąâ€şlne logowanie `admin` / `changeme`** Ă˘â‚¬â€ť jak w innych homelab stackach; dotyczy tylko **nowych** instalacji bez uÄąÄ˝ytkownikÄ‚Ĺ‚w w bazie. IstniejĂ„â€¦ce hasÄąâ€ša bez zmian.
- **Bootstrap** (`init_db`): konto admin tworzone tylko gdy baza nie ma ÄąÄ˝adnych uÄąÄ˝ytkownikÄ‚Ĺ‚w.
- **install.sh / install.ps1** (docker-simple i deploy): bez pytania o hasÄąâ€šo Ă˘â‚¬â€ť `changeme` w `.env` lub pomijanie gdy `.env` juÄąÄ˝ istnieje; generowany tylko `NETDASH_SECRET_KEY`.
- **Dokumentacja**: przypomnienie o **obowiĂ„â€¦zkowej zmianie hasÄąâ€ša** po pierwszym logowaniu (Ustawienia Ă˘â€ â€™ HasÄąâ€šo).

## v1.3.74

- **Fix**: skÄąâ€šadnia `HEALTHCHECK` w Dockerfile (`CMD-SHELL` Ă˘â€ â€™ `CMD sh -c`) Ă˘â‚¬â€ť blokowaÄąâ€ša build obrazu GHCR.

## v1.3.73

- **DomyÄąâ€şlny port 18787** (`NETDASH_PORT`): unika kolizji z **Readarr (8787)** i typowymi portami homelab (80, 443, 3000, 5000, 8080, 8096, 8989Ă˘â‚¬Â¦). Wszystkie compose, healthchecki i `run.py` respektujĂ„â€¦ zmiennĂ„â€¦ Äąâ€şrodowiskowĂ„â€¦.
- **Migracja z 8787**: istniejĂ„â€¦ce instalacje Ă˘â‚¬â€ť dodaj `NETDASH_PORT=8787` w `.env` do czasu zmiany zakÄąâ€šadki, albo usuÄąâ€ž i przejdÄąĹź na `http://<host>:18787`.
- **Skaner LAN**: rozpoznaje NetDash na porcie 18787 (8787 oznaczony jako legacy).

## v1.3.72

- **Auto-aktualizacja (QNAP / Docker)**: GitHub Actions publikuje obraz na `ghcr.io/lobrzut/netdash` przy tagu `v*`. Compose: `image` + opcjonalny profil **Watchtower** (`docker compose --profile auto-update up -d`). Etykieta `watchtower.enable` tylko na NetDash Ă˘â‚¬â€ť brak auto-update bez Äąâ€şwiadomego wÄąâ€šĂ„â€¦czenia.
- **Ustawienia Ă˘â€ â€™ O projekcie Ă˘â‚¬â€ť SprawdÄąĹź aktualizacje**: `GET /api/updates/check` (GitHub Releases API), status wersji, link do changelogu. Opcjonalnie **Aktualizuj teraz** (`POST /api/updates/apply`) przy `NETDASH_UPDATE_APPLY_ENABLED` + montowany `docker.sock` (dokumentacja ryzyk w `docs/QNAP.md`).
- **Dokumentacja**: `docs/QNAP.md` (Container Station, GHCR, Watchtower, PL), rozszerzony `DEPLOYMENT.md`.

## v1.3.71

- **Pulpit Ă˘â‚¬â€ť fix nachodzenia Ă˘Ââ€¦ na ikonĂ„â„˘**: w ukÄąâ€šadach Kompaktowy (duÄąÄ˝y) i ÄąĹˇredni pasek akcji jest z powrotem w prawym gÄ‚Ĺ‚rnym rogu (Ă˘Ââ€¦ po lewej w grupie przyciskÄ‚Ĺ‚w, edycja/notatki/WoL po prawej) Ă˘â‚¬â€ť bez nachodzenia na ikonĂ„â„˘ serwisu. Kompaktowy bez zmian (pasek rozwija siĂ„â„˘ na dole).

## v1.3.70

- **Ustawienia Ă˘â€ â€™ Pulpit Ă˘â‚¬â€ť fix listy motywÄ‚Ĺ‚w**: przeglĂ„â€¦darka mogÄąâ€ša trzymaĂ„â€ˇ w cache stary `index.html` (bez `?v=`), przez co w selectcie widaĂ„â€ˇ byÄąâ€šo tylko jednĂ„â€¦ opcjĂ„â„˘ (np. Ă˘â‚¬ĹľKompaktowy (duÄąÄ˝y)Ă˘â‚¬ĹĄ) mimo ÄąÄ˝e serwer serwuje 5 ukÄąâ€šadÄ‚Ĺ‚w. `syncDashboardLayoutSelect()` odbudowuje opcje z JS przy starcie i otwarciu ustawieÄąâ€ž; `Cache-Control: no-cache` na `/` + meta tag.

## v1.3.69

- **Pulpit Ă˘â‚¬â€ť ukÄąâ€šad Kompaktowy (mniejszy)**: zmniejszone kafelki (~178px Ä‚â€” min. 48px, ikona 32px) z rozwijanym paskiem akcji na dole przy hover Ă˘â‚¬â€ť wiĂ„â„˘cej serwisÄ‚Ĺ‚w na ekranie przy zachowaniu czytelnoÄąâ€şci.
- **Pulpit Ă˘â‚¬â€ť nowy ukÄąâ€šad Kompaktowy (duÄąÄ˝y)**: rozmiar kafelkÄ‚Ĺ‚w jak poprzedni Kompaktowy v1.3.68 (~210px Ä‚â€” min. 60px, ikona 38px), staÄąâ€ša wysokoÄąâ€şĂ„â€ˇ karty Ă˘â‚¬â€ť akcje (Ă˘Ââ€¦, edycja, notatki, WoL, sleep) w prawym gÄ‚Ĺ‚rnym rogu na hover (jak ÄąĹˇredni), bez rozszerzania kafelka w dÄ‚Ĺ‚Äąâ€š. PiĂ„â€¦ty motyw w Ustawienia Ă˘â€ â€™ Pulpit. i18n pl/en/de/uk.
- **Pulpit Ă˘â‚¬â€ť gwiazdka odpiĂ„â„˘cia po lewej**: w ukÄąâ€šadach Kompaktowy, Kompaktowy (duÄąÄ˝y) i ÄąĹˇredni przycisk Ă˘Ââ€¦ jest po lewej stronie paska akcji (edycja, notatki, WoL, sleep po prawej) Ă˘â‚¬â€ť `space-between` zamiast grupowania wszystkich ikon po prawej.

## v1.3.68

- **Pulpit Ă˘â‚¬â€ť ukÄąâ€šad Kompaktowy**: przywrÄ‚Ĺ‚cony pasek akcji rozwijany w dÄ‚Ĺ‚Äąâ€š na hover (Ă˘Ââ€¦, edycja, notatki, WoL, sleep) Ă˘â‚¬â€ť karta pÄąâ€šynnie roÄąâ€şnie pod treÄąâ€şciĂ„â€¦ zamiast nachodziĂ„â€ˇ w prawym gÄ‚Ĺ‚rnym rogu. Zachowane ulepszenia v1.3.64+: wiĂ„â„˘ksze kafelki (~210px), siatka `auto-fill`, 2-liniowe etykiety, lepszy padding. UkÄąâ€šad ÄąĹˇredni bez zmian (akcje w rogu).

## v1.3.67

- **NagÄąâ€šÄ‚Ĺ‚wek Ă˘â‚¬â€ť porzĂ„â€¦dek akcji**: selektor jĂ„â„˘zyka (PL/EN/DE/UA) przeniesiony z paska gÄąâ€šÄ‚Ĺ‚wnego do UstawieÄąâ€ž Ă˘â€ â€™ JĂ„â„˘zyk. Przycisk ustawieÄąâ€ž to sama ikona Ă˘Ĺˇâ„˘ obok Ă˘â‚¬ĹľWylogujĂ˘â‚¬ĹĄ (tooltip i `aria-label` z i18n). StaÄąâ€ša szerokoÄąâ€şĂ„â€ˇ slotu Ă˘â‚¬ĹľSkanuj sieĂ„â€ˇĂ˘â‚¬ĹĄ / Ă˘â‚¬Ĺľ+ DodajĂ˘â‚¬ĹĄ Ă˘â‚¬â€ť przeÄąâ€šĂ„â€¦czanie Pulpit Ă˘â€ â€ť Serwisy nie przesuwa ikon po prawej.

## v1.3.66

- **Pulpit Ă˘â‚¬â€ť ukÄąâ€šad ÄąĹˇredni (polish)**: wiĂ„â„˘ksze mini-karty w grupach kategorii (~200px+, min. 68px) Ă˘â‚¬â€ť ikona 38px, nazwa (13px semibold, 2 linie) i port jako podtytuÄąâ€š w pionowym stosie. Siatka `auto-fill` wypeÄąâ€šnia szerokoÄąâ€şĂ„â€ˇ pudeÄąâ€ška kategorii (bez pustych 2Ä‚â€”2 i pojedynczych Ă˘â‚¬ĹľdziurĂ˘â‚¬ĹĄ). Akcje (Ă˘Ââ€¦, edycja, notatki, WoL, sleep) w prawym gÄ‚Ĺ‚rnym rogu na hover Ă˘â‚¬â€ť bez nachodzenia na port/nazwĂ„â„˘. Delikatniejsza ramka przypiĂ„â„˘tych (akcent kategorii na hover zamiast staÄąâ€šej zielonej). Lepszy padding/nagÄąâ€šÄ‚Ĺ‚wki sekcji (WEB, INNE, APIĂ˘â‚¬Â¦). Dedup pinÄ‚Ĺ‚w rozszerzony o `host:port` (np. podwÄ‚Ĺ‚jny Portainer/AI-SIEM/RDP).

## v1.3.65

- **Pulpit Ă˘â‚¬â€ť Klasyczny (maÄąâ€šy)**: wyraÄąĹźnie wiĂ„â„˘ksze ikony na przypiĂ„â„˘tych kartach (27px Ă˘â€ â€™ 40px, ten sam rozmiar co Klasyczny) Ă˘â‚¬â€ť powiĂ„â„˘kszony kontener, glyph 14px, status-dot 7px. Siatka kart min. 7.5rem (mobile 6.25rem), lekko wiĂ„â„˘kszy padding/gap w gÄ‚Ĺ‚rnej strefie. Nazwa, URL i stopka bez zmian hierarchii.

## v1.3.64

- **Pulpit Ă˘â‚¬â€ť ukÄąâ€šad Kompaktowy (mini-karty)**: wyraÄąĹźnie wiĂ„â„˘ksze kafelki przypiĂ„â„˘tych serwisÄ‚Ĺ‚w (~210px+, min. 60px wysokoÄąâ€şci) Ă˘â‚¬â€ť ikona 38px, czytelna nazwa (13px, semibold) i port jako podtytuÄąâ€š. Siatka `auto-fill` wypeÄąâ€šnia szerokoÄąâ€şĂ„â€ˇ wiersza zamiast zostawiaĂ„â€ˇ pustĂ„â€¦ przestrzeÄąâ€ž po prawej. Akcje (Ă˘Ââ€¦, edycja, notatki, WoL, sleep) w prawym gÄ‚Ĺ‚rnym rogu na hover (Homer/Dashy) Ă˘â‚¬â€ť bez rozszerzania karty w dÄ‚Ĺ‚Äąâ€š. Lepsze wyrÄ‚Ĺ‚wnanie etykiet kategorii z wierszem kafelkÄ‚Ĺ‚w.

## v1.3.63

- **Pulpit Ă˘â‚¬â€ť ukÄąâ€šad Kompaktowy (polish)**: wiĂ„â„˘ksze chipy przypiĂ„â„˘tych serwisÄ‚Ĺ‚w (152Ă˘â‚¬â€ś184px Ä‚â€” min. 48px) z czytelniejszĂ„â€¦ etykietĂ„â€¦ (2 linie, 12px), lepszym paddingiem i wyrÄ‚Ĺ‚wnaniem ikony. Pasek akcji (Ă˘Ââ€¦, edycja, notatki, WoL, sleep) w dedykowanym wierszu pod treÄąâ€şciĂ„â€¦ Ă˘â‚¬â€ť bez nachodzenia na ikonĂ„â„˘/nazwĂ„â„˘. Szersze etykiety kategorii (2 linie), wyrÄ‚Ĺ‚wnanie wierszy `flex-start`.

## v1.3.62

- **Pulpit Ă˘â‚¬â€ť scroll (fix v3)**: naprawione trwaÄąâ€še blokowanie przewijania po zamkniĂ„â„˘ciu modala Ă˘â‚¬â€ť `closeIconPopover()` byÄąâ€šo wywoÄąâ€šywane bez definicji (ReferenceError), wiĂ„â„˘c `unlockPageScroll` nigdy nie dziaÄąâ€šaÄąâ€š i `body` zostawaÄąâ€šo z `position: fixed`. Blokada oparta na liczbie widocznych `.modal` w DOM (zamiast refcount), `reconcilePageScrollLock` przy starcie i `pageshow`. Jeden scrollport: `html { overflow-y: scroll }`, bez drugiego na `body`.

## v1.3.61

- **Pulpit Ă˘â‚¬â€ť scroll (fix v2)**: jeden scrollport na `html` (`overflow-y: scroll`, bez `!important`); `body` roÄąâ€şnie z treÄąâ€şciĂ„â€¦ (`overflow-y: visible`, `height: auto`). UsuniĂ„â„˘te `overflow-y: auto` z `html, body` (v1.3.58 zdjĂ„â„˘Äąâ€šo flex-trap, ale drugi scrollport na `body` nadal blokowaÄąâ€š kÄ‚Ĺ‚Äąâ€ško przy 17+ pinach / 8 kategoriach). Jawne `overflow: visible` / `max-height: none` na Äąâ€šaÄąâ€žcuchu `#app` Ă˘â€ â€™ `#dashboard-view` Ă˘â€ â€™ `.main` Ă˘â€ â€™ `.pinned-section` + guard `[data-theme]`. UkÄąâ€šad ÄąĹˇredni: `height: 100%` / `stretch` Ă˘â€ â€™ `auto` / `start`. Klasyczny/ÄąĹˇredni: max 3 kolumny grup od 1280px. Sticky header: `isolation: isolate`.
- **Pulpit Ă˘â‚¬â€ť dedup pinÄ‚Ĺ‚w**: `dedupePinnedServices` przez `normalizeUrlCompareKey` (jak duplikat URL w modalu) Ă˘â‚¬â€ť jeden wpis na ten sam endpoint (np. podwÄ‚Ĺ‚jny AI-SIEM).

## v1.3.60

- **Pulpit Ă˘â‚¬â€ť Klasyczny (maÄąâ€šy)**: powiĂ„â„˘kszenie ukÄąâ€šadu `classic-sm` z ~50% do ~63% wymiarÄ‚Ĺ‚w Klasycznego (ikona 27px, karta min. 116px, czcionki/paddingi/watermark proporcjonalnie). Zachowany pionowy ukÄąâ€šad Homer i aspect 22:19.

## v1.3.59

- **JĂ„â„˘zyk Ă˘â‚¬â€ť dropdown (fix)**: natywne opcje select (PL/EN/DE/UA) niewidoczne na biaÄąâ€šym popupie OS Ă˘â‚¬â€ť `color-scheme: dark|light` per motyw, `option { background, color }` dla wszystkich `select` i `.lang-select`. Etykieta UK Ă˘â€ â€™ UA w nagÄąâ€šÄ‚Ĺ‚wku.

## v1.3.58

- **Pulpit Ă˘â‚¬â€ť scroll (fix)**: usuniĂ„â„˘ty flex-column trap na `#dashboard-view` oraz `overflow-x: hidden` na `#app` / `#dashboard-view` (CSS wymuszaÄąâ€š `overflow-y: auto` na kontenerze o wysokoÄąâ€şci viewportu Ă˘â‚¬â€ť kÄ‚Ĺ‚Äąâ€ško myszy nie przewijaÄąâ€šo dokumentu). Przewijanie strony dziaÄąâ€ša przy 8+ grupach kategorii.
- **Pulpit Ă˘â‚¬â€ť ukÄąâ€šad ÄąĹˇredni (polish)**: staÄąâ€ša wysokoÄąâ€şĂ„â€ˇ mini-kart (52px), wyrÄ‚Ĺ‚wnanie ikona+nazwa+port, wiĂ„â„˘ksze odstĂ„â„˘py grup, etykiety kategorii z ellipsis+tooltip, pasek akcji na hover wyÄąâ€şrodkowany po prawej (bez nachodzenia na Ă˘Ââ€¦), padding przy hover pod gwiazdkĂ„â„˘.

## v1.3.57

- **Pulpit Ă˘â‚¬â€ť Ă˘Ââ€¦ odpinanie (fix)**: wiĂ„â„˘kszy inset gwiazdki od krawĂ„â„˘dzi karty/chipa (`0.5rem`), przycisk 24px Ă˘â‚¬â€ť nie nachodzi na zaokrĂ„â€¦glony rÄ‚Ĺ‚g ani border przy `overflow: hidden`. Classic-sm i compact Ă˘â‚¬â€ť proporcjonalnie mniejszy przycisk/inset; compact Ă˘â‚¬â€ť padding przy hover pod Ă˘Ââ€¦.

## v1.3.56

- **Pulpit Ă˘â‚¬â€ť Ă˘Ââ€¦ odpinanie**: gwiazdka w lewym gÄ‚Ĺ‚rnym rogu karty/chipa na hover (classic, classic-sm, medium, compact). Badge AUTO/LOGIN pozostajĂ„â€¦ po prawej; compact Ă˘â‚¬â€ť dodatkowy padding przy hover, ÄąÄ˝eby nie nachodziĂ„â€ˇ na ikonĂ„â„˘.

## v1.3.55

- **Pulpit Ă˘â‚¬â€ť scroll**: naprawione blokowanie przewijania pionowego przy wielu przypiĂ„â„˘tych kategoriach/serwisach (`overflow-y: visible` na `#dashboard-view` / `#app`, `flex: 1 0 auto` na `.main`). Modal ustawieÄąâ€ž bez zmian.
- **Pulpit Ă˘â‚¬â€ť WoL/SOL na przypiĂ„â„˘tych**: przyciski Ă˘Ĺ›Ĺ˝ Ä‘Ĺşâ€śĹĄ Ă˘ĹˇË‡ Ä‘Ĺşâ€™Â¤ na hover w classic, classic-sm, medium i compact (jak na kartach Serwisy). IstniejĂ„â€¦ce API + toast.
- **Pulpit Ă˘â‚¬â€ť Ă˘Ââ€¦ odpinanie**: gwiazdka w prawym gÄ‚Ĺ‚rnym rogu na hover (fix `position: relative` nadpisujĂ„â€¦cego `absolute`), z-index nad watermarkiem; compact Ă˘â‚¬â€ť osobny corner Ă˘Ââ€¦, akcje na dole chipa.

## v1.3.54

- **Pulpit Ă˘â‚¬â€ť motyw Klasyczny (maÄąâ€šy)**: czwarty ukÄąâ€šad `classic-sm` Ă˘â‚¬â€ť ta sama struktura co Klasyczny (pionowe karty w grupach, watermark, URL, kategoria, uptime), wymiary ~50% (ikona 20px, karta min. 88px). Ustawienia Ă˘â€ â€™ WyglĂ„â€¦d Ă˘â€ â€™ Pulpit. i18n pl/en/de/uk.

## v1.3.53

- **Pulpit Ă˘â‚¬â€ť sekcja przypiĂ„â„˘tych**: nagÄąâ€šÄ‚Ĺ‚wek Ă˘â‚¬ĹľPrzypiĂ„â„˘te serwisyĂ˘â‚¬ĹĄ zawsze widoczny (takÄąÄ˝e przy pustej liÄąâ€şcie), licznik pinÄ‚Ĺ‚w, pusta karta z CTA do SerwisÄ‚Ĺ‚w. Szersze etykiety kategorii w ukÄąâ€šadzie kompaktowym (bez obcinania Ă˘â‚¬ĹľDASHBOĂ˘â‚¬Â¦Ă˘â‚¬ĹĄ, Ă˘â‚¬ĹľDEVELOĂ˘â‚¬Â¦Ă˘â‚¬ĹĄ); tooltip na peÄąâ€šnej nazwie.
- **Serwisy Ă˘â‚¬â€ť duplikat URL**: ostrzeÄąÄ˝enie w modalu dodawania/edycji, gdy ten sam URL jest juÄąÄ˝ przypisany do innego serwisu (np. drugi Portainer). i18n pl/en/de/uk.
- **PWA (lekko)**: `manifest.json`, `theme-color`, ikona SVG Ă˘â‚¬â€ť moÄąÄ˝liwoÄąâ€şĂ„â€ˇ Ă˘â‚¬ĹľZainstaluj aplikacjĂ„â„˘Ă˘â‚¬ĹĄ w przeglĂ„â€¦darce.
- **Docs**: `DEPLOYMENT.md` Ă˘â‚¬â€ť wersja zsynchronizowana z `config.py`.

## v1.3.52

- **Dashboard Ă˘â‚¬â€ť 3 motywy pulpitu**: **Klasyczny** (Homer-style pionowe karty w grupach kategorii: ikona, nazwa, URL, kategoria, uptime, watermark), **ÄąĹˇredni** (poziome mini-karty ~58px: ikona + nazwa + port, subtelne grupy), **Kompaktowy** (gĂ„â„˘ste chipy w wierszach). Ustawienia Ă˘â€ â€™ WyglĂ„â€¦d Ă˘â€ â€™ Pulpit Ă˘â€ â€™ **Motyw pulpitu** z podglĂ„â€¦dem na ÄąÄ˝ywo. DomyÄąâ€şlny: ÄąĹˇredni. Migracja DB: `large`Ă˘â€ â€™classic, `normal`Ă˘â€ â€™medium, `compact` bez zmian.
- **Odpinanie (Ă˘Ââ€¦)**: przycisk w prawym gÄ‚Ĺ‚rnym rogu karty/chipa na hover Ă˘â‚¬â€ť nie blokuje klikniĂ„â„˘cia w serwis. Toast po odpiĂ„â„˘ciu. i18n pl/en/de/uk.

## v1.3.51

- **Dashboard Ă˘â‚¬â€ť przypiĂ„â„˘te serwisy (ultra-kompakt)**: dedykowane chipy `.pinned-chip` (~40Ä‚â€”140px) zamiast kart serwisowych Ă˘â‚¬â€ť wiersz kategorii (10px muted label) + inline chipy (32px ikona, nazwa, port tylko na hover). Bez badge PIN/auto/login, bez zielonej ramki pinned. Dedup po host:port:url. `data-pinned-size="compact"` wymuszony zawsze. ~200px wysokoÄąâ€şci dla ~11 pinÄ‚Ĺ‚w.

## v1.3.50

- **Dashboard Ă˘â‚¬â€ť przypiĂ„â„˘te serwisy (fix)**: Homer-style Ă˘â‚¬â€ť wiersz kategorii + poziome chipy (~56px), nie siatka wysokich kart w 5 kolumnach. Selektory `#pinned-container .service-card--pinned` po bazowym `.service-card` (cascade fix). UsuniĂ„â„˘ty `aspect-ratio` na przypiĂ„â„˘tych. Migracja DB: `pinned_card_size` large/normal Ă˘â€ â€™ compact. `body data-pinned-size="compact"` w HTML przed JS.

## v1.3.49

- **Service modal Ă˘â‚¬â€ť upload icon (fix)**: Ă˘â‚¬ĹľWgraj z plikuĂ˘â‚¬ĹĄ as primary action opens native OS file picker reliably (`sr-file-input` instead of `display:none`). URL field moved to collapsed Ă˘â‚¬Ĺľlub podaj URLĂ˘â‚¬ĹĄ; uploaded icons show preview + filename only (not raw `/uploads/icons/Ă˘â‚¬Â¦` in the main field). Identify favicon URLs stay in collapsed section. Same pattern for Settings Ă˘â€ â€™ Favicon upload. i18n pl/en/de/uk.

## v1.3.48

- **Dashboard Ă˘â‚¬â€ť kompaktowe przypiĂ„â„˘te serwisy**: karty w poziomie (ikona + nazwa + port), max ~58px wysokoÄąâ€şci; ukryty URL (tooltip na nazwie), bez kategorii/uptime w grupie. Mniejsze badge, watermark i panele grup (`minmax(14rem)`). Pin, hover-akcje i grupowanie bez zmian.
- **Settings Ă˘â€ â€™ WyglĂ„â€¦d Ă˘â€ â€™ Pulpit Ă˘â‚¬â€ť rozmiar przypiĂ„â„˘tych kart**: Kompaktowy (domyÄąâ€şlny) | Normalny | DuÄąÄ˝y. `pinned_card_size` w bazie; `body[data-pinned-size]`; podglĂ„â€¦d na ÄąÄ˝ywo. Lista Serwisy bez zmian. i18n pl/en/de/uk.

## v1.3.47

- **Service modal Ă˘â‚¬â€ť upload icon file**: Ă˘â‚¬ĹľWgraj plikĂ˘â‚¬ĹĄ / Upload icon button in add/edit modals (WyglĂ„â€¦d). Uploads PNG/JPEG/WebP/SVG (max 2 MB) via `POST /api/services/upload-icon`; preview and `icon_url` update immediately; filename/thumbnail shown for uploaded icons. Works alongside preset grid and URL field. Auth + mime/size validation. i18n pl/en/de/uk.

## v1.3.46

- **Dashboard Ă˘â‚¬â€ť przypiĂ„â„˘te serwisy w grupach kategorii**: karty przypiĂ„â„˘te na pulpicie sĂ„â€¦ zgrupowane w wiĂ„â„˘ksze panele (Homer/Dashy) z dyskretnĂ„â€¦ etykietĂ„â€¦ kategorii serwisu (DevOps, Web, InneĂ˘â‚¬Â¦). Grupy ukÄąâ€šadajĂ„â€¦ siĂ„â„˘ w siatce na desktopie i jednej kolumnie na mobile. Pin, akcje kart i watermark bez zmian.

## v1.3.45

- **Serwisy Ă˘â‚¬â€ť filtr dostĂ„â„˘pnoÄąâ€şci (Wszystkie | Online | Offline)**: osobny pasek obok dostĂ„â„˘pu; Offline usuniĂ„â„˘ty z paska dostĂ„â„˘pu (zostaje PrzypiĂ„â„˘te Ă˘Ââ€¦). Klik Ă˘â‚¬ĹľWszystkieĂ˘â‚¬ĹĄ w dostĂ„â„˘pie resetuje filtr Online/Offline; przy aktywnym Online/Offline piguÄąâ€ška dostĂ„â„˘pu Ă˘â‚¬ĹľWszystkieĂ˘â‚¬ĹĄ jest przyciemniona. Liczniki wzajemnie wykluczajĂ„â€¦ce: online + offline + nieznane = wszystkie. i18n pl/en/de/uk.

## v1.3.44

- **Service modal icon picker (inline)**: always-visible visual grid with search, category tabs, and emoji/SVG tiles in add/edit modals Ă˘â‚¬â€ť replaces hidden popover and old text `<select>`. Recent icons (localStorage), keyboard arrows + Enter, selected-state highlight, live preview. i18n pl/en/de/uk.

## v1.3.43

- **Settings modal width (fix)**: dialog now truly uses `min(1200px, 96vw)` Ă˘â‚¬â€ť overrides the base `.modal-content` `max-width: 440px` that kept v1.3.39 at ~440px. Sidebar stays 200px; content pane ~960px+. Two-column fields get a higher min width; fixed height and mobile layout (Ă˘â€°Â¤768px) unchanged.

## v1.3.42

- **Serwisy Ă˘â‚¬â€ť filtry Offline + PrzypiĂ„â„˘te Ă˘Ââ€¦ (jeden pasek)**: Wszystkie | Z logowaniem | Publiczne | WoL | Offline | PrzypiĂ„â„˘te Ă˘Ââ€¦ w jednym segmented control. Offline = `serviceHealthState` offline/error; PrzypiĂ„â„˘te = `pinned === true`. Liczniki kombinowalne z kategoriĂ„â€¦/sieciĂ„â€¦/wyszukiwaniem. i18n pl/en/de/uk.

## v1.3.41

- **Logo NetDash**: dopracowany SVG crosshair (ciemny zaokrĂ„â€¦glony kwadrat, neonowy zielony celownik z delikatnym glow). Ten sam plik w nagÄąâ€šÄ‚Ĺ‚wku, faviconie i domyÄąâ€şlnym watermarku kart serwisÄ‚Ĺ‚w. `use_custom_logo` pozostaje wyÄąâ€šĂ„â€¦czone Ă˘â‚¬â€ť bez logo HELLUK.

## v1.3.40

- **Serwisy Ă˘â‚¬â€ť filtry Offline i PrzypiĂ„â„˘te Ă˘Ââ€¦**: pasek filtrÄ‚Ĺ‚w dostĂ„â„˘pu rozszerzony do Wszystkie | Z logowaniem | Publiczne | WoL | Offline | PrzypiĂ„â„˘te Ă˘Ââ€¦. Offline = `is_online === false` lub bÄąâ€šĂ„â€¦d health (nie login-gated); PrzypiĂ„â„˘te = `pinned === true`. Liczniki na piguÄąâ€škach, kombinowalne z kategoriĂ„â€¦ i sieciĂ„â€¦. i18n pl/en/de/uk.

## v1.3.39

- **Settings modal width**: dialog widened to `min(960px, 95vw)`; sidebar fixed at 200px so the content pane gets more room. Fixed height unchanged; mobile layout below 640px unchanged.

## v1.3.38

- **Multi-network scanning**: Settings Ă˘â€ â€™ Scanning and the scan modal accept multiple CIDR ranges (one per line or comma-separated), e.g. `192.168.1.0/24, 192.168.0.0/24, 10.0.0.0/24`. Backend validates and scans all listed subnets; ARP scan covers all configured networks.
- **Settings Ă˘â€ â€™ Scanning scroll fix**: extra bottom padding on the scan tab so Ă˘â‚¬Ĺ›UsuÄąâ€ž nieaktywne po (dni)Ă˘â‚¬ĹĄ and its hint are fully visible when scrolled.
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

- Fix service card **Ä‚â€” delete button** positioning (exclude from flex `position: relative` rule); 28px top-right hit target, hover-only.
- Fix **watermark** intermittent load: `loading="eager"`, onerror fallback icon_url Ă˘â€ â€™ preset Ă˘â€ â€™ letter Ă˘â€ â€™ globe.

## v1.3.31

- Redesigned **Settings Ă˘â€ â€™ About**: hero layout, version badge, GitHub chip, read-only author card, tech stack chips.
- Editable author/description in **General Ă˘â€ â€™ Branding**; Save hidden on read-only tabs (About, Backup, Account).
- Build date set at Docker deploy (`NETDASH_BUILD_DATE`); i18n pl/en/de/uk for About strings.

## v1.3.30

- Fix service card **delete (Ä‚â€”) button**: was pulled into flex flow by `position: relative` on card children Ă˘â‚¬â€ť now anchored top-right with 28px hit target, hover-only like other actions; DELETE `/api/services/{id}` unchanged.
- Fix intermittent **card watermark**: eager load + onerror fallback chain (icon_url Ă˘â€ â€™ preset icon Ă˘â€ â€™ name letter Ă˘â€ â€™ globe).
- In-app **toast notifications** (success / error / info) replace native `alert()` dialogs; WoL/SOL success shows green toast with Ă˘Ĺ›â€ś.
- `confirm()` kept only for destructive actions (delete service/key/note, sleep, backup import).
- Uptime: preserve raw `is_online` from API; green dot when `is_online === true` even if `last_checked` is old; amber only for genuinely unchecked/stale services.
- HTTP health: explicit online for 401/403/redirects; hide stale Ă˘â‚¬Ĺ›checked agoĂ˘â‚¬ĹĄ label on online cards when check is older than 2Ä‚â€” interval.

## v1.3.27

- Fix uptime dots showing amber/stale for reachable services (Proxmox, GPTWOL, login-gated apps).
- Treat HTTP 401/403 and redirects as **online**; only 5xx / connection failures mark offline.
- Self-signed HTTPS already probed with `verify=False`; startup + background health loop logs and runs immediately.
- Sanitize percent-encoded URL bytes artifacts (`b%27next=/%27` Ă˘â€ â€™ `?next=/`).
- Frontend refreshes service status from DB between health-check cycles.

## v1.3.26

- Enriched **Add service** modal: sections, icon preview + preset/URL, category datalist, description, pin/login toggles, Identyfikuj button (shared logic with edit modal).
- `POST /api/services` accepts `icon_url`; manually added services marked `customized`.

## v1.3.25

- Uptime indicators on service cards; Homer-inspired card polish; empty-state improvements; Homer YAML import.
