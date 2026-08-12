"""Service availability checks (ping / HTTP) without full network rescan."""

import asyncio
import logging
import random
import re
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Service
from app.scanner import HTTP_TITLE_RE, _is_generic_title, get_local_ip, is_http_error_name
from app.url_utils import is_blocked_fetch_target, sanitize_service_url

logger = logging.getLogger("netdash.health")

# Serialize full-table health passes — concurrent loop + POST /api/services/health-check
# used to race on the same AsyncSession rows (StaleDataError).
_health_check_lock = asyncio.Lock()

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


def _is_host_only(service: Service) -> bool:
    port = service.port if service.port is not None else 0
    protocol = (service.protocol or "http").lower()
    return protocol == "host" or port == 0


async def _check_tcp_port(host: str, port: int) -> bool:
    if port < 1 or port > 65535:
        return False
    try:
        conn = asyncio.open_connection(host, port)
        _, writer = await asyncio.wait_for(conn, timeout=3.0)
        writer.close()
        await writer.wait_closed()
        return True
    except (asyncio.TimeoutError, OSError, ConnectionRefusedError):
        return False


async def check_service_online(service: Service) -> tuple[bool, str | None]:
    host = (service.host or "").strip()
    if not host:
        return False, None
    protocol = (service.protocol or "http").lower()
    port = service.port if service.port is not None else 0
    url = sanitize_service_url((service.url or "").strip())

    if _is_host_only(service):
        if host in ("127.0.0.1", "localhost"):
            return True, None
        try:
            local_ip = get_local_ip()
        except Exception:
            local_ip = None
        if local_ip and host == local_ip:
            return True, None
        from app.scanner import _ping_host

        return await _ping_host(host), None

    if service.has_login:
        if protocol in ("http", "https") and url:
            return await _check_http_url(url)
        if port > 0:
            return await _check_tcp_port(host, port), None
        from app.scanner import _ping_host

        return await _ping_host(host), None

    if protocol in ("http", "https") and url:
        return await _check_http_url(url)
    if protocol in ("http", "https") and port > 0:
        scheme = "https" if port in (443, 8443, 9443, 6443, 4443) else "http"
        return await _check_http_url(f"{scheme}://{host}:{port}/")
    if protocol == "tcp" and port > 0:
        return await _check_tcp_port(host, port), None
    from app.scanner import _ping_host

    return await _ping_host(host), None


async def apply_health_result(
    db: AsyncSession,
    service: Service,
    online: bool,
    detail: str | None = None,
) -> None:
    now = datetime.now(timezone.utc)
    threshold = max(1, settings.health_offline_after_failures)
    service.last_checked = now
    if online:
        service.health_fail_streak = 0
        service.is_online = True
        service.last_seen = now
        service.health_detail = None
        return

    streak = (service.health_fail_streak or 0) + 1
    service.health_fail_streak = streak
    if streak >= threshold:
        service.is_online = False
        if detail and (is_http_error_name(detail) or _HTTP_STATUS_RE.match(detail)):
            service.health_detail = detail[:128]


def effective_stale_remove_days(db_days: int) -> int:
    """UI/DB value wins when > 0; otherwise fall back to NETDASH_STALE_REMOVE_DAYS."""
    if db_days and db_days > 0:
        return db_days
    return max(0, settings.stale_remove_days)


def _stale_reference_time(service: Service) -> datetime | None:
    """Last time the service was known online (fallback: last health probe)."""
    ref = service.last_seen or service.last_checked
    if ref is None:
        return None
    if ref.tzinfo is None:
        return ref.replace(tzinfo=timezone.utc)
    return ref


def _is_stale_service_candidate(service: Service) -> bool:
    if service.is_online:
        return False
    if service.pinned or service.customized:
        return False
    if not service.auto_discovered:
        return False
    return True


async def purge_stale_services(db: AsyncSession, stale_days: int) -> int:
    """Remove auto-discovered services offline longer than stale_days. 0 = disabled."""
    if stale_days <= 0:
        return 0
    now = datetime.now(timezone.utc)
    threshold = timedelta(days=stale_days)
    result = await db.execute(select(Service))
    to_delete: list[Service] = []
    for service in result.scalars().all():
        if not _is_stale_service_candidate(service):
            continue
        ref = _stale_reference_time(service)
        if ref is None:
            continue
        if now - ref > threshold:
            to_delete.append(service)
    for service in to_delete:
        await db.delete(service)
    if to_delete:
        await db.commit()
        logger.info("Removed %s stale offline services (older than %s days)", len(to_delete), stale_days)
    return len(to_delete)


async def check_all_services(db: AsyncSession) -> int:
    async with _health_check_lock:
        result = await db.execute(select(Service))
        services = result.scalars().all()
        if not services:
            return 0

        sem = asyncio.Semaphore(settings.health_check_concurrency)
        # IPS-friendly: serialize probes to the SAME host (+jittered delay) so several services
        # sharing one host aren't probed as a simultaneous multi-port burst (IPS port-scan flag).
        host_gates: dict[str, asyncio.Semaphore] = {}
        per_host = max(1, settings.effective_port_parallel_per_host)
        delay = settings.effective_ports_per_host_delay
        jitter = settings.ports_per_host_jitter if settings.ips_friendly else 0.0

        def _host_gate(host: str) -> asyncio.Semaphore | None:
            if not settings.ips_friendly:
                return None
            return host_gates.setdefault(host, asyncio.Semaphore(per_host))

        async def _run(svc: Service) -> None:
            try:
                online, detail = await check_service_online(svc)
                await apply_health_result(db, svc, online, detail)
            except Exception:
                logger.warning("Health check failed for service %s (%s)", svc.id, svc.host, exc_info=True)
                await apply_health_result(db, svc, False)

        async def check_one(svc: Service):
            async with sem:
                gate = _host_gate((svc.host or "").strip())
                if gate is None:
                    await _run(svc)
                    return
                async with gate:
                    if delay > 0:
                        await asyncio.sleep(delay + (random.random() * jitter if jitter > 0 else 0.0))
                    await _run(svc)

        await asyncio.gather(*(check_one(s) for s in services))
        await db.commit()
        return len(services)
