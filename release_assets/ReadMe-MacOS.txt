EDOPro HD Sync for macOS
========================

What it does
------------
Downloads the missing HD card artwork for EDOPro (ProjectIgnis), so your
cards look sharp instead of blurry. Rush Duel, anime, GOAT, Pre-Errata and
alternate artworks are all covered, plus the playmat art for Field Spells.

How to use it
-------------
1. Unzip the download (double-click the .zip in Finder).
2. Double-click EDOPro-HD-Sync
3. It finds your ProjectIgnis folder and shows it in the window. If it got
   the wrong one, press "Change..." and pick the right folder.
4. Tick what you want, then press Start.

That's it. There is nothing to install, and nothing is left behind on your
Mac - the app is this one file, and you can put it wherever you like.

If macOS asks the very first time
---------------------------------
Because the file came from the web, macOS may refuse to open it once.
RIGHT-CLICK EDOPro-HD-Sync and choose "Open" (then "Open" again). After
that it opens normally on a double-click.

Helpful notes
-------------
- A Terminal window opens alongside the app window. That is normal - you
  can ignore it, and closing the app closes both.
- The app takes a second or two to start. That is normal: it unpacks itself
  each time so it can stay a single file.
- Only missing artwork is downloaded, so repeat runs are quick. Tick
  "Re-download everything" for a full refresh.
- "Only cards from my decks" is much faster on a fresh install - it grabs
  just the cards in your saved decks.
- "Show coverage" tells you how much artwork you have without downloading.
- The app tells you when a new version is out. Download it from
  https://github.com/cntrl-alt-lenny/EDOPro-HD-Sync/releases and replace
  this file with the new one.

Quick sanity check
------------------
Advanced users can run a quick offline self-test in Terminal:

  ./EDOPro-HD-Sync --health-check
