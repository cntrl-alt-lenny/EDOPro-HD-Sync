"""Tests for .ydk deck parsing, deck filtering, and orphan pruning."""

import os
import tempfile
import unittest
from types import SimpleNamespace

import main


class ParseYdkTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)

    def _write(self, name: str, body: str) -> str:
        path = os.path.join(self.temp_dir.name, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(body)
        return path

    def test_parses_main_extra_and_side(self):
        path = self._write(
            "deck.ydk",
            "#created by ...\n#main\n46986414\n46986414\n89631139\n"
            "#extra\n88477150\n!side\n18144508\n",
        )

        self.assertEqual(
            main.parse_ydk(path),
            {46986414, 89631139, 88477150, 18144508},
        )

    def test_skips_comments_blank_lines_and_non_integers(self):
        path = self._write(
            "deck.ydk",
            "\n# a comment\n!side\n46986414\n  \nnot-a-number\n-5\n0\n89631139\n",
        )

        self.assertEqual(main.parse_ydk(path), {46986414, 89631139})

    def test_missing_file_returns_empty_set(self):
        ghost = os.path.join(self.temp_dir.name, "nope.ydk")
        self.assertEqual(main.parse_ydk(ghost), set())


class CollectDeckFilterTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)

    def _write_deck(self, name: str, ids: list[int]) -> str:
        path = os.path.join(self.temp_dir.name, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write("#main\n")
            for cid in ids:
                f.write(f"{cid}\n")
        return path

    def test_none_when_no_deck_args(self):
        cfg = SimpleNamespace(deck_paths=[], decks_folder=None)
        self.assertIsNone(main.collect_deck_filter_ids(cfg))

    def test_unions_multiple_decks(self):
        deck_a = self._write_deck("a.ydk", [46986414])
        deck_b = self._write_deck("b.ydk", [89631139])
        cfg = SimpleNamespace(deck_paths=[deck_a, deck_b], decks_folder=None)

        self.assertEqual(main.collect_deck_filter_ids(cfg), {46986414, 89631139})

    def test_folder_of_decks(self):
        folder = os.path.join(self.temp_dir.name, "decks")
        os.makedirs(folder, exist_ok=True)
        for name, cid in [("a.ydk", 46986414), ("b.ydk", 89631139), ("readme.txt", 0)]:
            with open(os.path.join(folder, name), "w", encoding="utf-8") as f:
                f.write("#main\n")
                f.write(f"{cid}\n")
        cfg = SimpleNamespace(deck_paths=[], decks_folder=folder)

        self.assertEqual(main.collect_deck_filter_ids(cfg), {46986414, 89631139})


class PruneOrphansTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.pics = os.path.join(self.temp_dir.name, "pics")
        os.makedirs(self.pics, exist_ok=True)

    def _touch(self, name: str) -> None:
        open(os.path.join(self.pics, name), "wb").close()

    def test_removes_ids_not_in_known_set(self):
        self._touch("46986414.jpg")
        self._touch("89631139.jpg")
        self._touch("999999.jpg")  # orphan

        pruned = main.prune_orphan_images(self.pics, {46986414, 89631139})

        self.assertEqual(pruned, 1)
        self.assertTrue(os.path.exists(os.path.join(self.pics, "46986414.jpg")))
        self.assertTrue(os.path.exists(os.path.join(self.pics, "89631139.jpg")))
        self.assertFalse(os.path.exists(os.path.join(self.pics, "999999.jpg")))

    def test_ignores_non_jpg_and_non_numeric_files(self):
        self._touch("46986414.jpg")
        self._touch("readme.txt")
        self._touch("notes.jpg.bak")
        self._touch("weird-name.jpg")

        pruned = main.prune_orphan_images(self.pics, {46986414})

        self.assertEqual(pruned, 0)
        # All four files should still be there.
        self.assertEqual(len(os.listdir(self.pics)), 4)

    def test_missing_pics_dir_returns_zero(self):
        self.assertEqual(
            main.prune_orphan_images(os.path.join(self.temp_dir.name, "nope"), {1}),
            0,
        )


class UpdateCheckTests(unittest.TestCase):
    def test_dev_version_never_triggers_nag(self):
        # Session fake would be unreachable if the current version were 'dev',
        # because check_for_update short-circuits before touching the network.
        import asyncio

        fake_session = object()
        result = asyncio.run(main.check_for_update(fake_session, "dev"))
        self.assertIsNone(result)

    def test_parse_version_handles_v_prefix_and_trailers(self):
        self.assertEqual(main._parse_version("v4.5.1"), (4, 5, 1))
        self.assertEqual(main._parse_version("4.6.0-rc1"), (4, 6, 0))
        self.assertEqual(main._parse_version("bogus"), (0,))

    def test_parse_version_comparison(self):
        self.assertGreater(main._parse_version("v4.6.0"), main._parse_version("4.5.1"))
        self.assertLess(main._parse_version("v4.5.0"), main._parse_version("4.5.1"))


if __name__ == "__main__":
    unittest.main()
