import unittest

import main
from config import DEFAULTS
from tricky_cards import SAFE_MULTI_ART_FALLBACK_CASE


class CatalogLookupTests(unittest.TestCase):
    def setUp(self):
        self.official_source = DEFAULTS["sources"]["official"]

    def test_build_ygoprodeck_image_lookup_uses_exact_artwork_ids(self):
        payload = {
            "data": [
                {
                    "card_images": [
                        {"id": 89631139, "image_url": "https://cdn.example/89631139.jpg"},
                        {"id": "89631140"},
                    ]
                },
                {
                    "card_images": [
                        {"id": None},
                        {"id": "not-a-number"},
                    ]
                },
            ]
        }

        lookup = main.build_ygoprodeck_image_lookup(payload, self.official_source)

        self.assertEqual(
            lookup,
            {
                89631139: "https://cdn.example/89631139.jpg",
                89631140: f"{self.official_source}/89631140.jpg",
            },
        )

    def test_build_ygoprodeck_download_candidates_skips_wrong_multi_art_substitutes(self):
        lookup = {
            image_id: f"{self.official_source}/{image_id}.jpg"
            for image_id in SAFE_MULTI_ART_FALLBACK_CASE["confirmed_art_ids"]
        }

        candidates = main.build_ygoprodeck_download_candidates(
            SAFE_MULTI_ART_FALLBACK_CASE["card_id"],
            SAFE_MULTI_ART_FALLBACK_CASE["official_matches"],
            None,
            False,
            False,
            lookup,
            self.official_source,
        )

        self.assertEqual(candidates, [])

    def test_build_ygoprodeck_download_candidates_allows_suffix_name_match(self):
        candidates = main.build_ygoprodeck_download_candidates(
            46986424,
            [46986414],
            None,
            False,
            True,
            {46986414: f"{self.official_source}/46986414.jpg"},
            self.official_source,
        )

        self.assertEqual(
            candidates,
            [("name-match", f"{self.official_source}/46986414.jpg")],
        )

    def test_build_ygoprodeck_download_candidates_uses_pre_errata_offset_when_needed(self):
        candidates = main.build_ygoprodeck_download_candidates(
            70781062,
            [70781062],
            None,
            True,
            False,
            {70781052: f"{self.official_source}/70781052.jpg"},
            self.official_source,
        )

        self.assertEqual(
            candidates,
            [("pre-errata-offset", f"{self.official_source}/70781052.jpg")],
        )


if __name__ == "__main__":
    unittest.main()
