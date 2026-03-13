# EDOPro HD Sync

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)
![License](https://img.shields.io/github/license/cntrl-alt-lenny/EDOPro-HD-Sync)
![Release](https://img.shields.io/github/v/release/cntrl-alt-lenny/EDOPro-HD-Sync)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)

A fast, automatic HD artwork downloader for [EDOPro](https://github.com/ProjectIgnis/EDOPro). Scans your card databases, finds missing images, and downloads the best available artwork — including GOAT, Pre-Errata, and alternate art variants.

## Quick Start

### Windows

1. Download `EDOPro-HD-Sync-Windows-VERSION.zip` from [Releases](https://github.com/cntrl-alt-lenny/EDOPro-HD-Sync/releases/latest)
2. Extract the zip
3. Run `EDOPro-HD-Sync.exe`
4. Pick your EDOPro folder when prompted

### macOS

1. Download `EDOPro-HD-Sync-macOS.zip` from [Releases](https://github.com/cntrl-alt-lenny/EDOPro-HD-Sync/releases/latest)
2. Unzip into your EDOPro folder
3. Double-click `EDOPro-HD-Sync.command`
4. If macOS asks about security, go to **System Settings → Privacy & Security** and allow it

### Linux

1. Download `EDOPro-HD-Sync-Linux.AppImage` from [Releases](https://github.com/cntrl-alt-lenny/EDOPro-HD-Sync/releases/latest)
2. Make it executable: `chmod +x EDOPro-HD-Sync-Linux.AppImage`
3. Run it from your EDOPro folder:
   ```bash
   cd /path/to/EDOPro && ./EDOPro-HD-Sync-Linux.AppImage --force
   ```

### From Source

```bash
pip install -r requirements.txt
python main.py --force
```

## How It Works

Scans all `.cdb` card databases in your EDOPro folder, identifies cards with missing artwork, and downloads HD images from [YGOProDeck](https://ygoprodeck.com) with a [ProjectIgnis](https://github.com/ProjectIgnis/Images) fallback.

- **Alternate artworks** — each art variant gets its own correct image
- **GOAT format cards** — matched to their official artwork automatically
- **Pre-Errata cards** — resolved via suffix stripping and ID offset fallback
- **Manual overrides** — optional `manual_map.json` for edge cases

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.

## Credits

- Original concept: [EDOPro-Hd-Downloader](https://github.com/NiiMiyo/EDOPro-Hd-Downloader) by NiiMiyo
- Licensed under the [MIT License](LICENSE)
