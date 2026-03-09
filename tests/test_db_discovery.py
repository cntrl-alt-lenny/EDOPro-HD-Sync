import os
import tempfile
import unittest

import main


class DbDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.workspace_root = os.getcwd()
        self.temp_dir = tempfile.TemporaryDirectory(dir=self.workspace_root)
        self.addCleanup(self.temp_dir.cleanup)
        self.edopro_root = self.temp_dir.name

    def touch(self, relative_path: str) -> str:
        path = os.path.join(self.edopro_root, relative_path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, "wb").close()
        return path

    def test_get_db_files_includes_repository_delta_databases(self):
        root_db = self.touch("cards.cdb")
        expansion_db = self.touch(os.path.join("expansions", "goat-entries.cdb"))
        repo_delta_db = self.touch(
            os.path.join("repositories", "delta-bagooska", "goat-entries.delta.cdb")
        )
        self.touch(os.path.join("repositories", "delta-bagooska", "prerelease-loch.cdb"))

        self.assertEqual(
            main.get_db_files(self.edopro_root),
            [root_db, expansion_db, repo_delta_db],
        )


if __name__ == "__main__":
    unittest.main()
