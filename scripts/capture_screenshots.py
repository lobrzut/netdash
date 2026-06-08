"""Seed demo data and capture NetDash UI screenshots for README."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

BASE = "http://127.0.0.1:8788"
OUT_DIR = ROOT / "docs" / "screenshots"

DEMO_SERVICES = [
    {"name": "Jellyfin", "url": "http://media.local:8096", "host": "media.local", "port": 8096, "category": "Media", "icon": "jellyfin", "pinned": True, "has_login": True, "protocol": "http", "is_online": True, "auto_discovered": True},
    {"name": "Grafana", "url": "http://monitor.local:3000", "host": "monitor.local", "port": 3000, "category": "Monitoring", "icon": "grafana", "pinned": True, "has_login": False, "protocol": "http", "is_online": True, "auto_discovered": True},
    {"name": "Plex", "url": "http://media.local:32400", "host": "media.local", "port": 32400, "category": "Media", "icon": "plex", "pinned": True, "has_login": True, "protocol": "http", "is_online": False, "auto_discovered": True},
    {"name": "n8n", "url": "http://automation.local:5678", "host": "automation.local", "port": 5678, "category": "Automation", "icon": "n8n", "pinned": True, "has_login": True, "protocol": "http", "is_online": True, "auto_discovered": True},
    {"name": "Portainer", "url": "http://docker.local:9000", "host": "docker.local", "port": 9000, "category": "Docker", "icon": "docker", "pinned": False, "has_login": True, "protocol": "http", "is_online": True, "auto_discovered": True},
    {"name": "Home Assistant", "url": "http://smart.local:8123", "host": "smart.local", "port": 8123, "category": "Smart Home", "icon": "homeassistant", "pinned": False, "has_login": True, "protocol": "http", "is_online": True, "auto_discovered": True},
    {"name": "Proxmox", "url": "https://hypervisor.local:8006", "host": "hypervisor.local", "port": 8006, "category": "Virtualization", "icon": "proxmox", "pinned": False, "has_login": True, "protocol": "https", "is_online": True, "auto_discovered": True},
]

DEMO_KEYS = [
    {"name": "Grafana API", "secret": "glsa_demo_key_masked_value", "service": "Grafana", "username": "admin", "notes": "Read-only dashboard", "pinned": True},
    {"name": "Home Assistant", "secret": "eyJ_demo_token_value_here", "service": "HA", "notes": "Long-lived token", "pinned": False},
]

DEMO_NOTES = [
    {"title": "Router config", "content": "**Gateway:** 192.168.1.1\n- WiFi: WPA3\n- VLAN 10: IoT", "color": "blue", "pinned": True},
    {"title": "Backup schedule", "content": "Daily at 03:00 — NAS + cloud", "color": "green", "pinned": False},
]


async def seed_database() -> str:
    from sqlalchemy import select

    from app.auth import create_access_token
    from app.database import async_session
    from app.models import ApiKey, Note, Service
    from app.vault import encrypt_secret

    async with async_session() as db:
        existing = {s.name for s in (await db.execute(select(Service))).scalars()}
        for svc in DEMO_SERVICES:
            if svc["name"] in existing:
                continue
            db.add(Service(**svc))

        existing_keys = {k.name for k in (await db.execute(select(ApiKey))).scalars()}
        for key in DEMO_KEYS:
            if key["name"] in existing_keys:
                continue
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

        existing_notes = {n.title for n in (await db.execute(select(Note))).scalars()}
        for note in DEMO_NOTES:
            if note["title"] in existing_notes:
                continue
            db.add(Note(**note))

        await db.commit()

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
        page.wait_for_selector("#dashboard-view:not(.hidden)", timeout=15000)
        page.wait_for_timeout(1000)
        page.screenshot(path=str(OUT_DIR / "dashboard.png"))

        page.click("#nav-services-btn")
        page.wait_for_timeout(800)
        page.screenshot(path=str(OUT_DIR / "services.png"))

        page.click("#settings-btn")
        page.wait_for_selector("#settings-modal:not(.hidden)", timeout=5000)
        page.wait_for_timeout(500)
        page.screenshot(path=str(OUT_DIR / "settings.png"))

        context.clear_cookies()
        page.evaluate("localStorage.removeItem('netdash_token')")
        page.reload(wait_until="networkidle")
        page.wait_for_timeout(500)
        page.screenshot(path=str(OUT_DIR / "login.png"))

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
