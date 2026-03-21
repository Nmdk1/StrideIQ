"""
Phase 2 workout fluency: validate `workout_registry.json` against schema rules,
`workout_scaler.scale_workout` stem aliases, and pilot markdown section headers.

KB prose remains in *_pilot_v1.md; the JSON is the machine index for CI + future loaders.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
VARIANTS_DIR = REPO_ROOT / "_AI_CONTEXT_" / "KNOWLEDGE_BASE" / "workouts" / "variants"
REGISTRY_PATH = VARIANTS_DIR / "workout_registry.json"

VOLUME_FAMILIES = frozenset({"E", "M", "T", "I", "R", "long", "composite"})
SME_SHIPPING = frozenset({"approved"})

# workout_type strings accepted somewhere in `WorkoutScaler.scale_workout` dispatch
# (legacy aliases included so registry stems stay aligned with code).
_SCALER_WORKOUT_TYPES = frozenset(
    {
        "easy",
        "easy_run",
        "recovery",
        "easy_strides",
        "rest",
        "long",
        "long_run",
        "threshold_intervals",
        "t_intervals",
        "threshold",
        "t_run",
        "tempo",
        "long_mp",
        "marathon_pace_long",
        "long_mp_intervals",
        "long_hmp",
        "half_marathon_pace_long",
        "medium_long",
        "medium_long_mp",
        "interval",
        "intervals",
        "vo2max",
        "repetitions",
        "reps",
        "strides",
        "hills",
        "hill_sprints",
    }
)

# Stem (KB / registry) -> engine workout_type strings this variant family may use.
STEM_TO_ENGINE_WORKOUT_TYPES: dict[str, frozenset[str]] = {
    "threshold": frozenset({"threshold", "t_run", "tempo"}),
    "threshold_intervals": frozenset({"threshold_intervals", "t_intervals"}),
    "long": frozenset({"long", "long_run"}),
    "medium_long": frozenset({"medium_long", "medium_long_mp"}),
    "long_mp": frozenset({"long_mp", "marathon_pace_long", "long_mp_intervals"}),
    "long_hmp": frozenset({"long_hmp", "half_marathon_pace_long"}),
    "easy": frozenset({"easy", "easy_run"}),
    "recovery": frozenset({"recovery"}),
    "easy_strides": frozenset({"easy_strides"}),
    "hills": frozenset({"hills", "hill_sprints"}),
    "strides": frozenset({"strides"}),
    "rest": frozenset({"rest"}),
    "intervals": frozenset({"interval", "intervals", "vo2max"}),
    "repetitions": frozenset({"repetitions", "reps"}),
}

PILOT_FILES = frozenset(
    {
        "threshold_pilot_v1.md",
        "long_run_pilot_v1.md",
        "easy_pilot_v1.md",
        "intervals_pilot_v1.md",
        "repetitions_pilot_v1.md",
    }
)

_VARIANT_HEADER_RE = re.compile(r"(?m)^## `([a-z][a-z0-9_]*)`\s*$")


def _load_registry() -> dict:
    data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    assert data.get("schema_version"), "registry missing schema_version"
    variants = data.get("variants")
    assert isinstance(variants, list) and variants, "registry variants must be non-empty list"
    return data


def _variant_ids_in_markdown(pilot_name: str) -> list[str]:
    path = VARIANTS_DIR / pilot_name
    text = path.read_text(encoding="utf-8")
    return _VARIANT_HEADER_RE.findall(text)


@pytest.mark.skipif(not REGISTRY_PATH.is_file(), reason="workout_registry.json not in workspace")
def test_workout_registry_schema_and_stems():
    data = _load_registry()
    variants = data["variants"]
    ids = [v["id"] for v in variants]
    assert len(ids) == len(frozenset(ids)), f"duplicate ids: {sorted(ids)}"

    for row in variants:
        assert set(row.keys()) == {"id", "stem", "volume_family", "sme_status", "pilot"}, row
        assert row["volume_family"] in VOLUME_FAMILIES, row
        assert row["sme_status"] in SME_SHIPPING, row
        assert row["pilot"] in PILOT_FILES, row
        stem = row["stem"]
        assert stem in STEM_TO_ENGINE_WORKOUT_TYPES, f"unknown stem {stem!r} for {row['id']}"
        mapped = STEM_TO_ENGINE_WORKOUT_TYPES[stem]
        unknown = mapped - _SCALER_WORKOUT_TYPES
        assert not unknown, f"stem {stem} maps to unknown types {unknown}"


@pytest.mark.skipif(not REGISTRY_PATH.is_file(), reason="workout_registry.json not in workspace")
def test_workout_registry_matches_pilot_markdown_headers():
    data = _load_registry()
    by_pilot: dict[str, list[str]] = {}
    for row in data["variants"]:
        by_pilot.setdefault(row["pilot"], []).append(row["id"])

    for pilot, reg_ids in by_pilot.items():
        md_ids = _variant_ids_in_markdown(pilot)
        assert sorted(reg_ids) == sorted(md_ids), (
            f"pilot {pilot}: registry ids != markdown ## headers. "
            f"only_in_registry={sorted(frozenset(reg_ids) - frozenset(md_ids))} "
            f"only_in_md={sorted(frozenset(md_ids) - frozenset(reg_ids))}"
        )


@pytest.mark.skipif(not REGISTRY_PATH.is_file(), reason="workout_registry.json not in workspace")
def test_workout_registry_expected_v1_counts():
    """Locks v1 Phase 1 closure counts (38 rows across five pilots)."""
    data = _load_registry()
    by_pilot = {}
    for row in data["variants"]:
        by_pilot[row["pilot"]] = by_pilot.get(row["pilot"], 0) + 1
    assert by_pilot == {
        "threshold_pilot_v1.md": 9,
        "long_run_pilot_v1.md": 9,
        "easy_pilot_v1.md": 6,
        "intervals_pilot_v1.md": 12,
        "repetitions_pilot_v1.md": 2,
    }
    assert len(data["variants"]) == 38


@pytest.mark.skipif(not REGISTRY_PATH.is_file(), reason="workout_registry.json not in workspace")
def test_workout_registry_stem_counts_sanity():
    data = _load_registry()
    stems = [r["stem"] for r in data["variants"]]
    assert stems.count("threshold") == 4
    assert stems.count("threshold_intervals") == 5
    assert stems.count("long") == 4
    assert stems.count("long_mp") == 3
    assert stems.count("intervals") == 12
