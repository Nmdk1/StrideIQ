"""
Real athlete profiles cloned from production data.

These profiles are based on real athlete fitness bank data from the StrideIQ
production database. Use `scripts/extract_athlete_profiles.py` to refresh
from live data.

Each profile is a dict that maps to FitnessBank / FingerprintParams / LoadContext
fields, plus metadata for test matrix generation.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from services.fitness_bank import ExperienceLevel, FitnessBank, RacePerformance
from services.plan_framework.fingerprint_bridge import FingerprintParams
from services.plan_framework.load_context import LoadContext


# ── Athlete Profile Definitions ─────────────────────────────────────

REAL_ATHLETES = [
    {
        "name": "Michael",
        "tag": "founder",
        "rpi": 55.0,
        "current_weekly_miles": 62.0,
        "peak_weekly_miles": 75.0,
        "desired_peak_weekly_miles": 75.0,
        "peak_long_run_miles": 18.0,
        "current_long_run_miles": 15.0,
        "average_long_run_miles": 14.5,
        "sustainable_peak_weekly": 65.0,
        "experience_level": ExperienceLevel.EXPERIENCED,
        "peak_ctl": 80.0,
        "current_ctl": 70.0,
        "tau1": 42.0,
        "tau2": 7.0,
        "training_age": 8,
        "recent_quality_sessions_28d": 8,
        "recent_8w_median_weekly_miles": 60.0,
        "recent_8w_p75_long_run_miles": 16.0,
        "recent_16w_p50_long_run_miles": 14.0,
        "typical_long_run_day": 6,  # Sunday
        "typical_quality_day": 2,   # Wednesday
        "typical_rest_days": [0],   # Monday
        "cutback_frequency": 4,
        "quality_spacing_min_hours": 48,
        "limiter": "threshold",
        "l30_max_easy_long_mi": 16.0,
        "observed_recent_weekly_miles": 62.0,
        "is_returning_from_break": False,  # Returned: marathon done, BQ, back to intervals/threshold
    },
    {
        "name": "Brian",
        "tag": "low_volume_high_fitness",
        "rpi": 52.0,  # 8:14/mi for 20mi race → solid RPI
        "current_weekly_miles": 35.0,
        "peak_weekly_miles": 42.0,
        "desired_peak_weekly_miles": 45.0,
        "peak_long_run_miles": 20.0,  # 20-mile race finish
        "current_long_run_miles": 13.0,  # recent long runs shorter
        "average_long_run_miles": 12.0,
        "sustainable_peak_weekly": 38.0,
        "experience_level": ExperienceLevel.INTERMEDIATE,
        "peak_ctl": 55.0,
        "current_ctl": 45.0,
        "tau1": 40.0,
        "tau2": 8.0,
        "training_age": 3,
        "recent_quality_sessions_28d": 4,
        "recent_8w_median_weekly_miles": 33.0,
        "recent_8w_p75_long_run_miles": 13.0,
        "recent_16w_p50_long_run_miles": 12.0,
        "typical_long_run_day": 6,
        "typical_quality_day": 3,
        "typical_rest_days": [0, 4],
        "cutback_frequency": 3,
        "quality_spacing_min_hours": 48,
        "limiter": "volume",
        "l30_max_easy_long_mi": 13.0,
        "observed_recent_weekly_miles": 34.0,
    },
    {
        "name": "Larry",
        "tag": "masters_high_volume",
        "rpi": 52.0,
        "current_weekly_miles": 48.0,
        "peak_weekly_miles": 60.0,
        "desired_peak_weekly_miles": 60.0,
        "peak_long_run_miles": 20.0,
        "current_long_run_miles": 16.0,
        "average_long_run_miles": 15.0,
        "sustainable_peak_weekly": 55.0,
        "experience_level": ExperienceLevel.EXPERIENCED,
        "peak_ctl": 75.0,
        "current_ctl": 65.0,
        "tau1": 45.0,
        "tau2": 6.0,
        "training_age": 15,
        "recent_quality_sessions_28d": 6,
        "recent_8w_median_weekly_miles": 46.0,
        "recent_8w_p75_long_run_miles": 17.0,
        "recent_16w_p50_long_run_miles": 15.0,
        "typical_long_run_day": 5,  # Saturday
        "typical_quality_day": 2,
        "typical_rest_days": [0],
        "cutback_frequency": 4,
        "quality_spacing_min_hours": 48,
        "limiter": "speed",
        "l30_max_easy_long_mi": 17.0,
        "observed_recent_weekly_miles": 47.0,
    },
    {
        "name": "Josh",
        "tag": "fast_competitive",
        "rpi": 60.0,
        "current_weekly_miles": 55.0,
        "peak_weekly_miles": 70.0,
        "desired_peak_weekly_miles": 70.0,
        "peak_long_run_miles": 18.0,
        "current_long_run_miles": 15.0,
        "average_long_run_miles": 14.0,
        "sustainable_peak_weekly": 62.0,
        "experience_level": ExperienceLevel.EXPERIENCED,
        "peak_ctl": 85.0,
        "current_ctl": 75.0,
        "tau1": 38.0,
        "tau2": 7.0,
        "training_age": 6,
        "recent_quality_sessions_28d": 8,
        "recent_8w_median_weekly_miles": 53.0,
        "recent_8w_p75_long_run_miles": 16.0,
        "recent_16w_p50_long_run_miles": 14.0,
        "typical_long_run_day": 6,
        "typical_quality_day": 2,
        "typical_rest_days": [0],
        "cutback_frequency": 4,
        "quality_spacing_min_hours": 48,
        "limiter": None,
        "l30_max_easy_long_mi": 16.0,
        "observed_recent_weekly_miles": 54.0,
    },
    {
        "name": "Mark",
        "tag": "high_volume_ultra",
        "rpi": 50.0,
        "current_weekly_miles": 60.0,
        "peak_weekly_miles": 80.0,
        "desired_peak_weekly_miles": 80.0,
        "peak_long_run_miles": 22.0,
        "current_long_run_miles": 18.0,
        "average_long_run_miles": 16.0,
        "sustainable_peak_weekly": 70.0,
        "experience_level": ExperienceLevel.EXPERIENCED,
        "peak_ctl": 90.0,
        "current_ctl": 78.0,
        "tau1": 44.0,
        "tau2": 6.0,
        "training_age": 10,
        "recent_quality_sessions_28d": 6,
        "recent_8w_median_weekly_miles": 58.0,
        "recent_8w_p75_long_run_miles": 19.0,
        "recent_16w_p50_long_run_miles": 16.0,
        "typical_long_run_day": 5,
        "typical_quality_day": 2,
        "typical_rest_days": [0],
        "cutback_frequency": 4,
        "quality_spacing_min_hours": 48,
        "limiter": "threshold",
        "l30_max_easy_long_mi": 19.0,
        "observed_recent_weekly_miles": 59.0,
    },
    {
        "name": "Adam",
        "tag": "beginner_returning",
        "rpi": 42.0,
        "current_weekly_miles": 20.0,
        "peak_weekly_miles": 30.0,
        "desired_peak_weekly_miles": 30.0,
        "peak_long_run_miles": 13.1,  # St Jude HM PB — proven HM finisher
        "current_long_run_miles": 7.0,
        "average_long_run_miles": 6.5,
        "sustainable_peak_weekly": 25.0,
        "experience_level": ExperienceLevel.BEGINNER,
        "peak_ctl": 35.0,
        "current_ctl": 25.0,
        "tau1": 42.0,
        "tau2": 9.0,
        "training_age": 1,
        "recent_quality_sessions_28d": 2,
        "recent_8w_median_weekly_miles": 18.0,
        "recent_8w_p75_long_run_miles": 7.0,
        "recent_16w_p50_long_run_miles": 6.0,
        "typical_long_run_day": 6,
        "typical_quality_day": 3,
        "typical_rest_days": [0, 4],
        "cutback_frequency": 3,
        "quality_spacing_min_hours": 72,
        "limiter": "volume",
        "l30_max_easy_long_mi": 7.0,
        "observed_recent_weekly_miles": 19.0,
    },
]


# ── Test Matrix ─────────────────────────────────────────────────────

ALL_DISTANCES = ["5K", "10K", "half_marathon", "marathon", "50K", "50_mile", "100K", "100_mile"]

_DISTANCE_DEFAULT_WEEKS = {
    "5K": 10, "10K": 10, "half_marathon": 12, "marathon": 16,
    "50K": 16, "50_mile": 20, "100K": 20, "100_mile": 24,
}

_COMPRESSED_WEEKS = {
    "5K": 6, "10K": 8, "half_marathon": 8, "marathon": 12,
    "50K": 10, "50_mile": 14, "100K": 16, "100_mile": 18,
}

_EXTENDED_WEEKS = {
    "5K": 14, "10K": 14, "half_marathon": 18, "marathon": 24,
    "50K": 20, "50_mile": 28, "100K": 28, "100_mile": 32,
}


@dataclass
class TestCase:
    athlete_name: str
    distance: str
    weeks: int
    label: str  # "standard", "compressed", "extended"

    @property
    def id(self) -> str:
        return f"{self.athlete_name}_{self.distance}_{self.label}"


def build_test_matrix() -> List[TestCase]:
    """Generate the full test matrix: every athlete x every distance x time variants."""
    cases: List[TestCase] = []

    for athlete in REAL_ATHLETES:
        name = athlete["name"]
        for dist in ALL_DISTANCES:
            cases.append(TestCase(name, dist, _DISTANCE_DEFAULT_WEEKS[dist], "standard"))
            cases.append(TestCase(name, dist, _COMPRESSED_WEEKS[dist], "compressed"))
            cases.append(TestCase(name, dist, _EXTENDED_WEEKS[dist], "extended"))

    # Build/maintain modes (no race distance)
    for athlete in REAL_ATHLETES:
        name = athlete["name"]
        cases.append(TestCase(name, "build_volume", 6, "standard"))
        cases.append(TestCase(name, "build_intensity", 4, "standard"))
        cases.append(TestCase(name, "maintain", 4, "standard"))

    return cases


# ── Mock Builders ───────────────────────────────────────────────────

def build_fitness_bank(profile: dict) -> FitnessBank:
    """Create a FitnessBank from a real athlete profile dict."""
    exp = profile.get("experience_level", ExperienceLevel.INTERMEDIATE)
    if isinstance(exp, str):
        exp = ExperienceLevel(exp)

    return FitnessBank(
        athlete_id="real-" + profile["name"].lower(),
        peak_weekly_miles=profile["peak_weekly_miles"],
        peak_monthly_miles=profile["peak_weekly_miles"] * 4.0,
        peak_long_run_miles=profile["peak_long_run_miles"],
        peak_mp_long_run_miles=profile.get("peak_long_run_miles", 10) * 0.5,
        peak_threshold_miles=profile.get("peak_weekly_miles", 40) * 0.15,
        peak_ctl=profile.get("peak_ctl", 50.0),
        race_performances=[],
        best_rpi=profile["rpi"],
        best_race=None,
        current_weekly_miles=profile["current_weekly_miles"],
        current_ctl=profile.get("current_ctl", 40.0),
        current_atl=profile.get("current_ctl", 40.0) * 0.7,
        weeks_since_peak=4,
        current_long_run_miles=profile["current_long_run_miles"],
        average_long_run_miles=profile.get("average_long_run_miles", 10.0),
        tau1=profile.get("tau1", 42.0),
        tau2=profile.get("tau2", 7.0),
        experience_level=exp,
        constraint_type="volume" if profile.get("limiter") == "volume" else "none",
        constraint_details=None,
        is_returning_from_break=profile.get("is_returning_from_break", False),
        typical_long_run_day=profile.get("typical_long_run_day", 6),
        typical_quality_day=profile.get("typical_quality_day", 2),
        typical_rest_days=profile.get("typical_rest_days", [0]),
        weeks_to_80pct_ctl=8,
        weeks_to_race_ready=12,
        sustainable_peak_weekly=profile["sustainable_peak_weekly"],
        recent_quality_sessions_28d=profile.get("recent_quality_sessions_28d", 4),
        recent_8w_median_weekly_miles=profile.get("recent_8w_median_weekly_miles", profile["current_weekly_miles"] * 0.95),
        recent_16w_p90_weekly_miles=profile.get("recent_16w_p90_weekly_miles", profile["peak_weekly_miles"] * 0.9),
        recent_8w_p75_long_run_miles=profile.get("recent_8w_p75_long_run_miles", profile["current_long_run_miles"]),
        recent_16w_p50_long_run_miles=profile.get("recent_16w_p50_long_run_miles", profile["current_long_run_miles"] * 0.9),
        recent_16w_run_count=profile.get("training_age", 2) * 8,
        last_complete_week_miles=profile.get("current_weekly_miles", 30.0),
    )


def build_fingerprint(profile: dict) -> FingerprintParams:
    return FingerprintParams(
        cutback_frequency=profile.get("cutback_frequency", 3),
        quality_spacing_min_hours=profile.get("quality_spacing_min_hours", 48),
        limiter=profile.get("limiter"),
    )


def build_load_context(profile: dict) -> LoadContext:
    from datetime import date as _date
    return LoadContext(
        reference_date=_date.today(),
        l30_max_easy_long_mi=profile.get("l30_max_easy_long_mi", profile["current_long_run_miles"]),
        observed_recent_weekly_miles=profile.get("observed_recent_weekly_miles", profile["current_weekly_miles"]),
        history_override_easy_long=False,
    )
