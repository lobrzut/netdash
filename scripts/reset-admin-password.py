#!/usr/bin/env python3
"""Reset NetDash admin password in the SQLite database (offline / docker exec)."""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "data" / "netdash.db"


def main() -> int:
    parser = argparse.ArgumentParser(description="Reset NetDash admin password in netdash.db")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="Path to netdash.db")
    parser.add_argument("--username", default="admin", help="Admin username (default: admin)")
    parser.add_argument("--password", default="changeme", help="New password (default: changeme)")
    args = parser.parse_args()

    if not args.db.is_file():
        print(f"Database not found: {args.db}", file=sys.stderr)
        return 1

    sys.path.insert(0, str(ROOT))
    from app.auth import hash_password

    password_hash = hash_password(args.password)
    conn = sqlite3.connect(args.db)
    try:
        cur = conn.execute("SELECT id FROM users WHERE username = ?", (args.username,))
        row = cur.fetchone()
        if row is None:
            print(f"User {args.username!r} not found in {args.db}", file=sys.stderr)
            return 1
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE username = ?",
            (password_hash, args.username),
        )
        conn.commit()
    finally:
        conn.close()

    print(f"Password reset for {args.username!r} in {args.db}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
