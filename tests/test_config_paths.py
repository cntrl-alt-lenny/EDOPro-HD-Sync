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

    def test_default_config_uses_script_directory_when_running_from_source(self):
        script_dir = os.path.join(self.test_root, "source-build")
        os.makedirs(script_dir, exist_ok=True)
        fake_config_py = os.path.join(script_dir, "config.py")

        with mock.patch.object(config_module, "__file__", fake_config_py):
            cfg = Config([])

        expected = os.path.join(script_dir, config_module.CONFIG_FILENAME)
        self.assertEqual(cfg.config_path, expected)

    def test_default_config_uses_executable_directory_when_frozen(self):
        frozen_dir = os.path.join(self.test_root, "frozen-build")
        os.makedirs(frozen_dir, exist_ok=True)
        fake_executable = os.path.join(frozen_dir, "EDOPro-HD-Sync.exe")

        with mock.patch.object(config_module.sys, "executable", fake_executable), mock.patch.object(
            config_module.sys, "frozen", True, create=True
        ):
            cfg = Config([])

        expected = os.path.join(frozen_dir, config_module.CONFIG_FILENAME)
        self.assertEqual(cfg.config_path, expected)

    def test_default_config_loads_existing_file_from_script_directory(self):
        script_dir = os.path.join(self.test_root, "source-build")
        os.makedirs(script_dir, exist_ok=True)
        local_config = os.path.join(script_dir, config_module.CONFIG_FILENAME)
        with open(local_config, "w", encoding="utf-8") as file_obj:
            json.dump({"concurrency": 7}, file_obj)

        with mock.patch.object(config_module, "__file__", os.path.join(script_dir, "config.py")):
            cfg = Config([])

        self.assertEqual(cfg.config_path, local_config)
        self.assertEqual(cfg.concurrency, 7)

    def test_saving_edopro_path_creates_config_beside_executable(self):
        frozen_dir = os.path.join(self.test_root, "frozen-build")
        os.makedirs(frozen_dir, exist_ok=True)
        fake_executable = os.path.join(frozen_dir, "EDOPro-HD-Sync.exe")
        edopro_path = os.path.join(self.test_root, "ProjectIgnis")
        os.makedirs(edopro_path, exist_ok=True)

        with mock.patch.object(config_module.sys, "executable", fake_executable), mock.patch.object(
            config_module.sys, "frozen", True, create=True
        ):
            cfg = Config([])
            saved = cfg.set_edopro_path(edopro_path, save=True)

        self.assertTrue(saved)
        self.assertEqual(cfg.config_path, os.path.join(frozen_dir, config_module.CONFIG_FILENAME))
        self.assertTrue(os.path.exists(cfg.config_path))
        with open(cfg.config_path, "r", encoding="utf-8") as file_obj:
            saved_config = json.load(file_obj)
        self.assertEqual(saved_config["edopro_path"], os.path.abspath(edopro_path))

    def test_save_report_can_be_loaded_from_config_file(self):
        config_path = os.path.join(self.test_root, "config.json")
        with open(config_path, "w", encoding="utf-8") as file_obj:
            json.dump({"save_report": True}, file_obj)

        cfg = Config(["--config", config_path])

        self.assertTrue(cfg.save_report)

    def test_save_report_can_be_enabled_from_cli(self):
        cfg = Config(["--config", os.path.join(self.test_root, "config.json"), "--save-report"])

        self.assertTrue(cfg.save_report)


if __name__ == "__main__":
    unittest.main()
