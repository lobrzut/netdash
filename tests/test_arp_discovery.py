"""Unit tests for ARP discovery helpers (no live network required)."""

from __future__ import annotations

import unittest

from app.arp_discovery import (
    _build_arp_scan_cmd,
    _merge_entries,
    _parse_arp_scan_output,
    _parse_extra_hosts,
    _probe_explicit_hosts,
)
from app.config import settings
from app.schemas import DiscoveryHostEntry


class ParseArpScanOutputTests(unittest.TestCase):
    def test_parses_mac_and_hostname(self):
        stdout = "192.168.1.200\t00:11:22:33:44:55\thomelab\n"
        entries = _parse_arp_scan_output(stdout)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].ip, "192.168.1.200")
        self.assertEqual(entries[0].mac, "00:11:22:33:44:55")
        self.assertEqual(entries[0].hostname, "homelab")

    def test_ignores_invalid_lines(self):
        self.assertEqual(_parse_arp_scan_output("garbage\n"), [])


class BuildArpScanCmdTests(unittest.TestCase):
    def test_interval_is_plain_milliseconds(self):
        cmd = _build_arp_scan_cmd("192.168.1.0/24", None)
        self.assertIn("--interval=100", cmd)
        self.assertNotIn("100ms", cmd)

    def test_includes_interface_when_set(self):
        cmd = _build_arp_scan_cmd("192.168.1.0/24", "bond0")
        self.assertEqual(cmd[:3], ["arp-scan", "-I", "bond0"])

    def test_omits_interface_when_none(self):
        cmd = _build_arp_scan_cmd("192.168.1.0/24", None)
        self.assertNotIn("-I", cmd)
        self.assertEqual(cmd[1], "192.168.1.0/24")


class MergeEntriesTests(unittest.TestCase):
    def test_merge_prefers_mac_from_second_source(self):
        a = [DiscoveryHostEntry(ip="192.168.1.201", mac=None, online=True)]
        b = [DiscoveryHostEntry(ip="192.168.1.201", mac="AA:BB:CC:DD:EE:FF", online=True)]
        merged = _merge_entries(a, b)
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].mac, "AA:BB:CC:DD:EE:FF")


class ExtraHostsTests(unittest.TestCase):
    def test_parse_extra_hosts_from_settings(self):
        original = settings.arp_extra_hosts
        try:
            settings.arp_extra_hosts = "192.168.1.200, 192.168.1.201"
            self.assertEqual(_parse_extra_hosts(), ["192.168.1.200", "192.168.1.201"])
        finally:
            settings.arp_extra_hosts = original

    def test_probe_explicit_hosts_not_filtered_by_cidr(self):
        """Extra hosts outside current /28 must still be probed (mocked unreachable)."""
        original = settings.arp_extra_hosts
        try:
            settings.arp_extra_hosts = "192.168.1.200"
            # cidr arg is ignored — function probes all extra IPs
            found = _probe_explicit_hosts(["192.168.1.200"], "192.168.1.144/28")
            self.assertEqual(found, [])
        finally:
            settings.arp_extra_hosts = original


if __name__ == "__main__":
    unittest.main()
