"""Main application window for Autograder v2.

Layout (left panel = config + controls, right panel = results):

┌───────────────────────────────────────────────────────────────────┐
│  COP2273 Autograder v2                                            │
├────────────────────────┬──────────────────────────────────────────┤
│  Mode / Paths          │  Summary Bar                            │
│  Module Name           │  ─────────────────────────────────────  │
│  Utility Path          │  Results Table (sortable Treeview)      │
│  ─────────────────     │                                          │
│  Test Cases            │  ─────────────────────────────────────  │
│  ─────────────────     │  Detail Panel (side-by-side diff)       │
│  Options               │                                          │
│  Run / Stop            │                                          │
└────────────────────────┴──────────────────────────────────────────┘
"""

from __future__ import annotations

import os
import sys
import threading
import time
import traceback
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext
import tkinter as tk
from tkinter import ttk
from typing import Optional

from ui.theme import Theme, apply as apply_theme
from ui.summary_bar import SummaryBar
from ui.results_table import ResultsTable
from ui.detail_panel import DetailPanel
from engine.runner import ScriptRunner
from engine.categorizer import process_student
from engine.models import StudentResult


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(Theme.TITLE)
        self.root.geometry(f"{Theme.WINDOW_W}x{Theme.WINDOW_H}")
        self.root.resizable(True, True)
        self.root.configure(bg=Theme.BG)

        apply_theme(root)
        self._load_icon()

        # State
        self._base_path      = tk.StringVar()
        self._assignment_path = tk.StringVar()
        self._module_names   = tk.StringVar()
        self._utility_path   = tk.StringVar()
        self._mode           = tk.StringVar(value="folder")
        self._check_stdout   = tk.BooleanVar(value=True)
        self._show_details   = tk.BooleanVar(value=False)
        self._max_workers    = tk.IntVar(value=4)
        self._test_cases: list[_TestCaseWidget] = []
        self._results: list[StudentResult] = []
        self._is_running     = False
        self._status_var     = tk.StringVar(value="Ready")
        self._progress_var   = tk.StringVar(value="")

        self._build()

    # ------------------------------------------------------------------
    # Build layout
    # ------------------------------------------------------------------

    def _build(self):
        # Two-pane layout
        paned = ttk.PanedWindow(self.root, orient="horizontal")
        paned.pack(fill="both", expand=True, padx=8, pady=8)

        left  = self._build_left(paned)
        right = self._build_right(paned)

        paned.add(left,  weight=1)
        paned.add(right, weight=3)

        # Status bar (below paned)
        sb = ttk.Frame(self.root)
        sb.pack(fill="x", side="bottom", padx=8, pady=(0, 4))
        ttk.Label(sb, textvariable=self._status_var, anchor="w").pack(
            fill="x", side="left", expand=True)
        ttk.Label(sb, textvariable=self._progress_var, anchor="e",
                  foreground=Theme.ACCENT).pack(side="right")

    # ------ Left panel ---------------------------------------------------

    def _build_left(self, parent) -> ttk.Frame:
        frame = ttk.Frame(parent)

        # Title
        ttk.Label(frame, text=Theme.TITLE, style="Accent.TLabel").pack(
            fill="x", padx=10, pady=(10, 6))
        ttk.Separator(frame, orient="horizontal").pack(fill="x", padx=10, pady=(0, 6))

        # Scrollable left side
        canvas = tk.Canvas(frame, bg=Theme.BG, highlightthickness=0)
        vsb    = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        inner = ttk.Frame(canvas, style="Canvas.TFrame")
        win   = canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: canvas.configure(
            scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(
            win, width=e.width))

        self._build_config(inner)
        self._build_test_section(inner)
        self._build_options(inner)
        self._build_controls(inner)

        return frame

    def _build_config(self, parent):
        f = ttk.LabelFrame(parent, text="Configuration", padding=8)
        f.pack(fill="x", padx=8, pady=(0, 6))
        f.columnconfigure(1, weight=1)

        # Mode
        mode_row = ttk.Frame(f)
        mode_row.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 6))
        ttk.Radiobutton(mode_row, text="Folder Mode",
                        variable=self._mode, value="folder").pack(side="left", padx=(0, 14))
        ttk.Radiobutton(mode_row, text="File Mode",
                        variable=self._mode, value="file").pack(side="left")

        rows = [
            ("Base Solution:",    self._base_path,       self._browse_base,       0),
            ("Assignment Path:",  self._assignment_path, self._browse_assignment, 0),
            ("Module Name(s):",   self._module_names,    None,                    0),
            ("Utility Path:",     self._utility_path,    self._browse_utility,    0),
        ]
        for i, (label, var, browse_cmd, _) in enumerate(rows, start=1):
            ttk.Label(f, text=label).grid(row=i, column=0, sticky="w", pady=3)
            entry = ttk.Entry(f, textvariable=var)
            entry.grid(row=i, column=1, sticky="ew", padx=(4, 4), pady=3)
            if browse_cmd:
                ttk.Button(f, text="…", width=3, command=browse_cmd).grid(
                    row=i, column=2, pady=3)

    def _build_test_section(self, parent):
        outer = ttk.LabelFrame(parent, text="Test Cases", padding=8)
        outer.pack(fill="x", padx=8, pady=(0, 6))

        ctrl = ttk.Frame(outer)
        ctrl.pack(fill="x", pady=(0, 6))
        ttk.Button(ctrl, text="+ Add Test Case", command=self._add_test_case).pack(
            side="left", padx=(0, 6))
        ttk.Button(ctrl, text="Clear All", command=self._clear_test_cases).pack(side="left")

        self._test_case_frame = ttk.Frame(outer)
        self._test_case_frame.pack(fill="x")
        self._add_test_case()

    def _build_options(self, parent):
        f = ttk.LabelFrame(parent, text="Options", padding=8)
        f.pack(fill="x", padx=8, pady=(0, 6))

        ttk.Checkbutton(f, text="Grade standard output",
                        variable=self._check_stdout).pack(anchor="w")
        ttk.Checkbutton(f, text="Show detailed diff in results",
                        variable=self._show_details).pack(anchor="w")

        worker_row = ttk.Frame(f)
        worker_row.pack(anchor="w", pady=(4, 0))
        ttk.Label(worker_row, text="Parallel workers:").pack(side="left", padx=(0, 6))
        ttk.Spinbox(worker_row, from_=1, to=8, textvariable=self._max_workers,
                    width=4).pack(side="left")

    def _build_controls(self, parent):
        f = ttk.Frame(parent)
        f.pack(fill="x", padx=8, pady=(0, 8))

        self._run_btn = ttk.Button(f, text="▶ Run Autograder", command=self._run)
        self._run_btn.pack(side="left", padx=(0, 6))
        self._stop_btn = ttk.Button(f, text="■ Stop", command=self._stop,
                                    state=tk.DISABLED)
        self._stop_btn.pack(side="left", padx=(0, 6))
        ttk.Button(f, text="Test Single…", command=self._test_single).pack(side="left")

        self._save_btn = ttk.Button(f, text="Save Report", command=self._save_report)
        self._save_btn.pack(side="right")

    # ------ Right panel --------------------------------------------------

    def _build_right(self, parent) -> ttk.Frame:
        frame = ttk.Frame(parent)
        frame.rowconfigure(1, weight=2)
        frame.rowconfigure(2, weight=3)
        frame.columnconfigure(0, weight=1)

        # Summary bar
        self._summary = SummaryBar(frame, filter_callback=self._on_filter)
        self._summary.grid(row=0, column=0, sticky="ew", padx=4, pady=(4, 0))

        ttk.Separator(frame, orient="horizontal").grid(
            row=1, column=0, sticky="ew", pady=2)  # placeholder; proper separator

        # Results table
        table_frame = ttk.LabelFrame(frame, text="Results", padding=4)
        table_frame.grid(row=1, column=0, sticky="nsew", padx=4, pady=2)
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)

        self._table = ResultsTable(table_frame, on_select=self._on_student_select)
        self._table.grid(row=0, column=0, sticky="nsew")

        # Detail panel
        detail_frame = ttk.LabelFrame(frame, text="Inspection", padding=4)
        detail_frame.grid(row=2, column=0, sticky="nsew", padx=4, pady=2)
        detail_frame.columnconfigure(0, weight=1)
        detail_frame.rowconfigure(0, weight=1)

        self._detail = DetailPanel(detail_frame)
        self._detail.grid(row=0, column=0, sticky="nsew")

        return frame

    # ------------------------------------------------------------------
    # Test case widgets
    # ------------------------------------------------------------------

    def _add_test_case(self):
        idx = len(self._test_cases)
        tc = _TestCaseWidget(self._test_case_frame, idx, remove_cb=self._remove_test_case)
        tc.pack(fill="x", pady=2)
        self._test_cases.append(tc)

    def _remove_test_case(self, widget: _TestCaseWidget):
        if widget in self._test_cases:
            self._test_cases.remove(widget)
        widget.destroy()

    def _clear_test_cases(self):
        for tc in self._test_cases:
            tc.destroy()
        self._test_cases.clear()
        self._add_test_case()

    def _get_test_cases(self) -> list[dict]:
        return [tc.get_data() for tc in self._test_cases if tc.is_valid()]

    # ------------------------------------------------------------------
    # Browse commands
    # ------------------------------------------------------------------

    def _browse_base(self):
        if self._mode.get() == "file":
            p = filedialog.askopenfilename(filetypes=[("Python files", "*.py")])
        else:
            p = filedialog.askdirectory(title="Select Base Solution Folder")
        if p:
            self._base_path.set(p)

    def _browse_assignment(self):
        p = filedialog.askdirectory(title="Select Assignment Folder")
        if p:
            self._assignment_path.set(p)

    def _browse_utility(self):
        p = filedialog.askdirectory(title="Select Utility Folder")
        if p:
            self._utility_path.set(p)

    # ------------------------------------------------------------------
    # Grading run
    # ------------------------------------------------------------------

    def _run(self):
        if not self._base_path.get() or not self._assignment_path.get():
            messagebox.showerror("Missing paths",
                                 "Please set both Base Solution and Assignment Path.")
            return
        test_cases = self._get_test_cases()
        if not test_cases:
            messagebox.showerror("No test cases", "Add at least one test case.")
            return

        self._is_running = True
        self._run_btn.config(state=tk.DISABLED)
        self._stop_btn.config(state=tk.NORMAL)
        self._table.clear()
        self._summary.clear()
        self._detail.clear()
        self._results.clear()
        self._status_var.set("Starting…")

        thread = threading.Thread(target=self._grade_thread, args=(test_cases,), daemon=True)
        thread.start()

    def _stop(self):
        self._is_running = False
        self._status_var.set("Stopped by user")
        self._run_btn.config(state=tk.NORMAL)
        self._stop_btn.config(state=tk.DISABLED)

    def _grade_thread(self, test_cases: list[dict]):
        try:
            runner = ScriptRunner(
                timeout=Theme.TIMEOUT,
                utility_path=self._utility_path.get(),
                module_names=[m.strip() for m in self._module_names.get().split(",") if m.strip()],
            )
            mode            = self._mode.get()
            base_path       = self._base_path.get()
            assignment_path = self._assignment_path.get()
            check_stdout    = self._check_stdout.get()
            max_workers     = self._max_workers.get()

            # Find submissions
            student_paths = runner.find_student_submissions(assignment_path, mode)
            total = len(student_paths)
            self._set_status(f"Running base solution…")

            # Run base
            base_raws = runner.run_base_solution(base_path, test_cases, mode, assignment_path)
            if all(r.get("error") and r.get("returncode", 0) != 0 for r in base_raws):
                self._set_status("ERROR: Base solution failed to run.")
                return

            self._set_status(f"Grading {total} students (×{max_workers} parallel)…")

            completed = [0]

            def progress_cb(name, done, total_):
                if not self._is_running:
                    return
                completed[0] = done
                self._set_progress(f"{done}/{total_} — last: {name}")

            all_raw = runner.run_batch(
                student_paths, test_cases, mode, assignment_path,
                max_workers=max_workers,
                progress_callback=progress_cb,
            )

            if not self._is_running:
                return

            # Classify
            self._set_status("Classifying results…")
            results: list[StudentResult] = []
            for path in student_paths:
                if not self._is_running:
                    break
                name = os.path.basename(path)
                student_raws = all_raw.get(name, [])
                if not student_raws:
                    continue
                sr = process_student(
                    name=name,
                    path=path,
                    base_raws=base_raws,
                    student_raws=student_raws,
                    test_cases=test_cases,
                    check_stdout=check_stdout,
                )
                results.append(sr)

            self._results = results
            self.root.after(0, lambda: self._display_results(results))

        except Exception as e:
            msg = f"Error: {e}\n{traceback.format_exc()}"
            self._set_status(msg)
        finally:
            self._is_running = False
            self.root.after(0, lambda: self._run_btn.config(state=tk.NORMAL))
            self.root.after(0, lambda: self._stop_btn.config(state=tk.DISABLED))

    def _display_results(self, results: list[StudentResult]):
        self._table.load(results)
        self._summary.update(results)
        n = len(results)
        avg = sum(r.score for r in results) / n if n else 0
        self._set_status(f"Done — {n} students graded, avg {avg:.1f}%")
        self._set_progress("")

    # ------------------------------------------------------------------
    # Single submission test
    # ------------------------------------------------------------------

    def _test_single(self):
        if not self._base_path.get() or not self._assignment_path.get():
            messagebox.showerror("Missing paths",
                                 "Set both Base Solution and Assignment Path first.")
            return
        test_cases = self._get_test_cases()
        if not test_cases:
            messagebox.showerror("No test cases", "Add at least one test case.")
            return

        runner = ScriptRunner(
            timeout=Theme.TIMEOUT,
            utility_path=self._utility_path.get(),
            module_names=[m.strip() for m in self._module_names.get().split(",") if m.strip()],
        )
        mode            = self._mode.get()
        assignment_path = self._assignment_path.get()
        student_paths   = runner.find_student_submissions(assignment_path, mode)

        if not student_paths:
            messagebox.showerror("No submissions", "No student submissions found.")
            return

        path = _pick_submission_dialog(self.root, student_paths)
        if not path:
            return

        name = os.path.basename(path)
        self._set_status(f"Testing {name}…")

        def run():
            base_raws    = runner.run_base_solution(
                self._base_path.get(), test_cases, mode, assignment_path)
            student_raws = runner.run_student(path, test_cases, mode, assignment_path)
            sr = process_student(
                name=name, path=path,
                base_raws=base_raws, student_raws=student_raws,
                test_cases=test_cases, check_stdout=self._check_stdout.get(),
            )
            self.root.after(0, lambda: self._show_single(sr))

        threading.Thread(target=run, daemon=True).start()

    def _show_single(self, sr: StudentResult):
        self._results = [sr]
        self._table.load([sr])
        self._summary.update([sr])
        self._detail.show(sr)
        self._set_status(
            f"Single test — {sr.name}: {sr.category.label} ({sr.display_score})")

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def _on_student_select(self, result: StudentResult):
        self._detail.show(result)

    def _on_filter(self, category: Optional[str]):
        self._table.apply_filter(category)

    # ------------------------------------------------------------------
    # Report saving
    # ------------------------------------------------------------------

    def _save_report(self):
        if not self._results:
            messagebox.showinfo("Nothing to save", "Run the autograder first.")
            return
        path = filedialog.asksaveasfilename(
            title="Save Report",
            defaultextension=".md",
            filetypes=[("Markdown", "*.md"), ("Text", "*.txt"), ("All", "*.*")],
        )
        if not path:
            return
        report = _build_report(self._results)
        with open(path, "w", encoding="utf-8") as f:
            f.write(report)
        messagebox.showinfo("Saved", f"Report saved to:\n{path}")

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def _load_icon(self):
        icon_path = os.path.join(os.path.dirname(__file__), "..", Theme.ICON_PATH)
        icon_path = os.path.normpath(icon_path)
        if not os.path.exists(icon_path):
            return
        try:
            from PIL import Image, ImageTk
            img = Image.open(icon_path)
            self._icon = ImageTk.PhotoImage(img)
            self.root.iconphoto(True, self._icon)
        except Exception:
            pass
        if sys.platform == "darwin":
            try:
                from AppKit import NSApplication, NSImage
                ns = NSApplication.sharedApplication()
                ns.setApplicationIconImage_(NSImage.alloc().initWithContentsOfFile_(icon_path))
            except Exception:
                pass

    def _set_status(self, msg: str):
        self.root.after(0, lambda: self._status_var.set(msg))

    def _set_progress(self, msg: str):
        self.root.after(0, lambda: self._progress_var.set(msg))


# ---------------------------------------------------------------------------
# Test case widget (compact: stdin + optional file check side-by-side)
# ---------------------------------------------------------------------------

_PLACEHOLDER_INPUT = "Enter test input here…"
_PLACEHOLDER_FILE  = "Expected file content…"


class _TestCaseWidget(ttk.Frame):
    def __init__(self, parent, index: int, remove_cb):
        super().__init__(parent, style="Panel.TFrame", padding=4)
        self._index     = index
        self._remove_cb = remove_cb
        self._has_input = False
        self._has_file  = False
        self._build()

    def _build(self):
        self.columnconfigure(1, weight=2)
        self.columnconfigure(3, weight=1)

        # Header
        hdr = ttk.Frame(self)
        hdr.grid(row=0, column=0, columnspan=4, sticky="ew")
        ttk.Label(hdr, text=f"Test Case {self._index + 1}",
                  style="Header.TLabel").pack(side="left")
        ttk.Button(hdr, text="✕", width=3,
                   command=lambda: self._remove_cb(self)).pack(side="right")

        # stdin
        ttk.Label(self, text="stdin:").grid(row=1, column=0, sticky="nw", padx=(0, 4), pady=2)
        self._input = tk.Text(self, height=3, width=22, font=Theme.FONT_MONO,
                               bg=Theme.ENTRY_BG, fg=Theme.FG_DIM,
                               insertbackground=Theme.FG, relief="flat",
                               highlightthickness=1,
                               highlightbackground=Theme.BORDER,
                               highlightcolor=Theme.ACCENT)
        self._input.grid(row=1, column=1, sticky="ew", pady=2)
        self._input.insert("end", _PLACEHOLDER_INPUT)
        self._input.bind("<FocusIn>",  lambda e: self._focus_in(self._input,  "_has_input",  _PLACEHOLDER_INPUT))
        self._input.bind("<FocusOut>", lambda e: self._focus_out(self._input, "_has_input",  _PLACEHOLDER_INPUT))

        # File check (optional)
        fc = ttk.Frame(self)
        fc.grid(row=1, column=2, columnspan=2, sticky="nsew", padx=(8, 0))
        fc.columnconfigure(1, weight=1)

        ttk.Label(fc, text="File check\n(opt):").grid(row=0, column=0, sticky="nw", padx=(0, 4))
        fname_row = ttk.Frame(fc)
        fname_row.grid(row=0, column=1, sticky="ew")
        ttk.Label(fname_row, text="filename:").pack(side="left", padx=(0, 4))
        self._fname = ttk.Entry(fname_row, width=14)
        self._fname.pack(side="left", fill="x", expand=True)

        self._file_content = tk.Text(fc, height=3, width=18, font=Theme.FONT_MONO,
                                      bg=Theme.ENTRY_BG, fg=Theme.FG_DIM,
                                      insertbackground=Theme.FG, relief="flat",
                                      highlightthickness=1,
                                      highlightbackground=Theme.BORDER,
                                      highlightcolor=Theme.ACCENT)
        self._file_content.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(2, 0))
        self._file_content.insert("end", _PLACEHOLDER_FILE)
        self._file_content.bind("<FocusIn>",  lambda e: self._focus_in(self._file_content,  "_has_file",  _PLACEHOLDER_FILE))
        self._file_content.bind("<FocusOut>", lambda e: self._focus_out(self._file_content, "_has_file",  _PLACEHOLDER_FILE))

    def _focus_in(self, widget: tk.Text, attr: str, placeholder: str):
        if not getattr(self, attr):
            widget.delete("1.0", "end")
            widget.configure(fg=Theme.FG)

    def _focus_out(self, widget: tk.Text, attr: str, placeholder: str):
        content = widget.get("1.0", "end").strip()
        if not content:
            widget.delete("1.0", "end")
            widget.insert("end", placeholder)
            widget.configure(fg=Theme.FG_DIM)
            setattr(self, attr, False)
        else:
            setattr(self, attr, True)

    def is_valid(self) -> bool:
        txt = self._input.get("1.0", "end").strip()
        return bool(txt) and txt != _PLACEHOLDER_INPUT

    def get_data(self) -> dict:
        raw_input = self._input.get("1.0", "end").strip()
        if raw_input == _PLACEHOLDER_INPUT:
            raw_input = ""
        raw_file = self._file_content.get("1.0", "end").strip()
        if raw_file == _PLACEHOLDER_FILE:
            raw_file = ""
        return {
            "input": raw_input.split("\n") if raw_input else [],
            "expected_filename":     self._fname.get().strip(),
            "expected_file_content": raw_file,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pick_submission_dialog(root: tk.Tk, paths: list[str]) -> Optional[str]:
    dialog = tk.Toplevel(root)
    dialog.title("Select Submission")
    dialog.geometry("400x320")
    dialog.transient(root)
    dialog.grab_set()
    dialog.configure(bg=Theme.BG)

    ttk.Label(dialog, text="Choose a submission to test:").pack(pady=(12, 4), padx=12)

    lb = tk.Listbox(dialog, font=Theme.FONT_MONO,
                    bg=Theme.PANEL, fg=Theme.FG,
                    selectbackground=Theme.SEL_BG,
                    borderwidth=0, relief="flat")
    lb.pack(fill="both", expand=True, padx=12, pady=4)
    for p in paths:
        lb.insert("end", os.path.basename(p))

    chosen = [None]

    def ok():
        sel = lb.curselection()
        if sel:
            chosen[0] = paths[sel[0]]
        dialog.destroy()

    btn_row = ttk.Frame(dialog)
    btn_row.pack(pady=8)
    ttk.Button(btn_row, text="Select", command=ok).pack(side="left", padx=6)
    ttk.Button(btn_row, text="Cancel", command=dialog.destroy).pack(side="left")

    dialog.wait_window()
    return chosen[0]


def _build_report(results: list[StudentResult]) -> str:
    from engine.models import StudentCategory
    lines = ["# Autograder Report\n"]

    # Summary counts
    from collections import Counter
    counts = Counter(r.category.value for r in results)
    n = len(results)
    avg = sum(r.score for r in results) / n if n else 0

    lines.append(f"**{n} students graded — avg {avg:.1f}%**\n")
    for cat in StudentCategory:
        c = counts.get(cat.value, 0)
        lines.append(f"- {cat.emoji} {cat.label}: {c}")
    lines.append("")

    # Per-category sections
    for cat in StudentCategory:
        group = [r for r in results if r.category == cat]
        if not group:
            continue
        lines.append(f"\n## {cat.emoji} {cat.label} ({len(group)})\n")
        for r in sorted(group, key=lambda x: x.name):
            note_str = " | ".join(r.notes) if r.notes else ""
            lines.append(f"- **{r.name}** — {r.display_score}  {note_str}")

    return "\n".join(lines) + "\n"
