import asyncio
import os
import sqlite3
import tempfile
import unittest
from unittest import mock

import main
from config import Config, DEFAULTS


class OfficialMatchingTests(unittest.TestCase):
    def setUp(self):
        self.suffixes = DEFAULTS["suffixes_to_strip"]

    def test_scan_databases_keeps_all_official_ids_for_duplicate_names(self):
        workspace_root = os.getcwd()
        with tempfile.TemporaryDirectory(dir=workspace_root) as temp_dir:
            db_path = os.path.join(temp_dir, "cards.cdb")
            conn = sqlite3.connect(db_path)
            try:
                conn.execute("CREATE TABLE datas (id INTEGER PRIMARY KEY)")
                conn.execute("CREATE TABLE texts (id INTEGER PRIMARY KEY, name TEXT)")
                conn.executemany(
                    "INSERT INTO datas (id) VALUES (?)",
                    [(89631133,), (89631139,), (123456789,)],
                )
                conn.executemany(
                    "INSERT INTO texts (id, name) VALUES (?, ?)",
                    [
                        (89631133, "Blue-Eyes White Dragon"),
                        (89631139, "Blue-Eyes White Dragon"),
                        (123456789, "Unofficial Blue-Eyes"),
                    ],
                )
                conn.commit()
            finally:
                conn.close()

            id_to_name, name_to_official, _ = main.scan_databases([db_path])

        self.assertEqual(id_to_name[89631133], "Blue-Eyes White Dragon")
        self.assertEqual(
            name_to_official["Blue-Eyes White Dragon"],
            [89631133, 89631139],
        )
        self.assertNotIn("Unofficial Blue-Eyes", name_to_official)

    def test_scan_databases_sorts_official_ids_for_stable_fallback_order(self):
        workspace_root = os.getcwd()
        with tempfile.TemporaryDirectory(dir=workspace_root) as temp_dir:
            db_path = os.path.join(temp_dir, "cards.cdb")
            conn = sqlite3.connect(db_path)
            try:
                conn.execute("CREATE TABLE datas (id INTEGER PRIMARY KEY)")
                conn.execute("CREATE TABLE texts (id INTEGER PRIMARY KEY, name TEXT)")
                conn.executemany(
                    "INSERT INTO datas (id) VALUES (?)",
                    [(46986423,), (46986414,), (46986422,)],
                )
                conn.executemany(
                    "INSERT INTO texts (id, name) VALUES (?, ?)",
                    [
                        (46986423, "Dark Magician"),
                        (46986414, "Dark Magician"),
                        (46986422, "Dark Magician"),
                    ],
                )
                conn.commit()
            finally:
                conn.close()

            _, name_to_official, _ = main.scan_databases([db_path])

        self.assertEqual(
            name_to_official["Dark Magician"],
            [46986414, 46986422, 46986423],
        )

    def test_find_official_match_prefers_suffix_stripped_name(self):
        name_to_official = {
            "Dark Magician": [46986414],
            "Dark Magician (Pre-Errata)": [46986424],
        }

        official_ids, is_pre_errata_miss, is_suffix_match = main.find_official_match(
            "Dark Magician (Pre-Errata)",
            name_to_official,
            self.suffixes,
        )

        self.assertEqual(official_ids, [46986414])
        self.assertFalse(is_pre_errata_miss)
        self.assertTrue(is_suffix_match)

    def test_find_official_match_marks_pre_errata_miss_when_base_name_is_missing(self):
        name_to_official = {
            "Summoned Skull (Pre-Errata)": [70781062],
        }

        official_ids, is_pre_errata_miss, is_suffix_match = main.find_official_match(
            "Summoned Skull (Pre-Errata)",
            name_to_official,
            self.suffixes,
        )

        self.assertEqual(official_ids, [70781062])
        self.assertTrue(is_pre_errata_miss)
        self.assertFalse(is_suffix_match)


class DownloadCardTests(unittest.TestCase):
    def setUp(self):
        workspace_root = os.getcwd()
        self.temp_dir = tempfile.TemporaryDirectory(dir=workspace_root)
        self.addCleanup(self.temp_dir.cleanup)
        self.cfg = Config(
            [
                "--config",
                os.path.join(self.temp_dir.name, "config.json"),
                "--quiet",
            ]
        )
        self.cfg.set_edopro_path(self.temp_dir.name)
        os.makedirs(self.cfg.pics_path, exist_ok=True)

    def test_download_card_tries_direct_id_on_ygoprodeck(self):
        stats = main.DownloadStats()
        attempted_urls: list[str] = []

        async def fake_try_download(session, url, filepath, timeout, max_retries):
            attempted_urls.append(url)
            return True

        with mock.patch.object(
            main,
            "_try_download",
            new=mock.AsyncMock(side_effect=fake_try_download),
        ):
            asyncio.run(
                main.download_card(
                    object(),
                    46986414,
                    "Dark Magician",
                    [46986414],
                    None,
                    False,
                    False,
                    self.cfg,
                    stats,
                )
            )

        self.assertEqual(attempted_urls, [f"{self.cfg.sources['official']}/46986414.jpg"])
        self.assertEqual(stats.ok_hd, 1)

    def test_download_card_falls_back_to_project_ignis(self):
        stats = main.DownloadStats()
        attempted_urls: list[str] = []

        async def fake_try_download(session, url, filepath, timeout, max_retries):
            attempted_urls.append(url)
            return url.startswith(self.cfg.sources["backup"])

        with mock.patch.object(
            main,
            "_try_download",
            new=mock.AsyncMock(side_effect=fake_try_download),
        ):
            asyncio.run(
                main.download_card(
                    object(),
                    46986414,
                    "Dark Magician",
                    [46986414],
                    None,
                    False,
                    False,
                    self.cfg,
                    stats,
                )
            )

        self.assertEqual(
            attempted_urls,
            [
                f"{self.cfg.sources['official']}/46986414.jpg",
                f"{self.cfg.sources['backup']}/46986414.jpg",
            ],
        )
        self.assertEqual(stats.ok_fallback, 1)

    def test_download_card_suffix_match_tries_base_card_ids(self):
        stats = main.DownloadStats()
        attempted_urls: list[str] = []

        async def fake_try_download(session, url, filepath, timeout, max_retries):
            attempted_urls.append(url)
            return url.endswith("/46986414.jpg")

        with mock.patch.object(
            main,
            "_try_download",
            new=mock.AsyncMock(side_effect=fake_try_download),
        ):
            asyncio.run(
                main.download_card(
                    object(),
                    46986424,
                    "Dark Magician (Pre-Errata)",
                    [46986414],
                    None,
                    False,
                    True,
                    self.cfg,
                    stats,
                )
            )

        self.assertEqual(
            attempted_urls,
            [
                f"{self.cfg.sources['official']}/46986424.jpg",
                f"{self.cfg.sources['official']}/46986414.jpg",
            ],
        )
        self.assertEqual(stats.ok_hd, 1)

    def test_download_card_tries_pre_errata_offset_before_backup(self):
        stats = main.DownloadStats()
        attempted_urls: list[str] = []

        async def fake_try_download(session, url, filepath, timeout, max_retries):
            attempted_urls.append(url)
            return url.endswith("/46986414.jpg")

        with mock.patch.object(
            main,
            "_try_download",
            new=mock.AsyncMock(side_effect=fake_try_download),
        ):
            asyncio.run(
                main.download_card(
                    object(),
                    46986424,
                    "Dark Magician (Pre-Errata)",
                    [46986424],
                    None,
                    True,
                    False,
                    self.cfg,
                    stats,
                )
            )

        self.assertEqual(
            attempted_urls,
            [
                f"{self.cfg.sources['official']}/46986424.jpg",
                f"{self.cfg.sources['official']}/46986414.jpg",
            ],
        )
        self.assertEqual(stats.ok_hd, 1)

    def test_download_card_uses_manual_map_first(self):
        stats = main.DownloadStats()
        attempted_urls: list[str] = []

        async def fake_try_download(session, url, filepath, timeout, max_retries):
            attempted_urls.append(url)
            return True

        with mock.patch.object(
            main,
            "_try_download",
            new=mock.AsyncMock(side_effect=fake_try_download),
        ):
            asyncio.run(
                main.download_card(
                    object(),
                    46986424,
                    "Dark Magician (Pre-Errata)",
                    [46986414],
                    "12345678",
                    False,
                    True,
                    self.cfg,
                    stats,
                )
            )

        self.assertEqual(attempted_urls, [f"{self.cfg.sources['official']}/12345678.jpg"])
        self.assertEqual(stats.ok_mapped, 1)

    def test_download_card_skips_ygoprodeck_for_unofficial_ids(self):
        stats = main.DownloadStats()
        attempted_urls: list[str] = []

        async def fake_try_download(session, url, filepath, timeout, max_retries):
            attempted_urls.append(url)
            return True

        with mock.patch.object(
            main,
            "_try_download",
            new=mock.AsyncMock(side_effect=fake_try_download),
        ):
            asyncio.run(
                main.download_card(
                    object(),
                    200000001,
                    "Custom Fan Card",
                    [],
                    None,
                    False,
                    False,
                    self.cfg,
                    stats,
                )
            )

        self.assertEqual(attempted_urls, [f"{self.cfg.sources['backup']}/200000001.jpg"])
        self.assertEqual(stats.ok_fallback, 1)


if __name__ == "__main__":
    unittest.main()
