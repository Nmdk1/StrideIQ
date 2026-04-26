from datetime import date, datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from services.fitness_bank import ConstraintType, ExperienceLevel, FitnessBank, RacePerformance


def build_golden_activities():
    athlete_id = uuid4()
    return [
        # Probable cross-provider duplicate pair.
        SimpleNamespace(
            athlete_id=athlete_id,
            start_time=datetime(2026, 1, 5, 12, 0, 0, tzinfo=timezone.utc),
            distance_m=16093,
            duration_s=3600,
            provider="garmin",
            workout_type="long_run",
            name="Long Run",
        ),
        SimpleNamespace(
            athlete_id=athlete_id,
            start_time=datetime(2026, 1, 5, 12, 0, 0, tzinfo=timezone.utc),
            distance_m=16080,
            duration_s=3605,
            provider="strava",
            workout_type="long_run",
            name="Long Run",
        ),
        # Distinct double (>10 min apart): must not collapse.
        SimpleNamespace(
            athlete_id=athlete_id,
            start_time=datetime(2026, 1, 8, 7, 0, 0, tzinfo=timezone.utc),
            distance_m=10000,
            duration_s=2400,
            provider="strava",
            workout_type="easy_run",
            name="AM Run",
        ),
        SimpleNamespace(
            athlete_id=athlete_id,
            start_time=datetime(2026, 1, 8, 7, 11, 0, tzinfo=timezone.utc),
            distance_m=10020,
            duration_s=2410,
            provider="garmin",
            workout_type="easy_run",
            name="PM Run",
        ),
    ]


def build_golden_injury_return_bank(recent_quality_sessions_28d: int) -> FitnessBank:
    return FitnessBank(
        athlete_id="golden-athlete",
        peak_weekly_miles=70.0,
        peak_monthly_miles=270.0,
        peak_long_run_miles=22.0,
        peak_mp_long_run_miles=16.0,
        peak_threshold_miles=8.0,
        peak_ctl=90.0,
        race_performances=[
            RacePerformance(
                date=date(2025, 12, 13),
                distance="10k",
                distance_m=10000,
                finish_time_seconds=2340,  # 39:00
                pace_per_mile=6.27,
                rpi=53.3,
            ),
            RacePerformance(
                date=date(2026, 3, 15),
                distance="marathon",
                distance_m=42195,
                finish_time_seconds=10800,  # slower comeback race
                pace_per_mile=6.87,
                rpi=49.0,
                conditions="comeback",
            ),
        ],
        best_rpi=53.3,
        best_race=RacePerformance(
            date=date(2025, 12, 13),
            distance="10k",
            distance_m=10000,
            finish_time_seconds=2340,
            pace_per_mile=6.27,
            rpi=53.3,
        ),
        current_weekly_miles=28.0,
        current_ctl=52.0,
        current_atl=56.0,
        weeks_since_peak=12,
        current_long_run_miles=15.0,
        average_long_run_miles=16.5,
        tau1=35.0,
        tau2=9.0,
        experience_level=ExperienceLevel.EXPERIENCED,
        constraint_type=ConstraintType.INJURY,
        constraint_details="post-fracture return",
        is_returning_from_break=True,
        typical_long_run_day=6,
        typical_quality_day=3,
        typical_rest_days=[0],
        weeks_to_80pct_ctl=4,
        weeks_to_race_ready=5,
        sustainable_peak_weekly=62.0,
        recent_quality_sessions_28d=recent_quality_sessions_28d,
    )

