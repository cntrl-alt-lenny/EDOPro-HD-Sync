import unittest
from unittest import mock

import main


class StdoutStub:
    def __init__(self, encoding: str | None):
        self.encoding = encoding


class ConsoleEncodingTests(unittest.TestCase):
    def test_unicode_output_supported_for_utf8(self):
        with mock.patch.object(main.sys, "stdout", StdoutStub("utf-8")):
            self.assertTrue(main._stdout_supports_unicode())

    def test_unicode_output_disabled_for_cp1252(self):
        with mock.patch.object(main.sys, "stdout", StdoutStub("cp1252")):
            self.assertFalse(main._stdout_supports_unicode())


if __name__ == "__main__":
    unittest.main()