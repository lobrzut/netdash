"""URL endpoint normalization + host:port duplicate picking."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from app.service_endpoints import pick_endpoint_service
from app.url_utils import normalize_endpoint_url


class NormalizeEndpointUrlTests(unittest.TestCase):
    def test_strips_root_trailing_slash(self) -> None:
        self.assertEqual(
            normalize_endpoint_url("http://192.168.1.150:13378/"),
            "http://192.168.1.150:13378",
        )

    def test_keeps_path(self) -> None:
        self.assertEqual(
            normalize_endpoint_url("http://192.168.1.150:13378/web/"),
            "http://192.168.1.150:13378/web/",
        )

    def test_idempotent_without_slash(self) -> None:
        self.assertEqual(
            normalize_endpoint_url("http://192.168.1.150:13378"),
            "http://192.168.1.150:13378",
        )


class PickEndpointServiceTests(unittest.TestCase):
    def test_prefers_customized(self) -> None:
        auto = SimpleNamespace(id=1, customized=False, pinned=False)
        manual = SimpleNamespace(id=2, customized=True, pinned=False)
        self.assertIs(pick_endpoint_service([auto, manual]), manual)

    def test_prefers_older_when_equal(self) -> None:
        a = SimpleNamespace(id=10, customized=False, pinned=False)
        b = SimpleNamespace(id=20, customized=False, pinned=False)
        self.assertIs(pick_endpoint_service([b, a]), a)


if __name__ == "__main__":
    unittest.main()
