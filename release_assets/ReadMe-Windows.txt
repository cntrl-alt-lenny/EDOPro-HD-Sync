EDOPro HD Sync for Windows
==========================

How to use it
-------------
1. Unzip the download (right-click the .zip -> "Extract All").
2. Open the "EDOPro HD Sync" folder and double-click EDOPro-HD-Sync.bat
3. Tick what you want in the window that opens, then press Start.
4. The first time, pick your EDOPro folder when asked - it remembers
   your choice from then on.

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
You can open Command Prompt in this folder and run:

app\EDOPro-HD-Sync.exe --health-check

That runs a quick offline check to verify the tool is working correctly.
