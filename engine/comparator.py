"""Multi-tier output comparison pipeline.

Tiers (weakest → strongest match):
  EXACT      – raw stdout identical
  NORMALIZED – whitespace-normalized match
  SEMANTIC   – extracted data values match; prompt text ignored
  FILE_ONLY  – stdout differs but file output (CSV, TXT…) is correct
  MISMATCH   – values differ
  ERROR      – crash / timeout
"""

from __future__ import annotations

import re
from typing import Optional

from engine.models import MatchTier, TestResult


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def classify_test(
    test_num: int,
    input_lines: list[str],
    base_raw: dict,
    student_raw: dict,
    expected_override: str = "",
    expected_fname: str = "",
    check_stdout: bool = True,
) -> TestResult:
    """Run the full comparison cascade and return a TestResult.

    Args:
        test_num: 1-based test case index
        input_lines: stdin lines fed to both programs
        base_raw: raw result dict from runner for the base solution
        student_raw: raw result dict from runner for the student
        expected_override: optional manual expected file content
        expected_fname: filename key to check in file dicts
        check_stdout: when False, only file output is graded
    """
    base_stdout   = base_raw.get("stdout", "") or ""
    student_stdout = student_raw.get("stdout", "") or ""
    base_files    = base_raw.get("files") or {}
    student_files = student_raw.get("files") or {}
    error         = student_raw.get("error")
    error_type    = student_raw.get("error_type")

    # If there is an expected file content override, inject it as the base
    if expected_override and expected_fname:
        base_files = dict(base_files)
        base_files[expected_fname] = expected_override

    extractor = SemanticExtractor()
    sem_base    = extractor.extract(base_stdout, input_lines)
    sem_student = extractor.extract(student_stdout, input_lines)

    # --- Crash / error -------------------------------------------------------
    if error and student_raw.get("returncode", 0) != 0:
        file_ok, file_details = _file_match(base_files, student_files, expected_fname)
        return TestResult(
            test_num=test_num,
            input_lines=input_lines,
            base_stdout=base_stdout,
            student_stdout=student_stdout,
            base_files=base_files,
            student_files=student_files,
            match_tier=MatchTier.ERROR,
            stdout_match=False,
            file_match=file_ok,
            file_mismatch_details=file_details,
            semantic_values_base=sem_base,
            semantic_values_student=sem_student,
            error=error,
            error_type=error_type,
        )

    # --- Stdout tiers --------------------------------------------------------
    stdout_tier = MatchTier.MISMATCH
    stdout_match = False

    if check_stdout:
        if _exact_match(base_stdout, student_stdout):
            stdout_tier  = MatchTier.EXACT
            stdout_match = True
        elif _normalized_match(base_stdout, student_stdout):
            stdout_tier  = MatchTier.NORMALIZED
            stdout_match = True
        elif sem_base == sem_student and sem_base:
            stdout_tier  = MatchTier.SEMANTIC
            stdout_match = True
    else:
        # Stdout grading disabled — treat as passing
        stdout_match = True
        stdout_tier  = MatchTier.NORMALIZED

    # --- File output ---------------------------------------------------------
    file_ok, file_details = _file_match(base_files, student_files, expected_fname)

    # --- Overall tier --------------------------------------------------------
    if stdout_match and file_ok:
        tier = stdout_tier
    elif not check_stdout and file_ok:
        tier = MatchTier.FILE_ONLY
    elif file_ok and not stdout_match:
        tier = MatchTier.FILE_ONLY
    else:
        tier = MatchTier.MISMATCH

    return TestResult(
        test_num=test_num,
        input_lines=input_lines,
        base_stdout=base_stdout,
        student_stdout=student_stdout,
        base_files=base_files,
        student_files=student_files,
        match_tier=tier,
        stdout_match=stdout_match,
        file_match=file_ok,
        file_mismatch_details=file_details,
        semantic_values_base=sem_base,
        semantic_values_student=sem_student,
        error=error,
        error_type=error_type,
    )


# ---------------------------------------------------------------------------
# Tier implementations
# ---------------------------------------------------------------------------

def _exact_match(a: str, b: str) -> bool:
    return a == b


def _normalized_match(a: str, b: str) -> bool:
    return _normalize(a) == _normalize(b)


def _normalize(text: str) -> list[str]:
    """Strip, collapse whitespace, remove blank lines."""
    lines = []
    for line in text.strip().split("\n"):
        line = " ".join(line.split())
        if line:
            lines.append(line)
    return lines


def _file_match(
    base_files: dict,
    student_files: dict,
    expected_fname: str = "",
) -> tuple[bool, list[str]]:
    """Compare file outputs. Returns (match, mismatch_details).

    Returns (True, []) when:
      - No files are configured for comparison, OR
      - The base itself didn't generate the expected file (we can't penalise
        the student for a file the reference didn't produce either).
    """
    if not base_files:
        return True, []  # No file grading configured

    details: list[str] = []
    ok = True

    keys = [expected_fname] if expected_fname and expected_fname in base_files else list(base_files.keys())

    for key in keys:
        base_content    = base_files.get(key)
        # Fuzzy key lookup for student files (case-insensitive)
        student_content = _fuzzy_get(student_files, key)

        if base_content is None:
            # Base didn't generate this file either — skip (no penalty)
            continue

        if student_content is None:
            ok = False
            details.append(f"Missing file: {key}")
            continue

        if isinstance(base_content, bytes) or isinstance(student_content, bytes):
            # Binary file — exact byte comparison
            if base_content != student_content:
                ok = False
                details.append(f"Binary contents differ: {key}")
        else:
            # Text file — normalise whitespace / line endings before comparing
            # so csv.writer (\r\n) vs manual f.write (\n) differences don't matter
            if _normalize_file(base_content) != _normalize_file(student_content):
                ok = False
                details.append(f"Contents differ: {key}")

    return ok, details


def _normalize_file(content: str | bytes) -> list[str]:
    """Normalise a text file for comparison.

    - Strips leading/trailing whitespace from each line
    - Removes blank lines
    - Strips carriage returns (handles csv.writer \\r\\n vs manual \\n)

    More conservative than _normalize() so CSV commas/values are preserved.
    """
    if isinstance(content, bytes):
        return [content]  # bytes: compare as-is (handled in caller)
    lines = []
    for line in content.splitlines():
        line = line.strip()
        if line:
            lines.append(line)
    return lines


def _fuzzy_get(d: dict, key: str) -> Optional[str | bytes]:
    """Get dict value by key, falling back to case-insensitive match."""
    if key in d:
        return d[key]
    key_lower = key.lower()
    for k, v in d.items():
        if k.lower() == key_lower:
            return v
    return None


# ---------------------------------------------------------------------------
# Semantic Extractor
# ---------------------------------------------------------------------------

class SemanticExtractor:
    """Extracts meaningful data values from program stdout.

    Filters out:
      - Pure prompt lines ("Enter a filename: ", "Command: ")
      - Lines echoing the provided input
      - Decorative titles and menu headers

    Captures:
      - Numbered list items  ("1. Ally Gator")
      - Labeled values       ("Name: Ally Gator")
      - Status messages      ("was added", "was removed", "invalid command")
      - Error / not-found messages
    """

    _NUMBERED_ITEM = re.compile(r"^\d+\.\s+.+")
    _LABELED_VALUE = re.compile(r"^[A-Za-z][\w\s]*?:\s+\S")
    _STATUS_VERBS  = re.compile(
        r"\b(was added|was removed|has been updated|invalid|not found|"
        r"error|no existing|thank you|goodbye|welcome)\b",
        re.IGNORECASE,
    )
    # Lines that end with prompt punctuation and carry no data
    _PROMPT_ONLY   = re.compile(r"^[^:]*[:\?]\s*$")
    # Decorative headers / titles to skip
    _SKIP_PATTERNS = re.compile(
        r"^(COMMAND MENU|={3,}|-{3,}|\*{3,}|Contact Manager|"
        r"Welcome to .+|Thank you for using.+|Goodbye!?)$",
        re.IGNORECASE,
    )
    # Menu option lines like "[D]isplay - ..." or "[D] - ..."
    _MENU_LINE     = re.compile(r"^\[?\w+\]?\s*[-–—]\s*\w")

    def extract(self, stdout: str, input_lines: list[str]) -> list[tuple[str, str]]:
        """Return a list of (type, value) semantic tokens from stdout."""
        if not stdout:
            return []

        input_set = {line.strip() for line in input_lines}
        results: list[tuple[str, str]] = []

        for raw_line in stdout.split("\n"):
            line = raw_line.strip()
            if not line:
                continue

            # Skip lines that are verbatim input echoes
            if line in input_set:
                continue

            # Skip known decorative patterns
            if self._SKIP_PATTERNS.match(line):
                continue

            # Skip menu option lines
            if self._MENU_LINE.match(line):
                continue

            # Skip pure prompt lines (nothing after the colon/question mark)
            if self._PROMPT_ONLY.match(line):
                continue

            # Classify
            if self._NUMBERED_ITEM.match(line):
                results.append(("item", line))
            elif self._STATUS_VERBS.search(line):
                results.append(("status", self._normalize_status(line)))
            elif self._LABELED_VALUE.match(line):
                # Only keep if it carries actual data (not a prompt)
                if not self._PROMPT_ONLY.match(line):
                    results.append(("label", line))
            else:
                # Non-empty, non-prompt, non-menu — keep as generic text
                results.append(("text", line))

        return results

    def _normalize_status(self, line: str) -> str:
        """Reduce status messages to a canonical form for comparison.

        e.g. 'Ally Gator was removed and the file "contacts.csv" has been
             updated accordingly.' → 'ally gator was removed'
        """
        line = line.lower()
        # Drop file references
        line = re.sub(r'and the file.*$', '', line)
        line = re.sub(r'"[^"]*"', '', line)
        # Drop parenthetical / trailing decoration
        line = re.sub(r'\(.*?\)', '', line)
        return " ".join(line.split()).rstrip(".,!")


# ---------------------------------------------------------------------------
# Diff utilities (used by the UI)
# ---------------------------------------------------------------------------

def unified_diff_lines(
    base: str, student: str, context: int = 3
) -> list[tuple[str, str]]:
    """Return (tag, line) pairs for a side-by-side diff.

    tag is one of: 'equal', 'replace', 'insert', 'delete'
    """
    import difflib
    base_lines    = (base or "").splitlines()
    student_lines = (student or "").splitlines()
    sm = difflib.SequenceMatcher(None, base_lines, student_lines)
    result = []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            for line in base_lines[i1:i2]:
                result.append(("equal", line))
        elif op == "replace":
            for line in base_lines[i1:i2]:
                result.append(("delete", line))
            for line in student_lines[j1:j2]:
                result.append(("insert", line))
        elif op == "delete":
            for line in base_lines[i1:i2]:
                result.append(("delete", line))
        elif op == "insert":
            for line in student_lines[j1:j2]:
                result.append(("insert", line))
    return result
