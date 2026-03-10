"""Sortable, filterable Treeview table of student grading results."""

from __future__ import annotations
import subprocess
import sys
import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional

from ui.theme import Theme
from engine.models import StudentCategory, StudentResult


_COL_NAME     = "Name"
_COL_SCORE    = "Score"
_COL_CAT      = "Category"
_COL_TIER     = "Match Tier"
_COL_NOTES    = "Notes"
_COLUMNS      = (_COL_NAME, _COL_SCORE, _COL_CAT, _COL_TIER, _COL_NOTES)
_COL_WIDTHS   = {
    _COL_NAME:  90,
    _COL_SCORE: 70,
    _COL_CAT:   100,
    _COL_TIER:  110,
    _COL_NOTES: 500,
}


class ResultsTable(ttk.Frame):
    """Treeview-based results table with sorting, filtering, and row colors."""

    def __init__(
        self,
        parent: tk.Widget,
        on_select: Callable[[StudentResult], None],
    ):
        super().__init__(parent)
        self._on_select = on_select
        self._all_results: list[StudentResult] = []
        self._active_filter: Optional[str] = None
        self._sort_col: str = _COL_SCORE
        self._sort_rev: bool = False
        self._build()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self, results: list[StudentResult]):
        """Replace the table contents with a new result list."""
        self._all_results = results
        self._render()

    def apply_filter(self, category: Optional[str]):
        """Show only rows matching category value, or all if None."""
        self._active_filter = category
        self._render()

    def clear(self):
        self._all_results = []
        self._render()

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self._tree = ttk.Treeview(
            self,
            columns=_COLUMNS,
            show="headings",
            selectmode="browse",
        )

        vsb = ttk.Scrollbar(self, orient="vertical",   command=self._tree.yview)
        hsb = ttk.Scrollbar(self, orient="horizontal", command=self._tree.xview)
        self._tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self._tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        for col in _COLUMNS:
            self._tree.heading(
                col,
                text=col,
                command=lambda c=col: self._sort_by(c),
                anchor="w",
            )
            self._tree.column(col, width=_COL_WIDTHS[col], anchor="w", stretch=(col == _COL_NOTES))

        # Row color tags
        for cat in StudentCategory:
            self._tree.tag_configure(
                cat.value,
                foreground=Theme.CATEGORY_COLORS[cat.value],
            )

        self._tree.bind("<<TreeviewSelect>>", self._on_row_select)
        self._tree.bind("<Double-Button-1>", self._on_double_click)
        self._tree.bind("<Button-3>", self._on_right_click)

        # Context menu
        self._ctx = tk.Menu(self._tree, tearoff=False,
                            bg=Theme.PANEL, fg=Theme.FG,
                            activebackground=Theme.SEL_BG)
        self._ctx.add_command(label="Open student file", command=self._open_student_file)
        self._ctx.add_command(label="Copy notes",        command=self._copy_notes)

    # ------------------------------------------------------------------
    # Render
    # ------------------------------------------------------------------

    def _render(self):
        # Clear
        for item in self._tree.get_children():
            self._tree.delete(item)

        filtered = self._filtered()
        sorted_  = self._sorted(filtered)

        for r in sorted_:
            notes_str = " | ".join(r.notes) if r.notes else ""
            tier_str  = r.overall_match_tier.value.capitalize()
            values = (
                r.name,
                r.display_score,
                r.category.label,
                tier_str,
                notes_str,
            )
            self._tree.insert(
                "", "end",
                iid=r.name,
                values=values,
                tags=(r.category.value,),
            )

    # ------------------------------------------------------------------
    # Filtering & sorting
    # ------------------------------------------------------------------

    def _filtered(self) -> list[StudentResult]:
        if not self._active_filter:
            return self._all_results
        return [r for r in self._all_results if r.category.value == self._active_filter]

    def _sorted(self, results: list[StudentResult]) -> list[StudentResult]:
        col = self._sort_col
        rev = self._sort_rev

        if col == _COL_SCORE:
            key = lambda r: r.score
        elif col == _COL_CAT:
            _order = {c: i for i, c in enumerate(
                ["perfect", "cosmetic", "partial", "logic_fail", "crash"]
            )}
            key = lambda r: _order.get(r.category.value, 99)
        elif col == _COL_TIER:
            _torder = ["exact","normalized","semantic","file_only","mismatch","error"]
            key = lambda r: _torder.index(r.overall_match_tier.value) if r.overall_match_tier.value in _torder else 99
        else:
            key = lambda r: r.name.lower()

        return sorted(results, key=key, reverse=rev)

    def _sort_by(self, col: str):
        if self._sort_col == col:
            self._sort_rev = not self._sort_rev
        else:
            self._sort_col = col
            self._sort_rev = (col == _COL_SCORE)  # scores default descending
        self._render()

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    def _on_row_select(self, _event=None):
        sel = self._tree.selection()
        if not sel:
            return
        name = sel[0]
        result = self._result_by_name(name)
        if result:
            self._on_select(result)

    def _on_double_click(self, _event=None):
        self._open_student_file()

    def _on_right_click(self, event):
        row = self._tree.identify_row(event.y)
        if row:
            self._tree.selection_set(row)
        self._ctx.post(event.x_root, event.y_root)

    def _open_student_file(self):
        sel = self._tree.selection()
        if not sel:
            return
        result = self._result_by_name(sel[0])
        if not result:
            return
        path = result.path
        if sys.platform == "darwin":
            subprocess.Popen(["open", path])
        elif sys.platform == "win32":
            subprocess.Popen(["explorer", path])
        else:
            subprocess.Popen(["xdg-open", path])

    def _copy_notes(self):
        sel = self._tree.selection()
        if not sel:
            return
        result = self._result_by_name(sel[0])
        if not result:
            return
        notes = "\n".join(result.notes)
        self._tree.clipboard_clear()
        self._tree.clipboard_append(notes)

    def _result_by_name(self, name: str) -> Optional[StudentResult]:
        for r in self._all_results:
            if r.name == name:
                return r
        return None
