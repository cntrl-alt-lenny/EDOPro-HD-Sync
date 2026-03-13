import os
import tempfile
import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest import mock

import main


class SyncReportingTests(unittest.TestCase):
    def setUp(self):
        self.workspace_root = os.getcwd()
        self.temp_dir = tempfile.TemporaryDirectory(dir=self.workspace_root)
        self.addCleanup(self.temp_dir.cleanup)
        self.edopro_path = self.temp_dir.name
        self.pics_path = os.path.join(self.edopro_path, "pics")
        os.makedirs(self.pics_path, exist_ok=True)

    def make_cfg(self, **overrides):
        values = {
            "dry_run": False,
            "quiet": False,
            "edopro_path": self.edopro_path,
            "pics_path": self.pics_path,
            "config_path": os.path.join(self.edopro_path, "config.json"),
            "save_report": False,
        }
        values.update(overrides)
        return SimpleNamespace(**values)

    def test_find_official_match_logs_pre_errata_lookup_miss_when_not_quiet(self):
        with mock.patch.object(main.console, "print") as print_mock:
            match = main.find_official_match(
                "Firewall Dragon (Pre-Errata)",
                {},
                [" (Pre-Errata)"],
                quiet=False,
            )

        self.assertEqual(match, ([], True))
        print_mock.assert_called_once()
        self.assertIn(
            'Pre-Errata lookup miss: "Firewall Dragon" (from "Firewall Dragon (Pre-Errata)")',
            print_mock.call_args.args[0],
        )

    def test_find_official_match_skips_pre_errata_lookup_miss_when_quiet(self):
        with mock.patch.object(main.console, "print") as print_mock:
            match = main.find_official_match(
                "Firewall Dragon (Pre-Errata)",
                {},
                [" (Pre-Errata)"],
                quiet=True,
            )

        self.assertEqual(match, ([], True))
        print_mock.assert_not_called()

    def test_print_summary_does_not_write_failure_file_without_opt_in(self):
        stats = main.DownloadStats()
        stats.record_failure(12345678, "Missing Artwork Card")
        cfg = self.make_cfg()
        fixed_now = datetime(2026, 3, 12, 14, 5, 6)

        with mock.patch.object(main, "RICH_AVAILABLE", True), mock.patch.object(
            main.console, "print"
        ), mock.patch.object(main.console, "rule"), mock.patch.object(main, "datetime") as datetime_mock:
            datetime_mock.now.return_value = fixed_now
            main.print_summary(stats, 1, cfg, 5.0)

        self.assertFalse(
            os.path.exists(os.path.join(self.edopro_path, "Sync-Failed-20260312-140506.txt"))
        )

    def test_print_summary_writes_combined_report(self):
        stats = main.DownloadStats()
        stats.record_success(12345678, "ok_hd")
        stats.record_success(100000001, "ok_fallback")
        stats.record_failure(100000002, "Fan Card")
        cfg = self.make_cfg(save_report=True, quiet=True)
        fixed_now = datetime(2026, 3, 12, 14, 5, 6)

        with mock.patch.object(main, "RICH_AVAILABLE", True), mock.patch.object(
            main.console, "print"
        ), mock.patch.object(main.console, "rule"), mock.patch.object(main, "datetime") as datetime_mock:
            datetime_mock.now.return_value = fixed_now
            main.print_summary(stats, 3, cfg, 12.0)

        report_path = os.path.join(self.edopro_path, "sync-report-20260312-140506.txt")
        self.assertTrue(os.path.exists(report_path))

        with open(report_path, "r", encoding="utf-8") as file_obj:
            report_contents = file_obj.read()

        self.assertIn("- Downloaded: 2", report_contents)
        self.assertIn("- Unavailable (unofficial): 1", report_contents)
        self.assertIn("- Unavailable (other): 0", report_contents)
        self.assertIn("- Success rate: 100.0%", report_contents)
        self.assertIn("100000002\tFan Card", report_contents)


if __name__ == "__main__":
    unittest.main()
