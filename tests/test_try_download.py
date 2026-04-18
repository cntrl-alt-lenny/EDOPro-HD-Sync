"""Tests for the low-level HTTP retry/backoff path in _try_download."""

import asyncio
import os
import tempfile
import unittest
from unittest import mock

import aiohttp

import main


class _FakeResponse:
    def __init__(self, status: int, body: bytes):
        self.status = status
        self._body = body

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def read(self) -> bytes:
        return self._body


class _FakeSession:
    """Minimal ClientSession stand-in that replays a scripted sequence of responses."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0

    def get(self, url, timeout=None):
        self.calls += 1
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return _FakeResponse(*item)


class TryDownloadTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.filepath = os.path.join(self.temp_dir.name, "card.jpg")
        self.timeout = aiohttp.ClientTimeout(total=1)
        # No real sleeps so tests stay fast.
        patcher = mock.patch.object(main.asyncio, "sleep", new=mock.AsyncMock(return_value=None))
        patcher.start()
        self.addCleanup(patcher.stop)

    def _run(self, session, max_retries=3):
        return asyncio.run(
            main._try_download(session, "http://example/x.jpg", self.filepath, self.timeout, max_retries)
        )

    def test_writes_file_atomically_on_success(self):
        body = b"x" * 1024
        session = _FakeSession([(200, body)])

        result = self._run(session)

        self.assertTrue(result)
        with open(self.filepath, "rb") as f:
            self.assertEqual(f.read(), body)
        # Temp file should be cleaned up after successful rename.
        self.assertFalse(os.path.exists(self.filepath + ".part"))

    def test_rejects_payload_below_512_bytes(self):
        session = _FakeSession([(200, b"tiny"), (200, b"tiny"), (200, b"tiny")])

        result = self._run(session)

        self.assertFalse(result)
        self.assertFalse(os.path.exists(self.filepath))
        self.assertEqual(session.calls, 3)

    def test_returns_false_on_404_without_retry(self):
        session = _FakeSession([(404, b"")])

        result = self._run(session)

        self.assertFalse(result)
        self.assertEqual(session.calls, 1)

    def test_retries_transient_client_error_then_succeeds(self):
        session = _FakeSession([
            aiohttp.ClientConnectionError("boom"),
            (200, b"y" * 1024),
        ])

        result = self._run(session)

        self.assertTrue(result)
        self.assertEqual(session.calls, 2)

    def test_gives_up_after_max_retries(self):
        session = _FakeSession([
            TimeoutError(),
            TimeoutError(),
            TimeoutError(),
        ])

        result = self._run(session)

        self.assertFalse(result)
        self.assertEqual(session.calls, 3)

    def test_cleans_up_partial_file_when_disk_write_fails(self):
        session = _FakeSession([(200, b"z" * 1024)])

        # Point tmp_path at a directory that doesn't exist so open() raises OSError.
        broken_path = os.path.join(self.temp_dir.name, "missing-subdir", "card.jpg")
        result = asyncio.run(
            main._try_download(session, "http://example/x.jpg", broken_path, self.timeout, 3)
        )

        self.assertFalse(result)
        self.assertFalse(os.path.exists(broken_path + ".part"))


if __name__ == "__main__":
    unittest.main()
