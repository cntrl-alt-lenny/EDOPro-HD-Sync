"""Tests for Field Spell playmat artwork support (pics/field/)."""

import asyncio
import os
import sqlite3
import tempfile
import types
import unittest
from unittest import mock

import main

JPEG_BODY = b"\xff\xd8\xff" + b"\x00" * 1024
PNG_BODY = main.PNG_MAGIC + b"\x00" * 1024

FIELD_SPELL_TYPE = 0x80002
PLAIN_SPELL_TYPE = 0x2
MONSTER_TYPE = 0x11


class ScanDetectsFieldSpellsTests(unittest.TestCase):
    def _make_db(self, path, rows):
        conn = sqlite3.connect(path)
        try:
            conn.execute("CREATE TABLE datas (id INTEGER PRIMARY KEY, type INTEGER)")
            conn.execute("CREATE TABLE texts (id INTEGER PRIMARY KEY, name TEXT)")
            conn.executemany(
                "INSERT INTO datas (id, type) VALUES (?, ?)",
                [(cid, ctype) for cid, ctype, _ in rows],
            )
            conn.executemany(
                "INSERT INTO texts (id, name) VALUES (?, ?)", [(cid, name) for cid, _, name in rows]
            )
            conn.commit()
        finally:
            conn.close()

    def test_field_spells_are_detected_by_type_bits(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "cards.cdb")
            self._make_db(
                db_path,
                [
                    (22702055, FIELD_SPELL_TYPE, "Umi"),
                    (19613556, PLAIN_SPELL_TYPE, "Heavy Storm"),
                    (46986414, MONSTER_TYPE, "Dark Magician"),
                ],
            )
            _, _, _, field_ids = main.scan_databases([db_path])

        self.assertEqual(field_ids, {22702055})

    def test_databases_without_type_column_still_scan(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "cards.cdb")
            conn = sqlite3.connect(db_path)
            try:
                conn.execute("CREATE TABLE datas (id INTEGER PRIMARY KEY)")
                conn.execute("CREATE TABLE texts (id INTEGER PRIMARY KEY, name TEXT)")
                conn.execute("INSERT INTO datas (id) VALUES (12345678)")
                conn.execute("INSERT INTO texts (id, name) VALUES (12345678, 'Old Card')")
                conn.commit()
            finally:
                conn.close()
            id_to_name, _, _, field_ids = main.scan_databases([db_path])

        self.assertEqual(id_to_name, {12345678: "Old Card"})
        self.assertEqual(field_ids, set())


class _FakeSession:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0

    def get(self, url, timeout=None):
        self.calls += 1
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        status, body = item
        return _FakeResponse(status, body)


class _FakeResponse:
    def __init__(self, status, body):
        self.status = status
        self._body = body
        self.headers = {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def read(self):
        return self._body


class DownloadFieldArtTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cfg = types.SimpleNamespace(
            pics_path=os.path.join(self.tmp.name, "pics"),
            sources={"field": "http://field-source"},
            timeout=1,
            max_retries=1,
        )
        os.makedirs(main.field_art_dir(self.cfg), exist_ok=True)
        patcher = mock.patch.object(main.asyncio, "sleep", new=mock.AsyncMock())
        patcher.start()
        self.addCleanup(patcher.stop)

    def _download(self, session):
        stats = main.DownloadStats()
        asyncio.run(main.download_field_art(session, 22702055, "Umi", self.cfg, stats))
        return stats

    def test_success_saves_jpg_and_counts(self):
        stats = self._download(_FakeSession([(200, JPEG_BODY)]))

        self.assertEqual(stats.field_ok, 1)
        self.assertTrue(os.path.exists(os.path.join(main.field_art_dir(self.cfg), "22702055.jpg")))

    def test_404_is_definitive_field_failure(self):
        stats = self._download(_FakeSession([(404, b"")]))

        self.assertEqual(stats.field_failed, 1)
        self.assertNotIn(22702055, stats.field_transient_ids)

    def test_timeout_is_transient_field_failure(self):
        stats = self._download(_FakeSession([TimeoutError()]))

        self.assertEqual(stats.field_failed, 1)
        self.assertIn(22702055, stats.field_transient_ids)


class FieldArtHelpersTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cfg = types.SimpleNamespace(pics_path=os.path.join(self.tmp.name, "pics"))
        self.field_dir = main.field_art_dir(self.cfg)
        os.makedirs(self.field_dir, exist_ok=True)

    def test_has_field_art_accepts_png_or_jpg(self):
        self.assertFalse(main.has_field_art(self.cfg, 22702055))
        with open(os.path.join(self.field_dir, "22702055.png"), "wb") as f:
            f.write(PNG_BODY)
        self.assertTrue(main.has_field_art(self.cfg, 22702055))

    def test_find_broken_field_images_flags_corrupt_files_only(self):
        with open(os.path.join(self.field_dir, "111.jpg"), "wb") as f:
            f.write(JPEG_BODY)
        with open(os.path.join(self.field_dir, "222.png"), "wb") as f:
            f.write(b"truncated")
        with open(os.path.join(self.field_dir, "999.jpg"), "wb") as f:
            f.write(b"orphan not in dbs")

        broken = main.find_broken_field_images(self.field_dir, {111, 222})

        self.assertEqual(broken, [222])


class FieldSummaryRowTests(unittest.TestCase):
    def test_summary_includes_field_art_rows(self):
        stats = main.DownloadStats()
        stats.field_ok = 5
        stats.record_field_failure(22702055, "Umi")
        cfg = types.SimpleNamespace(dry_run=False)

        rows = main._build_summary_rows(stats, cfg, 5.0)

        self.assertIn(("Field art", "5", "green"), rows)
        self.assertIn(("Field art unavailable", "1", "yellow"), rows)


if __name__ == "__main__":
    unittest.main()
