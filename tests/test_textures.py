"""Tests for the curated-textures download feature."""

import asyncio
import os
import tempfile
import types
import unittest
from unittest import mock

import main

PNG_BODY = main.PNG_MAGIC + b"\x00" * 1024
JPEG_BODY = b"\xff\xd8\xff" + b"\x00" * 1024


class _Resp:
    def __init__(self, status=200, body=b"", json_data=None):
        self.status = status
        self._body = body
        self._json = json_data
        self.headers = {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def read(self):
        return self._body

    async def json(self):
        return self._json


class _Session:
    """Returns the release JSON for the API call and image bytes for each asset."""

    def __init__(self, release_json, asset_body=PNG_BODY, asset_status=200):
        self.release_json = release_json
        self.asset_body = asset_body
        self.asset_status = asset_status
        self.requested = []

    def get(self, url, timeout=None):
        self.requested.append(url)
        if url == main.TEXTURES_RELEASE_API:
            return _Resp(status=200, json_data=self.release_json)
        return _Resp(status=self.asset_status, body=self.asset_body)


class LooksLikeImageTests(unittest.TestCase):
    def test_accepts_png(self):
        self.assertTrue(main._looks_like_image(PNG_BODY))

    def test_accepts_jpeg(self):
        self.assertTrue(main._looks_like_image(JPEG_BODY))

    def test_rejects_too_small(self):
        self.assertFalse(main._looks_like_image(main.PNG_MAGIC + b"\x00" * 10))

    def test_rejects_non_image(self):
        self.assertFalse(main._looks_like_image(b"<html>error</html>" + b" " * 2000))


class CuratedTexturesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cfg = types.SimpleNamespace(
            edopro_path=self.tmp.name, timeout=30, max_retries=1, force=False
        )
        patcher = mock.patch.object(main.asyncio, "sleep", new=mock.AsyncMock())
        patcher.start()
        self.addCleanup(patcher.stop)

    def _run(self, session):
        return asyncio.run(main.download_curated_textures(session, self.cfg))

    def test_downloads_image_assets_into_textures_dir(self):
        release = {
            "assets": [
                {"name": "bg.png", "browser_download_url": "http://x/bg.png"},
                {"name": "cover.png", "browser_download_url": "http://x/cover.png"},
            ]
        }
        got, skipped, total = self._run(_Session(release))

        self.assertEqual((got, skipped, total), (2, 0, 2))
        textures = os.path.join(self.tmp.name, "textures")
        self.assertTrue(os.path.exists(os.path.join(textures, "bg.png")))
        self.assertTrue(os.path.exists(os.path.join(textures, "cover.png")))

    def test_ignores_non_image_assets(self):
        release = {
            "assets": [
                {"name": "bg.png", "browser_download_url": "http://x/bg.png"},
                {"name": "manifest.json", "browser_download_url": "http://x/manifest.json"},
            ]
        }
        got, skipped, total = self._run(_Session(release))

        self.assertEqual((got, skipped, total), (1, 0, 1))
        self.assertFalse(os.path.exists(os.path.join(self.tmp.name, "textures", "manifest.json")))

    def test_returns_zero_when_release_not_published(self):
        class _NotFound:
            def get(self, url, timeout=None):
                return _Resp(status=404)

        self.assertEqual(self._run(_NotFound()), (0, 0, 0))

    def test_counts_failed_asset_downloads(self):
        release = {"assets": [{"name": "bg.png", "browser_download_url": "http://x/bg.png"}]}
        # Asset returns a non-image body, so the download is rejected.
        session = _Session(release, asset_body=b"not an image" * 100)
        got, skipped, total = self._run(session)

        self.assertEqual((got, skipped, total), (0, 0, 1))

    def test_skips_textures_already_on_disk(self):
        textures = os.path.join(self.tmp.name, "textures")
        os.makedirs(textures, exist_ok=True)
        with open(os.path.join(textures, "bg.png"), "wb") as f:
            f.write(PNG_BODY)
        release = {"assets": [{"name": "bg.png", "browser_download_url": "http://x/bg.png"}]}
        session = _Session(release)

        got, skipped, total = self._run(session)

        self.assertEqual((got, skipped, total), (0, 1, 1))
        # Only the release listing was fetched — no asset download request.
        self.assertEqual(session.requested, [main.TEXTURES_RELEASE_API])

    def test_force_redownloads_existing_textures(self):
        textures = os.path.join(self.tmp.name, "textures")
        os.makedirs(textures, exist_ok=True)
        with open(os.path.join(textures, "bg.png"), "wb") as f:
            f.write(b"stale")
        release = {"assets": [{"name": "bg.png", "browser_download_url": "http://x/bg.png"}]}
        self.cfg.force = True

        got, skipped, total = self._run(_Session(release))

        self.assertEqual((got, skipped, total), (1, 0, 1))
        with open(os.path.join(textures, "bg.png"), "rb") as f:
            self.assertEqual(f.read(), PNG_BODY)


class ResolveWantTexturesTests(unittest.TestCase):
    def _cfg(self, textures=None, dry_run=False, quiet=False):
        return types.SimpleNamespace(textures=textures, dry_run=dry_run, quiet=quiet)

    def test_explicit_true_wins(self):
        self.assertTrue(main._resolve_want_textures(self._cfg(textures=True), has_cards=True))

    def test_explicit_false_wins(self):
        self.assertFalse(main._resolve_want_textures(self._cfg(textures=False), has_cards=False))

    def test_quiet_defaults_to_false(self):
        cfg = self._cfg(textures=None, quiet=True)
        self.assertFalse(main._resolve_want_textures(cfg, has_cards=True))

    def test_dry_run_defaults_to_false(self):
        cfg = self._cfg(textures=None, dry_run=True)
        self.assertFalse(main._resolve_want_textures(cfg, has_cards=True))

    def test_prompts_when_unset_and_interactive(self):
        cfg = self._cfg(textures=None)
        with mock.patch.object(main, "_prompt_yes_no", return_value=True) as prompt:
            self.assertTrue(main._resolve_want_textures(cfg, has_cards=False))
        prompt.assert_called_once()


class TextureReleaseApiTests(unittest.TestCase):
    def test_default_pack_uses_textures_tag(self):
        self.assertEqual(main._textures_release_api(None), main.TEXTURES_RELEASE_API)
        self.assertEqual(main._textures_release_api("default"), main.TEXTURES_RELEASE_API)

    def test_named_pack_uses_suffixed_tag(self):
        self.assertTrue(main._textures_release_api("dark").endswith("/tags/textures-dark"))


class _ReleasesSession:
    def __init__(self, releases):
        self.releases = releases

    def get(self, url, timeout=None):
        return _Resp(status=200, json_data=self.releases)


class ListTexturePacksTests(unittest.TestCase):
    def test_filters_to_textures_releases(self):
        releases = [
            {"tag_name": "v4.8.0", "name": "App 4.8.0"},
            {"tag_name": "textures", "name": "Curated Textures"},
            {"tag_name": "textures-dark", "name": "Dark Pack"},
            {"tag_name": "random", "name": "Nope"},
        ]
        packs = asyncio.run(main.list_texture_packs(_ReleasesSession(releases)))

        self.assertEqual(len(packs), 2)
        self.assertIn(("default", "Curated Textures"), packs)
        self.assertIn(("dark", "Dark Pack"), packs)


class ResolveTexturePackTests(unittest.TestCase):
    def _cfg(self, textures_pack=None, quiet=False, dry_run=False):
        return types.SimpleNamespace(textures_pack=textures_pack, quiet=quiet, dry_run=dry_run)

    def test_explicit_flag_wins(self):
        cfg = self._cfg(textures_pack="dark")
        self.assertEqual(asyncio.run(main._resolve_texture_pack(None, cfg)), "dark")

    def test_quiet_uses_default(self):
        cfg = self._cfg(quiet=True)
        self.assertEqual(asyncio.run(main._resolve_texture_pack(None, cfg)), "default")

    def test_single_pack_skips_prompt(self):
        with mock.patch.object(
            main, "list_texture_packs", new=mock.AsyncMock(return_value=[("default", "x")])
        ):
            self.assertEqual(
                asyncio.run(main._resolve_texture_pack(object(), self._cfg())), "default"
            )

    def test_multiple_packs_prompt_picks_choice(self):
        packs = [("default", "Std"), ("dark", "Dark")]
        with (
            mock.patch.object(main, "list_texture_packs", new=mock.AsyncMock(return_value=packs)),
            mock.patch("builtins.input", return_value="2"),
        ):
            self.assertEqual(asyncio.run(main._resolve_texture_pack(object(), self._cfg())), "dark")


class PackDownloadUrlTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cfg = types.SimpleNamespace(edopro_path=self.tmp.name, timeout=30, max_retries=1)

    def test_download_requests_pack_specific_release(self):
        captured = {}

        class _S:
            def get(self, url, timeout=None):
                captured.setdefault("url", url)
                return _Resp(status=404)

        asyncio.run(main.download_curated_textures(_S(), self.cfg, "dark"))
        self.assertTrue(captured["url"].endswith("/tags/textures-dark"))


if __name__ == "__main__":
    unittest.main()
