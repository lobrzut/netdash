"""Port profile selection for manual scans (v1.3.153)."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from app.scanner import (
    POPULAR_HOMELAB_PORTS,
    SAFE_WEB_PORTS,
    SERVICE_PORTS,
    resolve_manual_scan_ports,
)


class ScanPortProfileTests(unittest.TestCase):
    def test_default_safe_is_short(self):
        with patch("app.scanner.settings") as s:
            s.scan_all_ports = False
            s.scan_port_profile = "safe"
            s.scan_safe_mode = True
            ports = resolve_manual_scan_ports(full_scan=False)
        self.assertLessEqual(len(ports), 20)
        self.assertIn(80, ports)
        self.assertIn(22, ports)
        self.assertNotIn(6363, ports)

    def test_full_scan_uses_popular_even_in_safe_mode(self):
        with patch("app.scanner.settings") as s:
            s.scan_all_ports = False
            s.scan_port_profile = "safe"
            s.scan_safe_mode = True
            ports = resolve_manual_scan_ports(full_scan=True)
        for p in (6363, 2283, 8096, 32400, 8989, 5055, 51820):
            self.assertIn(p, ports, f"missing popular port {p}")
        self.assertLess(len(ports), 80)
        self.assertNotEqual(ports, sorted(set(SERVICE_PORTS + [22])))

    def test_profile_popular(self):
        with patch("app.scanner.settings") as s:
            s.scan_all_ports = False
            s.scan_port_profile = "popular"
            s.scan_safe_mode = True
            ports = resolve_manual_scan_ports(full_scan=False)
        self.assertIn(6363, ports)
        self.assertTrue(set(POPULAR_HOMELAB_PORTS).issubset(set(ports)))

    def test_all_listed_and_scan_all_ports(self):
        with patch("app.scanner.settings") as s:
            s.scan_all_ports = True
            s.scan_port_profile = "safe"
            s.scan_safe_mode = True
            ports = resolve_manual_scan_ports(full_scan=False)
        self.assertIn(6363, ports)
        self.assertIn(51820, ports)
        self.assertGreaterEqual(len(ports), len(SERVICE_PORTS))

    def test_service_ports_include_homelab_additions(self):
        for p in (6363, 2283, 5055, 8334, 51820):
            self.assertIn(p, SERVICE_PORTS)

    def test_safe_web_unchanged_core(self):
        for p in (80, 443, 8006, 5000, 5001, 8080, 8081):
            self.assertIn(p, SAFE_WEB_PORTS)


if __name__ == "__main__":
    unittest.main()
