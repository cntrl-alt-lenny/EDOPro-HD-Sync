#!/bin/bash
# EDOPro HD Sync — macOS Launcher
# Unzip EDOPro-HD-Sync-macOS.zip into your EDOPro folder, then double-click this file.

cd "$(dirname "$0")"

BINARY="EDOPro-HD-Sync-macOS"
ZIP_URL="https://github.com/cntrl-alt-lenny/EDOPro-HD-Sync/releases/latest/download/EDOPro-HD-Sync-macOS.zip"

if [ ! -f "$BINARY" ]; then
    echo "Binary not found — downloading EDOPro HD Sync..."
    curl -L --progress-bar "$ZIP_URL" -o _tmp.zip
    unzip -j _tmp.zip "$BINARY" -d .
    rm _tmp.zip
    chmod +x "$BINARY"
    echo ""
fi

./"$BINARY" "$@"

echo ""
read -rp "Press Enter to close this window..."
