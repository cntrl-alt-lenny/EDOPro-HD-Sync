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

    def test_download_card_tries_catalog_id_first_then_name_matched_alternatives(self):
        stats = main.DownloadStats()
        attempted_urls: list[str] = []
        ygoprodeck_lookup = {
            89631133: f"{self.cfg.sources['official']}/89631133.jpg",
            89631134: f"{self.cfg.sources['official']}/89631134.jpg",
            89631139: f"{self.cfg.sources['official']}/89631139.jpg",
        }

        async def fake_try_download(session, url, filepath, timeout, max_retries):
            attempted_urls.append(url)
            return url.endswith("/89631139.jpg")

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
                    True,
                    ygoprodeck_lookup,
                    self.cfg,
                    stats,
                    {},
                )
            )

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

    def test_download_card_prefers_backup_for_multi_art_default_id(self):
        stats = main.DownloadStats()
        attempted_urls: list[str] = []
        ygoprodeck_lookup = {
            89631139: f"{self.cfg.sources['official']}/89631139.jpg",
            89631140: f"{self.cfg.sources['official']}/89631140.jpg",
        }

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
                    ygoprodeck_lookup,
                    self.cfg,
                    stats,
                    {},
                )
            )

        self.assertEqual(attempted_urls, [f"{self.cfg.sources['backup']}/89631136.jpg"])
        self.assertEqual(stats.ok_fallback, 1)

    def test_download_card_uses_catalog_entry_for_confirmed_alt_art(self):
        stats = main.DownloadStats()
        attempted_urls: list[str] = []
        ygoprodeck_lookup = {
            89631139: f"{self.cfg.sources['official']}/89631139.jpg",
        }

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
                    89631139,
                    "Blue-Eyes White Dragon Alt Art",
                    [89631136, 89631139, 89631140],
                    None,
                    False,
                    False,
                    ygoprodeck_lookup,
                    self.cfg,
                    stats,
                    {},
                )
            )

        self.assertEqual(attempted_urls, [f"{self.cfg.sources['official']}/89631139.jpg"])
        self.assertEqual(stats.ok_hd, 1)

    def test_download_card_tries_pre_errata_offset_before_backup(self):
        stats = main.DownloadStats()
        attempted_urls: list[str] = []
        ygoprodeck_lookup = {
            46986414: f"{self.cfg.sources['official']}/46986414.jpg",
        }

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
                    ygoprodeck_lookup,
                    self.cfg,
                    stats,
                    {},
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

    def test_download_card_uses_manual_map_before_catalog_lookup(self):
        stats = main.DownloadStats()
        attempted_urls: list[str] = []
        ygoprodeck_lookup = {
            46986414: f"{self.cfg.sources['official']}/46986414.jpg",
            12345678: f"{self.cfg.sources['official']}/12345678.jpg",
        }

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
                    ygoprodeck_lookup,
                    self.cfg,
                    stats,
                    {},
                )
            )

        self.assertEqual(attempted_urls, [f"{self.cfg.sources['official']}/12345678.jpg"])
        self.assertEqual(stats.ok_mapped, 1)

    def test_download_card_speculative_keeps_distinct_multi_art_when_catalog_misses_it(self):
        stats = main.DownloadStats()
        default_art_cache: dict[int, bytes | None] = {}
        default_path = os.path.join(self.cfg.pics_path, "89631136.jpg")
        distinct_art = b"B" * 1024

        with open(default_path, "wb") as f:
            f.write(b"A" * 1024)

        async def fake_try_download_bytes(session, url, timeout, max_retries):
            return distinct_art

        with mock.patch.object(
            main,
            "_try_download_bytes",
            new=mock.AsyncMock(side_effect=fake_try_download_bytes),
        ):
            asyncio.run(
                main.download_card(
                    object(),
                    89631139,
                    "Blue-Eyes White Dragon",
                    [89631136, 89631139, 89631140],
                    None,
                    False,
                    False,
                    {},
                    self.cfg,
                    stats,
                    default_art_cache,
                )
            )

        saved_path = os.path.join(self.cfg.pics_path, "89631139.jpg")
        self.assertTrue(os.path.exists(saved_path))
        with open(saved_path, "rb") as f:
            self.assertEqual(f.read(), distinct_art)
        self.assertEqual(stats.ok_hd, 1)

    def test_download_card_speculative_discards_duplicate_multi_art_and_uses_backup(self):
        stats = main.DownloadStats()
        default_art_cache: dict[int, bytes | None] = {}
        attempted_urls: list[str] = []
        default_art = b"A" * 1024
        default_path = os.path.join(self.cfg.pics_path, "89631136.jpg")

        with open(default_path, "wb") as f:
            f.write(default_art)

        async def fake_try_download_bytes(session, url, timeout, max_retries):
            return default_art

        async def fake_try_download(session, url, filepath, timeout, max_retries):
            attempted_urls.append(url)
            return True

        with mock.patch.object(
            main,
            "_try_download_bytes",
            new=mock.AsyncMock(side_effect=fake_try_download_bytes),
        ), mock.patch.object(
            main,
            "_try_download",
            new=mock.AsyncMock(side_effect=fake_try_download),
        ):
            asyncio.run(
                main.download_card(
                    object(),
                    89631139,
                    "Blue-Eyes White Dragon",
                    [89631136, 89631139, 89631140],
                    None,
                    False,
                    False,
                    {},
                    self.cfg,
                    stats,
                    default_art_cache,
                )
            )

        self.assertEqual(attempted_urls, [f"{self.cfg.sources['backup']}/89631139.jpg"])
        self.assertEqual(stats.ok_fallback, 1)


class TrickyCardFixtureTests(unittest.TestCase):
    def test_real_world_multi_art_fixtures_are_available(self):
        name_to_official = {
            fixture["name"]: fixture["official_ids"] for fixture in KNOWN_MULTI_ART_CARDS
        }

        self.assertEqual(name_to_official["Blue-Eyes White Dragon"][0], 89631136)
        self.assertEqual(name_to_official["Dark Magician"][-1], 46986423)
        self.assertEqual(name_to_official["Red-Eyes Black Dragon"][-1], 74677431)

    def test_catalog_candidate_builder_only_keeps_confirmed_multi_art_ids(self):
        lookup = {
            image_id: f"{DEFAULTS['sources']['official']}/{image_id}.jpg"
            for image_id in SAFE_MULTI_ART_FALLBACK_CASE["confirmed_art_ids"]
        }
        confirmed_id = min(SAFE_MULTI_ART_FALLBACK_CASE["confirmed_art_ids"])

        self.assertEqual(
            main.build_ygoprodeck_download_candidates(
                SAFE_MULTI_ART_FALLBACK_CASE["card_id"],
                SAFE_MULTI_ART_FALLBACK_CASE["official_matches"],
                None,
                False,
                False,
                lookup,
                DEFAULTS["sources"]["official"],
            ),
            [],
        )
        self.assertEqual(
            main.build_ygoprodeck_download_candidates(
                confirmed_id,
                SAFE_MULTI_ART_FALLBACK_CASE["official_matches"],
                None,
                False,
                False,
                lookup,
                DEFAULTS["sources"]["official"],
            ),
            [("catalog-id", f"{DEFAULTS['sources']['official']}/{confirmed_id}.jpg")],
        )


if __name__ == "__main__":
    unittest.main()
