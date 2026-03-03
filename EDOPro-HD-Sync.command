#!/bin/bash
# EDOPro HD Sync — macOS Launcher
# First run: downloads the binary into the same folder, then runs it.
# Every run after that: launches immediately.

cd "$(dirname "$0")"

BINARY="EDOPro-HD-Sync-macOS"
URL="https://github.com/cntrl-alt-lenny/EDOPro-HD-Sync/releases/latest/download/EDOPro-HD-Sync-macOS"

if [ ! -f "$BINARY" ]; then
    echo "First run — downloading EDOPro HD Sync binary..."
    curl -L --progress-bar "$URL" -o "$BINARY"
    chmod +x "$BINARY"
    echo ""
fi

./"$BINARY" "$@"

echo ""
read -rp "Press Enter to close this window..."
