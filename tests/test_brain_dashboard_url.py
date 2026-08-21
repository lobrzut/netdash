"""Pomnia dashboard URL derivation from stats/healthz endpoint."""

from __future__ import annotations

import unittest

from app.url_utils import brain_dashboard_url


class BrainDashboardUrlTests(unittest.TestCase):
    def test_strips_trailing_stats_path(self) -> None:
        self.assertEqual(
            brain_dashboard_url("http://192.168.1.201:7860/stats"),
            "http://192.168.1.201:7860/",
        )

    def test_strips_stats_with_trailing_slash(self) -> None:
        self.assertEqual(
            brain_dashboard_url("http://192.168.1.201:7860/stats/"),
            "http://192.168.1.201:7860/",
        )

    def test_strips_healthz_path(self) -> None:
        self.assertEqual(
            brain_dashboard_url("http://192.168.1.150:7865/healthz"),
            "http://192.168.1.150:7865/",
        )

    def test_preserves_non_stats_path(self) -> None:
        self.assertEqual(
            brain_dashboard_url("http://192.168.1.201:7860/"),
            "http://192.168.1.201:7860/",
        )

    def test_empty_returns_none(self) -> None:
        self.assertIsNone(brain_dashboard_url(None))
        self.assertIsNone(brain_dashboard_url("   "))

    def test_invalid_returns_none(self) -> None:
        self.assertIsNone(brain_dashboard_url("not-a-url"))


if __name__ == "__main__":
    unittest.main()
