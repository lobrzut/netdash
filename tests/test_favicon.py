"""Icon resolution and favicon enrichment helpers."""

from __future__ import annotations

import unittest

from app.favicon import save_cached_icon, service_needs_icon_fetch
from app.icons import effective_browser_icon_url, resolve_port_brand_icon
from app.models import Service


class PortBrandIconTests(unittest.TestCase):
    def test_proxmox_port_8006(self):
        url = resolve_port_brand_icon(8006)
        self.assertIsNotNone(url)
        self.assertIn("proxmox", url or "")

    def test_effective_browser_icon_uses_port_fallback(self):
        url = effective_browser_icon_url(
            None,
            "https://192.168.1.10:8006",
            has_login=True,
            name="192.168.1.10:8006",
            port=8006,
        )
        self.assertIsNotNone(url)
        self.assertIn("proxmox", url or "")


class ServiceNeedsIconFetchTests(unittest.TestCase):
    def _svc(self, **kwargs) -> Service:
        defaults = dict(
            id=1,
            name="Custom App",
            url="https://192.168.1.20:4443",
            host="192.168.1.20",
            port=4443,
            protocol="https",
            icon="globe",
            icon_url=None,
            has_login=True,
        )
        defaults.update(kwargs)
        svc = Service()
        for key, value in defaults.items():
            if key != "id":
                setattr(svc, key, value)
        return svc

    def test_needs_fetch_when_no_brand_and_no_icon(self):
        self.assertTrue(service_needs_icon_fetch(self._svc()))

    def test_skips_when_port_brand_available(self):
        svc = self._svc(port=8006, url="https://192.168.1.10:8006", name="192.168.1.10:8006")
        self.assertFalse(service_needs_icon_fetch(svc))

    def test_skips_when_cached_upload_icon(self):
        svc = self._svc(icon_url="/uploads/icons/abc.png")
        self.assertFalse(service_needs_icon_fetch(svc))


class SaveCachedIconTests(unittest.TestCase):
    def test_save_returns_upload_path(self):
        path = save_cached_icon("10.0.0.5", 443, b"\x89PNG\r\n\x1a\n" + b"x" * 64, ".png")
        self.assertTrue(path.startswith("/uploads/icons/svc_"))


if __name__ == "__main__":
    unittest.main()
