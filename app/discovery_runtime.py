"""Runtime discovery toggle from AppSettings (UI). Env NETDASH_DISCOVERY_ENABLED overrides."""

from __future__ import annotations

_app_discovery_enabled: bool | None = None


def set_app_discovery_enabled(enabled: bool) -> None:
    global _app_discovery_enabled
    _app_discovery_enabled = enabled


def get_app_discovery_enabled() -> bool | None:
    return _app_discovery_enabled


def clear_app_discovery_enabled() -> None:
    global _app_discovery_enabled
    _app_discovery_enabled = None
