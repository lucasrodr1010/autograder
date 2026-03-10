"""Data classes for autograder results."""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class MatchTier(Enum):
    """Comparison result tier, from strongest to weakest match."""
    EXACT      = "exact"       # Raw stdout identical
    NORMALIZED = "normalized"  # Whitespace-normalized match
    SEMANTIC   = "semantic"    # Extracted values match, prompts differ
    FILE_ONLY  = "file_only"   # Stdout differs but file output correct
    MISMATCH   = "mismatch"    # Values differ
    ERROR      = "error"       # Crashed / timeout / syntax error


class StudentCategory(Enum):
    """Overall student classification."""
    PERFECT    = "perfect"     # All tests EXACT or NORMALIZED
    COSMETIC   = "cosmetic"    # All logic correct; only prompt wording differs
    PARTIAL    = "partial"     # Mix of passes and failures
    LOGIC_FAIL = "logic_fail"  # Code ran but produced wrong behavior
    CRASH      = "crash"       # Runtime / syntax / import / timeout error

    @property
    def label(self) -> str:
        return {
            "perfect":    "Perfect",
            "cosmetic":   "Cosmetic",
            "partial":    "Partial",
            "logic_fail": "Logic Fail",
            "crash":      "Crash",
        }[self.value]

    @property
    def emoji(self) -> str:
        return {
            "perfect":    "✅",
            "cosmetic":   "🔵",
            "partial":    "🟡",
            "logic_fail": "🟠",
            "crash":      "❌",
        }[self.value]


@dataclass
class TestResult:
    """Result of running one test case against one student submission."""
    test_num: int
    input_lines: list[str]
    base_stdout: str
    student_stdout: str
    base_files: dict[str, str | bytes | None]
    student_files: dict[str, str | bytes | None]
    match_tier: MatchTier
    stdout_match: bool          # True if stdout passes at any tier
    file_match: bool            # True if file output matches
    file_mismatch_details: list[str]
    semantic_values_base: list[tuple[str, str]]    # [(type, value), ...]
    semantic_values_student: list[tuple[str, str]]
    error: Optional[str] = None
    error_type: Optional[str] = None  # "SyntaxError", "EOFError", "Timeout", etc.

    @property
    def passed(self) -> bool:
        """True if test is considered passing (stdout or file-only match)."""
        return self.match_tier not in (MatchTier.MISMATCH, MatchTier.ERROR)


@dataclass
class StudentResult:
    """Aggregated result for one student across all test cases."""
    name: str
    path: str
    category: StudentCategory
    score: float                        # 0.0–100.0 based on passing tests
    test_results: list[TestResult]
    overall_match_tier: MatchTier
    notes: list[str] = field(default_factory=list)

    @property
    def passed_count(self) -> int:
        return sum(1 for t in self.test_results if t.passed)

    @property
    def total_count(self) -> int:
        return len(self.test_results)

    @property
    def display_score(self) -> str:
        return f"{self.score:.1f}%"
