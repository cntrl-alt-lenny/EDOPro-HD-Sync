EDOPro HD Sync for Windows
==========================

Easiest way (one file)
----------------------
1. Download "EDOPro-HD-Sync.bat" from the release.
2. Double-click it.
3. Pick your EDOPro folder when asked (it remembers your choice).
That's it - it downloads the app and your HD card artwork, then runs.

If Windows SmartScreen warns about the .bat, click "More info" then "Run anyway"
(the app it downloads is unblocked automatically, so it won't keep prompting).

Prefer the zip?
---------------
Extract "EDOPro-HD-Sync-Windows-vVERSION.zip", open the "EDOPro HD Sync Windows"
folder, run EDOPro-HD-Sync.exe, and pick your EDOPro folder when asked.

Helpful notes
-------------
- The one-file launcher keeps the app up to date automatically: when a new version is released, it downloads it on the next run.
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
