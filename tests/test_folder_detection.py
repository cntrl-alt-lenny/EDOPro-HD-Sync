import os
import tempfile
import unittest
from unittest import mock

import config as config_module
import main
from config import Config


def _make_edopro_folder(root: str, name: str, *, databases: bool = True) -> str:
    """Create a folder that looks like an EDOPro install."""
    path = os.path.join(root, name)
    os.makedirs(path, exist_ok=True)
    open(os.path.join(path, "EDOPro.exe"), "wb").close()
    if databases:
        os.makedirs(os.path.join(path, "expansions"), exist_ok=True)
        open(os.path.join(path, "expansions", "sets.cdb"), "wb").close()
    return path


class FolderRuleTests(unittest.TestCase):
    """folder_has_card_databases must agree with the scanner it stands in for."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = self.temp_dir.name

    def assert_agrees(self, path: str) -> None:
        self.assertEqual(
            config_module.folder_has_card_databases(path),
            bool(main.get_db_files(path)),
            f"detection and get_db_files() disagree about {path}",
        )

    def test_agrees_on_root_cards_database(self):
        path = os.path.join(self.root, "root-db")
        os.makedirs(path)
        open(os.path.join(path, "cards.cdb"), "wb").close()
        self.assert_agrees(path)

    def test_agrees_on_expansions(self):
        self.assert_agrees(_make_edopro_folder(self.root, "ProjectIgnis"))

    def test_agrees_on_repository_deltas(self):
        path = os.path.join(self.root, "repo-only", "repositories", "nested")
        os.makedirs(path)
        open(os.path.join(path, "cards.delta.cdb"), "wb").close()
        self.assert_agrees(os.path.join(self.root, "repo-only"))

    def test_agrees_on_empty_folder(self):
        path = os.path.join(self.root, "empty")
        os.makedirs(path)
        self.assert_agrees(path)

    def test_agrees_when_expansions_holds_no_databases(self):
        path = os.path.join(self.root, "no-cdb")
        os.makedirs(os.path.join(path, "expansions"))
        open(os.path.join(path, "expansions", "readme.txt"), "wb").close()
        self.assert_agrees(path)

    def test_folder_with_only_the_game_exe_still_looks_like_edopro(self):
        path = _make_edopro_folder(self.root, "Fresh", databases=False)
        self.assertTrue(config_module.looks_like_edopro_folder(path))
        self.assertFalse(config_module.folder_has_card_databases(path))


class FindFolderTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = self.temp_dir.name

    def patch_parents(self, *parents: str):
        return mock.patch.object(config_module, "_search_parents", lambda: list(parents))

    def test_finds_a_folder_by_its_usual_name(self):
        expected = _make_edopro_folder(self.root, "ProjectIgnis")
        with self.patch_parents(self.root):
            self.assertEqual(config_module.find_edopro_folder(), os.path.abspath(expected))

    def test_finds_a_renamed_folder_by_looking_inside(self):
        expected = _make_edopro_folder(self.root, "my card game")
        with self.patch_parents(self.root):
            self.assertEqual(config_module.find_edopro_folder(), os.path.abspath(expected))

    def test_prefers_a_folder_with_databases_over_a_bare_install(self):
        _make_edopro_folder(self.root, "EDOPro", databases=False)
        ready = _make_edopro_folder(self.root, "ProjectIgnis")
        with self.patch_parents(self.root):
            self.assertEqual(config_module.find_edopro_folder(), os.path.abspath(ready))

    def test_returns_none_when_there_is_nothing_to_find(self):
        os.makedirs(os.path.join(self.root, "holiday photos"))
        with self.patch_parents(self.root):
            self.assertIsNone(config_module.find_edopro_folder())

    def test_a_caller_guess_wins_over_the_search(self):
        guess = _make_edopro_folder(self.root, "guessed")
        _make_edopro_folder(self.root, "ProjectIgnis")
        with self.patch_parents(self.root):
            self.assertEqual(config_module.find_edopro_folder([guess]), os.path.abspath(guess))

    def test_missing_search_parents_are_skipped(self):
        expected = _make_edopro_folder(self.root, "ProjectIgnis")
        missing = os.path.join(self.root, "does-not-exist")
        with self.patch_parents(missing, self.root):
            self.assertEqual(config_module.find_edopro_folder(), os.path.abspath(expected))


class DetectOnStartupTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = self.temp_dir.name
        self.config_path = os.path.join(self.root, "config.json")

    def test_detection_fills_in_the_folder_and_flags_it_for_confirming(self):
        expected = _make_edopro_folder(self.root, "ProjectIgnis")
        cfg = Config(["--config", self.config_path])

        with mock.patch.object(config_module, "_search_parents", lambda: [self.root]):
            main.detect_edopro_folder(cfg)

        self.assertEqual(cfg.edopro_path, os.path.abspath(expected))
        self.assertTrue(cfg.folder_detected)

    def test_an_explicit_path_is_never_second_guessed(self):
        _make_edopro_folder(self.root, "ProjectIgnis")
        chosen = os.path.join(self.root, "somewhere-else")
        cfg = Config(["--config", self.config_path, "--edopro-path", chosen])

        with mock.patch.object(config_module, "_search_parents", lambda: [self.root]):
            main.detect_edopro_folder(cfg)

        self.assertEqual(cfg.edopro_path, os.path.abspath(chosen))
        self.assertFalse(cfg.folder_detected)

    def test_nothing_found_leaves_the_folder_unconfirmed(self):
        cfg = Config(["--config", self.config_path])

        with mock.patch.object(config_module, "_search_parents", lambda: [self.root]):
            main.detect_edopro_folder(cfg)

        self.assertFalse(cfg.folder_detected)


class ConfirmFolderTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = self.temp_dir.name
        self.edopro = _make_edopro_folder(self.root, "ProjectIgnis")
        self.cfg = Config(["--config", os.path.join(self.root, "config.json")])
        self.cfg.set_edopro_path(self.edopro)

    def test_accepting_the_found_folder_remembers_it(self):
        with mock.patch.object(main, "_prompt_yes_no", return_value=True):
            self.assertTrue(main.confirm_edopro_folder(self.cfg))

        self.assertEqual(self.cfg.edopro_path, os.path.abspath(self.edopro))
        self.assertTrue(os.path.exists(self.cfg.config_path))

    def test_declining_hands_over_to_the_folder_picker(self):
        other = _make_edopro_folder(self.root, "Other")
        with (
            mock.patch.object(main, "_prompt_yes_no", return_value=False),
            mock.patch.object(main, "prompt_for_edopro_path", return_value=["db"]) as picker,
        ):
            self.assertTrue(main.confirm_edopro_folder(self.cfg))
        picker.assert_called_once()
        self.assertTrue(os.path.isdir(other))

    def test_backing_out_of_the_picker_stops_the_run(self):
        with (
            mock.patch.object(main, "_prompt_yes_no", return_value=False),
            mock.patch.object(main, "prompt_for_edopro_path", return_value=None),
        ):
            self.assertFalse(main.confirm_edopro_folder(self.cfg))


if __name__ == "__main__":
    unittest.main()
