"""Unit tests for discovery policy resolution and scheduling."""

from __future__ import annotations

import os
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from app.discovery_policy import (
    legacy_policy_from_settings,
    normalize_policy,
    parse_discovery_schedule,
    policy_runs_background,
    resolve_discovery_policy,
    seconds_until_next_run,
)


class NormalizePolicyTests(unittest.TestCase):
    def test_valid_policies(self):
        for name in ("off", "on_demand", "scheduled", "passive", "adaptive"):
            self.assertEqual(normalize_policy(name), name)

    def test_legacy_aliases(self):
        self.assertEqual(normalize_policy("arp"), "passive")
        self.assertEqual(normalize_policy("local"), "on_demand")
        self.assertEqual(normalize_policy("adaptive"), "adaptive")

    def test_unknown_defaults_on_demand(self):
        self.assertEqual(normalize_policy("bogus"), "on_demand")


class ResolvePolicyTests(unittest.TestCase):
    def tearDown(self):
        os.environ.pop("NETDASH_DISCOVERY_POLICY", None)
        os.environ.pop("NETDASH_DISCOVERY_ENABLED", None)

    def test_env_policy_wins(self):
        with patch.dict(os.environ, {"NETDASH_DISCOVERY_POLICY": "passive"}):
            self.assertEqual(resolve_discovery_policy("on_demand"), "passive")

    def test_db_policy_when_env_unset(self):
        os.environ.pop("NETDASH_DISCOVERY_POLICY", None)
        self.assertEqual(resolve_discovery_policy("scheduled"), "scheduled")

    def test_legacy_adaptive_mode(self):
        os.environ.pop("NETDASH_DISCOVERY_POLICY", None)
        with patch("app.config.settings") as mock_settings:
            mock_settings.scan_disabled = False
            mock_settings.discovery_mode = "adaptive"
            self.assertEqual(legacy_policy_from_settings(), "adaptive")

    def test_legacy_disabled_env(self):
        with patch.dict(os.environ, {"NETDASH_DISCOVERY_ENABLED": "false"}):
            self.assertEqual(legacy_policy_from_settings(), "off")


class ScheduleParseTests(unittest.TestCase):
    def test_daily_time(self):
        spec = parse_discovery_schedule("03:00")
        self.assertEqual(spec.kind, "daily")
        self.assertEqual(spec.daily_at, (3, 0))

    def test_interval_hours(self):
        spec = parse_discovery_schedule("6h")
        self.assertEqual(spec.kind, "interval")
        self.assertEqual(spec.interval_sec, 6 * 3600)

    def test_seconds_until_interval(self):
        spec = parse_discovery_schedule("24h")
        self.assertEqual(seconds_until_next_run(spec), 86400.0)

    def test_seconds_until_daily_future(self):
        spec = parse_discovery_schedule("23:59")
        now = datetime(2026, 8, 12, 12, 0, tzinfo=timezone.utc)
        wait = seconds_until_next_run(spec, now=now)
        self.assertGreater(wait, 3600)


class PolicyBehaviorTests(unittest.TestCase):
    def test_background_policies(self):
        self.assertFalse(policy_runs_background("off"))
        self.assertFalse(policy_runs_background("on_demand"))
        self.assertTrue(policy_runs_background("scheduled"))
        self.assertTrue(policy_runs_background("passive"))
        self.assertTrue(policy_runs_background("adaptive"))


if __name__ == "__main__":
    unittest.main()
