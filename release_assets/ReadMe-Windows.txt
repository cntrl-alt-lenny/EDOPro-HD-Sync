EDOPro HD Sync for Windows
==========================

How to use it
-------------
1. Unzip the download (right-click the .zip -> "Extract All").
2. Open the "EDOPro HD Sync" folder and double-click EDOPro-HD-Sync.bat
3. Pick your EDOPro folder when asked (it remembers your choice).
4. Tick what you want in the window that opens, then press Start.

If Windows SmartScreen warns about the .bat, click "More info" then
"Run anyway".

Keep the two files together
---------------------------
EDOPro-HD-Sync.bat and the "app" folder next to it belong together - the
launcher installs the app from that folder on the first run. After that you
can keep or delete the extracted folder; the app lives in:
  %LOCALAPPDATA%\EDOPro-HD-Sync

Helpful notes
-------------
- The app opens a small window: tick what you want (field art, only your decks, textures, repair), press Start, and watch the progress right in the window.
- The launcher keeps the app up to date automatically: when a new version is released, it installs it on the next run (verified against GitHub's published checksum).
- It downloads only missing artwork by default (fast). To re-download everything, answer "y" when it offers a full refresh, or run with --force.
- The tool remembers your chosen EDOPro folder in config.json beside the exe.
- The tool tries YGOProDeck first for HD art, then falls back to ProjectIgnis.
- Multi-art cards (e.g. Ring of Destruction, Rescue Cat) get distinct artwork for each variant automatically.
- You can also download curated textures (custom backgrounds & card sleeves): answer "y" when the tool asks, or run with --textures.
- If Windows warns about the app, click "More info" and then "Run anyway" unless your release notes say the build is signed.

Quick sanity check
------------------
You can open Command Prompt in this folder and run:

EDOPro-HD-Sync.exe --health-check

That runs a quick offline check to verify the tool is working correctly.
