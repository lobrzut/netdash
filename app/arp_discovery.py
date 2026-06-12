"""Background ARP discovery (WatchYourLAN / Pi.Alert / NetAlertX style).

Uses arp-scan on a timer — no TCP port sweep during the discovery cycle.
Optional light port probe for newly seen hosts only (one host at a time).
"""

from __future__ import annotations

import asyncio
import ipaddress
import logging
import re
import shutil
import socket
import subprocess
from datetime import datetime, timezone
from typing import Any

from app.config import settings
from sqlalchemy import select

from app.database import async_session
from app.discovery_import import import_discovery_hosts
from app.models import AppSettings
from app.scanner import (
    SAFE_WEB_PORTS,
    _check_port,
    _identify_service,
    get_local_network,
    resolve_scan_cidrs,
)
from app.schemas import DiscoveryHostEntry

logger = logging.getLogger("netdash")

MAC_RE = re.compile(r"([0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}")
IP_NEIGH_RE = re.compile(
    r"^(\d+\.\d+\.\d+\.\d+)\s+dev\s+\S+\s+(?:lladdr\s+)?([0-9a-f:]{17})(?:\s|$)",
    re.MULTILINE,
)

_arp_task: asyncio.Task | None = None
_known_ips: set[str] = set()
_state: dict[str, Any] = {
    "enabled": False,
    "running": False,
    "last_cycle_at": None,
    "last_cycle_hosts": 0,
    "last_error": None,
    "cidr": None,
}


def _normalize_mac(mac: str) -> str:
    return mac.replace("-", ":").upper()


def _resolve_hostname(ip: str) -> str | None:
    try:
        name, _, _ = socket.gethostbyaddr(ip)
        if name and name != ip:
            return name.split(".")[0] or name
    except (socket.herror, socket.gaierror, OSError):
        return None
    return None


def _parse_arp_scan_output(stdout: str) -> list[DiscoveryHostEntry]:
    hosts: dict[str, DiscoveryHostEntry] = {}
    for line in stdout.splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        ip = parts[0]
        try:
            ipaddress.ip_address(ip)
        except ValueError:
            continue
        mac_match = MAC_RE.search(line)
        if not mac_match:
            continue
        mac = _normalize_mac(mac_match.group(0))
        hostname = parts[-1] if len(parts) >= 3 and not parts[-1].startswith("(") else None
        if hostname and hostname == ip:
            hostname = None
        hosts[ip] = DiscoveryHostEntry(ip=ip, mac=mac, hostname=hostname, online=True)
    return list(hosts.values())


def _run_arp_scan_subprocess(cidr: str) -> list[DiscoveryHostEntry]:
    """Synchronous arp-scan — rate-limited like WatchYourLAN."""
    if not shutil.which("arp-scan"):
        logger.warning("arp-scan not found — install arp-scan in container image")
        return _run_ip_neigh_fallback(cidr)

    cmd = [
        "arp-scan",
        cidr.strip(),
        "--interval=100ms",
        "--retry=1",
        "--ignoredups",
        "--quiet",
    ]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=max(120, settings.arp_interval),
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        logger.warning("arp-scan failed for %s: %s", cidr, exc)
        return _run_ip_neigh_fallback(cidr)

    if proc.returncode not in (0, 1):
        stderr = (proc.stderr or "").strip()[:200]
        logger.warning("arp-scan exit %s for %s: %s", proc.returncode, cidr, stderr)
        if not proc.stdout:
            return _run_ip_neigh_fallback(cidr)

    entries = _parse_arp_scan_output(proc.stdout or "")
    logger.info("arp-scan: %s host(s) in %s", len(entries), cidr)
    return entries


def _run_ip_neigh_fallback(cidr: str) -> list[DiscoveryHostEntry]:
    if not shutil.which("ip"):
        return []
    try:
        network = ipaddress.ip_network(cidr.strip(), strict=False)
    except ValueError:
        return []
    try:
        proc = subprocess.run(
            ["ip", "neigh", "show"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except OSError:
        return []
    hosts: dict[str, DiscoveryHostEntry] = {}
    for match in IP_NEIGH_RE.finditer(proc.stdout or ""):
        ip, mac = match.group(1), _normalize_mac(match.group(2))
        try:
            if ipaddress.ip_address(ip) not in network:
                continue
        except ValueError:
            continue
        hosts[ip] = DiscoveryHostEntry(
            ip=ip,
            mac=mac,
            hostname=_resolve_hostname(ip),
            online=True,
        )
    logger.info("ip neigh fallback: %s host(s) in %s", len(hosts), cidr)
    return list(hosts.values())


async def _probe_new_host(ip: str) -> None:
    """Light port probe for one new host — safe ports only, sequential."""
    from app.main import _upsert_service

    sem = asyncio.Semaphore(1)
    for port in SAFE_WEB_PORTS:
        if await _check_port(ip, port, sem):
            try:
                service = await _identify_service(ip, port)
                await _upsert_service(service)
            except Exception:
                logger.exception("ARP new-host probe failed for %s:%s", ip, port)
            await asyncio.sleep(settings.arp_probe_delay)
            return
        await asyncio.sleep(settings.arp_probe_delay * 0.5)


async def _resolve_arp_cidr() -> str:
    async with async_session() as db:
        result = await db.execute(select(AppSettings).limit(1))
        app_settings = result.scalar_one_or_none()
        scan_default = app_settings.scan_cidr_default if app_settings else None
    cidrs = resolve_scan_cidrs(None, scan_default)
    return cidrs[0] if cidrs else get_local_network()


async def run_arp_discovery_cycle() -> int:
    """Single ARP discovery cycle. Returns host count."""
    global _known_ips

    if _state["running"]:
        logger.debug("ARP discovery cycle skipped — previous still running")
        return _state.get("last_cycle_hosts") or 0

    _state["running"] = True
    try:
        cidr = await _resolve_arp_cidr()
        _state["cidr"] = cidr
        entries = await asyncio.to_thread(_run_arp_scan_subprocess, cidr)
        if not entries:
            _state["last_cycle_at"] = datetime.now(timezone.utc)
            _state["last_cycle_hosts"] = 0
            _state["last_error"] = None
            return 0

        seen_ips = {e.ip for e in entries}
        new_ips = sorted(seen_ips - _known_ips)
        _known_ips = seen_ips

        async with async_session() as db:
            await import_discovery_hosts(
                db,
                entries,
                source="arp-scan",
                source_hostname="netdash",
                mark_missing_offline=True,
            )

        if settings.arp_probe_new_hosts and new_ips:
            for ip in new_ips[: settings.arp_probe_max_hosts]:
                await _probe_new_host(ip)
                await asyncio.sleep(settings.arp_probe_delay)

        count = len(seen_ips)
        _state["last_cycle_at"] = datetime.now(timezone.utc)
        _state["last_cycle_hosts"] = count
        _state["last_error"] = None
        logger.info("ARP discovery cycle done: %s host(s) in %s (%s new)", count, cidr, len(new_ips))
        return count
    except Exception as exc:
        _state["last_error"] = str(exc)[:256]
        logger.exception("ARP discovery cycle error")
        raise
    finally:
        _state["running"] = False


async def _arp_discovery_loop() -> None:
    """Background scheduler — runs arp-scan every NETDASH_ARP_INTERVAL seconds."""
    _state["enabled"] = True
    startup_delay = max(5, min(60, settings.arp_interval // 6))
    logger.info(
        "ARP discovery scheduler started (interval=%ss, cidr=%s, probe_new=%s)",
        settings.arp_interval,
        settings.scan_cidr or get_local_network(),
        settings.arp_probe_new_hosts,
    )
    await asyncio.sleep(startup_delay)

    while True:
        try:
            await run_arp_discovery_cycle()
        except asyncio.CancelledError:
            raise
        except Exception:
            pass
        await asyncio.sleep(max(60, settings.arp_interval))


def get_arp_discovery_status() -> dict[str, Any]:
    return {
        "enabled": _state.get("enabled", False),
        "running": _state.get("running", False),
        "last_cycle_at": _state.get("last_cycle_at"),
        "last_cycle_hosts": _state.get("last_cycle_hosts", 0),
        "last_error": _state.get("last_error"),
        "cidr": _state.get("cidr"),
        "interval_sec": settings.arp_interval,
    }


def start_arp_discovery_scheduler() -> asyncio.Task | None:
    """Start background ARP discovery if discovery_mode=arp."""
    global _arp_task
    if settings.scan_disabled or settings.discovery_mode != "arp":
        return None
    if _arp_task and not _arp_task.done():
        return _arp_task
    _arp_task = asyncio.create_task(_arp_discovery_loop())
    return _arp_task


async def stop_arp_discovery_scheduler() -> None:
    global _arp_task
    if _arp_task:
        _arp_task.cancel()
        try:
            await _arp_task
        except asyncio.CancelledError:
            pass
        _arp_task = None
    _state["enabled"] = False
