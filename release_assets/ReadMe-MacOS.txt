EDOPro HD Sync for macOS
========================

How to use it
-------------
1. Unzip the download (double-click the .zip in Finder).
2. Open the "EDOPro HD Sync" folder and double-click EDOPro-HD-Sync.command
3. The first time, pick your ProjectIgnis folder (the dialog starts in
   Applications). It remembers your choice for next time.
4. Tick what you want in the window that opens, then press Start.

If macOS asks the very first time
---------------------------------
Because the file came from the web, macOS may ask once before opening it.
Just RIGHT-CLICK EDOPro-HD-Sync.command and choose "Open" (then "Open" again).
You do NOT need to go into System Settings. After that it opens normally.

Keep the two files together
---------------------------
EDOPro-HD-Sync.command and the "app" folder next to it belong together - the
launcher installs the app from that folder on the first run. After that you
can keep or delete the extracted folder; the app lives in:
  ~/Library/Application Support/EDOPro-HD-Sync

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

Quick sanity check
------------------
Advanced users can run a quick offline self-test in Terminal:

  "~/Library/Application Support/EDOPro-HD-Sync/EDOPro-HD-Sync-macOS" --health-check
