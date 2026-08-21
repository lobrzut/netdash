"""Unit tests for Pomnia → NetDash tile stats normalization."""

from __future__ import annotations

import unittest

from app.pomnia_stats import normalize_pomnia_stats


class NormalizePomniaStatsTests(unittest.TestCase):
    def test_healthz_with_index_counts(self) -> None:
        raw = {
            "ok": True,
            "service": "brain-core",
            "version": "0.1.65",
            "status": "ok",
            "uptimeSec": 410,
            "embed": {"backend": "fastembed", "model": "x", "ready": True},
            "index": {"files": 1, "chunks": 2},
        }
        out = normalize_pomnia_stats(raw, dashboard_url="http://192.168.1.150:7865/")
        self.assertTrue(out["ok"])
        self.assertEqual(out["schema"], "pomnia")
        self.assertEqual(out["index_files"], 1)
        self.assertEqual(out["index_chunks"], 2)
        self.assertTrue(out["counts_available"])
        self.assertEqual(out["uptime_sec"], 410)
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["version"], "0.1.65")
        self.assertEqual(out["notes"], 1)
        self.assertEqual(out["library_docs"], 2)
        self.assertEqual(out["graph_nodes"], 2)
        self.assertIsNone(out["sessions"])
        self.assertIsNone(out["code_files"])

    def test_redacted_index_is_not_fake_zero(self) -> None:
        raw = {
            "ok": True,
            "status": "ok",
            "uptimeSec": 12,
            "index": None,
            "notes": 0,
            "sessions": 0,
            "library_docs": 0,
            "code_files": 0,
            "graph_nodes": 0,
        }
        out = normalize_pomnia_stats(raw)
        self.assertFalse(out["counts_available"])
        self.assertIsNone(out["index_files"])
        self.assertIsNone(out["index_chunks"])
        self.assertIsNone(out["notes"])
        self.assertIsNone(out["graph_nodes"])
        self.assertEqual(out["uptime_sec"], 12)
        self.assertEqual(out["status"], "ok")

    def test_legacy_brain_hub_without_index_key(self) -> None:
        raw = {
            "notes": 10,
            "sessions": 3,
            "library_docs": 4,
            "code_files": 2,
            "graph_nodes": 99,
        }
        out = normalize_pomnia_stats(raw)
        self.assertTrue(out["counts_available"])
        self.assertEqual(out["index_files"], 10)
        self.assertEqual(out["index_chunks"], 99)


if __name__ == "__main__":
    unittest.main()
