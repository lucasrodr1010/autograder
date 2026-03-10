"""Detail panel: side-by-side output inspector for a selected student.

Shows per-test-case comparisons with:
  - Color-coded diff (base vs student stdout)
  - Semantic value extraction highlighting
  - File output diff inline
  - Prev / Next test case navigation
"""

from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from typing import Optional

from ui.theme import Theme
from engine.comparator import unified_diff_lines
from engine.models import MatchTier, StudentResult, TestResult


class DetailPanel(ttk.Frame):
    """Right-side panel that shows per-test details for a selected student."""

    def __init__(self, parent: tk.Widget):
        super().__init__(parent, style="Panel.TFrame")
        self._result: Optional[StudentResult] = None
        self._test_idx: int = 0
        self._build()

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def show(self, result: StudentResult):
        """Display a student result, starting at test case 1."""
        self._result = result
        self._test_idx = 0
        self._render_header()
        self._render_test()

    def clear(self):
        self._result = None
        self._test_idx = 0
        self._header_var.set("Select a student to inspect")
        self._clear_body()

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)  # body expands

        # -- Top: student header --
        self._header_var = tk.StringVar(value="Select a student to inspect")
        tk.Label(
            self,
            textvariable=self._header_var,
            bg=Theme.PANEL, fg=Theme.ACCENT,
            font=Theme.FONT_HEADER, anchor="w",
            padx=10, pady=6,
        ).grid(row=0, column=0, sticky="ew")

        ttk.Separator(self, orient="horizontal").grid(row=1, column=0, sticky="ew")

        # -- Body: notebook per test case (or single scrolled frame) --
        self._body = ttk.Frame(self, style="Panel.TFrame")
        self._body.columnconfigure(0, weight=1)
        self._body.rowconfigure(1, weight=1)
        self._body.grid(row=2, column=0, sticky="nsew", padx=4, pady=4)

        # Nav bar
        nav = ttk.Frame(self._body, style="Panel.TFrame")
        nav.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        self._prev_btn = ttk.Button(nav, text="◄ Prev", command=self._prev_test, width=8)
        self._prev_btn.pack(side=tk.LEFT, padx=(0, 4))
        self._next_btn = ttk.Button(nav, text="Next ►", command=self._next_test, width=8)
        self._next_btn.pack(side=tk.LEFT)
        self._test_label = tk.StringVar(value="")
        tk.Label(nav, textvariable=self._test_label,
                 bg=Theme.PANEL, fg=Theme.FG_DIM, font=Theme.FONT_SMALL
                 ).pack(side=tk.LEFT, padx=(12, 0))

        # Scrollable body area
        self._canvas = tk.Canvas(self._body, bg=Theme.PANEL, highlightthickness=0)
        self._vsb    = ttk.Scrollbar(self._body, orient="vertical", command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=self._vsb.set)
        self._canvas.grid(row=1, column=0, sticky="nsew")
        self._vsb.grid(row=1, column=1, sticky="ns")
        self._body.rowconfigure(1, weight=1)
        self._body.columnconfigure(0, weight=1)

        self._scroll_frame = ttk.Frame(self._canvas, style="Panel.TFrame")
        self._scroll_frame.columnconfigure(0, weight=1)
        self._win_id = self._canvas.create_window((0, 0), window=self._scroll_frame, anchor="nw")

        self._scroll_frame.bind("<Configure>", self._on_frame_configure)
        self._canvas.bind("<Configure>",       self._on_canvas_configure)

        # Mouse wheel scrolling
        self._canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def _prev_test(self):
        if self._result and self._test_idx > 0:
            self._test_idx -= 1
            self._render_test()

    def _next_test(self):
        if self._result and self._test_idx < len(self._result.test_results) - 1:
            self._test_idx += 1
            self._render_test()

    # ------------------------------------------------------------------
    # Render
    # ------------------------------------------------------------------

    def _render_header(self):
        if not self._result:
            return
        r = self._result
        self._header_var.set(
            f"{r.name}  —  {r.category.emoji} {r.category.label}  ({r.display_score})"
        )

    def _render_test(self):
        if not self._result:
            return
        tests = self._result.test_results
        if not tests:
            return

        n = len(tests)
        self._test_label.set(f"Test {self._test_idx + 1} / {n}")
        self._prev_btn.config(state=tk.NORMAL if self._test_idx > 0 else tk.DISABLED)
        self._next_btn.config(state=tk.NORMAL if self._test_idx < n - 1 else tk.DISABLED)

        tr = tests[self._test_idx]
        self._clear_body()
        self._build_test_view(tr)

    def _clear_body(self):
        for w in self._scroll_frame.winfo_children():
            w.destroy()

    def _build_test_view(self, tr: TestResult):
        frame = self._scroll_frame
        row = 0

        # ---- Status badge ----
        tier_color = _tier_color(tr.match_tier)
        status_text = f"  Test {tr.test_num}: {tr.match_tier.value.upper()}  "
        tk.Label(
            frame,
            text=status_text,
            bg=tier_color, fg=Theme.BG,
            font=Theme.FONT_HEADER, anchor="w",
            padx=4, pady=3,
        ).grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        row += 1

        # ---- Error block ----
        if tr.error:
            _section_label(frame, row, "Error")
            row += 1
            _text_block(frame, row, tr.error or "", fg=Theme.CRASH, height=4)
            row += 1

        # ---- Input ----
        _section_label(frame, row, "Input")
        row += 1
        _text_block(frame, row, "\n".join(tr.input_lines), fg=Theme.FG_DIM, height=max(2, len(tr.input_lines)))
        row += 1

        # ---- Side-by-side stdout diff ----
        _section_label(frame, row, "Stdout  (Base  ↔  Student)")
        row += 1
        diff_frame = ttk.Frame(frame, style="Panel.TFrame")
        diff_frame.columnconfigure(0, weight=1)
        diff_frame.columnconfigure(1, weight=1)
        diff_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        self._build_diff(diff_frame, tr)
        row += 1

        # ---- Semantic values ----
        if tr.match_tier == MatchTier.SEMANTIC:
            _section_label(frame, row, "Semantic Values Extracted")
            row += 1
            sem_txt = _format_semantic(tr.semantic_values_base, tr.semantic_values_student)
            _text_block(frame, row, sem_txt, fg=Theme.COSMETIC,
                        height=max(3, len(tr.semantic_values_base) + 2))
            row += 1

        # ---- File output ----
        if tr.base_files or tr.student_files:
            _section_label(frame, row, "File Output")
            row += 1
            for fname in sorted(set(list(tr.base_files.keys()) + list(tr.student_files.keys()))):
                b_content = tr.base_files.get(fname, "")
                s_content = tr.student_files.get(fname, "")
                b_txt = b_content if isinstance(b_content, str) else repr(b_content)
                s_txt = s_content if isinstance(s_content, str) else repr(s_content)

                tk.Label(frame, text=f"  {fname}",
                         bg=Theme.PANEL, fg=Theme.FG_DIM,
                         font=Theme.FONT_SMALL).grid(
                    row=row, column=0, columnspan=2, sticky="w")
                row += 1

                if b_content is None:
                    _text_block(frame, row, f"[not generated]",
                                fg=Theme.CRASH, height=2)
                else:
                    file_diff_frame = ttk.Frame(frame, style="Panel.TFrame")
                    file_diff_frame.columnconfigure(0, weight=1)
                    file_diff_frame.columnconfigure(1, weight=1)
                    file_diff_frame.grid(row=row, column=0, columnspan=2,
                                         sticky="ew", pady=(0, 4))
                    self._build_raw_diff(file_diff_frame, b_txt, s_txt)
                row += 1

            if tr.file_mismatch_details:
                for detail in tr.file_mismatch_details:
                    tk.Label(frame, text=f"  ⚠ {detail}",
                             bg=Theme.PANEL, fg=Theme.CRASH,
                             font=Theme.FONT_SMALL).grid(
                        row=row, column=0, columnspan=2, sticky="w")
                    row += 1

    def _build_diff(self, parent: ttk.Frame, tr: TestResult):
        """Side-by-side colored diff of base vs student stdout."""
        self._build_raw_diff(parent, tr.base_stdout or "", tr.student_stdout or "")

    def _build_raw_diff(self, parent: ttk.Frame, base_txt: str, student_txt: str):
        diff = unified_diff_lines(base_txt, student_txt)

        base_col    = tk.Text(parent, wrap="none", font=Theme.FONT_MONO,
                               bg=Theme.ENTRY_BG, fg=Theme.FG,
                               relief="flat", height=min(20, max(4, len(diff) + 2)),
                               state="disabled")
        student_col = tk.Text(parent, wrap="none", font=Theme.FONT_MONO,
                               bg=Theme.ENTRY_BG, fg=Theme.FG,
                               relief="flat", height=min(20, max(4, len(diff) + 2)),
                               state="disabled")
        base_col.grid(row=0, column=0, sticky="nsew", padx=(0, 2))
        student_col.grid(row=0, column=1, sticky="nsew")

        base_col.tag_configure("delete", background=Theme.DIFF_DEL,
                                foreground=Theme.DIFF_DEL_FG)
        base_col.tag_configure("equal",  foreground=Theme.DIFF_EQ_FG)

        student_col.tag_configure("insert", background=Theme.DIFF_ADD,
                                   foreground=Theme.DIFF_ADD_FG)
        student_col.tag_configure("equal",  foreground=Theme.DIFF_EQ_FG)

        base_col.config(state="normal")
        student_col.config(state="normal")

        for tag, line in diff:
            if tag == "equal":
                base_col.insert("end",    line + "\n", "equal")
                student_col.insert("end", line + "\n", "equal")
            elif tag == "delete":
                base_col.insert("end",    line + "\n", "delete")
                student_col.insert("end", "\n")          # blank placeholder
            elif tag == "insert":
                base_col.insert("end",    "\n")          # blank placeholder
                student_col.insert("end", line + "\n", "insert")
            elif tag == "replace":
                base_col.insert("end",    line + "\n", "delete")
                student_col.insert("end", line + "\n", "insert")

        base_col.config(state="disabled")
        student_col.config(state="disabled")

    # ------------------------------------------------------------------
    # Scroll helpers
    # ------------------------------------------------------------------

    def _on_frame_configure(self, _event=None):
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self._canvas.itemconfigure(self._win_id, width=event.width)

    def _on_mousewheel(self, event):
        if self._canvas.winfo_containing(event.x_root, event.y_root):
            import sys as _sys
            delta = -1 * event.delta if _sys.platform == "darwin" else -1 * int(event.delta / 120)
            self._canvas.yview_scroll(delta, "units")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tier_color(tier: MatchTier) -> str:
    return {
        MatchTier.EXACT:      Theme.PERFECT,
        MatchTier.NORMALIZED: Theme.PERFECT,
        MatchTier.SEMANTIC:   Theme.COSMETIC,
        MatchTier.FILE_ONLY:  Theme.PARTIAL,
        MatchTier.MISMATCH:   Theme.LOGIC_FAIL,
        MatchTier.ERROR:      Theme.CRASH,
    }.get(tier, Theme.FG_DIM)


def _section_label(parent: ttk.Frame, row: int, text: str):
    tk.Label(
        parent, text=text,
        bg=Theme.PANEL, fg=Theme.ACCENT,
        font=Theme.FONT_SMALL, anchor="w",
    ).grid(row=row, column=0, columnspan=2, sticky="w", pady=(6, 2))


def _text_block(parent: ttk.Frame, row: int, content: str,
                fg: str = Theme.FG, height: int = 4):
    txt = tk.Text(parent, wrap="word", font=Theme.FONT_MONO,
                  bg=Theme.ENTRY_BG, fg=fg, relief="flat",
                  height=height, state="disabled")
    txt.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 4))
    txt.config(state="normal")
    txt.insert("end", content)
    txt.config(state="disabled")


def _format_semantic(
    base: list[tuple[str, str]],
    student: list[tuple[str, str]],
) -> str:
    lines = ["Base extracted values:"]
    for typ, val in base:
        lines.append(f"  [{typ}] {val}")
    lines.append("")
    match_icon = "✓ Match" if base == student else "✗ Differ"
    lines.append(f"Student extracted values: {match_icon}")
    for typ, val in student:
        lines.append(f"  [{typ}] {val}")
    return "\n".join(lines)
