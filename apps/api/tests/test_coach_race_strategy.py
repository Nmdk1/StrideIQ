from datetime import date, datetime, timedelta, timezone

from services.coaching._conversation_contract import (
    ConversationContractType,
    classify_conversation_contract,
    validate_conversation_contract_response,
)


def test_classifies_broad_race_plan_language():
    for message in (
        "Build me a half marathon race plan.",
        "What's my 5K race strategy for Saturday?",
        "Give me a marathon race plan for managing the hills.",
    ):
        contract = classify_conversation_contract(message)
        assert contract.contract_type == ConversationContractType.RACE_STRATEGY
        assert "strategically sharper" in contract.outcome_target


def test_race_strategy_contract_validation_is_guidance_only():
    user_message = "Give me a 5K race strategy for tomorrow."

    # Validation is guidance-only for RACE_STRATEGY — structure is never enforced
    sparse_valid, sparse_reason = validate_conversation_contract_response(
        user_message,
        "Strategy: open controlled, hold effort through mile 2, then close aggressively.",
    )
    full_valid, full_reason = validate_conversation_contract_response(
        user_message,
        (
            "Objective: race for sub-19 if the first mile feels controlled. "
            "Primary limiter: continuous lactate tolerance, not general fitness. "
            "False limiter: ignore the fractured-femur 10K as a clean anchor. "
            "Pacing shape: open controlled, hold pressure through mile 2, then close. "
            "Course risk: the late rise can punish an early surge. "
            "Cues: relax shoulders, pass one runner at a time, keep cadence tall. "
            "Success beyond time: execute the middle mile without bargaining. "
            "Post-race learning: compare mile-2 fade against breathing and leg burn."
        ),
    )

    assert sparse_valid is True
    assert sparse_reason == "ok"
    assert full_valid is True
    assert full_reason == "ok"


def test_race_strategy_packet_assembles_current_race_context(db_session, test_athlete):
    from models import (
        Activity,
        AthleteFact,
        AthleteRaceResultAnchor,
        PerformanceEvent,
        PersonalBest,
        PlannedWorkout,
        TrainingPlan,
    )
    from services.coach_tools import get_race_strategy_packet

    test_athlete.rpi = 53.0
    test_athlete.preferred_units = "imperial"
    db_session.add(test_athlete)

    today = date.today()
    race_date = today + timedelta(days=14)
    plan = TrainingPlan(
        athlete_id=test_athlete.id,
        name="5K Build",
        status="active",
        goal_race_name="Mayor's Cup 5K",
        goal_race_date=race_date,
        goal_race_distance_m=5000,
        goal_time_seconds=18 * 60 + 45,
        plan_start_date=today,
        plan_end_date=race_date,
        total_weeks=8,
        plan_type="5k",
    )
    db_session.add(plan)
    db_session.flush()

    workout_date = today + timedelta(days=2)
    db_session.add(
        PlannedWorkout(
            athlete_id=test_athlete.id,
            plan_id=plan.id,
            scheduled_date=workout_date,
            week_number=1,
            day_of_week=(workout_date.weekday() + 1) % 7,
            title="5K sharpening workout",
            workout_type="quality",
            workout_subtype="threshold",
            phase="build",
            target_distance_km=10.0,
            completed=False,
        )
    )

    prior_race = Activity(
        athlete_id=test_athlete.id,
        name="Mayor's Cup 5K",
        sport="run",
        source="manual",
        start_time=datetime.now(timezone.utc) - timedelta(days=365),
        distance_m=5020,
        duration_s=19 * 60 + 20,
        workout_type="race",
        user_verified_race=True,
        is_race_candidate=True,
        total_elevation_gain=42,
        temperature_f=74,
        humidity_pct=72,
        weather_condition="humid",
        shape_sentence="Opened too hot, faded on the final rise.",
    )
    recent_workout = Activity(
        athlete_id=test_athlete.id,
        name="3 x mile at 5K pressure",
        sport="run",
        source="manual",
        start_time=datetime.now(timezone.utc) - timedelta(days=5),
        distance_m=9650,
        duration_s=43 * 60,
        workout_type="threshold",
        avg_hr=166,
        max_hr=181,
        total_elevation_gain=25,
        shape_sentence="Held rhythm but breathing tightened late.",
    )
    db_session.add_all([prior_race, recent_workout])
    db_session.flush()

    db_session.add(
        PersonalBest(
            athlete_id=test_athlete.id,
            distance_category="5k",
            distance_meters=5000,
            time_seconds=18 * 60 + 58,
            pace_per_mile=366,
            activity_id=prior_race.id,
            achieved_at=prior_race.start_time,
            is_race=True,
        )
    )
    db_session.add(
        PerformanceEvent(
            athlete_id=test_athlete.id,
            activity_id=prior_race.id,
            distance_category="5k",
            event_date=prior_race.start_time.date(),
            event_type="race",
            time_seconds=prior_race.duration_s,
            pace_per_mile=373,
            tsb_at_event=4.0,
            user_confirmed=True,
            detection_source="test",
        )
    )
    db_session.add(
        AthleteRaceResultAnchor(
            athlete_id=test_athlete.id,
            distance_key="5k",
            distance_meters=5000,
            time_seconds=18 * 60 + 58,
            race_date=prior_race.start_time.date(),
            source="user",
        )
    )
    db_session.add_all(
        [
            AthleteFact(
                athlete_id=test_athlete.id,
                fact_type="race_psychology",
                fact_key="race_style",
                fact_value="controlled chaos; can close harder than workouts suggest",
                confidence="athlete_stated",
                source_excerpt="I race controlled chaos",
                is_active=True,
            ),
            AthleteFact(
                athlete_id=test_athlete.id,
                fact_type="invalid_race_anchor",
                fact_key="coke_10k_invalid_anchor",
                fact_value="ran with a fractured femur; do not use as current fitness anchor",
                confidence="athlete_stated",
                source_excerpt="I had a fractured femur during that 10K",
                is_active=True,
            ),
            AthleteFact(
                athlete_id=test_athlete.id,
                fact_type="injury_context",
                fact_key="fractured_femur_history",
                fact_value="prior fractured femur affected race interpretation",
                confidence="athlete_stated",
                source_excerpt="fractured femur",
                is_active=True,
            ),
        ]
    )
    db_session.commit()

    packet = get_race_strategy_packet(
        db_session,
        test_athlete.id,
        race_name="Mayor's Cup 5K",
        race_distance="5k",
    )

    assert packet["ok"] is True
    data = packet["data"]
    assert data["target_race"]["name"] == "Mayor's Cup 5K"
    assert data["target_race"]["distance_m"] == 5000
    assert data["target_race"]["days_until"] == 14
    assert data["prior_course_activity"]["name"] == "Mayor's Cup 5K"
    assert data["prior_course_activity"]["weather"]["temperature_f"] == 74.0
    assert data["recent_race_relevant_workouts"][0]["name"] == "3 x mile at 5K pressure"
    assert data["race_history"]["personal_bests"][0]["distance"] == "5k"
    assert data["race_history"]["performance_events"][0]["event_type"] == "race"
    assert data["race_history"]["race_result_anchors"][0]["distance"] == "5k"
    assert "race_psychology" in data["athlete_memory"]
    assert "invalid_race_anchor" in data["athlete_memory"]
    assert "injury_context" in data["athlete_memory"]
    assert "course evidence" in packet["narrative"].lower()


def test_race_strategy_tool_registered_and_counts_as_grounding():
    from services.ai_coach import AICoach

    coach = AICoach.__new__(AICoach)
    tools = coach._opus_tools()
    tool_names = {tool["name"] for tool in tools}

    assert "get_race_strategy_packet" in tool_names
    is_valid, reason = coach._validate_tool_usage(
        message="Give me a 5K race strategy for tomorrow.",
        tools_called=["get_race_strategy_packet"],
        tool_calls_count=1,
    )
    assert is_valid is True
    assert reason == "ok"
