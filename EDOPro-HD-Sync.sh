#!/bin/bash
# EDOPro HD Sync — Linux Launcher
#
# Unzip the download, then run ./EDOPro-HD-Sync.sh (or double-click it and
# choose "Run"). The first time it asks for your ProjectIgnis folder; after
# that it just works. The app that ships next to this launcher is installed
# into a support folder and kept up to date automatically.

APP_NAME="EDOPro-HD-Sync-Linux"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SUPPORT_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/EDOPro-HD-Sync"
PREFS="$SUPPORT_DIR/edopro_folder.txt"
INSTALLED_FILE="$SUPPORT_DIR/binary_version.txt"
REPO_API="https://api.github.com/repos/cntrl-alt-lenny/EDOPro-HD-Sync/releases/latest"

# The launcher always runs the copy it manages here, so updates work the same
# whether you kept the extracted folder or moved this file somewhere else.
APP_DIR="$SUPPORT_DIR/app"
BINARY="$APP_DIR/$APP_NAME"
BUNDLED_DIR="$SCRIPT_DIR/app"
BUNDLED="$BUNDLED_DIR/$APP_NAME"

mkdir -p "$SUPPORT_DIR"

# Print the SHA-256 of a file as a bare hex string (Linux ships sha256sum).
hash_file() {
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$1" | awk '{print $1}'
    elif command -v shasum >/dev/null 2>&1; then
        shasum -a 256 "$1" | awk '{print $1}'
    fi
}

# A folder looks like EDOPro only if it has actual card databases —
# mirroring the app's own get_db_files() rule exactly.
looks_like_edopro() {
    [ -f "$1/cards.cdb" ] && return 0
    [ -n "$(find "$1/expansions" -maxdepth 1 -name '*.cdb' 2>/dev/null | head -1)" ] && return 0
    [ -n "$(find "$1/repositories" -name '*.delta.cdb' 2>/dev/null | head -1)" ] && return 0
    return 1
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

# Ask GitHub for the latest release: tag, download URL, and the SHA-256 digest
# GitHub publishes for the asset. Silent when offline so the app still runs.
LATEST_TAG=""
ZIP_URL=""
ZIP_DIGEST=""
fetch_release_info() {
    local json
    json="$(curl -fsSL --max-time 10 "$REPO_API" 2>/dev/null)" || return 0
    LATEST_TAG="$(printf '%s\n' "$json" | sed -n 's/.*"tag_name": *"\([^"]*\)".*/\1/p' | head -1)"
    ZIP_URL="$(printf '%s\n' "$json" | awk '/"name": "EDOPro-HD-Sync-Linux-v/{f=1} f && /"browser_download_url":/{sub(/.*": "/,""); sub(/".*/,""); print; exit}')"
    ZIP_DIGEST="$(printf '%s\n' "$json" | awk '/"name": "EDOPro-HD-Sync-Linux-v/{f=1} f && /"digest":/{sub(/.*sha256:/,""); sub(/".*/,""); print; exit}')"
}

# Download the release zip, verify it, and install the app from it. The old
# app is replaced only after every step succeeds, so a failed update can
# never break a working install.
install_from_release() {
    local new_dir actual src
    new_dir="$SUPPORT_DIR/_new.$$"
    rm -rf "$SUPPORT_DIR"/_new.* 2>/dev/null  # sweep scratch dirs orphaned by interrupts
    mkdir -p "$new_dir" || return 1

    if [ -z "$ZIP_URL" ]; then
        echo "Could not find the latest Linux download in the release."
        rm -rf "$new_dir"; return 1
    fi
    if ! curl -L --progress-bar "$ZIP_URL" -o "$new_dir/app.zip"; then
        echo "Download failed."
        rm -rf "$new_dir"; return 1
    fi

    if [ -n "$ZIP_DIGEST" ]; then
        actual="$(hash_file "$new_dir/app.zip")"
        if [ -z "$actual" ]; then
            echo "No SHA-256 tool found — skipping verification."
        elif [ "$actual" != "$ZIP_DIGEST" ]; then
            echo "Checksum mismatch — the download may be corrupted or tampered with."
            rm -rf "$new_dir"; return 1
        else
            echo "Download verified."
        fi
    fi

    if ! unzip -q "$new_dir/app.zip" -d "$new_dir/x"; then
        echo "Unzip failed. The download may be corrupted."
        rm -rf "$new_dir"; return 1
    fi
    src="$(find "$new_dir/x" -maxdepth 2 -type d -name app 2>/dev/null | head -1)"
    if [ -z "$src" ] || [ ! -x "$src/$APP_NAME" ]; then
        echo "Could not find the app inside the download."
        rm -rf "$new_dir"; return 1
    fi
    chmod +x "$src/$APP_NAME" 2>/dev/null
    if ! swap_in_app_dir "$src"; then
        rm -rf "$new_dir"; return 1
    fi
    printf '%s\n' "$LATEST_TAG" > "$INSTALLED_FILE"
    rm -rf "$new_dir"
    return 0
}

# Replace the installed app folder with a new one, keeping the old copy until
# the swap succeeds so a failure can never leave a half-installed app.
swap_in_app_dir() {
    local src="$1" backup="$APP_DIR.old.$$"
    rm -rf "$APP_DIR".old.* 2>/dev/null
    if [ -d "$APP_DIR" ] && ! mv "$APP_DIR" "$backup"; then
        return 1
    fi
    if ! mv "$src" "$APP_DIR"; then
        [ -d "$backup" ] && mv "$backup" "$APP_DIR"
        return 1
    fi
    rm -rf "$backup"
    return 0
}

# Install the app that shipped next to this launcher — no download needed.
seed_from_bundle() {
    local staging="$SUPPORT_DIR/_seed.$$"
    rm -rf "$SUPPORT_DIR"/_seed.* 2>/dev/null
    cp -R "$BUNDLED_DIR" "$staging" || return 1
    chmod +x "$staging/$APP_NAME" 2>/dev/null
    if ! swap_in_app_dir "$staging"; then
        rm -rf "$staging"; return 1
    fi
    if [ -f "$BUNDLED_DIR/version.txt" ]; then
        cat "$BUNDLED_DIR/version.txt" > "$INSTALLED_FILE"
        printf '\n' >> "$INSTALLED_FILE"
    else
        : > "$INSTALLED_FILE"
    fi
    return 0
}

fetch_release_info

if [ ! -x "$BINARY" ]; then
    if [ -f "$BUNDLED" ]; then
        echo "Setting up EDOPro HD Sync..."
        if ! seed_from_bundle; then
            echo "Could not install the app. Please re-download and try again."
            exit 1
        fi
    else
        echo "Setting up EDOPro HD Sync (first run)..."
        if ! install_from_release; then
            echo "Setup failed. Check your internet connection and try again."
            exit 1
        fi
    fi
    echo ""
elif [ -n "$LATEST_TAG" ] && [ -n "$ZIP_URL" ]; then
    installed="$(cat "$INSTALLED_FILE" 2>/dev/null | tr -d '[:space:]')"
    if [ "$installed" != "$LATEST_TAG" ]; then
        echo "A new version ($LATEST_TAG) is available — updating..."
        if install_from_release; then
            echo "Updated to $LATEST_TAG."
        else
            echo "Update failed — keeping the current version for now."
        fi
        echo ""
    fi
fi

if [ ! -x "$BINARY" ]; then
    echo "The app is missing and could not be installed. Please try again later."
    exit 1
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
