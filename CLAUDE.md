# EDOPro HD Sync - Project Guide for Claude

## What this is
A tool that automatically downloads HD card artwork for the EDOPro Yu-Gi-Oh! simulator (ProjectIgnis fork). Users place it in their EDOPro folder and run it - it scans the card databases, finds missing images, and downloads them from the best available source.

The owner is a non-programmer. Keep explanations plain and avoid jargon. Prefer simple, focused changes over clever abstractions.

**After committing and pushing any change, always offer to push a version tag so a new release is built automatically.** The owner will not know to do this themselves. Suggest the next patch/minor version based on what changed.

**Release packaging requirements must be preserved.** Publish **exactly one asset per platform** — no checksum files, no launchers — so the Releases page reads simply "Windows, macOS, Linux":
- `EDOPro-HD-Sync-Windows-vVERSION.zip`
- `EDOPro-HD-Sync-macOS-vVERSION.zip`
- `EDOPro-HD-Sync-Linux-vVERSION.zip`

**Each zip contains exactly two files: the app and a platform-specific `ReadMe.txt`.** That is the whole promise of the download — unzip, double-click, done. `build.yml` fails the build if a zip ever grows a third entry, loses either file, or ships a non-executable app. Nothing is installed and nothing is left on the user's machine: no support folder, no `%LOCALAPPDATA%`, no `~/Library/Application Support`.

**The Windows build must stay `--windowed`, and `build.yml` checks the PE subsystem byte to prove it.** A console build shows a stray black console window behind the app on every double-click. Do **not** try to fix that at runtime by hiding the console: that was tried and it does not hold. The console Explorer creates for a double-click is not the same object as the pseudo-console a terminal hands a child process, so the fix cannot be verified from any terminal — it looked like it worked in testing and still shipped the bug. Not creating a console at all is the only version that cannot regress. Output still reaches an inherited pipe or terminal, so `--health-check` and the CI smoke test are unaffected. Keep `--windowed` off macOS, where it would build a `.app` bundle instead of the single file the release needs.

Related: `should_pause_before_exit()` requires an interactive `sys.stdin`. A windowed double-click has no console, so pausing for Enter there would hang the app on input nobody can see.

**Keep the app as a bare executable, not a `.app` bundle or a script.** A zip preserves the executable bit (a browser download does not — mode 644 caused the "you do not have appropriate access privileges" bug in v5.0.0), so the raw binary double-clicks fine on all three platforms. Keep `.zip` (not `.7z`) for native unzip support.

**Build with PyInstaller `--onefile`, never `--onedir`.** Onedir is faster to start (0.3 s vs 1.9 s measured on the owner's machine, 23.6 MB binary) but spreads the app over ~1,000 files in an `_internal/` folder, which forced a launcher script to exist purely to hide it. That launcher was the single biggest source of bugs in the project's history (see below). One file, ~2 s to start, no launcher: that trade is deliberate — do not reverse it to shave a second off a tool people run occasionally.

**There is no launcher, and adding one back is a regression.** `EDOPro-HD-Sync.bat` / `.command` / `.sh` were deleted in v5.2.0. They existed to install the onedir app into a support folder and self-update it, and they broke repeatedly: the macOS executable-bit bug (v5.0.0), the Windows checksum bug, and finally a Windows launcher left copying a single `.exe` after the app became a folder — which created `app\EDOPro-HD-Sync.exe.new` inside a directory that was never created, so **every Windows install of v5.1.0/v5.1.1 failed outright**. Three launchers in three languages could not be kept in step with the packaging. Updates are now just a notice in the app pointing at the Releases page.

## Running / developing locally
```bash
pip install -r requirements.txt
python main.py                  # normal sync
python main.py --dry-run        # preview only
python main.py --force          # re-download everything
python main.py --generate-config  # write a default config.json
python main.py --health-check   # quick offline sanity check
```

## Project structure
```text
main.py                     # core logic: DB scan, download pipeline, Rich UI
config.py                   # settings + EDOPro folder detection
gui.py                      # tick-box options window (tkinter, all platforms)
requirements.txt            # aiohttp, rich, certifi
release_assets/ReadMe-*.txt # the ReadMe shipped beside the app in each zip
.github/workflows/build.yml # CI: builds one binary per platform on tag push
```

## App window (gui.py)
Plain packaged runs open a branded three-screen tkinter app (navy/gold, ttk 'clam' theme): OPTIONS (grouped tick-boxes + Start / Show coverage), PROGRESS (determinate gold bar, current-card status, live count, Cancel), and SUMMARY (hero numbers + unavailable breakdown / coverage table). Architecture: Tk owns the main thread; `gui.run_app(cfg, VERSION, run, _apply_gui_choices)` runs `main.run()` in a daemon worker thread and communicates through a queue via runtime hooks on Config — `gui_progress` (a Rich-Progress-compatible adapter), `folder_picker` (worker asks the window to show the native directory dialog), `coverage_sink`, `notice_sink`, and `cancel_event` (workers check it between downloads, so Cancel finishes in-flight files and still writes the failure caches). `run()` returns the DownloadStats the summary screen renders; `cfg.interactive_prompts=False` mutes all console questions. Rules in `_should_show_gui`: `--gui` forces it (even from source), `--no-gui` or any explicit power flag skips it, non-frozen runs never show it by default, and any Tk failure raises `gui.GuiUnavailable` → console flow. The build workflow hard-fails if tkinter is missing on a CI runner; Windows gets DPI awareness + a dark title bar via ctypes (see the pitfall comments in gui.py before touching styling).

## Deck-first sync
`--my-decks` (or the window's tick-box) points the deck filter at `<edopro>/deck`, scanned recursively for `.ydk`. On a fresh install (>2,000 cards indexed, <500 images on disk) the console flow asks "Quick start: only sync the cards in your N deck(s)?" before committing to a full ~13,000-card download.

## Architecture

### Card database scanning
EDOPro stores cards in SQLite `.cdb` files. The tool scans:
- `cards.cdb` at the EDOPro root (often an empty placeholder - skip if 0 bytes)
- every `*.cdb` in `expansions/`
- every `*.delta.cdb` under `repositories/`

From these it builds two maps:
- `id_to_name` - every card ID -> name
- `name_to_official` - name -> all official Konami IDs seen for that name (only IDs < 100,000,000)

### Download waterfall (in order, stops at first success)
1. **Manual override** - `BUILTIN_MANUAL_MAP` in `config.py` plus the user's optional `manual_map.json`. The built-in map pins multi-art suffix cards (e.g. two "Ring of Destruction (Pre-Errata)" variants) to distinct official artworks, since suffix stripping alone would give them all the same image.
2. **Direct ID on YGOProDeck** - tries `https://images.ygoprodeck.com/images/cards/{card_id}.jpg` for **every** card. YGOProDeck hosts official, Rush Duel, and anime/custom cards under the same IDs EDOPro uses (Rush coverage is partial: older sets are complete, the newest sets lag behind — `--recheck-missing` picks them up as they're added).
3. **Name-matched HD** - for GOAT/Pre-Errata suffix cards only. Strips the suffix, finds the base card's official IDs, and tries those on YGOProDeck.
4. **Pre-Errata offset fallback** - if a Pre-Errata suffix matched but the base card was missing from the scanned DBs, try `card_id - 10` on YGOProDeck.
5. **ProjectIgnis backup** - `https://pics.projectignis.org:2096/pics/{id}.jpg` — the official image server EDOPro itself downloads from (URL recovered from nixpkgs' from-source build; the `:2096` port is required). It has everything, including the newest Rush sets YGOProDeck lags on. **It's a small community server: it must stay LAST in the waterfall** so the YGOProDeck CDN absorbs the bulk. Field art has the same shape: `sources["field_backup"]` = `.../pics/field/{id}.png` after YGOProDeck's cropped .jpg. (The old GitHub `ProjectIgnis/Images` repo is deleted — never point at it.)

### Card ID rules
- IDs < 100,000,000 -> official Konami cards (these also count toward the "Official" failure bucket)
- IDs >= 100,000,000 -> Rush Duel (160M range, tracked via the DB filename) and anime/custom cards. All still get the direct YGOProDeck attempt.

### Field Spell playmat art
Field Spells (datas.type has both `0x2` SPELL and `0x80000` FIELD bits — `FIELD_SPELL_TYPE`) also get their cropped playmat artwork downloaded into `pics/field/{id}.jpg` from `https://images.ygoprodeck.com/images/cards_cropped/{id}.jpg`. EDOPro reads `.png` or `.jpg` there. Runs after the card sync, is incremental, has its own failure cache (`failed_fields.json`), is covered by `--repair`, and can be disabled with `--no-field-art` (or `"field_art": false` in config.json).

### GOAT / Pre-Errata trick
Cards like "Dark Magician GOAT" have a custom DB ID but the same artwork as "Dark Magician". The suffix-stripping logic removes known suffixes (` GOAT`, ` (Pre-Errata)`, etc.) and looks up the base name in `name_to_official` to find the real Konami ID, then downloads that HD image. If a Pre-Errata card's base name is missing from the scanned DBs, its GOAT DB ID is usually the real passcode + 10, so the downloader tries `card_id - 10` before falling back to ProjectIgnis.

### Failure cache (failed_cards.json, failed_fields.json)
Cards that fail to download are remembered for 14 days so repeat runs skip them (`failed_cards.json` for card art, `failed_fields.json` for field art). **Only definitive misses are cached** — `_try_download` returns a `FetchResult` (`OK` / `MISSING` / `ERROR`), and a card is cached only when every source said `MISSING` (HTTP 404). Timeouts, connection errors, rate limits, and 5xx are `ERROR` (transient) and are retried on the next run — never cache them, or one bad Wi-Fi day would silence hundreds of cards for two weeks.

### Concurrency
50 async workers drain a shared `asyncio.Queue`. Each worker loops until the queue is empty. This keeps a steady number of requests in flight without spawning tens of thousands of coroutines.

### SSL certificates
PyInstaller bundles do not include system SSL certs automatically. The app uses `certifi` and passes it to `aiohttp.TCPConnector` via `ssl.create_default_context(cafile=certifi.where())`. The build uses `--collect-data certifi` to include the cert bundle. **Do not remove this - it will silently break all downloads.**

## Release process
Push a version tag -> GitHub Actions builds 3 binaries -> attached to a GitHub Release automatically.

```bash
git tag v4.x.x && git push origin v4.x.x
```

The CI matrix builds:
- `EDOPro-HD-Sync-Windows-vVERSION.zip`
- `EDOPro-HD-Sync-macOS-vVERSION.zip`
- `EDOPro-HD-Sync-Linux-vVERSION.zip`

Each bundle includes a platform-specific `ReadMe.txt`. The workflow also smoke-tests the packaged binary with `--health-check` before the release asset is published.

`fail-fast: false` is set so a failure on one platform does not cancel the others.

## Release notes
Release notes are auto-generated by GitHub (`generate_release_notes: true` in build.yml) from the commits since the previous tag, so keep commit subjects short and user-readable. The README deliberately has no auto-updating "What's New" panels — the owner removed them; don't re-add them.

## Finding the EDOPro folder
The app locates the folder itself, so the user never has to know where EDOPro lives. `main.detect_edopro_folder()` runs once at startup (skipped entirely when `--edopro-path` was passed — an explicit answer is never second-guessed) and calls `config.find_edopro_folder()`, which checks, in order:

1. the caller's guesses — the remembered `edopro_path` from `config.json`, or the folder the app is sitting in
2. `EDOPRO_FOLDER_NAMES` joined onto each `_search_parents()` entry (home, Games, Desktop, Downloads, Documents, plus `%LOCALAPPDATA%\Programs`, `/Applications`, `~/.local/share`, …) — pure `isdir` checks, instant
3. one level inside each of those parents, for people who renamed the folder

Candidates are **scored, not first-match**: a folder with card databases (2) always beats one that merely looks like EDOPro (1), so a fresh install with no `.cdb` files yet never shadows a real one. The scan is capped by `_SEARCH_TIME_BUDGET_SECONDS` so startup can never appear to hang.

Two folder predicates exist on purpose and must not be merged:
- `folder_has_card_databases()` — **mirrors `main.get_db_files()` exactly.** If that returns nothing, this must be False, or the app would "find" a folder it then can't sync. `tests/test_folder_detection.py` asserts the two agree on every shape (root `cards.cdb`, `expansions/*.cdb`, `repositories/**/*.delta.cdb`, empty dirs, an `expansions/` with no `.cdb`). Keep that test passing whenever either function changes.
- `looks_like_edopro_folder()` — deliberately looser (accepts `EDOPro.exe` alone), because a freshly installed EDOPro that has not downloaded its databases yet is still the right folder.

**The user confirms the folder before anything downloads.** In the window, the OPTIONS screen's top card shows the folder with a **Change…** button, and pressing Start *is* the confirmation (`gui._render_folder` also disables Start when no folder is set). In the console flow, `main.confirm_edopro_folder()` asks "Use this folder?" defaulting to yes, and declining hands over to `prompt_for_edopro_path()`. The console prompt is gated on `cfg.folder_detected and cfg.interactive_prompts and not cfg.quiet`, so the window never double-asks and scripted runs never block.

## Updates
There is no self-updating machinery. `check_for_update()` compares `VERSION` against the latest GitHub tag and shows a notice pointing at the Releases page; the user downloads the new zip and replaces the one file. This replaced a launcher-driven auto-updater that broke the Windows install twice.

## Output files
- `pics/{id}.jpg` - downloaded card images (in the EDOPro folder)
- `pics/field/{id}.jpg` - Field Spell playmat artwork
- `failed_cards.json` / `failed_fields.json` - 14-day caches of definitively-missing art (beside the exe)
- `config.json` - optional user config (generated with `--generate-config`)
- `manual_map.json` - optional per-card ID overrides (user-created, not tracked in git)
- `manual_map.example.json` - copyable example showing the override format
