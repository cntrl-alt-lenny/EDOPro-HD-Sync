"""Tests for the tick-box options window plumbing (not the Tk widgets themselves)."""

import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

import gui
import main


def _cfg(**overrides):
    values = {
        "gui": None,
        "quiet": False,
        "dry_run": False,
        "stats": False,
        "health_check": False,
        "repair": False,
        "force": False,
        "deck_paths": [],
        "decks_folder": None,
        "my_decks": False,
        "prune": False,
        "recheck_missing": False,
        "textures": None,
        "textures_pack": None,
        "field_art": True,
        "save_report": False,
        "interactive_prompts": True,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class ShouldShowGuiTests(unittest.TestCase):
    def test_hidden_when_running_from_source(self):
        self.assertFalse(main._should_show_gui(_cfg()))

    def test_shown_for_plain_packaged_runs(self):
        with mock.patch.object(main.sys, "frozen", True, create=True):
            self.assertTrue(main._should_show_gui(_cfg()))

    def test_hidden_when_power_flags_are_passed(self):
        with mock.patch.object(main.sys, "frozen", True, create=True):
            self.assertFalse(main._should_show_gui(_cfg(quiet=True)))
            self.assertFalse(main._should_show_gui(_cfg(force=True)))
            self.assertFalse(main._should_show_gui(_cfg(my_decks=True)))
            self.assertFalse(main._should_show_gui(_cfg(textures=True)))

    def test_gui_flag_forces_it_even_from_source(self):
        self.assertTrue(main._should_show_gui(_cfg(gui=True)))

    def test_no_gui_flag_wins_even_when_packaged(self):
        with mock.patch.object(main.sys, "frozen", True, create=True):
            self.assertFalse(main._should_show_gui(_cfg(gui=False)))


class ApplyGuiChoicesTests(unittest.TestCase):
    def test_choices_land_on_config_and_mute_prompts(self):
        cfg = _cfg()
        main._apply_gui_choices(
            cfg,
            {
                "field_art": False,
                "my_decks": True,
                "textures": True,
                "repair": True,
                "force": False,
                "save_report": True,
                "stats": False,
            },
        )

        self.assertFalse(cfg.field_art)
        self.assertTrue(cfg.my_decks)
        self.assertTrue(cfg.textures)
        self.assertTrue(cfg.repair)
        self.assertFalse(cfg.force)
        self.assertTrue(cfg.save_report)
        self.assertFalse(cfg.interactive_prompts)

    def test_show_coverage_button_maps_to_stats(self):
        cfg = _cfg()
        main._apply_gui_choices(cfg, {"stats": True})
        self.assertTrue(cfg.stats)


class RunAppFallbackTests(unittest.TestCase):
    def test_run_app_raises_gui_unavailable_without_tkinter(self):
        with mock.patch.object(gui, "tk", None), self.assertRaises(gui.GuiUnavailable):
            gui.run_app(_cfg(), "1.0.0", None, None)

    def test_gui_progress_adapter_posts_rich_compatible_events(self):
        import queue as queue_mod

        events: queue_mod.Queue = queue_mod.Queue()
        progress = gui._GuiProgress(events)

        task = progress.add_task("Syncing card artwork", total=42)
        progress.update(task, description="Syncing Dark Magician")
        progress.update(task)  # description=None must be a no-op, not a crash
        progress.advance(task)

        self.assertEqual(events.get_nowait(), ("task", task, "Syncing card artwork", 42))
        self.assertEqual(events.get_nowait(), ("desc", task, "Syncing Dark Magician"))
        self.assertEqual(events.get_nowait(), ("adv", task, 1))
        self.assertTrue(events.empty())


class DeckHelpersTests(unittest.TestCase):
    def test_count_deck_files_walks_subfolders(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "AI"))
            for path in ("mydeck.ydk", os.path.join("AI", "bot.ydk"), "notes.txt"):
                with open(os.path.join(tmp, path), "w", encoding="utf-8") as f:
                    f.write("#main\n")
            self.assertEqual(main._count_deck_files(tmp), 2)

    def test_count_deck_files_missing_folder(self):
        self.assertEqual(main._count_deck_files("/nonexistent/deck/folder"), 0)

    def test_collect_deck_filter_walks_deck_subfolders(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "sub"))
            with open(os.path.join(tmp, "sub", "deep.ydk"), "w", encoding="utf-8") as f:
                f.write("#main\n46986414\n")
            cfg = SimpleNamespace(deck_paths=[], decks_folder=tmp)
            self.assertEqual(main.collect_deck_filter_ids(cfg), {46986414})


if __name__ == "__main__":
    unittest.main()
