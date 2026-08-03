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
- The app opens a small window: tick what you want (field art, only your decks, textures, repair), press Start, and watch the progress right in the window.
- The launcher keeps the app up to date automatically: when a new version is released, it installs it on the next run (verified against GitHub's published checksum).
- It downloads only missing artwork by default (fast). If everything is already there it offers to re-download all; or run with --force.
- The launcher and its settings live in:
  ~/Library/Application Support/EDOPro-HD-Sync
- The tool tries YGOProDeck first for HD art, then falls back to ProjectIgnis.
- Multi-art cards (e.g. Ring of Destruction, Rescue Cat) get distinct artwork
  for each variant automatically.
- You can also download curated textures (custom backgrounds & card sleeves):
  answer "y" when the tool asks.

Quick sanity check
------------------
Advanced users can run a quick offline self-test in Terminal:

  "~/Library/Application Support/EDOPro-HD-Sync/EDOPro-HD-Sync-macOS" --health-check
