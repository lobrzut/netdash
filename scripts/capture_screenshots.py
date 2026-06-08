"""Seed demo data and capture NetDash UI screenshots for README."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.seed_demo_data import DEMO_KEYS, DEMO_NOTES, DEMO_SERVICES

BASE = "http://127.0.0.1:8788"
OUT_DIR = ROOT / "docs" / "screenshots"


async def seed_database() -> str:
    from sqlalchemy import delete

    from app.auth import create_access_token
    from app.database import async_session
    from app.models import ApiKey, Note, Service
    from app.vault import encrypt_secret

    async with async_session() as db:
        await db.execute(delete(Service))
        await db.execute(delete(ApiKey))
        await db.execute(delete(Note))

        for svc in DEMO_SERVICES:
            db.add(Service(**svc))

        for key in DEMO_KEYS:
            secret = key["secret"]
            db.add(
                ApiKey(
                    name=key["name"],
                    secret_encrypted=encrypt_secret(secret),
                    secret_hint=secret[-4:] if len(secret) >= 4 else secret,
                    service=key["service"],
                    username=key.get("username"),
                    notes=key.get("notes"),
                    pinned=key.get("pinned", False),
                )
            )

        for note in DEMO_NOTES:
            db.add(Note(**note))

        await db.commit()

    return create_access_token("admin")


def capture_with_playwright(token: str) -> None:
    from playwright.sync_api import sync_playwright

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    viewport = {"width": 1280, "height": 800}
    init_script = f"""
        window.localStorage.setItem('netdash_token', {json.dumps(token)});
        window.localStorage.setItem('netdash_page', 'home');
    """

    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(viewport=viewport)
        context.add_init_script(init_script)
        page = context.new_page()
        page.goto(BASE, wait_until="networkidle")
        page.wait_for_selector("#dashboard-view:not(.hidden)", timeout=15000)
        page.wait_for_function(
            "() => document.querySelector('#nav-home-btn span')?.textContent !== 'nav.home'",
            timeout=15000,
        )
        page.wait_for_timeout(1500)
        page.screenshot(path=str(OUT_DIR / "dashboard.png"))

        page.click("#nav-services-btn")
        page.wait_for_selector("#page-services", state="visible", timeout=5000)
        page.wait_for_timeout(800)
        page.screenshot(path=str(OUT_DIR / "services.png"))

        page.click("#settings-btn")
        page.wait_for_selector("#settings-modal:not(.hidden)", timeout=5000)
        page.wait_for_timeout(500)
        page.screenshot(path=str(OUT_DIR / "settings.png"))

        login_context = browser.new_context(viewport=viewport)
        login_page = login_context.new_page()
        login_page.goto(BASE, wait_until="networkidle")
        login_page.wait_for_selector("#login-view:not(.hidden)", timeout=10000)
        login_page.wait_for_timeout(500)
        login_page.screenshot(path=str(OUT_DIR / "login.png"))
        login_context.close()

        browser.close()


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    token = asyncio.run(seed_database())

    try:
        capture_with_playwright(token)
    except ImportError:
        print("playwright not installed; run: pip install playwright && playwright install chromium", file=sys.stderr)
        return 1

    print(json.dumps({"ok": True, "out": str(OUT_DIR)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
