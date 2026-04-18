import unittest
from unittest import mock

import main


class CompletedProcessStub:
    def __init__(self, returncode: int, stdout: str):
        self.returncode = returncode
        self.stdout = stdout


class WindowsFolderPickerTests(unittest.TestCase):
    def test_powershell_picker_returns_selected_folder(self):
        with mock.patch.object(main.sys, "platform", "win32"), mock.patch.object(
            main.subprocess,
            "run",
            return_value=CompletedProcessStub(0, 'C:\\Users\\leona\\Games\\ProjectIgnis\n'),
        ) as run_mock:
            path, used_dialog = main.browse_for_edopro_path_with_powershell("C:\\")

        self.assertTrue(used_dialog)
        self.assertEqual(path, "C:\\Users\\leona\\Games\\ProjectIgnis")
        command = run_mock.call_args.args[0]
        self.assertEqual(command[0], "powershell.exe")
        self.assertIn("-STA", command)

    def test_powershell_picker_reports_cancelled_dialog(self):
        with mock.patch.object(main.sys, "platform", "win32"), mock.patch.object(
            main.subprocess,
            "run",
            return_value=CompletedProcessStub(0, ""),
        ):
            path, used_dialog = main.browse_for_edopro_path_with_powershell("C:\\")

        self.assertTrue(used_dialog)
        self.assertIsNone(path)


if __name__ == "__main__":
    unittest.main()
