import asyncio
import json
import os
import tempfile
import unittest
from unittest import mock

import main
from config import Config


class FakeResponse:
    status = 200

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakeSession:
    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def get(self, *args, **kwargs):
        return FakeResponse()


class StartupPromptTests(unittest.TestCase):
    def setUp(self):
        self.workspace_root = os.getcwd()
        self.temp_dir = tempfile.TemporaryDirectory(dir=self.workspace_root)
        self.addCleanup(self.temp_dir.cleanup)
        self.test_root = self.temp_dir.name

    def write_config(self, data: dict) -> str:
        config_path = os.path.join(self.test_root, "config.json")
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        return config_path

    def make_edopro_dir(self, name: str, *, with_cards: bool = False, with_expansion: bool = False) -> str:
        edopro_path = os.path.join(self.test_root, name)
        os.makedirs(edopro_path, exist_ok=True)
        if with_cards:
            open(os.path.join(edopro_path, "cards.cdb"), "wb").close()
        if with_expansion:
            expansions_path = os.path.join(edopro_path, "expansions")
            os.makedirs(expansions_path, exist_ok=True)
            open(os.path.join(expansions_path, "custom.cdb"), "wb").close()
        return edopro_path

    def test_prompt_retries_until_valid_and_saves_config(self):
        config_path = self.write_config({"concurrency": 7})
        invalid_path = os.path.join(self.test_root, "not-edopro")
        valid_path = self.make_edopro_dir("edopro-root", with_cards=True)
        cfg = Config(["--config", config_path, "--quiet"])

        with mock.patch("builtins.input", side_effect=[invalid_path, f'"{valid_path}"']):
            dbs = main.prompt_for_edopro_path(cfg)

        self.assertEqual(dbs, [os.path.join(valid_path, "cards.cdb")])
        self.assertEqual(cfg.edopro_path, os.path.abspath(valid_path))
        with open(config_path, "r", encoding="utf-8") as f:
            saved = json.load(f)
        self.assertEqual(saved["edopro_path"], os.path.abspath(valid_path))
        self.assertEqual(saved["concurrency"], 7)

    def test_run_uses_prompted_expansions_folder(self):
        config_path = self.write_config({})
        valid_path = self.make_edopro_dir("edopro-expansions", with_expansion=True)
        cfg = Config(["--config", config_path, "--dry-run", "--quiet"])
        expected_dbs = [os.path.join(valid_path, "expansions", "custom.cdb")]

        with mock.patch("builtins.input", return_value=valid_path), \
            mock.patch.object(main, "scan_databases", return_value=({123: "Test Card"}, {})) as scan_mock, \
            mock.patch.object(main, "load_manual_map", return_value={}), \
            mock.patch.object(main.aiohttp, "ClientSession", FakeSession):
            asyncio.run(main.run(cfg))

        scan_mock.assert_called_once_with(expected_dbs)
        self.assertTrue(os.path.isdir(os.path.join(valid_path, "pics")))
        with open(config_path, "r", encoding="utf-8") as f:
            saved = json.load(f)
        self.assertEqual(saved["edopro_path"], os.path.abspath(valid_path))


if __name__ == "__main__":
    unittest.main()
