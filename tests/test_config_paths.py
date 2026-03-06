import json
import os
import tempfile
import unittest
from unittest import mock

import config as config_module
from config import Config


class ConfigPathTests(unittest.TestCase):
    def setUp(self):
        self.workspace_root = os.getcwd()
        self.temp_dir = tempfile.TemporaryDirectory(dir=self.workspace_root)
        self.addCleanup(self.temp_dir.cleanup)
        self.test_root = self.temp_dir.name
        self.original_cwd = os.getcwd()
        os.chdir(self.test_root)
        self.addCleanup(os.chdir, self.original_cwd)

    def test_default_config_uses_appdata_when_no_local_config_exists(self):
        appdata_root = os.path.join(self.test_root, "AppData", "Roaming")

        with mock.patch.object(config_module.sys, "platform", "win32"), mock.patch.dict(
            os.environ,
            {"APPDATA": appdata_root, "LOCALAPPDATA": appdata_root},
            clear=False,
        ):
            cfg = Config([])

        expected = os.path.join(appdata_root, config_module.APP_NAME, config_module.CONFIG_FILENAME)
        self.assertEqual(cfg.config_path, expected)

    def test_existing_local_config_is_still_used_for_legacy_installs(self):
        local_config = os.path.join(self.test_root, config_module.CONFIG_FILENAME)
        with open(local_config, "w", encoding="utf-8") as file_obj:
            json.dump({"concurrency": 7}, file_obj)

        appdata_root = os.path.join(self.test_root, "AppData", "Roaming")
        with mock.patch.object(config_module.sys, "platform", "win32"), mock.patch.dict(
            os.environ,
            {"APPDATA": appdata_root, "LOCALAPPDATA": appdata_root},
            clear=False,
        ):
            cfg = Config([])

        self.assertEqual(cfg.config_path, local_config)
        self.assertEqual(cfg.concurrency, 7)

    def test_saving_edopro_path_creates_default_config_directory(self):
        appdata_root = os.path.join(self.test_root, "AppData", "Roaming")
        edopro_path = os.path.join(self.test_root, "ProjectIgnis")
        os.makedirs(edopro_path, exist_ok=True)

        with mock.patch.object(config_module.sys, "platform", "win32"), mock.patch.dict(
            os.environ,
            {"APPDATA": appdata_root, "LOCALAPPDATA": appdata_root},
            clear=False,
        ):
            cfg = Config([])
            saved = cfg.set_edopro_path(edopro_path, save=True)

        self.assertTrue(saved)
        self.assertTrue(os.path.exists(cfg.config_path))
        with open(cfg.config_path, "r", encoding="utf-8") as file_obj:
            saved_config = json.load(file_obj)
        self.assertEqual(saved_config["edopro_path"], os.path.abspath(edopro_path))


if __name__ == "__main__":
    unittest.main()
