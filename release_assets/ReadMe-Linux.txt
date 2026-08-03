EDOPro HD Sync for Linux
========================

How to use it
-------------
1. Unzip the download.
2. Open the "EDOPro HD Sync" folder and run ./EDOPro-HD-Sync.sh
   (or double-click it and choose "Run").
3. The first time, pick your ProjectIgnis folder. It remembers your choice.
4. Tick what you want in the window that opens, then press Start.

The folder picker needs zenity or kdialog (installed on most desktops). If you
run it from a terminal instead, it will ask you to type the path.

Keep the two files together
---------------------------
EDOPro-HD-Sync.sh and the "app" folder next to it belong together - the
launcher installs the app from that folder on the first run. After that you
can keep or delete the extracted folder; the app lives in:
  ~/.local/share/EDOPro-HD-Sync

Helpful notes
-------------
- Everything happens in one small window: tick what you want (field art,
  only your decks, textures, repair), press Start, and watch the progress.
- Updates are automatic: when a new version is released, the launcher
  installs it on the next run (verified against GitHub's published checksum).
- Only missing artwork is downloaded, so repeat runs are fast. Tick
  "Re-download everything" in the window for a full refresh.
- "Show coverage" tells you how much artwork you have without downloading.
- Rush Duel, anime, GOAT, Pre-Errata, and alternate artworks are all covered,
  plus the playmat art for Field Spells.
- Works on Steam Deck (Desktop Mode), Ubuntu, Fedora, Arch, etc. -
  anything x86_64 Linux.

Quick sanity check
------------------
From a terminal in this folder you can also run:

app/EDOPro-HD-Sync-Linux --health-check

That runs a quick offline check to verify the tool is working correctly.
