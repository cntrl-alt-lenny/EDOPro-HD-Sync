"""End-to-end run() flow tests for the failure-cache and deck-filter invariants."""

import asyncio
import json
import os
import tempfile
import time
import unittest
from unittest import mock

import main
from config import Config


class FakeResponse:
    status = 200

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakeSession:
    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def get(self, *args, **kwargs):
        return FakeResponse()


class RunFlowTests(unittest.TestCase):
    """Drive main.run() with mocked scanning + downloads against a temp folder."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = self.temp_dir.name
        self.pics = os.path.join(self.root, "pics")
        os.makedirs(self.pics, exist_ok=True)
        self.config_path = os.path.join(self.root, "config.json")
        self.cache_path = os.path.join(self.root, "failed_cards.json")
        self.db = os.path.join(self.root, "cards.cdb")
        with open(self.db, "w", encoding="utf-8") as f:
            f.write("placeholder")

    def _cfg(self, *extra):
        cfg = Config(["--config", self.config_path, "--quiet", "--no-field-art", *extra])
        cfg.set_edopro_path(self.root)
        return cfg

    def _seed_cache(self, ids):
        with open(self.cache_path, "w", encoding="utf-8") as f:
            json.dump({str(cid): time.time() for cid in ids}, f)

    def _run(self, cfg, cards, outcomes):
        """outcomes: card_id -> FetchResult for every URL of that card."""

        async def fake_try_download(session, url, filepath, timeout, retries, is_valid=None):
            cid = int(os.path.splitext(os.path.basename(filepath))[0])
            result = outcomes.get(cid, main.FetchResult.MISSING)
            if result is main.FetchResult.OK:
                with open(filepath, "wb") as f:
                    f.write(b"\xff\xd8\xff" + b"\x00" * 600)
            return result

        download_mock = mock.AsyncMock(side_effect=fake_try_download)
        with (
            mock.patch.object(main, "get_db_files", return_value=[self.db]),
            mock.patch.object(main, "scan_databases", return_value=(dict(cards), {}, set(), set())),
            mock.patch.object(main, "load_manual_map", return_value={}),
            mock.patch.object(main.aiohttp, "ClientSession", FakeSession),
            mock.patch.object(main, "_check_image_server", new=mock.AsyncMock(return_value=None)),
            mock.patch.object(main, "check_for_update", new=mock.AsyncMock(return_value=None)),
            mock.patch.object(main, "_try_download", new=download_mock),
        ):
            asyncio.run(main.run(cfg))
        return download_mock

    def _cache_keys(self):
        if not os.path.exists(self.cache_path):
            return set()
        with open(self.cache_path, encoding="utf-8") as f:
            return set(json.load(f).keys())

    def test_run_caches_only_definitive_misses_and_evicts_recovered_cards(self):
        # C is cached as missing but its art now exists on disk -> must be evicted.
        self._seed_cache([333])
        with open(os.path.join(self.pics, "333.jpg"), "wb") as f:
            f.write(b"\xff\xd8\xff" + b"\x00" * 600)

        cards = {111: "Definitive Miss", 222: "Transient Trouble", 333: "Recovered"}
        outcomes = {111: main.FetchResult.MISSING, 222: main.FetchResult.ERROR}
        self._run(self._cfg(), cards, outcomes)

        keys = self._cache_keys()
        self.assertIn("111", keys)  # 404 everywhere -> remembered
        self.assertNotIn("222", keys)  # network trouble -> retried next run
        self.assertNotIn("333", keys)  # art on disk -> evicted

    def test_deck_filtered_recheck_preserves_out_of_scope_cache(self):
        # 999 is cached but NOT in the deck; a --recheck-missing deck run
        # must leave its cache entry alone.
        self._seed_cache([999, 111])
        deck = os.path.join(self.root, "mine.ydk")
        with open(deck, "w", encoding="utf-8") as f:
            f.write("#main\n111\n")

        cards = {111: "Deck Card", 999: "Out Of Scope"}
        outcomes = {111: main.FetchResult.MISSING}
        downloads = self._run(self._cfg("--deck", deck, "--recheck-missing"), cards, outcomes)

        keys = self._cache_keys()
        self.assertIn("999", keys)  # untouched: never re-attempted
        self.assertIn("111", keys)  # re-attempted, still missing -> recached
        # Prove the recheck actually re-attempted 111 and never touched 999.
        attempted = [call.args[2] for call in downloads.await_args_list]
        self.assertTrue(any("111" in path for path in attempted))
        self.assertFalse(any("999" in path for path in attempted))

    def test_explicit_empty_deck_filter_errors_out(self):
        """A typo'd --deck must not silently escalate into a full 13k-card sync."""
        deck = os.path.join(self.root, "empty.ydk")
        with open(deck, "w", encoding="utf-8") as f:
            f.write("#main\n")

        cards = {111: "Only Card"}
        with self.assertRaises(SystemExit) as ctx:
            self._run(self._cfg("--deck", deck), cards, {111: main.FetchResult.OK})

        self.assertEqual(ctx.exception.code, 1)
        self.assertFalse(os.path.exists(os.path.join(self.pics, "111.jpg")))

    def test_my_decks_with_empty_decks_falls_back_to_full_sync(self):
        """The window/quick-start path keeps the friendly fallback."""
        deck_dir = os.path.join(self.root, "deck")
        os.makedirs(deck_dir, exist_ok=True)
        with open(os.path.join(deck_dir, "empty.ydk"), "w", encoding="utf-8") as f:
            f.write("#main\n")

        cards = {111: "Only Card"}
        self._run(self._cfg("--my-decks"), cards, {111: main.FetchResult.OK})

        self.assertTrue(os.path.exists(os.path.join(self.pics, "111.jpg")))

    def test_prune_is_skipped_when_deck_filter_is_active(self):
        deck = os.path.join(self.root, "mine.ydk")
        with open(deck, "w", encoding="utf-8") as f:
            f.write("#main\n111\n")
        # An orphan image that a mistaken prune-under-filter would delete.
        orphan = os.path.join(self.pics, "999999.jpg")
        with open(orphan, "wb") as f:
            f.write(b"\xff\xd8\xff" + b"\x00" * 600)

        cards = {111: "Deck Card"}
        outcomes = {111: main.FetchResult.OK}
        self._run(self._cfg("--deck", deck, "--prune"), cards, outcomes)

        self.assertTrue(os.path.exists(orphan))


if __name__ == "__main__":
    unittest.main()
