EDOPro HD Sync for macOS
========================

Easiest way (one file)
----------------------
1. Download "EDOPro-HD-Sync.command" from the release.
2. Double-click it.
3. The first time, pick your ProjectIgnis folder (the dialog starts in
   Applications). It remembers your choice for next time.
4. That's it - it downloads the app and your HD card artwork, then runs.

If macOS asks the very first time
---------------------------------
Because the file came from the web, macOS may ask once before opening it.
Just RIGHT-CLICK the file and choose "Open" (then "Open" again). You do NOT
need to go into System Settings. After the first run it opens normally.

(The app itself is downloaded behind the scenes and is not flagged by macOS,
so only this launcher file may prompt, and only once.)

Prefer the zip?
---------------
The "EDOPro-HD-Sync-macOS-vVERSION.zip" still works: unzip it, open the
"EDOPro HD Sync MacOS" folder, and double-click EDOPro-HD-Sync.command inside.

Helpful notes
-------------
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
