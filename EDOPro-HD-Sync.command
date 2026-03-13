#!/bin/bash
# EDOPro HD Sync — macOS Launcher
# Unzip into your EDOPro folder, then double-click this file.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BINARY="$SCRIPT_DIR/EDOPro-HD-Sync-macOS"
REPO_API="https://api.github.com/repos/cntrl-alt-lenny/EDOPro-HD-Sync/releases/latest"

# Run from the EDOPro root (one level up from this script's folder),
# so the tool finds cards.cdb, expansions/, etc.
cd "$SCRIPT_DIR/.."

if [ ! -f "$BINARY" ]; then
    echo "Binary not found — downloading EDOPro HD Sync..."
    ZIP_URL="$(python3 - "$REPO_API" <<'PY'
import json
import sys
import urllib.request

api_url = sys.argv[1]
with urllib.request.urlopen(api_url, timeout=20) as response:
    data = json.load(response)

for asset in data.get("assets", []):
    name = asset.get("name", "")
    if name.startswith("EDOPro HD Sync - MacOS Version (") and name.endswith(".zip"):
        print(asset["browser_download_url"])
        break
PY
)"
    if [ -z "$ZIP_URL" ]; then
        echo "Could not find the latest macOS download in the GitHub release."
        exit 1
    fi
    if ! curl -L --progress-bar "$ZIP_URL" -o "$SCRIPT_DIR/_tmp.zip"; then
        echo "Download failed. Check your internet connection and try again."
        exit 1
    fi
    if ! unzip -j "$SCRIPT_DIR/_tmp.zip" "EDOPro HD Sync MacOS/EDOPro-HD-Sync-macOS" -d "$SCRIPT_DIR"; then
        echo "Unzip failed. The download may be corrupted."
        rm -f "$SCRIPT_DIR/_tmp.zip"
        exit 1
    fi
    rm "$SCRIPT_DIR/_tmp.zip"
    if [ ! -f "$BINARY" ]; then
        echo "Could not find the app after unzip. Please re-download the zip."
        exit 1
    fi
    chmod +x "$BINARY"
    echo ""
fi

# Clear the macOS quarantine flag from the binary so it runs without
# triggering a second (or third) Gatekeeper security warning.
xattr -d com.apple.quarantine "$BINARY" 2>/dev/null

"$BINARY" --force

echo ""
read -rp "Press Enter to close this window..."
