"""Remove demo/junk entries from netdash.db (keep real 192.168.1.x hosts)."""
from __future__ import annotations

import argparse
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "data" / "netdash.db"

DEMO_HOST_PATTERNS = (
    r"\.local$",
    r"\.demo\.local$",
    r"^10\.0\.0\.",
)
DEMO_NAME_PATTERNS = (
    r"(?i)demo",
    r"(?i)kupa",
    r"(?i)bleble",
    r"(?i)grafana demo",
    r"(?i)openai demo",
    r"(?i)^ff$",
    r"(?i)^junk$",
)
DEMO_NOTE_TITLES = {
    "demo network",
    "backup schedule",
}
DEMO_NETWORK_CIDR = "10.0.0.0/24"
HOMELAB_PREFIX_RE = re.compile(r"^192\.168\.1\.")


def _is_demo_host(host: str) -> bool:
    return any(re.search(p, host) for p in DEMO_HOST_PATTERNS)


def _is_demo_name(name: str) -> bool:
    return any(re.search(p, name) for p in DEMO_NAME_PATTERNS)


def _is_real_homelab_host(host: str | None) -> bool:
    return bool(host and HOMELAB_PREFIX_RE.match(host.strip()))


def _table_exists(cur: sqlite3.Cursor, table: str) -> bool:
    row = cur.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
        (table,),
    ).fetchone()
    return row is not None


def _table_columns(cur: sqlite3.Cursor, table: str) -> set[str]:
    return {r[1] for r in cur.execute(f"PRAGMA table_info({table})").fetchall()}


def _is_demo_service_record(host: str | None, name: str | None, url: str | None) -> bool:
    host_val = (host or "").strip()
    name_val = (name or "").strip()
    url_val = (url or "").strip().lower()
    if _is_real_homelab_host(host_val):
        return False
    if _is_demo_host(host_val):
        return True
    if ".demo.local" in url_val or "10.0.0." in url_val:
        return True
    if _is_demo_name(name_val) and (not host_val or ".local" in host_val or "demo" in url_val):
        return True
    return False


def cleanup_demo_data(*, db_path: Path, apply: bool = False) -> dict[str, int]:
    removed = {"services": 0, "api_keys": 0, "notes": 0, "settings": 0}
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()

        if _table_exists(cur, "services"):
            for row_id, name, host, url in cur.execute(
                "SELECT id, name, host, url FROM services"
            ).fetchall():
                if _is_demo_service_record(host, name, url):
                    if apply:
                        cur.execute("DELETE FROM services WHERE id = ?", (row_id,))
                    removed["services"] += 1

        if _table_exists(cur, "api_keys"):
            api_cols = _table_columns(cur, "api_keys")
            has_notes = "notes" in api_cols
            query = "SELECT id, name, notes FROM api_keys" if has_notes else "SELECT id, name, '' FROM api_keys"
            for row_id, name, notes in cur.execute(query).fetchall():
                if _is_demo_name((name or "")) or _is_demo_name((notes or "")):
                    if apply:
                        cur.execute("DELETE FROM api_keys WHERE id = ?", (row_id,))
                    removed["api_keys"] += 1

        if _table_exists(cur, "notes"):
            for row_id, title in cur.execute("SELECT id, title FROM notes").fetchall():
                title_clean = (title or "").strip()
                if title_clean.lower() in DEMO_NOTE_TITLES or _is_demo_name(title_clean):
                    if apply:
                        cur.execute("DELETE FROM notes WHERE id = ?", (row_id,))
                    removed["notes"] += 1

        if _table_exists(cur, "app_settings") and "scan_cidr_default" in _table_columns(cur, "app_settings"):
            row = cur.execute("SELECT id, scan_cidr_default FROM app_settings LIMIT 1").fetchone()
            if row and row[1] == DEMO_NETWORK_CIDR:
                if apply:
                    cur.execute("UPDATE app_settings SET scan_cidr_default = NULL WHERE id = ?", (row[0],))
                removed["settings"] += 1

        if apply:
            conn.commit()
        else:
            conn.rollback()
        return removed
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Remove demo/junk records from NetDash DB safely.")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply deletions. Without this flag, script runs as dry-run only.",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB,
        help=f"Path to netdash.db (default: {DEFAULT_DB}).",
    )
    args = parser.parse_args()

    removed = cleanup_demo_data(db_path=args.db, apply=args.apply)
    total = sum(removed.values())
    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"Cleanup {mode}: candidates {total} entries - {removed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
