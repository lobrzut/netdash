"""Remove demo/junk entries from netdash.db (keep real 192.168.1.x hosts)."""
from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

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


def _is_demo_host(host: str) -> bool:
    return any(re.search(p, host) for p in DEMO_HOST_PATTERNS)


def _is_demo_name(name: str) -> bool:
    return any(re.search(p, name) for p in DEMO_NAME_PATTERNS)


async def cleanup_demo_data() -> dict[str, int]:
    from sqlalchemy import delete, select

    from app.database import async_session
    from app.models import ApiKey, AppSettings, Note, Service

    removed = {"services": 0, "api_keys": 0, "notes": 0}

    async with async_session() as db:
        services = (await db.scalars(select(Service))).all()
        for svc in services:
            if _is_demo_host(svc.host) or _is_demo_name(svc.name) or ".demo.local" in svc.url:
                await db.delete(svc)
                removed["services"] += 1

        keys = (await db.scalars(select(ApiKey))).all()
        for key in keys:
            if _is_demo_name(key.name) or (key.notes and _is_demo_name(key.notes)):
                await db.delete(key)
                removed["api_keys"] += 1

        notes = (await db.scalars(select(Note))).all()
        for note in notes:
            if note.title.lower() in DEMO_NOTE_TITLES or _is_demo_name(note.title):
                await db.delete(note)
                removed["notes"] += 1

        row = await db.scalar(select(AppSettings).limit(1))
        if row and row.scan_cidr_default == DEMO_NETWORK_CIDR:
            row.scan_cidr_default = None

        await db.commit()

    return removed


def main() -> int:
    removed = asyncio.run(cleanup_demo_data())
    total = sum(removed.values())
    print(f"Cleanup done: removed {total} entries — {removed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
