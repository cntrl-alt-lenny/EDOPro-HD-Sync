import os
import tempfile
import unittest
from unittest import mock

import main
from config import Config


class HealthCheckTests(unittest.TestCase):
    def setUp(self):
        self.workspace_root = os.getcwd()
        self.temp_dir = tempfile.TemporaryDirectory(dir=self.workspace_root)
        self.addCleanup(self.temp_dir.cleanup)
        self.cfg = Config(
            [
                "--config",
                os.path.join(self.temp_dir.name, "config.json"),
                "--health-check",
                "--quiet",
            ]
        )

    def test_run_health_check_passes(self):
        with mock.patch.object(main.console, "print") as print_mock, mock.patch.object(
            main.console, "rule"
        ):
            passed = main.run_health_check(self.cfg)

        self.assertTrue(passed)
        printed = "\n".join(str(call.args[0]) for call in print_mock.call_args_list if call.args)
        self.assertIn("Dark Magician (Pre-Errata)", printed)
        self.assertIn("Blue-Eyes White Dragon GOAT", printed)
        self.assertIn("All checks passed", printed)
