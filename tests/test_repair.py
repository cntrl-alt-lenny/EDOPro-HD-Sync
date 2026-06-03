"""Tests for --repair broken-image detection (find_broken_images)."""

import os
import tempfile
import unittest

import main

VALID_JPEG = b"\xff\xd8\xff" + b"\x00" * 1024


class FindBrokenImagesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.pics = self.tmp.name

    def _write(self, name, data):
        with open(os.path.join(self.pics, name), "wb") as f:
            f.write(data)

    def test_flags_corrupt_and_truncated_keeps_valid(self):
        self._write("1.jpg", VALID_JPEG)  # valid -> kept
        self._write("2.jpg", b"<html>Not Found</html>" + b" " * 2000)  # not a jpeg -> broken
        self._write("3.jpg", b"\xff\xd8\xff")  # too small -> broken
        self._write("4.jpg", b"")  # empty -> broken

        broken = set(main.find_broken_images(self.pics, {1, 2, 3, 4}))

        self.assertEqual(broken, {2, 3, 4})

    def test_ignores_unknown_ids_and_non_jpg_files(self):
        self._write("100.jpg", b"junk")  # broken but not a known id -> ignored
        self._write("notes.txt", b"junk")  # not a .jpg -> ignored
        self._write("cover.png", main.PNG_MAGIC)  # not a .jpg -> ignored

        self.assertEqual(main.find_broken_images(self.pics, {1, 2}), [])

    def test_missing_directory_returns_empty(self):
        self.assertEqual(main.find_broken_images(os.path.join(self.pics, "nope"), {1}), [])


if __name__ == "__main__":
    unittest.main()
