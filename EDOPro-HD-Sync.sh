#!/bin/bash
# EDOPro HD Sync — Linux Launcher (single file)
#
# Double-click it (choose "Run" if your file manager asks) or run it from a
# terminal. The first time, pick your ProjectIgnis folder; it remembers it.

APP_NAME="EDOPro-HD-Sync-Linux"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SUPPORT_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/EDOPro-HD-Sync"
PREFS="$SUPPORT_DIR/edopro_folder.txt"
REPO_API="https://api.github.com/repos/cntrl-alt-lenny/EDOPro-HD-Sync/releases/latest"

mkdir -p "$SUPPORT_DIR"

# Use the app if it's shipped next to this file (zip bundle); otherwise keep it
# in a support folder so you only ever need this one file.
if [ -x "$SCRIPT_DIR/$APP_NAME" ]; then
    BINARY="$SCRIPT_DIR/$APP_NAME"
else
    BINARY="$SUPPORT_DIR/$APP_NAME"
fi

# Print the SHA-256 of a file as a bare hex string (Linux ships sha256sum).
hash_file() {
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$1" | awk '{print $1}'
    elif command -v shasum >/dev/null 2>&1; then
        shasum -a 256 "$1" | awk '{print $1}'
    fi
}

# A folder looks like EDOPro if it has the card data or images.
looks_like_edopro() {
    [ -d "$1/expansions" ] || [ -f "$1/cards.cdb" ] || [ -d "$1/pics" ]
}

# Native folder picker (zenity/kdialog), falling back to a terminal prompt.
choose_folder() {
    if command -v zenity >/dev/null 2>&1; then
        zenity --file-selection --directory \
            --title="Select your ProjectIgnis (EDOPro) folder" 2>/dev/null
    elif command -v kdialog >/dev/null 2>&1; then
        kdialog --getexistingdirectory "$HOME" \
            --title "Select your ProjectIgnis (EDOPro) folder" 2>/dev/null
    elif [ -t 0 ]; then
        local reply
        read -rp "Enter your ProjectIgnis (EDOPro) folder path: " reply
        printf '%s' "$reply"
    fi
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
    if name.startswith("EDOPro-HD-Sync-Linux-v") and name.endswith(".zip"):
        zip_url = asset["browser_download_url"]
    elif name.startswith("EDOPro-HD-Sync-Linux-v") and name.endswith(".zip.sha256"):
        sha_url = asset["browser_download_url"]

print(zip_url)
print(sha_url)
PY
)"
    ZIP_URL="$(printf '%s\n' "$ASSET_INFO" | sed -n '1p')"
    SHA_URL="$(printf '%s\n' "$ASSET_INFO" | sed -n '2p')"
    if [ -z "$ZIP_URL" ]; then
        echo "Could not find the latest Linux download in the GitHub release."
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

    if ! unzip -j "$BIN_DIR/_tmp.zip" "EDOPro HD Sync Linux/EDOPro-HD-Sync-Linux" -d "$BIN_DIR"; then
        echo "Unzip failed. The download may be corrupted."
        rm -f "$BIN_DIR/_tmp.zip"
        exit 1
    fi
    rm -f "$BIN_DIR/_tmp.zip"
    if [ ! -f "$BINARY" ]; then
        echo "Could not find the app after unzip. Please try again."
        exit 1
    fi
fi

# Some file managers strip the executable bit on extract, so re-apply it.
chmod +x "$BINARY" 2>/dev/null

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
    picked="${picked%/}"  # drop any trailing slash
    if looks_like_edopro "$picked"; then
        EDOPRO_DIR="$picked"
        printf '%s\n' "$EDOPRO_DIR" > "$PREFS"
    elif command -v zenity >/dev/null 2>&1; then
        zenity --warning --no-wrap \
            --text="That folder does not look like EDOPro.\nPlease choose your ProjectIgnis folder (it should contain expansions and pics)." \
            2>/dev/null
    else
        echo "That folder does not look like EDOPro. Try again."
    fi
done

echo "Using EDOPro folder: $EDOPRO_DIR"
echo ""

"$BINARY" --edopro-path "$EDOPRO_DIR"

echo ""
if [ -t 0 ]; then
    read -rp "Press Enter to close this window..."
fi
