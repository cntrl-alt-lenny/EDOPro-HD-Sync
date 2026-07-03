"""Small cross-platform options dialog shown by the packaged app.

One tkinter window with tick-boxes for what to download, shown on Windows,
macOS, and Linux alike (PyInstaller bundles Tcl/Tk into the release binaries).
If tkinter is unavailable or the window can't open (e.g. no display), the
caller falls back to the regular console flow.
"""

import contextlib

try:
    import tkinter as tk
    from tkinter import ttk
except Exception:  # tkinter genuinely missing on some Pythons
    tk = None
    ttk = None


def gui_available() -> bool:
    return tk is not None


# (key, label, hint, default)
CHECKBOXES = [
    (
        "field_art",
        "Field Spell playmat artwork",
        "Also fetch the art shown on the board during duels",
        True,
    ),
    (
        "my_decks",
        "Only cards from my decks",
        "Much faster — just the cards you actually play",
        False,
    ),
    (
        "textures",
        "Curated textures",
        "Custom backgrounds and card sleeves",
        False,
    ),
    (
        "repair",
        "Repair broken images first",
        "Finds and re-downloads corrupt files",
        False,
    ),
    (
        "force",
        "Re-download everything",
        "Full refresh instead of only missing artwork",
        False,
    ),
    (
        "save_report",
        "Save a sync report",
        "Writes a text file listing anything unavailable",
        False,
    ),
]


def show_options_dialog(version: str, defaults: dict | None = None) -> dict | None:
    """Show the tick-box launcher window.

    Returns a dict with one bool per CHECKBOXES key plus "stats" (True when the
    user pressed "Show coverage" instead of Start), or None when the user
    closed the window / pressed Escape — the caller should exit quietly then.
    Raises if the window can't be created (caller falls back to console mode).
    """
    defaults = defaults or {}
    result: dict | None = None

    root = tk.Tk()
    root.title(f"EDOPro HD Sync v{version}")
    root.resizable(False, False)
    with contextlib.suppress(Exception):
        root.attributes("-topmost", True)

    frame = ttk.Frame(root, padding=18)
    frame.grid(sticky="nsew")

    ttk.Label(frame, text="EDOPro HD Sync", font=("", 16, "bold")).grid(sticky="w")
    ttk.Label(frame, text="Tick what you want, then press Start.").grid(sticky="w", pady=(2, 12))

    variables: dict[str, tk.BooleanVar] = {}
    for key, label, hint, default in CHECKBOXES:
        variables[key] = tk.BooleanVar(value=bool(defaults.get(key, default)))
        ttk.Checkbutton(frame, text=label, variable=variables[key]).grid(sticky="w")
        ttk.Label(frame, text=hint, font=("", 10), foreground="#777777").grid(
            sticky="w", padx=(24, 0), pady=(0, 6)
        )

    def close_with(value: dict | None) -> None:
        nonlocal result
        result = value
        root.destroy()

    def choices(stats: bool) -> dict:
        picked = {key: var.get() for key, var in variables.items()}
        picked["stats"] = stats
        return picked

    buttons = ttk.Frame(frame)
    buttons.grid(sticky="e", pady=(14, 0))
    ttk.Button(buttons, text="Show coverage", command=lambda: close_with(choices(True))).grid(
        row=0, column=0, padx=(0, 8)
    )
    start = ttk.Button(buttons, text="Start", command=lambda: close_with(choices(False)))
    start.grid(row=0, column=1)

    root.bind("<Return>", lambda _event: close_with(choices(False)))
    root.bind("<Escape>", lambda _event: close_with(None))
    root.protocol("WM_DELETE_WINDOW", lambda: close_with(None))

    # Center the window on screen and bring it to the front.
    root.update_idletasks()
    x = (root.winfo_screenwidth() - root.winfo_width()) // 2
    y = (root.winfo_screenheight() - root.winfo_height()) // 3
    root.geometry(f"+{max(x, 0)}+{max(y, 0)}")
    with contextlib.suppress(Exception):
        root.lift()
        root.focus_force()
        start.focus_set()

    root.mainloop()
    return result
