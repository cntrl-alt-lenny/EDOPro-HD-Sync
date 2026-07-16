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
INSTALLED_FILE="$SUPPORT_DIR/binary_version.txt"
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

# A folder looks like EDOPro only if it has actual card databases —
# the same test the app applies, so the two never disagree.
looks_like_edopro() {
    [ -n "$(find "$1" -maxdepth 3 -name '*.cdb' 2>/dev/null | head -1)" ]
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

# Ask GitHub for the latest release (tag + download links). Quietly does
# nothing when offline so the cached app still runs without internet.
LATEST_TAG=""
ZIP_URL=""
SHA_URL=""
fetch_release_info() {
    local json
    json="$(curl -fsSL --max-time 10 "$REPO_API" 2>/dev/null)"
    LATEST_TAG="$(printf '%s\n' "$json" | sed -n 's/.*"tag_name": *"\([^"]*\)".*/\1/p' | head -1)"
    ZIP_URL="$(printf '%s\n' "$json" | sed -n 's/.*"browser_download_url": *"\(https[^"]*EDOPro-HD-Sync-macOS-v[^"]*\.zip\)".*/\1/p' | head -1)"
    SHA_URL="$(printf '%s\n' "$json" | sed -n 's/.*"browser_download_url": *"\(https[^"]*EDOPro-HD-Sync-macOS-v[^"]*\.zip\.sha256\)".*/\1/p' | head -1)"
}

install_app() {
    # Download + verify + unpack into a scratch folder; the existing app is
    # replaced only after every step succeeds, so a failed update can never
    # break a working install.
    local bin_dir new_dir expected actual
    bin_dir="$(dirname "$BINARY")"
    new_dir="$bin_dir/_new.$$"
    rm -rf "$new_dir"
    mkdir -p "$new_dir" || return 1

    if [ -z "$ZIP_URL" ]; then
        echo "Could not find the latest macOS download in the release."
        rm -rf "$new_dir"; return 1
    fi
    if ! curl -L --progress-bar "$ZIP_URL" -o "$new_dir/app.zip"; then
        echo "Download failed."
        rm -rf "$new_dir"; return 1
    fi

    # Verify the download against the published SHA-256 checksum before trusting it.
    if [ -n "$SHA_URL" ] && curl -fsSL "$SHA_URL" -o "$new_dir/app.zip.sha256"; then
        expected="$(awk '{print $1}' "$new_dir/app.zip.sha256")"
        actual="$(hash_file "$new_dir/app.zip")"
        if [ -z "$actual" ]; then
            echo "No SHA-256 tool found — skipping checksum verification."
        elif [ -z "$expected" ]; then
            echo "Could not read the checksum file — skipping verification."
        elif [ "$expected" != "$actual" ]; then
            echo "Checksum mismatch — the download may be corrupted or tampered with."
            rm -rf "$new_dir"; return 1
        else
            echo "Checksum verified."
        fi
    else
        echo "Checksum file unavailable — skipping verification."
    fi

    if ! unzip -o -j "$new_dir/app.zip" "EDOPro HD Sync MacOS/EDOPro-HD-Sync-macOS" -d "$new_dir"; then
        echo "Unzip failed. The download may be corrupted."
        rm -rf "$new_dir"; return 1
    fi
    if [ ! -f "$new_dir/$APP_NAME" ]; then
        echo "Could not find the app inside the download."
        rm -rf "$new_dir"; return 1
    fi
    chmod +x "$new_dir/$APP_NAME"
    if ! mv -f "$new_dir/$APP_NAME" "$BINARY"; then
        rm -rf "$new_dir"; return 1
    fi
    printf '%s\n' "$LATEST_TAG" > "$INSTALLED_FILE"
    rm -rf "$new_dir"
    return 0
}

# --- Install or update the app (only the copy this launcher manages) ---
if [ "$BINARY" = "$SUPPORT_DIR/$APP_NAME" ]; then
    fetch_release_info
    if [ ! -x "$BINARY" ]; then
        echo "Setting up EDOPro HD Sync (first run)..."
        if ! install_app; then
            echo "Setup failed. Check your internet connection and try again."
            exit 1
        fi
        echo ""
    elif [ -n "$LATEST_TAG" ] && [ -n "$ZIP_URL" ]; then
        installed="$(cat "$INSTALLED_FILE" 2>/dev/null)"
        if [ "$installed" != "$LATEST_TAG" ]; then
            echo "A new version ($LATEST_TAG) is available — updating..."
            if install_app; then
                echo "Updated to $LATEST_TAG."
            else
                echo "Update failed — keeping the current version for now."
            fi
            echo ""
        fi
    fi
fi

if [ ! -x "$BINARY" ]; then
    echo "The app is missing and could not be downloaded. Please try again later."
    exit 1
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

"$BINARY" --edopro-path "$EDOPRO_DIR"

echo ""
read -rp "Press Enter to close this window..."
