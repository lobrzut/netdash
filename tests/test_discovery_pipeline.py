"""Unit tests for adaptive tiered discovery (no live network)."""

from __future__ import annotations

import unittest

from app.config import settings
from app.discovery_pipeline import (
    _hosts_needing_port_scan,
    _select_cycle_cidr,
    _select_cycle_cidrs,
    _should_mark_missing_offline,
    detect_hardware_profile,
    format_status_line,
    get_profile_config,
)


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
    def test_format_status_line(self):
        line = format_status_line(
            {"tcp": 3, "arp_mac_added": 2, "services": 4, "arp_skipped": 0, "chunk": 5},
            "weak",
        )
        self.assertIn("tcp 3", line)
        self.assertIn("arp +2 MAC", line)
        self.assertIn("4 usług", line)
        self.assertIn("chunk 5", line)
        self.assertIn("profil: weak", line)

    def test_format_status_line_arp_skipped(self):
        line = format_status_line({"tcp": 1, "arp_skipped": 1}, "weak")
        self.assertIn("arp wyłączony", line)


class ChunkSelectionTests(unittest.TestCase):
    def test_weak_profile_chunks_wide_cidr(self):
        profile = get_profile_config("weak")
        chunk = _select_cycle_cidr("192.168.1.0/24", profile)
        self.assertTrue(chunk.endswith("/28"))

    def test_weak_rotates_single_chunk_per_cycle(self):
        original_cidr = settings.scan_cidr
        try:
            settings.scan_cidr = "192.168.1.0/24"
            profile = get_profile_config("weak")
            cidrs = _select_cycle_cidrs("192.168.1.0/24", profile)
            self.assertEqual(len(cidrs), 1)
            self.assertTrue(cidrs[0].endswith("/28"))
        finally:
            settings.scan_cidr = original_cidr


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


if __name__ == "__main__":
    unittest.main()
