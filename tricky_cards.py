"""Real-world regression fixtures used by health checks and tests."""

KNOWN_MULTI_ART_CARDS = [
    {
        "name": "Blue-Eyes White Dragon",
        "official_ids": [
            89631136,
            89631137,
            89631138,
            89631139,
            89631140,
            89631141,
            89631142,
            89631143,
            89631144,
            89631145,
            89631146,
            89631147,
            89631148,
        ],
    },
    {
        "name": "Dark Magician",
        "official_ids": [
            36996508,
            46986410,
            46986411,
            46986412,
            46986413,
            46986414,
            46986415,
            46986416,
            46986417,
            46986418,
            46986419,
            46986420,
            46986421,
            46986422,
            46986423,
        ],
    },
    {
        "name": "Red-Eyes Black Dragon",
        "official_ids": [
            74677422,
            74677423,
            74677424,
            74677425,
            74677426,
            74677427,
            74677428,
            74677429,
            74677430,
            74677431,
        ],
    },
]

KNOWN_SUFFIX_CASES = [
    {
        "name": "Dark Magician (Pre-Errata)",
        "required_match_id": 46986414,
        "expected_pre_errata_miss": False,
        "expected_suffix_match": True,
    },
]

SAFE_MULTI_ART_FALLBACK_CASE = {
    "card_id": 89631136,
    "name": "Blue-Eyes White Dragon",
    "official_matches": [89631136, 89631139, 89631140],
    "confirmed_art_ids": {89631139, 89631140},
}
