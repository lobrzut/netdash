"""Server-side favicon fetch and icon enrichment for auto-discovered services."""

from __future__ import annotations

import asyncio
import hashlib
import logging
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
from sqlalchemy import select

from app.config import DATA_DIR, settings
from app.database import async_session
from app.icons import (
    effective_browser_icon_url,
    extract_favicon_url,
    resolve_brand_icon,
    resolve_port_brand_icon,
)
from app.models import Service
from app.url_utils import is_blocked_fetch_target, is_safe_browser_icon_url, sanitize_service_url

logger = logging.getLogger("netdash")

ICONS_DIR = DATA_DIR / "uploads" / "icons"
ICONS_DIR.mkdir(parents=True, exist_ok=True)

_MAX_ICON_BYTES = 512 * 1024
_MIN_ICON_BYTES = 32
_USER_AGENT = "NetDash/1.0 IconFetcher"

_CONTENT_TYPE_EXT = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "image/svg+xml": ".svg",
    "image/x-icon": ".ico",
    "image/vnd.microsoft.icon": ".ico",
}


def _icon_ext(content_type: str | None, url: str) -> str:
    if content_type:
        ct = content_type.split(";", 1)[0].strip().lower()
        if ct in _CONTENT_TYPE_EXT:
            return _CONTENT_TYPE_EXT[ct]
    path = urlparse(url).path.lower()
    for ext in (".png", ".jpg", ".jpeg", ".webp", ".svg", ".ico"):
        if path.endswith(ext):
            return ext if ext != ".jpeg" else ".jpg"
    return ".png"


def _cache_path(host: str, port: int, ext: str) -> Path:
    digest = hashlib.sha256(f"{host}:{port}".encode()).hexdigest()[:16]
    return ICONS_DIR / f"svc_{digest}{ext}"


def save_cached_icon(host: str, port: int, content: bytes, ext: str) -> str:
    dest = _cache_path(host, port, ext)
    dest.write_bytes(content)
    return f"/uploads/icons/{dest.name}"


def service_needs_icon_fetch(svc: Service) -> bool:
    """True when the service has no browser-safe watermark icon."""
    if effective_browser_icon_url(
        svc.icon_url,
        svc.url,
        has_login=svc.has_login,
        name=svc.name,
        description=svc.description,
        port=svc.port,
    ):
        return False
    if svc.protocol in ("http", "https") and svc.url:
        return True
    return resolve_port_brand_icon(svc.port) is not None


async def _download_icon(client: httpx.AsyncClient, url: str) -> tuple[bytes, str] | None:
    if is_blocked_fetch_target(url):
        return None
    try:
        response = await client.get(url, headers={"User-Agent": _USER_AGENT})
    except (httpx.HTTPError, asyncio.TimeoutError):
        return None
    if response.status_code >= 400:
        return None
    content = response.content
    if len(content) < _MIN_ICON_BYTES or len(content) > _MAX_ICON_BYTES:
        return None
    ct = response.headers.get("content-type", "")
    if ct and not ct.lower().startswith("image/") and "icon" not in ct.lower():
        return None
    return content, _icon_ext(ct, str(response.url))


async def fetch_remote_favicon(service_url: str) -> tuple[bytes, str] | None:
    """Fetch favicon bytes from a service URL (server-side, LAN-safe)."""
    safe_url = sanitize_service_url(service_url)
    if not safe_url:
        return None
    parsed = urlparse(safe_url)
    if parsed.scheme not in ("http", "https"):
        return None

    schemes = [parsed.scheme]
    alt = "http" if parsed.scheme == "https" else "https"
    schemes.append(alt)

    timeout = httpx.Timeout(settings.http_timeout, connect=min(5.0, settings.http_timeout))
    async with httpx.AsyncClient(verify=False, follow_redirects=True, timeout=timeout) as client:
        for scheme in schemes:
            if scheme == parsed.scheme:
                page_url = safe_url
            else:
                port = parsed.port
                host = parsed.hostname or ""
                if (scheme == "https" and port == 443) or (scheme == "http" and port == 80):
                    page_url = f"{scheme}://{host}"
                elif port:
                    page_url = f"{scheme}://{host}:{port}"
                else:
                    page_url = f"{scheme}://{host}"

            if is_blocked_fetch_target(page_url):
                continue

            try:
                response = await client.get(page_url, headers={"User-Agent": _USER_AGENT})
            except (httpx.HTTPError, asyncio.TimeoutError):
                response = None

            if response is not None and response.status_code < 500:
                body = response.text[:8192]
                favicon_href = extract_favicon_url(str(response.url), body)
                if favicon_href:
                    data = await _download_icon(client, favicon_href)
                    if data:
                        return data

            base = f"{scheme}://{parsed.netloc}"
            favicon_url = urljoin(base + "/", "favicon.ico")
            data = await _download_icon(client, favicon_url)
            if data:
                return data

    return None


async def resolve_service_icon_url(
    *,
    name: str | None,
    url: str | None,
    description: str | None = None,
    port: int | None = None,
    host: str | None = None,
    has_login: bool = False,
    fetch_remote: bool = True,
) -> str | None:
    """Best icon URL for a service — brand CDN, port fingerprint, or cached favicon."""
    brand = resolve_brand_icon(name, description, url)
    if brand:
        return brand
    if port is not None:
        port_brand = resolve_port_brand_icon(port)
        if port_brand:
            return port_brand

    if not fetch_remote or not url:
        return None
    parsed = urlparse(sanitize_service_url(url) or "")
    if parsed.scheme not in ("http", "https"):
        return None

    if host and port is not None:
        cached = _find_existing_cache(host, port)
        if cached:
            return cached

    data = await fetch_remote_favicon(url)
    if data and host and port is not None:
        content, ext = data
        return save_cached_icon(host, port, content, ext)
    return None


def _find_existing_cache(host: str, port: int) -> str | None:
    digest = hashlib.sha256(f"{host}:{port}".encode()).hexdigest()[:16]
    prefix = f"svc_{digest}"
    for path in ICONS_DIR.glob(f"{prefix}.*"):
        if path.is_file() and path.stat().st_size >= _MIN_ICON_BYTES:
            return f"/uploads/icons/{path.name}"
    return None


async def enrich_missing_service_icons(*, limit: int = 100) -> int:
    """Fetch and persist icons for services missing browser-safe watermarks."""
    updated = 0
    sem = asyncio.Semaphore(4)

    async with async_session() as db:
        result = await db.execute(select(Service))
        candidates = [svc for svc in result.scalars().all() if service_needs_icon_fetch(svc)]
        if limit:
            candidates = candidates[:limit]

        async def enrich_one(svc: Service) -> bool:
            async with sem:
                icon_url = await resolve_service_icon_url(
                    name=svc.name,
                    url=svc.url,
                    description=svc.description,
                    port=svc.port,
                    host=svc.host,
                    has_login=svc.has_login,
                    fetch_remote=True,
                )
            if not icon_url or icon_url == svc.icon_url:
                return False
            if not is_safe_browser_icon_url(icon_url):
                return False
            svc.icon_url = icon_url
            return True

        for svc in candidates:
            try:
                if await enrich_one(svc):
                    updated += 1
            except Exception:
                logger.exception("Icon enrich failed for %s:%s", svc.host, svc.port)

        if updated:
            await db.commit()
    return updated
