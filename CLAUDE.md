# EDOPro HD Sync - Project Guide for Claude

## What this is
A tool that automatically downloads HD card artwork for the EDOPro Yu-Gi-Oh! simulator (ProjectIgnis fork). Users place it in their EDOPro folder and run it - it scans the card databases, finds missing images, and downloads them from the best available source.

The owner is a non-programmer. Keep explanations plain and avoid jargon. Prefer simple, focused changes over clever abstractions.

**After committing and pushing any change, always offer to push a version tag so a new release is built automatically.** The owner will not know to do this themselves. Suggest the next patch/minor version based on what changed.

**Release packaging requirements must be preserved.** Keep the platform bundle names in this format:
- `EDOPro HD Sync - Windows Version VERSION.zip`
- `EDOPro HD Sync - MacOS Version VERSION.zip`
- `EDOPro HD Sync - Linux Version VERSION.zip`

Each platform bundle must include a platform-specific `ReadMe.txt`, and macOS/Windows should stay on `.zip` rather than `.7z` because native unzip support is better for non-technical users.

When users compare official failure counts between versions, remember that a lower number is usually good, but many remaining "official" misses are expected tokens, placeholders, or alternate-art IDs that the tool now skips on purpose because downloading them would produce the wrong image.

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
requirements.txt            # aiohttp, rich, certifi
EDOPro-HD-Sync.command      # macOS double-click launcher
.github/workflows/build.yml # CI: builds binaries for all 3 platforms on tag push
```

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
1. **Manual override** - `manual_map.json` lets users pin specific card IDs.
2. **Exact ID from the YGOProDeck catalog** - at startup the tool downloads the full `cardinfo.php` catalog once and builds an exact `card_id -> image_url` lookup from `card_images`.
3. **Name-matched HD** - strips GOAT/Pre-Errata suffixes, then tries matching official IDs that the catalog explicitly lists. Skipped for direct-name multi-art cards because a different artwork ID would be wrong art.
4. **Pre-Errata offset fallback** - if a Pre-Errata suffix matched but the base card was missing from the scanned DBs, try `card_id - 10` only if that exact ID exists in the catalog.
5. **ProjectIgnis backup** - `https://raw.githubusercontent.com/ProjectIgnis/Images/master/pics/{id}.jpg`

### Card ID rules
- IDs < 100,000,000 -> official Konami cards
- IDs >= 100,000,000 -> custom/fan/unofficial cards

### GOAT / Pre-Errata trick
Cards like "Dark Magician GOAT" have a custom DB ID but the same artwork as "Dark Magician". The suffix-stripping logic removes known suffixes (` GOAT`, ` (Pre-Errata)`, etc.) and looks up the base name in `name_to_official` to find the real Konami ID, then downloads that HD image only if the YGOProDeck catalog explicitly lists that artwork ID. If a Pre-Errata card's base name is missing from the scanned DBs, its GOAT DB ID is usually the real passcode + 10, so the downloader gets one last exact-catalog try with `card_id - 10` before falling back to ProjectIgnis.

### Concurrency
50 async workers drain a shared `asyncio.Queue`. Each worker loops until the queue is empty. This keeps a steady number of requests in flight without spawning tens of thousands of coroutines.

### SSL certificates
PyInstaller bundles do not include system SSL certs automatically. The app uses `certifi` and passes it to `aiohttp.TCPConnector` via `ssl.create_default_context(cafile=certifi.where())`. The build uses `--collect-data certifi` to include the cert bundle. **Do not remove this - it will silently break all downloads.**

## Release process
Push a version tag -> GitHub Actions builds 3 binaries -> attached to a GitHub Release automatically.

```bash
git tag v3.x.x && git push origin v3.x.x
```

The CI matrix builds:
- `EDOPro HD Sync - Windows Version VERSION.zip`
- `EDOPro HD Sync - MacOS Version VERSION.zip`
- `EDOPro HD Sync - Linux Version VERSION.zip`

Each bundle includes a platform-specific `ReadMe.txt`. The workflow also smoke-tests the packaged binary with `--health-check` before the release asset is published.

`fail-fast: false` is set so a failure on one platform does not cancel the others.

## macOS launcher (`EDOPro-HD-Sync.command`)
- Bash script, double-click opens it in Terminal
- `cd "$(dirname "$0")"` sets working dir to the EDOPro folder
- Downloads the binary from the latest release if not already present
- `xattr -d com.apple.quarantine` strips the macOS quarantine flag so users only get one security prompt
- Must stay marked executable in git: `git update-index --chmod=+x EDOPro-HD-Sync.command`

## Output files
- `pics/{id}.jpg` - downloaded card images (in the EDOPro folder)
- `config.json` - optional user config (generated with `--generate-config`)
- `manual_map.json` - optional per-card ID overrides (user-created, not tracked in git)
- `manual_map.example.json` - copyable example showing the override format. Alternate arts (Blue-Eyes, Dark Magician, etc.) are now auto-handled by the catalog lookup.
