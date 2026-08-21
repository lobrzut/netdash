"""Normalize Pomnia /healthz or /stats (and legacy Brain /stats) for the NetDash tile."""

from __future__ import annotations

from typing import Any


def _as_int(value: Any) -> int | None:
    if value is None or value is False:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _is_pomnia_payload(raw: dict[str, Any]) -> bool:
    if raw.get("service") == "brain-core":
        return True
    if "uptimeSec" in raw or "embed" in raw:
        return True
    return "index" in raw


def format_uptime(seconds: int | None) -> str | None:
    if seconds is None:
        return None
    sec = max(0, int(seconds))
    days, rem = divmod(sec, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)
    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m"
    return f"{secs}s"


def normalize_pomnia_stats(
    raw: dict[str, Any],
    *,
    dashboard_url: str | None = None,
    stats_url: str | None = None,
) -> dict[str, Any]:
    """Map upstream JSON to search-appliance tile fields.

    Prefer ``index.files`` / ``index.chunks``. When Pomnia redacts ``index`` to
    null, do not invent zeros from legacy Brain aliases on the same payload.
    """
    from app.url_utils import brain_dashboard_url

    pomnia = _is_pomnia_payload(raw)
    idx = raw.get("index")
    counts_available = False
    files: int | None = None
    chunks: int | None = None

    if isinstance(idx, dict):
        files = _as_int(idx.get("files"))
        chunks = _as_int(idx.get("chunks"))
        counts_available = True
        if files is None:
            files = 0
        if chunks is None:
            chunks = 0
    elif pomnia and "index" in raw and idx is None:
        counts_available = False
        files = None
        chunks = None
    else:
        # Legacy Brain Hub /stats without an index key.
        counts_available = True
        files = _as_int(raw.get("notes"))
        if files is None:
            files = _as_int(raw.get("library_docs")) or 0
        chunks = _as_int(raw.get("graph_nodes"))
        if chunks is None:
            chunks = 0

    uptime_sec = _as_int(raw.get("uptimeSec"))
    status = raw.get("status") or raw.get("service")
    version = raw.get("version")
    embed = raw.get("embed") if isinstance(raw.get("embed"), dict) else None
    activity = raw.get("activity_7d")
    dash = dashboard_url if dashboard_url is not None else brain_dashboard_url(stats_url)

    return {
        "ok": True,
        "schema": "pomnia" if pomnia else "legacy",
        "mode": "pomnia" if pomnia else "legacy",
        "dashboard_url": dash,
        "counts_available": counts_available,
        "index_available": counts_available,
        "index_files": files,
        "index_chunks": chunks,
        "status": status,
        "version": version,
        "uptime_sec": uptime_sec,
        "uptime_label": format_uptime(uptime_sec),
        "embed": embed,
        "vault_owner": raw.get("vaultOwner"),
        # Honest aliases: do not fake zeros when Pomnia redacted the index.
        "notes": files if counts_available else None,
        "sessions": None if pomnia else _as_int(raw.get("sessions")),
        "library_docs": (
            chunks
            if (pomnia and counts_available)
            else (_as_int(raw.get("library_docs")) if not pomnia else None)
        ),
        "code_files": None if pomnia else _as_int(raw.get("code_files")),
        "graph_nodes": chunks if counts_available else None,
        "last_session_at": None if pomnia else raw.get("last_session_at"),
        "activity_7d": [int(x) for x in activity][:14] if isinstance(activity, list) else [],
        "pomnia": {
            "version": version,
            "status": status,
            "vaultOwner": raw.get("vaultOwner"),
            "uptimeSec": uptime_sec,
            "embed": embed,
        },
    }
