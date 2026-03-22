"""P4 LoadContext + semi-custom / standard history wiring (DB integration)."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

import pytest

from services.plan_framework.load_context import (
    P4_D4_M_DAYS,
    P4_D4_N,
    P4_L30_INCLUSIVE_DAYS,
    build_load_context,
    compute_d4_long_run_override_and_stats,
    easy_long_floor_miles_from_l30,
    effective_starting_weekly_miles_semi_custom,
)
from services.plan_framework.load_context import LoadContext


def _dt(d: date, hour: int = 12) -> datetime:
    return datetime(d.year, d.month, d.day, hour, 0, 0, tzinfo=timezone.utc)


def test_build_load_context_empty_history(db_session):
    from models import Athlete

    athlete = Athlete(
        email=f"lc_{uuid4()}@example.com",
        display_name="LC",
        subscription_tier="free",
        role="athlete",
    )
    db_session.add(athlete)
    db_session.commit()
    db_session.refresh(athlete)

    ref = date(2026, 6, 15)
    ctx = build_load_context(athlete.id, db_session, ref)
    assert ctx.l30_max_easy_long_mi is None
    assert ctx.observed_recent_weekly_miles is None
    assert ctx.history_override_easy_long is False
    assert "cold_start_l30" in ctx.disclosures


def test_build_load_context_l30_95min_counts_and_89_excluded(db_session):
    from models import Activity, Athlete

    athlete = Athlete(
        email=f"lc2_{uuid4()}@example.com",
        display_name="LC2",
        subscription_tier="free",
        role="athlete",
    )
    db_session.add(athlete)
    db_session.commit()
    db_session.refresh(athlete)

    ref = date(2026, 6, 15)
    db_session.add(
        Activity(
            athlete_id=athlete.id,
            name="long",
            start_time=_dt(ref - timedelta(days=5)),
            sport="run",
            source="manual",
            duration_s=int(95 * 60),
            distance_m=int(12 * 1609.344),
            workout_type="Run",
            is_duplicate=False,
        )
    )
    db_session.add(
        Activity(
            athlete_id=athlete.id,
            name="shortlong",
            start_time=_dt(ref - timedelta(days=4)),
            sport="run",
            source="manual",
            duration_s=int(89 * 60),
            distance_m=int(15 * 1609.344),
            workout_type="Run",
            is_duplicate=False,
        )
    )
    db_session.commit()

    ctx = build_load_context(athlete.id, db_session, ref)
    assert ctx.l30_max_easy_long_mi is not None
    assert abs(ctx.l30_max_easy_long_mi - 12.0) < 0.2


def test_build_load_context_race_excluded_from_l30(db_session):
    from models import Activity, Athlete

    athlete = Athlete(
        email=f"lc3_{uuid4()}@example.com",
        display_name="LC3",
        subscription_tier="free",
        role="athlete",
    )
    db_session.add(athlete)
    db_session.commit()
    db_session.refresh(athlete)

    ref = date(2026, 6, 15)
    db_session.add(
        Activity(
            athlete_id=athlete.id,
            name="race",
            start_time=_dt(ref - timedelta(days=3)),
            sport="run",
            source="manual",
            duration_s=int(95 * 60),
            distance_m=int(26 * 1609.344),
            workout_type="Race",
            is_duplicate=False,
        )
    )
    db_session.commit()

    ctx = build_load_context(athlete.id, db_session, ref)
    assert ctx.l30_max_easy_long_mi is None


def test_l30_boundary_30_days_before_reference_excluded(db_session):
    from models import Activity, Athlete

    athlete = Athlete(
        email=f"lc4_{uuid4()}@example.com",
        display_name="LC4",
        subscription_tier="free",
        role="athlete",
    )
    db_session.add(athlete)
    db_session.commit()
    db_session.refresh(athlete)

    ref = date(2026, 6, 15)
    boundary_day = ref - timedelta(days=P4_L30_INCLUSIVE_DAYS)

    db_session.add(
        Activity(
            athlete_id=athlete.id,
            name="edge",
            start_time=_dt(boundary_day),
            sport="run",
            source="manual",
            duration_s=int(95 * 60),
            distance_m=int(20 * 1609.344),
            workout_type="Run",
            is_duplicate=False,
        )
    )
    db_session.commit()

    ctx = build_load_context(athlete.id, db_session, ref)
    assert ctx.l30_max_easy_long_mi is None

    inside = boundary_day + timedelta(days=1)
    db_session.add(
        Activity(
            athlete_id=athlete.id,
            name="inside",
            start_time=_dt(inside),
            sport="run",
            source="manual",
            duration_s=int(95 * 60),
            distance_m=int(11 * 1609.344),
            workout_type="Run",
            is_duplicate=False,
        )
    )
    db_session.commit()

    ctx2 = build_load_context(athlete.id, db_session, ref)
    assert ctx2.l30_max_easy_long_mi is not None
    assert ctx2.l30_max_easy_long_mi >= 10.5


def test_d4_override_true_when_n_and_m_satisfied(db_session):
    from models import Activity, Athlete

    athlete = Athlete(
        email=f"d4t_{uuid4()}@example.com",
        display_name="D4T",
        subscription_tier="free",
        role="athlete",
    )
    db_session.add(athlete)
    db_session.commit()
    db_session.refresh(athlete)

    ref = date(2026, 6, 15)
    for i in range(P4_D4_N):
        db_session.add(
            Activity(
                athlete_id=athlete.id,
                name=f"15_{i}",
                start_time=_dt(ref - timedelta(days=200 + i * 3)),
                sport="run",
                source="manual",
                duration_s=3600,
                distance_m=int(15.5 * 1609.344),
                workout_type="Run",
                is_duplicate=False,
            )
        )
    db_session.add(
        Activity(
            athlete_id=athlete.id,
            name="18recent",
            start_time=_dt(ref - timedelta(days=30)),
            sport="run",
            source="manual",
            duration_s=7200,
            distance_m=int(18.5 * 1609.344),
            workout_type="Run",
            is_duplicate=False,
        )
    )
    db_session.commit()

    ok, c15, last18 = compute_d4_long_run_override_and_stats(
        db_session, athlete.id, ref
    )
    assert c15 >= P4_D4_N
    assert last18 is not None
    assert (ref - last18).days <= P4_D4_M_DAYS
    assert ok is True

    ctx = build_load_context(athlete.id, db_session, ref)
    assert ctx.history_override_easy_long is True


def test_d4_override_false_when_count_low(db_session):
    from models import Activity, Athlete

    athlete = Athlete(
        email=f"d4f_{uuid4()}@example.com",
        display_name="D4F",
        subscription_tier="free",
        role="athlete",
    )
    db_session.add(athlete)
    db_session.commit()
    db_session.refresh(athlete)

    ref = date(2026, 6, 15)
    for i in range(3):
        db_session.add(
            Activity(
                athlete_id=athlete.id,
                name=f"15_{i}",
                start_time=_dt(ref - timedelta(days=100 + i)),
                sport="run",
                source="manual",
                duration_s=3600,
                distance_m=int(16 * 1609.344),
                workout_type="Run",
                is_duplicate=False,
            )
        )
    db_session.add(
        Activity(
            athlete_id=athlete.id,
            name="18recent",
            start_time=_dt(ref - timedelta(days=20)),
            sport="run",
            source="manual",
            duration_s=7200,
            distance_m=int(19 * 1609.344),
            workout_type="Run",
            is_duplicate=False,
        )
    )
    db_session.commit()

    ok, c15, _ = compute_d4_long_run_override_and_stats(db_session, athlete.id, ref)
    assert c15 < P4_D4_N
    assert ok is False


def test_effective_starting_weekly_miles_cap():
    lc = LoadContext(
        reference_date=date.today(),
        l30_max_easy_long_mi=None,
        observed_recent_weekly_miles=40.0,
        history_override_easy_long=False,
        disclosures=[],
    )
    eff = effective_starting_weekly_miles_semi_custom(30.0, lc, tier_max_weekly_miles=80.0)
    assert eff == 40.0
    eff2 = effective_starting_weekly_miles_semi_custom(30.0, lc, tier_max_weekly_miles=44.0)
    assert abs(eff2 - min(40.0, 40.0 * 1.15, 44.0)) < 1e-6


def test_easy_long_floor_from_l30():
    f = easy_long_floor_miles_from_l30(14.0, "marathon", "mid")
    assert f is not None and f >= 14.0


def test_semi_custom_low_questionnaire_high_history_raises_first_long(db_session):
    from models import Activity, Athlete
    from services.plan_framework.generator import PlanGenerator

    athlete = Athlete(
        email=f"semi_{uuid4()}@example.com",
        display_name="Semi",
        subscription_tier="free",
        role="athlete",
    )
    db_session.add(athlete)
    db_session.commit()
    db_session.refresh(athlete)

    race_date = date.today() + timedelta(weeks=20)
    duration_weeks = 18
    start_date = race_date - timedelta(weeks=duration_weeks - 1, days=6)

    for w in range(4):
        ws = start_date - timedelta(days=7 * (w + 1))
        for d in range(5):
            db_session.add(
                Activity(
                    athlete_id=athlete.id,
                    name=f"w{w}d{d}",
                    start_time=_dt(ws + timedelta(days=d)),
                    sport="run",
                    source="manual",
                    duration_s=3600,
                    distance_m=int(10 * 1609.344),
                    workout_type="Run",
                    is_duplicate=False,
                )
            )
    db_session.add(
        Activity(
            athlete_id=athlete.id,
            name="l30long",
            start_time=_dt(start_date - timedelta(days=3)),
            sport="run",
            source="manual",
            duration_s=int(95 * 60),
            distance_m=int(14 * 1609.344),
            workout_type="Run",
            is_duplicate=False,
        )
    )
    db_session.commit()

    gen = PlanGenerator(db_session)
    plan = gen.generate_semi_custom(
        distance="marathon",
        duration_weeks=duration_weeks,
        current_weekly_miles=25.0,
        days_per_week=6,
        race_date=race_date,
        recent_race_distance="half_marathon",
        recent_race_time_seconds=120 * 60,
        athlete_id=athlete.id,
    )
    w1 = plan.get_week(1)
    longs = [x for x in w1 if x.workout_type == "long"]
    assert longs, "expected a long in week 1"
    assert (longs[0].distance_miles or 0) >= 13.5


def test_generate_standard_use_history_false_vs_true_volume_shift(db_session):
    from models import Activity, Athlete
    from services.plan_framework.generator import PlanGenerator

    athlete = Athlete(
        email=f"std_{uuid4()}@example.com",
        display_name="Std",
        subscription_tier="free",
        role="athlete",
    )
    db_session.add(athlete)
    db_session.commit()
    db_session.refresh(athlete)

    start = date.today() + timedelta(days=3)
    start_monday = start - timedelta(days=start.weekday())

    for w in range(4):
        ws = start_monday - timedelta(weeks=w + 1)
        for d in range(5):
            db_session.add(
                Activity(
                    athlete_id=athlete.id,
                    name=f"w{w}d{d}",
                    start_time=_dt(ws + timedelta(days=d)),
                    sport="run",
                    source="manual",
                    duration_s=3600,
                    distance_m=int(12 * 1609.344),
                    workout_type="Run",
                    is_duplicate=False,
                )
            )
    db_session.commit()

    gen = PlanGenerator(db_session)
    p0 = gen.generate_standard(
        "marathon", 12, "mid", 6, start_date=start_monday, use_history=False
    )
    p1 = gen.generate_standard(
        "marathon",
        12,
        "mid",
        6,
        start_date=start_monday,
        athlete_id=athlete.id,
        use_history=True,
    )
    assert p0.weekly_volumes[0] <= p1.weekly_volumes[0]
