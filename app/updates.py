"""GitHub release check for in-app update notifications."""

from __future__ import annotations

import re
from typing import Any

import httpx

from app.config import GITHUB_REPO, VERSION

_GITHUB_API = "https://api.github.com/repos/lobrzut/netdash/releases/latest"
_VERSION_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)")


def normalize_version(version: str | None) -> str:
    if not version:
        return ""
    text = version.strip()
    return text[1:] if text.startswith("v") else text


def version_tuple(version: str | None) -> tuple[int, int, int] | None:
    if not version:
        return None
    match = _VERSION_RE.match(version.strip())
    if not match:
        return None
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def is_newer_version(current: str, latest: str) -> bool:
    cur = version_tuple(current)
    lat = version_tuple(latest)
    if cur is None or lat is None:
        return False
    return lat > cur


async def fetch_latest_release() -> dict[str, Any]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": f"NetDash/{VERSION}",
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(_GITHUB_API, headers=headers)
        response.raise_for_status()
        data = response.json()

    tag = str(data.get("tag_name") or "").strip()
    return {
        "latest_version": normalize_version(tag) or None,
        "release_url": data.get("html_url"),
        "release_notes": data.get("body") or None,
        "published_at": data.get("published_at"),
        "github_repo": GITHUB_REPO,
    }
