<p align="center">
  <img src="assets/github-banner.jpg" alt="EDOPro HD Sync banner" width="100%">
</p>

<h1 align="center">EDOPro HD Sync</h1>

<p align="center"><b>Every card in HD. One double-click.</b></p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/github/license/cntrl-alt-lenny/EDOPro-HD-Sync" alt="License">
  <img src="https://img.shields.io/github/v/release/cntrl-alt-lenny/EDOPro-HD-Sync" alt="Release">
  <img src="https://img.shields.io/github/downloads/cntrl-alt-lenny/EDOPro-HD-Sync/total?color=2ea44f&label=downloads" alt="Downloads">
  <img src="https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey" alt="Platform">
</p>

<p align="center">
  A fast, automatic HD artwork downloader for <a href="https://github.com/edo9300/edopro">EDOPro</a>.
  It scans your card databases, finds every missing image, and fetches the best available artwork —
  official, Rush Duel, anime/custom, GOAT, Pre-Errata, and alternate arts included.
</p>

<p align="center">
  <img src="assets/app-window.svg" alt="EDOPro HD Sync options window" width="520">
</p>

## Download

Grab **one file** for your platform — no install, no Python, no setup.

| Platform | Get this file | Then |
|---|---|---|
| **Windows** | [`EDOPro-HD-Sync.bat`](https://github.com/cntrl-alt-lenny/EDOPro-HD-Sync/releases/latest) | Double-click it. If SmartScreen warns, choose **More info → Run anyway**. |
| **macOS** | [`EDOPro-HD-Sync.command`](https://github.com/cntrl-alt-lenny/EDOPro-HD-Sync/releases/latest) | Double-click it (first time: **right-click → Open**), then pick your ProjectIgnis folder. |
| **Linux** | [`EDOPro-HD-Sync.sh`](https://github.com/cntrl-alt-lenny/EDOPro-HD-Sync/releases/latest) | Run `./EDOPro-HD-Sync.sh`, then pick your ProjectIgnis folder. |

Each launcher downloads the app (checksum-verified), remembers your EDOPro folder, and **keeps itself on the latest version automatically**. Full platform zip bundles with a `ReadMe.txt` are also on the [Releases page](https://github.com/cntrl-alt-lenny/EDOPro-HD-Sync/releases/latest).

## Features

- **Tick-box options window** — the packaged app opens a small window on Windows, macOS, and Linux: pick field art, only-my-decks, textures, repair, or a full refresh, then press Start.
- **Every card type covered** — official, Rush Duel, and anime/custom cards are all fetched directly by the same IDs EDOPro uses.
- **Field Spell playmat art** — the cropped artwork EDOPro displays on the board is downloaded into `pics/field/` automatically.
- **Deck-first sync** — `--my-decks` (or its tick-box) only fetches cards used in your decks, so a fresh install is playable in minutes instead of hours.
- **Coverage at a glance** — `--stats` shows artwork coverage and disk usage without downloading a thing.
- **Repair mode** — `--repair` finds corrupt or half-downloaded images and re-fetches them.
- **Curated textures** — optionally grab a hand-picked set of backgrounds and card sleeves.
- **Self-updating launchers** — one double-clickable file per platform installs new versions on its own.
- **Safe and resumable** — checksum-verified downloads, a 14-day failure cache so known-missing cards aren't hammered, and optional timestamped sync reports.

## How it works

1. **Scan** — reads every `.cdb` card database in your EDOPro folder (root, `expansions/`, and repository deltas).
2. **Diff** — compares the card list against the images already in `pics/` and only queues what's missing.
3. **Fetch** — 50 async workers try each card on [YGOProDeck](https://ygoprodeck.com), with a waterfall for tricky cases: manual overrides, GOAT / Pre-Errata suffix matching, an ID-offset fallback, and ProjectIgnis's own image server as the final backup (so even brand-new Rush Duel sets download).
4. **Extras** — Field Spell playmat art lands in `pics/field/`, definitive misses are cached for 14 days, and a sync report can be saved when it's done.

## CLI reference

The packaged app needs no flags — the options window covers the common choices. Power users get the full set:

<details>
<summary><b>All flags</b></summary>

| Flag | What it does |
|---|---|
| `--force` / `--no-force` | Re-download **all** images for a full refresh (default: only missing). |
| `--dry-run` | Preview what would be downloaded without downloading. |
| `--my-decks` | Only sync cards used in your EDOPro deck folder (much faster). |
| `--deck PATH` | Only sync cards in one `.ydk` file (repeat to combine decks). |
| `--decks-folder PATH` | Only sync cards in every `.ydk` inside a folder. |
| `--stats` | Show artwork coverage and disk usage, then exit. |
| `--repair` | Re-download images that are missing, corrupt, or not valid JPEGs. |
| `--field-art` / `--no-field-art` | Field Spell playmat art into `pics/field/` (default: on). |
| `--textures` / `--no-textures` | Also download the curated texture pack into `textures/`. |
| `--textures-pack NAME` | Pick a specific texture pack. |
| `--gui` / `--no-gui` | Force or skip the tick-box options window. |
| `--recheck-missing` | Retry cards in the failure cache (useful after new sets hit YGOProDeck). |
| `--prune` | After the sync, delete images whose IDs are no longer in any database. |
| `--edopro-path PATH` | Point at a specific EDOPro/ProjectIgnis folder. |
| `--save-report` / `--no-save-report` | Write a timestamped `.txt` sync report. |
| `--quiet` | Minimal output — just the progress bar and summary. |
| `--concurrency N` | Max simultaneous downloads (default: 50). |
| `--max-retries N` | Retry failed downloads N times (default: 3). |
| `--timeout N` | HTTP timeout in seconds (default: 30). |
| `--config PATH` | Use a custom config file. |
| `--generate-config` | Write a default `config.json` and exit. |
| `--health-check` | Run quick offline sanity checks and exit. |
| `--no-pause` | Windows packaged builds: close immediately instead of waiting for Enter. |

</details>

## From source

```bash
git clone https://github.com/cntrl-alt-lenny/EDOPro-HD-Sync.git
cd EDOPro-HD-Sync
pip install -r requirements.txt

python main.py                 # normal sync
python main.py --my-decks      # deck-first sync
python main.py --health-check  # quick offline sanity check
```

## Contributing

Contributions are welcome — open an issue or send a pull request. Please run `python main.py --health-check` and the test suite before submitting.

## Credits

- Original concept: [EDOPro-Hd-Downloader](https://github.com/NiiMiyo/EDOPro-Hd-Downloader) by NiiMiyo
- Card artwork hosted by [YGOProDeck](https://ygoprodeck.com) and [ProjectIgnis](https://github.com/ProjectIgnis)
- Licensed under the [MIT License](LICENSE)
