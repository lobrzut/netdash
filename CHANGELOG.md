# Changelog

## v1.3.28

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
