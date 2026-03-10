"""Script execution engine with parallel student grading and tempdir sandboxing."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable, Optional


# Data file extensions eligible for reset between test cases
_DATA_EXTENSIONS = frozenset({".csv", ".txt", ".json", ".xml", ".dat", ".tsv", ".ini", ".cfg"})

# OS/editor system files that should never be copied into student sandboxes
_SYSTEM_FILES = frozenset({".ds_store", "thumbs.db", "desktop.ini", ".gitkeep", ".gitignore"})


class ScriptRunner:
    """Executes student Python scripts in isolated sandboxes.

    Each student gets one temp directory for all their test cases.
    Data files (CSV, TXT, etc.) from the assignment root are refreshed
    between test cases so earlier runs don't corrupt later ones.
    """

    def __init__(
        self,
        python_exe: str = sys.executable,
        timeout: int = 30,
        utility_path: str = "",
        module_names: list[str] | None = None,
    ):
        self.python_exe = python_exe
        self.timeout = timeout
        self.utility_path = utility_path
        self.module_names = module_names or []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def find_main_script(self, folder_path: str) -> Optional[str]:
        """Find the main Python script in a student folder.

        Priority:
          1. File whose name starts with the folder name (e.g. 'jc_ica5.py' in 'JC/')
          2. File containing 'ica' or 'pca' (case-insensitive)
          3. First valid .py file alphabetically
        """
        folder = Path(folder_path)
        python_files = list(folder.glob("*.py"))
        if not python_files:
            return None

        skip = {"fibonacci_ratio.py", "graphics.py"}
        for name in self.module_names:
            n = name.strip()
            if not n.endswith(".py"):
                n += ".py"
            skip.add(n.lower())

        valid = sorted(
            [f for f in python_files if f.name.lower() not in skip],
            key=lambda f: f.name,
        )
        if not valid:
            return None

        folder_lower = folder.name.lower()
        for f in valid:
            if f.name.lower().startswith(folder_lower):
                return str(f)

        for f in valid:
            low = f.name.lower()
            if "ica" in low or "pca" in low or "lca" in low or "hwa" in low:
                return str(f)

        return str(valid[0])

    def find_student_submissions(
        self, assignment_path: str, mode: str
    ) -> list[str]:
        """Return paths to all student submissions.

        mode='folder' → subdirs containing .py files
        mode='file'   → .py files directly in the folder
        """
        root = Path(assignment_path)
        paths = []
        if mode == "file":
            for item in sorted(root.iterdir()):
                if item.is_file() and item.suffix == ".py":
                    paths.append(str(item))
        else:
            for item in sorted(root.iterdir()):
                if item.is_dir() and not item.name.startswith("__"):
                    if list(item.glob("*.py")):
                        paths.append(str(item))
        return paths

    def run_student(
        self,
        student_path: str,
        test_cases: list[dict],
        mode: str,
        assignment_root: str,
        strict_stdout: bool = True,
    ) -> list[dict]:
        """Run all test cases for one student inside a single temp sandbox.

        Returns a list of raw result dicts (one per test case):
          {test_num, input, stdout, files, error, error_type, returncode}
        """
        if mode == "file":
            main_script_path = student_path
            source_dir = str(Path(student_path).parent)
        else:
            main_script_path = self.find_main_script(student_path)
            source_dir = student_path

        if not main_script_path:
            return [
                self._error_result(i + 1, tc["input"], "No main script found", "FileNotFound")
                for i, tc in enumerate(test_cases)
            ]

        script_name = Path(main_script_path).name
        results = []

        with tempfile.TemporaryDirectory() as tmp:
            # Copy student files once
            self._copy_dir(source_dir, tmp, py_only=False)

            # Track which non-.py files came with the student's original submission
            # so we know what to preserve vs. clean up between test cases
            original_data_files = self._list_data_files(tmp)

            for i, tc in enumerate(test_cases):
                # Remove files generated during the previous test case
                # (e.g. contacts.csv the student wrote) before resetting the clean copy
                if i > 0:
                    self._clean_generated_files(tmp, original_data_files)

                # Reset clean data files from assignment root (e.g. empty contacts.csv)
                self._reset_data_files(assignment_root, tmp)

                # Snapshot AFTER reset but BEFORE execution so auto-detection only
                # captures files the student *generates*, not the ones we placed
                pre_run_files = self._list_data_files(tmp)

                result = self._run_one(tmp, script_name, tc["input"])
                result["test_num"] = i + 1
                result["input"] = tc["input"]

                # Collect expected file output
                expected_fname = tc.get("expected_filename", "").strip()
                result["files"] = self._read_output_files(tmp, expected_fname, pre_run_files)

                results.append(result)

        return results

    def run_batch(
        self,
        student_paths: list[str],
        test_cases: list[dict],
        mode: str,
        assignment_root: str,
        max_workers: int = 4,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> dict[str, list[dict]]:
        """Grade all students in parallel using a thread pool.

        Returns {student_name: [raw_result_dicts]}.
        progress_callback(student_name, completed, total) called after each.
        """
        total = len(student_paths)
        all_results: dict[str, list[dict]] = {}

        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            future_to_name = {
                pool.submit(
                    self.run_student, path, test_cases, mode, assignment_root
                ): os.path.basename(path)
                for path in student_paths
            }

            completed = 0
            for future in as_completed(future_to_name):
                name = future_to_name[future]
                completed += 1
                try:
                    all_results[name] = future.result()
                except Exception as exc:
                    all_results[name] = [
                        self._error_result(i + 1, tc["input"], str(exc), "InternalError")
                        for i, tc in enumerate(test_cases)
                    ]
                if progress_callback:
                    progress_callback(name, completed, total)

        return all_results

    def run_base_solution(
        self,
        base_path: str,
        test_cases: list[dict],
        mode: str,
        assignment_root: str,
    ) -> list[dict]:
        """Run the base/reference solution against all test cases."""
        return self.run_student(base_path, test_cases, mode, assignment_root)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_env(self) -> dict:
        env = os.environ.copy()
        if self.utility_path:
            existing = env.get("PYTHONPATH", "")
            env["PYTHONPATH"] = (
                self.utility_path + os.pathsep + existing if existing else self.utility_path
            )
        return env

    def _run_one(self, cwd: str, script_name: str, input_lines: list[str]) -> dict:
        """Execute one script in cwd and return a raw result dict."""
        input_text = "\n".join(input_lines) + "\n"
        try:
            proc = subprocess.run(
                [self.python_exe, script_name],
                input=input_text,
                text=True,
                capture_output=True,
                cwd=cwd,
                env=self._build_env(),
                timeout=self.timeout,
            )
            error_type = None
            error_msg = None
            if proc.returncode != 0:
                stderr = proc.stderr
                error_type = self._classify_error(stderr)
                error_msg = stderr.strip()

            return {
                "stdout": proc.stdout,
                "stderr": proc.stderr,
                "returncode": proc.returncode,
                "error": error_msg,
                "error_type": error_type,
                "files": {},
            }
        except subprocess.TimeoutExpired:
            return {
                "stdout": "",
                "stderr": "",
                "returncode": -1,
                "error": f"Execution timeout ({self.timeout}s)",
                "error_type": "Timeout",
                "files": {},
            }
        except Exception as e:
            return {
                "stdout": "",
                "stderr": "",
                "returncode": -1,
                "error": str(e),
                "error_type": "InternalError",
                "files": {},
            }

    def _classify_error(self, stderr: str) -> str:
        """Extract a short error type label from stderr."""
        for kind in (
            "SyntaxError", "IndentationError", "TabError",
            "NameError", "AttributeError", "TypeError",
            "ValueError", "ImportError", "ModuleNotFoundError",
            "FileNotFoundError", "EOFError", "RecursionError",
            "ZeroDivisionError", "IndexError", "KeyError",
        ):
            if kind in stderr:
                return kind
        return "RuntimeError"

    def _copy_dir(self, src: str, dst: str, py_only: bool = False):
        """Copy files from src into dst (flat copy, no subdirs).

        System/OS files (.DS_Store, Thumbs.db, etc.) are always skipped.
        """
        for item in os.listdir(src):
            s = os.path.join(src, item)
            d = os.path.join(dst, item)
            if not os.path.isfile(s):
                continue
            if item.lower() in _SYSTEM_FILES:
                continue
            if py_only and not item.endswith(".py"):
                continue
            shutil.copy2(s, d)

    def _list_data_files(self, directory: str) -> set[str]:
        """Return names of non-.py files currently in directory."""
        return {
            item for item in os.listdir(directory)
            if os.path.isfile(os.path.join(directory, item))
            and not item.endswith(".py")
            and not item.endswith(".pyc")
        }

    def _reset_data_files(self, assignment_root: str, tmp: str):
        """Restore original data files from assignment_root into tmp.

        Only recognized data extensions (.csv, .txt, .json, …) are copied so
        that system files (ICA5.pdf, .DS_Store, etc.) never pollute the sandbox.
        """
        if not assignment_root or not os.path.isdir(assignment_root):
            return
        for item in os.listdir(assignment_root):
            s = os.path.join(assignment_root, item)
            if not os.path.isfile(s):
                continue
            ext = os.path.splitext(item)[1].lower()
            if ext not in _DATA_EXTENSIONS:
                continue
            shutil.copy2(s, os.path.join(tmp, item))

    def _clean_generated_files(self, tmp: str, original_data_files: set[str]):
        """Remove non-.py files that were generated during the previous test run.

        Preserves files that came with the student's original submission folder.
        After this call, _reset_data_files() restores the clean assignment data,
        guaranteeing each test case starts from a known-good state.
        """
        for item in list(os.listdir(tmp)):
            path = os.path.join(tmp, item)
            if not os.path.isfile(path):
                continue
            if item.endswith((".py", ".pyc")):
                continue
            if item not in original_data_files:
                try:
                    os.remove(path)
                except OSError:
                    pass

    def _read_output_files(
        self, tmp: str, expected_fname: str, pre_data_files: set[str]
    ) -> dict[str, str | bytes | None]:
        """Read the expected output file from the temp directory.

        If expected_fname is given, read that (with fuzzy case matching).
        Otherwise, auto-detect newly generated files by comparing against
        the pre-run data file snapshot.
        """
        files: dict[str, str | bytes | None] = {}

        if expected_fname:
            # Try exact match first, then case-insensitive
            target = self._fuzzy_find(tmp, expected_fname)
            files[expected_fname] = self._read_file(target) if target else None
        else:
            # Auto-detect: find files that appeared after execution
            current = {
                item for item in os.listdir(tmp)
                if os.path.isfile(os.path.join(tmp, item))
                and not item.endswith((".py", ".pyc"))
            }
            new_files = current - pre_data_files
            for fname in sorted(new_files):
                path = os.path.join(tmp, fname)
                files[fname] = self._read_file(path)

        return files

    def _fuzzy_find(self, directory: str, filename: str) -> Optional[str]:
        """Find a file in directory matching filename case-insensitively."""
        target_lower = filename.lower()
        for item in os.listdir(directory):
            if item.lower() == target_lower:
                return os.path.join(directory, item)
        return None

    def _read_file(self, path: str) -> str | bytes | None:
        """Read a file as text (fallback to bytes for binary files)."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except UnicodeDecodeError:
            with open(path, "rb") as f:
                return f.read()
        except OSError:
            return None

    def _error_result(
        self, test_num: int, input_lines: list[str], msg: str, error_type: str
    ) -> dict:
        return {
            "test_num": test_num,
            "input": input_lines,
            "stdout": "",
            "stderr": "",
            "returncode": -1,
            "error": msg,
            "error_type": error_type,
            "files": {},
        }
