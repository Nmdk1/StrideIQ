"""
Canonical fake athlete library for plan generation testing.

10 athletes spanning the full competitive spectrum — beginner through elite —
covering varied mileage, race history, injury/comeback status, and age profiles.

Each athlete has:
  - FitnessBank  (constraint-aware + model-driven planner input)
  - semi_custom_inputs  (generate_semi_custom input dict)
  - label  (human-readable name for report output)
  - notes  (what makes this athlete interesting / edge-case)
"""
from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

from services.fitness_bank import (
    ConstraintType,
    ExperienceLevel,
    FitnessBank,
    RacePerformance,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _race(distance: str, distance_m: float, finish_s: int, rpi: float) -> RacePerformance:
    pace_per_mile = (finish_s / 60.0) / (distance_m / 1609.344)
    return RacePerformance(
        date=date.today() - timedelta(days=60),
        distance=distance,
        distance_m=distance_m,
        finish_time_seconds=finish_s,
        pace_per_mile=pace_per_mile,
        rpi=rpi,
    )


# ---------------------------------------------------------------------------
# Athlete 1 — Beginner
# 15 mpw, 5K goal, no race history. Just started structured training.
# ---------------------------------------------------------------------------
def make_beginner() -> FitnessBank:
    peak_mpw = 18.0
    return FitnessBank(
        athlete_id=str(uuid4()),
        peak_weekly_miles=peak_mpw,
        peak_monthly_miles=peak_mpw * 4.0,
        peak_long_run_miles=7.0,
        peak_mp_long_run_miles=0.0,
        peak_threshold_miles=0.0,
        peak_ctl=22.0,
        race_performances=[],
        best_rpi=None,
        best_race=None,
        current_weekly_miles=15.0,
        current_ctl=18.0,
        current_atl=16.0,
        weeks_since_peak=2,
        current_long_run_miles=5.0,
        average_long_run_miles=5.0,
        tau1=35.0,
        tau2=7.0,
        experience_level=ExperienceLevel.BEGINNER,
        constraint_type=ConstraintType.NONE,
        constraint_details=None,
        is_returning_from_break=False,
        typical_long_run_day=6,
        typical_quality_day=3,
        typical_rest_days=[0, 2],
        weeks_to_80pct_ctl=4,
        weeks_to_race_ready=8,
        sustainable_peak_weekly=peak_mpw * 0.85,
        recent_quality_sessions_28d=1,
        recent_8w_median_weekly_miles=14.0,
        recent_16w_p90_weekly_miles=17.0,
        recent_8w_p75_long_run_miles=5.5,
        recent_16w_p50_long_run_miles=5.0,
        recent_16w_run_count=20,
        peak_confidence="low",
    )

BEGINNER = {
    "label": "Beginner (15 mpw, no race history)",
    "notes": "Just started structured training. 3x/week, 5K goal. Tests floor logic.",
    "make_bank": make_beginner,
    "semi_custom": {
        "current_weekly_miles": 15.0,
        "days_per_week": 4,
        "recent_race_distance": None,
        "recent_race_time_seconds": None,
    },
}


# ---------------------------------------------------------------------------
# Athlete 2 — Building recreational runner
# 28 mpw, 54:00 10K (RPI ~41), 5 days/week. 2 years running.
# ---------------------------------------------------------------------------
def make_recreational() -> FitnessBank:
    race_10k = _race("10k", 10000.0, 3240, 41.0)   # 54:00 10K
    peak_mpw = 32.0
    return FitnessBank(
        athlete_id=str(uuid4()),
        peak_weekly_miles=peak_mpw,
        peak_monthly_miles=peak_mpw * 4.1,
        peak_long_run_miles=12.0,
        peak_mp_long_run_miles=0.0,
        peak_threshold_miles=3.0,
        peak_ctl=40.0,
        race_performances=[race_10k],
        best_rpi=41.0,
        best_race=race_10k,
        current_weekly_miles=28.0,
        current_ctl=34.0,
        current_atl=30.0,
        weeks_since_peak=4,
        current_long_run_miles=10.0,
        average_long_run_miles=9.0,
        tau1=38.0,
        tau2=7.0,
        experience_level=ExperienceLevel.BEGINNER,
        constraint_type=ConstraintType.NONE,
        constraint_details=None,
        is_returning_from_break=False,
        typical_long_run_day=6,
        typical_quality_day=3,
        typical_rest_days=[0],
        weeks_to_80pct_ctl=3,
        weeks_to_race_ready=6,
        sustainable_peak_weekly=peak_mpw * 0.88,
        recent_quality_sessions_28d=2,
        recent_8w_median_weekly_miles=27.0,
        recent_16w_p90_weekly_miles=31.0,
        recent_8w_p75_long_run_miles=10.5,
        recent_16w_p50_long_run_miles=9.0,
        recent_16w_run_count=36,
        peak_confidence="moderate",
    )

RECREATIONAL = {
    "label": "Recreational (28 mpw, 54:00 10K)",
    "notes": "Developing runner. Handling quality but not a lot of volume history.",
    "make_bank": make_recreational,
    "semi_custom": {
        "current_weekly_miles": 28.0,
        "days_per_week": 5,
        "recent_race_distance": "10k",
        "recent_race_time_seconds": 3240,
    },
}


# ---------------------------------------------------------------------------
# Athlete 3 — Injury return (comeback)
# Was 50 mpw, now 30, 3 months off. 1:45 HM (RPI ~43).
# ---------------------------------------------------------------------------
def make_comeback() -> FitnessBank:
    race_half = _race("half_marathon", 21097.5, 6300, 43.0)   # 1:45 HM
    peak_mpw = 50.0
    return FitnessBank(
        athlete_id=str(uuid4()),
        peak_weekly_miles=peak_mpw,
        peak_monthly_miles=peak_mpw * 4.0,
        peak_long_run_miles=18.0,
        peak_mp_long_run_miles=0.0,
        peak_threshold_miles=5.0,
        peak_ctl=60.0,
        race_performances=[race_half],
        best_rpi=43.0,
        best_race=race_half,
        current_weekly_miles=30.0,
        current_ctl=36.0,
        current_atl=32.0,
        weeks_since_peak=14,
        current_long_run_miles=10.0,
        average_long_run_miles=9.0,
        tau1=40.0,
        tau2=7.0,
        experience_level=ExperienceLevel.INTERMEDIATE,
        constraint_type=ConstraintType.INJURY,
        constraint_details="injury_return",
        is_returning_from_break=True,
        typical_long_run_day=6,
        typical_quality_day=3,
        typical_rest_days=[0],
        weeks_to_80pct_ctl=6,
        weeks_to_race_ready=10,
        sustainable_peak_weekly=peak_mpw * 0.80,
        recent_quality_sessions_28d=1,
        recent_8w_median_weekly_miles=28.0,
        recent_16w_p90_weekly_miles=42.0,
        recent_8w_p75_long_run_miles=11.0,
        recent_16w_p50_long_run_miles=9.0,
        recent_16w_run_count=28,
        peak_confidence="moderate",
    )

COMEBACK = {
    "label": "Injury Return (30 mpw → was 50, 1:45 HM)",
    "notes": "Recovering from 3-month break. Tests conservative load context and floor logic.",
    "make_bank": make_comeback,
    "semi_custom": {
        "current_weekly_miles": 30.0,
        "days_per_week": 5,
        "recent_race_distance": "half_marathon",
        "recent_race_time_seconds": 6300,
    },
}


# ---------------------------------------------------------------------------
# Athlete 4 — Consistent intermediate
# 45 mpw, 45:00 10K (RPI ~47), healthy and progressing.
# ---------------------------------------------------------------------------
def make_consistent_mid() -> FitnessBank:
    race_10k = _race("10k", 10000.0, 2700, 47.0)   # 45:00 10K
    peak_mpw = 50.0
    return FitnessBank(
        athlete_id=str(uuid4()),
        peak_weekly_miles=peak_mpw,
        peak_monthly_miles=peak_mpw * 4.2,
        peak_long_run_miles=16.0,
        peak_mp_long_run_miles=12.0,
        peak_threshold_miles=6.0,
        peak_ctl=60.0,
        race_performances=[race_10k],
        best_rpi=47.0,
        best_race=race_10k,
        current_weekly_miles=45.0,
        current_ctl=54.0,
        current_atl=48.0,
        weeks_since_peak=4,
        current_long_run_miles=14.0,
        average_long_run_miles=13.0,
        tau1=40.0,
        tau2=7.0,
        experience_level=ExperienceLevel.INTERMEDIATE,
        constraint_type=ConstraintType.NONE,
        constraint_details=None,
        is_returning_from_break=False,
        typical_long_run_day=6,
        typical_quality_day=3,
        typical_rest_days=[0],
        weeks_to_80pct_ctl=2,
        weeks_to_race_ready=4,
        sustainable_peak_weekly=peak_mpw * 0.90,
        recent_quality_sessions_28d=4,
        recent_8w_median_weekly_miles=44.0,
        recent_16w_p90_weekly_miles=49.0,
        recent_8w_p75_long_run_miles=15.0,
        recent_16w_p50_long_run_miles=13.0,
        recent_16w_run_count=60,
        peak_confidence="high",
    )

CONSISTENT_MID = {
    "label": "Consistent Mid (45 mpw, 45:00 10K)",
    "notes": "Steady improver with reliable history. Baseline N=1 test case.",
    "make_bank": make_consistent_mid,
    "semi_custom": {
        "current_weekly_miles": 45.0,
        "days_per_week": 6,
        "recent_race_distance": "10k",
        "recent_race_time_seconds": 2700,
    },
}


# ---------------------------------------------------------------------------
# Athlete 5 — Masters runner (50 mpw, slower recovery, age 52)
# 50 mpw, 47:00 10K (RPI ~46), but needs extra recovery days.
# ---------------------------------------------------------------------------
def make_masters() -> FitnessBank:
    race_10k = _race("10k", 10000.0, 2820, 46.0)   # 47:00 10K
    peak_mpw = 55.0
    return FitnessBank(
        athlete_id=str(uuid4()),
        peak_weekly_miles=peak_mpw,
        peak_monthly_miles=peak_mpw * 4.0,
        peak_long_run_miles=16.0,
        peak_mp_long_run_miles=10.0,
        peak_threshold_miles=6.0,
        peak_ctl=66.0,
        race_performances=[race_10k],
        best_rpi=46.0,
        best_race=race_10k,
        current_weekly_miles=50.0,
        current_ctl=60.0,
        current_atl=50.0,
        weeks_since_peak=3,
        current_long_run_miles=14.0,
        average_long_run_miles=14.0,
        tau1=42.0,
        tau2=8.0,   # Slightly longer fatigue for masters
        experience_level=ExperienceLevel.EXPERIENCED,
        constraint_type=ConstraintType.NONE,
        constraint_details=None,
        is_returning_from_break=False,
        typical_long_run_day=6,
        typical_quality_day=3,
        typical_rest_days=[0, 2],   # Two rest days needed
        weeks_to_80pct_ctl=2,
        weeks_to_race_ready=4,
        sustainable_peak_weekly=peak_mpw * 0.88,
        recent_quality_sessions_28d=3,
        recent_8w_median_weekly_miles=49.0,
        recent_16w_p90_weekly_miles=54.0,
        recent_8w_p75_long_run_miles=15.0,
        recent_16w_p50_long_run_miles=14.0,
        recent_16w_run_count=55,
        peak_confidence="high",
    )

MASTERS = {
    "label": "Masters (50 mpw, age ~52, 47:00 10K)",
    "notes": "Experienced but needs 2 rest days. Tests 5d/week plan quality.",
    "make_bank": make_masters,
    "semi_custom": {
        "current_weekly_miles": 50.0,
        "days_per_week": 5,
        "recent_race_distance": "10k",
        "recent_race_time_seconds": 2820,
    },
}


# ---------------------------------------------------------------------------
# Athlete 6 — Founder mirror
# 55–65 mpw, 39:14 10K (RPI ~51.5), long runs 18–22mi. Competitive masters.
# ---------------------------------------------------------------------------
def make_founder_mirror() -> FitnessBank:
    race_10k = _race("10k", 10000.0, 2354, 51.5)   # 39:14 10K
    peak_mpw = 65.0
    return FitnessBank(
        athlete_id=str(uuid4()),
        peak_weekly_miles=peak_mpw,
        peak_monthly_miles=peak_mpw * 4.3,
        peak_long_run_miles=22.0,
        peak_mp_long_run_miles=16.0,
        peak_threshold_miles=8.0,
        peak_ctl=78.0,
        race_performances=[race_10k],
        best_rpi=51.5,
        best_race=race_10k,
        current_weekly_miles=55.0,
        current_ctl=66.0,
        current_atl=58.0,
        weeks_since_peak=6,
        current_long_run_miles=18.0,
        average_long_run_miles=19.0,
        tau1=42.0,
        tau2=7.0,
        experience_level=ExperienceLevel.EXPERIENCED,
        constraint_type=ConstraintType.NONE,
        constraint_details=None,
        is_returning_from_break=False,
        typical_long_run_day=6,
        typical_quality_day=3,
        typical_rest_days=[0],
        weeks_to_80pct_ctl=1,
        weeks_to_race_ready=3,
        sustainable_peak_weekly=peak_mpw * 0.92,
        recent_quality_sessions_28d=6,
        recent_8w_median_weekly_miles=58.0,
        recent_16w_p90_weekly_miles=64.0,
        recent_8w_p75_long_run_miles=20.0,
        recent_16w_p50_long_run_miles=18.0,
        recent_16w_run_count=80,
        peak_confidence="high",
    )

FOUNDER_MIRROR = {
    "label": "Founder Mirror (55-65 mpw, 39:14 10K, RPI ~51.5)",
    "notes": "Competitive masters, long runs 18-22mi, training for marathon/HM.",
    "make_bank": make_founder_mirror,
    "semi_custom": {
        "current_weekly_miles": 55.0,
        "days_per_week": 6,
        "recent_race_distance": "10k",
        "recent_race_time_seconds": 2354,
    },
}


# ---------------------------------------------------------------------------
# Athlete 7 — Sub-3 marathon aspirant
# 65 mpw, 38:30 10K (RPI ~52), targeting sub-3 marathon.
# ---------------------------------------------------------------------------
def make_sub3_marathoner() -> FitnessBank:
    race_10k = _race("10k", 10000.0, 2310, 52.0)   # 38:30 10K
    race_marathon = _race("marathon", 42195.0, 10680, 52.0)  # 2:58 marathon
    peak_mpw = 70.0
    return FitnessBank(
        athlete_id=str(uuid4()),
        peak_weekly_miles=peak_mpw,
        peak_monthly_miles=peak_mpw * 4.3,
        peak_long_run_miles=22.0,
        peak_mp_long_run_miles=18.0,
        peak_threshold_miles=9.0,
        peak_ctl=84.0,
        race_performances=[race_10k, race_marathon],
        best_rpi=52.0,
        best_race=race_10k,
        current_weekly_miles=65.0,
        current_ctl=78.0,
        current_atl=68.0,
        weeks_since_peak=4,
        current_long_run_miles=20.0,
        average_long_run_miles=19.0,
        tau1=42.0,
        tau2=7.0,
        experience_level=ExperienceLevel.EXPERIENCED,
        constraint_type=ConstraintType.NONE,
        constraint_details=None,
        is_returning_from_break=False,
        typical_long_run_day=6,
        typical_quality_day=3,
        typical_rest_days=[0],
        weeks_to_80pct_ctl=1,
        weeks_to_race_ready=2,
        sustainable_peak_weekly=peak_mpw * 0.93,
        recent_quality_sessions_28d=7,
        recent_8w_median_weekly_miles=64.0,
        recent_16w_p90_weekly_miles=69.0,
        recent_8w_p75_long_run_miles=21.0,
        recent_16w_p50_long_run_miles=19.0,
        recent_16w_run_count=88,
        peak_confidence="high",
    )

SUB3_MARATHONER = {
    "label": "Sub-3 Aspirant (65 mpw, 38:30 10K, 2:58 marathon)",
    "notes": "Multiple race anchors. Serious mileage. Tests MP work density at high volume.",
    "make_bank": make_sub3_marathoner,
    "semi_custom": {
        "current_weekly_miles": 65.0,
        "days_per_week": 6,
        "recent_race_distance": "marathon",
        "recent_race_time_seconds": 10680,
    },
}


# ---------------------------------------------------------------------------
# Athlete 8 — High mileage competitive
# 72 mpw, 35:00 10K (RPI ~56). Near-elite training.
# ---------------------------------------------------------------------------
def make_high_mileage() -> FitnessBank:
    race_10k = _race("10k", 10000.0, 2100, 56.0)   # 35:00 10K
    peak_mpw = 80.0
    return FitnessBank(
        athlete_id=str(uuid4()),
        peak_weekly_miles=peak_mpw,
        peak_monthly_miles=peak_mpw * 4.4,
        peak_long_run_miles=24.0,
        peak_mp_long_run_miles=18.0,
        peak_threshold_miles=12.0,
        peak_ctl=96.0,
        race_performances=[race_10k],
        best_rpi=56.0,
        best_race=race_10k,
        current_weekly_miles=72.0,
        current_ctl=86.0,
        current_atl=76.0,
        weeks_since_peak=3,
        current_long_run_miles=22.0,
        average_long_run_miles=21.0,
        tau1=44.0,
        tau2=7.0,
        experience_level=ExperienceLevel.ELITE,
        constraint_type=ConstraintType.NONE,
        constraint_details=None,
        is_returning_from_break=False,
        typical_long_run_day=6,
        typical_quality_day=3,
        typical_rest_days=[0],
        weeks_to_80pct_ctl=1,
        weeks_to_race_ready=2,
        sustainable_peak_weekly=peak_mpw * 0.95,
        recent_quality_sessions_28d=8,
        recent_8w_median_weekly_miles=74.0,
        recent_16w_p90_weekly_miles=79.0,
        recent_8w_p75_long_run_miles=23.0,
        recent_16w_p50_long_run_miles=21.0,
        recent_16w_run_count=100,
        peak_confidence="high",
    )

HIGH_MILEAGE = {
    "label": "High Mileage (72 mpw, 35:00 10K, RPI ~56)",
    "notes": "Near-elite. Tests high-volume long run floors and threshold density.",
    "make_bank": make_high_mileage,
    "semi_custom": {
        "current_weekly_miles": 72.0,
        "days_per_week": 6,
        "recent_race_distance": "10k",
        "recent_race_time_seconds": 2100,
    },
}


# ---------------------------------------------------------------------------
# Athlete 9 — Ultra/high-mileage marathon specialist
# 85 mpw, 32:00 10K (RPI ~59), 2:30 marathon target.
# ---------------------------------------------------------------------------
def make_elite_adjacent() -> FitnessBank:
    race_10k = _race("10k", 10000.0, 1920, 59.0)   # 32:00 10K
    race_marathon = _race("marathon", 42195.0, 9000, 58.5)  # 2:30 marathon
    peak_mpw = 95.0
    return FitnessBank(
        athlete_id=str(uuid4()),
        peak_weekly_miles=peak_mpw,
        peak_monthly_miles=peak_mpw * 4.5,
        peak_long_run_miles=24.0,
        peak_mp_long_run_miles=20.0,
        peak_threshold_miles=14.0,
        peak_ctl=114.0,
        race_performances=[race_10k, race_marathon],
        best_rpi=59.0,
        best_race=race_10k,
        current_weekly_miles=85.0,
        current_ctl=102.0,
        current_atl=90.0,
        weeks_since_peak=3,
        current_long_run_miles=22.0,
        average_long_run_miles=22.0,
        tau1=46.0,
        tau2=7.0,
        experience_level=ExperienceLevel.ELITE,
        constraint_type=ConstraintType.NONE,
        constraint_details=None,
        is_returning_from_break=False,
        typical_long_run_day=6,
        typical_quality_day=3,
        typical_rest_days=[],   # No scheduled rest days
        weeks_to_80pct_ctl=1,
        weeks_to_race_ready=1,
        sustainable_peak_weekly=peak_mpw * 0.96,
        recent_quality_sessions_28d=10,
        recent_8w_median_weekly_miles=87.0,
        recent_16w_p90_weekly_miles=93.0,
        recent_8w_p75_long_run_miles=23.0,
        recent_16w_p50_long_run_miles=22.0,
        recent_16w_run_count=112,
        peak_confidence="high",
    )

ELITE_ADJACENT = {
    "label": "Elite Adjacent (85 mpw, 32:00 10K, 2:30 marathon)",
    "notes": "No scheduled rest days. Tests plan ceiling and long run hard cap behavior.",
    "make_bank": make_elite_adjacent,
    "semi_custom": {
        "current_weekly_miles": 85.0,
        "days_per_week": 7,
        "recent_race_distance": "marathon",
        "recent_race_time_seconds": 9000,
    },
}


# ---------------------------------------------------------------------------
# Athlete 10 — Age group winner with declining mileage
# Was 70 mpw in prime, now 40 mpw at age 60. 43:00 10K (RPI ~48).
# Tests the "history > current" logic — long run floor from peak history.
# ---------------------------------------------------------------------------
def make_declining_masters() -> FitnessBank:
    race_10k = _race("10k", 10000.0, 2580, 48.0)   # 43:00 10K
    peak_mpw = 70.0
    current_mpw = 42.0
    return FitnessBank(
        athlete_id=str(uuid4()),
        peak_weekly_miles=peak_mpw,
        peak_monthly_miles=peak_mpw * 4.2,
        peak_long_run_miles=20.0,
        peak_mp_long_run_miles=14.0,
        peak_threshold_miles=8.0,
        peak_ctl=84.0,
        race_performances=[race_10k],
        best_rpi=48.0,
        best_race=race_10k,
        current_weekly_miles=current_mpw,
        current_ctl=50.0,
        current_atl=42.0,
        weeks_since_peak=52,   # Peak was a year ago
        current_long_run_miles=14.0,
        average_long_run_miles=13.0,
        tau1=44.0,
        tau2=9.0,   # Longer fatigue window for older athlete
        experience_level=ExperienceLevel.EXPERIENCED,
        constraint_type=ConstraintType.NONE,
        constraint_details=None,
        is_returning_from_break=False,
        typical_long_run_day=6,
        typical_quality_day=3,
        typical_rest_days=[0, 3],   # Two rest days
        weeks_to_80pct_ctl=3,
        weeks_to_race_ready=6,
        sustainable_peak_weekly=current_mpw * 0.95,
        recent_quality_sessions_28d=3,
        recent_8w_median_weekly_miles=41.0,
        recent_16w_p90_weekly_miles=50.0,
        recent_8w_p75_long_run_miles=15.0,
        recent_16w_p50_long_run_miles=13.0,
        recent_16w_run_count=48,
        peak_confidence="moderate",
    )

DECLINING_MASTERS = {
    "label": "Declining Masters (42 mpw, was 70, 43:00 10K, age ~60)",
    "notes": "Large gap between peak history and current volume. Tests L30 floor vs current mpw.",
    "make_bank": make_declining_masters,
    "semi_custom": {
        "current_weekly_miles": 42.0,
        "days_per_week": 5,
        "recent_race_distance": "10k",
        "recent_race_time_seconds": 2580,
    },
}


# ---------------------------------------------------------------------------
# All athletes in order (used by tests and report script)
# ---------------------------------------------------------------------------
ALL_ATHLETES = [
    BEGINNER,
    RECREATIONAL,
    COMEBACK,
    CONSISTENT_MID,
    MASTERS,
    FOUNDER_MIRROR,
    SUB3_MARATHONER,
    HIGH_MILEAGE,
    ELITE_ADJACENT,
    DECLINING_MASTERS,
]
