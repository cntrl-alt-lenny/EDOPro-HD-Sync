# EDOPro HD Sync — Project Guide for Claude

## What this is
A tool that automatically downloads HD card artwork for the EDOPro Yu-Gi-Oh! simulator (ProjectIgnis fork). Users place it in their EDOPro folder and run it — it scans the card databases, finds missing images, and downloads them from the best available source.

The owner is a non-programmer. Keep explanations plain and avoid jargon. Prefer simple, focused changes over clever abstractions.

**After committing and pushing any change, always offer to push a version tag so a new release is built automatically.** The owner will not know to do this themselves. Suggest the next patch/minor version based on what changed.

**Release packaging requirements must be preserved.** Keep the platform bundle names in this format:
- `EDOPro HD Sync - Windows Version VERSION.zip`
- `EDOPro HD Sync - MacOS Version VERSION.zip`
- `EDOPro HD Sync - Linux Version VERSION.zip`

Each platform bundle must include a platform-specific `ReadMe.txt`, and macOS/Windows should stay on `.zip` rather than `.7z` because native unzip support is better for non-technical users.

`alternate-art-cache.json` is a runtime memory file, not a user settings file. It stores which alternate-art IDs YGOProDeck confirmed as safe so the downloader can avoid wrong default art on future runs.

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
```
main.py                     # core logic: DB scan, download pipeline, Rich UI
config.py                   # settings: defaults → config.json → CLI flags
requirements.txt            # aiohttp, rich, certifi
EDOPro-HD-Sync.command      # macOS double-click launcher (bash menu + bootstrapper)
.github/workflows/build.yml # CI: builds binaries for all 3 platforms on tag push
```

## Architecture

### Card database scanning
EDOPro stores cards in SQLite `.cdb` files. The tool scans:
- `cards.cdb` at the EDOPro root (often an empty placeholder — skip if 0 bytes)
- every `*.cdb` in `expansions/`

From these it builds two maps:
- `id_to_name` — every card ID → name
- `name_to_official` — name → all official Konami IDs seen for that name (only IDs < 100,000,000)

### Download waterfall (in order, stops at first success)
1. **Manual override** — `manual_map.json` lets users pin specific card IDs
2. **Direct ID on ygoprodeck** — `https://images.ygoprodeck.com/images/cards/{id}.jpg` (skipped for IDs ≥ 100M, which ygoprodeck never has). Tried first so alternate artworks (Blue-Eyes, Dark Magician, etc.) each get their own correct image. For multi-art cards, the YGOProDeck API is queried at startup to learn which IDs have distinct artwork; IDs not on that list skip this step to avoid downloading the wrong image.
3. **Name-matched HD** — strips GOAT/Pre-Errata suffixes, tries every matching official ID on ygoprodeck until one works. This is the fallback for GOAT/Pre-Errata cards whose custom DB ID doesn't exist on ygoprodeck. Skipped for multi-art cards (would give the wrong artwork).
4. **Pre-Errata offset fallback** — if a Pre-Errata suffix matched but the base card was missing from the scanned DBs, try `card_id - 10` on ygoprodeck
5. **ProjectIgnis backup** — `https://raw.githubusercontent.com/ProjectIgnis/Images/master/pics/{id}.jpg`

Confirmed alternate-art IDs are cached in `alternate-art-cache.json` beside the tool so repeated runs do not depend entirely on the live YGOProDeck API.

### Card ID rules
- IDs < 100,000,000 → official Konami cards (ygoprodeck has them)
- IDs ≥ 100,000,000 → custom/fan/unofficial cards (skip ygoprodeck, try backup only)

### GOAT / Pre-Errata trick
Cards like "Dark Magician GOAT" have a custom DB ID but the same artwork as "Dark Magician". The suffix-stripping logic removes known suffixes (` GOAT`, ` (Pre-Errata)`, etc.) and looks up the base name in `name_to_official` to find the real Konami ID, then downloads that HD image for the custom card's ID. If a Pre-Errata card's base name is missing from the scanned DBs, its GOAT DB ID is usually the real passcode + 10, so the downloader gets one last ygoprodeck try with `card_id - 10` before falling back to ProjectIgnis.

### Concurrency
50 async workers drain a shared `asyncio.Queue`. Each worker loops until the queue is empty. This keeps exactly 50 requests in flight at all times (not 22,000 simultaneous coroutines).

### SSL certificates
PyInstaller bundles don't include system SSL certs. We explicitly use `certifi` and pass it to `aiohttp.TCPConnector` via `ssl.create_default_context(cafile=certifi.where())`. The build uses `--collect-data certifi` to include the cert bundle. **Do not remove this — it will silently break all downloads.**

## Release process
Push a version tag → GitHub Actions builds 3 binaries → attached to a GitHub Release automatically.

```bash
git tag v3.x.x && git push origin v3.x.x
```

The CI matrix builds:
- `EDOPro HD Sync - Windows Version VERSION.zip`
- `EDOPro HD Sync - MacOS Version VERSION.zip`
- `EDOPro HD Sync - Linux Version VERSION.zip`

Each bundle includes a platform-specific `ReadMe.txt`. The workflow also smoke-tests the packaged binary with `--health-check` before the release asset is published.

`fail-fast: false` is set so a failure on one platform doesn't cancel the others.

## macOS launcher (EDOPro-HD-Sync.command)
- Bash script, double-click opens it in Terminal
- `cd "$(dirname "$0")"` sets working dir to the EDOPro folder
- Downloads the binary from the latest release if not already present
- `xattr -d com.apple.quarantine` strips the macOS quarantine flag so users only get one security prompt
- Shows a numbered menu before running so users can choose a mode
- Must stay marked executable in git: `git update-index --chmod=+x EDOPro-HD-Sync.command`

## Output files
- `pics/{id}.jpg` — downloaded card images (in the EDOPro folder)
- `alternate-art-cache.json` — cached YGOProDeck alternate-art confirmations beside the tool/config
- `config.json` — optional user config (generated with `--generate-config`)
- `manual_map.json` — optional per-card ID overrides (user-created, not tracked in git)
- `manual_map.example.json` — copyable example showing the override format. Alternate arts (Blue-Eyes, Dark Magician, etc.) are now auto-handled by the waterfall trying each card's own ID first.
