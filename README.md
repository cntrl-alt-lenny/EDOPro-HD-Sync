# EDOPro HD Sync

A lightning-fast, automated HD artwork downloader for EDOPro.

Reads your local `.cdb` databases (including expansions, Alt Arts, GOAT formats, and Anime cards) and downloads every missing HD card image automatically.

## Features

- **Zero Configuration** — drop it in your EDOPro folder and run it.
- **Database Sync** — scans `cards.cdb` + all expansion databases so every installed card gets artwork.
- **Async Downloads** — fetches up to 50 images simultaneously with automatic retries.
- **Smart Matching** — maps GOAT / Pre-Errata variants to their official HD art via suffix stripping.
- **Manual Overrides** — use `manual_map.json` to force specific card-ID-to-image mappings.
- **Rich Progress UI** — colour-coded progress bar, spinner, and summary table in the terminal.
- **Fully Configurable** — tune concurrency, retries, timeouts, and image sources via `config.json` or CLI flags.
- **Cross-Platform** — works on Windows, Linux, and macOS.

## Quick Start

### From a Release Binary

1. Download the executable for your OS from the [Releases page](LINK_TO_YOUR_RELEASES_PAGE).
2. Place it inside your **EDOPro root folder** (where `EDOPro.exe` / `cards.cdb` lives).
3. Double-click to run (or run from a terminal for more options).

### From Source

```bash
# Python 3.10+ required
pip install -r requirements.txt
python main.py
```

## CLI Options

```
python main.py [OPTIONS]

Options:
  --force            Re-download ALL images, even existing ones
  --dry-run          Preview what would be downloaded (no actual downloads)
  --concurrency N    Max simultaneous downloads (default: 50)
  --max-retries N    Retry failed downloads N times (default: 3)
  --timeout N        HTTP timeout in seconds (default: 30)
  --config PATH      Use a custom config file (default: config.json)
  --generate-config  Create a default config.json and exit
  --quiet            Minimal output — progress bar and summary only
```

## Configuration

Run `python main.py --generate-config` to create a `config.json` you can edit:

```json
{
  "edopro_path": ".",
  "concurrency": 50,
  "max_retries": 3,
  "timeout": 30,
  "sources": {
    "official": "https://images.ygoprodeck.com/images/cards",
    "backup": "https://raw.githubusercontent.com/ProjectIgnis/Images/master/pics"
  },
  "suffixes_to_strip": [" GOAT", " (Pre-Errata)", " (GOAT)", " Pre-Errata"]
}
```

CLI flags always override config file values.

## Manual Mapping

For cards that can't be auto-matched, create a `manual_map.json` in your EDOPro folder:

```json
{
  "511000818": "12345678"
}
```

This tells the tool: "for card ID 511000818, download the image for card 12345678 instead."

## Credits & License

- Original concept: [EDOPro-Hd-Downloader](https://github.com/NiiMiyo/EDOPro-Hd-Downloader) by NiiMiyo.
- Licensed under the [MIT License](LICENSE).
