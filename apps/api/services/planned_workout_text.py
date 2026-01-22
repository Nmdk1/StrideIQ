"""
Utilities for keeping PlannedWorkout text fields coherent during edits.

Owner intent:
- Avoid trust-breaking mismatches like changing workout type/distance while leaving
  stale description/coach notes behind.
- Fix common mojibake sequences (UTF-8 mis-decoding) seen in stored text.
"""

from __future__ import annotations

from typing import Optional, Protocol


class _HasWorkoutTextFields(Protocol):
    title: Optional[str]
    description: Optional[str]
    coach_notes: Optional[str]


def normalize_text(v: Optional[str]) -> Optional[str]:
    """
    Normalize common mojibake sequences seen in stored/generated workout text.

    Example:
      'easyâ†’MP' -> 'easy→MP'
    """
    if v is None:
        return None
    # Keep this list tight and evidence-driven (add only when observed).
    return v.replace("â†’", "→")


def normalize_workout_text_fields(workout: _HasWorkoutTextFields) -> None:
    workout.title = normalize_text(workout.title)
    workout.description = normalize_text(workout.description)
    workout.coach_notes = normalize_text(workout.coach_notes)


def clear_derived_text_on_structural_change(
    workout: _HasWorkoutTextFields,
    *,
    structural_changed: bool,
    description_provided: bool,
    coach_notes_provided: bool,
    changes: list[str],
) -> None:
    """
    If a workout's structure changed (type/subtype/distance/duration) and the caller
    did not explicitly provide new description/notes, clear them to avoid stale text.
    """
    if not structural_changed:
        return

    if not description_provided and workout.description:
        workout.description = None
        changes.append("description cleared (stale after structural edit)")

    if not coach_notes_provided and workout.coach_notes:
        workout.coach_notes = None
        changes.append("notes cleared (stale after structural edit)")

