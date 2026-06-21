"""Service availability checks (ping / HTTP) without full network rescan."""

import asyncio
import logging
import re
from datetime import datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Service
from app.scanner import HTTP_TITLE_RE, _is_generic_title, get_local_ip, is_http_error_name
from app.url_utils import is_blocked_fetch_target, sanitize_service_url

logger = logging.getLogger("netdash.health")

_HTTP_STATUS_RE = re.compile(r"^HTTP\s+(\d{3})\b", re.IGNORECASE)
# Auth / redirect responses mean the host is reachable, not an outage.
_REACHABLE_HTTP_CODES = frozenset(range(300, 400)) | {401, 403}


def _http_detail_from_response(response: httpx.Response) -> str | None:
    if response.status_code in _REACHABLE_HTTP_CODES:
        return None
    if response.status_code < 400:
        return None
    body = response.text[:8192]
    title_match = HTTP_TITLE_RE.search(body)
    if title_match:
        title = re.sub(r"\s+", " ", title_match.group(1)).strip()
        if title and (_is_generic_title(title) or is_http_error_name(title)):
            return title[:128]
    return f"HTTP {response.status_code}"


async def _check_http_url(url: str) -> tuple[bool, str | None]:
    """Probe HTTP(S) URL; tolerate broken TLS sockets and HEAD 405."""
    if is_blocked_fetch_target(url):
        return False, None
    try:
        async with httpx.AsyncClient(
            verify=False,
            follow_redirects=True,
            timeout=3.0,
        ) as client:
            response = await client.get(
                url,
                headers={"User-Agent": "NetDash/1.0 Health"},
            )
            detail = _http_detail_from_response(response)
            return response.status_code < 500, detail
    except (httpx.HTTPError, asyncio.TimeoutError, AttributeError, OSError, RuntimeError):
        return False, None
    except Exception:
        logger.debug("HTTP health probe failed for %s", url, exc_info=True)
        return False, None


async def check_service_online(service: Service) -> tuple[bool, str | None]:
    host = (service.host or "").strip()
    if not host:
        return False, None
    try:
        local_ip = get_local_ip()
    except Exception:
        local_ip = None
    if local_ip and host == local_ip:
        return True, None
    protocol = (service.protocol or "http").lower()
    port = service.port if service.port is not None else 0
    url = sanitize_service_url((service.url or "").strip())
    if service.has_login:
        from app.scanner import _ping_host

        online = await _ping_host(host)
        return online, None
    if protocol in ("http", "https") and url:
        return await _check_http_url(url)
    if protocol == "host" or port == 0:
        from app.scanner import _ping_host

        online = await _ping_host(host)
        return online, None
    if protocol in ("http", "https"):
        scheme = "https" if port in (443, 8443, 9443, 6443, 4443) else "http"
        return await _check_http_url(f"{scheme}://{host}:{port}/")
    from app.scanner import _ping_host

    online = await _ping_host(host)
    return online, None


async def apply_health_result(
    db: AsyncSession,
    service: Service,
    online: bool,
    detail: str | None = None,
) -> None:
    now = datetime.now(timezone.utc)
    service.is_online = online
    service.last_checked = now
    if online:
        service.last_seen = now
        service.health_detail = None
    elif detail and (is_http_error_name(detail) or _HTTP_STATUS_RE.match(detail)):
        service.health_detail = detail[:128]


async def check_all_services(db: AsyncSession) -> int:
    result = await db.execute(select(Service))
    services = result.scalars().all()
    if not services:
        return 0

    sem = asyncio.Semaphore(settings.health_check_concurrency)

    async def check_one(svc: Service):
        async with sem:
            try:
                online, detail = await check_service_online(svc)
                await apply_health_result(db, svc, online, detail)
            except Exception:
                logger.warning("Health check failed for service %s (%s)", svc.id, svc.host, exc_info=True)
                await apply_health_result(db, svc, False)

    await asyncio.gather(*(check_one(s) for s in services))
    await db.commit()
    return len(services)
