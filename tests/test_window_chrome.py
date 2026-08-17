"""The double-click experience: no stray console, no over-tall window."""

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
    def test_the_window_never_leaves_a_hidden_prompt_waiting(self):
        cfg = types.SimpleNamespace(no_pause=False)
        with (
            mock.patch.object(main.sys, "platform", "win32"),
            mock.patch.object(main.sys, "frozen", True, create=True),
        ):
            self.assertFalse(main.should_pause_before_exit(cfg, gui_ran=True))

    def test_console_runs_still_pause_so_the_output_can_be_read(self):
        cfg = types.SimpleNamespace(no_pause=False)
        with (
            mock.patch.object(main.sys, "platform", "win32"),
            mock.patch.object(main.sys, "frozen", True, create=True),
        ):
            self.assertTrue(main.should_pause_before_exit(cfg, gui_ran=False))

    def test_no_pause_flag_still_wins(self):
        cfg = types.SimpleNamespace(no_pause=True)
        with (
            mock.patch.object(main.sys, "platform", "win32"),
            mock.patch.object(main.sys, "frozen", True, create=True),
        ):
            self.assertFalse(main.should_pause_before_exit(cfg, gui_ran=False))


class HideConsoleTests(unittest.TestCase):
    """Hiding the wrong console would take away the user's own terminal."""

    def _run_with_owner(self, owner_exe: str, our_exe: str = r"C:\apps\EDOPro-HD-Sync.exe"):
        hidden: list = []
        kernel32 = mock.MagicMock()
        user32 = mock.MagicMock()
        kernel32.GetConsoleWindow.return_value = 1234
        kernel32.OpenProcess.return_value = 99

        def query_name(_handle, _flags, buffer, _size):
            buffer.value = owner_exe
            return 1

        kernel32.QueryFullProcessImageNameW.side_effect = query_name
        user32.ShowWindow.side_effect = lambda hwnd, cmd: hidden.append((hwnd, cmd))

        windll = mock.MagicMock(kernel32=kernel32, user32=user32)
        with (
            mock.patch.object(gui.sys, "platform", "win32"),
            mock.patch.object(gui.sys, "executable", our_exe),
            mock.patch("ctypes.windll", windll, create=True),
        ):
            gui._hide_own_console_window()
        return hidden

    def test_hides_a_console_this_app_created(self):
        hidden = self._run_with_owner(r"C:\apps\EDOPro-HD-Sync.exe")
        self.assertEqual(hidden, [(1234, 0)])

    def test_ignores_case_differences_in_the_path(self):
        hidden = self._run_with_owner(r"c:\APPS\edopro-hd-sync.EXE")
        self.assertEqual(hidden, [(1234, 0)])

    def test_leaves_command_prompt_alone(self):
        self.assertEqual(self._run_with_owner(r"C:\Windows\System32\cmd.exe"), [])

    def test_leaves_windows_terminal_alone(self):
        self.assertEqual(self._run_with_owner(r"C:\Program Files\WindowsTerminal.exe"), [])

    def test_does_nothing_off_windows(self):
        with mock.patch.object(gui.sys, "platform", "darwin"):
            self.assertIsNone(gui._hide_own_console_window())


if __name__ == "__main__":
    unittest.main()
