"""Seed demo data and capture NetDash UI screenshots for README."""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

BASE = os.environ.get("NETDASH_SCREENSHOT_URL", "http://127.0.0.1:8787")
OUT_DIR = ROOT / "docs" / "screenshots"


async def get_auth_token() -> str:
    from app.auth import create_access_token

    from scripts.seed_demo_data import seed_demo_data

    await seed_demo_data()
    return create_access_token("admin")


def capture_with_playwright(token: str) -> None:
    from playwright.sync_api import sync_playwright

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    viewport = {"width": 1280, "height": 800}

    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(viewport=viewport)
        context.add_init_script(
            f"window.localStorage.setItem('netdash_token', {json.dumps(token)});"
        )
        page = context.new_page()
        page.goto(BASE, wait_until="networkidle")
        page.wait_for_function(
            "() => document.querySelector('#nav-home-btn span')?.textContent !== 'nav.home'",
            timeout=15000,
        )
        page.wait_for_selector("#dashboard-view:not(.hidden)", timeout=15000)
        page.wait_for_timeout(1200)
        page.screenshot(path=str(OUT_DIR / "dashboard.png"))

        page.click("#nav-services-btn")
        page.wait_for_timeout(1000)
        page.screenshot(path=str(OUT_DIR / "services.png"))

        page.click("#settings-btn")
        page.wait_for_selector("#settings-modal:not(.hidden)", timeout=5000)
        page.click('.settings-tab[data-tab="backup"]')
        page.wait_for_timeout(600)
        page.screenshot(path=str(OUT_DIR / "settings.png"))

        login_context = browser.new_context(viewport=viewport)
        login_page = login_context.new_page()
        login_page.goto(BASE, wait_until="networkidle")
        login_page.wait_for_selector("#login-view:not(.hidden)", timeout=15000)
        login_page.wait_for_timeout(600)
        login_page.screenshot(path=str(OUT_DIR / "login.png"))
        login_context.close()

        browser.close()


def main() -> int:
    os.environ.setdefault("NETDASH_DEMO_MODE", "1")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    token = asyncio.run(get_auth_token())

    try:
        capture_with_playwright(token)
    except ImportError:
        print(
            "playwright not installed; run: pip install playwright && playwright install chromium",
            file=sys.stderr,
        )
        return 1
    except Exception as exc:
        print(f"capture failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps({"ok": True, "out": str(OUT_DIR), "base": BASE}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
