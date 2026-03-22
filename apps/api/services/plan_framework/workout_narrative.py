"""
Grounded coach-style copy for plan scaler output (P3).

Templates + numeric inputs only — no LLM, no invented history. Callers must pass
``prev_mp_miles`` only when it reflects the last planned ``long_mp`` in this plan.
"""

from __future__ import annotations

from typing import Optional, Tuple


def mp_long_option_a_copy(
    mp_week: int,
    mp_miles: float,
    mp_structure: str,
    total_miles: float,
    prev_mp_miles: Optional[int],
) -> Tuple[str, str]:
    """Title and description for continuous / primary MP long (option A)."""
    cur = int(round(mp_miles))
    tot = int(round(total_miles))
    title = f"Long run with MP (week {mp_week}): {mp_structure}"

    if prev_mp_miles is None:
        narrative = (
            f"First MP long in this plan: {cur} mi at goal marathon pace this session "
            f"({mp_structure}). Learn the effort before longer continuous blocks — not a race."
        )
    else:
        narrative = (
            f"Building from {prev_mp_miles} to {cur} mi at MP — more race-pace volume "
            "so fueling and rhythm stick when you are tired."
        )

    detail = f"{tot} mi total with {mp_structure}."
    description = f"{narrative} {detail}"
    return title, description


def mp_long_option_b_copy(
    mp_week: int,
    reps: int,
    rep_distance: int,
    total_miles: float,
    mp_miles: float,
    prev_mp_miles: Optional[int],
) -> Tuple[str, str]:
    """Title and description for MP long option B (intervals in the long run)."""
    cur = int(round(mp_miles))
    tot = int(round(total_miles))
    title = f"Long run with MP — intervals (week {mp_week}): {reps}×{rep_distance} mi @ MP"

    if prev_mp_miles is None:
        narrative = (
            f"Option B: same {cur} mi at MP as option A, split into {reps}×{rep_distance} mi reps "
            "with easy between — use if continuous MP feels like too much today."
        )
    else:
        narrative = (
            f"Option B: building from {prev_mp_miles} to {cur} mi at MP (as reps), "
            "same progression intent as the continuous version."
        )

    detail = f"{tot} mi total with {reps}×{rep_distance} mi @ MP and 1 mi easy between reps."
    description = f"{narrative} {detail}"
    return title, description
