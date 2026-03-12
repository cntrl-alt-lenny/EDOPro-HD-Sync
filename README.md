# EDOPro HD Sync

A fast HD artwork downloader for EDOPro.

It scans your local `.cdb` databases, including repository delta files used by formats like GOAT, finds missing card images, and downloads the best match automatically.

## Features

- Windows folder picker so you can choose your EDOPro install in File Explorer instead of typing a path.
- `config.json` is stored beside the executable, or beside `main.py` when running from source.
- Async downloads with retries and SSL cert bundling for packaged builds.
- Smart GOAT / Pre-Errata matching, duplicate-name fallback candidates, and optional `manual_map.json` overrides.
- Progress UI and a clearer end-of-run summary with totals, failures, speed, and runtime.
- Cross-platform release builds for Windows, macOS, and Linux.

## Quick Start

### Windows release zip

1. Download `EDOPro-HD-Sync-Windows-VERSION.zip` from the Releases page.
2. Extract the zip anywhere.
3. Run `EDOPro-HD-Sync.exe`.
4. When the folder picker opens, choose your EDOPro folder.
5. After the sync finishes, press Enter to close the window.

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
  --save-failures    Write a timestamped .txt file of cards that still failed to sync
  --no-pause         On Windows packaged builds, close immediately on exit
```

## Configuration

By default the app stores `config.json` beside the program you run:

- Packaged builds: next to `EDOPro-HD-Sync.exe`
- From source: next to `main.py`

You can still override that with `--config PATH`.

Run `python main.py --generate-config` to create an editable config file:

```json
{
  "edopro_path": ".",
  "concurrency": 50,
  "max_retries": 3,
  "timeout": 30,
  "save_failures": false,
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

This repo also includes `manual_map.json` and `manual_map.example.json` with Blue-Eyes alternate-art safety-net mappings. They are kept mainly as examples now: duplicate-name alternate arts should auto-match, and Pre-Errata cards use the built-in `card_id - 10` fallback.

## Release Icon

Windows executables need an `.ico` file, not a raw PNG. The build accepts a PNG source at `assets/app-icon.png`, converts it to `build/app-icon.ico`, and uses that for the Windows release.

## Windows Signing

Windows Smart App Control can block unfamiliar unsigned apps. To ship a signed Windows release from GitHub Actions, configure these repository settings:

- Secrets: `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, `AZURE_TENANT_ID`
- Variables: `TRUSTED_SIGNING_ACCOUNT_NAME`, `TRUSTED_SIGNING_CERTIFICATE_PROFILE_NAME`, `TRUSTED_SIGNING_ENDPOINT`

The workflow will sign `EDOPro-HD-Sync.exe` with Microsoft Trusted Signing before packaging it into `EDOPro-HD-Sync-Windows-VERSION.zip`. If they are missing, the workflow still builds the executable and ZIP but warns that Smart App Control may block it.

## Credits and License

- Original concept: [EDOPro-Hd-Downloader](https://github.com/NiiMiyo/EDOPro-Hd-Downloader) by NiiMiyo
- Licensed under the [MIT License](LICENSE)
