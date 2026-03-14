EDOPro HD Sync for Linux
========================

1. Extract this zip anywhere you like.
2. Open the "EDOPro HD Sync Linux" folder.
3. Make the AppImage executable:

chmod +x EDOPro-HD-Sync-Linux.AppImage

4. Run it:

./EDOPro-HD-Sync-Linux.AppImage

Helpful notes
-------------
- If you run it outside your EDOPro folder, the tool will ask you to choose the correct folder.
- Packaged builds refresh artwork automatically, so you do not need to add --force.
- config.json is saved beside the AppImage.
- The tool tries YGOProDeck first for HD art, then falls back to ProjectIgnis.

Quick sanity check
------------------
You can run:

./EDOPro-HD-Sync-Linux.AppImage --health-check

That runs a quick offline check to verify the tool is working correctly.
