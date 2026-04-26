from datetime import datetime, timedelta, timezone

from models import Activity, ActivitySplit
from services.coaching._conversation_contract import (
    ConversationContractType,
    classify_conversation_contract,
)


def _run(
    db_session,
    athlete_id,
    *,
    name: str,
    days_ago: int,
    distance_m: int,
    duration_s: int,
    workout_type: str | None = None,
    shape_sentence: str | None = None,
) -> Activity:
    activity = Activity(
        athlete_id=athlete_id,
        name=name,
        sport="run",
        source="manual",
        start_time=datetime.now(timezone.utc) - timedelta(days=days_ago),
        distance_m=distance_m,
        duration_s=duration_s,
        workout_type=workout_type,
        shape_sentence=shape_sentence,
    )
    db_session.add(activity)
    db_session.flush()
    return activity


def _add_16x400_splits(db_session, activity: Activity) -> None:
    split_number = 1
    for rep in range(1, 17):
        db_session.add(
            ActivitySplit(
                activity_id=activity.id,
                split_number=split_number,
                distance=400,
                elapsed_time=86,
                moving_time=86,
                average_heartrate=168,
                lap_type="work",
                interval_number=rep,
            )
        )
        split_number += 1
        db_session.add(
            ActivitySplit(
                activity_id=activity.id,
                split_number=split_number,
                distance=35,
                elapsed_time=90,
                moving_time=30,
                average_heartrate=148,
                lap_type="rest",
            )
        )
        split_number += 1


def test_split_aware_search_returns_generic_title_interval_workout(db_session, test_athlete):
    from services.coach_tools import search_activities

    workout = _run(
        db_session,
        test_athlete.id,
        name="Morning Run",
        days_ago=28,
        distance_m=11200,
        duration_s=4300,
    )
    _add_16x400_splits(db_session, workout)
    db_session.commit()

    result = search_activities(
        db_session,
        test_athlete.id,
        name_contains="16x400",
        sport="run",
        limit=10,
    )

    assert result["ok"] is True
    assert result["data"]["search_criteria"]["split_aware_fallback_ran"] is True
    assert result["data"]["match_count"] == 1
    match = result["data"]["activities"][0]
    assert match["activity_id"] == str(workout.id)
    assert match["name"] == "Morning Run"
    assert match["split_summary"]["total_reps"] == 16
    assert match["split_summary"]["rep_distance_m"] == 400


def test_race_packet_ranks_split_confirmed_16x400_above_newer_easy_runs(db_session, test_athlete):
    from services.coach_tools import get_race_strategy_packet

    workout = _run(
        db_session,
        test_athlete.id,
        name="Morning Run",
        days_ago=28,
        distance_m=11200,
        duration_s=4300,
    )
    _add_16x400_splits(db_session, workout)

    for idx in range(8):
        _run(
            db_session,
            test_athlete.id,
            name=f"Easy aerobic run {idx + 1}",
            days_ago=idx + 2,
            distance_m=7000 + (idx * 500),
            duration_s=2400 + (idx * 180),
            workout_type="easy_run",
        )
    db_session.commit()

    packet = get_race_strategy_packet(
        db_session,
        test_athlete.id,
        race_distance="5k",
        lookback_days=60,
    )

    assert packet["ok"] is True
    workouts = packet["data"]["recent_race_relevant_workouts"]
    ids = [row["activity_id"] for row in workouts]
    assert str(workout.id) in ids
    assert ids.index(str(workout.id)) < min(
        idx for idx, row in enumerate(workouts) if row["name"].startswith("Easy aerobic")
    )

    selected = next(row for row in workouts if row["activity_id"] == str(workout.id))
    assert selected["split_summary"]["total_reps"] == 16
    assert selected["selection_reason"] == "split_confirmed_quality_session"
    assert selected["race_specificity"] == "high"


def test_training_block_narrative_classifies_generic_title_interval_from_splits(
    db_session, test_athlete
):
    from services.coach_tools import get_training_block_narrative

    workout = _run(
        db_session,
        test_athlete.id,
        name="Morning Run",
        days_ago=28,
        distance_m=11200,
        duration_s=4300,
    )
    _add_16x400_splits(db_session, workout)
    db_session.commit()

    result = get_training_block_narrative(db_session, test_athlete.id, days=42)

    assert result["ok"] is True
    row = next(
        item
        for item in result["data"]["quality_sessions"]
        if item["activity_id"] == str(workout.id)
    )
    assert row["classification"] == "speed"
    assert row["split_summary"]["total_reps"] == 16
    assert row["split_summary"]["rep_distance_m"] == 400
    assert "16 x 400m" in result["narrative"]


def test_thread_aware_classification_promotes_race_day_followups():
    context = [
        {
            "role": "user",
            "content": (
                "I have a tune-up 5K this morning and I am considering Maurten "
                "bicarb before I leave for packet pickup."
            ),
        },
        {
            "role": "assistant",
            "content": "Use the race strategy packet before answering.",
        },
    ]

    correction = classify_conversation_contract(
        "I did 16 x 400 faster than that.",
        conversation_context=context,
    )
    pace = classify_conversation_contract(
        "I'm going out at 5:50 pace.",
        conversation_context=context,
    )
    dated_repair = classify_conversation_contract(
        "That workout was on March 28th.",
        conversation_context=[
            *context,
            {
                "role": "assistant",
                "content": "I searched but could not find the 16 x 400 workout.",
            },
        ],
    )

    assert correction.contract_type == ConversationContractType.CORRECTION_DISPUTE
    assert pace.contract_type == ConversationContractType.RACE_DAY
    assert dated_repair.contract_type == ConversationContractType.CORRECTION_DISPUTE
