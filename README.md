# EDOPro HD Sync

A lightning-fast, automated asset downloader for EDOPro. 

This tool automatically detects which cards you have in your local EDOPro database (including Alt Arts, GOAT formats, and Anime cards) and downloads the missing HD artwork instantly.

## Features

* **Zero Configuration:** Just drop it in your EDOPro folder and run it.
* **Database Sync:** Reads your local `cards.cdb` to ensure you get artwork for *every* card you actually have installed, not just the standard meta cards.
* **Async Speed:** Uses asynchronous downloads to fetch hundreds of images simultaneously. 
* **Cross-Platform:** Works natively on Windows, Linux, and macOS.

## Installation

### Windows / macOS / Linux
1.  Go to the [Releases Page](LINK_TO_YOUR_RELEASES_PAGE_HERE).
2.  Download the executable for your system.
3.  Place the file inside your root **EDOPro** folder (where `EDOPro.exe` is located).
4.  Run the file.

## Building from Source

If you want to run the python script directly:

1.  Install Python 3.10+.
2.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```
3.  Run the script:
    ```bash
    python main.py
    ```

## Credits & License

* Original concept based on [EDOPro-Hd-Downloader](https://github.com/NiiMiyo/EDOPro-Hd-Downloader) by NiiMiyo.
* Licensed under the [MIT License](LICENSE).
