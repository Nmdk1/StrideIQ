"""
Grounded coach-style copy for plan scaler output (P3).

Templates + numeric inputs only — no LLM, no invented history. Callers must pass
``prev_mp_miles`` only when it reflects the last planned ``long_mp`` in this plan.
Threshold ``prev_*`` reflects the last planned workout of the same stem in this plan.
"""

from __future__ import annotations

from typing import Optional, Tuple


def threshold_continuous_description(
    n_minutes: int,
    prev_minutes: Optional[int],
) -> str:
    """Coach lead + factual tail; title stays ``Threshold Run: {N} min`` (variant regex)."""
    factual = f"Continuous {n_minutes} min at threshold pace."
    if prev_minutes is None:
        narrative = (
            f"First threshold block in this plan: {n_minutes} minutes at a sustainably hard effort, "
            "not race pace. Learn what threshold feels like while you can still speak in short phrases."
        )
    elif prev_minutes == n_minutes:
        narrative = (
            f"Same continuous duration as last time: {n_minutes} minutes at threshold. "
            "Lock in rhythm and breathing before adding time."
        )
    else:
        narrative = (
            f"Building from {prev_minutes} to {n_minutes} minutes at the same effort, more accumulated time "
            "at threshold without changing the feel."
        )
    return f"{narrative} {factual}"


def threshold_intervals_description(
    reps: int,
    duration: int,
    prev: Optional[Tuple[int, int]],
) -> str:
    """Coach lead + factual tail; title prefix unchanged for variant regex."""
    factual = f"{reps}x{duration} min at threshold pace with 2 min jog recovery."
    if prev is None:
        narrative = (
            f"First threshold intervals in this plan: {reps}x{duration} min with jog recovery between. "
            "Aim for even pacing on each rep; controlled beats heroic."
        )
        return f"{narrative} {factual}"

    pr, pd = prev
    if reps == pr and duration == pd:
        narrative = (
            f"Same prescription as last time: {reps}x{duration} min at threshold. "
            "Smooth out pacing or start the first rep a touch easier."
        )
        return f"{narrative} {factual}"
    if reps != pr and duration != pd:
        narrative = (
            f"Progressing from {pr}x{pd} min to {reps}x{duration} min at threshold, "
            "more stimulus at the same quality bar."
        )
    elif reps != pr:
        narrative = (
            f"Progressing from {pr}x{pd} min to {reps}x{pd} min at threshold, "
            "more reps at the same duration."
        )
    else:
        narrative = (
            f"Progressing from {pr}x{pd} min to {pr}x{duration} min at threshold, "
            "longer reps at the same count."
        )
    return f"{narrative} {factual}"


def mp_touch_copy(mp_miles: float, total_miles: float) -> Tuple[str, str]:
    """Cutback consolidation MP touch — not a dress rehearsal (P3.2)."""
    mp_i = int(round(mp_miles))
    tot = int(round(total_miles))
    title = f"Medium long with MP touch: {mp_i} mi @ MP"
    narrative = (
        "Cutback consolidation: a short block at goal marathon pace so race rhythm does not go cold "
        "without loading a full MP long this week."
    )
    detail = f"{tot} mi total — easy bookends around {mp_i} mi at MP."
    return title, f"{narrative} {detail}"


def hmp_long_copy(
    total_miles: float,
    easy_warmup: float,
    hmp_miles: float,
    week_in_phase: int,
) -> Tuple[str, str]:
    """
    Title MUST start with ``Long Run with HMP:`` for ``workout_variant_dispatch`` (P3.2).
    """
    tot = int(round(total_miles))
    ew = int(round(easy_warmup))
    hm = int(round(hmp_miles))
    title = f"Long Run with HMP: last {hm} mi @ HMP"
    if week_in_phase <= 1:
        lead = (
            f"First HMP segment in this plan: {ew} mi easy, then {hm} mi at half marathon pace — "
            "faster than threshold, still controlled."
        )
    elif week_in_phase == 2:
        lead = (
            f"Progressing the HMP finish: {ew} mi easy, then {hm} mi at HMP to rehearse race rhythm on tired legs."
        )
    else:
        lead = (
            f"Race-specific long: {ew} mi easy, then {hm} mi at HMP — practice the second half of your long run."
        )
    detail = f"{tot} mi total."
    return title, f"{lead} {detail}"


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
