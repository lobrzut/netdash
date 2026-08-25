"""Brand icons must resolve locally — no cdn.simpleicons.org at render time."""
from __future__ import annotations

from pathlib import Path

from app import icons


def test_every_slug_in_the_tables_has_a_vendored_file() -> None:
    """A slug without an SVG is worse than no slug at all.

    resolve_brand_icon would hand the UI a URL that 404s, the <img> stays broken
    and the favicon fallback never runs — the tile is empty forever. This is the
    regression that left 21 brands blank before 1.3.164.
    """
    used = {slug for _pattern, slug in icons.BRAND_SLUGS}
    used |= set(icons.PORT_BRAND_SLUGS.values())
    assert used, "brand tables are empty"
    missing = sorted(used - icons.VENDORED_BRAND_SLUGS)
    assert not missing, (
        f"no SVG in app/static/brands for: {missing}. "
        "Run `node scripts/vendor_brand_icons.mjs`, or drop the slug from app/icons.py."
    )


def test_resolved_icons_never_point_at_a_third_party_cdn() -> None:
    for name in ("proxmox", "jellyfin", "grafana", "pihole", "traefik", "pomnia"):
        url = icons.resolve_brand_icon(name)
        assert url, f"{name} lost its icon"
        assert url.startswith("/static/"), f"{name} resolved off-box: {url}"

    for port in icons.PORT_BRAND_ICONS:
        url = icons.resolve_port_brand_icon(port)
        assert url is None or url.startswith("/static/"), f"port {port} resolved off-box: {url}"


def test_unknown_brand_falls_through_to_favicon() -> None:
    """None is the contract that lets the caller try the favicon path."""
    assert icons.simple_icon_url("definitely-not-a-brand-9000") is None
    assert icons.resolve_brand_icon("some random box on the lan") is None


def test_vendored_files_are_real_svgs() -> None:
    brands = Path(icons.BRANDS_DIR)
    files = sorted(brands.glob("*.svg"))
    assert len(files) >= 80, f"expected the full icon set, found {len(files)}"
    for svg in files:
        head = svg.read_text(encoding="utf-8")[:200]
        assert head.startswith("<svg "), f"{svg.name} is not an SVG"
        assert "cdn.simpleicons.org" not in head, f"{svg.name} still references the CDN"
