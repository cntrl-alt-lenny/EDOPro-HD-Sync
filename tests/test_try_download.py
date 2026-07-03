"""Tests for the low-level HTTP retry/backoff path in _try_download."""

import asyncio
import os
import tempfile
import unittest
from unittest import mock

import aiohttp

import main

JPEG_MAGIC = b"\xff\xd8\xff"


def _jpeg_body(size: int = 1024) -> bytes:
    """A payload that passes _looks_like_jpeg: JPEG magic bytes + enough length."""
    return JPEG_MAGIC + b"\x00" * size


class _FakeResponse:
    def __init__(self, status: int, body: bytes, headers: dict | None = None):
        self.status = status
        self._body = body
        self.headers = headers or {}

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
        # No real sleeps so tests stay fast; keep a handle to assert on delays.
        self.sleep_mock = mock.AsyncMock(return_value=None)
        patcher = mock.patch.object(main.asyncio, "sleep", new=self.sleep_mock)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _run(self, session, max_retries=3):
        return asyncio.run(
            main._try_download(
                session, "http://example/x.jpg", self.filepath, self.timeout, max_retries
            )
        )

    def test_writes_file_atomically_on_success(self):
        body = _jpeg_body()
        session = _FakeSession([(200, body)])

        result = self._run(session)

        self.assertIs(result, main.FetchResult.OK)
        with open(self.filepath, "rb") as f:
            self.assertEqual(f.read(), body)
        # Temp file should be cleaned up after successful rename.
        self.assertFalse(os.path.exists(self.filepath + ".part"))

    def test_rejects_payload_below_512_bytes(self):
        session = _FakeSession([(200, b"tiny"), (200, b"tiny"), (200, b"tiny")])

        result = self._run(session)

        # A bad body could be an anti-bot page, so it's transient, not missing.
        self.assertIs(result, main.FetchResult.ERROR)
        self.assertFalse(os.path.exists(self.filepath))
        self.assertEqual(session.calls, 3)

    def test_rejects_non_jpeg_payload_with_200(self):
        # An HTML error page served with HTTP 200 clears the size threshold but
        # is not a JPEG, so it must be rejected rather than saved as a .jpg.
        page = b"<html><body>Not Found</body></html>" + b" " * 1024
        session = _FakeSession([(200, page), (200, page), (200, page)])

        result = self._run(session)

        self.assertIs(result, main.FetchResult.ERROR)
        self.assertFalse(os.path.exists(self.filepath))
        self.assertEqual(session.calls, 3)

    def test_returns_missing_on_404_without_retry(self):
        session = _FakeSession([(404, b"")])

        result = self._run(session)

        # Only a 404 is proof the image doesn't exist — safe to cache.
        self.assertIs(result, main.FetchResult.MISSING)
        self.assertEqual(session.calls, 1)

    def test_honors_retry_after_on_429(self):
        session = _FakeSession(
            [
                (429, b"", {"Retry-After": "5"}),
                (200, _jpeg_body()),
            ]
        )

        result = self._run(session)

        self.assertIs(result, main.FetchResult.OK)
        self.assertEqual(session.calls, 2)
        # The server's cooldown is honored instead of the exponential backoff.
        self.sleep_mock.assert_awaited_once_with(5.0)

    def test_429_without_retry_after_falls_back_to_backoff(self):
        session = _FakeSession(
            [
                (429, b""),
                (200, _jpeg_body()),
            ]
        )

        result = self._run(session)

        self.assertIs(result, main.FetchResult.OK)
        self.assertEqual(session.calls, 2)
        # No header -> normal first-attempt backoff of 2**0 == 1.
        self.sleep_mock.assert_awaited_once_with(1)

    def test_retry_after_is_capped(self):
        session = _FakeSession(
            [
                (429, b"", {"Retry-After": "9999"}),
                (200, _jpeg_body()),
            ]
        )

        result = self._run(session)

        self.assertIs(result, main.FetchResult.OK)
        self.sleep_mock.assert_awaited_once_with(main.RETRY_AFTER_CAP_SECONDS)

    def test_retries_transient_client_error_then_succeeds(self):
        session = _FakeSession(
            [
                aiohttp.ClientConnectionError("boom"),
                (200, _jpeg_body()),
            ]
        )

        result = self._run(session)

        self.assertIs(result, main.FetchResult.OK)
        self.assertEqual(session.calls, 2)

    def test_gives_up_after_max_retries(self):
        session = _FakeSession(
            [
                TimeoutError(),
                TimeoutError(),
                TimeoutError(),
            ]
        )

        result = self._run(session)

        # Timeouts are transient — the card must not be cached as unavailable.
        self.assertIs(result, main.FetchResult.ERROR)
        self.assertEqual(session.calls, 3)

    def test_cleans_up_partial_file_when_disk_write_fails(self):
        session = _FakeSession([(200, _jpeg_body())])

        # Point tmp_path at a directory that doesn't exist so open() raises OSError.
        broken_path = os.path.join(self.temp_dir.name, "missing-subdir", "card.jpg")
        result = asyncio.run(
            main._try_download(session, "http://example/x.jpg", broken_path, self.timeout, 3)
        )

        self.assertIs(result, main.FetchResult.ERROR)
        self.assertFalse(os.path.exists(broken_path + ".part"))


class DownloadCardOutcomeTests(unittest.TestCase):
    """download_card must separate 'art doesn't exist' from 'network trouble'."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.sleep_mock = mock.AsyncMock(return_value=None)
        patcher = mock.patch.object(main.asyncio, "sleep", new=self.sleep_mock)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _cfg(self, **overrides):
        from types import SimpleNamespace

        values = {
            "pics_path": self.temp_dir.name,
            "force": False,
            "dry_run": False,
            "sources": {"official": "http://official", "backup": "http://backup"},
            "timeout": 1,
            "max_retries": 1,
        }
        values.update(overrides)
        return SimpleNamespace(**values)

    def _download(self, session, cfg, card_id=46986414):
        stats = main.DownloadStats()
        asyncio.run(
            main.download_card(
                session,
                card_id,
                "Dark Magician",
                [],
                None,
                False,
                False,
                cfg,
                stats,
            )
        )
        return stats

    def test_all_sources_404_is_a_definitive_miss(self):
        # Direct ID 404s, backup 404s -> unavailable for real, safe to cache.
        session = _FakeSession([(404, b""), (404, b"")])

        stats = self._download(session, self._cfg())

        self.assertEqual(stats.failed, 1)
        self.assertNotIn(46986414, stats.transient_ids)

    def test_network_error_on_any_source_is_transient(self):
        # Direct ID 404s, but the backup times out -> must NOT be cached.
        session = _FakeSession([(404, b""), TimeoutError()])

        stats = self._download(session, self._cfg())

        self.assertEqual(stats.failed, 1)
        self.assertIn(46986414, stats.transient_ids)

    def test_dry_run_counts_planned_downloads(self):
        session = _FakeSession([])
        with mock.patch.object(main.console, "print"):
            stats = self._download(session, self._cfg(dry_run=True))

        self.assertEqual(stats.planned, 1)
        self.assertEqual(session.calls, 0)


if __name__ == "__main__":
    unittest.main()
