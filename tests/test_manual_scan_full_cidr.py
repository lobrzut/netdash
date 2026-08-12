"""Manual scan may accept /24 under safe_mode when allow_full_cidr is on."""

from __future__ import annotations

import unittest

from app import scanner
from app.config import settings


class ManualScanFullCidrTests(unittest.TestCase):
    def setUp(self) -> None:
        self._orig = {
            "scan_safe_mode": settings.scan_safe_mode,
            "manual_scan_allow_full_cidr": settings.manual_scan_allow_full_cidr,
            "manual_scan_max_hosts": settings.manual_scan_max_hosts,
            "scan_safe_block_wide": settings.scan_safe_block_wide,
            "scan_safe_min_prefix": settings.scan_safe_min_prefix,
            "discovery_policy": settings.discovery_policy,
        }
        settings.scan_safe_mode = True
        settings.manual_scan_allow_full_cidr = True
        settings.manual_scan_max_hosts = 256
        settings.scan_safe_block_wide = True
        settings.scan_safe_min_prefix = 28

    def tearDown(self) -> None:
        for key, value in self._orig.items():
            setattr(settings, key, value)

    def test_validate_accepts_slash24_under_safe_mode(self) -> None:
        scanner.validate_manual_scan_cidrs(["192.168.1.0/24"])

    def test_expand_keeps_full_cidr_for_manual(self) -> None:
        expanded = scanner.expand_cidrs_for_safe_mode(
            ["192.168.1.0/24"], for_manual=True
        )
        self.assertEqual(expanded, ["192.168.1.0/24"])

    def test_legacy_block_still_rejects_when_disabled(self) -> None:
        settings.manual_scan_allow_full_cidr = False
        with self.assertRaises(scanner.ScanError) as ctx:
            scanner.validate_manual_scan_cidrs(["192.168.1.0/24"])
        self.assertEqual(ctx.exception.code, "cidr_too_wide")

    def test_parse_cidr_manual_uses_manual_host_cap(self) -> None:
        hosts = scanner.parse_cidr("192.168.1.0/24", manual_scan=True)
        self.assertGreaterEqual(len(hosts), 200)
        self.assertLessEqual(len(hosts), settings.effective_manual_scan_max_hosts)

    def test_detected_cidrs_prefer_configured_slash24(self) -> None:
        cidrs = scanner.get_detected_cidrs("192.168.1.0/24")
        self.assertIn("192.168.1.0/24", cidrs)
        self.assertEqual(cidrs[0], "192.168.1.0/24")


if __name__ == "__main__":
    unittest.main()
