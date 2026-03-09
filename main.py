"""
EDOPro HD Sync - Automatically download missing HD card artwork for EDOPro.

Improvements over the original:
  - Rich progress bars and color-coded console output
  - Automatic retries with exponential backoff on failed downloads
  - Configurable via config.json and CLI arguments
  - Detailed summary report at the end
"""

import asyncio
import json
import os
import sqlite3
import ssl
import subprocess
import sys
from datetime import datetime
from time import perf_counter

import aiohttp
import certifi

from config import Config

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
    except (LookupError, UnicodeEncodeError):
        return False
    return True


if RICH_AVAILABLE and _stdout_supports_unicode():
    console = Console()
else:
    RICH_AVAILABLE = False

    class _FallbackConsole:
        """Bare-minimum stand-in when rich is not installed."""

        @staticmethod
        def print(*args, **kwargs):
            kwargs.pop("style", None)
            kwargs.pop("highlight", None)
            print(*args, **kwargs)

        @staticmethod
        def rule(title=""):
            print(f"\n{'-' * 20} {title} {'-' * 20}\n")

    console = _FallbackConsole()


VERSION = "3.10.5"


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
            try:
                root.destroy()
            except Exception:
                pass


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
    console.print(
        f"[yellow]No .cdb files found in:[/yellow] [bold]{checked_path}[/bold]"
        if RICH_AVAILABLE
        else f"No .cdb files found in: {checked_path}"
    )

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
                    console.print(
                        "[yellow]No folder selected. Exiting.[/yellow]"
                        if RICH_AVAILABLE
                        else "No folder selected. Exiting."
                    )
                    return None
            else:
                if not warned_about_fallback:
                    console.print(
                        "[yellow]Windows folder picker unavailable. Enter the path manually instead.[/yellow]"
                        if RICH_AVAILABLE
                        else "Windows folder picker unavailable. Enter the path manually instead."
                    )
                    warned_about_fallback = True
                candidate = read_edopro_path_from_console()
                if not candidate:
                    console.print(
                        "[yellow]No folder entered. Exiting.[/yellow]"
                        if RICH_AVAILABLE
                        else "No folder entered. Exiting."
                    )
                    return None
        else:
            candidate = read_edopro_path_from_console()
            if not candidate:
                console.print(
                    "[yellow]No folder entered. Exiting.[/yellow]"
                    if RICH_AVAILABLE
                    else "No folder entered. Exiting."
                )
                return None

        dbs = get_db_files(candidate)
        if dbs:
            saved = cfg.set_edopro_path(candidate, save=True)
            console.print(
                f"[green]Using EDOPro folder:[/green] [bold]{cfg.edopro_path}[/bold]"
                if RICH_AVAILABLE
                else f"Using EDOPro folder: {cfg.edopro_path}"
            )
            if not saved:
                console.print(
                    f"[yellow]Could not save settings to {os.path.abspath(cfg.config_path)}.[/yellow]"
                    if RICH_AVAILABLE
                    else f"Could not save settings to {os.path.abspath(cfg.config_path)}."
                )
            return dbs

        console.print(
            "[yellow]That folder does not look like EDOPro. It needs cards.cdb, expansions/*.cdb, or repositories/**/*.delta.cdb.[/yellow]"
            if RICH_AVAILABLE
            else "That folder does not look like EDOPro. It needs cards.cdb, expansions/*.cdb, or repositories/**/*.delta.cdb."
        )


def scan_databases(db_files: list[str]) -> tuple[dict[int, str], dict[str, int]]:
    """
    Read every .cdb and return two mappings:

      id_to_name       - card_id -> card name (every card we know about)
      name_to_official - name -> official id (IDs < 100,000,000 only)
    """
    id_to_name: dict[int, str] = {}
    name_to_official: dict[str, int] = {}

    for db in db_files:
        # Skip empty placeholder files (EDOPro ships a 0-byte cards.cdb)
        if os.path.getsize(db) == 0:
            continue
        try:
            with sqlite3.connect(db) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT d.id, t.name "
                    "FROM datas d INNER JOIN texts t ON d.id = t.id"
                )
                for card_id, name in cursor.fetchall():
                    id_to_name[card_id] = name
                    if card_id < 100_000_000 and name not in name_to_official:
                        name_to_official[name] = card_id
        except sqlite3.Error as exc:
            console.print(
                f"[yellow]Error reading {db}: {exc}[/yellow]"
                if RICH_AVAILABLE
                else f"Error reading {db}: {exc}"
            )

    return id_to_name, name_to_official


# Name matching

def find_official_match(
    name: str,
    name_to_official: dict[str, int],
    suffixes: list[str],
) -> int | None:
    """Try to resolve a card name to its official Konami ID."""
    if name in name_to_official:
        return name_to_official[name]
    for suffix in suffixes:
        if name.endswith(suffix):
            clean = name[: -len(suffix)]
            if clean in name_to_official:
                return name_to_official[clean]
    return None


def load_manual_map(path: str) -> dict[str, str]:
    """Load the optional manual_map.json override file."""
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as file_obj:
            return json.load(file_obj)
    except (json.JSONDecodeError, OSError):
        return {}


# Download logic with retries

class DownloadStats:
    """Counters for the current sync run."""

    def __init__(self):
        self.ok_hd = 0
        self.ok_mapped = 0
        self.ok_fallback = 0
        self.skipped = 0
        self.failed = 0
        self.failed_cards: list[tuple[int, str]] = []

    @property
    def total_ok(self) -> int:
        return self.ok_hd + self.ok_mapped + self.ok_fallback


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
    for attempt in range(1, max_retries + 1):
        try:
            async with session.get(url, timeout=timeout) as resp:
                if resp.status == 200:
                    content = await resp.read()
                    if len(content) < 512:
                        if attempt >= max_retries:
                            return False
                    else:
                        with open(filepath, "wb") as file_obj:
                            file_obj.write(content)
                        return True
                elif resp.status == 404:
                    return False
        except (aiohttp.ClientError, asyncio.TimeoutError):
            pass
        except OSError as exc:
            console.print(
                f"[red]Cannot write to {filepath}: {exc}[/red]"
                if RICH_AVAILABLE
                else f"Cannot write to {filepath}: {exc}"
            )
            return False

        if attempt < max_retries:
            await asyncio.sleep(2 ** (attempt - 1))

    return False


async def download_card(
    session: aiohttp.ClientSession,
    card_id: int,
    name: str,
    official_match: int | None,
    manual_match: str | None,
    cfg: Config,
    stats: DownloadStats,
    progress=None,
    task_id=None,
) -> None:
    """Download a single card image using the 3-strategy waterfall."""
    filepath = os.path.join(cfg.pics_path, f"{card_id}.jpg")

    if not cfg.force and os.path.exists(filepath):
        stats.skipped += 1
        if progress and task_id is not None:
            progress.advance(task_id)
        return

    if cfg.dry_run:
        tag = "manual-map" if manual_match else ("hd-match" if official_match else "fallback")
        console.print(
            f"  [dim]Would download:[/dim] {name} ({card_id}) [{tag}]"
            if RICH_AVAILABLE
            else f"  Would download: {name} ({card_id}) [{tag}]"
        )
        if progress and task_id is not None:
            progress.advance(task_id)
        return

    timeout = aiohttp.ClientTimeout(total=cfg.timeout)

    if manual_match:
        url = f"{cfg.sources['official']}/{manual_match}.jpg"
        if await _try_download(session, url, filepath, timeout, cfg.max_retries):
            stats.ok_mapped += 1
            if progress and task_id is not None:
                progress.advance(task_id)
            return

    if official_match and official_match != card_id:
        url = f"{cfg.sources['official']}/{official_match}.jpg"
        if await _try_download(session, url, filepath, timeout, cfg.max_retries):
            stats.ok_hd += 1
            if progress and task_id is not None:
                progress.advance(task_id)
            return

    if card_id < 100_000_000:
        url = f"{cfg.sources['official']}/{card_id}.jpg"
        if await _try_download(session, url, filepath, timeout, cfg.max_retries):
            stats.ok_hd += 1
            if progress and task_id is not None:
                progress.advance(task_id)
            return

    if "backup" in cfg.sources:
        url = f"{cfg.sources['backup']}/{card_id}.jpg"
        if await _try_download(session, url, filepath, timeout, cfg.max_retries):
            stats.ok_fallback += 1
            if progress and task_id is not None:
                progress.advance(task_id)
            return

    stats.failed += 1
    stats.failed_cards.append((card_id, name))
    if progress and task_id is not None:
        progress.advance(task_id)


# Summary

def print_summary(stats: DownloadStats, total_missing: int, cfg: Config, runtime_seconds: float):
    """Print summary lines and optionally write report/log files."""
    attempted_downloads = stats.total_ok + stats.failed
    success_rate = "n/a"
    if attempted_downloads:
        success_rate = f"{(stats.total_ok / attempted_downloads) * 100:.1f}%"

    summary_rows: list[tuple[str, str, str | None]] = [("Missing images", f"{total_missing:,}", None)]
    if cfg.dry_run:
        summary_rows.append(("Would download", f"{max(total_missing - stats.skipped, 0):,}", None))
        summary_rows.append(("Already on disk", f"{stats.skipped:,}", "dim"))
    else:
        summary_rows.append(("Downloaded", f"{stats.total_ok:,}", "green"))
        summary_rows.append(("Unavailable", f"{stats.failed:,}", "red" if stats.failed else "dim"))
        summary_rows.append(("Already existed", f"{stats.skipped:,}", "dim"))
        summary_rows.append(("Success rate", success_rate, "green" if stats.total_ok else "dim"))
        summary_rows.append(("Avg speed", format_rate(stats.total_ok, runtime_seconds), "dim"))
        summary_rows.append(("HD artwork", f"{stats.ok_hd:,}", "green"))
        summary_rows.append(("Manual mapped", f"{stats.ok_mapped:,}", "green"))
        summary_rows.append(("Low-res fallback", f"{stats.ok_fallback:,}", "yellow"))

    if RICH_AVAILABLE:
        console.print()
        console.rule("[bold]Sync Summary[/bold]")
        for label, value, style in summary_rows:
            formatted = f"{value:>12}"
            if style:
                console.print(f"  {label:<18} [{style}]{formatted}[/{style}]")
            else:
                console.print(f"  {label:<18} {formatted}")
        console.print(f"  {'Images folder':<18} [bold]{os.path.abspath(cfg.pics_path)}[/bold]")
        if stats.failed_cards and not cfg.quiet:
            console.print(f"\n[red]Failed cards ({len(stats.failed_cards)}):[/red]")
            for card_id, card_name in stats.failed_cards[:20]:
                console.print(f"  [dim]{card_id}[/dim] - {card_name}")
            if len(stats.failed_cards) > 20:
                console.print(f"  ... and {len(stats.failed_cards) - 20} more.")
        console.rule()
    else:
        sep = "-" * 38
        print(f"\n{sep}")
        print("  Sync Summary")
        print(sep)
        for label, value, _ in summary_rows:
            print(f"  {label:<18} {value:>12}")
        print(f"  {'Images folder':<18} {os.path.abspath(cfg.pics_path)}")
        print(sep)

    if stats.failed_cards and not cfg.dry_run:
        log_path = os.path.join(cfg.edopro_path, "sync-failed.txt")
        try:
            with open(log_path, "w", encoding="utf-8") as file_obj:
                file_obj.write(
                    f"EDOPro HD Sync - cards with no artwork found ({len(stats.failed_cards)} total)\n"
                )
                file_obj.write(
                    "These are usually custom or fan-made cards with no official artwork source.\n"
                )
                file_obj.write("-" * 60 + "\n")
                for card_id, card_name in stats.failed_cards:
                    file_obj.write(f"{card_id}\t{card_name}\n")
            console.print(
                f"[dim]Failed card list saved to: {log_path}[/dim]"
                if RICH_AVAILABLE
                else f"Failed card list saved to: {log_path}"
            )
        except OSError:
            pass

    if cfg.save_report:
        now = datetime.now()
        report_path = os.path.join(
            cfg.edopro_path,
            f"sync-report-{now.strftime('%Y%m%d-%H%M%S')}.txt",
        )
        try:
            with open(report_path, "w", encoding="utf-8") as file_obj:
                file_obj.write("EDOPro HD Sync Report\n")
                file_obj.write("=" * 40 + "\n")
                file_obj.write(f"Generated: {now.strftime('%Y-%m-%d %H:%M:%S')}\n")
                file_obj.write(f"Mode: {'Dry run (preview only)' if cfg.dry_run else 'Download'}\n")
                file_obj.write(f"Runtime: {format_duration(runtime_seconds)}\n")
                file_obj.write("\nSummary\n")
                for label, value, _ in summary_rows:
                    file_obj.write(f"- {label}: {value}\n")
                file_obj.write(f"- Images folder: {os.path.abspath(cfg.pics_path)}\n")
                if stats.failed_cards:
                    file_obj.write("\nFailed cards\n")
                    for card_id, card_name in stats.failed_cards:
                        file_obj.write(f"{card_id}\t{card_name}\n")
            console.print(
                f"[dim]Summary report saved to: {report_path}[/dim]"
                if RICH_AVAILABLE
                else f"Summary report saved to: {report_path}"
            )
        except OSError as exc:
            console.print(
                f"[yellow]Could not write summary report: {exc}[/yellow]"
                if RICH_AVAILABLE
                else f"Could not write summary report: {exc}"
            )


# Main

async def run(cfg: Config):
    started_at = perf_counter()
    try:
        if RICH_AVAILABLE:
            console.print(f"[bold cyan]EDOPro HD Sync[/bold cyan] [dim]v{VERSION}[/dim]")
            console.print("[dim]Automatic HD artwork downloader for EDOPro[/dim]")
        else:
            console.print(f"EDOPro HD Sync v{VERSION}")
            console.print("Automatic HD artwork downloader for EDOPro")

        dbs = get_db_files(cfg.edopro_path)
        if not dbs:
            dbs = prompt_for_edopro_path(cfg)
            if not dbs:
                return

        os.makedirs(cfg.pics_path, exist_ok=True)
        abs_pics = os.path.abspath(cfg.pics_path)
        console.print(
            f"[dim]Saving images to:[/dim] [bold]{abs_pics}[/bold]"
            if RICH_AVAILABLE
            else f"Saving images to: {abs_pics}"
        )

        console.print(
            f"[dim]Found {len(dbs)} database(s): {', '.join(os.path.basename(db) for db in dbs)}[/dim]"
            if RICH_AVAILABLE
            else f"Found {len(dbs)} database(s): {', '.join(os.path.basename(db) for db in dbs)}"
        )

        id_to_name, name_to_official = scan_databases(dbs)
        manual_map = load_manual_map(cfg.manual_map_file)
        console.print(
            f"[dim]Indexed {len(id_to_name):,} cards  |  {len(name_to_official):,} HD candidates  |  {len(manual_map)} manual overrides[/dim]"
            if RICH_AVAILABLE
            else f"Indexed {len(id_to_name):,} cards  |  {len(name_to_official):,} HD candidates  |  {len(manual_map)} manual overrides"
        )

        if cfg.force:
            missing_ids = list(id_to_name.keys())
        else:
            missing_ids = [
                card_id
                for card_id in id_to_name
                if not os.path.exists(os.path.join(cfg.pics_path, f"{card_id}.jpg"))
            ]

        if not missing_ids:
            console.print(
                "\n[bold green]All synced - nothing to download![/bold green]"
                if RICH_AVAILABLE
                else "\nAll synced - nothing to download!"
            )
            return

        console.print(
            f"\n[bold]{'Previewing' if cfg.dry_run else 'Downloading'} {len(missing_ids):,} missing images[/bold]  "
            f"[dim](concurrency={cfg.concurrency}, retries={cfg.max_retries})[/dim]"
            if RICH_AVAILABLE
            else f"\n{'Previewing' if cfg.dry_run else 'Downloading'} {len(missing_ids):,} missing images  "
            f"(concurrency={cfg.concurrency}, retries={cfg.max_retries})"
        )

        stats = DownloadStats()
        queue: asyncio.Queue[int] = asyncio.Queue()
        for card_id in missing_ids:
            queue.put_nowait(card_id)

        ssl_ctx = ssl.create_default_context(cafile=certifi.where())
        connector = aiohttp.TCPConnector(
            limit=cfg.concurrency,
            enable_cleanup_closed=True,
            ssl=ssl_ctx,
        )

        async with aiohttp.ClientSession(connector=connector) as session:
            try:
                test_timeout = aiohttp.ClientTimeout(total=8)
                async with session.get(
                    f"{cfg.sources['official']}/46986414.jpg",
                    timeout=test_timeout,
                ) as resp:
                    if resp.status == 200:
                        console.print(
                            "[dim green]Connected to image server[/dim green]"
                            if RICH_AVAILABLE
                            else "Connected to image server"
                        )
                    else:
                        console.print(
                            f"[yellow]Image server returned HTTP {resp.status} - downloads may fail[/yellow]"
                            if RICH_AVAILABLE
                            else f"Image server returned HTTP {resp.status}"
                        )
            except Exception as exc:
                console.print(
                    f"[bold red]Cannot reach image server: {exc}\n"
                    "  Check your internet connection - downloads will fail.[/bold red]"
                    if RICH_AVAILABLE
                    else f"Cannot reach image server: {exc}"
                )

            def make_worker(progress=None, task_id=None):
                async def worker():
                    while True:
                        try:
                            card_id = queue.get_nowait()
                        except asyncio.QueueEmpty:
                            return
                        name = id_to_name[card_id]
                        official = find_official_match(name, name_to_official, cfg.suffixes)
                        manual = manual_map.get(str(card_id))
                        await download_card(
                            session,
                            card_id,
                            name,
                            official,
                            manual,
                            cfg,
                            stats,
                            progress,
                            task_id,
                        )

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

        print_summary(stats, len(missing_ids), cfg, perf_counter() - started_at)
    finally:
        elapsed = perf_counter() - started_at
        console.print(
            f"[bold]Total runtime:[/bold] {format_duration(elapsed)}"
            if RICH_AVAILABLE
            else f"Total runtime: {format_duration(elapsed)}"
        )


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
    try:
        input("\nPress Enter to close this window...")
    except EOFError:
        pass


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
        console.print(
            "\n[yellow]Interrupted - partial progress is saved.[/yellow]"
            if RICH_AVAILABLE
            else "\nInterrupted - partial progress is saved."
        )
    except SystemExit as exc:
        exit_code = _extract_exit_code(exc.code)
    except Exception as exc:
        exit_code = 1
        if getattr(sys, "frozen", False):
            console.print(
                f"\n[bold red]Unexpected error:[/bold red] {exc}"
                if RICH_AVAILABLE
                else f"\nUnexpected error: {exc}"
            )
        else:
            raise
    finally:
        pause_before_exit(cfg)

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
