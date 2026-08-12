"""Host:port service endpoint helpers (dedupe / pick keeper)."""

from __future__ import annotations

from typing import Protocol, TypeVar


class EndpointRow(Protocol):
    id: int | None
    customized: bool
    pinned: bool


T = TypeVar("T", bound=EndpointRow)


def pick_endpoint_service(matches: list[T]) -> T | None:
    """Prefer customized / pinned / oldest id when duplicate host:port rows exist."""
    if not matches:
        return None
    return sorted(
        matches,
        key=lambda s: (
            0 if s.customized else 1,
            0 if s.pinned else 1,
            s.id or 0,
        ),
    )[0]
