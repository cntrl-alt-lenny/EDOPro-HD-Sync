EDOPro HD Sync for macOS
========================

1. Unzip this folder into your EDOPro folder.
2. Open the "EDOPro HD Sync MacOS" folder.
3. Double-click EDOPro-HD-Sync.command.
4. If macOS blocks it, go to System Settings -> Privacy & Security and allow it.

Helpful notes
-------------
- The launcher downloads the latest binary automatically if the macOS app file is missing.
- Packaged builds refresh artwork automatically, so you do not need to add --force.
- config.json and alternate-art-cache.json are kept beside the tool files in this folder.

Quick sanity check
------------------
You can also run this in Terminal from the tool folder:

./EDOPro-HD-Sync-macOS --health-check

That runs a quick offline check for the known tricky alternate-art cases.
