"""Student classification engine.

Converts a list of raw runner results into fully classified StudentResult
objects, including behavioral annotations.
"""

from __future__ import annotations

import os

from engine.comparator import classify_test
from engine.models import MatchTier, StudentCategory, StudentResult, TestResult


def process_student(
    name: str,
    path: str,
    base_raws: list[dict],
    student_raws: list[dict],
    test_cases: list[dict],
    check_stdout: bool = True,
) -> StudentResult:
    """Build a full StudentResult from raw runner outputs.

    Args:
        name: Student identifier (folder/file basename)
        path: Filesystem path to student submission
        base_raws: Raw result dicts from base solution (one per test case)
        student_raws: Raw result dicts from student (one per test case)
        test_cases: Original test case configs (for expected file metadata)
        check_stdout: When False, only file output is graded
    """
    test_results: list[TestResult] = []

    for i, (base_raw, student_raw) in enumerate(zip(base_raws, student_raws)):
        tc = test_cases[i] if i < len(test_cases) else {}
        tr = classify_test(
            test_num=i + 1,
            input_lines=tc.get("input", []),
            base_raw=base_raw,
            student_raw=student_raw,
            expected_override=tc.get("expected_file_content", ""),
            expected_fname=tc.get("expected_filename", ""),
            check_stdout=check_stdout,
        )
        test_results.append(tr)

    category, overall_tier = _classify(test_results)
    score = _score(test_results)
    notes = _generate_notes(test_results, student_raws)

    return StudentResult(
        name=name,
        path=path,
        category=category,
        score=score,
        test_results=test_results,
        overall_match_tier=overall_tier,
        notes=notes,
    )


def process_base(
    base_raws: list[dict],
    test_cases: list[dict],
) -> list[dict]:
    """Return base raws as-is (they are the reference; no classification needed)."""
    return base_raws


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _classify(tests: list[TestResult]) -> tuple[StudentCategory, MatchTier]:
    """Determine overall category and best match tier."""
    if not tests:
        return StudentCategory.CRASH, MatchTier.ERROR

    tiers = [t.match_tier for t in tests]

    # Any crash → CRASH (unless the crash only affects some tests)
    all_error = all(t == MatchTier.ERROR for t in tiers)
    any_error = any(t == MatchTier.ERROR for t in tiers)

    if all_error:
        return StudentCategory.CRASH, MatchTier.ERROR

    # Score-based classification
    passing = [t for t in tests if t.passed]
    n_pass = len(passing)
    n_total = len(tests)

    if n_pass == 0:
        if any_error:
            return StudentCategory.CRASH, MatchTier.ERROR
        return StudentCategory.LOGIC_FAIL, MatchTier.MISMATCH

    if n_pass < n_total:
        # Mix: some pass, some don't
        if any_error:
            return StudentCategory.CRASH, MatchTier.ERROR
        return StudentCategory.PARTIAL, _best_tier(tiers)

    # All passing — determine quality tier
    best = _best_tier(tiers)
    if best in (MatchTier.EXACT, MatchTier.NORMALIZED):
        return StudentCategory.PERFECT, best
    if best in (MatchTier.SEMANTIC, MatchTier.FILE_ONLY):
        return StudentCategory.COSMETIC, best
    return StudentCategory.PARTIAL, best


def _best_tier(tiers: list[MatchTier]) -> MatchTier:
    """Return the best (strongest) tier from a list."""
    order = [
        MatchTier.EXACT,
        MatchTier.NORMALIZED,
        MatchTier.SEMANTIC,
        MatchTier.FILE_ONLY,
        MatchTier.MISMATCH,
        MatchTier.ERROR,
    ]
    for t in order:
        if t in tiers:
            return t
    return MatchTier.ERROR


def _score(tests: list[TestResult]) -> float:
    if not tests:
        return 0.0
    return (sum(1 for t in tests if t.passed) / len(tests)) * 100.0


def _generate_notes(
    test_results: list[TestResult],
    student_raws: list[dict],
) -> list[str]:
    """Generate human-readable behavioral annotations for a student."""
    notes: list[str] = []

    # --- Error annotation ---
    error_types: list[str] = []
    for raw in student_raws:
        et = raw.get("error_type")
        if et and et not in error_types:
            error_types.append(et)
    for et in error_types:
        if et == "Timeout":
            notes.append("Execution timed out (infinite loop or blocking input?)")
        elif et == "EOFError":
            notes.append("Requested more input() than provided (EOFError)")
        elif et in ("ModuleNotFoundError", "ImportError"):
            notes.append(f"Import error — missing module or wrong import path")
        elif et in ("SyntaxError", "IndentationError", "TabError"):
            notes.append(f"{et} — code does not parse")
        elif et:
            notes.append(f"{et} during execution")

        # Surface the actual error line for quick diagnosis
        for raw in student_raws:
            if raw.get("error_type") == et:
                stderr = raw.get("stderr", "")
                if stderr:
                    last_line = [l for l in stderr.strip().split("\n") if l.strip()]
                    if last_line:
                        notes.append(f"  → {last_line[-1].strip()}")
                break

    # --- Semantic mismatch annotations ---
    for tr in test_results:
        if tr.match_tier == MatchTier.SEMANTIC:
            # All values matched semantically — note prompt differences
            notes.append(_prompt_diff_note(tr))
            break

    # --- Rigid input validation detection ---
    for tr in test_results:
        if tr.match_tier in (MatchTier.MISMATCH, MatchTier.ERROR):
            if _has_invalid_loop(tr.student_stdout):
                notes.append(
                    "Rigid input validation — 'Invalid command' repeated for "
                    "verbose inputs (missing .lower() or .startswith() normalization)"
                )
                break

    # --- Missing output detection ---
    for tr in test_results:
        if not tr.student_stdout and tr.base_stdout:
            notes.append("Produced no stdout output")
            break

    # --- File output notes ---
    for tr in test_results:
        for detail in tr.file_mismatch_details:
            if "Missing" in detail:
                notes.append(f"Did not generate output file ({detail})")
            else:
                notes.append(f"File output mismatch: {detail}")

    return notes


def _prompt_diff_note(tr: TestResult) -> str:
    """Produce a short description of how the student's prompts differed."""
    import difflib
    base_lines    = [l.strip() for l in (tr.base_stdout or "").split("\n") if l.strip()]
    student_lines = [l.strip() for l in (tr.student_stdout or "").split("\n") if l.strip()]

    # Find the first line that differs
    sm = difflib.SequenceMatcher(None, base_lines, student_lines)
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "replace":
            base_sample    = base_lines[i1] if i1 < len(base_lines) else ""
            student_sample = student_lines[j1] if j1 < len(student_lines) else ""
            if base_sample and student_sample:
                return (
                    f"Prompt differs: '{_truncate(base_sample)}' "
                    f"vs '{_truncate(student_sample)}'"
                )
    return "Prompt text differs from base solution"


def _has_invalid_loop(stdout: str) -> bool:
    """Detect rigid command-rejection loops in student output.

    Only counts lines where 'invalid' refers to a COMMAND, not a contact number.
    'Invalid contact number.' is *correct* behavior for out-of-range views; we
    must not penalise it as rigid validation.

    Triggers when the student produces ≥ 3 command-rejection messages, which
    strongly implies they only accept single-letter commands and reject the
    verbose alternatives used in test cases.
    """
    if not stdout:
        return False
    count = 0
    for line in stdout.lower().split("\n"):
        line = line.strip()
        if not line:
            continue
        # 'Invalid contact number.' / 'Invalid contact.' = correct behaviour → skip
        if "contact" in line or "number" in line:
            continue
        if "invalid" in line or "try again" in line:
            count += 1
    return count >= 3


def _truncate(s: str, n: int = 40) -> str:
    return s if len(s) <= n else s[:n] + "…"
