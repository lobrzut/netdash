"""Unit tests for adaptive tiered discovery (no live network)."""

from __future__ import annotations

import unittest

from app.config import settings
from app.discovery_pipeline import (
    _hosts_needing_port_scan,
    _select_cycle_cidr,
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
        self.assertEqual(cfg.ping_parallel, 8)
        self.assertEqual(cfg.port_parallel, 1)
        self.assertEqual(cfg.interval_sec, 300)


class StatusLineTests(unittest.TestCase):
    def test_format_status_line(self):
        line = format_status_line(
            {"ping": 42, "arp_mac_added": 12, "ports_new": 3, "arp_skipped": 0},
            "weak",
        )
        self.assertIn("ping 42", line)
        self.assertIn("arp +12 MAC", line)
        self.assertIn("3 nowe porty", line)
        self.assertIn("profil: weak", line)

    def test_format_status_line_arp_skipped(self):
        line = format_status_line({"ping": 5, "arp_skipped": 1}, "weak")
        self.assertIn("arp wyłączony", line)


class ChunkSelectionTests(unittest.TestCase):
    def test_weak_profile_chunks_wide_cidr(self):
        profile = get_profile_config("weak")
        chunk = _select_cycle_cidr("192.168.1.0/24", profile)
        self.assertTrue(chunk.endswith("/28"))


class PortScanTargetTests(unittest.TestCase):
    def test_new_hosts_always_probed(self):
        targets = _hosts_needing_port_scan({"192.168.1.10", "192.168.1.11"}, {"192.168.1.11"})
        self.assertIn("192.168.1.11", targets)


if __name__ == "__main__":
    unittest.main()
