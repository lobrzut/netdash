"""Targeted single-host/port probe + popular port profile."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from app import scanner
from app.config import settings
from app.scanner import (
    DiscoveredService,
    normalize_probe_host,
    probe_single_host_port,
    resolve_manual_scan_ports,
)


class ProbeHostValidationTests(unittest.TestCase):
    def test_accepts_ipv4(self):
        self.assertEqual(normalize_probe_host(" 192.168.1.150 "), "192.168.1.150")

    def test_rejects_cidr(self):
        with self.assertRaises(ValueError):
            normalize_probe_host("192.168.1.0/24")

    def test_rejects_empty(self):
        with self.assertRaises(ValueError):
            normalize_probe_host("  ")


class PopularPortsProfileTests(unittest.TestCase):
    def setUp(self) -> None:
        self._orig = {
            "scan_safe_mode": settings.scan_safe_mode,
            "scan_port_profile": settings.scan_port_profile,
            "scan_all_ports": settings.scan_all_ports,
        }
        settings.scan_safe_mode = True
        settings.scan_port_profile = "safe"
        settings.scan_all_ports = False

    def tearDown(self) -> None:
        for key, value in self._orig.items():
            setattr(settings, key, value)

    def test_basic_safe_excludes_qbittorrent(self):
        ports = resolve_manual_scan_ports(full_scan=False)
        self.assertNotIn(6363, ports)
        self.assertIn(80, ports)

    def test_popular_includes_homelab_stack(self):
        ports = resolve_manual_scan_ports(full_scan=True)
        for expected in (6363, 2283, 7878, 8989, 8096, 8123, 32400):
            self.assertIn(expected, ports, msg=f"missing {expected}")
        self.assertLess(len(ports), 100)


class ProbeSingleHostTests(unittest.IsolatedAsyncioTestCase):
    async def test_closed_port_no_http(self):
        with patch("app.scanner.tcp_port_open_sync", return_value="refused"), patch(
            "app.scanner._probe_http_detailed", new_callable=AsyncMock
        ) as http:
            result = await probe_single_host_port("192.168.1.150", 6363)
        self.assertFalse(result["open"])
        self.assertEqual(result["tcp_status"], "refused")
        self.assertFalse(result["identified"])
        http.assert_not_awaited()

    async def test_open_identifies_qbittorrent(self):
        discovered = DiscoveredService(
            host="192.168.1.150",
            port=6363,
            name="qBittorrent",
            url="http://192.168.1.150:6363",
            protocol="http",
            category="Media",
            icon="download",
            has_login=True,
        )
        with patch("app.scanner.tcp_port_open_sync", return_value="open"), patch(
            "app.scanner._probe_http_detailed",
            new_callable=AsyncMock,
            return_value=(discovered, 200),
        ):
            result = await probe_single_host_port("192.168.1.150", 6363, protocol="auto")
        self.assertTrue(result["open"])
        self.assertTrue(result["identified"])
        self.assertEqual(result["name"], "qBittorrent")
        self.assertEqual(result["status_code"], 200)
        self.assertEqual(result["service"].name, "qBittorrent")

    async def test_tcp_protocol_skips_http(self):
        with patch("app.scanner.tcp_port_open_sync", return_value="open"), patch(
            "app.scanner._probe_http_detailed", new_callable=AsyncMock
        ) as http:
            result = await probe_single_host_port("10.0.0.5", 22, protocol="tcp")
        http.assert_not_awaited()
        self.assertTrue(result["open"])
        self.assertEqual(result["protocol"], "tcp")
        self.assertEqual(result["name"], "SSH")

    async def test_auto_tries_http_on_uncommon_port(self):
        discovered = DiscoveredService(
            host="10.0.0.9",
            port=4210,
            name="Custom App",
            url="http://10.0.0.9:4210",
            protocol="http",
            category="Web",
            icon="globe",
        )
        with patch("app.scanner.tcp_port_open_sync", return_value="open"), patch(
            "app.scanner._probe_http_detailed",
            new_callable=AsyncMock,
            return_value=(discovered, 200),
        ) as http:
            result = await probe_single_host_port("10.0.0.9", 4210, protocol="auto")
        http.assert_awaited_once()
        self.assertEqual(result["name"], "Custom App")


class IdentifyUsesPopularPorts(unittest.IsolatedAsyncioTestCase):
    async def test_identify_http_for_6363(self):
        discovered = DiscoveredService(
            host="1.2.3.4",
            port=6363,
            name="qBittorrent",
            url="http://1.2.3.4:6363",
            protocol="http",
            category="Media",
            icon="download",
        )
        with patch(
            "app.scanner._probe_http",
            new_callable=AsyncMock,
            return_value=discovered,
        ) as http:
            service = await scanner._identify_service("1.2.3.4", 6363)
        http.assert_awaited_once()
        self.assertEqual(service.name, "qBittorrent")


if __name__ == "__main__":
    unittest.main()
