"""Health probe behaviour for local and port services."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from app.health import _is_host_only, apply_health_result, check_service_online
from app.models import Service


class HostOnlyDetectionTests(unittest.TestCase):
    def test_host_protocol_is_host_only(self):
        svc = Service(name="x", url="", host="10.0.0.1", port=22, protocol="host")
        self.assertTrue(_is_host_only(svc))

    def test_port_zero_is_host_only(self):
        svc = Service(name="x", url="", host="10.0.0.1", port=0, protocol="http")
        self.assertTrue(_is_host_only(svc))

    def test_http_port_is_not_host_only(self):
        svc = Service(name="x", url="http://10.0.0.1:3000", host="10.0.0.1", port=3000, protocol="http")
        self.assertFalse(_is_host_only(svc))


class LocalPortHealthTests(unittest.IsolatedAsyncioTestCase):
    async def test_local_http_service_is_probed_not_assumed_online(self):
        svc = Service(
            name="Khoj",
            url="http://192.168.1.248:4210",
            host="192.168.1.248",
            port=4210,
            protocol="http",
        )
        with patch("app.health.get_local_ip", return_value="192.168.1.248"), patch(
            "app.health._check_http_url", new_callable=AsyncMock, return_value=(False, None)
        ) as probe:
            online, _ = await check_service_online(svc)
        self.assertFalse(online)
        probe.assert_awaited_once()

    async def test_local_host_only_stays_online(self):
        svc = Service(name="VM", url="", host="192.168.1.248", port=0, protocol="host")
        with patch("app.health.get_local_ip", return_value="192.168.1.248"):
            online, _ = await check_service_online(svc)
        self.assertTrue(online)

    async def test_has_login_local_uses_http_not_ping(self):
        svc = Service(
            name="Hermes",
            url="http://192.168.1.248:8080",
            host="192.168.1.248",
            port=8080,
            protocol="http",
            has_login=True,
        )
        with patch("app.health.get_local_ip", return_value="192.168.1.248"), patch(
            "app.health._check_http_url", new_callable=AsyncMock, return_value=(False, None)
        ) as probe, patch("app.scanner._ping_host", new_callable=AsyncMock, return_value=True) as ping:
            online, _ = await check_service_online(svc)
        self.assertFalse(online)
        probe.assert_awaited_once()
        ping.assert_not_awaited()


class HealthFailStreakTests(unittest.IsolatedAsyncioTestCase):
    async def test_offline_after_threshold_failures(self):
        svc = Service(
            name="x",
            url="http://1.2.3.4",
            host="1.2.3.4",
            port=80,
            protocol="http",
            is_online=True,
            health_fail_streak=0,
        )
        db = AsyncMock()
        with patch("app.health.settings") as cfg:
            cfg.health_offline_after_failures = 2
            await apply_health_result(db, svc, False)
            self.assertTrue(svc.is_online)
            self.assertEqual(svc.health_fail_streak, 1)
            await apply_health_result(db, svc, False)
            self.assertFalse(svc.is_online)
            self.assertEqual(svc.health_fail_streak, 2)

    async def test_success_resets_streak(self):
        svc = Service(
            name="x",
            url="http://1.2.3.4",
            host="1.2.3.4",
            port=80,
            protocol="http",
            is_online=False,
            health_fail_streak=3,
        )
        db = AsyncMock()
        with patch("app.health.settings") as cfg:
            cfg.health_offline_after_failures = 2
            await apply_health_result(db, svc, True)
        self.assertTrue(svc.is_online)
        self.assertEqual(svc.health_fail_streak, 0)


if __name__ == "__main__":
    unittest.main()
