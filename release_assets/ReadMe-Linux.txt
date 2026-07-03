EDOPro HD Sync for Linux
========================

Easiest way (one file)
----------------------
1. Download "EDOPro-HD-Sync.sh" from the release.
2. Run it: ./EDOPro-HD-Sync.sh   (or double-click and choose "Run").
3. Pick your ProjectIgnis folder when asked (it remembers your choice).
That's it - it downloads the app and your HD card artwork, then runs.

The folder picker needs zenity or kdialog (installed on most desktops). If you
run it from a terminal instead, it will ask you to type the path.

Prefer the zip?
---------------
Unzip "EDOPro-HD-Sync-Linux-vVERSION.zip", open the "EDOPro HD Sync Linux"
folder, and run ./EDOPro-HD-Sync.sh from there.

Helpful notes
-------------
- A small options window opens first: tick what you want (field art, only your decks, textures, repair) and press Start.
- The launcher downloads the app automatically and keeps it up to date when new versions are released.
- It downloads only missing artwork by default (fast). To re-download everything, answer "y" when it offers a full refresh, or run with --force.
- It remembers your chosen EDOPro folder for next time.
- The tool tries YGOProDeck first for HD art, then falls back to ProjectIgnis.
- Multi-art cards (e.g. Ring of Destruction, Rescue Cat) get distinct artwork for each variant automatically.
- You can also download curated textures (custom backgrounds & card sleeves): answer "y" when the tool asks, or run with --textures.
- Works on Steam Deck (Desktop Mode), Ubuntu, Fedora, Arch, etc. — anything x86_64 Linux.

Quick sanity check
------------------
From a terminal in this folder you can also run:

./EDOPro-HD-Sync-Linux --health-check

That runs a quick offline check to verify the tool is working correctly.
