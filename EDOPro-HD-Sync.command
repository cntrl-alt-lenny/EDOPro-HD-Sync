#!/bin/bash
# EDOPro HD Sync — macOS Launcher (single file)
#
# Just double-click this file. The first time, it will:
#   1. Ask you to pick your ProjectIgnis folder (it starts in Applications).
#   2. Download the app into a hidden support folder.
#   3. Download your HD card artwork into that folder.
# After that, double-click any time and it "just works" — it remembers your folder.

APP_NAME="EDOPro-HD-Sync-macOS"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SUPPORT_DIR="$HOME/Library/Application Support/EDOPro-HD-Sync"
PREFS="$SUPPORT_DIR/edopro_folder.txt"
REPO_API="https://api.github.com/repos/cntrl-alt-lenny/EDOPro-HD-Sync/releases/latest"

mkdir -p "$SUPPORT_DIR"

# Clear any quarantine flag from this launcher so future runs never prompt.
xattr -d com.apple.quarantine "$0" 2>/dev/null

# Use the app if it's shipped next to this file (zip bundle); otherwise keep it
# in the hidden support folder so you only ever need this one file.
if [ -x "$SCRIPT_DIR/$APP_NAME" ]; then
    BINARY="$SCRIPT_DIR/$APP_NAME"
else
    BINARY="$SUPPORT_DIR/$APP_NAME"
fi

# Print the SHA-256 of a file as a bare hex string (macOS ships shasum).
hash_file() {
    if command -v shasum >/dev/null 2>&1; then
        shasum -a 256 "$1" | awk '{print $1}'
    elif command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$1" | awk '{print $1}'
    fi
}

# A folder looks like EDOPro if it has the card data or images.
looks_like_edopro() {
    [ -d "$1/expansions" ] || [ -f "$1/cards.cdb" ] || [ -d "$1/pics" ]
}

# Native "choose folder" dialog, starting in the ProjectIgnis folder if present.
choose_folder() {
    local default_loc="/Applications"
    [ -d "/Applications/ProjectIgnis" ] && default_loc="/Applications/ProjectIgnis"
    osascript <<OSA 2>/dev/null
try
    set chosen to choose folder with prompt "Select your ProjectIgnis (EDOPro) folder" default location (POSIX file "$default_loc")
    POSIX path of chosen
on error
    ""
end try
OSA
}

# --- Download the app if we don't have it yet ---
if [ ! -x "$BINARY" ]; then
    BIN_DIR="$(dirname "$BINARY")"
    echo "Setting up EDOPro HD Sync (first run)..."
    ASSET_INFO="$(python3 - "$REPO_API" <<'PY'
import json
import sys
import urllib.request

api_url = sys.argv[1]
with urllib.request.urlopen(api_url, timeout=20) as response:
    data = json.load(response)

zip_url = ""
sha_url = ""
for asset in data.get("assets", []):
    name = asset.get("name", "")
    if name.startswith("EDOPro-HD-Sync-macOS-v") and name.endswith(".zip"):
        zip_url = asset["browser_download_url"]
    elif name.startswith("EDOPro-HD-Sync-macOS-v") and name.endswith(".zip.sha256"):
        sha_url = asset["browser_download_url"]

print(zip_url)
print(sha_url)
PY
)"
    ZIP_URL="$(printf '%s\n' "$ASSET_INFO" | sed -n '1p')"
    SHA_URL="$(printf '%s\n' "$ASSET_INFO" | sed -n '2p')"
    if [ -z "$ZIP_URL" ]; then
        echo "Could not find the latest macOS download in the GitHub release."
        exit 1
    fi
    if ! curl -L --progress-bar "$ZIP_URL" -o "$BIN_DIR/_tmp.zip"; then
        echo "Download failed. Check your internet connection and try again."
        exit 1
    fi

    # Verify the download against the published SHA-256 checksum before trusting it.
    if [ -n "$SHA_URL" ] && curl -fsSL "$SHA_URL" -o "$BIN_DIR/_tmp.zip.sha256"; then
        expected="$(awk '{print $1}' "$BIN_DIR/_tmp.zip.sha256")"
        actual="$(hash_file "$BIN_DIR/_tmp.zip")"
        rm -f "$BIN_DIR/_tmp.zip.sha256"
        if [ -z "$actual" ]; then
            echo "No SHA-256 tool found — skipping checksum verification."
        elif [ -z "$expected" ]; then
            echo "Could not read the checksum file — skipping verification."
        elif [ "$expected" != "$actual" ]; then
            echo "Checksum mismatch — the download may be corrupted or tampered with."
            rm -f "$BIN_DIR/_tmp.zip"
            exit 1
        else
            echo "Checksum verified."
        fi
    else
        echo "Checksum file unavailable — skipping verification."
    fi

    if ! unzip -j "$BIN_DIR/_tmp.zip" "EDOPro HD Sync MacOS/EDOPro-HD-Sync-macOS" -d "$BIN_DIR"; then
        echo "Unzip failed. The download may be corrupted."
        rm -f "$BIN_DIR/_tmp.zip"
        exit 1
    fi
    rm -f "$BIN_DIR/_tmp.zip"
    if [ ! -f "$BINARY" ]; then
        echo "Could not find the app after unzip. Please try again."
        exit 1
    fi
    chmod +x "$BINARY"
    echo ""
fi

# Clear the quarantine flag from the app so it runs without a Gatekeeper prompt.
xattr -d com.apple.quarantine "$BINARY" 2>/dev/null

# --- Figure out which folder is your EDOPro/ProjectIgnis install ---
EDOPRO_DIR=""
if [ -f "$PREFS" ]; then
    saved="$(cat "$PREFS" 2>/dev/null)"
    if [ -n "$saved" ] && looks_like_edopro "$saved"; then
        EDOPRO_DIR="$saved"
    fi
fi

while [ -z "$EDOPRO_DIR" ]; do
    picked="$(choose_folder)"
    if [ -z "$picked" ]; then
        echo "No folder selected. Exiting."
        exit 1
    fi
    picked="${picked%/}"  # POSIX path of a folder ends in a slash; drop it
    if looks_like_edopro "$picked"; then
        EDOPRO_DIR="$picked"
        printf '%s\n' "$EDOPRO_DIR" > "$PREFS"
    else
        osascript -e 'display dialog "That folder does not look like EDOPro. Please choose your ProjectIgnis folder (it should contain the expansions and pics folders)." buttons {"Try Again"} default button 1 with icon caution' >/dev/null 2>&1
    fi
done

echo "Using EDOPro folder: $EDOPRO_DIR"
echo ""

"$BINARY" --force --edopro-path "$EDOPRO_DIR"

echo ""
read -rp "Press Enter to close this window..."
