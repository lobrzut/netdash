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

    def test_proxmox_still_uses_cdn(self) -> None:
        self.assertTrue(str(resolve_brand_icon("Proxmox VE") or "").startswith("https://cdn.simpleicons.org/"))


if __name__ == "__main__":
    unittest.main()
