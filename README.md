# EDOPro HD Sync

A fast HD artwork downloader for EDOPro.

It scans your local `.cdb` databases, finds missing card images, and downloads the best match automatically.

## Features

- Windows folder picker so you can choose your EDOPro install in File Explorer instead of typing a path.
- Clean per-user config storage, so the app does not drop `config.json` beside itself on first run.
- Portable Windows release bundle that runs through Python's signed embedded runtime instead of a custom unsigned `.exe`.
- Async downloads with retries and SSL cert bundling for packaged builds.
- Smart GOAT / Pre-Errata matching plus optional `manual_map.json` overrides.
- Progress UI and a clearer end-of-run summary with totals, failures, speed, and runtime.
- Cross-platform release builds for Windows, macOS, and Linux.

## Quick Start

### Windows release bundle

1. Download `EDOPro-HD-Sync-Windows.zip` from the Releases page.
2. Extract the zip anywhere.
3. Double-click `EDOPro-HD-Sync.cmd`.
4. When the folder picker opens, choose your EDOPro folder.
5. After the sync finishes, press any key to close the window.

### From source

```bash
pip install -r requirements.txt
python main.py
```

## CLI Options

```text
python main.py [OPTIONS]

Options:
  --force            Re-download ALL images, even existing ones
  --dry-run          Preview what would be downloaded (no actual downloads)
  --concurrency N    Max simultaneous downloads (default: 50)
  --max-retries N    Retry failed downloads N times (default: 3)
  --timeout N        HTTP timeout in seconds (default: 30)
  --config PATH      Use a custom config file
  --generate-config  Create a default config file and exit
  --quiet            Minimal output - progress bar and summary only
  --save-report      Write a timestamped .txt sync report in the EDOPro folder
  --no-pause         On Windows packaged builds, close immediately on exit
```

## Configuration

By default the app stores config in a per-user location instead of the executable folder:

- Windows: `%APPDATA%\EDOPro-HD-Sync\config.json`
- macOS: `~/Library/Application Support/EDOPro-HD-Sync/config.json`
- Linux: `$XDG_CONFIG_HOME/EDOPro-HD-Sync/config.json` or `~/.config/EDOPro-HD-Sync/config.json`

You can still override that with `--config PATH`.

Run `python main.py --generate-config` to create an editable config file:

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

## Manual Mapping

For cards that cannot be auto-matched, create `manual_map.json` in your EDOPro folder:

```json
{
  "511000818": "12345678"
}
```

That tells the app to download the image for `12345678` and save it as `511000818.jpg`.

## Release Icon

Windows executables need an `.ico` file, not a raw PNG. The build accepts a PNG source at `assets/app-icon.png`, converts it to `build/app-icon.ico`, and uses that for the macOS/Linux packaged artifacts. The Windows release is currently a portable `.zip` bundle instead of a custom `.exe`, specifically to avoid Smart App Control blocking an unsigned binary.

## Credits and License

- Original concept: [EDOPro-Hd-Downloader](https://github.com/NiiMiyo/EDOPro-Hd-Downloader) by NiiMiyo
- Licensed under the [MIT License](LICENSE)
