EDOPro HD Sync for Linux
========================

How to use it
-------------
1. Unzip the download.
2. Open the "EDOPro HD Sync" folder and run ./EDOPro-HD-Sync.sh
   (or double-click it and choose "Run").
3. The first time, pick your ProjectIgnis folder. It remembers your choice.
4. Tick what you want in the window that opens, then press Start.

The folder picker needs zenity or kdialog (installed on most desktops). If you
run it from a terminal instead, it will ask you to type the path.

Keep the two files together
---------------------------
EDOPro-HD-Sync.sh and the "app" folder next to it belong together - the
launcher installs the app from that folder on the first run. After that you
can keep or delete the extracted folder; the app lives in:
  ~/.local/share/EDOPro-HD-Sync

Helpful notes
-------------
- The app opens a small window: tick what you want (field art, only your decks, textures, repair), press Start, and watch the progress right in the window.
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
