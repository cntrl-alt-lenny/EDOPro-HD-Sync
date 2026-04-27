EDOPro HD Sync for Linux
========================

1. Unzip into your EDOPro folder.
2. Open the "EDOPro HD Sync Linux" folder.
3. Double-click EDOPro-HD-Sync.sh.
   (If your file manager opens it as text instead, right-click it and pick
   "Run" or "Run in Konsole" / "Run in Terminal".)

If double-click doesn't work, open a terminal in this folder and run:

./EDOPro-HD-Sync.sh

Helpful notes
-------------
- The launcher downloads the latest binary automatically if EDOPro-HD-Sync-Linux is missing.
- Packaged builds refresh artwork automatically, so you do not need to add --force.
- config.json is saved beside the launcher in this folder.
- The tool tries YGOProDeck first for HD art, then falls back to ProjectIgnis.
- Multi-art cards (e.g. Ring of Destruction, Rescue Cat) get distinct artwork for each variant automatically.
- Works on Steam Deck (Desktop Mode), Ubuntu, Fedora, Arch, etc. — anything x86_64 Linux.

Quick sanity check
------------------
From a terminal in this folder you can also run:

./EDOPro-HD-Sync-Linux --health-check

That runs a quick offline check to verify the tool is working correctly.
