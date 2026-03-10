"""Tokyo Night theme constants and ttk style configuration."""

from __future__ import annotations
import tkinter as tk
from tkinter import ttk


class Theme:
    # ---- Window ----------------------------------------------------------
    WINDOW_W = 1280
    WINDOW_H = 860
    TITLE    = "COP2273 Autograder v2"
    ICON_PATH = "icon.png"

    # ---- Fonts -----------------------------------------------------------
    FONT_TITLE  = ("Arial", 16, "bold")
    FONT_HEADER = ("Arial", 12, "bold")
    FONT_BODY   = ("Arial", 11)
    FONT_MONO   = ("Consolas", 10)
    FONT_SMALL  = ("Arial", 9)

    # ---- Tokyo Night palette ---------------------------------------------
    BG          = "#1a1b26"   # deep background
    PANEL       = "#24283b"   # panel / frame surface
    BORDER      = "#414868"   # border / divider
    FG          = "#c0caf5"   # primary text
    FG_DIM      = "#565f89"   # secondary / dimmed text
    ACCENT      = "#7aa2f7"   # blue accent
    BTN_BG      = "#33467c"
    BTN_HOVER   = "#414868"
    ENTRY_BG    = "#16161e"
    SEL_BG      = "#33467c"

    # ---- Semantic colors (results) ---------------------------------------
    PERFECT     = "#9ece6a"   # green
    COSMETIC    = "#7aa2f7"   # blue
    PARTIAL     = "#e0af68"   # yellow
    LOGIC_FAIL  = "#ff9e64"   # orange
    CRASH       = "#f7768e"   # red

    # ---- Diff colors -----------------------------------------------------
    DIFF_ADD    = "#1a3a2a"   # added line background
    DIFF_DEL    = "#3a1a1e"   # deleted line background
    DIFF_ADD_FG = "#9ece6a"
    DIFF_DEL_FG = "#f7768e"
    DIFF_EQ_FG  = "#565f89"

    # ---- Category → color map -------------------------------------------
    CATEGORY_COLORS = {
        "perfect":    PERFECT,
        "cosmetic":   COSMETIC,
        "partial":    PARTIAL,
        "logic_fail": LOGIC_FAIL,
        "crash":      CRASH,
    }

    # ---- Timing ----------------------------------------------------------
    TIMEOUT = 30


def apply(root: tk.Tk) -> ttk.Style:
    """Apply the Tokyo Night theme to all ttk widgets."""
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    bg, fg, panel, border, accent = (
        Theme.BG, Theme.FG, Theme.PANEL, Theme.BORDER, Theme.ACCENT
    )

    style.configure(".",
        background=bg, foreground=fg,
        fieldbackground=Theme.ENTRY_BG,
        font=Theme.FONT_BODY,
    )
    style.configure("TFrame",       background=bg)
    style.configure("Panel.TFrame", background=panel)
    style.configure("TLabel",       background=bg, foreground=fg)
    style.configure("Dim.TLabel",   background=bg, foreground=Theme.FG_DIM)
    style.configure("Accent.TLabel",background=bg, foreground=accent,
                    font=Theme.FONT_TITLE)
    style.configure("Header.TLabel",background=bg, foreground=accent,
                    font=Theme.FONT_HEADER)

    style.configure("TLabelframe",
        background=bg, foreground=fg,
        bordercolor=border, lightcolor=border,
        darkcolor=border, borderwidth=1,
    )
    style.configure("TLabelframe.Label",
        background=bg, foreground=accent, font=Theme.FONT_HEADER)

    style.configure("TButton",
        background=Theme.BTN_BG, foreground=fg,
        borderwidth=0, focusthickness=0,
        focuscolor=accent, relief="flat", padding=6,
    )
    style.map("TButton",
        background=[("active", Theme.BTN_HOVER), ("pressed", accent)],
        foreground=[("pressed", bg)],
    )

    style.configure("TEntry",
        fieldbackground=Theme.ENTRY_BG, foreground=fg,
        insertcolor=fg, borderwidth=1, relief="flat", padding=5,
        bordercolor=border, lightcolor=border, darkcolor=border,
    )

    style.configure("Vertical.TScrollbar",
        background=panel, troughcolor=bg,
        borderwidth=0, arrowcolor=accent,
    )
    style.configure("Horizontal.TScrollbar",
        background=panel, troughcolor=bg,
        borderwidth=0, arrowcolor=accent,
    )

    style.configure("TCheckbutton", background=bg, foreground=fg)
    style.configure("TRadiobutton", background=bg, foreground=fg)
    style.configure("TSeparator",   background=border)

    # Treeview
    style.configure("Treeview",
        background=panel, foreground=fg,
        fieldbackground=panel,
        rowheight=24, borderwidth=0,
        font=Theme.FONT_BODY,
    )
    style.configure("Treeview.Heading",
        background=Theme.BTN_BG, foreground=fg,
        font=Theme.FONT_BODY, relief="flat",
    )
    style.map("Treeview",
        background=[("selected", Theme.SEL_BG)],
        foreground=[("selected", fg)],
    )
    style.map("Treeview.Heading",
        background=[("active", Theme.BTN_HOVER)],
    )

    # Notebook (tabs) for detail panel
    style.configure("TNotebook",       background=bg, borderwidth=0)
    style.configure("TNotebook.Tab",
        background=Theme.BTN_BG, foreground=fg, padding=(10, 4),
    )
    style.map("TNotebook.Tab",
        background=[("selected", panel)],
        foreground=[("selected", accent)],
    )

    # Canvas host inner frame
    style.configure("Canvas.TFrame", background=bg)

    return style
