"""Tests for the always-on startup update notification."""

import asyncio
import unittest
from unittest import mock

import main


class NotifyIfUpdateAvailableTests(unittest.TestCase):
    def test_prints_nag_when_newer_version_exists(self):
        with (
            mock.patch.object(main, "check_for_update", new=mock.AsyncMock(return_value="v99.0.0")),
            mock.patch.object(main.console, "print") as print_mock,
        ):
            asyncio.run(main.notify_if_update_available())

        print_mock.assert_called_once()
        self.assertIn("v99.0.0", print_mock.call_args.args[0])

    def test_silent_when_already_up_to_date(self):
        with (
            mock.patch.object(main, "check_for_update", new=mock.AsyncMock(return_value=None)),
            mock.patch.object(main.console, "print") as print_mock,
        ):
            asyncio.run(main.notify_if_update_available())

        print_mock.assert_not_called()

    def test_silent_when_the_check_itself_fails(self):
        with (
            mock.patch.object(
                main, "check_for_update", new=mock.AsyncMock(side_effect=RuntimeError("boom"))
            ),
            mock.patch.object(main.console, "print") as print_mock,
        ):
            asyncio.run(main.notify_if_update_available())

        print_mock.assert_not_called()

    def test_update_message_mentions_the_launcher_auto_update(self):
        message = main._update_message("v9.9.9")
        self.assertIn("v9.9.9", message)
        self.assertIn("launcher", message)


if __name__ == "__main__":
    unittest.main()
