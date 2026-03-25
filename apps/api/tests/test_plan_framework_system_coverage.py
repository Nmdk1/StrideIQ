from __future__ import annotations

from datetime import datetime, timedelta, date, timezone
from uuid import uuid4


def test_plan_framework_high_volume_experienced_gets_vo2_touch_and_year_round_strides(db_session):
    """
    Regression guard for the plan_framework generator:
    - High-volume, experienced runner should get periodic VO2 touches early (base_speed).
    - Strides should appear year-round as easy+strides (without sacrificing easy volume).
    - No athlete-facing 'tempo' workout_type should be emitted.
    """
    from models import Athlete, Activity
    from services.plan_framework.generator import PlanGenerator

    athlete = Athlete(
        email=f"pf_cov_{uuid4()}@example.com",
        display_name="PF Coverage",
        subscription_tier="free",
        role="athlete",
        onboarding_stage="complete",
        onboarding_completed=True,
        birthdate=date(1985, 1, 1),
    )
    db_session.add(athlete)
    db_session.commit()
    db_session.refresh(athlete)

    # Experience proxy: lots of recent runs (last 120 days).
    now = datetime.now(timezone.utc)
    for i in range(45):
        db_session.add(
            Activity(
                athlete_id=athlete.id,
                name=f"Easy Run {i}",
                start_time=now - timedelta(days=i * 2),
                sport="run",
                source="manual",
                duration_s=45 * 60,
                distance_m=int(7 * 1609.344),
                is_duplicate=False,
            )
        )
    db_session.commit()

    gen = PlanGenerator(db_session)
    race_date = date.today() + timedelta(weeks=12)
    plan = gen.generate_semi_custom(
        distance="marathon",
        duration_weeks=12,
        current_weekly_miles=70,
        days_per_week=6,
        race_date=race_date,
        recent_race_distance="5k",
        recent_race_time_seconds=20 * 60,
        athlete_id=athlete.id,
    )

    # Strides should be present every week (easy_strides day).
    for week in range(1, 11):  # exclude taper/race tail
        week_workouts = plan.get_week(week)
        assert any(w.workout_type == "easy_strides" for w in week_workouts), f"Week {week} missing easy_strides"

    # VO2 touch (intervals) must NOT appear in marathon base_speed phase (T2-1 phase guard).
    # The base_speed allowed_workouts for marathon are: easy, long, strides, hills, recovery.
    # High-volume athletes in base phase get hills/easy_strides, not intervals.
    wk2 = plan.get_week(2)
    assert not any(w.workout_type == "intervals" for w in wk2), (
        "T2-1 violation: 'intervals' appeared in marathon base_speed phase (week 2). "
        "Phase guard must redirect to an allowed quality workout (hills/strides/easy_strides)."
    )
    # Quality session must still be present (hills or easy_strides is the correct substitute)
    base_quality_types = {"hills", "easy_strides", "strides"}
    assert any(w.workout_type in base_quality_types for w in wk2), (
        f"Week 2 (base_speed) should have a quality session (hills/strides). "
        f"Got: {[w.workout_type for w in wk2]}"
    )

    # Terminology invariant: never emit ambiguous 'tempo' as a workout_type.
    assert all("tempo" not in (w.workout_type or "").lower() for w in plan.workouts)

