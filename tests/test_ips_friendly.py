"""Unit tests for IPS-friendly (stealth) per-host port probing (v1.3.149)."""

from __future__ import annotations

import asyncio
import time
import unittest
from unittest import mock

from app import scanner
from app.config import settings


class EffectiveSettingsTests(unittest.TestCase):
    def test_ips_friendly_caps_per_host(self):
        original = settings.ips_friendly
        try:
            settings.ips_friendly = True
            self.assertEqual(settings.effective_port_parallel_per_host, 1)
            self.assertGreater(settings.effective_ports_per_host_delay, 0.0)
        finally:
            settings.ips_friendly = original

    def test_disabled_falls_back_to_broad_concurrency(self):
        original = settings.ips_friendly
        try:
            settings.ips_friendly = False
            self.assertEqual(settings.effective_ports_per_host_delay, 0.0)
            self.assertGreaterEqual(
                settings.effective_port_parallel_per_host,
                settings.effective_scan_concurrency,
            )
        finally:
            settings.ips_friendly = original


class ProbeHostPortsTests(unittest.IsolatedAsyncioTestCase):
    async def test_serial_when_ips_friendly(self):
        """With per-host parallelism 1, no two probes to a host overlap."""
        overlap = {"max": 0, "cur": 0}

        async def fake_check(host: str, port: int) -> bool:
            overlap["cur"] += 1
            overlap["max"] = max(overlap["max"], overlap["cur"])
            await asyncio.sleep(0.01)
            overlap["cur"] -= 1
            return port == 80

        originals = (
            settings.ips_friendly,
            settings.ports_per_host_delay,
            settings.ports_per_host_jitter,
            settings.port_parallel_per_host,
        )
        try:
            settings.ips_friendly = True
            settings.ports_per_host_delay = 0.0
            settings.ports_per_host_jitter = 0.0
            settings.port_parallel_per_host = 1
            with mock.patch.object(scanner, "_check_port_raw", fake_check):
                found = await scanner._probe_host_ports("10.0.0.1", [22, 80, 443, 8080])
            self.assertEqual(overlap["max"], 1)
            self.assertEqual(found, [80])
        finally:
            (
                settings.ips_friendly,
                settings.ports_per_host_delay,
                settings.ports_per_host_jitter,
                settings.port_parallel_per_host,
            ) = originals

    async def test_delay_spreads_probes(self):
        async def fake_check(host: str, port: int) -> bool:
            return False

        originals = (settings.ips_friendly, settings.ports_per_host_delay, settings.ports_per_host_jitter)
        try:
            settings.ips_friendly = True
            settings.ports_per_host_delay = 0.05
            settings.ports_per_host_jitter = 0.0
            with mock.patch.object(scanner, "_check_port_raw", fake_check):
                start = time.monotonic()
                await scanner._probe_host_ports("10.0.0.2", [22, 80, 443])
                elapsed = time.monotonic() - start
            # 3 ports * 0.05 s spacing => noticeably more than an instant burst.
            self.assertGreaterEqual(elapsed, 0.1)
        finally:
            settings.ips_friendly, settings.ports_per_host_delay, settings.ports_per_host_jitter = originals

    async def test_stop_on_first_returns_single_open(self):
        async def fake_check(host: str, port: int) -> bool:
            return True

        originals = (settings.ips_friendly, settings.ports_per_host_delay, settings.scan_randomize_ports)
        try:
            settings.ips_friendly = True
            settings.ports_per_host_delay = 0.0
            settings.scan_randomize_ports = False
            with mock.patch.object(scanner, "_check_port_raw", fake_check):
                found = await scanner._probe_host_ports(
                    "10.0.0.3", [22, 80, 443], stop_on_first=True
                )
            self.assertEqual(len(found), 1)
        finally:
            settings.ips_friendly, settings.ports_per_host_delay, settings.scan_randomize_ports = originals


if __name__ == "__main__":
    unittest.main()
