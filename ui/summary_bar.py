"""Summary bar widget showing category counts and average score.

Layout:
  ■ 3 Perfect  ■ 17 Cosmetic  ■ 5 Logic Fail  ■ 6 Crash  │ 31 total │ Avg: 72.3%

Each colored chip is also a filter button — clicking it calls the provided
filter_callback with the category string (or None to reset).
"""

from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional

from ui.theme import Theme
from engine.models import StudentCategory, StudentResult


class SummaryBar(ttk.Frame):
    def __init__(self, parent: tk.Widget, filter_callback: Callable[[Optional[str]], None]):
        super().__init__(parent, style="Panel.TFrame")
        self._filter_cb = filter_callback
        self._active_filter: Optional[str] = None
        self._chip_frames: dict[str, tk.Frame] = {}
        self._build()

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def update(self, results: list[StudentResult]):
        """Refresh counts and average from a list of StudentResult."""
        counts: dict[str, int] = {c.value: 0 for c in StudentCategory}
        total_score = 0.0
        for r in results:
            counts[r.category.value] += 1
            total_score += r.score

        n = len(results)
        avg = total_score / n if n else 0.0

        for cat_val, count in counts.items():
            if cat_val in self._count_vars:
                self._count_vars[cat_val].set(str(count))

        self._total_var.set(f"{n} total")
        self._avg_var.set(f"Avg: {avg:.1f}%")

    def clear(self):
        for v in self._count_vars.values():
            v.set("0")
        self._total_var.set("0 total")
        self._avg_var.set("Avg: —")
        self._set_active(None)

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build(self):
        self._count_vars: dict[str, tk.StringVar] = {}

        categories = [
            (StudentCategory.PERFECT,    "Perfect"),
            (StudentCategory.COSMETIC,   "Cosmetic"),
            (StudentCategory.PARTIAL,    "Partial"),
            (StudentCategory.LOGIC_FAIL, "Logic Fail"),
            (StudentCategory.CRASH,      "Crash"),
        ]

        col = 0
        for cat, label in categories:
            color = Theme.CATEGORY_COLORS[cat.value]
            count_var = tk.StringVar(value="0")
            self._count_vars[cat.value] = count_var

            chip = tk.Frame(self, bg=color, cursor="hand2", padx=8, pady=4)
            chip.grid(row=0, column=col, padx=(0, 6), pady=6, sticky="nsew")
            self._chip_frames[cat.value] = chip

            tk.Label(
                chip,
                textvariable=count_var,
                bg=color, fg=Theme.BG,
                font=Theme.FONT_HEADER,
            ).pack(side=tk.LEFT, padx=(0, 4))
            tk.Label(
                chip,
                text=label,
                bg=color, fg=Theme.BG,
                font=Theme.FONT_BODY,
            ).pack(side=tk.LEFT)

            # Bind click for filtering
            cat_val = cat.value
            for widget in (chip,) + tuple(chip.winfo_children()):
                widget.bind("<Button-1>", lambda e, v=cat_val: self._on_chip_click(v))

            col += 1

        # Separator
        ttk.Separator(self, orient="vertical").grid(
            row=0, column=col, padx=10, sticky="ns", pady=4
        )
        col += 1

        # Total and average
        self._total_var = tk.StringVar(value="0 total")
        self._avg_var   = tk.StringVar(value="Avg: —")

        tk.Label(self, textvariable=self._total_var,
                 bg=Theme.BG, fg=Theme.FG_DIM,
                 font=Theme.FONT_BODY).grid(row=0, column=col, padx=(0, 12))
        col += 1
        tk.Label(self, textvariable=self._avg_var,
                 bg=Theme.BG, fg=Theme.ACCENT,
                 font=Theme.FONT_HEADER).grid(row=0, column=col, padx=(0, 6))

    # ------------------------------------------------------------------
    # Interaction
    # ------------------------------------------------------------------

    def _on_chip_click(self, cat_val: str):
        if self._active_filter == cat_val:
            # Toggle off
            self._set_active(None)
            self._filter_cb(None)
        else:
            self._set_active(cat_val)
            self._filter_cb(cat_val)

    def _set_active(self, active: Optional[str]):
        self._active_filter = active
        for cat_val, chip in self._chip_frames.items():
            color = Theme.CATEGORY_COLORS[cat_val]
            if active is None or cat_val == active:
                chip.configure(bg=color)
                for w in chip.winfo_children():
                    w.configure(bg=color)
            else:
                # Dim inactive chips
                chip.configure(bg=Theme.BORDER)
                for w in chip.winfo_children():
                    w.configure(bg=Theme.BORDER)
