#!/bin/bash
# EDOPro HD Sync — Linux Launcher
# Unzip into your EDOPro folder, then run this script (double-click in your
# file manager, or `./EDOPro-HD-Sync.sh` from a terminal).

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BINARY="$SCRIPT_DIR/EDOPro-HD-Sync-Linux"
REPO_API="https://api.github.com/repos/cntrl-alt-lenny/EDOPro-HD-Sync/releases/latest"

# Print the SHA-256 of a file as a bare hex string (Linux ships sha256sum).
hash_file() {
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$1" | awk '{print $1}'
    elif command -v shasum >/dev/null 2>&1; then
        shasum -a 256 "$1" | awk '{print $1}'
    fi
}

# Run from the EDOPro root (one level up from this script's folder),
# so the tool finds cards.cdb, expansions/, etc.
cd "$SCRIPT_DIR/.."

if [ ! -f "$BINARY" ]; then
    echo "Binary not found — downloading EDOPro HD Sync..."
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
    if ! curl -L --progress-bar "$ZIP_URL" -o "$SCRIPT_DIR/_tmp.zip"; then
        echo "Download failed. Check your internet connection and try again."
        exit 1
    fi

    # Verify the download against the published SHA-256 checksum before trusting it.
    if [ -n "$SHA_URL" ] && curl -fsSL "$SHA_URL" -o "$SCRIPT_DIR/_tmp.zip.sha256"; then
        expected="$(awk '{print $1}' "$SCRIPT_DIR/_tmp.zip.sha256")"
        actual="$(hash_file "$SCRIPT_DIR/_tmp.zip")"
        rm -f "$SCRIPT_DIR/_tmp.zip.sha256"
        if [ -z "$actual" ]; then
            echo "No SHA-256 tool found — skipping checksum verification."
        elif [ -z "$expected" ]; then
            echo "Could not read the checksum file — skipping verification."
        elif [ "$expected" != "$actual" ]; then
            echo "Checksum mismatch — the download may be corrupted or tampered with."
            echo "  expected: $expected"
            echo "  actual:   $actual"
            rm -f "$SCRIPT_DIR/_tmp.zip"
            exit 1
        else
            echo "Checksum verified."
        fi
    else
        echo "Checksum file unavailable — skipping verification."
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
