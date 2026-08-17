"""The double-click experience: no stray console, no over-tall window."""

import contextlib
import types
import unittest
from unittest import mock

import gui
import main


class ElidePathTests(unittest.TestCase):
    def test_a_short_path_is_left_alone(self):
        path = r"C:\Users\leo\Games\ProjectIgnis"
        self.assertEqual(gui._elide_path(path), path)

    def test_a_long_path_keeps_the_folders_that_identify_it(self):
        path = r"C:\Users\leonardo\Documents\Games\Yu-Gi-Oh\ProjectIgnis"
        elided = gui._elide_path(path)
        self.assertTrue(elided.endswith("ProjectIgnis"), elided)
        self.assertTrue(elided.startswith("…\\"), elided)
        self.assertLessEqual(len(elided), 36)

    def test_posix_paths_keep_their_own_separator(self):
        path = "/home/leonardo/very/deeply/nested/games/folder/ProjectIgnis"
        elided = gui._elide_path(path)
        self.assertTrue(elided.startswith("…/"), elided)
        self.assertNotIn("\\", elided)
        self.assertTrue(elided.endswith("ProjectIgnis"), elided)

    def test_a_single_long_name_still_shortens(self):
        elided = gui._elide_path("x" * 90)
        self.assertLessEqual(len(elided), 92)
        self.assertTrue(elided.startswith("…"), elided)


class PauseBeforeExitTests(unittest.TestCase):
    """Pausing without a console to pause in is an invisible hang."""

    def _frozen_windows(self, stdin):
        return (
            mock.patch.object(main.sys, "platform", "win32"),
            mock.patch.object(main.sys, "frozen", True, create=True),
            mock.patch.object(main.sys, "stdin", stdin),
        )

    @staticmethod
    def _stdin(isatty: bool):
        return types.SimpleNamespace(isatty=lambda: isatty)

    def test_the_window_never_leaves_a_hidden_prompt_waiting(self):
        cfg = types.SimpleNamespace(no_pause=False)
        with contextlib.ExitStack() as stack:
            for patch in self._frozen_windows(self._stdin(True)):
                stack.enter_context(patch)
            self.assertFalse(main.should_pause_before_exit(cfg, gui_ran=True))

    def test_terminal_runs_pause_so_the_output_can_be_read(self):
        cfg = types.SimpleNamespace(no_pause=False)
        with contextlib.ExitStack() as stack:
            for patch in self._frozen_windows(self._stdin(True)):
                stack.enter_context(patch)
            self.assertTrue(main.should_pause_before_exit(cfg, gui_ran=False))

    def test_a_double_click_with_no_console_never_pauses(self):
        cfg = types.SimpleNamespace(no_pause=False)
        with contextlib.ExitStack() as stack:
            for patch in self._frozen_windows(None):
                stack.enter_context(patch)
            self.assertFalse(main.should_pause_before_exit(cfg, gui_ran=False))

    def test_a_piped_run_never_pauses(self):
        cfg = types.SimpleNamespace(no_pause=False)
        with contextlib.ExitStack() as stack:
            for patch in self._frozen_windows(self._stdin(False)):
                stack.enter_context(patch)
            self.assertFalse(main.should_pause_before_exit(cfg, gui_ran=False))

    def test_a_closed_stdin_never_pauses(self):
        cfg = types.SimpleNamespace(no_pause=False)
        broken = types.SimpleNamespace(isatty=mock.Mock(side_effect=ValueError("closed")))
        with contextlib.ExitStack() as stack:
            for patch in self._frozen_windows(broken):
                stack.enter_context(patch)
            self.assertFalse(main.should_pause_before_exit(cfg, gui_ran=False))

    def test_no_pause_flag_still_wins(self):
        cfg = types.SimpleNamespace(no_pause=True)
        with contextlib.ExitStack() as stack:
            for patch in self._frozen_windows(self._stdin(True)):
                stack.enter_context(patch)
            self.assertFalse(main.should_pause_before_exit(cfg, gui_ran=False))


if __name__ == "__main__":
    unittest.main()
