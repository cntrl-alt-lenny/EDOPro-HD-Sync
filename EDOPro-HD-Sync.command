#!/bin/bash
# EDOPro HD Sync — macOS Launcher
# Unzip EDOPro-HD-Sync-macOS.zip into your EDOPro folder, then double-click this file.

cd "$(dirname "$0")"

BINARY="EDOPro-HD-Sync-macOS"
ZIP_URL="https://github.com/cntrl-alt-lenny/EDOPro-HD-Sync/releases/latest/download/EDOPro-HD-Sync-macOS.zip"

if [ ! -f "$BINARY" ]; then
    echo "Binary not found — downloading EDOPro HD Sync..."
    if ! curl -L --progress-bar "$ZIP_URL" -o _tmp.zip; then
        echo "Download failed. Check your internet connection and try again."
        exit 1
    fi
    if ! unzip -j _tmp.zip "$BINARY" -d .; then
        echo "Unzip failed. The download may be corrupted."
        rm -f _tmp.zip
        exit 1
    fi
    rm _tmp.zip
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
echo "  ╔══════════════════════════════════════╗"
echo "  ║        EDOPro HD Sync Launcher       ║"
echo "  ╠══════════════════════════════════════╣"
echo "  ║  1) Sync missing cards  (default)    ║"
echo "  ║  2) Force re-download all cards      ║"
echo "  ║  3) Preview only — no downloading    ║"
echo "  ║  4) Generate a config file           ║"
echo "  ╚══════════════════════════════════════╝"
echo ""
read -rp "  Choose [1-4] or press Enter for default: " choice
echo ""

case "$choice" in
    2) FLAGS="--force" ;;
    3) FLAGS="--dry-run" ;;
    4) FLAGS="--generate-config" ;;
    *) FLAGS="" ;;
esac

./"$BINARY" $FLAGS

echo ""
read -rp "Press Enter to close this window..."
