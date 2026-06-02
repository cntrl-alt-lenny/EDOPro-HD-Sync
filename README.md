<p align="center">
  <img src="assets/github-banner.jpg" alt="EDOPro HD Sync banner" width="100%">
</p>

<h1 align="center">EDOPro HD Sync</h1>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/github/license/cntrl-alt-lenny/EDOPro-HD-Sync" alt="License">
  <img src="https://img.shields.io/github/v/release/cntrl-alt-lenny/EDOPro-HD-Sync" alt="Release">
  <img src="https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey" alt="Platform">
</p>

<p align="center">
  A fast, automatic HD artwork downloader for <a href="https://github.com/edo9300/edopro">EDOPro</a>.
  It scans your card databases, finds missing images, and downloads the best available artwork,
  including GOAT, Pre-Errata, and alternate art variants.
</p>

## Why It Feels Better

- **Tries every card ID directly** - no startup catalog download, just simple direct requests
- **Truthful alternate-art handling** - falls back to ProjectIgnis when YGOProDeck doesn't have the art
- **Offline health check** - quickly verifies suffix-stripping logic
- **Simple packaged releases** - ready-to-use downloads for Windows, macOS, and Linux
- **Curated textures** - optionally fetch a hand-picked set of backgrounds and card sleeves

## Quick Start

### Windows

1. Download `EDOPro-HD-Sync-Windows-vVERSION.zip` from [Releases](https://github.com/cntrl-alt-lenny/EDOPro-HD-Sync/releases/latest)
2. Extract the zip and open the `EDOPro HD Sync Windows` folder
3. Run `EDOPro-HD-Sync.exe`
4. Pick your EDOPro folder when prompted
5. The bundle includes a Windows `ReadMe.txt` with the same steps

### macOS

1. Download the single `EDOPro-HD-Sync.command` file from [Releases](https://github.com/cntrl-alt-lenny/EDOPro-HD-Sync/releases/latest)
2. Double-click it
3. The first time, pick your ProjectIgnis folder (the dialog starts in Applications) — it remembers your choice
4. If macOS asks the first time, **right-click the file and choose Open** (no System Settings trip needed)

It downloads the app and your HD artwork, then runs. The full `EDOPro-HD-Sync-macOS-vVERSION.zip` bundle (with a Mac `ReadMe.txt`) is also available if you prefer it.

### Linux

1. Download `EDOPro-HD-Sync-Linux-vVERSION.zip` from [Releases](https://github.com/cntrl-alt-lenny/EDOPro-HD-Sync/releases/latest)
2. Unzip into your EDOPro folder and open the `EDOPro HD Sync Linux` folder
3. Run `./EDOPro-HD-Sync.sh` (double-click in your file manager, or run it from a terminal)
4. The launcher runs the tool from your EDOPro folder, or prompts you to choose the folder if it can't find one
5. The bundle includes a Linux `ReadMe.txt`

### From Source

```bash
pip install -r requirements.txt
python main.py --force
python main.py --health-check
```

## How It Works

Scans all `.cdb` card databases in your EDOPro folder, tries each card's ID directly on [YGOProDeck](https://ygoprodeck.com), and falls back to [ProjectIgnis](https://github.com/ProjectIgnis/Images) when the HD image isn't available.

- **Alternate artworks** - each art ID is tried individually on YGOProDeck; if it 404s, ProjectIgnis provides the backup
- **GOAT format cards** - matched to their official artwork by stripping the GOAT suffix
- **Pre-Errata cards** - resolved via suffix stripping, with a small ID-offset fallback for legacy edge cases
- **Manual overrides** - optional `manual_map.json` for edge cases

## Helpful Commands

- `python main.py --health-check` runs an offline sanity check for suffix-stripping and Pre-Errata matching
- `python main.py --dry-run` previews what would be downloaded
- `python main.py --textures` also downloads the curated texture pack (custom backgrounds and card sleeves) into `textures/` (the packaged app asks about this too)
- `python main.py --edopro-path "/path/to/ProjectIgnis"` points the tool at a specific folder

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.

## Credits

- Original concept: [EDOPro-Hd-Downloader](https://github.com/NiiMiyo/EDOPro-Hd-Downloader) by NiiMiyo
- Licensed under the [MIT License](LICENSE)
