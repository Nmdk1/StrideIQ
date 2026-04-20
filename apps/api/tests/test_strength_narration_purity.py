"""Strength v1 narration purity contract.

The product strategy contract for strength v1 is "Observe → Learn →
Educate → Repeat" — the system *never* prescribes a workout, *never*
recommends a treatment, *never* tells the athlete what they should do.

This test scans every file in the strength v1 surface (router source,
Pydantic schemas, ORM models, service modules) for forbidden
imperative phrases. If a future change adds prescriptive language to
any of these modules, this test fails before it ships.

Scope (intentional):
  - apps/api/routers/strength_v1.py
  - apps/api/routers/symptoms_v1.py
  - apps/api/routers/routines_goals_v1.py
  - apps/api/schemas_strength_v1.py
  - apps/api/schemas_symptom_v1.py
  - apps/api/schemas_routine_goal_v1.py
  - apps/api/models/strength_v1.py
  - apps/api/services/strength_taxonomy.py
  - apps/api/services/strength_parser.py

Out of scope: docstrings of the *test* files themselves (they are
allowed to discuss the contract using the very phrases the contract
forbids), and the scope spec ``docs/specs/STRENGTH_V1_SCOPE.md``
(which exists to *describe* what the system never says).

If you need to use a forbidden phrase legitimately (e.g. a comment
explaining "we never prescribe X"), bracket it with
``# narration-purity: allow`` on the same line. The test honours
that pragma. (We intentionally do not piggyback on ``# noqa:`` —
ruff rejects unknown noqa codes, which would fail an unrelated
lint job.)
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]


# Files in the strength v1 surface. Listed explicitly (not globbed) so
# adding a new strength module is a deliberate decision: include it
# here and accept the contract.
SURFACE_FILES: List[Path] = [
    REPO_ROOT / "routers" / "strength_v1.py",
    REPO_ROOT / "routers" / "symptoms_v1.py",
    REPO_ROOT / "routers" / "routines_goals_v1.py",
    REPO_ROOT / "schemas_strength_v1.py",
    REPO_ROOT / "schemas_symptom_v1.py",
    REPO_ROOT / "schemas_routine_goal_v1.py",
    REPO_ROOT / "models" / "strength_v1.py",
    REPO_ROOT / "services" / "strength_taxonomy.py",
    REPO_ROOT / "services" / "strength_parser.py",
]


# Forbidden imperative phrases. These are user-facing patterns the
# system must never write back to the athlete. They are matched
# case-insensitively, on word boundaries where it makes sense.
#
# We deliberately allow scientific / engine-internal language like
# "estimated 1RM" or "movement pattern" — that is observation, not
# prescription. The list targets the *prescription/recommendation*
# axis only.
FORBIDDEN_PATTERNS: List[str] = [
    # "you should do X reps at Y weight"
    r"you should",
    # "we recommend / I recommend"
    r"\brecommend\b",
    r"\brecommended\b",
    r"\brecommendation\b",
    # "try this routine"
    r"\btry this\b",
    # "increase / decrease" as a directive ("you should increase volume")
    r"you (?:must|need to|have to) ",
    # "the system suggests"
    r"system suggests",
    r"\bsuggested workout\b",
    # treatment language we never use
    r"\bdiagnose(?:s|d|sis)?\b",
    r"\bprognos\w*\b",
    r"\btreatment plan\b",
    r"\brehab plan\b",
    r"\bsee a doctor\b",
    # rest/training prescriptions
    r"\brest day required\b",
    r"\btake (?:a )?day off\b",
    r"\bdo not run\b",
    r"\bskip your\b",
]


PRAGMA_RE = re.compile(r"#\s*narration-purity:\s*allow", re.IGNORECASE)


def _scan_file(path: Path) -> List[str]:
    """Return list of "<rel_path>:<lineno>: <matched>" violations."""
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    violations: List[str] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        if PRAGMA_RE.search(line):
            continue
        # Strip URLs first; "rest" or "recommend" appearing in a
        # link is not a narration violation.
        scrub = re.sub(r"https?://\S+", "", line)
        for pattern in FORBIDDEN_PATTERNS:
            m = re.search(pattern, scrub, re.IGNORECASE)
            if m:
                rel = path.relative_to(REPO_ROOT)
                violations.append(
                    f"{rel}:{lineno}: matched {pattern!r}: {line.strip()!r}"
                )
    return violations


class TestStrengthNarrationPurity:
    def test_surface_files_contain_no_prescriptive_language(self):
        all_violations: List[str] = []
        for path in SURFACE_FILES:
            all_violations.extend(_scan_file(path))
        assert not all_violations, (
            "Strength v1 narration purity violation. The system must "
            "never prescribe. Either reword the line, or add "
            "'# narration-purity: allow' on the offending line if it "
            "is a comment explaining what the system intentionally "
            "does NOT say.\n  - "
            + "\n  - ".join(all_violations)
        )

    def test_surface_file_list_is_not_empty(self):
        """Sanity check: the test would silently pass if SURFACE_FILES
        was wiped, so verify at least one file exists in CI."""
        existing = [p for p in SURFACE_FILES if p.exists()]
        assert len(existing) >= 5, (
            "expected most strength v1 surface files to exist; got "
            f"{[str(p) for p in existing]}"
        )

    @pytest.mark.parametrize(
        "phrase",
        [
            "you should do 3 sets of 5",
            "we recommend a 4-day split",
            "rest day required",
            "see a doctor about your knee",
        ],
    )
    def test_scanner_catches_known_violations(self, tmp_path, phrase):
        """Self-test the scanner. Without this, a typo in
        FORBIDDEN_PATTERNS would silently neuter the contract."""
        bad = tmp_path / "fake.py"
        bad.write_text(f'"""docstring"""\n# {phrase}\n')
        violations: List[str] = []
        text = bad.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            for pattern in FORBIDDEN_PATTERNS:
                if re.search(pattern, line, re.IGNORECASE):
                    violations.append(line)
                    break
        assert violations, f"scanner did not flag known violation: {phrase!r}"
