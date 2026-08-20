"""GOAT / Pre-Errata entries: their own wording versus the sharpest picture."""

import json
import os
import tempfile
import threading
import unittest
from types import SimpleNamespace

import config as config_module
import main
from config import DEFAULTS, Config

SOURCES = DEFAULTS["sources"]
OFFICIAL = SOURCES["official"]
BACKUP = SOURCES["backup"]
SUFFIXES = DEFAULTS["suffixes_to_strip"]


def reasons(**kwargs):
    defaults = dict(
        card_id=511000818,
        official_matches=[8131171],
        manual_match=None,
        is_pre_errata_miss=False,
        is_suffix_match=True,
        sources=SOURCES,
    )
    defaults.update(kwargs)
    return [r for r, _ in main.build_download_candidates(**defaults)]


def urls(**kwargs):
    defaults = dict(
        card_id=511000818,
        official_matches=[8131171],
        manual_match=None,
        is_pre_errata_miss=False,
        is_suffix_match=True,
        sources=SOURCES,
    )
    defaults.update(kwargs)
    return [u for _, u in main.build_download_candidates(**defaults)]


class DefaultOrderTests(unittest.TestCase):
    """The order that shipped: sharpest image wins."""

    def test_own_art_is_tried_before_borrowing_the_base_card(self):
        self.assertEqual(reasons(), ["direct-id", "name-match", "backup"])

    def test_a_manual_override_still_outranks_everything(self):
        self.assertEqual(
            reasons(manual_match="57728570"),
            ["manual-map", "direct-id", "name-match", "backup"],
        )

    def test_the_small_community_server_is_always_last(self):
        self.assertEqual(reasons()[-1], "backup")
        self.assertEqual(urls()[-1], f"{BACKUP}/511000818.jpg")

    def test_pre_errata_offset_is_tried_when_the_base_card_is_missing(self):
        got = reasons(
            card_id=16226796, official_matches=[], is_suffix_match=False, is_pre_errata_miss=True
        )
        self.assertEqual(got, ["direct-id", "pre-errata-offset", "backup"])
        self.assertIn(
            f"{OFFICIAL}/16226786.jpg",
            urls(
                card_id=16226796,
                official_matches=[],
                is_suffix_match=False,
                is_pre_errata_miss=True,
            ),
        )

    def test_a_card_is_never_queued_for_its_own_id_twice(self):
        # It is its own "base card" here; direct-id already covers that URL.
        got = urls(card_id=8131171, official_matches=[8131171])
        self.assertEqual(got.count(f"{OFFICIAL}/8131171.jpg"), 1, got)
        self.assertNotIn("name-match", reasons(card_id=8131171, official_matches=[8131171]))


class OriginalTextTests(unittest.TestCase):
    """With the tick-box on, a card's own artwork comes first."""

    def test_the_cards_own_art_outranks_the_base_card(self):
        self.assertEqual(
            reasons(original_text=True),
            ["direct-id", "backup", "name-match"],
        )

    def test_own_art_outranks_a_manual_override_too(self):
        # The override points at an official reprint, which carries the
        # errata'd wording - exactly what this setting exists to avoid.
        got = reasons(manual_match="57728570", original_text=True)
        self.assertLess(got.index("backup"), got.index("manual-map"))

    def test_substitutes_still_follow_so_nothing_ends_up_worse(self):
        got = reasons(original_text=True)
        self.assertIn("name-match", got)
        self.assertEqual(sorted(got), sorted(reasons()))

    def test_ordinary_cards_are_completely_unaffected(self):
        plain = dict(card_id=46986414, official_matches=[46986414], is_suffix_match=False)
        self.assertEqual(reasons(**plain), reasons(original_text=True, **plain))

    def test_a_card_with_no_backup_source_configured_still_works(self):
        sources = {"official": OFFICIAL}
        self.assertEqual(reasons(sources=sources, original_text=True), ["direct-id", "name-match"])


class EraEntryTests(unittest.TestCase):
    """Which cards the setting applies to."""

    def test_recognises_goat_and_pre_errata_entries(self):
        for name in (
            "Sinister Serpent (Pre-Errata)",
            "Thunder Dragon (GOAT)",
            "Dark Magician GOAT",
            "Some Card Pre-Errata",
        ):
            self.assertTrue(main.is_era_entry(name, SUFFIXES), name)

    def test_leaves_ordinary_cards_alone(self):
        for name in ("Sinister Serpent", "Thunder Dragon", "Goat Token", "Scapegoat"):
            self.assertFalse(main.is_era_entry(name, SUFFIXES), name)


class RefreshOnFlipTests(unittest.TestCase):
    """Flipping the setting has to re-fetch the cards it changes."""

    @staticmethod
    def _cfg(**overrides):
        values = {
            "original_text": False,
            "saved_original_text": False,
            "dry_run": False,
            "force": False,
            "cancel_event": None,
        }
        values.update(overrides)
        return SimpleNamespace(**values)

    def test_no_refresh_when_the_setting_has_not_changed(self):
        self.assertFalse(main._should_refresh_era_art(self._cfg()))
        self.assertFalse(
            main._should_refresh_era_art(self._cfg(original_text=True, saved_original_text=True))
        )

    def test_refresh_when_switched_on(self):
        self.assertTrue(main._should_refresh_era_art(self._cfg(original_text=True)))

    def test_refresh_when_switched_back_off(self):
        self.assertTrue(main._should_refresh_era_art(self._cfg(saved_original_text=True)))

    def test_a_dry_run_never_deletes_anything(self):
        self.assertFalse(main._should_refresh_era_art(self._cfg(original_text=True, dry_run=True)))

    def test_force_already_redownloads_everything(self):
        self.assertFalse(main._should_refresh_era_art(self._cfg(original_text=True, force=True)))

    def test_a_cancelled_run_is_not_recorded_as_applied(self):
        event = threading.Event()
        cfg = self._cfg(original_text=True, cancel_event=event)
        self.assertFalse(main._run_was_cancelled(cfg))
        event.set()
        self.assertTrue(main._run_was_cancelled(cfg))


class SettingPersistenceTests(unittest.TestCase):
    def test_the_setting_survives_a_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "config.json")
            cfg = Config(["--config", path])
            self.assertFalse(cfg.original_text)
            self.assertFalse(cfg.saved_original_text)

            config_module.save_setting(path, "original_text", True)
            reopened = Config(["--config", path])
            self.assertTrue(reopened.original_text)
            self.assertTrue(reopened.saved_original_text)

    def test_saving_one_setting_leaves_the_others_alone(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "config.json")
            config_module.save_edopro_path(path, r"C:\Games\ProjectIgnis")
            config_module.save_setting(path, "original_text", True)
            with open(path, encoding="utf-8") as f:
                saved = json.load(f)
            self.assertEqual(saved["edopro_path"], r"C:\Games\ProjectIgnis")
            self.assertTrue(saved["original_text"])

    def test_the_flag_overrides_the_saved_value(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "config.json")
            config_module.save_setting(path, "original_text", True)
            cfg = Config(["--config", path, "--no-original-text"])
            self.assertFalse(cfg.original_text)
            # ...and the run then knows a refresh back to sharp art is due.
            self.assertTrue(cfg.saved_original_text)


if __name__ == "__main__":
    unittest.main()
