"""Scheduled discovery — one full IPS-friendly scan cycle, then sleep until next run."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from app.config import settings
from app.discovery_pipeline import run_scheduled_full_scan
from app.discovery_policy import parse_discovery_schedule, seconds_until_next_run

logger = logging.getLogger("netdash")

_task: asyncio.Task | None = None
_state: dict[str, Any] = {
    "enabled": False,
    "running": False,
    "mode": "scheduled",
    "last_cycle_at": None,
    "last_cycle_hosts": 0,
    "last_status_line": None,
    "last_error": None,
    "next_run_at": None,
    "schedule": None,
}


async def _scheduled_loop() -> None:
    spec = parse_discovery_schedule(settings.discovery_schedule)
    _state["enabled"] = True
    _state["schedule"] = settings.discovery_schedule
    startup_delay = max(0, settings.effective_discovery_startup_delay)
    logger.info(
        "Scheduled discovery started (schedule=%s, first_run_in=%ss)",
        settings.discovery_schedule,
        startup_delay,
    )
    if startup_delay:
        await asyncio.sleep(startup_delay)

    while True:
        if not settings.scheduled_discovery_enabled:
            _state["enabled"] = False
            await asyncio.sleep(60)
            continue

        spec = parse_discovery_schedule(settings.discovery_schedule)
        wait_sec = seconds_until_next_run(spec)
        next_at = datetime.now(timezone.utc).timestamp() + wait_sec
        _state["next_run_at"] = datetime.fromtimestamp(next_at, tz=timezone.utc)
        _state["schedule"] = settings.discovery_schedule
        logger.info(
            "Scheduled discovery: next run in %.0fs (%s)",
            wait_sec,
            _state["next_run_at"].isoformat() if _state["next_run_at"] else "?",
        )
        await asyncio.sleep(wait_sec)

        if not settings.scheduled_discovery_enabled:
            continue
        _state["running"] = True
        try:
            count = await run_scheduled_full_scan()
            _state["last_cycle_at"] = datetime.now(timezone.utc)
            _state["last_cycle_hosts"] = count
            _state["last_status_line"] = (
                f"Harmonogram: zakończono skan — {count} hostów"
            )
            _state["last_error"] = None
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            _state["last_error"] = str(exc)[:256]
            logger.exception("Scheduled discovery run failed")
        finally:
            _state["running"] = False


def get_scheduled_discovery_status() -> dict[str, Any]:
    return {
        "enabled": _state.get("enabled", False),
        "running": _state.get("running", False),
        "mode": "scheduled",
        "discovery_method": "tcp-scheduled",
        "last_cycle_at": _state.get("last_cycle_at"),
        "last_cycle_hosts": _state.get("last_cycle_hosts", 0),
        "last_status_line": _state.get("last_status_line"),
        "last_error": _state.get("last_error"),
        "next_run_at": _state.get("next_run_at"),
        "schedule": _state.get("schedule") or settings.discovery_schedule,
    }


def start_scheduled_discovery_scheduler() -> asyncio.Task | None:
    global _task
    if not settings.scheduled_discovery_enabled:
        return None
    if _task and not _task.done():
        return _task
    _task = asyncio.create_task(_scheduled_loop())
    return _task


async def stop_scheduled_discovery_scheduler() -> None:
    global _task
    if _task:
        _task.cancel()
        try:
            await _task
        except asyncio.CancelledError:
            pass
        _task = None
    _state["enabled"] = False
