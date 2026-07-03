"""Adaptive tiered discovery — TCP-first → ARP enrichment (profile-aware).

Tier 0: hardware profile (weak / normal / strong)
Tier 1: TCP connect sweep on common ports — ANY open port = host live + auto service
Tier 2: arp-scan / ip neigh for MAC enrichment only (not a discovery gate)
Tier 3: HTTP health checks — independent loop in main.py (unchanged)

Weak QNAP: dual /28 chunks per cycle (rotated + opposite half) — full /24 in ~40 min.
"""

from __future__ import annotations

import asyncio
import ipaddress
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.arp_discovery import (
    _detect_lan_interface,
    _merge_entries,
    _parse_extra_hosts,
    _probe_explicit_hosts_with_ports,
    _resolve_hostname,
    _run_arp_scan_only,
    _run_ip_neigh_fallback,
)
from app.config import settings
from app.database import async_session
from app.discovery_import import import_discovery_hosts
from app.models import AppSettings
from app.scanner import (
    SERVICE_PORTS,
    TCP_DISCOVERY_PRIMARY_PORTS,
    _check_port,
    _identify_service,
    _probe_host_ports,
    get_local_network,
    parse_cidr,
    resolve_scan_cidrs,
)
from app.schemas import DiscoveryHostEntry

logger = logging.getLogger("netdash")

_icon_enrich_task: asyncio.Task | None = None


def _schedule_icon_enrich(services_hint: int = 0) -> None:
    """Background favicon fetch for auto-discovered services missing watermarks."""
    global _icon_enrich_task

    async def _run() -> None:
        await asyncio.sleep(2)
        try:
            from app.enrich import enrich_service_icons

            limit = max(20, min(150, services_hint + 10))
            count = await enrich_service_icons(limit=limit)
            if count:
                logger.info("Discovery icon enrich updated %s service(s)", count)
        except Exception:
            logger.exception("Discovery icon enrich failed")

    if _icon_enrich_task and not _icon_enrich_task.done():
        return
    _icon_enrich_task = asyncio.create_task(_run())

ARP_BROKEN_STREAK = 3
WEAK_CHUNKS_PER_CYCLE = 2

_task: asyncio.Task | None = None
_known_ips: set[str] = set()
_arp_zero_streak = 0
_chunk_index = 0
_cidr_index = 0
_profile: str | None = None

_state: dict[str, Any] = {
    "enabled": False,
    "running": False,
    "mode": "adaptive",
    "profile": None,
    "current_tier": None,
    "last_cycle_at": None,
    "last_cycle_hosts": 0,
    "last_status_line": None,
    "last_tiers": None,
    "last_error": None,
    "cidr": None,
    "iface": None,
    "arp_skipped": False,
    "interval_sec": None,
    "chunk_index": 0,
    "chunk_index_secondary": None,
    "chunk_total": 0,
    "cidr_index": 0,
    "cidr_total": 0,
    "active_cidr": None,
}


@dataclass(frozen=True)
class ProfileConfig:
    name: str
    interval_sec: int
    tcp_parallel: int
    port_parallel: int
    tier_delay_sec: float
    max_hosts: int
    chunk_prefix: int


_PROFILES: dict[str, ProfileConfig] = {
    "weak": ProfileConfig("weak", 600, 4, 2, 3.0, 8, 28),
    "normal": ProfileConfig("normal", 180, 16, 8, 1.0, 256, 24),
    "strong": ProfileConfig("strong", 120, 32, 16, 0.5, 256, 24),
}


def _read_mem_total_kb() -> int | None:
    try:
        with open("/proc/meminfo", encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("MemTotal:"):
                    return int(line.split()[1])
    except OSError:
        return None
    return None


def detect_hardware_profile() -> str:
    """Tier 0 — auto-detect or honor NETDASH_DISCOVERY_PROFILE."""
    raw = (settings.discovery_profile or "auto").strip().lower()
    if raw in _PROFILES:
        return raw

    if settings.scan_safe_mode:
        return "weak"

    mem_kb = _read_mem_total_kb()
    if mem_kb is not None and mem_kb < 2_000_000:
        return "weak"

    cpus = os.cpu_count() or 1
    if cpus >= 4 and not settings.scan_safe_mode:
        return "strong"

    return "normal"


def get_profile_config(profile: str | None = None) -> ProfileConfig:
    name = profile or _profile or detect_hardware_profile()
    return _PROFILES.get(name, _PROFILES["normal"])


def effective_interval(profile: ProfileConfig) -> int:
    if settings.discovery_interval:
        return max(60, settings.discovery_interval)
    return profile.interval_sec


def format_status_line(tiers: dict[str, int], profile: str) -> str:
    services_n = tiers.get("services", 0)
    hosts_n = tiers.get("tcp", 0)
    chunk_idx = tiers.get("chunk_index")
    chunk_idx2 = tiers.get("chunk_index_secondary")
    chunk_total = tiers.get("chunk_total")

    if chunk_total and chunk_total > 1 and chunk_idx:
        if chunk_idx2 and chunk_idx2 != chunk_idx:
            chunk_label = f"chunk {chunk_idx}+{chunk_idx2}/{chunk_total}"
        else:
            chunk_label = f"chunk {chunk_idx}/{chunk_total}"
        return (
            f"Skan TCP: {chunk_label}, "
            f"znaleziono {services_n} serwisów ({hosts_n} hostów, profil: {profile})"
        )
    return f"Skan TCP: {hosts_n} hostów, {services_n} serwisów (profil: {profile})"


def _select_cycle_cidr(cidr: str, profile: ProfileConfig) -> str:
    """Deprecated wrapper — returns first CIDR from _select_cycle_cidrs."""
    return _select_cycle_cidrs(cidr, profile)[0]


def _select_cycle_cidrs(cidr: str, profile: ProfileConfig) -> list[str]:
    """Rotate /28 chunks — auto mode never scans a full /24+ in one cycle."""
    global _chunk_index
    wide = cidr.strip()
    try:
        wide_net = ipaddress.ip_network(wide, strict=False)
    except ValueError:
        return [cidr]

    chunk_pfx = (
        settings.auto_discovery_chunk_prefix
        if settings.auto_discovery_always_chunk
        else profile.chunk_prefix
    )
    force_chunk = settings.auto_discovery_always_chunk or profile.name == "weak"

    if not force_chunk or wide_net.prefixlen >= chunk_pfx:
        _state["chunk_total"] = 1
        _state["chunk_index"] = 1
        _state["chunk_index_secondary"] = None
        return [str(wide_net)]

    all_chunks = [str(c) for c in wide_net.subnets(new_prefix=chunk_pfx)]
    if not all_chunks:
        return [wide]

    chunk_total = len(all_chunks)
    primary_idx = _chunk_index % chunk_total

    if profile.name == "weak" and chunk_total > 1 and settings.weak_dual_chunk:
        secondary_idx = (primary_idx + chunk_total // 2) % chunk_total
        indices = [primary_idx]
        if secondary_idx != primary_idx:
            indices.append(secondary_idx)
        selected = [all_chunks[i] for i in indices]
        _chunk_index += WEAK_CHUNKS_PER_CYCLE
        _state["chunk_total"] = chunk_total
        _state["chunk_index"] = primary_idx + 1
        _state["chunk_index_secondary"] = (
            secondary_idx + 1 if secondary_idx != primary_idx else None
        )
        chunk_log = (
            f"{_state['chunk_index']}+{_state['chunk_index_secondary']}"
            if _state["chunk_index_secondary"]
            else str(_state["chunk_index"])
        )
        logger.info(
            "Adaptive discovery: profile=%s chunk %s/%s %s (from %s)",
            profile.name,
            chunk_log,
            chunk_total,
            selected,
            wide,
        )
        return selected

    selected = all_chunks[primary_idx]
    _chunk_index += 1
    _state["chunk_total"] = chunk_total
    _state["chunk_index"] = primary_idx + 1
    _state["chunk_index_secondary"] = None

    logger.info(
        "Adaptive discovery: profile=%s chunk %s/%s %s (from %s)",
        profile.name,
        _state["chunk_index"],
        _state["chunk_total"],
        selected,
        wide,
    )
    return [selected]


def _should_mark_missing_offline(
    scanned_cidrs: list[str],
    tiers: dict[str, int],
    seen_count: int,
) -> bool:
    """TCP chunk discovery never mass-offlines — health checker owns service status."""
    return False


AUTO_PORT_PROBE_BATCH = 10


async def _probe_extra_ports(
    ip: str,
    host_ports: list[int],
    port_sem: asyncio.Semaphore,
    profile: ProfileConfig,
) -> list[int]:
    """Gradual SERVICE_PORTS probe on a live host — avoids TCP floods."""
    extra_ports = [p for p in SERVICE_PORTS if p not in host_ports]
    if not extra_ports:
        return host_ports
    found = list(host_ports)
    if settings.ips_friendly:
        # Spread the ~180 extra ports over time (1 port/host at a time, jittered) so endpoint
        # IPS (Symantec SEP etc.) never sees a many-port burst from us and blocks our IP.
        found.extend(await _probe_host_ports(ip, extra_ports, global_sem=port_sem))
        return found
    batch = max(2, profile.port_parallel)
    pause = profile.tier_delay_sec * (0.5 if settings.auto_discovery_all_ports else 0.15)
    for i in range(0, len(extra_ports), batch):
        chunk = extra_ports[i : i + batch]
        checks = await asyncio.gather(*(_check_port(ip, port, port_sem) for port in chunk))
        found.extend(port for port, ok in zip(chunk, checks) if ok)
        await asyncio.sleep(pause)
    return found


async def _tier1_tcp_discovery(
    cidr: str,
    profile: ProfileConfig,
) -> tuple[set[str], dict[str, list[int]], int]:
    """TCP-first — any open port on common list means host is live; upsert all services."""
    from app.main import _upsert_service

    _state["current_tier"] = "tcp"
    candidates = parse_cidr(cidr, max_hosts=profile.max_hosts)
    live: set[str] = set()
    open_ports_by_ip: dict[str, list[int]] = {}
    services_created = 0

    ip_sem = asyncio.Semaphore(profile.tcp_parallel)
    port_sem = asyncio.Semaphore(profile.port_parallel)
    batch = profile.tcp_parallel

    async def probe_host(ip: str) -> None:
        nonlocal services_created
        async with ip_sem:
            # IPS-friendly per-host probing (1 port at a time, jittered) so we never burst
            # many distinct ports at one host — the classic port-scan signature IPS blocks.
            host_ports = await _probe_host_ports(
                ip, list(TCP_DISCOVERY_PRIMARY_PORTS), global_sem=port_sem
            )
            if not host_ports:
                return

            live.add(ip)
            if settings.auto_discovery_all_ports:
                host_ports = await _probe_extra_ports(ip, host_ports, port_sem, profile)
            elif settings.scan_all_ports:
                extra_ports = [p for p in SERVICE_PORTS if p not in host_ports]
                extra_open = await _probe_host_ports(ip, extra_ports, global_sem=port_sem)
                host_ports = host_ports + extra_open

            open_ports_by_ip[ip] = host_ports
            logger.info("TCP discovery: %s live ports=%s", ip, host_ports)

            for port in host_ports:
                try:
                    service = await _identify_service(ip, port)
                    await _upsert_service(service)
                    services_created += 1
                except Exception:
                    logger.exception("TCP discovery service upsert failed for %s:%s", ip, port)

            await asyncio.sleep(profile.tier_delay_sec * 0.1)

    for i in range(0, len(candidates), batch):
        chunk = candidates[i : i + batch]
        await asyncio.gather(*(probe_host(ip) for ip in chunk))
        await asyncio.sleep(profile.tier_delay_sec * 0.25)

    logger.info(
        "Tier 1 TCP: %s live host(s), %s service(s) in %s",
        len(live),
        services_created,
        cidr,
    )
    return live, open_ports_by_ip, services_created


def _tier2_arp_enrich(
    cidr: str,
    tcp_ips: set[str],
    profile: ProfileConfig,
) -> tuple[list[DiscoveryHostEntry], dict[str, int]]:
    """ARP / ip neigh — MAC enrichment only; does not add hosts TCP missed."""
    global _arp_zero_streak

    _state["current_tier"] = "arp"
    stats: dict[str, int] = {"arp_skipped": 0, "arp_mac_added": 0, "arp_hosts_added": 0}
    iface = _detect_lan_interface(cidr)
    _state["iface"] = iface

    if not tcp_ips:
        return [], stats

    if _arp_zero_streak >= ARP_BROKEN_STREAK:
        stats["arp_skipped"] = 1
        _state["arp_skipped"] = True
        logger.info("Tier 2 ARP skipped — arp-scan broken (%s zero cycles)", _arp_zero_streak)
        entries = [
            DiscoveryHostEntry(ip=ip, mac=None, hostname=_resolve_hostname(ip), online=True)
            for ip in sorted(tcp_ips)
        ]
        return entries, stats

    _state["arp_skipped"] = False
    arp_entries = _run_arp_scan_only(cidr, iface)
    neigh_entries = _run_ip_neigh_fallback(cidr)

    if len(arp_entries) == 0:
        _arp_zero_streak += 1
    else:
        _arp_zero_streak = 0

    mac_by_ip: dict[str, str] = {}
    hostname_by_ip: dict[str, str | None] = {}
    for entry in _merge_entries(arp_entries, neigh_entries):
        if entry.mac:
            mac_by_ip[entry.ip] = entry.mac
        if entry.hostname:
            hostname_by_ip[entry.ip] = entry.hostname

    entries: list[DiscoveryHostEntry] = []
    for ip in sorted(tcp_ips):
        mac = mac_by_ip.get(ip)
        hostname = hostname_by_ip.get(ip) or _resolve_hostname(ip)
        entries.append(DiscoveryHostEntry(ip=ip, mac=mac, hostname=hostname, online=True))
        if mac:
            stats["arp_mac_added"] += 1

    logger.info(
        "Tier 2 ARP enrich: %s host(s), +%s MAC (iface=%s, streak=%s)",
        len(entries),
        stats["arp_mac_added"],
        iface,
        _arp_zero_streak,
    )
    return entries, stats


async def _tier0_extra_hosts(profile: ProfileConfig) -> tuple[set[str], dict[str, DiscoveryHostEntry], int]:
    """Always probe NETDASH_ARP_EXTRA_HOSTS — not gated by /28 chunk rotation."""
    from app.main import _upsert_service

    extra_ips = _parse_extra_hosts()
    if not extra_ips:
        return set(), {}, 0

    _state["current_tier"] = "extra-hosts"
    entries_by_ip: dict[str, DiscoveryHostEntry] = {}
    live: set[str] = set()
    services_created = 0

    extra_entries, open_ports_by_ip = await asyncio.to_thread(
        _probe_explicit_hosts_with_ports, extra_ips, None
    )
    for entry in extra_entries:
        entries_by_ip[entry.ip] = entry
        live.add(entry.ip)

    for ip, ports in open_ports_by_ip.items():
        for port in ports:
            try:
                service = await _identify_service(ip, port)
                await _upsert_service(service)
                services_created += 1
            except Exception:
                logger.exception("Extra-host service upsert failed for %s:%s", ip, port)
        await asyncio.sleep(profile.tier_delay_sec * 0.1)

    if live:
        logger.info(
            "Tier 0 extra-hosts: %s host(s), %s service(s) — %s",
            len(live),
            services_created,
            ", ".join(sorted(live)),
        )
    return live, entries_by_ip, services_created


async def _resolve_discovery_cidrs() -> list[str]:
    """All user-configured networks for background auto-discovery."""
    async with async_session() as db:
        result = await db.execute(select(AppSettings).limit(1))
        app_settings = result.scalar_one_or_none()
        scan_default = app_settings.scan_cidr_default if app_settings else None
    cidrs = resolve_scan_cidrs(None, scan_default)
    if not cidrs:
        cidrs = [get_local_network()]
    return cidrs


def _pick_rotated_cidr(cidrs: list[str]) -> str:
    """Round-robin across user-defined CIDRs — one base network per cycle."""
    global _cidr_index
    if len(cidrs) == 1:
        _state["cidr_total"] = 1
        _state["cidr_index"] = 1
        _state["active_cidr"] = cidrs[0]
        return cidrs[0]
    idx = _cidr_index % len(cidrs)
    _cidr_index += 1
    _state["cidr_total"] = len(cidrs)
    _state["cidr_index"] = idx + 1
    _state["active_cidr"] = cidrs[idx]
    return cidrs[idx]


async def _resolve_discovery_cidr() -> str:
    cidrs = await _resolve_discovery_cidrs()
    return _pick_rotated_cidr(cidrs)


async def run_discovery_cycle() -> int:
    """Single adaptive discovery cycle. Returns total host count."""
    global _known_ips, _profile

    if not settings.effective_discovery_enabled:
        return _state.get("last_cycle_hosts") or 0

    if _state["running"]:
        logger.debug("Discovery cycle skipped — previous still running")
        return _state.get("last_cycle_hosts") or 0

    _state["running"] = True
    _state["current_tier"] = "profile"
    tiers: dict[str, int] = {}

    try:
        _profile = detect_hardware_profile()
        profile = get_profile_config(_profile)
        _state["profile"] = profile.name
        _state["interval_sec"] = effective_interval(profile)

        base_cidr = await _resolve_discovery_cidr()
        cycle_cidrs = _select_cycle_cidrs(base_cidr, profile)
        _state["cidr"] = cycle_cidrs[0] if len(cycle_cidrs) == 1 else ", ".join(cycle_cidrs)

        if _state.get("chunk_total", 0) > 1:
            tiers["chunk_index"] = _state.get("chunk_index", 0)
            tiers["chunk_index_secondary"] = _state.get("chunk_index_secondary")
            tiers["chunk_total"] = _state.get("chunk_total", 0)

        tcp_ips: set[str] = set()
        merged_map: dict[str, DiscoveryHostEntry] = {}
        services_created = 0
        arp_skipped_any = False

        for cidr in cycle_cidrs:
            chunk_live, _open_ports, chunk_services = await _tier1_tcp_discovery(cidr, profile)
            tcp_ips |= chunk_live
            services_created += chunk_services
            await asyncio.sleep(profile.tier_delay_sec)

            entries, arp_stats = await asyncio.to_thread(
                _tier2_arp_enrich, cidr, chunk_live, profile
            )
            if arp_stats.get("arp_skipped"):
                arp_skipped_any = True
            for entry in entries:
                existing = merged_map.get(entry.ip)
                if existing is None:
                    merged_map[entry.ip] = entry
                elif not existing.mac and entry.mac:
                    merged_map[entry.ip] = DiscoveryHostEntry(
                        ip=entry.ip,
                        mac=entry.mac,
                        hostname=entry.hostname or existing.hostname,
                        online=True,
                    )
            await asyncio.sleep(profile.tier_delay_sec)

        extra_live, extra_map, extra_services = await _tier0_extra_hosts(profile)
        tcp_ips |= extra_live
        services_created += extra_services
        for ip, entry in extra_map.items():
            existing = merged_map.get(ip)
            if existing is None:
                merged_map[ip] = entry
            elif not existing.mac and entry.mac:
                merged_map[ip] = DiscoveryHostEntry(
                    ip=entry.ip,
                    mac=entry.mac,
                    hostname=entry.hostname or existing.hostname,
                    online=True,
                )

        entries = list(merged_map.values())
        tiers["tcp"] = len(tcp_ips)
        tiers["extra_hosts"] = len(extra_live)
        tiers["arp_skipped"] = 1 if arp_skipped_any else 0
        tiers["arp_mac_added"] = sum(1 for e in entries if e.mac)
        tiers["services"] = services_created

        if not entries:
            _state["last_cycle_at"] = datetime.now(timezone.utc)
            _state["last_cycle_hosts"] = 0
            _state["last_tiers"] = tiers
            _state["last_status_line"] = format_status_line(tiers, profile.name)
            _state["last_error"] = None
            _state["current_tier"] = None
            logger.warning(
                "Adaptive discovery: no hosts in %s (profile=%s) — next chunk in %ss",
                _state["cidr"],
                profile.name,
                effective_interval(profile),
            )
            return 0

        seen_ips = {e.ip for e in entries}
        new_ips = seen_ips - _known_ips
        _known_ips |= seen_ips

        mark_offline = _should_mark_missing_offline(cycle_cidrs, tiers, len(seen_ips))

        async with async_session() as db:
            await import_discovery_hosts(
                db,
                entries,
                source="tcp-discovery",
                source_hostname="netdash",
                mark_missing_offline=mark_offline,
                offline_scope_cidrs=cycle_cidrs,
            )

        count = len(seen_ips)
        status_line = format_status_line(tiers, profile.name)
        _state["last_cycle_at"] = datetime.now(timezone.utc)
        _state["last_cycle_hosts"] = count
        _state["last_tiers"] = tiers
        _state["last_status_line"] = status_line
        _state["last_error"] = None
        _state["current_tier"] = None

        logger.info(
            "Adaptive discovery done: %s host(s) in %s — %s (new=%s, services=%s)",
            count,
            _state["cidr"],
            status_line,
            len(new_ips),
            services_created,
        )
        if services_created:
            _schedule_icon_enrich(services_created)
        return count
    except Exception as exc:
        _state["last_error"] = str(exc)[:256]
        _state["current_tier"] = None
        logger.exception("Adaptive discovery cycle error")
        raise
    finally:
        _state["running"] = False


async def _discovery_loop() -> None:
    global _profile
    _state["enabled"] = True
    _profile = detect_hardware_profile()
    profile = get_profile_config(_profile)
    interval = effective_interval(profile)
    _state["profile"] = profile.name
    _state["interval_sec"] = interval

    startup_delay = max(0, settings.effective_discovery_startup_delay)
    if not settings.effective_discovery_enabled:
        logger.info(
            "TCP-first discovery disabled (NETDASH_DISCOVERY_ENABLED=false or low-memory auto-off)"
        )
        _state["enabled"] = False
        return
    logger.info(
        "TCP-first discovery started (profile=%s, interval=%ss, first_cycle_in=%ss, cidr=%s)",
        profile.name,
        interval,
        startup_delay,
        settings.scan_cidr or get_local_network(),
    )
    if startup_delay:
        await asyncio.sleep(startup_delay)

    while True:
        if not settings.effective_discovery_enabled:
            _state["enabled"] = False
            await asyncio.sleep(60)
            continue
        try:
            await run_discovery_cycle()
        except asyncio.CancelledError:
            raise
        except Exception:
            pass
        profile = get_profile_config()
        await asyncio.sleep(max(60, effective_interval(profile)))


def get_discovery_pipeline_status() -> dict[str, Any]:
    return {
        "enabled": _state.get("enabled", False),
        "running": _state.get("running", False),
        "mode": "adaptive",
        "discovery_method": "tcp-first",
        "profile": _state.get("profile") or detect_hardware_profile(),
        "current_tier": _state.get("current_tier"),
        "last_cycle_at": _state.get("last_cycle_at"),
        "last_cycle_hosts": _state.get("last_cycle_hosts", 0),
        "last_status_line": _state.get("last_status_line"),
        "last_tiers": _state.get("last_tiers"),
        "last_error": _state.get("last_error"),
        "cidr": _state.get("cidr"),
        "iface": _state.get("iface"),
        "arp_skipped": _state.get("arp_skipped", False),
        "arp_zero_streak": _arp_zero_streak,
        "interval_sec": _state.get("interval_sec") or effective_interval(get_profile_config()),
        "chunk_index": _state.get("chunk_index"),
        "chunk_index_secondary": _state.get("chunk_index_secondary"),
        "chunk_total": _state.get("chunk_total"),
        "cidr_index": _state.get("cidr_index"),
        "cidr_total": _state.get("cidr_total"),
        "active_cidr": _state.get("active_cidr"),
        "auto_all_ports": settings.auto_discovery_all_ports,
        "always_chunk": settings.auto_discovery_always_chunk,
        "weak_dual_chunk": settings.weak_dual_chunk,
        "discovery_enabled": settings.effective_discovery_enabled,
        "tcp_ports": TCP_DISCOVERY_PRIMARY_PORTS,
        "ips_friendly": settings.ips_friendly,
        "port_parallel_per_host": settings.effective_port_parallel_per_host,
        "ports_per_host_delay": settings.effective_ports_per_host_delay,
    }


def start_discovery_scheduler() -> asyncio.Task | None:
    global _task
    if not settings.effective_discovery_enabled:
        logger.info("Adaptive discovery scheduler not started — discovery disabled")
        return None
    if settings.scan_disabled or settings.discovery_mode != "adaptive":
        return None
    if _task and not _task.done():
        return _task
    _task = asyncio.create_task(_discovery_loop())
    return _task


async def stop_discovery_scheduler() -> None:
    global _task
    if _task:
        _task.cancel()
        try:
            await _task
        except asyncio.CancelledError:
            pass
        _task = None
    _state["enabled"] = False


# Backward-compat test hooks
def _hosts_needing_port_scan(seen_ips: set[str], new_ips: set[str]) -> list[str]:
    return sorted(new_ips)

