"""
Map framework engine output (workout_type + title + segments) to
`workout_variant_id` rows in `workout_registry.json`.

Conservative: only returns ids that exist with `sme_status: approved` in the
registry. If the JSON is missing (e.g. minimal image), returns None.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional


def _resolve_registry_path() -> Path:
    """
    Locate workout_registry.json.

    Primary: apps/api/data/workout_variants/workout_registry.json
    (relative to any ancestor that contains a data/ dir).
    Fallback: legacy _AI_CONTEXT_/... path for backward compat.
    Docker: /app/data/workout_variants/workout_registry.json (COPY in Dockerfile).
    """
    here = Path(__file__).resolve()
    for anc in here.parents:
        primary = anc / "data" / "workout_variants" / "workout_registry.json"
        if primary.is_file():
            return primary
    for anc in here.parents:
        legacy = (
            anc
            / "_AI_CONTEXT_"
            / "KNOWLEDGE_BASE"
            / "workouts"
            / "variants"
            / "workout_registry.json"
        )
        if legacy.is_file():
            return legacy
    return here.parent / ".workout_registry_not_bundled.json"


REGISTRY_PATH = _resolve_registry_path()

_THR_INT_TITLE_RE = re.compile(
    r"Threshold Intervals:\s*(\d+)x(\d+)\s*min", re.IGNORECASE
)
_INTERVAL_TITLE_RE = re.compile(r"Intervals:\s*\d+x(\d+)m", re.IGNORECASE)
_REPS_TITLE_RE = re.compile(r"Reps:\s*(\d+)x(\d+)m", re.IGNORECASE)
_THR_RUN_TITLE_RE = re.compile(r"Threshold Run:\s*(\d+)\s*min", re.IGNORECASE)

_approved_ids_cache: Optional[frozenset[str]] = None


def clear_workout_variant_id_cache() -> None:
    """Test hook: reset lazy-loaded registry id set."""
    global _approved_ids_cache
    _approved_ids_cache = None


def _approved_variant_ids() -> frozenset[str]:
    global _approved_ids_cache
    if _approved_ids_cache is not None:
        return _approved_ids_cache
    if not REGISTRY_PATH.is_file():
        _approved_ids_cache = frozenset()
        return _approved_ids_cache
    data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    ids = frozenset(
        v["id"]
        for v in data.get("variants", [])
        if isinstance(v, dict) and v.get("sme_status") == "approved" and v.get("id")
    )
    _approved_ids_cache = ids
    return _approved_ids_cache


def _interval_rep_m_from_segments(segments: Optional[List[Dict[str, Any]]]) -> Optional[int]:
    if not segments:
        return None
    for seg in segments:
        if not isinstance(seg, dict):
            continue
        if seg.get("type") != "intervals":
            continue
        dm = seg.get("distance_m")
        if dm is not None:
            try:
                return int(dm)
            except (TypeError, ValueError):
                return None
    return None


def _coerce_variant_id(candidate: Optional[str]) -> Optional[str]:
    if not candidate:
        return None
    if candidate in _approved_variant_ids():
        return candidate
    return None


def resolve_workout_variant_id(
    workout_type: str,
    title: str,
    segments: Optional[List[Dict[str, Any]]] = None,
) -> Optional[str]:
    """
    Best-effort id for a single generated workout (option A path).

    Titles and shapes are pinned to `workout_scaler.py` as of Phase 3 wiring.
    """
    wt = (workout_type or "").strip().lower()
    ttl = (title or "").strip()

    if wt == "rest":
        return _coerce_variant_id("rest_day_complete")

    if wt == "recovery":
        return _coerce_variant_id("recovery_run_aerobic")

    if wt in ("easy", "easy_run"):
        if ttl == "Easy Run":
            return _coerce_variant_id("easy_conversational_staple")
        return None

    if wt == "easy_strides":
        return _coerce_variant_id("easy_strides_neuromuscular_touch")

    if wt == "strides":
        return _coerce_variant_id("strides_after_easy_neuromuscular")

    if wt in ("hills", "hill_sprints"):
        return _coerce_variant_id("easy_run_hill_sprints_neuromuscular")

    if wt in ("long", "long_run"):
        if ttl == "Long Run" or ttl.startswith("Long Run:"):
            return _coerce_variant_id("long_easy_aerobic_staple")
        return None

    if wt == "medium_long":
        if ttl.startswith("Medium Long:"):
            return _coerce_variant_id("medium_long_aerobic_staple")
        return None

    if wt in ("long_mp", "marathon_pace_long", "mp_touch"):
        return _coerce_variant_id("long_mp_continuous_marathon")

    if wt == "long_mp_intervals":
        return _coerce_variant_id("long_mp_intervals_in_long")

    if wt in ("long_hmp", "half_marathon_pace_long"):
        if ttl.startswith("Long Run with HMP:"):
            return _coerce_variant_id("long_hmp_finish_half_marathon")
        return None

    if wt in ("threshold", "t_run", "tempo"):
        if _THR_RUN_TITLE_RE.match(ttl):
            return _coerce_variant_id("threshold_continuous_progressive")
        return None

    if wt in ("threshold_intervals", "t_intervals"):
        m = _THR_INT_TITLE_RE.match(ttl)
        if m:
            dur = int(m.group(2))
            if dur <= 6:
                return _coerce_variant_id("threshold_intervals_5_to_6_min")
            return _coerce_variant_id("threshold_intervals_8_to_12_min")
        return None

    if wt in ("interval", "intervals", "vo2max"):
        m = _INTERVAL_TITLE_RE.search(ttl)
        rep_m = int(m.group(1)) if m else _interval_rep_m_from_segments(segments)
        if rep_m == 400:
            return _coerce_variant_id("vo2_400m_short_reps_development")
        if rep_m == 800:
            return _coerce_variant_id("vo2_800m_reps_development")
        if rep_m == 1000:
            return _coerce_variant_id("vo2_1000m_reps_classic")
        if rep_m == 1200:
            return _coerce_variant_id("vo2_1200m_10k_race_rhythm")
        return None

    if wt in ("repetitions", "reps"):
        m = _REPS_TITLE_RE.match(ttl)
        if m:
            rep_m = int(m.group(2))
            if rep_m <= 200:
                return _coerce_variant_id("reps_200m_neuromuscular_early")
            return _coerce_variant_id("reps_300m_economy_late")
        return None

    return None
