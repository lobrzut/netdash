"""Insert fake demo data for README screenshots (never use on production)."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DEMO_NETWORK_IP = "10.0.0.5"
DEMO_NETWORK_CIDR = "10.0.0.0/24"

DEMO_SERVICES = [
    {
        "name": "Grafana Demo",
        "url": "http://grafana.demo.local:3000",
        "host": "grafana.demo.local",
        "port": 3000,
        "category": "Monitoring",
        "icon": "grafana",
        "pinned": True,
        "has_login": True,
        "protocol": "http",
        "is_online": True,
        "auto_discovered": True,
    },
    {
        "name": "Home Assistant",
        "url": "http://ha.demo.local:8123",
        "host": "ha.demo.local",
        "port": 8123,
        "category": "Smart Home",
        "icon": "homeassistant",
        "pinned": True,
        "has_login": True,
        "protocol": "http",
        "is_online": True,
        "auto_discovered": True,
    },
    {
        "name": "Proxmox",
        "url": "https://proxmox.demo.local:8006",
        "host": "proxmox.demo.local",
        "port": 8006,
        "category": "Virtualization",
        "icon": "proxmox",
        "pinned": True,
        "has_login": True,
        "protocol": "https",
        "is_online": True,
        "auto_discovered": True,
    },
    {
        "name": "Jellyfin",
        "url": "http://10.0.0.20:8096",
        "host": "10.0.0.20",
        "port": 8096,
        "category": "Media",
        "icon": "jellyfin",
        "pinned": True,
        "has_login": True,
        "protocol": "http",
        "is_online": True,
        "auto_discovered": True,
    },
    {
        "name": "Portainer",
        "url": "http://10.0.0.30:9000",
        "host": "10.0.0.30",
        "port": 9000,
        "category": "Docker",
        "icon": "docker",
        "pinned": False,
        "has_login": True,
        "protocol": "http",
        "is_online": True,
        "auto_discovered": True,
    },
    {
        "name": "n8n",
        "url": "http://automation.demo.local:5678",
        "host": "automation.demo.local",
        "port": 5678,
        "category": "Automation",
        "icon": "n8n",
        "pinned": False,
        "has_login": True,
        "protocol": "http",
        "is_online": True,
        "auto_discovered": True,
    },
    {
        "name": "Plex",
        "url": "http://10.0.0.21:32400",
        "host": "10.0.0.21",
        "port": 32400,
        "category": "Media",
        "icon": "plex",
        "pinned": False,
        "has_login": True,
        "protocol": "http",
        "is_online": False,
        "auto_discovered": True,
    },
]

DEMO_KEYS = [
    {
        "name": "OpenAI Demo",
        "secret": "sk-demo-xxxxxxxxxxxxxxxxxxxx",
        "service": "API",
        "username": "demo",
        "notes": "Read-only demo key",
        "pinned": True,
    },
    {
        "name": "Grafana API",
        "secret": "glsa_demo_readonly_token_xx",
        "service": "Grafana",
        "username": "admin",
        "notes": "Dashboard import token",
        "pinned": False,
    },
]

DEMO_NOTES = [
    {
        "title": "Demo network",
        "content": "**Gateway:** 10.0.0.1\n- VLAN 10: IoT\n- VLAN 20: Media",
        "color": "blue",
        "pinned": True,
    },
    {
        "title": "Backup schedule",
        "content": "Daily at 03:00 — demo NAS + cloud sync",
        "color": "green",
        "pinned": False,
    },
]


async def seed_demo_data() -> None:
    from sqlalchemy import delete, select

    from app.database import async_session
    from app.models import ApiKey, AppSettings, Note, Service
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

        row = await db.scalar(select(AppSettings).limit(1))
        if row:
            row.scan_cidr_default = DEMO_NETWORK_CIDR
            row.language = "pl"
            row.show_vault = True
            row.show_notes = True

        await db.commit()


def main() -> int:
    asyncio.run(seed_demo_data())
    print(f"Demo data seeded ({len(DEMO_SERVICES)} services, network {DEMO_NETWORK_CIDR})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
