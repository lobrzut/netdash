"""Discovery runtime toggle (UI / DB) with env override."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from app.config import settings
from app.discovery_runtime import clear_app_discovery_enabled, set_app_discovery_enabled


class DiscoveryRuntimeTests(unittest.TestCase):
    def tearDown(self) -> None:
        clear_app_discovery_enabled()

    def test_ui_toggle_disables_when_env_unset(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("NETDASH_DISCOVERY_ENABLED", None)
            set_app_discovery_enabled(False)
            self.assertFalse(settings.effective_discovery_enabled)

    def test_ui_toggle_enables_when_env_unset(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("NETDASH_DISCOVERY_ENABLED", None)
            set_app_discovery_enabled(True)
            with patch.object(settings, "discovery_enabled", True):
                with patch("builtins.open", side_effect=OSError):
                    self.assertTrue(settings.effective_discovery_enabled)

    def test_env_lock_overrides_ui(self) -> None:
        set_app_discovery_enabled(True)
        with patch.dict(os.environ, {"NETDASH_DISCOVERY_ENABLED": "false"}):
            self.assertFalse(settings.effective_discovery_enabled)
            self.assertTrue(settings.discovery_env_locked)

    def test_env_lock_allows_true(self) -> None:
        set_app_discovery_enabled(False)
        with patch.dict(os.environ, {"NETDASH_DISCOVERY_ENABLED": "true"}):
            self.assertTrue(settings.effective_discovery_enabled)


if __name__ == "__main__":
    unittest.main()
