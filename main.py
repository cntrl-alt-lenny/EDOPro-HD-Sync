"""
EDOPro HD Sync — Automatically download missing HD card artwork for EDOPro.

Improvements over the original:
  • Rich progress bars and colour-coded console output
  • Automatic retries with exponential backoff on failed downloads
  • Configurable via config.json and CLI arguments
  • Detailed summary report at the end
"""

import os
import ssl
import sys
import json
import sqlite3
import asyncio
from datetime import datetime
from time import perf_counter
import aiohttp
import certifi

from config import Config

# ── Rich console setup ────────────────────────────────────────────────────────
# We import rich here so the rest of the file can use `console` everywhere.

try:
    from rich.console import Console
    from rich.progress import (
        Progress,
        BarColumn,
        TextColumn,
        MofNCompleteColumn,
        TimeRemainingColumn,
        SpinnerColumn,
    )

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

# Thin wrapper so the code never crashes if rich is missing.
if RICH_AVAILABLE:
    console = Console()
else:
    class _FallbackConsole:
        """Bare-minimum stand-in when rich is not installed."""
        @staticmethod
        def print(*args, **kwargs):
            kwargs.pop("style", None)
            kwargs.pop("highlight", None)
            print(*args, **kwargs)

        @staticmethod
        def rule(title=""):
            print(f"\n{'─'*20} {title} {'─'*20}\n")

    console = _FallbackConsole()

VERSION = "3.8.1"


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


# ── Database scanning ─────────────────────────────────────────────────────────

def get_db_files(edopro_path: str) -> list[str]:
    """Find every .cdb file in the EDOPro root and expansions/ folder."""
    dbs: list[str] = []
    root_db = os.path.join(edopro_path, "cards.cdb")
    if os.path.exists(root_db):
        dbs.append(root_db)

    exp_path = os.path.join(edopro_path, "expansions")
    if os.path.isdir(exp_path):
        for f in sorted(os.listdir(exp_path)):
            if f.endswith(".cdb"):
                dbs.append(os.path.join(exp_path, f))
    return dbs


def normalize_edopro_path(path: str) -> str:
    """Trim quotes and expand user input into an absolute folder path."""
    cleaned = path.strip().strip('"')
    return os.path.abspath(os.path.expanduser(cleaned))



def prompt_for_edopro_path(cfg: Config) -> list[str] | None:
    """Prompt until the user enters a valid EDOPro folder or cancels."""
    checked_path = os.path.abspath(cfg.edopro_path)
    console.print(
        f"[yellow]No .cdb files found in:[/yellow] [bold]{checked_path}[/bold]"
        if RICH_AVAILABLE
        else f"No .cdb files found in: {checked_path}"
    )
    console.print("Enter your EDOPro folder path. Leave it blank to quit.")

    while True:
        try:
            entered = input("EDOPro folder path: ").strip()
        except EOFError:
            entered = ""

        if not entered:
            console.print(
                "[yellow]No folder entered. Exiting.[/yellow]"
                if RICH_AVAILABLE
                else "No folder entered. Exiting."
            )
            return None

        candidate = normalize_edopro_path(entered)
        dbs = get_db_files(candidate)
        if dbs:
            saved = cfg.set_edopro_path(candidate, save=True)
            console.print(
                f"[green]Using EDOPro folder:[/green] [bold]{cfg.edopro_path}[/bold]"
                if RICH_AVAILABLE
                else f"Using EDOPro folder: {cfg.edopro_path}"
            )
            if saved:
                console.print(
                    f"[dim]Saved to {os.path.abspath(cfg.config_path)}[/dim]"
                    if RICH_AVAILABLE
                    else f"Saved to {os.path.abspath(cfg.config_path)}"
                )
            else:
                console.print(
                    f"[yellow]Could not save {os.path.abspath(cfg.config_path)}; you may need to enter it again next time.[/yellow]"
                    if RICH_AVAILABLE
                    else f"Could not save {os.path.abspath(cfg.config_path)}; you may need to enter it again next time."
                )
            return dbs

        console.print(
            "[yellow]That folder does not look like EDOPro. It needs cards.cdb or expansions/*.cdb.[/yellow]"
            if RICH_AVAILABLE
            else "That folder does not look like EDOPro. It needs cards.cdb or expansions/*.cdb."
        )


def scan_databases(db_files: list[str]) -> tuple[dict[int, str], dict[str, int]]:
    """
    Read every .cdb and return two mappings:

      id_to_name       — card_id  →  card name  (every card we know about)
      name_to_official  — name     →  official id (IDs < 100 000 000 only)
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
                f"[yellow]⚠️  Error reading {db}: {exc}[/yellow]"
                if RICH_AVAILABLE
                else f"⚠️  Error reading {db}: {exc}"
            )

    return id_to_name, name_to_official


# ── Name matching ─────────────────────────────────────────────────────────────

def find_official_match(
    name: str,
    name_to_official: dict[str, int],
    suffixes: list[str],
) -> int | None:
    """Try to resolve a card name to its official Konami ID."""
    # 1. Exact match
    if name in name_to_official:
        return name_to_official[name]
    # 2. Suffix-stripped match
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
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


# ── Download logic with retries ───────────────────────────────────────────────

class DownloadStats:
    """Thread-safe-ish counters (fine for asyncio single-thread)."""

    def __init__(self):
        self.ok_hd = 0         # Downloaded via official HD
        self.ok_mapped = 0     # Downloaded via manual map
        self.ok_fallback = 0   # Downloaded via backup / low-res
        self.skipped = 0       # Already existed
        self.failed = 0        # Could not download at all
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
                    # Sanity check: a valid JPEG is > 1 KB typically
                    if len(content) < 512:
                        if attempt >= max_retries:
                            return False
                    else:
                        with open(filepath, "wb") as f:
                            f.write(content)
                        return True
                elif resp.status == 404:
                    return False  # No point retrying a 404
                # 5xx or transient — fall through to retry
        except (aiohttp.ClientError, asyncio.TimeoutError):
            pass
        except OSError as exc:
            # Disk/permission error writing the file — report once and give up
            console.print(
                f"[red]Cannot write to {filepath}: {exc}[/red]"
                if RICH_AVAILABLE
                else f"Cannot write to {filepath}: {exc}"
            )
            return False

        # Exponential backoff: 1s, 2s, 4s …
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

    # Skip existing (unless --force)
    if not cfg.force and os.path.exists(filepath):
        stats.skipped += 1
        if progress and task_id is not None:
            progress.advance(task_id)
        return

    if cfg.dry_run:
        tag = "manual-map" if manual_match else ("hd-match" if official_match else "fallback")
        console.print(f"  [dim]Would download:[/dim] {name} ({card_id}) [{tag}]" if RICH_AVAILABLE else f"  Would download: {name} ({card_id}) [{tag}]")
        if progress and task_id is not None:
            progress.advance(task_id)
        return

    timeout = aiohttp.ClientTimeout(total=cfg.timeout)

    # Strategy 1 — Manual override
    if manual_match:
        url = f"{cfg.sources['official']}/{manual_match}.jpg"
        if await _try_download(session, url, filepath, timeout, cfg.max_retries):
            stats.ok_mapped += 1
            if progress and task_id is not None:
                progress.advance(task_id)
            return

    # Strategy 2 — Smart name-matched HD art
    if official_match and official_match != card_id:
        url = f"{cfg.sources['official']}/{official_match}.jpg"
        if await _try_download(session, url, filepath, timeout, cfg.max_retries):
            stats.ok_hd += 1
            if progress and task_id is not None:
                progress.advance(task_id)
            return

    # Strategy 3 — Direct ID on official source
    # Skip for custom/unofficial IDs (≥ 100M) — ygoprodeck only has official Konami cards,
    # so trying these is a guaranteed 404 that just wastes time.
    if card_id < 100_000_000:
        url = f"{cfg.sources['official']}/{card_id}.jpg"
        if await _try_download(session, url, filepath, timeout, cfg.max_retries):
            stats.ok_hd += 1
            if progress and task_id is not None:
                progress.advance(task_id)
            return

    # Strategy 4 — Low-res fallback (Project Ignis)
    if "backup" in cfg.sources:
        url = f"{cfg.sources['backup']}/{card_id}.jpg"
        if await _try_download(session, url, filepath, timeout, cfg.max_retries):
            stats.ok_fallback += 1
            if progress and task_id is not None:
                progress.advance(task_id)
            return

    # All strategies exhausted
    stats.failed += 1
    stats.failed_cards.append((card_id, name))
    if progress and task_id is not None:
        progress.advance(task_id)


# ── Summary ───────────────────────────────────────────────────────────────────

def print_summary(stats: DownloadStats, total_missing: int, cfg: Config, runtime_seconds: float):
    """Print summary lines and optionally write report/log files."""
    summary_rows: list[tuple[str, int, str | None]] = []
    if cfg.dry_run:
        summary_rows.append(("Would download", total_missing - stats.skipped, None))
        summary_rows.append(("Already on disk", stats.skipped, "dim"))
    else:
        summary_rows.append(("HD artwork", stats.ok_hd, "green"))
        summary_rows.append(("Manual-mapped", stats.ok_mapped, "green"))
        summary_rows.append(("Low-res fallback", stats.ok_fallback, "yellow"))
        summary_rows.append(("Already existed", stats.skipped, "dim"))
        summary_rows.append(("Failed", stats.failed, "red" if stats.failed else "dim"))

    if RICH_AVAILABLE:
        console.print()
        console.rule("[bold]Sync Summary[/bold]")
        for label, value, style in summary_rows:
            formatted = f"{value:>7,}"
            if style:
                console.print(f"  {label:<18} [{style}]{formatted}[/{style}]")
            else:
                console.print(f"  {label:<18} {formatted}")
        if stats.failed_cards and not cfg.quiet:
            console.print(f"\n[red]Failed cards ({len(stats.failed_cards)}):[/red]")
            for cid, cname in stats.failed_cards[:20]:
                console.print(f"  [dim]{cid}[/dim] — {cname}")
            if len(stats.failed_cards) > 20:
                console.print(f"  … and {len(stats.failed_cards) - 20} more.")
        console.rule()
    else:
        sep = "─" * 38
        print(f"\n{sep}")
        print("  Sync Summary")
        print(sep)
        for label, value, _ in summary_rows:
            print(f"  {label:<18} {value:>7,}")
        print(sep)

    # Write failed cards to a log file
    if stats.failed_cards and not cfg.dry_run:
        log_path = os.path.join(cfg.edopro_path, "sync-failed.txt")
        try:
            with open(log_path, "w", encoding="utf-8") as f:
                f.write(f"EDOPro HD Sync — cards with no artwork found ({len(stats.failed_cards)} total)\n")
                f.write("These are usually custom/fan-made cards with no official artwork source.\n")
                f.write("─" * 60 + "\n")
                for cid, cname in stats.failed_cards:
                    f.write(f"{cid}\t{cname}\n")
            console.print(
                f"[dim]Failed card list saved to: {log_path}[/dim]"
                if RICH_AVAILABLE
                else f"Failed card list saved to: {log_path}"
            )
        except OSError:
            pass  # Not critical if the log can't be written

    if cfg.save_report:
        now = datetime.now()
        report_path = os.path.join(
            cfg.edopro_path,
            f"sync-report-{now.strftime('%Y%m%d-%H%M%S')}.txt",
        )
        try:
            with open(report_path, "w", encoding="utf-8") as f:
                f.write("EDOPro HD Sync Report\n")
                f.write("=" * 40 + "\n")
                f.write(f"Generated: {now.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Mode: {'Dry run (preview only)' if cfg.dry_run else 'Download'}\n")
                f.write(f"Runtime: {format_duration(runtime_seconds)}\n")
                f.write("\nSummary\n")
                for label, value, _ in summary_rows:
                    f.write(f"- {label}: {value}\n")
                if stats.failed_cards:
                    f.write("\nFailed cards\n")
                    for cid, cname in stats.failed_cards:
                        f.write(f"{cid}\t{cname}\n")
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


# ── Main ──────────────────────────────────────────────────────────────────────

async def run(cfg: Config):
    started_at = perf_counter()
    # Banner
    try:
        if RICH_AVAILABLE:
            console.print(f"[bold cyan]EDOPro HD Sync[/bold cyan] [dim]v{VERSION}[/dim]")
            console.print("[dim]Automatic HD artwork downloader for EDOPro[/dim]")
        else:
            console.print(f"EDOPro HD Sync v{VERSION}")
            console.print("Automatic HD artwork downloader for EDOPro")

        # 1. Discover databases
        dbs = get_db_files(cfg.edopro_path)
        if not dbs:
            dbs = prompt_for_edopro_path(cfg)
            if not dbs:
                return

        # Ensure pics/ exists after the final EDOPro folder is known
        os.makedirs(cfg.pics_path, exist_ok=True)
        abs_pics = os.path.abspath(cfg.pics_path)
        console.print(
            f"[dim]Saving images to:[/dim] [bold]{abs_pics}[/bold]"
            if RICH_AVAILABLE
            else f"Saving images to: {abs_pics}"
        )

        console.print(
            f"[dim]Found {len(dbs)} database(s): {', '.join(os.path.basename(d) for d in dbs)}[/dim]"
            if RICH_AVAILABLE
            else f"Found {len(dbs)} database(s): {', '.join(os.path.basename(d) for d in dbs)}"
        )

        # 2. Scan
        id_to_name, name_to_official = scan_databases(dbs)
        manual_map = load_manual_map(cfg.manual_map_file)
        console.print(
            f"[dim]Indexed {len(id_to_name):,} cards  •  {len(name_to_official):,} HD candidates  •  {len(manual_map)} manual overrides[/dim]"
            if RICH_AVAILABLE
            else f"Indexed {len(id_to_name):,} cards  |  {len(name_to_official):,} HD candidates  |  {len(manual_map)} manual overrides"
        )

        # 3. Find missing
        if cfg.force:
            missing_ids = list(id_to_name.keys())
        else:
            missing_ids = [
                cid
                for cid in id_to_name
                if not os.path.exists(os.path.join(cfg.pics_path, f"{cid}.jpg"))
            ]

        if not missing_ids:
            console.print(
                "\n[bold green]✨ All synced — nothing to download![/bold green]"
                if RICH_AVAILABLE
                else "\nAll synced — nothing to download!"
            )
            return

        console.print(
            f"\n[bold]{'Previewing' if cfg.dry_run else 'Downloading'} {len(missing_ids):,} missing images[/bold]  "
            f"[dim](concurrency={cfg.concurrency}, retries={cfg.max_retries})[/dim]"
            if RICH_AVAILABLE
            else f"\n{'Previewing' if cfg.dry_run else 'Downloading'} {len(missing_ids):,} missing images  "
            f"(concurrency={cfg.concurrency}, retries={cfg.max_retries})"
        )

        # 4. Download with progress
        stats = DownloadStats()

        # Build a queue of all card IDs to process.
        # A fixed pool of `concurrency` workers drains it — this keeps exactly
        # N tasks active at a time instead of creating one coroutine per card.
        queue: asyncio.Queue[int] = asyncio.Queue()
        for cid in missing_ids:
            queue.put_nowait(cid)

        ssl_ctx = ssl.create_default_context(cafile=certifi.where())
        connector = aiohttp.TCPConnector(
            limit=cfg.concurrency,
            enable_cleanup_closed=True,
            ssl=ssl_ctx,
        )

        async with aiohttp.ClientSession(connector=connector) as session:
            # Quick connectivity check before the main loop
            try:
                test_timeout = aiohttp.ClientTimeout(total=8)
                async with session.get(
                    f"{cfg.sources['official']}/46986414.jpg",
                    timeout=test_timeout,
                ) as resp:
                    if resp.status == 200:
                        console.print(
                            "[dim green]✓ Connected to image server[/dim green]"
                            if RICH_AVAILABLE
                            else "✓ Connected to image server"
                        )
                    else:
                        console.print(
                            f"[yellow]⚠ Image server returned HTTP {resp.status} — downloads may fail[/yellow]"
                            if RICH_AVAILABLE
                            else f"⚠ Image server returned HTTP {resp.status}"
                        )
            except Exception as exc:
                console.print(
                    f"[bold red]✗ Cannot reach image server: {exc}\n"
                    "  Check your internet connection — downloads will fail.[/bold red]"
                    if RICH_AVAILABLE
                    else f"✗ Cannot reach image server: {exc}"
                )

            def make_worker(progress=None, task_id=None):
                async def worker():
                    while True:
                        try:
                            cid = queue.get_nowait()
                        except asyncio.QueueEmpty:
                            return
                        name = id_to_name[cid]
                        official = find_official_match(name, name_to_official, cfg.suffixes)
                        manual = manual_map.get(str(cid))
                        await download_card(
                            session, cid, name, official, manual,
                            cfg, stats, progress, task_id,
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
                    task_id = progress.add_task("Syncing…", total=len(missing_ids))
                    workers = [make_worker(progress, task_id)() for _ in range(cfg.concurrency)]
                    await asyncio.gather(*workers)
            else:
                workers = [make_worker()() for _ in range(cfg.concurrency)]
                await asyncio.gather(*workers)

        # 5. Summary
        print_summary(stats, len(missing_ids), cfg, perf_counter() - started_at)
    finally:
        elapsed = perf_counter() - started_at
        console.print(
            f"[bold]Total runtime:[/bold] {format_duration(elapsed)}"
            if RICH_AVAILABLE
            else f"Total runtime: {format_duration(elapsed)}"
        )


def main():
    cfg = Config()

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    try:
        asyncio.run(run(cfg))
    except KeyboardInterrupt:
        console.print(
            "\n[yellow]Interrupted — partial progress is saved.[/yellow]"
            if RICH_AVAILABLE
            else "\nInterrupted — partial progress is saved."
        )


if __name__ == "__main__":
    main()
