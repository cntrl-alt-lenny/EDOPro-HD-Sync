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
import sys

DEFAULTS = {
    "edopro_path": ".",
    "concurrency": 50,
    "max_retries": 3,
    "timeout": 30,
    "save_failures": False,
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


def _pick_value(cli_val, file_val, default):
    if cli_val is not None:
        return cli_val
    if file_val is not None:
        return file_val
    return default


def _ensure_int(name: str, value, default: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        print(f"Warning: {name} must be an integer; using {default}.")
        return default
    return value


def _clamp_min_int(name: str, value: int, minimum: int) -> int:
    if value < minimum:
        print(f"Warning: {name} must be >= {minimum}; using {minimum}.")
        return minimum
    return value


def _ensure_bool(name: str, value, default: bool) -> bool:
    if not isinstance(value, bool):
        print(f"Warning: {name} must be true or false; using {default}.")
        return default
    return value


def _load_config_file(path: str) -> dict:
    """Read config.json if it exists; return empty dict otherwise."""
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            print(f"Warning: {path} must contain a JSON object at the top level; using defaults.")
            return {}
        return data
    except (json.JSONDecodeError, OSError) as exc:
        print(f"Warning: Could not read {path}: {exc}; using defaults.")
        return {}


def _write_config_file(path: str, config_data: dict) -> None:
    """Write config data with a stable, user-editable layout."""
    parent_dir = os.path.dirname(os.path.abspath(path))
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config_data, f, indent=2)


def generate_default_config(path: str) -> None:
    """Write a fresh config.json with all defaults so users can edit it."""
    _write_config_file(path, DEFAULTS)
    print(f"Generated default config at {path}")


def save_edopro_path(path: str, edopro_path: str) -> bool:
    """Update only the remembered EDOPro path in the config file."""
    config_data = _load_config_file(path)
    config_data["edopro_path"] = edopro_path
    try:
        _write_config_file(path, config_data)
    except OSError as exc:
        print(f"Warning: Could not write {path}: {exc}")
        return False
    return True


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
        default=None,
        help="Use a custom config file (default: config.json beside the executable/script).",
    )
    p.add_argument(
        "--generate-config",
        action="store_true",
        help="Write a default config.json and exit.",
    )
    p.add_argument(
        "--quiet",
        action="store_true",
        help="Minimal output - only show the progress bar and summary.",
    )
    p.add_argument(
        "--save-report",
        action="store_true",
        help="Write a timestamped .txt sync report in the EDOPro folder.",
    )
    p.add_argument(
        "--save-failures",
        action="store_true",
        default=None,
        help="Write a timestamped .txt file of cards that still failed to sync.",
    )
    p.add_argument(
        "--no-pause",
        action="store_true",
        help="On Windows packaged builds, close immediately instead of waiting for Enter.",
    )
    return p


class Config:
    """Immutable bag of settings built from defaults to file to CLI."""

    def __init__(self, argv: list[str] | None = None):
        parser = _build_parser()
        self.cli = parser.parse_args(argv)
        default_config_base = sys.executable if getattr(sys, "frozen", False) else __file__
        self.config_path: str = (
            os.path.abspath(os.path.expanduser(self.cli.config))
            if self.cli.config
            else os.path.join(
                os.path.dirname(os.path.abspath(default_config_base)),
                CONFIG_FILENAME,
            )
        )

        if self.cli.generate_config:
            generate_default_config(self.config_path)
            raise SystemExit(0)

        file_cfg = _load_config_file(self.config_path)

        self.edopro_path: str = ""
        self.pics_path: str = ""
        self.manual_map_file: str = ""
        self.set_edopro_path(file_cfg.get("edopro_path", DEFAULTS["edopro_path"]))

        self.concurrency: int = _pick_value(
            self.cli.concurrency, file_cfg.get("concurrency"), DEFAULTS["concurrency"]
        )
        self.max_retries: int = _pick_value(
            self.cli.max_retries, file_cfg.get("max_retries"), DEFAULTS["max_retries"]
        )
        self.timeout: int = _pick_value(
            self.cli.timeout, file_cfg.get("timeout"), DEFAULTS["timeout"]
        )

        self.concurrency = _ensure_int("concurrency", self.concurrency, DEFAULTS["concurrency"])
        self.max_retries = _ensure_int("max_retries", self.max_retries, DEFAULTS["max_retries"])
        self.timeout = _ensure_int("timeout", self.timeout, DEFAULTS["timeout"])

        self.concurrency = _clamp_min_int("concurrency", self.concurrency, 1)
        self.max_retries = _clamp_min_int("max_retries", self.max_retries, 1)
        self.timeout = _clamp_min_int("timeout", self.timeout, 1)

        sources = dict(DEFAULTS["sources"])
        file_sources = file_cfg.get("sources")
        if isinstance(file_sources, dict):
            sources.update(file_sources)
        elif file_sources is not None:
            print("Warning: sources must be an object; using defaults.")
        self.sources: dict = sources
        self.suffixes: list = file_cfg.get(
            "suffixes_to_strip", DEFAULTS["suffixes_to_strip"]
        )

        self.force: bool = self.cli.force
        self.dry_run: bool = self.cli.dry_run
        self.quiet: bool = self.cli.quiet
        self.save_report: bool = self.cli.save_report
        self.save_failures: bool = _ensure_bool(
            "save_failures",
            _pick_value(
                self.cli.save_failures,
                file_cfg.get("save_failures"),
                DEFAULTS["save_failures"],
            ),
            DEFAULTS["save_failures"],
        )
        self.no_pause: bool = self.cli.no_pause

    def set_edopro_path(self, edopro_path: str, save: bool = False) -> bool:
        """Update path-derived fields and optionally persist the new folder."""
        normalized_path = os.path.abspath(os.path.expanduser(edopro_path))
        self.edopro_path = normalized_path
        self.pics_path = os.path.join(self.edopro_path, "pics")
        self.manual_map_file = os.path.join(self.edopro_path, "manual_map.json")
        if save:
            return save_edopro_path(self.config_path, self.edopro_path)
        return True
