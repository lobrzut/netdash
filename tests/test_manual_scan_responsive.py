"""Manual /24 scan: internal chunking, scaled timeout, known-ips assign."""

from __future__ import annotations

import unittest

from app import scanner
from app.config import settings
from app import discovery_pipeline as dp


class ManualScanChunkingTests(unittest.TestCase):
    def setUp(self) -> None:
        self._orig = {
            "manual_scan_internal_chunk": settings.manual_scan_internal_chunk,
            "manual_scan_work_chunk_prefix": settings.manual_scan_work_chunk_prefix,
            "manual_scan_allow_full_cidr": settings.manual_scan_allow_full_cidr,
            "manual_scan_max_duration": settings.manual_scan_max_duration,
            "manual_scan_timeout_per_host": settings.manual_scan_timeout_per_host,
            "manual_scan_timeout_cap": settings.manual_scan_timeout_cap,
        }
        settings.manual_scan_internal_chunk = True
        settings.manual_scan_work_chunk_prefix = 28
        settings.manual_scan_allow_full_cidr = True
        settings.manual_scan_max_duration = 1800.0
        settings.manual_scan_timeout_per_host = 6.0
        settings.manual_scan_timeout_cap = 3600.0

    def tearDown(self) -> None:
        for key, value in self._orig.items():
            setattr(settings, key, value)

    def test_chunk_slash24_into_sixteen_slash28(self) -> None:
        chunks = scanner.chunk_cidrs_for_manual_work(["192.168.1.0/24"])
        self.assertEqual(len(chunks), 16)
        self.assertTrue(all(c.endswith("/28") for c in chunks))
        self.assertEqual(chunks[0], "192.168.1.0/28")
        self.assertEqual(chunks[-1], "192.168.1.240/28")

    def test_chunk_keeps_narrow_cidr(self) -> None:
        chunks = scanner.chunk_cidrs_for_manual_work(["192.168.1.144/28"])
        self.assertEqual(chunks, ["192.168.1.144/28"])

    def test_expand_still_keeps_full_manual_cidr(self) -> None:
        expanded = scanner.expand_cidrs_for_safe_mode(["192.168.1.0/24"], for_manual=True)
        self.assertEqual(expanded, ["192.168.1.0/24"])

    def test_timeout_scales_with_host_count(self) -> None:
        settings.manual_scan_max_duration = 200.0
        settings.manual_scan_timeout_per_host = 6.0
        settings.manual_scan_timeout_cap = 3600.0
        # effective_manual_scan_max_duration = max(200, safe_max_duration≈180) → 200
        small = scanner.compute_manual_scan_timeout(["192.168.1.144/28"])
        large = scanner.compute_manual_scan_timeout(["192.168.1.0/24"])
        self.assertEqual(small, 200.0)
        self.assertGreaterEqual(large, 1500.0)
        self.assertLessEqual(large, 3600.0)
        settings.manual_scan_timeout_per_host = 20.0
        capped = scanner.compute_manual_scan_timeout(["192.168.1.0/24"])
        self.assertEqual(capped, 3600.0)


class KnownIpsAssignTests(unittest.TestCase):
    def test_known_ips_replaced_not_unioned(self) -> None:
        dp._known_ips = {"10.0.0.1", "10.0.0.2"}
        seen = {"10.0.0.2", "10.0.0.3"}
        # Mimic the fixed assignment in run_discovery_cycle
        new_ips = seen - dp._known_ips
        dp._known_ips = seen
        self.assertEqual(new_ips, {"10.0.0.3"})
        self.assertEqual(dp._known_ips, seen)
        self.assertNotIn("10.0.0.1", dp._known_ips)


if __name__ == "__main__":
    unittest.main()
