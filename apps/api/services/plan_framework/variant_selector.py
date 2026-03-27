"""
Variant Selector — bridge between workout_registry.json and the generator.

Reads the SME-approved knowledge base and selects the correct workout variant
for each slot based on:
  - workout stem (threshold, intervals, long, easy, etc.)
  - build_context_tag from the current phase
  - week_in_phase and total_phase_weeks for progression
  - distance and athlete_ctx for N=1 adjustments

This replaces hardcoded variant ID assignment with registry-driven selection.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from .workout_variant_dispatch import _resolve_registry_path


_REGISTRY_CACHE: Optional[List[Dict[str, Any]]] = None


def _load_registry() -> List[Dict[str, Any]]:
    global _REGISTRY_CACHE
    if _REGISTRY_CACHE is not None:
        return _REGISTRY_CACHE

    path = _resolve_registry_path()
    if not path.is_file():
        _REGISTRY_CACHE = []
        return _REGISTRY_CACHE

    data = json.loads(path.read_text(encoding="utf-8"))
    _REGISTRY_CACHE = [
        v for v in data.get("variants", [])
        if isinstance(v, dict) and v.get("sme_status") == "approved"
    ]
    return _REGISTRY_CACHE


def clear_variant_selector_cache() -> None:
    global _REGISTRY_CACHE
    _REGISTRY_CACHE = None


_STEM_MAP: Dict[str, str] = {
    "threshold": "threshold",
    "t_run": "threshold",
    "tempo": "threshold",
    "threshold_intervals": "threshold_intervals",
    "t_intervals": "threshold_intervals",
    "intervals": "intervals",
    "interval": "intervals",
    "vo2max": "intervals",
    "long": "long",
    "long_run": "long",
    "long_mp": "long_mp",
    "marathon_pace_long": "long_mp",
    "long_hmp": "long_hmp",
    "half_marathon_pace_long": "long_hmp",
    "medium_long": "medium_long",
    "easy": "easy",
    "easy_run": "easy",
    "recovery": "recovery",
    "easy_strides": "easy_strides",
    "strides": "strides",
    "hills": "hills",
    "hill_sprints": "hills",
    "rest": "rest",
    "repetitions": "repetitions",
    "reps": "repetitions",
    "mp_touch": "long_mp",
    "medium_long_mp": "long_mp",
}


def _candidates_for_stem(stem: str) -> List[Dict[str, Any]]:
    registry = _load_registry()
    return [v for v in registry if v.get("stem") == stem]


def select_variant(
    workout_type: str,
    build_context_tag: str,
    week_in_phase: int = 1,
    total_phase_weeks: int = 4,
    distance: str = "marathon",
    athlete_ctx: Optional[Dict[str, Any]] = None,
    title: str = "",
    segments: Optional[List[Dict[str, Any]]] = None,
) -> Optional[str]:
    """
    Select the best variant ID from the registry for a given workout slot.

    Returns None if no match (caller preserves existing behavior).
    """
    stem = _STEM_MAP.get(workout_type or "", "")
    if not stem:
        return None

    candidates = _candidates_for_stem(stem)
    if not candidates:
        return None

    tagged = [
        v for v in candidates
        if build_context_tag in (v.get("build_context_tags") or [])
    ]
    pool = tagged if tagged else candidates

    if stem == "threshold":
        return _select_threshold(pool, week_in_phase, total_phase_weeks, title)
    if stem == "threshold_intervals":
        return _select_threshold_intervals(pool, week_in_phase, total_phase_weeks, title)
    if stem == "intervals":
        return _select_intervals(pool, week_in_phase, total_phase_weeks, distance, build_context_tag, title, segments)
    if stem == "long":
        return _select_long(pool, build_context_tag, title)
    if stem == "long_mp":
        return _select_long_mp(pool, build_context_tag, title)
    if stem == "long_hmp":
        return _pick_id(pool, "long_hmp_finish_half_marathon")
    if stem == "medium_long":
        return _pick_id(pool, "medium_long_aerobic_staple")
    if stem == "easy":
        return _pick_id(pool, "easy_conversational_staple")
    if stem == "recovery":
        return _pick_id(pool, "recovery_run_aerobic")
    if stem == "easy_strides":
        return _pick_id(pool, "easy_strides_neuromuscular_touch")
    if stem == "strides":
        return _pick_id(pool, "strides_after_easy_neuromuscular")
    if stem == "hills":
        return _pick_id(pool, "easy_run_hill_sprints_neuromuscular")
    if stem == "rest":
        return _pick_id(pool, "rest_day_complete")
    if stem == "repetitions":
        return _select_repetitions(pool, week_in_phase, total_phase_weeks)

    return pool[0]["id"] if pool else None


def _pick_id(pool: List[Dict[str, Any]], preferred: str) -> Optional[str]:
    for v in pool:
        if v["id"] == preferred:
            return preferred
    return pool[0]["id"] if pool else None


def _select_threshold(
    pool: List[Dict[str, Any]],
    week_in_phase: int,
    total_phase_weeks: int,
    title: str,
) -> Optional[str]:
    import re
    m = re.search(r"(\d+)\s*min", title, re.IGNORECASE)
    duration_min = int(m.group(1)) if m else 0

    if duration_min <= 15:
        return _pick_id(pool, "threshold_continuous_short_block")
    return _pick_id(pool, "threshold_continuous_progressive")


def _select_threshold_intervals(
    pool: List[Dict[str, Any]],
    week_in_phase: int,
    total_phase_weeks: int,
    title: str,
) -> Optional[str]:
    import re
    m = re.search(r"(\d+)x(\d+)\s*min", title, re.IGNORECASE)
    if m:
        dur = int(m.group(2))
        if dur <= 6:
            return _pick_id(pool, "threshold_intervals_5_to_6_min")
        if dur <= 7:
            return _pick_id(pool, "cruise_intervals_classic")
        return _pick_id(pool, "threshold_intervals_8_to_12_min")

    progress = week_in_phase / max(1, total_phase_weeks)
    if progress <= 0.5:
        return _pick_id(pool, "threshold_intervals_5_to_6_min")
    return _pick_id(pool, "cruise_intervals_classic")


def _select_intervals(
    pool: List[Dict[str, Any]],
    week_in_phase: int,
    total_phase_weeks: int,
    distance: str,
    build_context_tag: str,
    title: str,
    segments: Optional[List[Dict[str, Any]]],
) -> Optional[str]:
    import re
    m = re.search(r"(\d+)x(\d+)m", title, re.IGNORECASE)
    rep_m = int(m.group(2)) if m else None

    if rep_m is None and segments:
        for seg in segments:
            if isinstance(seg, dict) and seg.get("type") == "intervals":
                dm = seg.get("distance_m")
                if dm is not None:
                    try:
                        rep_m = int(dm)
                    except (TypeError, ValueError):
                        pass
                    break

    if rep_m == 400:
        return _pick_id(pool, "vo2_400m_short_reps_development")
    if rep_m == 800:
        return _pick_id(pool, "vo2_800m_reps_development")
    if rep_m == 1000:
        if distance == "5k" and build_context_tag in ("race_specific", "peak_fitness"):
            return _pick_id(pool, "vo2_5k_peak_1000_development")
        return _pick_id(pool, "vo2_1000m_reps_classic")
    if rep_m == 1200:
        return _pick_id(pool, "vo2_1200m_10k_race_rhythm")

    if build_context_tag == "minimal_sharpen":
        return _pick_id(pool, "vo2_minimal_sharpen_micro_touch")
    if build_context_tag in ("injury_return", "durability_rebuild"):
        return _pick_id(pool, "vo2_conservative_low_dose")

    progress = week_in_phase / max(1, total_phase_weeks)
    if progress <= 0.33:
        return _pick_id(pool, "vo2_400m_short_reps_development")
    if progress <= 0.66:
        return _pick_id(pool, "vo2_800m_reps_development")
    return _pick_id(pool, "vo2_1000m_reps_classic")


def _select_long(
    pool: List[Dict[str, Any]],
    build_context_tag: str,
    title: str,
) -> Optional[str]:
    return _pick_id(pool, "long_easy_aerobic_staple")


def _select_long_mp(
    pool: List[Dict[str, Any]],
    build_context_tag: str,
    title: str,
) -> Optional[str]:
    if "interval" in title.lower() or "block" in title.lower():
        return _pick_id(pool, "long_mp_intervals_in_long")
    return _pick_id(pool, "long_mp_continuous_marathon")


def _select_repetitions(
    pool: List[Dict[str, Any]],
    week_in_phase: int,
    total_phase_weeks: int,
) -> Optional[str]:
    progress = week_in_phase / max(1, total_phase_weeks)
    if progress <= 0.5:
        return _pick_id(pool, "reps_200m_neuromuscular_early")
    return _pick_id(pool, "reps_300m_economy_late")
