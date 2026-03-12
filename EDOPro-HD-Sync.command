#!/bin/bash
# EDOPro HD Sync — macOS Launcher
# Unzip EDOPro-HD-Sync-macOS.zip into your EDOPro folder, then double-click this file.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BINARY="$SCRIPT_DIR/EDOPro-HD-Sync-macOS"

# Run from the EDOPro root (one level up from this script's folder),
# so the tool finds cards.cdb, expansions/, etc.
cd "$SCRIPT_DIR/.."
ZIP_URL="https://github.com/cntrl-alt-lenny/EDOPro-HD-Sync/releases/latest/download/EDOPro-HD-Sync-macOS.zip"

if [ ! -f "$BINARY" ]; then
    echo "Binary not found — downloading EDOPro HD Sync..."
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

# ── Menu ──────────────────────────────────────────────────────────────────────
echo ""
echo "EDOPro HD Sync Launcher"
echo "1) Sync missing cards only"
echo "2) Refresh all card images (overwrite existing) [default]"
echo ""
read -rp "Choose [1-2] or press Enter for default: " choice
echo ""

FLAGS=()
case "$choice" in
    1) ;;
    *) FLAGS+=(--force) ;;
esac

read -rp "Save a timestamped sync report (.txt)? [y/N]: " save_report
echo ""
case "$save_report" in
    [Yy]|[Yy][Ee][Ss]) FLAGS+=(--save-report) ;;
esac

read -rp "Save a timestamped failed-card list (.txt)? [y/N]: " save_failures
echo ""
case "$save_failures" in
    [Yy]|[Yy][Ee][Ss]) FLAGS+=(--save-failures) ;;
esac

"$BINARY" "${FLAGS[@]}"

echo ""
read -rp "Press Enter to close this window..."
