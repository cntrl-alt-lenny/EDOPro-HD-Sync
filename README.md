# EDOPro HD Sync

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)
![License](https://img.shields.io/github/license/cntrl-alt-lenny/EDOPro-HD-Sync)
![Release](https://img.shields.io/github/v/release/cntrl-alt-lenny/EDOPro-HD-Sync)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)

A fast, automatic HD artwork downloader for [EDOPro](https://github.com/edo9300/edopro). Scans your card databases, finds missing images, and downloads the best available artwork — including GOAT, Pre-Errata, and alternate art variants.

## Quick Start

### Windows

1. Download `EDOPro HD Sync - Windows Version (VERSION).zip` from [Releases](https://github.com/cntrl-alt-lenny/EDOPro-HD-Sync/releases/latest)
2. Extract the zip and open the `EDOPro HD Sync Windows` folder
3. Run `EDOPro-HD-Sync.exe`
4. Pick your EDOPro folder when prompted
5. The bundle includes a Windows `ReadMe.txt` with the same steps

### macOS

1. Download `EDOPro HD Sync - MacOS Version (VERSION).zip` from [Releases](https://github.com/cntrl-alt-lenny/EDOPro-HD-Sync/releases/latest)
2. Unzip into your EDOPro folder and open the `EDOPro HD Sync MacOS` folder
3. Double-click `EDOPro-HD-Sync.command`
4. If macOS asks about security, go to **System Settings → Privacy & Security** and allow it
5. The bundle includes a Mac-specific `ReadMe.txt`

### Linux

1. Download `EDOPro HD Sync - Linux Version (VERSION).zip` from [Releases](https://github.com/cntrl-alt-lenny/EDOPro-HD-Sync/releases/latest)
2. Extract it and open the `EDOPro HD Sync Linux` folder
3. Make the AppImage executable: `chmod +x EDOPro-HD-Sync-Linux.AppImage`
4. Run it from your EDOPro folder, or let it prompt you to choose the folder:
   ```bash
   cd /path/to/EDOPro && /path/to/EDOPro\ HD\ Sync\ Linux/EDOPro-HD-Sync-Linux.AppImage
   ```
5. The bundle includes a Linux `ReadMe.txt`

### From Source

```bash
pip install -r requirements.txt
python main.py --force
python main.py --health-check
```

## How It Works

Scans all `.cdb` card databases in your EDOPro folder, identifies cards with missing artwork, and downloads HD images from [YGOProDeck](https://ygoprodeck.com) with a [ProjectIgnis](https://github.com/ProjectIgnis/Images) fallback.

- **Alternate artworks** — each art variant gets its own correct image
- **Alternate-art cache** — confirmed multi-art IDs are cached locally so future runs are faster and less dependent on live API responses
- **GOAT format cards** — matched to their official artwork automatically
- **Pre-Errata cards** — resolved via suffix stripping and ID offset fallback
- **Manual overrides** — optional `manual_map.json` for edge cases

## Helpful Commands

- `python main.py --health-check` runs an offline sanity check for Blue-Eyes, Dark Magician, Red-Eyes, and Pre-Errata matching logic
- `python main.py --dry-run` previews what would be downloaded

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.

## Credits

- Original concept: [EDOPro-Hd-Downloader](https://github.com/NiiMiyo/EDOPro-Hd-Downloader) by NiiMiyo
- Licensed under the [MIT License](LICENSE)
