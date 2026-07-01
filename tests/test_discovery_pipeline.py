"""Unit tests for adaptive tiered discovery (no live network)."""

from __future__ import annotations

import unittest

from app.config import settings
from app.discovery_pipeline import (
    _hosts_needing_port_scan,
    _pick_rotated_cidr,
    _select_cycle_cidr,
    _select_cycle_cidrs,
    _should_mark_missing_offline,
    detect_hardware_profile,
    format_status_line,
    get_profile_config,
)
from app.scanner import ScanError, validate_manual_scan_cidrs


class ProfileDetectionTests(unittest.TestCase):
    def test_explicit_weak_profile(self):
        original = settings.discovery_profile
        try:
            settings.discovery_profile = "weak"
            self.assertEqual(detect_hardware_profile(), "weak")
        finally:
            settings.discovery_profile = original

    def test_profile_config_weak(self):
        cfg = get_profile_config("weak")
        self.assertEqual(cfg.tcp_parallel, 8)
        self.assertEqual(cfg.port_parallel, 4)
        self.assertEqual(cfg.interval_sec, 300)
        self.assertEqual(cfg.max_hosts, 16)


class StatusLineTests(unittest.TestCase):
    def test_format_status_line_chunked(self):
        line = format_status_line(
            {
                "tcp": 3,
                "services": 12,
                "chunk_index": 3,
                "chunk_total": 16,
            },
            "weak",
        )
        self.assertIn("Skan TCP: chunk 3/16", line)
        self.assertIn("12 serwisów", line)
        self.assertIn("profil: weak", line)

    def test_format_status_line_dual_chunk(self):
        line = format_status_line(
            {
                "tcp": 2,
                "services": 6,
                "chunk_index": 1,
                "chunk_index_secondary": 9,
                "chunk_total": 16,
            },
            "weak",
        )
        self.assertIn("Skan TCP: chunk 1+9/16", line)
        self.assertIn("6 serwisów", line)

    def test_format_status_line_full_cidr(self):
        line = format_status_line({"tcp": 8, "services": 24}, "strong")
        self.assertIn("8 hostów", line)
        self.assertIn("24 serwisów", line)
        self.assertIn("profil: strong", line)


class ChunkSelectionTests(unittest.TestCase):
    def test_weak_profile_chunks_wide_cidr(self):
        profile = get_profile_config("weak")
        chunk = _select_cycle_cidr("192.168.1.0/24", profile)
        self.assertTrue(chunk.endswith("/28"))

    def test_weak_rotates_dual_chunks_per_cycle(self):
        original_cidr = settings.scan_cidr
        try:
            settings.scan_cidr = "192.168.1.0/24"
            profile = get_profile_config("weak")
            import app.discovery_pipeline as dp

            dp._chunk_index = 0
            cidrs = _select_cycle_cidrs("192.168.1.0/24", profile)
            self.assertEqual(len(cidrs), 2)
            self.assertTrue(all(c.endswith("/28") for c in cidrs))
            self.assertEqual(cidrs[0], "192.168.1.0/28")
            self.assertEqual(cidrs[1], "192.168.1.128/28")
            self.assertEqual(dp._state["chunk_index"], 1)
            self.assertEqual(dp._state["chunk_index_secondary"], 9)

            cidrs2 = _select_cycle_cidrs("192.168.1.0/24", profile)
            self.assertEqual(cidrs2[0], "192.168.1.32/28")
            self.assertEqual(cidrs2[1], "192.168.1.160/28")
            self.assertEqual(dp._state["chunk_index"], 3)
            self.assertEqual(dp._state["chunk_index_secondary"], 11)
            dp._chunk_index = 0
        finally:
            settings.scan_cidr = original_cidr

    def test_normal_profile_chunks_when_always_chunk_enabled(self):
        original = settings.auto_discovery_always_chunk
        try:
            settings.auto_discovery_always_chunk = True
            profile = get_profile_config("normal")
            import app.discovery_pipeline as dp

            dp._chunk_index = 0
            chunk = _select_cycle_cidr("192.168.1.0/24", profile)
            self.assertTrue(chunk.endswith("/28"))
        finally:
            settings.auto_discovery_always_chunk = original

    def test_cidr_rotation(self):
        import app.discovery_pipeline as dp

        dp._cidr_index = 0
        first = _pick_rotated_cidr(["192.168.1.0/24", "192.168.10.0/24"])
        second = _pick_rotated_cidr(["192.168.1.0/24", "192.168.10.0/24"])
        self.assertEqual(first, "192.168.1.0/24")
        self.assertEqual(second, "192.168.10.0/24")
        dp._cidr_index = 0


class ManualScanValidationTests(unittest.TestCase):
    def test_rejects_wider_than_slash_24(self):
        with self.assertRaises(ScanError) as ctx:
            validate_manual_scan_cidrs(["192.168.0.0/23"])
        self.assertEqual(ctx.exception.code, "manual_cidr_too_wide")

    def test_rejects_too_many_hosts(self):
        original_hosts = settings.manual_scan_max_hosts
        original_safe = settings.scan_safe_mode
        try:
            settings.scan_safe_mode = False
            settings.manual_scan_max_hosts = 32
            with self.assertRaises(ScanError) as ctx:
                validate_manual_scan_cidrs(["192.168.1.0/24"])
            self.assertEqual(ctx.exception.code, "manual_too_many_hosts")
        finally:
            settings.manual_scan_max_hosts = original_hosts
            settings.scan_safe_mode = original_safe

    def test_allows_slash_28(self):
        validate_manual_scan_cidrs(["192.168.1.144/28"])


class OfflineMarkingTests(unittest.TestCase):
    def test_never_mass_offline_tcp_chunks(self):
        self.assertFalse(
            _should_mark_missing_offline(
                ["192.168.1.192/28"],
                {"arp_mac_added": 5, "tcp": 8, "arp_skipped": 0},
                8,
            )
        )


class PortScanTargetTests(unittest.TestCase):
    def test_new_hosts_always_probed(self):
        targets = _hosts_needing_port_scan({"192.168.1.10", "192.168.1.11"}, {"192.168.1.11"})
        self.assertIn("192.168.1.11", targets)


class SafeWebPortsTests(unittest.TestCase):
    def test_safe_web_ports_includes_proxmox(self):
        from app.scanner import SAFE_WEB_PORTS

        self.assertIn(8006, SAFE_WEB_PORTS)

    def test_safe_web_ports_includes_qnap(self):
        from app.scanner import SAFE_WEB_PORTS

        for port in (5000, 5001, 8080, 8081, 873, 2049):
            self.assertIn(port, SAFE_WEB_PORTS, f"QNAP port {port} missing from SAFE_WEB_PORTS")


if __name__ == "__main__":
    unittest.main()
