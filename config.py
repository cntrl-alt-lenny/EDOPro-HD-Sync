"""
Configuration management for EDOPro HD Sync.

Loads settings from (in priority order):
  1. CLI arguments (highest priority)
  2. config.json file
  3. Built-in defaults (lowest priority)
"""

import argparse
import json
import os

# ── Defaults ──────────────────────────────────────────────────────────────────

DEFAULTS = {
    "edopro_path": ".",
    "concurrency": 50,
    "max_retries": 3,
    "timeout": 30,
    "sources": {
        "official": "https://images.ygoprodeck.com/images/cards",
        "backup": "https://raw.githubusercontent.com/ProjectIgnis/Images/master/pics",
    },
    "suffixes_to_strip": [
        " GOAT",
        " (Pre-Errata)",
        " (GOAT)",
        " Pre-Errata",
    ],
}

CONFIG_FILENAME = "config.json"


# ── Config file ───────────────────────────────────────────────────────────────

def _load_config_file(path: str) -> dict:
    """Read config.json if it exists; return empty dict otherwise."""
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        print(f"⚠️  Could not read {path}: {exc}  — using defaults.")
        return {}


def generate_default_config(path: str) -> None:
    """Write a fresh config.json with all defaults so users can edit it."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(DEFAULTS, f, indent=2)
    print(f"📄 Generated default config at {path}")


# ── CLI arguments ─────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="EDOPro HD Sync",
        description="Automatically download missing HD card artwork for EDOPro.",
    )
    p.add_argument(
        "--force",
        action="store_true",
        help="Re-download ALL images, even ones that already exist.",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be downloaded without actually downloading.",
    )
    p.add_argument(
        "--concurrency",
        type=int,
        default=None,
        help="Max simultaneous downloads (default: 50).",
    )
    p.add_argument(
        "--max-retries",
        type=int,
        default=None,
        help="Retry failed downloads N times (default: 3).",
    )
    p.add_argument(
        "--timeout",
        type=int,
        default=None,
        help="HTTP timeout in seconds (default: 30).",
    )
    p.add_argument(
        "--config",
        type=str,
        default=CONFIG_FILENAME,
        help="Path to config file (default: config.json).",
    )
    p.add_argument(
        "--generate-config",
        action="store_true",
        help="Write a default config.json and exit.",
    )
    p.add_argument(
        "--quiet",
        action="store_true",
        help="Minimal output — only show the progress bar and summary.",
    )
    return p


# ── Public API ────────────────────────────────────────────────────────────────

class Config:
    """Immutable bag of settings built from defaults → file → CLI."""

    def __init__(self):
        parser = _build_parser()
        self.cli = parser.parse_args()

        # If user just wants a config file generated, do that and bail
        if self.cli.generate_config:
            generate_default_config(self.cli.config)
            raise SystemExit(0)

        file_cfg = _load_config_file(self.cli.config)

        # Merge: defaults ← file ← CLI
        self.edopro_path: str = file_cfg.get("edopro_path", DEFAULTS["edopro_path"])
        self.pics_path: str = os.path.join(self.edopro_path, "pics")
        self.manual_map_file: str = os.path.join(self.edopro_path, "manual_map.json")

        self.concurrency: int = (
            self.cli.concurrency
            or file_cfg.get("concurrency")
            or DEFAULTS["concurrency"]
        )
        self.max_retries: int = (
            self.cli.max_retries
            or file_cfg.get("max_retries")
            or DEFAULTS["max_retries"]
        )
        self.timeout: int = (
            self.cli.timeout
            or file_cfg.get("timeout")
            or DEFAULTS["timeout"]
        )

        self.sources: dict = file_cfg.get("sources", DEFAULTS["sources"])
        self.suffixes: list = file_cfg.get(
            "suffixes_to_strip", DEFAULTS["suffixes_to_strip"]
        )

        self.force: bool = self.cli.force
        self.dry_run: bool = self.cli.dry_run
        self.quiet: bool = self.cli.quiet
