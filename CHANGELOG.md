# Changelog

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
