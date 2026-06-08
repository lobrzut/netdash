"""Service availability checks (ping / HTTP) without full network rescan."""

import asyncio
import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Service
from app.scanner import _ping_host, get_local_ip

logger = logging.getLogger("netdash.health")


async def _check_http_url(url: str) -> bool:
    """Probe HTTP(S) URL; tolerate broken TLS sockets and HEAD 405."""
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
            return response.status_code < 500
    except (httpx.HTTPError, asyncio.TimeoutError, AttributeError, OSError, RuntimeError):
        return False
    except Exception:
        logger.debug("HTTP health probe failed for %s", url, exc_info=True)
        return False


async def check_service_online(service: Service) -> bool:
    host = (service.host or "").strip()
    if not host:
        return False
    try:
        local_ip = get_local_ip()
    except Exception:
        local_ip = None
    if local_ip and host == local_ip:
        return True
    protocol = (service.protocol or "http").lower()
    port = service.port if service.port is not None else 0
    url = (service.url or "").strip()
    if protocol in ("http", "https") and url:
        return await _check_http_url(url)
    if protocol == "host" or port == 0:
        return await _ping_host(host)
    if protocol in ("http", "https"):
        scheme = "https" if port in (443, 8443, 9443, 6443, 4443) else "http"
        return await _check_http_url(f"{scheme}://{host}:{port}/")
    return await _ping_host(host)


async def apply_health_result(db: AsyncSession, service: Service, online: bool) -> None:
    now = datetime.now(timezone.utc)
    service.is_online = online
    service.last_checked = now
    if online:
        service.last_seen = now


async def check_all_services(db: AsyncSession) -> int:
    result = await db.execute(select(Service))
    services = result.scalars().all()
    if not services:
        return 0

    sem = asyncio.Semaphore(10)

    async def check_one(svc: Service):
        async with sem:
            try:
                online = await check_service_online(svc)
                await apply_health_result(db, svc, online)
            except Exception:
                logger.warning("Health check failed for service %s (%s)", svc.id, svc.host, exc_info=True)
                await apply_health_result(db, svc, False)

    await asyncio.gather(*(check_one(s) for s in services))
    await db.commit()
    return len(services)
