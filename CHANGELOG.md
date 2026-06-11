# Changelog

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
