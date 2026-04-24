from datetime import date

from models import NutritionEntry


def _entry(test_athlete, *, target_date, calories, notes, entry_type="daily"):
    return NutritionEntry(
        athlete_id=test_athlete.id,
        date=target_date,
        entry_type=entry_type,
        calories=calories,
        protein_g=25,
        carbs_g=60,
        fat_g=12,
        notes=notes,
        macro_source="test",
    )


def test_nutrition_log_sums_additive_daily_entries_for_today(db_session, test_athlete):
    from services.coach_tools import get_nutrition_log

    today = date.today()
    db_session.add_all(
        [
            _entry(test_athlete, target_date=today, calories=500, notes="Breakfast"),
            _entry(test_athlete, target_date=today, calories=1200, notes="Lunch"),
            _entry(test_athlete, target_date=today, calories=500, notes="Snack"),
        ]
    )
    db_session.commit()

    result = get_nutrition_log(db_session, test_athlete.id, days=7)

    assert result["ok"] is True
    summary = result["data"]["summary"]
    today_key = today.isoformat()
    assert summary["today"]["date"] == today_key
    assert summary["today"]["logged_calories"] == 2200
    assert summary["today"]["entry_count"] == 3
    assert summary["by_date"][today_key]["calories"] == 2200
    assert summary["coverage"]["interpretation"] == "partial_logs_additive"
    assert "logged so far today" in result["narrative"]
    assert result["evidence"][0]["type"] == "nutrition_log"


def test_nutrition_log_empty_response_includes_coverage(db_session, test_athlete):
    from services.coach_tools import get_nutrition_log

    result = get_nutrition_log(db_session, test_athlete.id, days=7)

    assert result["ok"] is True
    assert result["data"]["entries"] == []
    assert result["data"]["summary"]["coverage"]["entries_returned"] == 0
    assert result["evidence"][0]["value"].startswith("No nutrition entries")
