"""Tests for the persistent failure cache helpers."""

import json
import os
import tempfile
import time
import unittest

import main


class FailureCacheTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.path = os.path.join(self.temp_dir.name, "failed_cards.json")

    def test_load_returns_empty_when_missing(self):
        self.assertEqual(main.load_failure_cache(self.path), {})

    def test_round_trip_save_and_load(self):
        main.save_failure_cache(self.path, {12345: time.time(), 67890: time.time() - 10})

        loaded = main.load_failure_cache(self.path)

        self.assertEqual(set(loaded.keys()), {12345, 67890})

    def test_expired_entries_are_dropped_on_load(self):
        old = time.time() - (30 * 86400)  # 30 days ago
        fresh = time.time() - 60
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump({"100": old, "200": fresh}, f)

        loaded = main.load_failure_cache(self.path, ttl_days=14)

        self.assertEqual(set(loaded.keys()), {200})

    def test_bad_json_is_ignored(self):
        with open(self.path, "w", encoding="utf-8") as f:
            f.write("not json")

        self.assertEqual(main.load_failure_cache(self.path), {})

    def test_non_dict_payload_is_ignored(self):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump([1, 2, 3], f)

        self.assertEqual(main.load_failure_cache(self.path), {})

    def test_save_is_atomic(self):
        """After save, no stray .part file should remain."""
        main.save_failure_cache(self.path, {1: time.time()})

        self.assertFalse(os.path.exists(self.path + ".part"))
        self.assertTrue(os.path.exists(self.path))


if __name__ == "__main__":
    unittest.main()
