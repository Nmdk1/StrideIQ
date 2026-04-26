"""
Phase 2 workout fluency: validate `workout_registry.json` against schema rules,
`workout_scaler.scale_workout` stem aliases, pilot markdown section headers, and
closed `build_context_tag` enum (WORKOUT_FLUENCY_REGISTRY_SPEC §6.3).

KB prose remains in *_pilot_v1.md; JSON is the machine index for CI + future loaders.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

def _find_api_root() -> Path:
    """Walk up from this test file to find the apps/api directory."""
    p = Path(__file__).resolve()
    for parent in p.parents:
        if (parent / "data" / "workout_variants").is_dir():
            return parent
    return p.parents[min(3, len(p.parents) - 1)]

API_ROOT = _find_api_root()
VARIANTS_DIR = API_ROOT / "data" / "workout_variants"
REGISTRY_PATH = VARIANTS_DIR / "workout_registry.json"

VOLUME_FAMILIES = frozenset({"E", "M", "T", "I", "R", "long", "composite"})
SME_SHIPPING = frozenset({"approved"})

# WORKOUT_FLUENCY_REGISTRY_SPEC.md §6.3 — do not extend without spec revision + SME.
BUILD_CONTEXT_TAGS_ALLOWED = frozenset(
    {
        "injury_return",
        "durability_rebuild",
        "minimal_sharpen",
        "base_building",
        "race_specific",
        "peak_fitness",
        "full_featured_healthy",
    }
)
_TAG_ALT = "|".join(sorted(BUILD_CONTEXT_TAGS_ALLOWED, key=len, reverse=True))
_TAGS_LINE_RE = re.compile(r"`(" + _TAG_ALT + r")`")
_SAME_AS_TAGS_RE = re.compile(r"Same as\s+\*\*`([a-z][a-z0-9_]*)`\*\*")

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

PILOT_PARSE_ORDER = [
    "threshold_pilot_v1.md",
    "long_run_pilot_v1.md",
    "easy_pilot_v1.md",
    "intervals_pilot_v1.md",
    "repetitions_pilot_v1.md",
]

_VARIANT_HEADER_RE = re.compile(r"(?m)^## `([a-z][a-z0-9_]*)`\s*$")

_REGISTRY_ROW_KEYS = frozenset(
    {"id", "stem", "volume_family", "sme_status", "pilot", "build_context_tags",
     "display_name", "when_to_avoid", "pairs_poorly_with"}
)


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


def _build_context_tags_from_pilots() -> dict[str, list[str]]:
    """Extract tags from pilot markdown; resolves `Same as **`id`**` references within a file."""
    out: dict[str, list[str]] = {}
    for pilot in PILOT_PARSE_ORDER:
        path = VARIANTS_DIR / pilot
        text = path.read_text(encoding="utf-8")
        matches = list(_VARIANT_HEADER_RE.finditer(text))
        raw_lines: dict[str, str] = {}
        for i, m in enumerate(matches):
            vid = m.group(1)
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            body = text[start:end]
            line = None
            for ln in body.splitlines():
                if ln.strip().startswith("- **typical_build_context_tags:**"):
                    line = ln.strip()
                    break
            if not line:
                raise AssertionError(f"no typical_build_context_tags line for {vid} in {pilot}")
            raw_lines[vid] = line

        for vid in raw_lines:
            line = raw_lines[vid]
            tags = frozenset(_TAGS_LINE_RE.findall(line))
            if not tags:
                ref = _SAME_AS_TAGS_RE.search(line)
                if not ref:
                    raise AssertionError(f"no tags for {vid} in {pilot}: {line!r}")
                other = ref.group(1)
                if other not in raw_lines:
                    raise AssertionError(f"{vid} references unknown variant {other} in {pilot}")
                tags = frozenset(_TAGS_LINE_RE.findall(raw_lines[other]))
                if not tags:
                    raise AssertionError(f"indirect empty tags for {vid} via {other}")
            unknown = tags - BUILD_CONTEXT_TAGS_ALLOWED
            assert not unknown, f"unknown build_context_tag(s) {unknown} for {vid} in {pilot}"
            out[vid] = sorted(tags)
    return out


def _eligible_variant_ids(stem: str, primary_tag: str, variants: list[dict]) -> frozenset[str]:
    """Deterministic eligibility: primary tag must appear in the variant's tag list."""
    return frozenset(
        r["id"] for r in variants if r["stem"] == stem and primary_tag in r["build_context_tags"]
    )


@pytest.mark.skipif(not REGISTRY_PATH.is_file(), reason="workout_registry.json not in workspace")
def test_workout_registry_schema_and_stems():
    data = _load_registry()
    variants = data["variants"]
    ids = [v["id"] for v in variants]
    assert len(ids) == len(frozenset(ids)), f"duplicate ids: {sorted(ids)}"

    for row in variants:
        assert set(row.keys()) == _REGISTRY_ROW_KEYS, row
        assert row["volume_family"] in VOLUME_FAMILIES, row
        assert row["sme_status"] in SME_SHIPPING, row
        assert row["pilot"] in PILOT_FILES, row
        stem = row["stem"]
        assert stem in STEM_TO_ENGINE_WORKOUT_TYPES, f"unknown stem {stem!r} for {row['id']}"
        mapped = STEM_TO_ENGINE_WORKOUT_TYPES[stem]
        unknown = mapped - _SCALER_WORKOUT_TYPES
        assert not unknown, f"stem {stem} maps to unknown types {unknown}"

        tags = row["build_context_tags"]
        assert isinstance(tags, list) and tags, f"build_context_tags empty for {row['id']}"
        assert tags == sorted(tags), f"build_context_tags must be sorted for {row['id']}"
        bad = frozenset(tags) - BUILD_CONTEXT_TAGS_ALLOWED
        assert not bad, f"illegal tag(s) {bad} for {row['id']}"


@pytest.mark.skipif(not REGISTRY_PATH.is_file(), reason="workout_registry.json not in workspace")
def test_workout_registry_build_context_tags_match_pilot_markdown():
    data = _load_registry()
    from_md = _build_context_tags_from_pilots()
    for row in data["variants"]:
        assert row["build_context_tags"] == from_md[row["id"]], (
            f"JSON build_context_tags drift from pilot markdown for {row['id']}"
        )


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


@pytest.mark.skipif(not REGISTRY_PATH.is_file(), reason="workout_registry.json not in workspace")
def test_workout_registry_display_fields_complete():
    """Every approved variant must have display_name, when_to_avoid, pairs_poorly_with (schema 0.3)."""
    data = _load_registry()
    for row in data["variants"]:
        vid = row["id"]
        assert isinstance(row.get("display_name"), str) and row["display_name"].strip(), (
            f"display_name missing or empty for {vid}"
        )
        assert isinstance(row.get("when_to_avoid"), str) and row["when_to_avoid"].strip(), (
            f"when_to_avoid missing or empty for {vid}"
        )
        assert isinstance(row.get("pairs_poorly_with"), str) and row["pairs_poorly_with"].strip(), (
            f"pairs_poorly_with missing or empty for {vid}"
        )


@pytest.mark.skipif(not REGISTRY_PATH.is_file(), reason="workout_registry.json not in workspace")
def test_eligibility_snapshot_primary_tag_and_stem():
    """
    Matrix stub: given a resolved primary build_context_tag + stem, eligible variant ids
    are those listing that tag. Snapshots pin behavior for future planner wiring.
    """
    data = _load_registry()
    v = data["variants"]
    assert _eligible_variant_ids("threshold", "injury_return", v) == frozenset(
        {"threshold_continuous_progressive", "threshold_continuous_short_block"}
    )
    assert _eligible_variant_ids("intervals", "injury_return", v) == frozenset(
        {"vo2_400m_short_reps_development", "vo2_conservative_low_dose"}
    )
    assert _eligible_variant_ids("long", "minimal_sharpen", v) == frozenset({"long_easy_aerobic_staple"})
    assert len(_eligible_variant_ids("intervals", "peak_fitness", v)) == 10
