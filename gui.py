"""Branded app window: options -> progress -> summary (tkinter, all platforms).

One tkinter implementation serves Windows, macOS, and Linux; PyInstaller
bundles Tcl/Tk into the release binaries. The window owns the main thread and
runs the download pipeline in a worker thread, talking to it through a queue
plus the runtime hooks on Config (gui_progress, folder_picker, coverage_sink,
notice_sink, cancel_event). If Tk is missing or no display is available,
run_app raises GuiUnavailable and the caller falls back to the console flow.
"""

import contextlib
import platform
import queue
import sys
import threading

try:
    import tkinter as tk
    from tkinter import filedialog, ttk
    from tkinter import font as tkfont
except Exception:  # tkinter genuinely missing on some Pythons
    tk = None
    ttk = None

# Brand palette (matches assets/github-banner.jpg)
BG = "#0d1425"
BG_CARD = "#131c31"
BG_CHIP = "#1b2740"
BORDER = "#263351"
GOLD = "#f0a832"
GOLD_HI = "#ffd76a"
GOLD_DOWN = "#d18f1f"
GOLD_DIM = "#c9a24a"
ON_GOLD = "#161006"
TEXT = "#d7deee"
TEXT_DIM = "#8fa0bf"
TEXT_FAINT = "#5c6c8c"
GREEN = "#6fcf97"
RED = "#ef7d7d"
FOCUS = "#7ea4e0"
DISABLED = "#3a4059"

CONTENT_WIDTH = 460

# (section, [(key, label, hint, default), ...])
CHECKBOX_GROUPS = [
    (
        "ARTWORK",
        [
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
        ],
    ),
    (
        "EXTRAS",
        [
            (
                "textures",
                "Curated textures",
                "Custom backgrounds and card sleeves",
                False,
            ),
            (
                "save_report",
                "Save a sync report",
                "Writes a text file listing anything unavailable",
                False,
            ),
        ],
    ),
    (
        "MAINTENANCE",
        [
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
        ],
    ),
]

CHECKBOXES = [box for _section, boxes in CHECKBOX_GROUPS for box in boxes]


class GuiUnavailable(RuntimeError):
    """The window can't be created (no tkinter, no display, broken Tk)."""


def gui_available() -> bool:
    return tk is not None


def _ui_fonts() -> dict:
    system = platform.system()
    if system == "Windows":
        base = "Segoe UI"
    elif system == "Darwin":
        base = ".AppleSystemUIFont"  # Tk's alias for the SF system font
    else:
        base = "DejaVu Sans"
        try:
            if base not in tkfont.families():
                base = "TkDefaultFont"
        except Exception:
            base = "TkDefaultFont"
    return {
        "body": (base, 10),
        "hint": (base, 9),
        "section": (base, 9, "bold"),
        "title": (base, 16, "bold"),
        "big": (base, 26, "bold"),
        "button": (base, 10, "bold"),
    }


def _set_windows_dpi_awareness() -> None:
    """Must run before the first Tk window exists or text renders blurry."""
    if sys.platform != "win32":
        return
    import ctypes

    with contextlib.suppress(Exception):
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        return
    with contextlib.suppress(Exception):
        ctypes.windll.user32.SetProcessDPIAware()


def _apply_windows_dark_titlebar(root) -> None:
    """Ask DWM for a dark title bar so the navy window doesn't get a white cap."""
    if sys.platform != "win32":
        return
    import ctypes

    with contextlib.suppress(Exception):
        root.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
        value = ctypes.c_int(1)
        for attribute in (20, 19):  # DWMWA_USE_IMMERSIVE_DARK_MODE (20; 19 pre-20H1)
            if (
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, attribute, ctypes.byref(value), ctypes.sizeof(value)
                )
                == 0
            ):
                break
        # Force a repaint so the change shows immediately.
        root.withdraw()
        root.deiconify()


def _apply_style(root) -> None:
    f = _ui_fonts()
    root.configure(bg=BG)
    style = ttk.Style(root)
    style.theme_use("clam")  # the only built-in theme that honors all colors below

    style.configure(
        ".",
        background=BG,
        foreground=TEXT,
        font=f["body"],
        bordercolor=BORDER,
        focuscolor=FOCUS,
        lightcolor=BG,
        darkcolor=BG,
        troughcolor=BG_CHIP,
        selectbackground=BG_CHIP,
        selectforeground=TEXT,
    )

    style.configure("TFrame", background=BG)
    style.configure(
        "Card.TFrame",
        background=BG_CARD,
        bordercolor=BORDER,
        relief="solid",
        borderwidth=1,
        lightcolor=BG_CARD,
        darkcolor=BG_CARD,
    )

    style.configure("TLabel", background=BG, foreground=TEXT)
    style.configure("Title.TLabel", font=f["title"])
    style.configure(
        "Chip.TLabel", background=BG_CHIP, foreground=GOLD_HI, font=f["hint"], padding=(8, 2)
    )
    style.configure("Section.TLabel", foreground=GOLD_DIM, font=f["section"])
    style.configure("CardBody.TLabel", background=BG_CARD)
    style.configure("Hint.TLabel", background=BG_CARD, foreground=TEXT_DIM, font=f["hint"])
    style.configure("Status.TLabel", foreground=TEXT_DIM)
    style.configure("Faint.TLabel", foreground=TEXT_FAINT, font=f["hint"])
    style.configure("Notice.TLabel", foreground=GOLD_DIM, font=f["hint"])
    style.configure("Good.TLabel", foreground=GREEN)
    style.configure("Bad.TLabel", foreground=RED)
    style.configure("Big.TLabel", font=f["big"], foreground=GOLD_HI)
    style.configure("BigCalm.TLabel", font=f["big"], foreground=TEXT_FAINT)
    style.configure("BigBad.TLabel", font=f["big"], foreground=RED)

    style.configure(
        "Card.TCheckbutton",
        background=BG_CARD,
        foreground=TEXT,
        font=f["body"],
        indicatorbackground=BG,
        indicatorforeground=ON_GOLD,
        indicatormargin=(0, 2, 8, 2),
        padding=(0, 2),
        focuscolor=FOCUS,
    )
    style.map(
        "Card.TCheckbutton",
        background=[("active", BG_CARD)],  # kill clam's light hover flash
        foreground=[("disabled", TEXT_FAINT)],
        indicatorbackground=[
            ("disabled", BG_CHIP),
            ("selected", GOLD),
            ("pressed", BG_CHIP),
        ],
        indicatorforeground=[("disabled", TEXT_FAINT), ("selected", ON_GOLD)],
    )

    style.configure(
        "Primary.TButton",
        background=GOLD,
        foreground=ON_GOLD,
        font=f["button"],
        padding=(18, 8),
        borderwidth=0,
        relief="flat",
        bordercolor=GOLD,
        lightcolor=GOLD,
        darkcolor=GOLD,
        focusthickness=2,
        focuscolor=FOCUS,
    )
    style.map(
        "Primary.TButton",
        background=[("disabled", DISABLED), ("pressed", GOLD_DOWN), ("active", GOLD_HI)],
        foreground=[("disabled", TEXT_FAINT)],
        bordercolor=[("pressed", GOLD_DOWN), ("active", GOLD_HI)],
        lightcolor=[("pressed", GOLD_DOWN), ("active", GOLD_HI)],
        darkcolor=[("pressed", GOLD_DOWN), ("active", GOLD_HI)],
    )

    style.configure(
        "Secondary.TButton",
        background=BG,
        foreground=TEXT,
        font=f["body"],
        padding=(14, 7),
        borderwidth=1,
        relief="flat",
        bordercolor=BORDER,
        lightcolor=BG,
        darkcolor=BG,
        focusthickness=2,
        focuscolor=FOCUS,
    )
    style.map(
        "Secondary.TButton",
        background=[("pressed", BG_CHIP), ("active", BG_CHIP)],
        foreground=[("disabled", TEXT_FAINT), ("active", GOLD_HI)],
        bordercolor=[("active", "#3a4c74")],
    )

    # Flat progressbar: bevel colors match fill/trough so no broken 3D edges.
    style.configure(
        "Gold.Horizontal.TProgressbar",
        background=GOLD,
        troughcolor=BG_CHIP,
        bordercolor=BG_CHIP,
        lightcolor=GOLD,
        darkcolor=GOLD,
        thickness=10,
    )


class _GuiProgress:
    """Rich-Progress-compatible adapter; thread-safe via the event queue."""

    def __init__(self, events: "queue.Queue"):
        self._events = events
        self._next_id = 0

    def add_task(self, description: str, total: int = 0):
        task_id = self._next_id
        self._next_id += 1
        self._events.put(("task", task_id, description, total))
        return task_id

    def update(self, task_id, description: str | None = None, **_kwargs) -> None:
        if description:
            self._events.put(("desc", task_id, description))

    def advance(self, task_id, step: int = 1) -> None:
        self._events.put(("adv", task_id, step))


class _App:
    def __init__(self, cfg, version: str, run_coro, apply_choices):
        self.cfg = cfg
        self.version = version
        self.run_coro = run_coro
        self.apply_choices = apply_choices
        self.events: queue.Queue = queue.Queue()
        self.exit_code = 0
        self.mode = "sync"  # or "coverage"
        self.total = 0
        self.done = 0
        self.finished = False
        self.folder_cancelled = False
        self.coverage_shown = False
        self.current = None  # which screen frame is on top (tkraise keeps all mapped)
        self.result: dict = {}
        self.cancel_event = threading.Event()

        _set_windows_dpi_awareness()
        try:
            self.root = tk.Tk()
        except Exception as exc:  # no display, broken Tk install, ...
            raise GuiUnavailable(str(exc)) from exc

        try:
            self.root.title(f"EDOPro HD Sync v{version}")
            self.root.resizable(False, False)
            _apply_style(self.root)
            _apply_windows_dark_titlebar(self.root)

            self.shell = ttk.Frame(self.root)
            self.shell.grid(sticky="nsew")
            self.root.columnconfigure(0, weight=1)
            self.shell.columnconfigure(0, weight=1)

            self._build_options()
            self._build_progress()
            self._build_summary()
            self._show(self.options_frame)

            with contextlib.suppress(Exception):
                self.root.attributes("-topmost", True)
                # Drop topmost once it has served its purpose (macOS quirk).
                self.root.after(400, lambda: self.root.attributes("-topmost", False))
                self.root.lift()
                self.root.focus_force()
        except GuiUnavailable:
            raise
        except Exception as exc:
            with contextlib.suppress(Exception):
                self.root.destroy()
            raise GuiUnavailable(str(exc)) from exc

    # -- screens ---------------------------------------------------------

    def _screen(self) -> "ttk.Frame":
        frame = ttk.Frame(self.shell, padding=(24, 20, 24, 22))
        frame.grid(row=0, column=0, sticky="nsew")
        frame.columnconfigure(0, weight=1)
        return frame

    def _build_options(self) -> None:
        f = self.options_frame = self._screen()

        header = ttk.Frame(f)
        header.grid(sticky="ew")
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="EDOPro HD Sync", style="Title.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(header, text=f"v{self.version}", style="Chip.TLabel").grid(
            row=0, column=1, sticky="e"
        )
        ttk.Label(f, text="Tick what you want, then press Start.", style="Status.TLabel").grid(
            sticky="w", pady=(4, 18)
        )

        self.variables: dict[str, tk.BooleanVar] = {}
        defaults = {"field_art": getattr(self.cfg, "field_art", True)}
        for section, boxes in CHECKBOX_GROUPS:
            ttk.Label(f, text=section, style="Section.TLabel").grid(sticky="w", pady=(0, 6))
            card = ttk.Frame(f, style="Card.TFrame", padding=(14, 12, 14, 6))
            card.grid(sticky="ew", pady=(0, 16))
            card.columnconfigure(0, weight=1)
            for key, label, hint, default in boxes:
                self.variables[key] = tk.BooleanVar(value=bool(defaults.get(key, default)))
                ttk.Checkbutton(
                    card, text=label, style="Card.TCheckbutton", variable=self.variables[key]
                ).grid(sticky="w")
                ttk.Label(card, text=hint, style="Hint.TLabel").grid(
                    sticky="w", padx=(26, 0), pady=(0, 10)
                )

        self.notice_var = tk.StringVar(value="")
        ttk.Label(f, textvariable=self.notice_var, style="Notice.TLabel").grid(
            sticky="w", pady=(0, 6)
        )

        buttons = ttk.Frame(f)
        buttons.grid(sticky="e", pady=(4, 0))
        ttk.Button(
            buttons, text="Show coverage", style="Secondary.TButton", command=self._on_coverage
        ).grid(row=0, column=0, padx=(0, 10))
        start = ttk.Button(buttons, text="Start", style="Primary.TButton", command=self._on_start)
        start.grid(row=0, column=1)

        self.root.bind("<Return>", lambda _e: self._on_start())
        self.root.bind("<Escape>", lambda _e: self._on_escape())
        self.root.protocol("WM_DELETE_WINDOW", self._on_escape)

    def _build_progress(self) -> None:
        f = self.progress_frame = self._screen()
        ttk.Label(f, text="Syncing artwork", style="Title.TLabel").grid(sticky="w")
        self.stage_var = tk.StringVar(value="Scanning card databases…")
        ttk.Label(f, textvariable=self.stage_var, style="Status.TLabel", width=58, anchor="w").grid(
            sticky="w", pady=(12, 10)
        )
        self.bar = ttk.Progressbar(
            f, style="Gold.Horizontal.TProgressbar", mode="indeterminate", length=CONTENT_WIDTH - 48
        )
        self.bar.grid(sticky="ew")
        counts = ttk.Frame(f)
        counts.grid(sticky="ew", pady=(10, 16))
        counts.columnconfigure(0, weight=1)
        self.count_var = tk.StringVar(value="")
        ttk.Label(counts, textvariable=self.count_var, style="Faint.TLabel").grid(
            row=0, column=1, sticky="e"
        )
        self.cancel_button = ttk.Button(
            f, text="Cancel", style="Secondary.TButton", command=self._on_cancel
        )
        self.cancel_button.grid(sticky="e")

    def _build_summary(self) -> None:
        f = self.summary_frame = self._screen()
        self.summary_title_var = tk.StringVar(value="Sync complete")
        ttk.Label(f, textvariable=self.summary_title_var, style="Title.TLabel").grid(
            sticky="w", pady=(0, 16)
        )

        hero = ttk.Frame(f)
        hero.grid(sticky="ew")
        hero.columnconfigure(0, weight=1)
        hero.columnconfigure(1, weight=1)
        self.hero_ok_var = tk.StringVar(value="0")
        self.hero_bad_var = tk.StringVar(value="0")
        self.hero_ok_label = ttk.Label(hero, textvariable=self.hero_ok_var, style="Big.TLabel")
        self.hero_ok_label.grid(row=0, column=0)
        self.hero_bad_label = ttk.Label(
            hero, textvariable=self.hero_bad_var, style="BigCalm.TLabel"
        )
        self.hero_bad_label.grid(row=0, column=1)
        self.hero_ok_caption = ttk.Label(hero, text="downloaded", style="Faint.TLabel")
        self.hero_ok_caption.grid(row=1, column=0)
        self.hero_bad_caption = ttk.Label(hero, text="unavailable", style="Faint.TLabel")
        self.hero_bad_caption.grid(row=1, column=1)

        self.breakdown_card = ttk.Frame(f, style="Card.TFrame", padding=(14, 10))
        self.breakdown_card.grid(sticky="ew", pady=(16, 6))
        self.breakdown_card.columnconfigure(0, weight=1)

        self.summary_note_var = tk.StringVar(value="")
        ttk.Label(
            f, textvariable=self.summary_note_var, style="Status.TLabel", wraplength=440
        ).grid(sticky="w", pady=(2, 16))
        ttk.Button(f, text="Close", style="Primary.TButton", command=self._close).grid(sticky="e")

    # -- layout helpers ----------------------------------------------------

    def _show(self, frame) -> None:
        self.current = frame
        frame.tkraise()
        self.root.update_idletasks()
        width = max(self.root.winfo_width(), CONTENT_WIDTH)
        x = (self.root.winfo_screenwidth() - width) // 2
        y = (self.root.winfo_screenheight() - self.root.winfo_height()) // 3
        self.root.geometry(f"+{max(x, 0)}+{max(y, 0)}")

    def _breakdown_rows(self, rows: list[tuple[str, str]]) -> None:
        for child in self.breakdown_card.winfo_children():
            child.destroy()
        for i, (name, value) in enumerate(rows):
            ttk.Label(self.breakdown_card, text=name, style="CardBody.TLabel").grid(
                row=i, column=0, sticky="w", pady=3
            )
            ttk.Label(self.breakdown_card, text=value, style="Hint.TLabel").grid(
                row=i, column=1, sticky="e", pady=3
            )
        if not rows:
            self.breakdown_card.grid_remove()
        else:
            self.breakdown_card.grid()

    # -- actions -----------------------------------------------------------

    def _picks(self) -> dict:
        return {key: var.get() for key, var in self.variables.items()}

    def _launch(self, stats_only: bool) -> None:
        picks = self._picks()
        picks["stats"] = stats_only
        self.mode = "coverage" if stats_only else "sync"
        self.apply_choices(self.cfg, picks)

        # Fresh event per launch so a stray earlier cancel can't poison the run.
        self.cancel_event = threading.Event()
        self.cfg.gui_progress = _GuiProgress(self.events)
        self.cfg.cancel_event = self.cancel_event
        self.cfg.notice_sink = lambda text: self.events.put(("notice", text))
        self.cfg.coverage_sink = lambda data: self.events.put(("coverage", data))
        self.cfg.folder_picker = self._folder_picker_from_worker

        self.root.bind("<Return>", lambda _e: None)
        self.stage_var.set(
            "Reading card databases…" if not stats_only else "Measuring artwork coverage…"
        )
        self.bar.configure(mode="indeterminate")
        self.bar.start(12)
        self._show(self.progress_frame)

        def worker() -> None:
            import asyncio

            payload: dict = {}
            try:
                payload["stats"] = asyncio.run(self.run_coro(self.cfg))
            except SystemExit as exc:
                payload["exit"] = exc.code if isinstance(exc.code, int) else 1
            except Exception as exc:
                payload["error"] = f"{type(exc).__name__}: {exc}"
            self.events.put(("done", payload))

        threading.Thread(target=worker, daemon=True).start()
        self.root.after(80, self._pump)

    def _on_start(self) -> None:
        self._launch(stats_only=False)

    def _on_coverage(self) -> None:
        self._launch(stats_only=True)

    def _on_cancel(self) -> None:
        self.cancel_event.set()
        self.cancel_button.state(["disabled"])
        self.stage_var.set("Finishing current downloads…")

    def _on_escape(self) -> None:
        # All three frames stay "mapped" once gridded (tkraise only reorders),
        # so gate on the explicitly tracked current screen.
        if self.current is self.progress_frame and not self.finished:
            self._on_cancel()
            return
        self._close()

    def _close(self) -> None:
        with contextlib.suppress(Exception):
            self.root.destroy()

    def _folder_picker_from_worker(self, initial_dir: str):
        """Called from the worker thread; the Tk dialog must run on this thread."""
        ready = threading.Event()
        box: dict = {}
        self.events.put(("pick_folder", initial_dir, ready, box))
        ready.wait(timeout=900)
        return box.get("path")

    # -- event pump ----------------------------------------------------------

    def _pump(self) -> None:
        try:
            while True:
                event = self.events.get_nowait()
                self._handle(event)
        except queue.Empty:
            pass
        if not self.finished:
            self.root.after(80, self._pump)

    def _handle(self, event: tuple) -> None:
        kind = event[0]
        if kind == "task":
            _, _tid, description, total = event
            self.total = int(total)
            self.done = 0
            self.stage_var.set(description)
            self.bar.stop()
            self.bar.configure(mode="determinate", maximum=max(self.total, 1), value=0)
            self.count_var.set(f"0 of {self.total:,}")
        elif kind == "adv":
            self.done += int(event[2])
            self.bar.configure(value=self.done)
            self.count_var.set(f"{self.done:,} of {self.total:,}")
        elif kind == "desc":
            text = str(event[2])
            self.stage_var.set(text if len(text) <= 56 else text[:55] + "…")
        elif kind == "notice":
            self.notice_var.set(str(event[1]))
        elif kind == "coverage":
            self._show_coverage(event[1])
        elif kind == "pick_folder":
            _, initial, ready, box = event
            with contextlib.suppress(Exception):
                box["path"] = (
                    filedialog.askdirectory(
                        parent=self.root,
                        initialdir=initial or "~",
                        title="Select your ProjectIgnis (EDOPro) folder",
                        mustexist=True,
                    )
                    or None
                )
            if box.get("path") is None:
                self.folder_cancelled = True
            ready.set()
        elif kind == "done":
            self._finish(event[1])

    # -- final screens ---------------------------------------------------------

    def _show_coverage(self, data: dict) -> None:
        self.mode = "coverage"
        self.coverage_shown = True
        self.summary_title_var.set("Artwork coverage")

        def pct(part: int, whole: int) -> str:
            return f"{100 * part / whole:.0f}%" if whole else "n/a"

        self.hero_ok_var.set(pct(data["cards_have"], data["cards_total"]))
        self.hero_ok_caption.configure(text="card art on disk")
        self.hero_bad_var.set(pct(data["fields_have"], data["fields_total"]))
        self.hero_bad_label.configure(style="Big.TLabel")
        self.hero_bad_caption.configure(text="field art on disk")

        from main import _format_size  # local import avoids a cycle at module load

        rows = [
            ("Cards indexed", f"{data['cards_total']:,}"),
            ("Card art on disk", f"{data['cards_have']:,}"),
            ("Field art on disk", f"{data['fields_have']:,} of {data['fields_total']:,}"),
            ("Disk usage", _format_size(data["disk_bytes"])),
        ]
        if data["known_missing"]:
            rows.append(("Known-missing (cached)", f"{data['known_missing']:,}"))
        self._breakdown_rows(rows)
        self.summary_note_var.set(f"Images folder: {data['pics_path']}")

    def _finish(self, payload: dict) -> None:
        self.finished = True
        self.bar.stop()

        # Exit code and failure detection come first, whatever the mode —
        # a SystemExit or cancelled folder dialog must never masquerade as
        # "Already up to date" (or as a default coverage screen).
        if "exit" in payload:
            self.exit_code = payload["exit"] or 0
        elif "error" in payload:
            self.exit_code = 1
        error_text = payload.get("error")
        if error_text is None and payload.get("exit") not in (None, 0):
            error_text = "The sync could not run — see the console window for details."

        stats = payload.get("stats")
        if error_text is None and self.mode == "coverage" and not self.coverage_shown:
            error_text = "Coverage could not be measured — see the console window for details."

        if error_text is not None:
            self.summary_title_var.set("Something went wrong")
            self.hero_ok_var.set("—")
            self.hero_bad_var.set("—")
            self.hero_bad_label.configure(style="BigCalm.TLabel")
            self._breakdown_rows([])
            self.summary_note_var.set(error_text)
        elif self.mode == "coverage":
            pass  # _show_coverage already populated the screen
        elif stats is None and self.folder_cancelled:
            self.summary_title_var.set("No folder selected")
            self.hero_ok_var.set("—")
            self.hero_ok_caption.configure(text="nothing synced")
            self.hero_bad_var.set("")
            self.hero_bad_caption.configure(text="")
            self._breakdown_rows([])
            self.summary_note_var.set(
                "Run the app again and pick your EDOPro folder to sync artwork."
            )
        elif stats is None:
            self.summary_title_var.set("Already up to date")
            self.hero_ok_var.set("✓")
            self.hero_ok_caption.configure(text="all artwork present")
            self.hero_bad_var.set("")
            self.hero_bad_caption.configure(text="")
            self._breakdown_rows([])
            self.summary_note_var.set("Nothing was missing — enjoy your duels!")
        else:
            cancelled = self.cancel_event.is_set()
            self.summary_title_var.set("Sync cancelled" if cancelled else "Sync complete")
            downloaded = stats.total_ok + stats.field_ok
            unavailable = stats.failed + stats.field_failed
            self.hero_ok_var.set(f"{downloaded:,}")
            self.hero_bad_var.set(f"{unavailable:,}")
            self.hero_bad_label.configure(
                style="BigBad.TLabel" if unavailable else "BigCalm.TLabel"
            )
            rows = []
            if stats.total_ok:
                rows.append(("Card artwork", f"{stats.total_ok:,}"))
            if stats.field_ok:
                rows.append(("Field Spell artwork", f"{stats.field_ok:,}"))
            if stats.skipped:
                rows.append(("Already on disk", f"{stats.skipped:,}"))
            rush = stats.rush_failures
            unofficial = stats.unofficial_failures
            tokens = len(stats.token_failures)
            official = len(stats.official_failures)
            transient = stats.transient_failures
            if rush:
                rows.append(("Rush Duel (no art yet)", f"{rush:,}"))
            if unofficial:
                rows.append(("Anime / custom (no art yet)", f"{unofficial:,}"))
            if tokens:
                rows.append(("Tokens / placeholders", f"{tokens:,}"))
            if official:
                rows.append(("Official cards unavailable", f"{official:,}"))
            if stats.field_failed:
                rows.append(("Field art unavailable", f"{stats.field_failed:,}"))
            if transient:
                rows.append(("Network errors (will retry)", f"{transient:,}"))
            self._breakdown_rows(rows)
            notes = []
            if unavailable:
                notes.append(
                    "Unavailable cards are remembered for 14 days and skipped on the next run."
                )
            if getattr(self.cfg, "save_report", False):
                notes.append("A sync report was saved next to the app.")
            self.summary_note_var.set(" ".join(notes))

        self._show(self.summary_frame)
        self.root.bind("<Return>", lambda _e: self._close())
        self.root.bind("<Escape>", lambda _e: self._close())
        self.root.protocol("WM_DELETE_WINDOW", self._close)

    def run(self) -> int:
        self.root.mainloop()
        return self.exit_code


def run_app(cfg, version: str, run_coro, apply_choices) -> int:
    """Open the app window and drive a full sync from it. Returns an exit code.

    Raises GuiUnavailable when the window can't be created, so the caller can
    fall back to the plain console flow.
    """
    if tk is None:
        raise GuiUnavailable("tkinter is not available")
    return _App(cfg, version, run_coro, apply_choices).run()
