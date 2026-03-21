"""
Keep `_AI_CONTEXT_/KNOWLEDGE_BASE/workouts/variants/STEM_COVERAGE.md` aligned with
`workout_scaler.py` (ScaledWorkout.workout_type literals) and `generator.py`
(string returns from workout-resolution helpers).

If this test fails after a plan_framework change, update the code *or* STEM_COVERAGE
in the same PR.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
STEM_PATH = REPO_ROOT / "_AI_CONTEXT_" / "KNOWLEDGE_BASE" / "workouts" / "variants" / "STEM_COVERAGE.md"
SCALER_PATH = REPO_ROOT / "apps" / "api" / "services" / "plan_framework" / "workout_scaler.py"
GENERATOR_PATH = REPO_ROOT / "apps" / "api" / "services" / "plan_framework" / "generator.py"

_GENERATOR_WORKOUT_RESOLVERS = frozenset(
    {
        "_get_workout_for_day",
        "_get_long_run_type",
        "_get_quality_workout",
        "_get_secondary_quality",
    }
)


def _str_return_value(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _workout_types_from_generator() -> set[str]:
    text = GENERATOR_PATH.read_text(encoding="utf-8")
    tree = ast.parse(text)
    out: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        if node.name not in _GENERATOR_WORKOUT_RESOLVERS:
            continue
        for sub in ast.walk(node):
            if not isinstance(sub, ast.Return) or sub.value is None:
                continue
            s = _str_return_value(sub.value)
            if s is not None:
                out.add(s)
    return out


def _literal_workout_types_from_scaler() -> set[str]:
    text = SCALER_PATH.read_text(encoding="utf-8")
    found = set(re.findall(r'workout_type\s*=\s*"([a-z_][a-z_0-9]*)"', text))
    # Pass-through branch: workout_type=workout_type (easy / recovery / easy_run)
    found |= {"easy", "easy_run", "recovery"}
    return found


def _parse_stem_coverage_documented() -> tuple[set[str], set[str]]:
    """Returns (main_table_types, footnote_only_types)."""
    text = STEM_PATH.read_text(encoding="utf-8")
    table_types: set[str] = set()
    in_table = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("| `") and "Pilot KB" in stripped:
            in_table = True
            continue
        if not in_table:
            continue
        if stripped.startswith("|----") or stripped.startswith("|---"):
            continue
        m = re.match(r"^\|\s*`([a-z_][a-z_0-9]*)`\s*\|", stripped)
        if m:
            table_types.add(m.group(1))
            continue
        # End of table: blank line or non-table line
        if not stripped.startswith("|"):
            break

    footnote_only: set[str] = set()
    if "Not a separate pilot" in text and "`long_mp_intervals`" in text:
        footnote_only.add("long_mp_intervals")

    return table_types, footnote_only


@pytest.mark.skipif(not STEM_PATH.is_file(), reason="STEM_COVERAGE.md not in workspace")
def test_stem_coverage_matches_plan_framework_emissions():
    from_code = _literal_workout_types_from_scaler() | _workout_types_from_generator()
    table_doc, footnote_doc = _parse_stem_coverage_documented()
    documented = table_doc | footnote_doc

    missing_in_doc = sorted(from_code - documented)
    stale_in_doc = sorted(documented - from_code)

    assert not missing_in_doc, (
        "STEM_COVERAGE.md missing workout_type(s) emitted by scaler/generator: "
        f"{missing_in_doc}. Add a row (or footnote) in {STEM_PATH.relative_to(REPO_ROOT)}."
    )
    assert not stale_in_doc, (
        "STEM_COVERAGE.md lists workout_type(s) not returned by scaler/generator: "
        f"{stale_in_doc}. Remove or fix rows in {STEM_PATH.relative_to(REPO_ROOT)}."
    )
