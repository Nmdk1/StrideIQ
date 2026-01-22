from __future__ import annotations

from dataclasses import dataclass

from services.planned_workout_text import (
    clear_derived_text_on_structural_change,
    normalize_text,
    normalize_workout_text_fields,
)


@dataclass
class _Workout:
    title: str | None = None
    description: str | None = None
    coach_notes: str | None = None


def test_normalize_text_replaces_arrow_mojibake() -> None:
    assert normalize_text("easyâ†’MP") == "easy→MP"
    assert normalize_text(None) is None


def test_normalize_workout_text_fields_normalizes_all_fields() -> None:
    w = _Workout(title="Aâ†’B", description="Câ†’D", coach_notes="Eâ†’F")
    normalize_workout_text_fields(w)
    assert w.title == "A→B"
    assert w.description == "C→D"
    assert w.coach_notes == "E→F"


def test_clear_derived_text_on_structural_change_clears_when_not_provided() -> None:
    w = _Workout(title="T", description="desc", coach_notes="notes")
    changes: list[str] = []
    clear_derived_text_on_structural_change(
        w,
        structural_changed=True,
        description_provided=False,
        coach_notes_provided=False,
        changes=changes,
    )
    assert w.description is None
    assert w.coach_notes is None
    assert any("description cleared" in c for c in changes)
    assert any("notes cleared" in c for c in changes)


def test_clear_derived_text_on_structural_change_does_not_clear_if_provided() -> None:
    w = _Workout(title="T", description="desc", coach_notes="notes")
    changes: list[str] = []
    clear_derived_text_on_structural_change(
        w,
        structural_changed=True,
        description_provided=True,
        coach_notes_provided=True,
        changes=changes,
    )
    assert w.description == "desc"
    assert w.coach_notes == "notes"
    assert changes == []

