"""Remove auto-discovered services for a removed Docker stack (by name/url keywords)."""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "data" / "netdash.db"

DEFAULT_KEYWORDS = (
    "hermes",
    "khoj",
    "secondbrain",
    "second-brain",
    "second_brain",
)


def _matches(service: tuple, keywords: tuple[str, ...]) -> bool:
    row_id, name, host, port, url, category = service
    blob = " ".join(
        str(part or "")
        for part in (name, host, url, category)
    ).lower()
    return any(keyword in blob for keyword in keywords)


def find_stack_services(
    db_path: Path,
    keywords: tuple[str, ...] = DEFAULT_KEYWORDS,
) -> list[tuple]:
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT id, name, host, port, url, category FROM services ORDER BY id"
        ).fetchall()
        return [row for row in rows if _matches(row, keywords)]
    finally:
        conn.close()


def cleanup_stack_services(
    *,
    db_path: Path,
    keywords: tuple[str, ...] = DEFAULT_KEYWORDS,
    apply: bool = False,
) -> list[tuple]:
    matches = find_stack_services(db_path, keywords)
    if apply and matches:
        conn = sqlite3.connect(db_path)
        try:
            ids = [row[0] for row in matches]
            conn.executemany("DELETE FROM services WHERE id = ?", [(i,) for i in ids])
            conn.commit()
        finally:
            conn.close()
    return matches


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Delete NetDash services matching removed stack keywords."
    )
    parser.add_argument("--apply", action="store_true", help="Delete matches (default: dry-run).")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="Path to netdash.db")
    parser.add_argument(
        "--keyword",
        action="append",
        dest="keywords",
        help="Extra keyword (repeatable). Defaults: hermes, khoj, secondbrain, …",
    )
    args = parser.parse_args()
    keywords = tuple(k.lower() for k in (args.keywords or DEFAULT_KEYWORDS))
    matches = cleanup_stack_services(db_path=args.db, keywords=keywords, apply=args.apply)
    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"{mode}: {len(matches)} service(s)")
    for row in matches:
        print(f"  id={row[0]} name={row[1]!r} host={row[2]} port={row[3]} url={row[4]!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
