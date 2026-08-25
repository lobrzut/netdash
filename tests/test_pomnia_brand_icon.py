"""Brand icon resolution for Pomnia and simpleicons."""

from __future__ import annotations

import unittest

from app.icons import (
    effective_browser_icon_url,
    resolve_brand_icon,
    resolve_port_brand_icon,
)


class PomniaBrandIconTests(unittest.TestCase):
    def test_resolve_by_name(self) -> None:
        self.assertEqual(resolve_brand_icon("Pomnia"), "/static/pomnia-icon.png")
        self.assertEqual(resolve_brand_icon("brain-core status"), "/static/pomnia-icon.png")

    def test_resolve_by_port(self) -> None:
        self.assertEqual(resolve_port_brand_icon(7865), "/static/pomnia-icon.png")

    def test_private_favicon_falls_back_to_local_brand(self) -> None:
        url = effective_browser_icon_url(
            "http://192.168.1.150:7865/favicon.ico",
            "http://192.168.1.150:7865",
            has_login=False,
            name="Pomnia",
            port=7865,
        )
        self.assertEqual(url, "/static/pomnia-icon.png")

    def test_third_party_brand_is_served_from_our_own_static(self) -> None:
        """Was test_proxmox_still_uses_cdn until 1.3.164.

        The old contract sent every brand tile to cdn.simpleicons.org at render
        time. A self-hosted dashboard should not phone a third-party CDN, and an
        offline homelab saw blank squares, so the icons are vendored now.
        """
        self.assertEqual(resolve_brand_icon("Proxmox VE"), "/static/brands/proxmox.svg")

    def test_brand_without_a_vendored_icon_yields_none(self) -> None:
        """None is what hands the caller down to the favicon fallback.

        simple-icons dropped these brands; returning a 404-ing CDN URL instead of
        None is exactly what left 21 tiles permanently empty before 1.3.164.
        """
        self.assertIsNone(resolve_brand_icon("lidarr"))
        self.assertIsNone(resolve_brand_icon("sabnzbd"))


if __name__ == "__main__":
    unittest.main()
