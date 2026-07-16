# EDOPro HD Sync - Project Guide for Claude

## What this is
A tool that automatically downloads HD card artwork for the EDOPro Yu-Gi-Oh! simulator (ProjectIgnis fork). Users place it in their EDOPro folder and run it - it scans the card databases, finds missing images, and downloads them from the best available source.

The owner is a non-programmer. Keep explanations plain and avoid jargon. Prefer simple, focused changes over clever abstractions.

**After committing and pushing any change, always offer to push a version tag so a new release is built automatically.** The owner will not know to do this themselves. Suggest the next patch/minor version based on what changed.

**Release packaging requirements must be preserved.** Keep the release zip names in this format:
- `EDOPro-HD-Sync-Windows-vVERSION.zip`
- `EDOPro-HD-Sync-macOS-vVERSION.zip`
- `EDOPro-HD-Sync-Linux-vVERSION.zip`

Each platform bundle must include a platform-specific `ReadMe.txt`, and macOS/Windows should stay on `.zip` rather than `.7z` because native unzip support is better for non-technical users.

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
config.py                   # settings: defaults -> config.json -> CLI flags
gui.py                      # tick-box options window (tkinter, all platforms)
requirements.txt            # aiohttp, rich, certifi
EDOPro-HD-Sync.command      # macOS double-click launcher
.github/workflows/build.yml # CI: builds binaries for all 3 platforms on tag push
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

## Launcher auto-update
All three launchers keep their cached app copy up to date: on each run they ask GitHub for the latest release tag (short timeout; skipped silently when offline) and compare it to `binary_version.txt`. **Update order is sacred: download + checksum-verify + unpack into a scratch dir FIRST, replace the binary LAST** — a failed update must never break a working install (on failure they print "keeping the current version" and run the old binary). The shell launchers parse the release JSON with sed (no python3 — stock Macs don't have it), the .bat passes its own path via the HDSYNC_SELF env var (paths with apostrophes), and `looks_like_edopro` requires actual `.cdb` files so the launcher and app never disagree about a folder. Zip-bundle copies (binary next to the launcher) are never auto-updated.

## macOS launcher (`EDOPro-HD-Sync.command`)
- Standalone single file: double-click opens it in Terminal; it does NOT need to live inside the EDOPro folder. Attached to releases on its own and also bundled in the zip.
- First run shows a native "choose folder" dialog (defaults to `/Applications`, auto-targets `/Applications/ProjectIgnis`) and remembers the choice in `~/Library/Application Support/EDOPro-HD-Sync/edopro_folder.txt`
- Downloads + checksum-verifies the binary into `~/Library/Application Support/EDOPro-HD-Sync` if missing (or uses the binary shipped next to it in the zip bundle)
- `xattr -d com.apple.quarantine` strips the quarantine flag from itself and the binary. The binary is fetched via curl so it isn't quarantined — the app opens with no Gatekeeper/Privacy prompt; only the launcher file itself may need a one-time right-click → Open
- Runs the binary with `--edopro-path "<folder>"`. It no longer passes `--force`, so runs are incremental (only missing art); pass `--force` for a full refresh, or use the in-app "re-download everything?" prompt that appears when nothing is missing
- Must stay marked executable in git: `git update-index --chmod=+x EDOPro-HD-Sync.command`

## Linux & Windows launchers
- `EDOPro-HD-Sync.sh` (Linux) mirrors the macOS launcher: standalone single file, folder picker via `zenity`/`kdialog` (terminal fallback), self-downloads + checksum-verifies the binary into `~/.local/share/EDOPro-HD-Sync`, remembers the folder, runs with `--edopro-path`. Keep it executable in git.
- `EDOPro-HD-Sync.bat` (Windows) is a batch/PowerShell polyglot: the embedded PowerShell after the `#PSSTART#` marker downloads + checksum-verifies the zip into `%LOCALAPPDATA%\EDOPro-HD-Sync`, runs `Unblock-File` (the SmartScreen equivalent of the macOS quarantine strip), then runs the exe (which shows its own folder picker). `.gitattributes` keeps it CRLF; test.yml validates the embedded PowerShell parses on the Windows runner.
- All three launchers are attached to releases as standalone single files (and bundled in their platform zips).

## Output files
- `pics/{id}.jpg` - downloaded card images (in the EDOPro folder)
- `pics/field/{id}.jpg` - Field Spell playmat artwork
- `failed_cards.json` / `failed_fields.json` - 14-day caches of definitively-missing art (beside the exe)
- `config.json` - optional user config (generated with `--generate-config`)
- `manual_map.json` - optional per-card ID overrides (user-created, not tracked in git)
- `manual_map.example.json` - copyable example showing the override format
