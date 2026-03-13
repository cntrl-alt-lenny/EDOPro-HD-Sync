import asyncio
import os
import sqlite3
import tempfile
import unittest
from unittest import mock

import main
from config import Config, DEFAULTS
from tricky_cards import KNOWN_MULTI_ART_CARDS, SAFE_MULTI_ART_FALLBACK_CASE


class OfficialMatchingTests(unittest.TestCase):
    def setUp(self):
        self.suffixes = DEFAULTS["suffixes_to_strip"]

    def test_scan_databases_keeps_all_official_ids_for_duplicate_names(self):
        workspace_root = os.getcwd()
        with tempfile.TemporaryDirectory(dir=workspace_root) as temp_dir:
            db_path = os.path.join(temp_dir, "cards.cdb")
            with sqlite3.connect(db_path) as conn:
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

            id_to_name, name_to_official, rush_ids = main.scan_databases([db_path])

        self.assertEqual(id_to_name[89631133], "Blue-Eyes White Dragon")
        self.assertEqual(
            name_to_official["Blue-Eyes White Dragon"],
            [89631133, 89631139],
        )
        self.assertNotIn("Unofficial Blue-Eyes", name_to_official)

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

    def test_download_card_tries_own_id_first_then_alternatives(self):
        stats = main.DownloadStats()
        attempted_urls: list[str] = []

        async def fake_try_download(session, url, filepath, timeout, max_retries):
            attempted_urls.append(url)
            # Own ID fails, but a name-matched alternative succeeds.
            return url.endswith("/89631139.jpg")

        # Card 89631133 is a single-art scenario (no ygoprodeck_art_ids filter).
        with mock.patch.object(
            main,
            "_try_download",
            new=mock.AsyncMock(side_effect=fake_try_download),
        ):
            asyncio.run(
                main.download_card(
                    object(),
                    89631133,
                    "Blue-Eyes White Dragon",
                    [89631133, 89631134, 89631139],
                    None,
                    False,
                    True,   # is_suffix_match — treat as suffix card so step 3 runs
                    set(),  # ygoprodeck_art_ids
                    self.cfg,
                    stats,
                )
            )

        # Card's own ID is tried first, then alternatives (skipping self).
        self.assertEqual(
            attempted_urls,
            [
                f"{self.cfg.sources['official']}/89631133.jpg",
                f"{self.cfg.sources['official']}/89631134.jpg",
                f"{self.cfg.sources['official']}/89631139.jpg",
            ],
        )
        self.assertEqual(stats.ok_hd, 1)
        self.assertEqual(stats.failed, 0)

    def test_download_card_prefers_backup_for_multi_art_without_api_match(self):
        """Multi-art card whose ID is NOT on ygoprodeck should try backup first."""
        stats = main.DownloadStats()
        attempted_urls: list[str] = []

        async def fake_try_download(session, url, filepath, timeout, max_retries):
            attempted_urls.append(url)
            return True  # Everything succeeds

        ygoprodeck_art_ids = {89631139, 89631140}  # 89631136 is NOT here

        with mock.patch.object(
            main,
            "_try_download",
            new=mock.AsyncMock(side_effect=fake_try_download),
        ):
            asyncio.run(
                main.download_card(
                    object(),
                    89631136,
                    "Blue-Eyes White Dragon",
                    [89631136, 89631139, 89631140],
                    None,
                    False,
                    False,  # is_suffix_match — direct name lookup
                    ygoprodeck_art_ids,
                    self.cfg,
                    stats,
                )
            )

        # Should skip own ID (not on ygoprodeck), skip name-matched
        # alternatives (multi-art), and go to ProjectIgnis backup first.
        self.assertEqual(len(attempted_urls), 1)
        self.assertIn("ProjectIgnis", attempted_urls[0])
        self.assertEqual(stats.ok_fallback, 1)

    def test_download_card_skips_ygoprodeck_when_multi_art_lookup_is_empty(self):
        """An empty alternate-art lookup should still avoid the wrong default art."""
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
                    89631136,
                    "Blue-Eyes White Dragon",
                    [89631136, 89631139, 89631140],
                    None,
                    False,
                    False,
                    set(),
                    self.cfg,
                    stats,
                )
            )

        self.assertEqual(attempted_urls, [f"{self.cfg.sources['backup']}/89631136.jpg"])
        self.assertEqual(stats.ok_fallback, 1)

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
                    False,  # is_suffix_match
                    set(),  # ygoprodeck_art_ids
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
        self.assertEqual(stats.ok_fallback, 0)
        self.assertEqual(stats.failed, 0)


class TrickyCardFixtureTests(unittest.TestCase):
    def test_real_world_multi_art_fixtures_are_available(self):
        name_to_official = {
            fixture["name"]: fixture["official_ids"] for fixture in KNOWN_MULTI_ART_CARDS
        }

        self.assertEqual(
            name_to_official["Blue-Eyes White Dragon"][0],
            89631136,
        )
        self.assertEqual(
            name_to_official["Dark Magician"][-1],
            46986423,
        )
        self.assertEqual(
            name_to_official["Red-Eyes Black Dragon"][-1],
            74677431,
        )

    def test_should_try_direct_hd_only_for_confirmed_multi_art_ids(self):
        confirmed_art_ids = set(SAFE_MULTI_ART_FALLBACK_CASE["confirmed_art_ids"])

        self.assertFalse(
            main.should_try_direct_hd(
                SAFE_MULTI_ART_FALLBACK_CASE["card_id"],
                SAFE_MULTI_ART_FALLBACK_CASE["official_matches"],
                False,
                set(),
            )
        )
        self.assertTrue(
            main.should_try_direct_hd(
                min(confirmed_art_ids),
                SAFE_MULTI_ART_FALLBACK_CASE["official_matches"],
                False,
                confirmed_art_ids,
            )
        )


if __name__ == "__main__":
    unittest.main()
