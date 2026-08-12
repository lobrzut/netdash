"""Runtime discovery prefs from AppSettings (UI). Env vars override when set."""

from __future__ import annotations

_app_discovery_enabled: bool | None = None
_app_discovery_policy: str | None = None


def set_app_discovery_enabled(enabled: bool) -> None:
    global _app_discovery_enabled
    _app_discovery_enabled = enabled


def get_app_discovery_enabled() -> bool | None:
    return _app_discovery_enabled


def set_app_discovery_policy(policy: str | None) -> None:
    global _app_discovery_policy
    _app_discovery_policy = policy.strip().lower() if policy else None


def get_app_discovery_policy() -> str | None:
    return _app_discovery_policy


def clear_app_discovery_enabled() -> None:
    global _app_discovery_enabled, _app_discovery_policy
    _app_discovery_enabled = None
    _app_discovery_policy = None
