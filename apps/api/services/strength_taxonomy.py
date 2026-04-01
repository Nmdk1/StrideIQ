"""
Strength exercise taxonomy, 1RM estimation, and session classification.

This module provides:
  - MOVEMENT_PATTERN_MAP: Garmin exercise name → (movement_pattern, muscle_group)
  - UNILATERAL_EXERCISES: set of exercises performed one side at a time
  - estimate_1rm(): Epley formula for 1-10 rep range
  - classify_session_type(): session intensity classification from parsed sets

The taxonomy evolves without migrations — add new Garmin exercise names here
as they appear in production logs. Unknown exercises fall back to
DEFAULT_MOVEMENT_PATTERN = ("compound_other", None).
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Movement Pattern Taxonomy
# ---------------------------------------------------------------------------

MOVEMENT_PATTERN_MAP: Dict[str, Tuple[str, Optional[str]]] = {
    # --- Hip-dominant compound (posterior chain) ---
    "DEADLIFT": ("hip_hinge", "posterior_chain"),
    "BARBELL_DEADLIFT": ("hip_hinge", "posterior_chain"),
    "DUMBBELL_DEADLIFT": ("hip_hinge", "posterior_chain"),
    "TRAP_BAR_DEADLIFT": ("hip_hinge", "posterior_chain"),
    "ROMANIAN_DEADLIFT": ("hip_hinge", "posterior_chain"),
    "SUMO_DEADLIFT": ("hip_hinge", "posterior_chain"),
    "STIFF_LEG_DEADLIFT": ("hip_hinge", "posterior_chain"),
    "SINGLE_LEG_DEADLIFT": ("hip_hinge", "posterior_chain"),
    "HIP_THRUST": ("hip_hinge", "glutes"),
    "GLUTE_BRIDGE": ("hip_hinge", "glutes"),
    "KETTLEBELL_SWING": ("hip_hinge", "posterior_chain"),
    "GOOD_MORNING": ("hip_hinge", "posterior_chain"),

    # --- Squat pattern (quad-dominant compound) ---
    "SQUAT": ("squat", "quadriceps"),
    "BARBELL_SQUAT": ("squat", "quadriceps"),
    "BACK_SQUAT": ("squat", "quadriceps"),
    "FRONT_SQUAT": ("squat", "quadriceps"),
    "GOBLET_SQUAT": ("squat", "quadriceps"),
    "OVERHEAD_SQUAT": ("squat", "quadriceps"),
    "SPLIT_SQUAT": ("squat", "quadriceps"),
    "BULGARIAN_SPLIT_SQUAT": ("squat", "quadriceps"),

    # --- Lunge pattern (unilateral lower body) ---
    "LUNGE": ("lunge", "quadriceps"),
    "WALKING_LUNGE": ("lunge", "quadriceps"),
    "REVERSE_LUNGE": ("lunge", "quadriceps"),
    "LATERAL_LUNGE": ("lunge", "hip_abductors"),
    "STEP_UP": ("lunge", "quadriceps"),

    # --- Push (upper body) ---
    "BENCH_PRESS": ("push", "chest"),
    "INCLINE_BENCH_PRESS": ("push", "chest"),
    "PUSH_UP": ("push", "chest"),
    "OVERHEAD_PRESS": ("push", "shoulders"),
    "MILITARY_PRESS": ("push", "shoulders"),
    "DUMBBELL_PRESS": ("push", "chest"),
    "DIPS": ("push", "triceps"),

    # --- Pull (upper body) ---
    "PULL_UP": ("pull", "lats"),
    "CHIN_UP": ("pull", "biceps"),
    "LAT_PULLDOWN": ("pull", "lats"),
    "BARBELL_ROW": ("pull", "upper_back"),
    "DUMBBELL_ROW": ("pull", "upper_back"),
    "SEATED_ROW": ("pull", "upper_back"),
    "FACE_PULL": ("pull", "rear_delts"),

    # --- Core ---
    "PLANK": ("core", "core_anterior"),
    "SIDE_PLANK": ("core", "core_lateral"),
    "CRUNCH": ("core", "core_anterior"),
    "SIT_UP": ("core", "core_anterior"),
    "RUSSIAN_TWIST": ("core", "core_rotational"),
    "DEAD_BUG": ("core", "core_anterior"),
    "BIRD_DOG": ("core", "core_posterior"),
    "PALLOF_PRESS": ("core", "core_rotational"),
    "AB_WHEEL": ("core", "core_anterior"),
    "HANGING_LEG_RAISE": ("core", "core_anterior"),

    # --- Plyometric (explosive / reactive) ---
    "BOX_JUMP": ("plyometric", "lower_body_explosive"),
    "JUMP_SQUAT": ("plyometric", "lower_body_explosive"),
    "DEPTH_JUMP": ("plyometric", "lower_body_explosive"),
    "BOUNDING": ("plyometric", "lower_body_explosive"),
    "SINGLE_LEG_HOP": ("plyometric", "lower_body_explosive"),

    # --- Carry (loaded locomotion) ---
    "FARMERS_WALK": ("carry", "full_body"),
    "SUITCASE_CARRY": ("carry", "core_lateral"),
    "OVERHEAD_CARRY": ("carry", "shoulders"),

    # --- Calf / lower leg ---
    "CALF_RAISE": ("calf", "calves"),
    "SEATED_CALF_RAISE": ("calf", "calves"),

    # --- Isolation (machine / single-joint) ---
    "LEG_PRESS": ("isolation", "quadriceps"),
    "LEG_EXTENSION": ("isolation", "quadriceps"),
    "LEG_CURL": ("isolation", "hamstrings"),
    "BICEP_CURL": ("isolation", "biceps"),
    "TRICEP_EXTENSION": ("isolation", "triceps"),
    "LATERAL_RAISE": ("isolation", "shoulders"),
}

UNILATERAL_EXERCISES = frozenset({
    "SPLIT_SQUAT",
    "BULGARIAN_SPLIT_SQUAT",
    "LUNGE",
    "WALKING_LUNGE",
    "REVERSE_LUNGE",
    "LATERAL_LUNGE",
    "STEP_UP",
    "SINGLE_LEG_HOP",
    "SUITCASE_CARRY",
    "DUMBBELL_ROW",
    "SINGLE_LEG_DEADLIFT",
})

DEFAULT_MOVEMENT_PATTERN: Tuple[str, None] = ("compound_other", None)


def lookup_movement_pattern(exercise_name: str) -> Tuple[str, Optional[str]]:
    """Return (movement_pattern, muscle_group) for a Garmin exercise name."""
    return MOVEMENT_PATTERN_MAP.get(exercise_name, DEFAULT_MOVEMENT_PATTERN)


def is_unilateral(exercise_name: str) -> bool:
    """Return True if the exercise is performed one limb at a time."""
    return exercise_name in UNILATERAL_EXERCISES


# ---------------------------------------------------------------------------
# Estimated 1RM — Epley Formula
# ---------------------------------------------------------------------------

def estimate_1rm(weight_kg: Optional[float], reps: Optional[int]) -> Optional[float]:
    """Epley formula — reasonable for 1-10 rep range.

    Returns estimated one-rep max in kg, or None if inputs are invalid
    or outside the reliable range (>10 reps).
    """
    if weight_kg is None or weight_kg <= 0:
        return None
    if reps is None or reps < 1:
        return None
    if reps == 1:
        return round(weight_kg, 1)
    if reps > 10:
        return None
    return round(weight_kg * (1 + reps / 30), 1)


# ---------------------------------------------------------------------------
# Session Intensity Classification
# ---------------------------------------------------------------------------

_LOWER_BODY_PATTERNS = frozenset({"hip_hinge", "squat", "lunge", "calf", "plyometric"})


def classify_session_type(
    sets: List[dict],
    peak_1rm_by_category: Optional[Dict[str, float]] = None,
) -> str:
    """Classify a strength session based on its exercise sets.

    Args:
        sets: List of dicts with keys: reps, weight_kg, estimated_1rm_kg,
              movement_pattern, exercise_category, set_type.
        peak_1rm_by_category: Map of exercise_category → athlete's historical
              peak estimated 1RM for that exercise. Used to compute relative
              intensity. None or empty when no history exists.

    Returns:
        One of: "maximal", "strength_endurance", "hypertrophy", "endurance",
        "power", "mixed".
    """
    active_sets = [s for s in sets if s.get("set_type", "active") == "active"]
    if not active_sets:
        return "mixed"

    peak_1rm = peak_1rm_by_category or {}

    reps_list = [s["reps"] for s in active_sets if s.get("reps") is not None and s["reps"] > 0]
    if not reps_list:
        return "mixed"

    avg_reps = sum(reps_list) / len(reps_list)

    # Compute average relative intensity (pct of 1RM) when possible
    pct_1rm_values = []
    for s in active_sets:
        cat = s.get("exercise_category", "")
        w = s.get("weight_kg")
        if w and w > 0 and cat in peak_1rm and peak_1rm[cat] > 0:
            pct_1rm_values.append(w / peak_1rm[cat])

    avg_pct_1rm = (sum(pct_1rm_values) / len(pct_1rm_values)) if pct_1rm_values else None

    plyometric_sets = sum(
        1 for s in active_sets if s.get("movement_pattern") == "plyometric"
    )
    heavy_sets = sum(1 for p in pct_1rm_values if p >= 0.85)

    # Power: plyometric work combined with heavy lifting
    if plyometric_sets > 0 and (heavy_sets > 0 or (avg_pct_1rm is not None and avg_pct_1rm >= 0.85)):
        return "power"

    if avg_pct_1rm is not None:
        if avg_reps <= 5 and avg_pct_1rm >= 0.85:
            return "maximal"
        if 6 <= avg_reps <= 10 and avg_pct_1rm >= 0.75:
            return "strength_endurance"
        if 6 <= avg_reps <= 12 and avg_pct_1rm < 0.75:
            return "hypertrophy"

    if avg_reps >= 13:
        return "endurance"

    # Fallback when no 1RM history: rep-count only
    if avg_pct_1rm is None:
        if avg_reps <= 5:
            return "maximal"
        if avg_reps >= 13:
            return "endurance"

    return "mixed"
