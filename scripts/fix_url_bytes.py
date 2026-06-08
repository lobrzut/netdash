#!/usr/bin/env python3
"""One-off cleanup for URLs corrupted with Python bytes repr (e.g. ?b'next=%2F')."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sqlalchemy import select

from app.database import async_session
from app.models import Service
from app.url_utils import sanitize_service_url


async def main() -> int:
    fixed = 0
    async with async_session() as db:
        result = await db.execute(select(Service))
        for svc in result.scalars().all():
            clean = sanitize_service_url(svc.url)
            if clean and svc.url != clean:
                print(f"#{svc.id} {svc.name}: {svc.url!r} -> {clean!r}")
                svc.url = clean
                fixed += 1
        if fixed:
            await db.commit()
    print(f"Fixed {fixed} URL(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
