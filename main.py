"""
EDOPro HD Sync - Automatically download missing HD card artwork for EDOPro.

Improvements over the original:
  - Rich progress bars and color-coded console output
  - Automatic retries with exponential backoff on failed downloads
  - Configurable via config.json and CLI arguments
  - Detailed summary report at the end
"""

import asyncio
import contextlib
import json
import ntpath
import os
import re
import sqlite3
import ssl
import subprocess
import sys
from datetime import datetime
from time import perf_counter

import aiohttp
import certifi

from config import BUILTIN_MANUAL_MAP, DEFAULTS, Config

if sys.platform == "win32":
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception:
        tk = None
        filedialog = None
else:
    tk = None
    filedialog = None

# Rich console setup
# We import rich here so the rest of the file can use `console` everywhere.

try:
    from rich.console import Console
    from rich.progress import (
        BarColumn,
        MofNCompleteColumn,
        Progress,
        SpinnerColumn,
        TextColumn,
        TimeRemainingColumn,
    )

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


def _stdout_supports_unicode() -> bool:
    """Return True when stdout can encode Rich output safely."""
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    try:
        "\u2500".encode(encoding)
        return True
    except (UnicodeEncodeError, LookupError):
        return False


_MARKUP_RE = re.compile(r"\[/?[a-zA-Z0-9_#][a-zA-Z0-9 _#]*\]")


def _strip_markup(value: str) -> str:
    """Remove Rich-style [tag]...[/tag] markup so plain consoles stay readable."""
    return _MARKUP_RE.sub("", value)


if RICH_AVAILABLE and _stdout_supports_unicode():
    console = Console()
else:
    RICH_AVAILABLE = False

    class _FallbackConsole:
        @staticmethod
        def print(*args, **kwargs):
            kwargs.pop("style", None)
            kwargs.pop("highlight", None)
            stripped = tuple(
                _strip_markup(arg) if isinstance(arg, str) else arg for arg in args
            )
            print(*stripped, **kwargs)

        @staticmethod
        def rule(title=""):
            print(f"\n{'-' * 20} {_strip_markup(title)} {'-' * 20}\n")

    console = _FallbackConsole()


def _read_version() -> str:
    """Read the VERSION file bundled next to the script/executable."""
    base = getattr(sys, "_MEIPASS", None) or os.path.dirname(
        os.path.abspath(sys.executable if getattr(sys, "frozen", False) else __file__)
    )
    try:
        with open(os.path.join(base, "VERSION"), encoding="utf-8") as f:
            return f.read().strip() or "dev"
    except OSError:
        return "dev"


VERSION = _read_version()


def format_duration(seconds: float) -> str:
    """Render elapsed time in a compact human-friendly format."""
    if seconds < 60:
        return f"{seconds:.2f}s"
    total_seconds = int(round(seconds))
    minutes, secs = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes}m {secs:02d}s"
    return f"{minutes}m {secs:02d}s"


def format_rate(count: int, seconds: float) -> str:
    """Render a compact images-per-second value."""
    if count <= 0 or seconds <= 0:
        return "n/a"
    return f"{count / seconds:.1f}/s"


# Database scanning

def get_db_files(edopro_path: str) -> list[str]:
    """Find card DBs in the EDOPro root, expansions/, and repository delta folders."""
    dbs: list[str] = []
    root_db = os.path.join(edopro_path, "cards.cdb")
    if os.path.exists(root_db):
        dbs.append(root_db)

    exp_path = os.path.join(edopro_path, "expansions")
    if os.path.isdir(exp_path):
        for filename in sorted(os.listdir(exp_path)):
            if filename.endswith(".cdb"):
                dbs.append(os.path.join(exp_path, filename))

    repo_path = os.path.join(edopro_path, "repositories")
    if os.path.isdir(repo_path):
        for current_root, dirnames, filenames in os.walk(repo_path):
            dirnames.sort()
            for filename in sorted(filenames):
                if filename.endswith(".delta.cdb"):
                    dbs.append(os.path.join(current_root, filename))
    return dbs


def normalize_edopro_path(path: str) -> str:
    """Trim quotes and expand user input into an absolute folder path."""
    cleaned = path.strip().strip('"')
    if sys.platform == "win32" and (
        cleaned.startswith("\\\\")
        or (len(cleaned) >= 2 and cleaned[1] == ":")
        or "\\" in cleaned
    ):
        return ntpath.abspath(ntpath.expanduser(cleaned))
    return os.path.abspath(os.path.expanduser(cleaned))


def browse_for_edopro_path_with_powershell(initial_dir: str) -> tuple[str | None, bool]:
    """Open a Windows folder picker via PowerShell when Tk is unavailable."""
    if sys.platform != "win32":
        return None, False

    start_dir = initial_dir if os.path.isdir(initial_dir) else os.path.expanduser("~")
    script = """
Add-Type -AssemblyName System.Windows.Forms
$dialog = New-Object System.Windows.Forms.FolderBrowserDialog
$dialog.Description = 'Select your EDOPro folder'
$dialog.UseDescriptionForTitle = $true
$dialog.SelectedPath = $env:EDOPRO_INITIAL_DIR
if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    Write-Output $dialog.SelectedPath
}
""".strip()

    try:
        result = subprocess.run(
            [
                "powershell.exe",
                "-NoLogo",
                "-NoProfile",
                "-STA",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                script,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env={**os.environ, "EDOPRO_INITIAL_DIR": start_dir},
            timeout=120,
            check=False,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return None, False

    if result.returncode != 0:
        return None, False

    selected = result.stdout.strip()
    if not selected:
        return None, True
    return normalize_edopro_path(selected), True


def browse_for_edopro_path(initial_dir: str) -> tuple[str | None, bool]:
    """Open a Windows folder picker. Returns (path, used_dialog)."""
    selected, used_dialog = browse_for_edopro_path_with_powershell(initial_dir)
    if used_dialog:
        return selected, True

    if sys.platform != "win32" or tk is None or filedialog is None:
        return None, False

    root = None
    try:
        start_dir = initial_dir if os.path.isdir(initial_dir) else os.path.expanduser("~")
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        root.update_idletasks()
        selected = filedialog.askdirectory(
            parent=root,
            initialdir=start_dir,
            title="Select your EDOPro folder",
            mustexist=True,
        )
        if not selected:
            return None, True
        return normalize_edopro_path(selected), True
    except Exception:
        return None, False
    finally:
        if root is not None:
            with contextlib.suppress(Exception):
                root.destroy()


def read_edopro_path_from_console() -> str | None:
    """Read an EDOPro folder path from stdin."""
    try:
        entered = input("EDOPro folder path: ").strip()
    except EOFError:
        entered = ""
    if not entered:
        return None
    return normalize_edopro_path(entered)


def prompt_for_edopro_path(cfg: Config) -> list[str] | None:
    """Prompt until the user enters a valid EDOPro folder or cancels."""
    checked_path = os.path.abspath(cfg.edopro_path)
    console.print(f"[yellow]No .cdb files found in:[/yellow] [bold]{checked_path}[/bold]")

    if sys.platform == "win32":
        console.print("Select your EDOPro folder in the window that opens. Cancel to quit.")
    else:
        console.print("Enter your EDOPro folder path. Leave it blank to quit.")

    warned_about_fallback = False
    while True:
        candidate: str | None
        if sys.platform == "win32":
            candidate, used_dialog = browse_for_edopro_path(cfg.edopro_path)
            if used_dialog:
                if not candidate:
                    console.print("[yellow]No folder selected. Exiting.[/yellow]")
                    return None
            else:
                if not warned_about_fallback:
                    console.print(
                        "[yellow]Windows folder picker unavailable. "
                        "Enter the path manually instead.[/yellow]"
                    )
                    warned_about_fallback = True
                candidate = read_edopro_path_from_console()
                if not candidate:
                    console.print("[yellow]No folder entered. Exiting.[/yellow]")
                    return None
        else:
            candidate = read_edopro_path_from_console()
            if not candidate:
                console.print("[yellow]No folder entered. Exiting.[/yellow]")
                return None

        dbs = get_db_files(candidate)
        if dbs:
            saved = cfg.set_edopro_path(candidate, save=True)
            console.print(
                f"[green]Using EDOPro folder:[/green] [bold]{cfg.edopro_path}[/bold]"
            )
            if not saved:
                console.print(
                    f"[yellow]Could not save settings to "
                    f"{os.path.abspath(cfg.config_path)}.[/yellow]"
                )
            return dbs

        console.print(
            "[yellow]That folder does not look like EDOPro. It needs cards.cdb, "
            "expansions/*.cdb, or repositories/**/*.delta.cdb.[/yellow]"
        )


def scan_databases(db_files: list[str]) -> tuple[dict[int, str], dict[str, list[int]], set[int]]:
    """
    Read every .cdb and return:

      id_to_name       - card_id -> card name (every card we know about)
      name_to_official - name -> official ids (IDs < 100,000,000 only)
      rush_ids         - card IDs that came from Rush Duel databases
    """
    id_to_name: dict[int, str] = {}
    name_to_official: dict[str, list[int]] = {}
    rush_ids: set[int] = set()

    for db in db_files:
        # Skip empty placeholder files (EDOPro ships a 0-byte cards.cdb)
        if os.path.getsize(db) == 0:
            continue
        is_rush = "rush" in os.path.basename(db).lower()
        conn = None
        try:
            conn = sqlite3.connect(db)
            cursor = conn.execute(
                "SELECT d.id, t.name "
                "FROM datas d INNER JOIN texts t ON d.id = t.id "
                "ORDER BY d.id"
            )
            for card_id, name in cursor.fetchall():
                id_to_name[card_id] = name
                if is_rush:
                    rush_ids.add(card_id)
                if card_id < 100_000_000:
                    official_ids = name_to_official.setdefault(name, [])
                    if card_id not in official_ids:
                        official_ids.append(card_id)
        except sqlite3.Error as exc:
            console.print(f"[yellow]Error reading {db}: {exc}[/yellow]")
        finally:
            if conn is not None:
                conn.close()

    for official_ids in name_to_official.values():
        official_ids.sort()

    return id_to_name, name_to_official, rush_ids


# Name matching

def find_official_match(
    name: str,
    name_to_official: dict[str, list[int]],
    suffixes: list[str],
    quiet: bool = False,
) -> tuple[list[int], bool, bool]:
    """Try to resolve a card name to one or more official Konami IDs.

    Returns (official_ids, is_pre_errata_miss, is_suffix_match).
    is_suffix_match is True when matches came from stripping a GOAT/Pre-Errata
    suffix rather than a direct name lookup.
    """
    pre_errata_miss = False

    for suffix in suffixes:
        if name.endswith(suffix):
            clean = name[: -len(suffix)]
            if clean in name_to_official:
                return name_to_official[clean], False, True
            if "Pre-Errata" in suffix:
                pre_errata_miss = True
                if not quiet:
                    console.print(
                        f'[dim]Pre-Errata lookup miss: "{clean}" (from "{name}")[/dim]'
                    )

    return name_to_official.get(name, []), pre_errata_miss, False


def load_manual_map(path: str) -> dict[str, str]:
    """Load built-in overrides, merged with the optional manual_map.json file.

    Keys beginning with "_" are treated as inline documentation and skipped, so
    users can keep comment fields in the JSON without polluting the override map.
    """
    result = dict(BUILTIN_MANUAL_MAP)
    if not os.path.exists(path):
        return result
    try:
        with open(path, encoding="utf-8") as file_obj:
            raw = json.load(file_obj)
    except (json.JSONDecodeError, OSError):
        return result
    if isinstance(raw, dict):
        result.update(
            {k: v for k, v in raw.items() if isinstance(k, str) and not k.startswith("_")}
        )
    return result


# Download logic with retries

class DownloadStats:
    """Counters for the current sync run."""

    def __init__(self, rush_ids: set[int] | None = None):
        self.ok_hd = 0
        self.ok_mapped = 0
        self.ok_fallback = 0
        self.official_backup = 0
        self.official_ok = 0
        self.skipped = 0
        self.failed = 0
        self.failed_cards: list[tuple[int, str]] = []
        self.unexpected_errors: list[tuple[int, str, str]] = []
        self._rush_ids: set[int] = rush_ids or set()

    @property
    def total_ok(self) -> int:
        return self.ok_hd + self.ok_mapped + self.ok_fallback

    @property
    def rush_failures(self) -> int:
        return sum(1 for cid, _ in self.failed_cards if cid in self._rush_ids)

    @property
    def unofficial_failures(self) -> int:
        return sum(
            1 for cid, _ in self.failed_cards
            if cid >= 100_000_000 and cid not in self._rush_ids
        )

    @property
    def official_failures(self) -> list[tuple[int, str]]:
        """Official non-Rush cards that failed — these are actual problems."""
        return [
            (cid, name) for cid, name in self.failed_cards
            if cid < 100_000_000 and cid not in self._rush_ids
        ]

    def record_success(self, card_id: int, counter_name: str) -> None:
        setattr(self, counter_name, getattr(self, counter_name) + 1)
        if card_id < 100_000_000:
            self.official_ok += 1
            if counter_name == "ok_fallback":
                self.official_backup += 1

    def record_failure(self, card_id: int, name: str) -> None:
        self.failed += 1
        self.failed_cards.append((card_id, name))

    def record_unexpected_error(self, card_id: int, name: str, exc: BaseException) -> None:
        self.unexpected_errors.append((card_id, name, f"{type(exc).__name__}: {exc}"))


async def _try_download(
    session: aiohttp.ClientSession,
    url: str,
    filepath: str,
    timeout: aiohttp.ClientTimeout,
    max_retries: int,
) -> bool:
    """
    Attempt to GET `url` and save to `filepath`.
    Retries up to `max_retries` times with exponential backoff.
    """
    tmp_path = f"{filepath}.part"
    for attempt in range(1, max_retries + 1):
        try:
            async with session.get(url, timeout=timeout) as resp:
                if resp.status == 200:
                    content = await resp.read()
                    if len(content) < 512:
                        if attempt >= max_retries:
                            return False
                    else:
                        with open(tmp_path, "wb") as file_obj:
                            file_obj.write(content)
                        os.replace(tmp_path, filepath)
                        return True
                elif resp.status == 404:
                    return False
        except (TimeoutError, aiohttp.ClientError):
            pass
        except OSError as exc:
            console.print(f"[red]Cannot write to {filepath}: {exc}[/red]")
            _remove_quietly(tmp_path)
            return False

        if attempt < max_retries:
            await asyncio.sleep(2 ** (attempt - 1))

    _remove_quietly(tmp_path)
    return False


def _remove_quietly(path: str) -> None:
    """Delete a file if present, swallowing any errors."""
    with contextlib.suppress(OSError):
        os.remove(path)


async def download_card(
    session: aiohttp.ClientSession,
    card_id: int,
    name: str,
    official_matches: list[int],
    manual_match: str | None,
    is_pre_errata_miss: bool,
    is_suffix_match: bool,
    cfg: Config,
    stats: DownloadStats,
    progress=None,
    task_id=None,
) -> None:
    """Download a single card image using a simple waterfall."""
    filepath = os.path.join(cfg.pics_path, f"{card_id}.jpg")

    if not cfg.force and os.path.exists(filepath):
        stats.skipped += 1
        if progress and task_id is not None:
            progress.advance(task_id)
        return

    official_source = cfg.sources["official"]
    timeout = aiohttp.ClientTimeout(total=cfg.timeout)

    # Build download candidates in priority order
    candidates: list[tuple[str, str]] = []

    # 1. Manual override
    if manual_match:
        candidates.append(("manual-map", f"{official_source}/{manual_match}.jpg"))

    # 2. Try the card's own ID on YGOProDeck (official cards only)
    if card_id < 100_000_000:
        candidates.append(("direct-id", f"{official_source}/{card_id}.jpg"))

    # 3. For GOAT/Pre-Errata suffix cards, try the base card's official IDs
    if is_suffix_match:
        for official_id in official_matches:
            if official_id != card_id:
                candidates.append(("name-match", f"{official_source}/{official_id}.jpg"))

    # 4. Pre-Errata offset fallback (card_id - 10)
    if is_pre_errata_miss and card_id >= 10:
        offset_id = card_id - 10
        if not any(url.endswith(f"/{offset_id}.jpg") for _, url in candidates):
            candidates.append(("pre-errata-offset", f"{official_source}/{offset_id}.jpg"))

    if cfg.dry_run:
        tag = candidates[0][0] if candidates else "fallback"
        console.print(f"  [dim]Would download:[/dim] {name} ({card_id}) via {tag}")
        if progress and task_id is not None:
            progress.advance(task_id)
        return

    for reason, url in candidates:
        if await _try_download(session, url, filepath, timeout, cfg.max_retries):
            stats.record_success(card_id, "ok_mapped" if reason == "manual-map" else "ok_hd")
            if progress and task_id is not None:
                progress.advance(task_id)
            return

    # 5. ProjectIgnis backup
    if "backup" in cfg.sources:
        url = f"{cfg.sources['backup']}/{card_id}.jpg"
        if await _try_download(session, url, filepath, timeout, cfg.max_retries):
            stats.record_success(card_id, "ok_fallback")
            if progress and task_id is not None:
                progress.advance(task_id)
            return

    stats.record_failure(card_id, name)
    if progress and task_id is not None:
        progress.advance(task_id)


# Summary

def _build_summary_rows(
    stats: DownloadStats, cfg: Config, runtime_seconds: float,
) -> list[tuple[str, str, str | None]]:
    """Build the rows shown in the terminal summary."""
    rows: list[tuple[str, str, str | None]] = []
    if cfg.dry_run:
        rows.append(("Would download", f"{max(stats.total_ok + stats.failed, 0):,}", None))
        if stats.skipped:
            rows.append(("Already on disk", f"{stats.skipped:,}", "dim"))
    else:
        rows.append(("Downloaded", f"{stats.total_ok:,}", "green"))
        if stats.official_backup:
            rows.append(("Backup art", f"{stats.official_backup:,}", "cyan"))
        if stats.skipped:
            rows.append(("Already existed", f"{stats.skipped:,}", "dim"))
        if stats.failed:
            rows.append(("Unavailable", f"{stats.failed:,}", "yellow"))
            rush = stats.rush_failures
            unofficial = stats.unofficial_failures
            official = stats.official_failures
            if rush:
                rows.append(("  Rush Duel", f"{rush:,}", "dim"))
            if unofficial:
                rows.append(("  Anime / fan-made", f"{unofficial:,}", "dim"))
            if official:
                rows.append(("  Official", f"{len(official):,}", "dim"))
        rows.append(("Time", format_duration(runtime_seconds), None))
        rows.append(("Speed", format_rate(stats.total_ok, runtime_seconds), None))
    return rows


def _write_report(stats: DownloadStats, cfg: Config, runtime_seconds: float) -> None:
    """Write a sync report file with grouped failure categories."""
    now = datetime.now()
    timestamp = now.strftime("%Y%m%d-%H%M%S")
    report_path = os.path.join(
        os.path.dirname(cfg.config_path), f"sync-report-{timestamp}.txt",
    )
    try:
        with open(report_path, "w", encoding="utf-8") as f:
            f.write("EDOPro HD Sync Report\n")
            f.write("=" * 40 + "\n")
            f.write(f"Generated: {now.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Runtime:   {format_duration(runtime_seconds)}\n")
            f.write(f"Speed:     {format_rate(stats.total_ok, runtime_seconds)}\n")
            f.write(f"\nDownloaded:      {stats.total_ok:,}\n")
            if stats.official_backup:
                f.write(f"Backup art:      {stats.official_backup:,}\n")
            if stats.skipped:
                f.write(f"Already existed: {stats.skipped:,}\n")
            f.write(f"Unavailable:     {stats.failed:,}\n")
            f.write(f"Images folder:   {os.path.abspath(cfg.pics_path)}\n")

            if stats.failed_cards:
                f.write(f"\n{'=' * 40}\n")
                f.write("Unavailable Breakdown\n")
                f.write(f"{'=' * 40}\n")
                rush = stats.rush_failures
                unofficial = stats.unofficial_failures
                official = stats.official_failures
                if rush:
                    f.write(f"  Rush Duel cards:       {rush:,}\n")
                if unofficial:
                    f.write(f"  Anime / fan-made:      {unofficial:,}\n")
                if official:
                    f.write(f"  Official cards:        {len(official):,}\n")
                    f.write(
                        "\nOfficial cards that could not be found:\n"
                    )
                    f.write("-" * 60 + "\n")
                    for card_id, card_name in official:
                        f.write(f"  {card_id}\t{card_name}\n")
            else:
                f.write("\nAll cards downloaded successfully.\n")
        console.print(f"[dim]Report saved to: {report_path}[/dim]")
    except OSError as exc:
        console.print(f"[yellow]Could not write sync report: {exc}[/yellow]")


def print_summary(
    stats: DownloadStats, cfg: Config, runtime_seconds: float,
    save_report: bool = False,
):
    """Print a clean terminal summary and optionally save a report."""
    rows = _build_summary_rows(stats, cfg, runtime_seconds)
    label_width = max(len(label) for label, _, _ in rows)

    console.print()
    console.rule("[bold]Sync Complete[/bold]")
    for label, value, style in rows:
        formatted = f"{value:>12}"
        if style:
            console.print(f"  {label:<{label_width}} [{style}]{formatted}[/{style}]")
        else:
            console.print(f"  {label:<{label_width}} {formatted}")
    console.rule()

    if cfg.dry_run:
        return

    if save_report:
        _write_report(stats, cfg, runtime_seconds)


# Main

def _prompt_yes_no(question: str, default: bool = False) -> bool:
    """Prompt for a yes/no answer, returning the default on blank input."""
    suffix = "[Y/n]" if default else "[y/N]"
    try:
        answer = input(f"{question} {suffix}: ").strip().lower()
    except EOFError:
        return default
    if not answer:
        return default
    if answer in {"y", "yes"}:
        return True
    if answer in {"n", "no"}:
        return False
    return default


def run_health_check(cfg: Config) -> bool:
    """Run quick offline checks for suffix-stripping logic."""
    suffixes = DEFAULTS["suffixes_to_strip"]
    name_to_official = {
        "Dark Magician": [36996508, 46986414],
        "Blue-Eyes White Dragon": [89631136, 89631139],
    }
    checks: list[tuple[bool, str]] = []

    # Check that suffix stripping resolves Pre-Errata cards to their base
    official_ids, is_pre_errata_miss, is_suffix_match = find_official_match(
        "Dark Magician (Pre-Errata)", name_to_official, suffixes, quiet=True,
    )
    checks.append((
        46986414 in official_ids and not is_pre_errata_miss and is_suffix_match,
        "Dark Magician (Pre-Errata): suffix stripping resolves to base art",
    ))

    # Check that GOAT suffix stripping works
    official_ids, is_pre_errata_miss, is_suffix_match = find_official_match(
        "Blue-Eyes White Dragon GOAT", name_to_official, suffixes, quiet=True,
    )
    checks.append((
        89631136 in official_ids and not is_pre_errata_miss and is_suffix_match,
        "Blue-Eyes White Dragon GOAT: suffix stripping resolves to base art",
    ))

    # Check that Pre-Errata miss is flagged when base name is absent
    official_ids, is_pre_errata_miss, is_suffix_match = find_official_match(
        "Summoned Skull (Pre-Errata)", name_to_official, suffixes, quiet=True,
    )
    checks.append((
        is_pre_errata_miss and not is_suffix_match,
        "Summoned Skull (Pre-Errata): flags pre-errata miss when base is absent",
    ))

    console.print()
    console.rule("[bold]Health Check[/bold]")

    for passed, label in checks:
        prefix = "[green]OK[/green]" if passed else "[red]FAIL[/red]"
        console.print(f"  {prefix} {label}")

    passed = all(ok for ok, _ in checks)
    if passed:
        console.print("\n[bold green]All checks passed.[/bold green]")
    else:
        console.print(
            "\n[bold red]Health check failed — please review the messages above.[/bold red]"
        )
    return passed


async def run(cfg: Config):
    started_at = perf_counter()

    console.print(f"[bold cyan]EDOPro HD Sync[/bold cyan] [dim]v{VERSION}[/dim]")

    if cfg.health_check:
        if not run_health_check(cfg):
            raise SystemExit(1)
        return

    dbs = get_db_files(cfg.edopro_path)
    if not dbs:
        dbs = prompt_for_edopro_path(cfg)
        if not dbs:
            return

    os.makedirs(cfg.pics_path, exist_ok=True)

    id_to_name, name_to_official, rush_ids = scan_databases(dbs)
    manual_map = load_manual_map(cfg.manual_map_file)
    console.print(f"[dim]Indexed {len(id_to_name):,} cards[/dim]")

    has_non_empty_db = any(
        os.path.isfile(db) and os.path.getsize(db) > 0 for db in dbs
    )
    if has_non_empty_db and not id_to_name:
        console.print(
            "[bold red]No cards found in the scanned databases. "
            "They may be corrupt or in an unexpected schema.[/bold red]"
        )
        raise SystemExit(1)

    if cfg.force:
        missing_ids = list(id_to_name.keys())
    else:
        missing_ids = [
            card_id
            for card_id in id_to_name
            if not os.path.exists(os.path.join(cfg.pics_path, f"{card_id}.jpg"))
        ]

    if not missing_ids:
        console.print("\n[bold green]All synced — nothing to download![/bold green]")
        return

    console.print(
        f"\n[bold yellow]This will download all {len(missing_ids):,} "
        "card images.[/bold yellow]"
    )

    # Ask about saving a report before starting (unless --save-report or --quiet).
    save_report_after = cfg.save_report
    if not cfg.dry_run and not cfg.save_report and not cfg.quiet:
        save_report_after = _prompt_yes_no("Save a sync report when finished?")

    # Pre-compute match info for every card to avoid redundant lookups in workers.
    card_match_info: dict[int, tuple[list[int], str | None, bool, bool]] = {}
    for card_id in missing_ids:
        name = id_to_name[card_id]
        official, is_pre_errata_miss, is_suffix_match = find_official_match(
            name, name_to_official, cfg.suffixes, quiet=True,
        )
        manual = manual_map.get(str(card_id))
        card_match_info[card_id] = (official, manual, is_pre_errata_miss, is_suffix_match)

    stats = DownloadStats(rush_ids=rush_ids)
    queue: asyncio.Queue[int] = asyncio.Queue()
    for card_id in missing_ids:
        queue.put_nowait(card_id)

    ssl_ctx = ssl.create_default_context(cafile=certifi.where())
    connector = aiohttp.TCPConnector(
        limit=cfg.concurrency,
        limit_per_host=min(cfg.concurrency, 25),
        enable_cleanup_closed=True,
        ssl=ssl_ctx,
    )

    async with aiohttp.ClientSession(connector=connector) as session:
        if not cfg.dry_run:
            try:
                test_timeout = aiohttp.ClientTimeout(total=8)
                async with session.get(
                    f"{cfg.sources['official']}/46986414.jpg",
                    timeout=test_timeout,
                ) as resp:
                    if resp.status != 200:
                        console.print(
                            f"[yellow]Image server returned HTTP {resp.status} — "
                            "downloads may fail[/yellow]"
                        )
            except Exception as exc:
                console.print(
                    f"[bold red]Cannot reach image server: {exc}\n"
                    "  Check your internet connection.[/bold red]"
                )

        def make_worker(progress=None, task_id=None):
            async def worker():
                while True:
                    try:
                        card_id = queue.get_nowait()
                    except asyncio.QueueEmpty:
                        return
                    name = id_to_name[card_id]
                    official, manual, is_pre_errata_miss, is_suffix_match = card_match_info[card_id]
                    try:
                        await download_card(
                            session,
                            card_id,
                            name,
                            official,
                            manual,
                            is_pre_errata_miss,
                            is_suffix_match,
                            cfg,
                            stats,
                            progress,
                            task_id,
                        )
                    except asyncio.CancelledError:
                        raise
                    except Exception as exc:
                        stats.record_failure(card_id, name)
                        stats.record_unexpected_error(card_id, name, exc)
                        if progress and task_id is not None:
                            progress.advance(task_id)

            return worker

        if RICH_AVAILABLE and not cfg.quiet:
            with Progress(
                SpinnerColumn(),
                TextColumn("[bold blue]{task.description}"),
                BarColumn(bar_width=40),
                MofNCompleteColumn(),
                TimeRemainingColumn(),
                console=console,
            ) as progress:
                task_id = progress.add_task("Syncing...", total=len(missing_ids))
                workers = [make_worker(progress, task_id)() for _ in range(cfg.concurrency)]
                await asyncio.gather(*workers)
        else:
            workers = [make_worker()() for _ in range(cfg.concurrency)]
            await asyncio.gather(*workers)

    print_summary(stats, cfg, perf_counter() - started_at, save_report_after)


def should_pause_before_exit(cfg: Config | None) -> bool:
    """Keep the bundled Windows app open so double-click runs are readable."""
    return (
        sys.platform == "win32"
        and getattr(sys, "frozen", False)
        and not (cfg and cfg.no_pause)
    )


def pause_before_exit(cfg: Config | None) -> None:
    """Wait for Enter before closing when the packaged Windows app finishes."""
    if not should_pause_before_exit(cfg):
        return
    with contextlib.suppress(EOFError):
        input("\nPress Enter to close this window...")


def _extract_exit_code(code) -> int:
    """Convert a SystemExit payload into a shell-friendly integer."""
    if code is None:
        return 0
    if isinstance(code, int):
        return code
    return 1


def main() -> int:
    cfg: Config | None = None
    exit_code = 0

    try:
        cfg = Config()

        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

        asyncio.run(run(cfg))
    except KeyboardInterrupt:
        exit_code = 130
        console.print("\n[yellow]Interrupted - partial progress is saved.[/yellow]")
    except SystemExit as exc:
        exit_code = _extract_exit_code(exc.code)
    except Exception as exc:
        exit_code = 1
        if getattr(sys, "frozen", False):
            console.print(f"\n[bold red]Unexpected error:[/bold red] {exc}")
        else:
            raise
    finally:
        pause_before_exit(cfg)

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
