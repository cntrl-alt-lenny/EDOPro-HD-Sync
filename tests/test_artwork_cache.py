import asyncio
import os
import tempfile
import unittest
from unittest import mock

import main


class ArtworkCacheTests(unittest.TestCase):
    def setUp(self):
        self.workspace_root = os.getcwd()
        self.temp_dir = tempfile.TemporaryDirectory(dir=self.workspace_root)
        self.addCleanup(self.temp_dir.cleanup)
        self.cache_path = os.path.join(self.temp_dir.name, "alternate-art-cache.json")

    def test_load_artwork_cache_returns_empty_for_missing_file(self):
        self.assertEqual(main.load_artwork_cache(self.cache_path), {})

    def test_resolve_ygoprodeck_artwork_ids_uses_cache_and_fetches_missing_names(self):
        main.save_artwork_cache(
            self.cache_path,
            {
                "Blue-Eyes White Dragon": {
                    "artwork_ids": [89631139, 89631140],
                    "official_count": 3,
                    "updated_at": 9_000,
                },
            },
        )

        async def fake_fetch(session, names, ssl_ctx):
            self.assertEqual(names, ["Red-Eyes Black Dragon"])
            return ({"Red-Eyes Black Dragon": {74677422, 74677423}}, set())

        with mock.patch.object(main, "time", return_value=9_100), mock.patch.object(
            main,
            "fetch_ygoprodeck_artwork_ids_by_name",
            new=mock.AsyncMock(side_effect=fake_fetch),
        ):
            result = asyncio.run(
                main.resolve_ygoprodeck_artwork_ids(
                    object(),
                    {
                        "Blue-Eyes White Dragon": [89631136, 89631139, 89631140],
                        "Red-Eyes Black Dragon": [74677422, 74677423],
                    },
                    object(),
                    self.cache_path,
                )
            )

        self.assertEqual(result.cached_names, 1)
        self.assertEqual(result.fetched_names, 1)
        self.assertEqual(result.failed_names, 0)
        self.assertEqual(
            result.art_ids,
            {89631139, 89631140, 74677422, 74677423},
        )
        saved = main.load_artwork_cache(self.cache_path)
        self.assertIn("Red-Eyes Black Dragon", saved)

    def test_resolve_ygoprodeck_artwork_ids_reuses_stale_cache_when_refresh_fails(self):
        main.save_artwork_cache(
            self.cache_path,
            {
                "Blue-Eyes White Dragon": {
                    "artwork_ids": [89631139],
                    "official_count": 3,
                    "updated_at": 0,
                },
            },
        )

        with mock.patch.object(
            main,
            "fetch_ygoprodeck_artwork_ids_by_name",
            new=mock.AsyncMock(return_value=({}, {"Blue-Eyes White Dragon"})),
        ), mock.patch.object(main, "time", return_value=main.ARTWORK_CACHE_MAX_AGE_SECONDS + 10):
            result = asyncio.run(
                main.resolve_ygoprodeck_artwork_ids(
                    object(),
                    {"Blue-Eyes White Dragon": [89631136, 89631139, 89631140]},
                    object(),
                    self.cache_path,
                )
            )

        self.assertEqual(result.reused_cache_names, 1)
        self.assertEqual(result.failed_names, 0)
        self.assertEqual(result.art_ids, {89631139})
