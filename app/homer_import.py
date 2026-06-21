"""Parse Homer dashboard config.yml into NetDash service records."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import yaml

DEFAULT_CATEGORY = "Inne"


def _coerce_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _item_to_service(item: dict[str, Any], category: str) -> dict[str, str] | None:
    name = _coerce_str(item.get("name") or item.get("title"))
    url = _coerce_str(item.get("url") or item.get("link") or item.get("href"))
    if not name or not url:
        return None
    if not url.startswith(("http://", "https://")):
        url = f"http://{url.lstrip('/')}"
    icon_url = _coerce_str(item.get("logo") or item.get("icon_url") or item.get("image"))
    icon = "globe"
    raw_icon = _coerce_str(item.get("icon"))
    if raw_icon and not raw_icon.startswith(("http://", "https://", "fas ", "far ", "fab ")):
        icon = raw_icon.lower().replace(" ", "-")
    description = _coerce_str(item.get("subtitle") or item.get("tag") or item.get("description")) or None
    return {
        "name": name[:128],
        "url": url[:512],
        "category": (category or DEFAULT_CATEGORY)[:64],
        "icon": icon[:64],
        "icon_url": icon_url[:512] if icon_url else None,
        "description": description,
    }


def _walk_groups(node: Any, category: str, out: list[dict[str, str]]) -> None:
    if isinstance(node, list):
        for entry in node:
            _walk_groups(entry, category, out)
        return
    if not isinstance(node, dict):
        return

    group_name = _coerce_str(node.get("name") or node.get("title")) or category
    items = node.get("items")
    if isinstance(items, list):
        for item in items:
            if isinstance(item, dict):
                svc = _item_to_service(item, group_name)
                if svc:
                    out.append(svc)
            elif isinstance(item, list):
                _walk_groups(item, group_name, out)
        return

    # Flat service entry (no nested items)
    svc = _item_to_service(node, category or group_name)
    if svc and _coerce_str(node.get("url") or node.get("link")):
        out.append(svc)


def parse_homer_config(yaml_text: str) -> list[dict[str, str]]:
    """Return deduplicated service dicts from Homer config YAML."""
    try:
        data = yaml.safe_load(yaml_text)
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("Invalid Homer config: expected YAML mapping at root")

    services: list[dict[str, str]] = []
    raw_services = data.get("services")
    if raw_services is None:
        raise ValueError("Invalid Homer config: missing 'services' key")
    _walk_groups(raw_services, DEFAULT_CATEGORY, services)

    seen: set[tuple[str, str]] = set()
    unique: list[dict[str, str]] = []
    for svc in services:
        key = (svc["name"].lower(), svc["url"].lower())
        if key in seen:
            continue
        seen.add(key)
        parsed = urlparse(svc["url"])
        if not parsed.scheme or not parsed.netloc:
            continue
        unique.append(svc)
    return unique
