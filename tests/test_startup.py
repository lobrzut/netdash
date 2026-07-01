"""Startup defer settings (no live network)."""

from __future__ import annotations

import unittest

from app.config import settings


class StartupDeferTests(unittest.TestCase):
    def test_startup_health_defer_auto_safe_mode(self):
        original_defer = settings.startup_health_defer
        original_safe = settings.scan_safe_mode
        try:
            settings.startup_health_defer = None
            settings.scan_safe_mode = True
            self.assertTrue(settings.effective_startup_health_defer)
            self.assertEqual(settings.effective_startup_health_defer_seconds, 90)

            settings.scan_safe_mode = False
            self.assertFalse(settings.effective_startup_health_defer)
            self.assertEqual(settings.effective_startup_health_defer_seconds, 5)
        finally:
            settings.startup_health_defer = original_defer
            settings.scan_safe_mode = original_safe

    def test_startup_health_defer_explicit_false(self):
        original_defer = settings.startup_health_defer
        try:
            settings.startup_health_defer = False
            self.assertFalse(settings.effective_startup_health_defer)
        finally:
            settings.startup_health_defer = original_defer

    def test_startup_health_defer_custom_seconds(self):
        original_secs = settings.startup_health_defer_seconds
        try:
            settings.startup_health_defer_seconds = 120
            self.assertEqual(settings.effective_startup_health_defer_seconds, 120)
        finally:
            settings.startup_health_defer_seconds = original_secs

    def test_discovery_startup_delay_default(self):
        original = settings.discovery_startup_delay
        try:
            settings.discovery_startup_delay = 60
            self.assertEqual(settings.discovery_startup_delay, 60)
        finally:
            settings.discovery_startup_delay = original


if __name__ == "__main__":
    unittest.main()
