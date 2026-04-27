#!/bin/bash
# EDOPro HD Sync — Linux Launcher
# Unzip into your EDOPro folder, then run this script (double-click in your
# file manager, or `./EDOPro-HD-Sync.sh` from a terminal).

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BINARY="$SCRIPT_DIR/EDOPro-HD-Sync-Linux"
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
    if name.startswith("EDOPro-HD-Sync-Linux-v") and name.endswith(".zip"):
        print(asset["browser_download_url"])
        break
PY
)"
    if [ -z "$ZIP_URL" ]; then
        echo "Could not find the latest Linux download in the GitHub release."
        exit 1
    fi
    if ! curl -L --progress-bar "$ZIP_URL" -o "$SCRIPT_DIR/_tmp.zip"; then
        echo "Download failed. Check your internet connection and try again."
        exit 1
    fi
    if ! unzip -j "$SCRIPT_DIR/_tmp.zip" "EDOPro HD Sync Linux/EDOPro-HD-Sync-Linux" -d "$SCRIPT_DIR"; then
        echo "Unzip failed. The download may be corrupted."
        rm -f "$SCRIPT_DIR/_tmp.zip"
        exit 1
    fi
    rm "$SCRIPT_DIR/_tmp.zip"
    if [ ! -f "$BINARY" ]; then
        echo "Could not find the app after unzip. Please re-download the zip."
        exit 1
    fi
    echo ""
fi

# Some file managers strip the executable bit on extract, so re-apply it.
chmod +x "$BINARY" 2>/dev/null

"$BINARY" --force

echo ""
read -rp "Press Enter to close this window..."
