"""Discovery policy resolution — off, on_demand, scheduled, passive, adaptive (legacy)."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal

PolicyName = Literal["off", "on_demand", "scheduled", "passive", "adaptive"]

VALID_POLICIES: frozenset[str] = frozenset(
    {"off", "on_demand", "scheduled", "passive", "adaptive"}
)

_LEGACY_MODE_MAP: dict[str, PolicyName] = {
    "adaptive": "adaptive",
    "arp": "passive",
    "local": "on_demand",
    "remote": "off",
}

_POLICY_LABELS_PL: dict[str, str] = {
    "off": "Wyłączone",
    "on_demand": "Na żądanie (zalecane)",
    "scheduled": "Harmonogram",
    "passive": "Pasywne (ARP)",
    "adaptive": "Legacy adaptive (niezalecane z SEP)",
}


def normalize_policy(raw: str | None) -> PolicyName:
    if not raw or not str(raw).strip():
        return "on_demand"
    value = str(raw).strip().lower()
    if value in VALID_POLICIES:
        return value  # type: ignore[return-value]
    if value in _LEGACY_MODE_MAP:
        return _LEGACY_MODE_MAP[value]
    return "on_demand"


def policy_env_locked() -> bool:
    raw = os.environ.get("NETDASH_DISCOVERY_POLICY")
    return raw is not None and bool(str(raw).strip())


def legacy_policy_from_settings() -> PolicyName:
    """Map NETDASH_DISCOVERY_MODE + NETDASH_DISCOVERY_ENABLED when policy env unset."""
    from app.config import settings

    if settings.scan_disabled:
        return "off"
    raw_enabled = os.environ.get("NETDASH_DISCOVERY_ENABLED")
    if raw_enabled is not None and str(raw_enabled).strip():
        if str(raw_enabled).strip().lower() not in ("true", "1", "yes", "on"):
            return "off"
    mode = (settings.discovery_mode or "local").strip().lower()
    return _LEGACY_MODE_MAP.get(mode, "on_demand")


def resolve_discovery_policy(db_policy: str | None = None) -> PolicyName:
    """Effective policy: env NETDASH_DISCOVERY_POLICY → DB → legacy mode mapping."""
    env = os.environ.get("NETDASH_DISCOVERY_POLICY")
    if env and str(env).strip():
        return normalize_policy(env)
    if db_policy and str(db_policy).strip():
        return normalize_policy(db_policy)
    return legacy_policy_from_settings()


def policy_runs_background(policy: PolicyName) -> bool:
    return policy in ("scheduled", "passive", "adaptive")


def policy_is_legacy_adaptive(policy: PolicyName) -> bool:
    return policy == "adaptive"


@dataclass(frozen=True)
class ScheduleSpec:
    kind: Literal["daily", "interval"]
    daily_at: tuple[int, int] | None = None  # hour, minute UTC
    interval_sec: int | None = None


_TIME_RE = re.compile(r"^(\d{1,2}):(\d{2})$")
_INTERVAL_RE = re.compile(r"^(\d+)\s*h(?:ours?)?$", re.IGNORECASE)


def parse_discovery_schedule(raw: str | None) -> ScheduleSpec:
    """Parse NETDASH_DISCOVERY_SCHEDULE: '03:00' (daily UTC) or '24h' / '6h' interval."""
    text = (raw or "03:00").strip()
    time_match = _TIME_RE.match(text)
    if time_match:
        hour = max(0, min(23, int(time_match.group(1))))
        minute = max(0, min(59, int(time_match.group(2))))
        return ScheduleSpec(kind="daily", daily_at=(hour, minute))
    interval_match = _INTERVAL_RE.match(text)
    if interval_match:
        hours = max(1, int(interval_match.group(1)))
        return ScheduleSpec(kind="interval", interval_sec=hours * 3600)
    return ScheduleSpec(kind="interval", interval_sec=86400)


def seconds_until_next_run(spec: ScheduleSpec, *, now: datetime | None = None) -> float:
    """Seconds to wait before the next scheduled discovery run."""
    current = now or datetime.now(timezone.utc)
    if spec.kind == "interval" and spec.interval_sec:
        return float(spec.interval_sec)
    if spec.kind == "daily" and spec.daily_at:
        hour, minute = spec.daily_at
        target = current.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= current:
            target += timedelta(days=1)
        return max(60.0, (target - current).total_seconds())
    return 86400.0
