from datetime import date, timedelta

from models import NutritionEntry
from services.coaching.runtime_v2_packet import assemble_v2_packet, packet_to_prompt


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


def test_v2_packet_includes_compact_nutrition_context_for_current_food_query(
    db_session,
    test_athlete,
):
    today = date.today()
    db_session.add_all(
        [
            _entry(test_athlete, target_date=today, calories=500, notes="Breakfast"),
            _entry(test_athlete, target_date=today, calories=1200, notes="Lunch"),
        ]
    )
    db_session.commit()

    packet = assemble_v2_packet(
        athlete_id=test_athlete.id,
        db=db_session,
        message="can you see what i have eaten so far today?",
        conversation_context=[],
        legacy_athlete_state="",
    )
    block = packet["blocks"]["nutrition_context"]
    data = block["data"]
    prompt = packet_to_prompt(packet)

    assert block["status"] == "complete"
    assert data["query_type"] == "current_log"
    assert "preserve any training" in data["response_guidance"]
    assert data["coverage"]["start_date"] == today.isoformat()
    assert data["coverage"]["end_date"] == today.isoformat()
    assert data["coverage"]["interpretation"] == "partial_logs_additive_not_complete_day_total"
    assert data["today"]["calories"] == 1700
    assert data["today"]["entry_count"] == 2
    assert [entry["notes"] for entry in data["entries"]] == ["Lunch", "Breakfast"]
    assert "nutrition_context" in prompt
    assert "direct_nutrition_log_only" in prompt
    assert "calendar_context" not in prompt
    assert "activity_evidence_state" not in prompt
    assert "training_adaptation_context" not in prompt
    assert "recent_threads" not in prompt
    assert "Breakfast" in prompt
    assert "Lunch" in prompt
    assert "get_nutrition_log" not in prompt


def test_v2_packet_keeps_training_context_when_nutrition_question_mentions_run(
    db_session,
    test_athlete,
):
    today = date.today()
    db_session.add(
        _entry(
            test_athlete,
            target_date=today,
            calories=500,
            notes="Breakfast and 20 oz water",
        )
    )
    db_session.commit()

    packet = assemble_v2_packet(
        athlete_id=test_athlete.id,
        db=db_session,
        message=(
            "Given today's food log and today's run, am I underfueling or fine "
            "for recovery?"
        ),
        conversation_context=[],
        legacy_athlete_state="",
    )
    prompt = packet_to_prompt(packet)

    assert packet["blocks"]["nutrition_context"]["data"]["query_type"] == "current_log"
    assert "Breakfast and 20 oz water" in prompt
    assert "full_compact" in prompt
    assert "recent_activities" in prompt
    assert "training_adaptation_context" in prompt
    assert "direct_nutrition_log_only" not in prompt


def test_v2_packet_fetches_named_weekday_and_today_for_nutrition_question(
    db_session,
    test_athlete,
):
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    db_session.add_all(
        [
            _entry(test_athlete, target_date=monday, calories=1800, notes="Monday food"),
            _entry(test_athlete, target_date=today, calories=900, notes="Today food"),
        ]
    )
    db_session.commit()

    packet = assemble_v2_packet(
        athlete_id=test_athlete.id,
        db=db_session,
        message=(
            "Monday and today are my typical daily food intake. What do you "
            "think of it to support my lifting and running?"
        ),
        conversation_context=[],
        legacy_athlete_state="",
    )
    data = packet["blocks"]["nutrition_context"]["data"]
    prompt = packet_to_prompt(packet)

    assert data["query_type"] == "date_range_named_days"
    assert data["coverage"]["start_date"] == monday.isoformat()
    assert data["coverage"]["end_date"] == today.isoformat()
    assert "Monday food" in prompt
    assert "Today food" in prompt
    assert "full_compact" in prompt
    assert "recent_activities" in prompt
    assert "direct_nutrition_log_only" not in prompt


def test_v2_named_day_nutrition_summary_uses_all_rows_before_entry_cap(
    db_session,
    test_athlete,
):
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    entries = [
        _entry(test_athlete, target_date=monday, calories=100, notes=f"Monday {i}")
        for i in range(6)
    ]
    entries.extend(
        _entry(test_athlete, target_date=today, calories=200, notes=f"Today {i}")
        for i in range(18)
    )
    db_session.add_all(entries)
    db_session.commit()

    packet = assemble_v2_packet(
        athlete_id=test_athlete.id,
        db=db_session,
        message=(
            "Monday and today are my typical daily food intake. What do you "
            "think of it to support my lifting and running?"
        ),
        conversation_context=[],
        legacy_athlete_state="",
    )
    data = packet["blocks"]["nutrition_context"]["data"]
    returned_notes = {entry["notes"] for entry in data["entries"]}

    assert data["by_date"][monday.isoformat()]["calories"] == 600
    assert data["by_date"][today.isoformat()]["calories"] == 3600
    assert data["coverage"]["requested_named_dates"] == [
        {"label": "Monday", "date": monday.isoformat()},
        {"label": "today", "date": today.isoformat()},
    ]
    assert "name each requested day explicitly" in data["response_guidance"]
    assert any(note.startswith("Monday") for note in returned_notes)
    assert any(note.startswith("Today") for note in returned_notes)
    assert data["coverage"]["entries_found"] == 24
    assert data["coverage"]["entries_returned"] == 12


def test_v2_packet_omits_nutrition_context_when_not_relevant(
    db_session,
    test_athlete,
):
    packet = assemble_v2_packet(
        athlete_id=test_athlete.id,
        db=db_session,
        message="Should I run easy today?",
        conversation_context=[],
        legacy_athlete_state="",
    )
    prompt = packet_to_prompt(packet)

    assert "nutrition_context" not in packet["blocks"]
    assert "nutrition_context" not in prompt


def test_v2_packet_nutrition_context_handles_empty_current_log(
    db_session,
    test_athlete,
):
    packet = assemble_v2_packet(
        athlete_id=test_athlete.id,
        db=db_session,
        message="how many calories have I logged today?",
        conversation_context=[],
        legacy_athlete_state="",
    )
    data = packet["blocks"]["nutrition_context"]["data"]

    assert data["query_type"] == "current_log"
    assert data["coverage"]["entries_found"] == 0
    assert data["today"]["calories"] == 0
    assert data["today"]["entry_count"] == 0
    assert data["entries"] == []
