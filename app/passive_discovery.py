"""Passive LAN discovery — ARP/neighbor table only (IPS-friendly, no TCP sweep)."""

from __future__ import annotations

import asyncio
import ipaddress
import logging
import socket
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.arp_scan import _read_arp_table, read_arp_hosts_in_cidr
from app.config import settings
from app.database import async_session
from app.discovery_import import import_discovery_hosts
from app.models import AppSettings
from app.scanner import get_local_network, resolve_scan_cidrs
from app.schemas import DiscoveryHostEntry

logger = logging.getLogger("netdash")

_task: asyncio.Task | None = None
_state: dict[str, Any] = {
    "enabled": False,
    "running": False,
    "mode": "passive",
    "last_cycle_at": None,
    "last_cycle_hosts": 0,
    "last_status_line": None,
    "last_error": None,
    "interval_sec": None,
    "cidr": None,
}


def _resolve_hostname(ip: str) -> str | None:
    try:
        name, _, _ = socket.gethostbyaddr(ip)
        if name and name != ip:
            short = name.split(".")[0]
            return short if short else name
    except (socket.herror, socket.gaierror, OSError):
        return None
    return None


async def _resolve_passive_cidrs() -> list[str]:
    async with async_session() as db:
        result = await db.execute(select(AppSettings).limit(1))
        app_settings = result.scalar_one_or_none()
        scan_default = app_settings.scan_cidr_default if app_settings else None
    cidrs = resolve_scan_cidrs(None, scan_default)
    return cidrs or [get_local_network()]


def _collect_passive_entries(cidrs: list[str]) -> list[DiscoveryHostEntry]:
    arp_table = _read_arp_table()
    seen: dict[str, DiscoveryHostEntry] = {}
    for cidr in cidrs:
        try:
            network = ipaddress.ip_network(cidr.strip(), strict=False)
        except ValueError:
            continue
        for ip in read_arp_hosts_in_cidr(cidr):
            if ip in seen:
                continue
            mac = arp_table.get(ip)
            seen[ip] = DiscoveryHostEntry(
                ip=ip,
                mac=mac,
                hostname=_resolve_hostname(ip),
                online=True,
            )
        # Gateway often in ARP even when not returned by read_arp_hosts_in_cidr filter
        try:
            gw = str(network.network_address + 1)
            if gw not in seen and gw in arp_table:
                seen[gw] = DiscoveryHostEntry(
                    ip=gw,
                    mac=arp_table[gw],
                    hostname=_resolve_hostname(gw),
                    online=True,
                )
        except (ValueError, TypeError):
            pass
    return list(seen.values())


async def run_passive_discovery_cycle() -> int:
    """Single passive cycle — read kernel ARP/neighbor table, import host cards."""
    if not settings.passive_discovery_enabled:
        return _state.get("last_cycle_hosts") or 0
    if _state["running"]:
        logger.debug("Passive discovery skipped — previous cycle still running")
        return _state.get("last_cycle_hosts") or 0

    _state["running"] = True
    try:
        cidrs = await _resolve_passive_cidrs()
        _state["cidr"] = ", ".join(cidrs)
        entries = await asyncio.to_thread(_collect_passive_entries, cidrs)
        if not entries:
            _state["last_cycle_at"] = datetime.now(timezone.utc)
            _state["last_cycle_hosts"] = 0
            _state["last_status_line"] = "Pasywne: brak hostów w tablicy ARP (poczekaj na ruch w LAN)"
            _state["last_error"] = None
            logger.info("Passive discovery: no hosts in ARP table for %s", _state["cidr"])
            return 0

        async with async_session() as db:
            await import_discovery_hosts(
                db,
                entries,
                source="passive-arp",
                source_hostname="netdash",
                mark_missing_offline=False,
            )

        count = len(entries)
        macs = sum(1 for e in entries if e.mac)
        _state["last_cycle_at"] = datetime.now(timezone.utc)
        _state["last_cycle_hosts"] = count
        _state["last_status_line"] = (
            f"Pasywne ARP: {count} hostów ({macs} z MAC) — bez skanu TCP"
        )
        _state["last_error"] = None
        logger.info("Passive discovery: %s host(s) from ARP — %s", count, _state["cidr"])
        return count
    except Exception as exc:
        _state["last_error"] = str(exc)[:256]
        logger.exception("Passive discovery cycle error")
        raise
    finally:
        _state["running"] = False


async def _passive_loop() -> None:
    interval = max(300, settings.passive_interval)
    _state["enabled"] = True
    _state["interval_sec"] = interval
    startup_delay = max(0, min(settings.effective_discovery_startup_delay, 120))
    logger.info(
        "Passive discovery started (interval=%ss, first_cycle_in=%ss)",
        interval,
        startup_delay,
    )
    if startup_delay:
        await asyncio.sleep(startup_delay)

    while True:
        if not settings.passive_discovery_enabled:
            _state["enabled"] = False
            await asyncio.sleep(60)
            continue
        try:
            await run_passive_discovery_cycle()
        except asyncio.CancelledError:
            raise
        except Exception:
            pass
        interval = max(300, settings.passive_interval)
        _state["interval_sec"] = interval
        await asyncio.sleep(interval)


def get_passive_discovery_status() -> dict[str, Any]:
    return {
        "enabled": _state.get("enabled", False),
        "running": _state.get("running", False),
        "mode": "passive",
        "discovery_method": "arp-table",
        "last_cycle_at": _state.get("last_cycle_at"),
        "last_cycle_hosts": _state.get("last_cycle_hosts", 0),
        "last_status_line": _state.get("last_status_line"),
        "last_error": _state.get("last_error"),
        "interval_sec": _state.get("interval_sec") or settings.passive_interval,
        "cidr": _state.get("cidr"),
    }


def start_passive_discovery_scheduler() -> asyncio.Task | None:
    global _task
    if not settings.passive_discovery_enabled:
        return None
    if _task and not _task.done():
        return _task
    _task = asyncio.create_task(_passive_loop())
    return _task


async def stop_passive_discovery_scheduler() -> None:
    global _task
    if _task:
        _task.cancel()
        try:
            await _task
        except asyncio.CancelledError:
            pass
        _task = None
    _state["enabled"] = False
