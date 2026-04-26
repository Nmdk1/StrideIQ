"""
Synthetic athlete profiles for V2 evaluation.

15 fixed profiles.  Version-controlled.  Do not change between runs.
These are used by the harness to produce repeatable test output.
"""

from __future__ import annotations

from services.fitness_bank import (
    ConstraintType,
    ExperienceLevel,
    FitnessBank,
)
from services.plan_framework.fingerprint_bridge import FingerprintParams
from services.plan_framework.load_context import LoadContext
from datetime import date


PROFILES = [
    {
        "id": "beginner_5k",
        "rpi": 35, "days_per_week": 3, "weekly_miles": 12,
        "training_age": 0.5, "goal_event": "5K",
        "weeks_to_race": 10, "mode": "race",
        "experience": ExperienceLevel.BEGINNER,
    },
    {
        "id": "developing_10k",
        "rpi": 42, "days_per_week": 4, "weekly_miles": 22,
        "training_age": 2, "goal_event": "10K",
        "weeks_to_race": 10, "mode": "race",
        "experience": ExperienceLevel.INTERMEDIATE,
    },
    {
        "id": "developing_hm",
        "rpi": 45, "days_per_week": 4, "weekly_miles": 28,
        "training_age": 3, "goal_event": "half_marathon",
        "weeks_to_race": 12, "mode": "race",
        "experience": ExperienceLevel.INTERMEDIATE,
    },
    {
        "id": "established_marathon",
        "rpi": 55, "days_per_week": 5, "weekly_miles": 45,
        "training_age": 8, "goal_event": "marathon",
        "weeks_to_race": 16, "mode": "race",
        "experience": ExperienceLevel.EXPERIENCED,
        "notes": "Founder profile — review this one manually",
    },
    {
        "id": "masters_marathon",
        "rpi": 50, "days_per_week": 5, "weekly_miles": 38,
        "training_age": 20, "goal_event": "marathon",
        "weeks_to_race": 18, "mode": "race",
        "experience": ExperienceLevel.EXPERIENCED,
    },
    {
        "id": "advanced_50k",
        "rpi": 58, "days_per_week": 6, "weekly_miles": 55,
        "training_age": 6, "goal_event": "50K",
        "weeks_to_race": 12, "mode": "race",
        "experience": ExperienceLevel.EXPERIENCED,
    },
    {
        "id": "champion_100mi",
        "rpi": 65, "days_per_week": 6, "weekly_miles": 75,
        "training_age": 10, "goal_event": "100_mile",
        "weeks_to_race": 16, "mode": "race",
        "experience": ExperienceLevel.ELITE,
    },
    {
        "id": "onramp_brand_new",
        "rpi": None, "days_per_week": 3, "weekly_miles": 0,
        "training_age": 0, "goal_event": None,
        "weeks_to_race": None, "mode": "build_onramp",
        "experience": ExperienceLevel.BEGINNER,
        "notes": "No RPI — brand new runner. Paces from defaults.",
    },
    {
        "id": "build_volume_low",
        "rpi": 40, "days_per_week": 4, "weekly_miles": 20,
        "training_age": 1, "goal_event": None,
        "weeks_to_race": None, "mode": "build_volume",
        "experience": ExperienceLevel.BEGINNER,
    },
    {
        "id": "build_volume_high",
        "rpi": 56, "days_per_week": 5, "weekly_miles": 50,
        "training_age": 5, "goal_event": None,
        "weeks_to_race": None, "mode": "build_volume",
        "experience": ExperienceLevel.EXPERIENCED,
    },
    {
        "id": "build_intensity",
        "rpi": 52, "days_per_week": 5, "weekly_miles": 40,
        "training_age": 4, "goal_event": None,
        "weeks_to_race": None, "mode": "build_intensity",
        "experience": ExperienceLevel.INTERMEDIATE,
    },
    {
        "id": "maintain_casual",
        "rpi": 42, "days_per_week": 3, "weekly_miles": 18,
        "training_age": 3, "goal_event": None,
        "weeks_to_race": None, "mode": "maintain",
        "experience": ExperienceLevel.INTERMEDIATE,
    },
    {
        "id": "short_build_hm",
        "rpi": 48, "days_per_week": 4, "weekly_miles": 30,
        "training_age": 3, "goal_event": "half_marathon",
        "weeks_to_race": 8, "mode": "race",
        "experience": ExperienceLevel.INTERMEDIATE,
        "notes": "Compressed timeline — tests phase allocation",
    },
    {
        "id": "first_marathon",
        "rpi": 44, "days_per_week": 4, "weekly_miles": 25,
        "training_age": 2, "goal_event": "marathon",
        "weeks_to_race": 20, "mode": "race",
        "experience": ExperienceLevel.INTERMEDIATE,
        "notes": "First-time marathoner — fueling targets critical",
    },
    {
        "id": "return_from_injury",
        "rpi": 48, "days_per_week": 3, "weekly_miles": 10,
        "training_age": 5, "goal_event": None,
        "weeks_to_race": None, "mode": "build_onramp",
        "experience": ExperienceLevel.EXPERIENCED,
        "notes": "Experienced runner rebuilding — tests onramp for non-beginners",
    },
]


def build_mock_fitness_bank(profile: dict) -> FitnessBank:
    """Create a FitnessBank from a synthetic profile dict."""
    weekly_mi = profile["weekly_miles"]
    return FitnessBank(
        athlete_id=profile["id"],
        peak_weekly_miles=weekly_mi * 1.2 if weekly_mi > 0 else 30.0,
        peak_monthly_miles=weekly_mi * 4.5 if weekly_mi > 0 else 120.0,
        peak_long_run_miles=weekly_mi * 0.35 if weekly_mi > 0 else 12.0,
        peak_mp_long_run_miles=weekly_mi * 0.25 if weekly_mi > 0 else 0.0,
        peak_threshold_miles=6.0,
        peak_ctl=weekly_mi * 1.5 if weekly_mi > 0 else 30.0,
        race_performances=[],
        best_rpi=float(profile["rpi"]) if profile["rpi"] else 0.0,
        best_race=None,
        current_weekly_miles=float(weekly_mi),
        current_ctl=weekly_mi * 1.2 if weekly_mi > 0 else 25.0,
        current_atl=weekly_mi * 1.0 if weekly_mi > 0 else 20.0,
        weeks_since_peak=4,
        current_long_run_miles=weekly_mi * 0.30 if weekly_mi > 0 else 0.0,
        average_long_run_miles=weekly_mi * 0.28 if weekly_mi > 0 else 0.0,
        tau1=42.0,
        tau2=7.0,
        experience_level=profile["experience"],
        constraint_type=ConstraintType.NONE,
        constraint_details=None,
        is_returning_from_break=profile["id"] == "return_from_injury",
        typical_long_run_day=5,
        typical_quality_day=2,
        typical_rest_days=[0, 6],
        weeks_to_80pct_ctl=4,
        weeks_to_race_ready=8,
        sustainable_peak_weekly=weekly_mi * 1.1 if weekly_mi > 0 else 25.0,
    )


_FINGERPRINT_OVERRIDES = {
    "beginner_5k": {"limiter": "volume", "quality_spacing_min_hours": 72},
    "developing_10k": {"limiter": "speed"},
    "established_marathon": {"limiter": "threshold", "primary_quality_emphasis": "threshold"},
    "advanced_50k": {"limiter": "threshold"},
    "build_volume_low": {"limiter": "volume", "quality_spacing_min_hours": 72},
    "first_marathon": {"limiter": "volume"},
    "return_from_injury": {"limiter": "volume", "quality_spacing_min_hours": 72},
}


def build_mock_fingerprint(profile: dict) -> FingerprintParams:
    """Fingerprint with limiter/emphasis for N=1 testing."""
    overrides = _FINGERPRINT_OVERRIDES.get(profile["id"], {})
    return FingerprintParams(**overrides)


def build_mock_load_context(profile: dict) -> LoadContext:
    """Default load context from weekly miles."""
    weekly_mi = profile["weekly_miles"]
    return LoadContext(
        reference_date=date.today(),
        l30_max_easy_long_mi=weekly_mi * 0.30 if weekly_mi > 0 else None,
        observed_recent_weekly_miles=float(weekly_mi) if weekly_mi > 0 else None,
        history_override_easy_long=False,
    )
