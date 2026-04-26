"""
Phase 3 — meal template service.

Covers:
- compute_signature determinism + normalization
- upsert_template skips single-item entries (implicit-learner fix)
- save_named_template promotes an existing implicit row
- list_named_templates returns only is_user_named=True
- log_template_for_athlete builds a NutritionEntry with totals
- mark_name_prompt_shown is idempotent
"""

from __future__ import annotations

from datetime import date as date_type
from uuid import uuid4

import pytest

from core.database import SessionLocal
from models import Athlete, MealTemplate, NutritionEntry
from services.meal_template_service import (
    NAME_PROMPT_THRESHOLD,
    TemplateItem,
    compute_signature,
    delete_template,
    find_template,
    list_named_templates,
    log_template_for_athlete,
    mark_name_prompt_shown,
    save_named_template,
    update_template,
    upsert_template,
)


@pytest.fixture
def athlete():
    db = SessionLocal()
    try:
        a = Athlete(
            email=f"meal_tpl_{uuid4().hex[:8]}@example.com",
            display_name="Meal Template Tester",
            subscription_tier="free",
        )
        db.add(a)
        db.commit()
        db.refresh(a)
        yield a

        # Clean up
        db.query(NutritionEntry).filter(
            NutritionEntry.athlete_id == a.id
        ).delete()
        db.query(MealTemplate).filter(
            MealTemplate.athlete_id == a.id
        ).delete()
        db.delete(a)
        db.commit()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Pure
# ---------------------------------------------------------------------------


class TestComputeSignature:
    def test_sorted_normalized(self):
        assert compute_signature(["Eggs", "Toast"]) == compute_signature(
            ["TOAST", "  eggs  "]
        )

    def test_handles_spaces_and_dedup(self):
        assert compute_signature(["Greek Yogurt", "berries", "Greek Yogurt"]) == (
            "berries+greek_yogurt"
        )

    def test_empty_returns_empty(self):
        assert compute_signature([]) == ""
        assert compute_signature([""]) == ""


# ---------------------------------------------------------------------------
# Implicit-learner write
# ---------------------------------------------------------------------------


class TestUpsertTemplate:
    def test_skips_single_item_entries(self, athlete):
        db = SessionLocal()
        try:
            row = upsert_template(athlete.id, ["protein bar"], [{"food": "protein bar"}], db)
            assert row is None, "single-item entries must not pollute templates"

            count = db.query(MealTemplate).filter(
                MealTemplate.athlete_id == athlete.id
            ).count()
            assert count == 0
        finally:
            db.close()

    def test_creates_then_increments(self, athlete):
        db = SessionLocal()
        try:
            foods = ["eggs", "toast", "coffee"]
            items = [{"food": f} for f in foods]

            r1 = upsert_template(athlete.id, foods, items, db)
            assert r1 is not None
            assert r1.times_confirmed == 1
            assert r1.is_user_named is False

            r2 = upsert_template(athlete.id, foods, items, db)
            assert r2 is not None
            assert r2.id == r1.id
            assert r2.times_confirmed == 2
        finally:
            db.close()


class TestFindTemplate:
    def test_returns_only_after_threshold(self, athlete):
        db = SessionLocal()
        try:
            foods = ["oats", "milk", "honey"]
            items = [{"food": f} for f in foods]

            for _ in range(NAME_PROMPT_THRESHOLD - 1):
                upsert_template(athlete.id, foods, items, db)
            assert find_template(athlete.id, foods, db) is None

            upsert_template(athlete.id, foods, items, db)
            match = find_template(athlete.id, foods, db)
            assert match is not None
            assert match["times_confirmed"] >= NAME_PROMPT_THRESHOLD
            assert match["should_prompt_name"] is True
        finally:
            db.close()

    def test_should_prompt_false_after_user_names(self, athlete):
        db = SessionLocal()
        try:
            foods = ["oats", "milk", "honey"]
            items = [TemplateItem(food=f) for f in foods]
            row = save_named_template(athlete.id, "Workday Breakfast", items, db)
            row.times_confirmed = NAME_PROMPT_THRESHOLD
            db.commit()

            match = find_template(athlete.id, foods, db)
            assert match is not None
            assert match["is_user_named"] is True
            assert match["should_prompt_name"] is False
        finally:
            db.close()


# ---------------------------------------------------------------------------
# Explicit save
# ---------------------------------------------------------------------------


class TestSaveNamedTemplate:
    def test_create_new(self, athlete):
        db = SessionLocal()
        try:
            row = save_named_template(
                athlete.id,
                "Workday Breakfast",
                [
                    TemplateItem(food="Eggs", calories=140, protein_g=12),
                    TemplateItem(food="Toast", calories=120, carbs_g=22),
                ],
                db,
            )
            assert row.is_user_named is True
            assert row.name == "Workday Breakfast"
            assert len(row.items) == 2
        finally:
            db.close()

    def test_promotes_existing_implicit_row(self, athlete):
        db = SessionLocal()
        try:
            foods = ["eggs", "toast"]
            for _ in range(2):
                upsert_template(athlete.id, foods, [{"food": f} for f in foods], db)

            existing = db.query(MealTemplate).filter(
                MealTemplate.athlete_id == athlete.id
            ).one()
            assert existing.is_user_named is False

            row = save_named_template(
                athlete.id,
                "Quick Breakfast",
                [TemplateItem(food=f) for f in foods],
                db,
            )
            assert row.id == existing.id
            assert row.is_user_named is True
            assert row.name == "Quick Breakfast"
            assert row.times_confirmed >= 2
        finally:
            db.close()

    def test_blank_name_rejected(self, athlete):
        db = SessionLocal()
        try:
            with pytest.raises(ValueError):
                save_named_template(
                    athlete.id, "   ", [TemplateItem(food="eggs")], db
                )
        finally:
            db.close()

    def test_empty_items_rejected(self, athlete):
        db = SessionLocal()
        try:
            with pytest.raises(ValueError):
                save_named_template(athlete.id, "Empty", [], db)
        finally:
            db.close()


class TestListNamedTemplates:
    def test_returns_only_named(self, athlete):
        db = SessionLocal()
        try:
            upsert_template(
                athlete.id,
                ["a", "b"],
                [{"food": "a"}, {"food": "b"}],
                db,
            )
            save_named_template(
                athlete.id,
                "Named One",
                [TemplateItem(food="x"), TemplateItem(food="y")],
                db,
            )
            named = list_named_templates(athlete.id, db)
            assert len(named) == 1
            assert named[0].name == "Named One"
        finally:
            db.close()


# ---------------------------------------------------------------------------
# Update / delete
# ---------------------------------------------------------------------------


class TestUpdateAndDelete:
    def test_rename(self, athlete):
        db = SessionLocal()
        try:
            row = save_named_template(
                athlete.id, "Old", [TemplateItem(food="a"), TemplateItem(food="b")], db
            )
            updated = update_template(row.id, athlete.id, db, name="New")
            assert updated is not None
            assert updated.name == "New"
        finally:
            db.close()

    def test_replace_items(self, athlete):
        db = SessionLocal()
        try:
            row = save_named_template(
                athlete.id, "M", [TemplateItem(food="a"), TemplateItem(food="b")], db
            )
            updated = update_template(
                row.id,
                athlete.id,
                db,
                items=[
                    TemplateItem(food="c", calories=100),
                    TemplateItem(food="d", calories=50),
                ],
            )
            assert updated is not None
            foods = sorted(it["food"] for it in updated.items)
            assert foods == ["c", "d"]
        finally:
            db.close()

    def test_delete(self, athlete):
        db = SessionLocal()
        try:
            row = save_named_template(
                athlete.id, "Bye", [TemplateItem(food="a"), TemplateItem(food="b")], db
            )
            assert delete_template(row.id, athlete.id, db) is True
            assert delete_template(row.id, athlete.id, db) is False
        finally:
            db.close()


# ---------------------------------------------------------------------------
# Logging a template
# ---------------------------------------------------------------------------


class TestLogTemplate:
    def test_creates_entry_with_summed_macros(self, athlete):
        db = SessionLocal()
        try:
            row = save_named_template(
                athlete.id,
                "Lunch",
                [
                    TemplateItem(food="rice", calories=200, carbs_g=44),
                    TemplateItem(food="chicken", calories=180, protein_g=33),
                ],
                db,
            )
            entry = log_template_for_athlete(
                row.id,
                athlete.id,
                date_type.today(),
                "daily",
                db,
            )
            assert entry is not None
            assert float(entry.calories) == 380
            assert float(entry.protein_g) == 33
            assert float(entry.carbs_g) == 44
            assert entry.macro_source == "meal_template"
            assert entry.notes == "Lunch"
        finally:
            db.close()

    def test_returns_none_for_unknown_template(self, athlete):
        db = SessionLocal()
        try:
            entry = log_template_for_athlete(
                999_999_999, athlete.id, date_type.today(), "daily", db
            )
            assert entry is None
        finally:
            db.close()


class TestMarkNamePromptShown:
    def test_idempotent(self, athlete):
        db = SessionLocal()
        try:
            row = save_named_template(
                athlete.id, "P", [TemplateItem(food="a"), TemplateItem(food="b")], db
            )
            mark_name_prompt_shown(row.id, athlete.id, db)
            db.refresh(row)
            first = row.name_prompted_at
            assert first is not None

            mark_name_prompt_shown(row.id, athlete.id, db)
            db.refresh(row)
            assert row.name_prompted_at == first
        finally:
            db.close()
