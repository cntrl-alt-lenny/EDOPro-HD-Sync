EDOPro HD Sync for Windows
==========================

1. Extract this zip anywhere you like.
2. Open the "EDOPro HD Sync Windows" folder.
3. Run EDOPro-HD-Sync.exe.
4. Pick your EDOPro folder when the tool asks for it.

Helpful notes
-------------
- Packaged builds refresh artwork automatically, so you do not need to add --force.
- The tool remembers your chosen EDOPro folder in config.json beside the exe.
- The tool tries YGOProDeck first for HD art, then falls back to ProjectIgnis.
- If Windows warns about the app, click "More info" and then "Run anyway" unless your release notes say the build is signed.

Quick sanity check
------------------
You can open Command Prompt in this folder and run:

EDOPro-HD-Sync.exe --health-check

That runs a quick offline check to verify the tool is working correctly.
