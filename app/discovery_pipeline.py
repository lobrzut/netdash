"""Adaptive tiered discovery — ping → ARP → light port probe (profile-aware).

Tier 0: hardware profile (weak / normal / strong)
Tier 1: ICMP or TCP :80 ping sweep (cheapest, always first)
Tier 2: arp-scan for MAC enrichment + hosts ping missed (skip if broken)
Tier 3: light port probe for NEW or stale (>24h) hosts only
Tier 4: HTTP health checks — independent loop in main.py (unchanged)
"""

from __future__ import annotations

import asyncio
import ipaddress
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select

from app.arp_discovery import (
    _detect_lan_interface,
    _merge_entries,
    _parse_extra_hosts,
    _probe_explicit_hosts,
    _resolve_hostname,
    _run_arp_scan_only,
    _run_ip_neigh_fallback,
)
from app.config import settings
from app.database import async_session
from app.discovery_import import import_discovery_hosts
from app.models import AppSettings
from app.scanner import (
    _check_port,
    _identify_service,
    _ping_host,
    expand_cidrs_for_safe_mode,
    get_local_network,
    icmp_ping_available,
    parse_cidr,
    resolve_scan_cidrs,
    safe_mode_scan_cidrs,
)
from app.schemas import DiscoveryHostEntry

logger = logging.getLogger("netdash")

LIGHT_PROBE_PORTS = [80, 443, 8080, 8000, 3000, 5000, 22]
PORT_STALE_HOURS = 24
ARP_BROKEN_STREAK = 3

_task: asyncio.Task | None = None
_known_ips: set[str] = set()
_port_scanned_at: dict[str, datetime] = {}
_arp_zero_streak = 0
_chunk_index = 0
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
}


@dataclass(frozen=True)
class ProfileConfig:
    name: str
    interval_sec: int
    ping_parallel: int
    port_parallel: int
    tier_delay_sec: float
    max_hosts: int
    chunk_prefix: int


_PROFILES: dict[str, ProfileConfig] = {
    "weak": ProfileConfig("weak", 300, 8, 1, 2.0, 128, 28),
    "normal": ProfileConfig("normal", 180, 16, 2, 1.0, 256, 24),
    "strong": ProfileConfig("strong", 120, 32, 4, 0.5, 256, 24),
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
    ping_n = tiers.get("ping", 0)
    arp_mac = tiers.get("arp_mac_added", 0)
    ports_new = tiers.get("ports_new", 0)
    parts = [f"ping {ping_n}"]
    if tiers.get("arp_skipped"):
        parts.append("arp wyłączony")
    elif arp_mac:
        parts.append(f"arp +{arp_mac} MAC")
    else:
        parts.append("arp 0 MAC")
    if ports_new:
        parts.append(f"{ports_new} nowe porty")
    parts.append(f"profil: {profile}")
    return " → ".join(parts)


def _select_cycle_cidr(cidr: str, profile: ProfileConfig) -> str:
    """On weak hosts rotate /28 chunks instead of flooding /24 every cycle."""
    global _chunk_index
    network = ipaddress.ip_network(cidr.strip(), strict=False)
    if network.prefixlen >= profile.chunk_prefix:
        return str(network)

    chunks = safe_mode_scan_cidrs(cidr)
    if len(chunks) <= 1:
        return chunks[0] if chunks else cidr

    selected = chunks[_chunk_index % len(chunks)]
    _chunk_index += 1
    logger.info(
        "Adaptive discovery: profile=%s chunk %s/%s → %s (from %s)",
        profile.name,
        _chunk_index % len(chunks) or len(chunks),
        len(chunks),
        selected,
        cidr,
    )
    return selected


async def _tier1_ping_sweep(cidr: str, profile: ProfileConfig) -> set[str]:
    """ICMP ping with TCP :80 fallback — rate-limited batch."""
    _state["current_tier"] = "ping"
    candidates = parse_cidr(cidr, max_hosts=profile.max_hosts)
    live: set[str] = set()
    icmp_ok = await icmp_ping_available()
    sem = asyncio.Semaphore(profile.ping_parallel)
    batch = profile.ping_parallel

    async def probe_host(ip: str) -> None:
        async with sem:
            if icmp_ok and await _ping_host(ip):
                live.add(ip)
                return
            if await _check_port(ip, 80, sem):
                live.add(ip)

    for i in range(0, len(candidates), batch):
        chunk = candidates[i : i + batch]
        await asyncio.gather(*(probe_host(ip) for ip in chunk))
        await asyncio.sleep(profile.tier_delay_sec * 0.25)

    extra = _parse_extra_hosts()
    if extra:
        for entry in await asyncio.to_thread(_probe_explicit_hosts, extra, cidr):
            live.add(entry.ip)

    logger.info("Tier 1 ping: %s live host(s) in %s", len(live), cidr)
    return live


def _tier2_arp(
    cidr: str,
    ping_ips: set[str],
    profile: ProfileConfig,
) -> tuple[list[DiscoveryHostEntry], dict[str, int]]:
    """arp-scan + ip neigh — skipped when arp-scan returned 0 hosts repeatedly."""
    global _arp_zero_streak

    _state["current_tier"] = "arp"
    stats: dict[str, int] = {"arp_skipped": 0, "arp_mac_added": 0, "arp_hosts_added": 0}
    iface = _detect_lan_interface(cidr)
    _state["iface"] = iface

    if _arp_zero_streak >= ARP_BROKEN_STREAK:
        stats["arp_skipped"] = 1
        _state["arp_skipped"] = True
        logger.info("Tier 2 ARP skipped — arp-scan broken (%s zero cycles)", _arp_zero_streak)
        entries = [
            DiscoveryHostEntry(ip=ip, mac=None, hostname=_resolve_hostname(ip), online=True)
            for ip in sorted(ping_ips)
        ]
        return entries, stats

    _state["arp_skipped"] = False
    arp_entries = _run_arp_scan_only(cidr, iface)
    neigh_entries = _run_ip_neigh_fallback(cidr)

    if len(arp_entries) == 0:
        _arp_zero_streak += 1
    else:
        _arp_zero_streak = 0

    arp_ips = {e.ip for e in arp_entries}
    ping_only = ping_ips - arp_ips

    ping_entries = [
        DiscoveryHostEntry(ip=ip, mac=None, hostname=_resolve_hostname(ip), online=True)
        for ip in sorted(ping_only)
    ]

    merged = _merge_entries(arp_entries, neigh_entries, ping_entries)
    merged_map = {e.ip: e for e in merged}

    for ip in ping_ips:
        if ip not in merged_map:
            merged_map[ip] = DiscoveryHostEntry(
                ip=ip, mac=None, hostname=_resolve_hostname(ip), online=True
            )

    for entry in merged_map.values():
        if entry.mac:
            stats["arp_mac_added"] += 1

    stats["arp_hosts_added"] = len(merged_map) - len(ping_ips)
    if stats["arp_hosts_added"] < 0:
        stats["arp_hosts_added"] = 0

    logger.info(
        "Tier 2 ARP: %s host(s), +%s MAC, +%s from ARP (iface=%s, streak=%s)",
        len(merged_map),
        stats["arp_mac_added"],
        stats["arp_hosts_added"],
        iface,
        _arp_zero_streak,
    )
    return list(merged_map.values()), stats


async def _tier3_port_probe(
    ips: list[str],
    profile: ProfileConfig,
) -> int:
    """Light port probe — sequential on weak, parallel on strong."""
    from app.main import _upsert_service

    _state["current_tier"] = "ports"
    if not ips:
        return 0

    sem = asyncio.Semaphore(profile.port_parallel)
    created = 0
    now = datetime.now(timezone.utc)

    for ip in ips:
        found_port = False
        for port in LIGHT_PROBE_PORTS:
            if await _check_port(ip, port, sem):
                try:
                    service = await _identify_service(ip, port)
                    await _upsert_service(service)
                    created += 1
                    found_port = True
                except Exception:
                    logger.exception("Port probe failed for %s:%s", ip, port)
                break
            await asyncio.sleep(profile.tier_delay_sec * 0.2)
        _port_scanned_at[ip] = now
        if found_port:
            await asyncio.sleep(profile.tier_delay_sec)
        elif profile.port_parallel == 1:
            await asyncio.sleep(profile.tier_delay_sec * 0.5)

    logger.info("Tier 3 ports: probed %s host(s), %s service(s) updated", len(ips), created)
    return created


def _hosts_needing_port_scan(seen_ips: set[str], new_ips: set[str]) -> list[str]:
    now = datetime.now(timezone.utc)
    stale_before = now - timedelta(hours=PORT_STALE_HOURS)
    targets: list[str] = []
    for ip in sorted(seen_ips):
        if ip in new_ips:
            targets.append(ip)
            continue
        last = _port_scanned_at.get(ip)
        if last is None:
            targets.append(ip)
            continue
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        if last < stale_before:
            targets.append(ip)
    cap = max(1, settings.discovery_port_max_hosts)
    return targets[:cap]


async def _resolve_discovery_cidr() -> str:
    async with async_session() as db:
        result = await db.execute(select(AppSettings).limit(1))
        app_settings = result.scalar_one_or_none()
        scan_default = app_settings.scan_cidr_default if app_settings else None
    cidrs = resolve_scan_cidrs(None, scan_default)
    base = cidrs[0] if cidrs else get_local_network()
    expanded = expand_cidrs_for_safe_mode([base])
    return expanded[0] if expanded else base


async def run_discovery_cycle() -> int:
    """Single adaptive discovery cycle. Returns total host count."""
    global _known_ips, _profile

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
        cidr = _select_cycle_cidr(base_cidr, profile)
        _state["cidr"] = cidr

        ping_ips = await _tier1_ping_sweep(cidr, profile)
        tiers["ping"] = len(ping_ips)
        await asyncio.sleep(profile.tier_delay_sec)

        entries, arp_stats = await asyncio.to_thread(_tier2_arp, cidr, ping_ips, profile)
        tiers.update(arp_stats)
        await asyncio.sleep(profile.tier_delay_sec)

        if not entries:
            _state["last_cycle_at"] = datetime.now(timezone.utc)
            _state["last_cycle_hosts"] = 0
            _state["last_tiers"] = tiers
            _state["last_status_line"] = format_status_line(tiers, profile.name)
            _state["last_error"] = None
            _state["current_tier"] = None
            logger.warning("Adaptive discovery: no hosts in %s (profile=%s)", cidr, profile.name)
            return 0

        seen_ips = {e.ip for e in entries}
        new_ips = seen_ips - _known_ips
        _known_ips = seen_ips

        arp_count = len([e for e in entries if e.mac])
        mark_offline = tiers.get("arp_skipped", 0) == 0 and (
            tiers.get("arp_hosts_added", 0) > 0 or tiers.get("ping", 0) > 0
        )

        async with async_session() as db:
            await import_discovery_hosts(
                db,
                entries,
                source="adaptive-discovery",
                source_hostname="netdash",
                mark_missing_offline=mark_offline,
            )

        port_targets = _hosts_needing_port_scan(seen_ips, new_ips)
        if settings.discovery_port_probe and port_targets:
            ports_new = await _tier3_port_probe(port_targets, profile)
            tiers["ports_new"] = ports_new
        else:
            tiers["ports_new"] = 0

        count = len(seen_ips)
        status_line = format_status_line(tiers, profile.name)
        _state["last_cycle_at"] = datetime.now(timezone.utc)
        _state["last_cycle_hosts"] = count
        _state["last_tiers"] = tiers
        _state["last_status_line"] = status_line
        _state["last_error"] = None
        _state["current_tier"] = None

        logger.info(
            "Adaptive discovery done: %s host(s) in %s — %s (arp_macs=%s, new=%s)",
            count,
            cidr,
            status_line,
            arp_count,
            len(new_ips),
        )
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

    startup_delay = max(5, min(60, interval // 6))
    logger.info(
        "Adaptive discovery scheduler started (profile=%s, interval=%ss, cidr=%s)",
        profile.name,
        interval,
        settings.scan_cidr or get_local_network(),
    )
    await asyncio.sleep(startup_delay)

    while True:
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
        "extra_hosts": _parse_extra_hosts(),
    }


def start_discovery_scheduler() -> asyncio.Task | None:
    global _task
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
