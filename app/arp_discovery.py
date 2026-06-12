"""Background ARP discovery (WatchYourLAN / Pi.Alert / NetAlertX style).

Uses arp-scan on a timer — no TCP port sweep during the discovery cycle.
Falls back to ip neigh, ping sweep, and quick-scan TCP when arp-scan returns 0.
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
import time
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
    discover_live_hosts_quick,
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
IFACE_FROM_ROUTE_RE = re.compile(r"\bdev\s+(\S+)")

_arp_task: asyncio.Task | None = None
_known_ips: set[str] = set()
_state: dict[str, Any] = {
    "enabled": False,
    "running": False,
    "last_cycle_at": None,
    "last_cycle_hosts": 0,
    "last_error": None,
    "cidr": None,
    "iface": None,
    "last_sources": None,
}


def _normalize_mac(mac: str) -> str:
    return mac.replace("-", ":").upper()


def _parse_extra_hosts() -> list[str]:
    raw = (settings.arp_extra_hosts or "").strip()
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


def _detect_lan_interface(cidr: str) -> str | None:
    """Resolve LAN interface: NETDASH_ARP_IFACE or `ip route get <gateway>`."""
    if settings.arp_iface:
        return settings.arp_iface.strip()

    if not shutil.which("ip"):
        return None

    try:
        network = ipaddress.ip_network(cidr.strip(), strict=False)
        probe = str(network.network_address + 1)
    except ValueError:
        probe = "192.168.1.1"

    try:
        proc = subprocess.run(
            ["ip", "route", "get", probe],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except OSError:
        return None

    match = IFACE_FROM_ROUTE_RE.search(proc.stdout or "")
    if not match:
        return None
    iface = match.group(1)
    return iface if iface != "lo" else None


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


def _build_arp_scan_cmd(cidr: str, iface: str | None) -> list[str]:
    cmd = [
        "arp-scan",
        cidr.strip(),
        "--interval=100ms",
        "--retry=1",
        "--ignoredups",
        "--quiet",
    ]
    if iface:
        cmd[1:1] = ["-I", iface]
    return cmd


def _run_arp_scan_only(cidr: str, iface: str | None) -> list[DiscoveryHostEntry]:
    """Synchronous arp-scan — rate-limited like WatchYourLAN."""
    if not shutil.which("arp-scan"):
        logger.warning("arp-scan not found — install arp-scan in container image")
        return []

    cmd = _build_arp_scan_cmd(cidr, iface)
    logger.info("arp-scan cmd: %s", " ".join(cmd))
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=max(120, settings.arp_interval),
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        logger.warning("arp-scan failed for %s (iface=%s): %s", cidr, iface, exc)
        return []

    entries = _parse_arp_scan_output(proc.stdout or "")
    if not entries:
        stderr = (proc.stderr or "").strip()
        if stderr:
            logger.warning(
                "arp-scan: 0 host(s) in %s (iface=%s, exit=%s) stderr: %s",
                cidr,
                iface,
                proc.returncode,
                stderr[:500],
            )
        else:
            logger.warning(
                "arp-scan: 0 host(s) in %s (iface=%s, exit=%s)",
                cidr,
                iface,
                proc.returncode,
            )
    else:
        logger.info("arp-scan: %s host(s) in %s (iface=%s)", len(entries), cidr, iface)
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
    logger.info("ip neigh: %s host(s) in %s", len(hosts), cidr)
    return list(hosts.values())


def _ping_host_sync(ip: str) -> bool:
    cmd = ["ping", "-c", "1", "-W", "1", ip]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=5, check=False)
        return proc.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False


def _tcp_reachable_sync(ip: str) -> bool:
    timeout = min(settings.scan_timeout, 1.5)
    for port in SAFE_WEB_PORTS:
        try:
            with socket.create_connection((ip, port), timeout=timeout):
                return True
        except OSError:
            continue
    return False


def _host_is_live_sync(ip: str) -> bool:
    return _ping_host_sync(ip) or _tcp_reachable_sync(ip)


def _run_ping_sweep_fallback(cidr: str) -> list[DiscoveryHostEntry]:
    """Rate-limited ping (+ TCP) sweep when arp-scan returns nothing."""
    if not settings.arp_ping_fallback:
        return []
    try:
        network = ipaddress.ip_network(cidr.strip(), strict=False)
    except ValueError:
        return []

    max_hosts = max(1, settings.arp_ping_max_hosts)
    hosts = [str(host) for host in network.hosts()][:max_hosts]
    found: list[DiscoveryHostEntry] = []
    delay = max(0.05, settings.arp_ping_delay)

    logger.info("ping sweep fallback: probing up to %s host(s) in %s", len(hosts), cidr)
    for ip in hosts:
        if _host_is_live_sync(ip):
            found.append(
                DiscoveryHostEntry(
                    ip=ip,
                    mac=None,
                    hostname=_resolve_hostname(ip),
                    online=True,
                )
            )
        time.sleep(delay)

    logger.info("ping sweep fallback: %s live host(s) in %s", len(found), cidr)
    return found


def _probe_explicit_hosts(ips: list[str], cidr: str) -> list[DiscoveryHostEntry]:
    """Always probe NETDASH_ARP_EXTRA_HOSTS — ping/TCP even when arp-scan works."""
    try:
        network = ipaddress.ip_network(cidr.strip(), strict=False)
    except ValueError:
        network = None

    found: list[DiscoveryHostEntry] = []
    for ip in ips:
        try:
            ipaddress.ip_address(ip)
        except ValueError:
            continue
        if network is not None:
            try:
                if ipaddress.ip_address(ip) not in network:
                    continue
            except ValueError:
                continue
        if not _host_is_live_sync(ip):
            logger.debug("extra host probe: %s not reachable", ip)
            continue
        found.append(
            DiscoveryHostEntry(
                ip=ip,
                mac=None,
                hostname=_resolve_hostname(ip),
                online=True,
            )
        )
        logger.info("extra host probe: %s is live", ip)
    return found


def _merge_entries(*groups: list[DiscoveryHostEntry]) -> list[DiscoveryHostEntry]:
    merged: dict[str, DiscoveryHostEntry] = {}
    for group in groups:
        for entry in group:
            existing = merged.get(entry.ip)
            if existing is None:
                merged[entry.ip] = entry
                continue
            if not existing.mac and entry.mac:
                existing.mac = entry.mac
            if not existing.hostname and entry.hostname:
                existing.hostname = entry.hostname
            existing.online = entry.online is not False
    return list(merged.values())


def _discover_hosts_sync(cidr: str) -> tuple[list[DiscoveryHostEntry], dict[str, Any]]:
    """arp-scan → ip neigh → ping sweep → explicit extra hosts."""
    iface = _detect_lan_interface(cidr)
    sources: dict[str, int] = {}

    arp_entries = _run_arp_scan_only(cidr, iface)
    sources["arp-scan"] = len(arp_entries)

    neigh_entries = _run_ip_neigh_fallback(cidr)
    sources["ip-neigh"] = len(neigh_entries)

    ping_entries: list[DiscoveryHostEntry] = []
    if len(arp_entries) == 0 and settings.arp_ping_fallback:
        ping_entries = _run_ping_sweep_fallback(cidr)
        sources["ping-sweep"] = len(ping_entries)

    extra_entries = _probe_explicit_hosts(_parse_extra_hosts(), cidr)
    if extra_entries or _parse_extra_hosts():
        sources["extra-hosts"] = len(extra_entries)

    entries = _merge_entries(arp_entries, neigh_entries, ping_entries, extra_entries)
    stats = {"iface": iface, "sources": sources}
    logger.info(
        "ARP discovery sync: %s host(s) in %s iface=%s sources=%s",
        len(entries),
        cidr,
        iface,
        sources,
    )
    return entries, stats


async def _quick_scan_fallback(cidr: str) -> list[DiscoveryHostEntry]:
    """Quick-scan style TCP/ping discovery when all sync methods return 0."""
    extra = _parse_extra_hosts()
    live = await discover_live_hosts_quick(cidr, extra_hosts=extra)
    entries = [
        DiscoveryHostEntry(ip=ip, mac=None, hostname=_resolve_hostname(ip), online=True)
        for ip in live
    ]
    logger.info("quick-scan fallback: %s live host(s) in %s", len(entries), cidr)
    return entries


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

        entries, stats = await asyncio.to_thread(_discover_hosts_sync, cidr)
        _state["iface"] = stats.get("iface")
        _state["last_sources"] = stats.get("sources")

        if not entries:
            entries = await _quick_scan_fallback(cidr)
            sources = dict(stats.get("sources") or {})
            sources["quick-scan"] = len(entries)
            _state["last_sources"] = sources

        if not entries:
            _state["last_cycle_at"] = datetime.now(timezone.utc)
            _state["last_cycle_hosts"] = 0
            _state["last_error"] = None
            logger.warning(
                "ARP discovery cycle: no hosts found in %s (iface=%s, sources=%s)",
                cidr,
                stats.get("iface"),
                stats.get("sources"),
            )
            return 0

        seen_ips = {e.ip for e in entries}
        new_ips = sorted(seen_ips - _known_ips)
        _known_ips = seen_ips

        arp_count = (stats.get("sources") or {}).get("arp-scan", 0)
        mark_offline = arp_count > 0

        async with async_session() as db:
            await import_discovery_hosts(
                db,
                entries,
                source="arp-scan",
                source_hostname="netdash",
                mark_missing_offline=mark_offline,
            )

        if settings.arp_probe_new_hosts and new_ips:
            for ip in new_ips[: settings.arp_probe_max_hosts]:
                await _probe_new_host(ip)
                await asyncio.sleep(settings.arp_probe_delay)

        count = len(seen_ips)
        _state["last_cycle_at"] = datetime.now(timezone.utc)
        _state["last_cycle_hosts"] = count
        _state["last_error"] = None
        logger.info(
            "ARP discovery cycle done: %s host(s) in %s iface=%s sources=%s (%s new)",
            count,
            cidr,
            stats.get("iface"),
            _state.get("last_sources"),
            len(new_ips),
        )
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
        "ARP discovery scheduler started (interval=%ss, cidr=%s, iface=%s, probe_new=%s)",
        settings.arp_interval,
        settings.scan_cidr or get_local_network(),
        settings.arp_iface or "auto",
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
        "iface": _state.get("iface"),
        "last_sources": _state.get("last_sources"),
        "interval_sec": settings.arp_interval,
        "extra_hosts": _parse_extra_hosts(),
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
