"""
Athlete Plan Profile — N=1 Override System (Phase 1C)

Stateless derivation service that reads athlete activity history and produces
an AthleteProfile dataclass.  The profile is computed on demand, deterministic
for a given history snapshot, and every field carries an explicit confidence
and source annotation.

ADR: docs/ADR_061_ATHLETE_PLAN_PROFILE.md

Key design decisions:
- Long runs are identified by DURATION (moving_time >= 105 min), not distance.
  Duration is the physiological gate; distance is the prescription unit.
- Confidence scores gate overrides: the generator uses N=1 values only when
  confidence >= 0.6; otherwise it falls back to tier defaults.
- Cold start IS a template, and the system says so via disclosures.
"""

import logging
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from services.plan_framework.constants import (
    CUTBACK_RULES,
    LONG_RUN_PEAKS,
    VOLUME_TIER_THRESHOLDS,
    Distance,
    VolumeTier,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# The physiological threshold where glycogen depletion drives long-run-specific
# adaptations: mitochondrial biogenesis, fat oxidation, capillarization.
# See ADR-061 Question 1 for the science.
LONG_RUN_DURATION_THRESHOLD_MIN = 105

# Data sufficiency thresholds
RICH_WEEKS = 12
RICH_RUNS = 40
ADEQUATE_WEEKS = 8
ADEQUATE_RUNS = 25
THIN_WEEKS = 4
THIN_RUNS = 12

# Gap detection: consecutive days with no run activities = injury/break
GAP_THRESHOLD_DAYS = 28

# Quality workout types (from workout_classifier)
QUALITY_TYPES = {
    "tempo_run", "tempo_intervals", "threshold",
    "vo2max_intervals", "interval", "intervals",
    "marathon_pace", "fartlek",
}


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------

@dataclass
class AthleteProfile:
    """N=1 training parameters derived from activity history."""

    # --- Volume ---
    volume_tier: VolumeTier
    current_weekly_miles: float
    peak_weekly_miles: float
    volume_trend: str                      # "building" | "maintaining" | "declining"
    volume_confidence: float               # 0.0–1.0

    # --- Long Run (duration-gated: moving_time >= 105 min) ---
    long_run_baseline_minutes: float
    long_run_baseline_miles: float
    long_run_max_minutes: float
    long_run_max_miles: float
    long_run_frequency: float              # Long runs per week (e.g., 0.85)
    long_run_typical_pace_per_mile: float  # Median pace of long runs (min/mi)
    long_run_confidence: float             # 0.0–1.0
    long_run_source: str                   # "history" | "tier_default"

    # --- Recovery ---
    recovery_half_life_hours: float
    recovery_confidence: float
    suggested_cutback_frequency: int       # 3, 4, or 5 weeks

    # --- Quality Tolerance ---
    quality_sessions_per_week: float
    handles_back_to_back_quality: bool
    quality_confidence: float

    # --- Metadata ---
    weeks_of_data: int
    data_sufficiency: str                  # "rich" | "adequate" | "thin" | "cold_start"
    staleness_days: int
    disclosures: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class AthletePlanProfileService:
    """Derives N=1 training parameters from activity history.

    This service is stateless — no DB writes, no side effects.
    Deterministic for a given history snapshot.  Safe to call repeatedly.

    Two entry points:
    - derive_profile()         — reads from DB by athlete_id
    - derive_profile_from_activities() — accepts a pre-loaded list (for tests)
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def derive_profile(
        self,
        athlete_id,
        db,
        goal_distance: str,
    ) -> AthleteProfile:
        """Compute profile from DB activity history."""
        from models import Activity

        cutoff = datetime.now(timezone.utc) - timedelta(weeks=18)
        activities = (
            db.query(Activity)
            .filter(
                Activity.athlete_id == athlete_id,
                Activity.start_time >= cutoff,
                Activity.distance_m >= 500,   # exclude noise
            )
            .order_by(Activity.start_time.desc())
            .all()
        )

        return self.derive_profile_from_activities(activities, goal_distance)

    def derive_profile_from_activities(
        self,
        activities: List[Any],
        goal_distance: str,
    ) -> AthleteProfile:
        """Compute profile from a list of Activity-like objects."""

        # 1. Filter to runs only
        runs = self._filter_runs(activities)

        # 2. Select analysis window (handles gaps, tapers)
        window, disclosures = self._get_analysis_window(runs)

        # 3. Data sufficiency
        sufficiency = self._classify_sufficiency(window)
        weeks = self._count_weeks(window)

        # 4. Derive each domain
        vol = self._derive_volume(window, goal_distance)
        lr = self._derive_long_run(window, weeks_of_data=weeks)
        rec = self._derive_recovery(window)
        qt = self._derive_quality_tolerance(window, weeks_of_data=weeks)

        # 5. Staleness
        staleness = 0
        if window:
            most_recent = max(a.start_time for a in window)
            if most_recent.tzinfo is None:
                most_recent = most_recent.replace(tzinfo=timezone.utc)
            staleness = (datetime.now(timezone.utc) - most_recent).days

        # 6. Build disclosures based on sufficiency and confidence
        disclosures = list(disclosures)  # copy
        if sufficiency == "cold_start":
            disclosures.append(
                "I don't have enough training history to personalize yet. "
                "I'm using estimated defaults based on your reported mileage. "
                "Connect Strava or log 4+ weeks of runs for a personalized plan."
            )
        elif sufficiency == "thin":
            disclosures.append(
                f"I have {weeks} weeks of training data. Volume and long run "
                "targets are preliminary — I'll adjust as I learn your patterns."
            )
        elif sufficiency == "adequate":
            if rec["confidence"] < 0.5 or qt["confidence"] < 0.5:
                disclosures.append(
                    "Recovery speed and quality tolerance are estimated from "
                    "limited data. These will refine over the next 4 weeks."
                )

        if lr["source"] == "tier_default" and sufficiency != "cold_start":
            disclosures.append(
                "None of your recent runs exceed 1:45 — you haven't been doing "
                f"long runs. Your plan includes them to build the aerobic base "
                f"for {goal_distance.replace('_', ' ')}."
            )

        return AthleteProfile(
            # Volume
            volume_tier=vol["tier"],
            current_weekly_miles=vol["current_weekly_miles"],
            peak_weekly_miles=vol["peak_weekly_miles"],
            volume_trend=vol["trend"],
            volume_confidence=vol["confidence"],
            # Long run
            long_run_baseline_minutes=lr["baseline_minutes"],
            long_run_baseline_miles=lr["baseline_miles"],
            long_run_max_minutes=lr["max_minutes"],
            long_run_max_miles=lr["max_miles"],
            long_run_frequency=lr["frequency"],
            long_run_typical_pace_per_mile=lr["typical_pace"],
            long_run_confidence=lr["confidence"],
            long_run_source=lr["source"],
            # Recovery
            recovery_half_life_hours=rec["half_life"],
            recovery_confidence=rec["confidence"],
            suggested_cutback_frequency=rec["cutback_frequency"],
            # Quality
            quality_sessions_per_week=qt["sessions_per_week"],
            handles_back_to_back_quality=qt["back_to_back"],
            quality_confidence=qt["confidence"],
            # Metadata
            weeks_of_data=weeks,
            data_sufficiency=sufficiency,
            staleness_days=staleness,
            disclosures=disclosures,
        )

    # ------------------------------------------------------------------
    # Filtering
    # ------------------------------------------------------------------

    @staticmethod
    def _filter_runs(activities: List[Any]) -> List[Any]:
        """Keep only running activities."""
        return [a for a in activities if getattr(a, "sport", "run") == "run"]

    # ------------------------------------------------------------------
    # Analysis Window (gap detection, taper handling)
    # ------------------------------------------------------------------

    def _get_analysis_window(
        self, activities: List[Any]
    ) -> Tuple[List[Any], List[str]]:
        """Select the relevant analysis window.

        Handles:
        - Injury/break gaps (> 28 days): use only post-gap data
        - Recent race/taper: extend window backward to capture pre-taper
        """
        disclosures: List[str] = []

        if not activities:
            return [], disclosures

        # Sort by start_time descending (most recent first)
        sorted_acts = sorted(
            activities,
            key=lambda a: a.start_time,
            reverse=True,
        )

        # --- Gap detection ---
        # Walk backward through sorted activities looking for gaps > 28 days
        gap_index = None
        for i in range(len(sorted_acts) - 1):
            current_time = sorted_acts[i].start_time
            next_time = sorted_acts[i + 1].start_time
            # Make timezone-aware for comparison
            if current_time.tzinfo is None:
                current_time = current_time.replace(tzinfo=timezone.utc)
            if next_time.tzinfo is None:
                next_time = next_time.replace(tzinfo=timezone.utc)
            gap_days = (current_time - next_time).days
            if gap_days >= GAP_THRESHOLD_DAYS:
                gap_index = i
                gap_weeks = gap_days // 7
                post_gap_acts = sorted_acts[:i + 1]
                post_gap_weeks = self._count_weeks(post_gap_acts)
                disclosures.append(
                    f"You appear to be returning from a {gap_weeks}-week break. "
                    f"Your plan is based on your recent {post_gap_weeks} weeks "
                    f"of training, not your pre-break volume. As you rebuild, "
                    f"targets will adjust upward."
                )
                sorted_acts = post_gap_acts
                break

        # --- Recent race / taper detection ---
        now = datetime.now(timezone.utc)
        recent_race = any(
            getattr(a, "is_race_candidate", False) or
            getattr(a, "user_verified_race", False)
            for a in sorted_acts
            if (now - (a.start_time.replace(tzinfo=timezone.utc)
                       if a.start_time.tzinfo is None else a.start_time)).days <= 21
        )

        if recent_race and gap_index is None:
            # Extend window to 18 weeks to capture pre-taper training.
            # Always apply the wider window and disclosure when a race is
            # detected — even if most data is already within 12 weeks,
            # taper-reduced volume should not pull down baselines.
            #
            # NOTE: If both a 28+ day gap AND a recent race exist, gap
            # handling takes priority and this block is skipped.  This is
            # correct: an athlete who returned from a 6-week injury, trained
            # for 3 weeks, then raced should be profiled on their post-gap
            # data only.  3 weeks of post-injury data is a thin profile
            # regardless of what happened before — and extending backward
            # past the gap would re-include stale pre-injury data that no
            # longer reflects current capacity.
            cutoff = now - timedelta(weeks=18)
            sorted_acts = sorted(
                [a for a in activities
                 if (a.start_time.replace(tzinfo=timezone.utc)
                     if a.start_time.tzinfo is None else a.start_time) >= cutoff],
                key=lambda a: a.start_time,
                reverse=True,
            )
            disclosures.append(
                "Your recent taper/race period is excluded from baseline "
                "calculations. Targets reflect your pre-taper training capacity."
            )

        # Default: last 12 weeks
        if gap_index is None and not recent_race:
            cutoff = now - timedelta(weeks=12)
            sorted_acts = [
                a for a in sorted_acts
                if (a.start_time.replace(tzinfo=timezone.utc)
                    if a.start_time.tzinfo is None else a.start_time) >= cutoff
            ]

        return sorted_acts, disclosures

    # ------------------------------------------------------------------
    # Data Sufficiency
    # ------------------------------------------------------------------

    def _classify_sufficiency(self, activities: List[Any]) -> str:
        """Classify data sufficiency: rich, adequate, thin, cold_start."""
        weeks = self._count_weeks(activities)
        runs = len(activities)

        if weeks >= RICH_WEEKS and runs >= RICH_RUNS:
            return "rich"
        if weeks >= ADEQUATE_WEEKS and runs >= ADEQUATE_RUNS:
            return "adequate"
        if weeks >= THIN_WEEKS and runs >= THIN_RUNS:
            return "thin"
        return "cold_start"

    @staticmethod
    def _count_weeks(activities: List[Any]) -> int:
        """Count distinct ISO weeks with at least one activity."""
        if not activities:
            return 0
        weeks = set()
        for a in activities:
            t = a.start_time
            if t.tzinfo is None:
                t = t.replace(tzinfo=timezone.utc)
            weeks.add(t.isocalendar()[:2])  # (year, week)
        return len(weeks)

    # ------------------------------------------------------------------
    # Long Run Derivation (Duration-Gated)
    # ------------------------------------------------------------------

    def _identify_long_runs(self, activities: List[Any]) -> List[Any]:
        """Identify long runs: moving_time >= 105 minutes.

        duration_s on the Activity model IS Strava's moving_time
        (see strava_index.py / strava_ingest.py).
        """
        long_runs = []
        for a in activities:
            if getattr(a, "sport", "run") != "run":
                continue
            duration_min = (getattr(a, "duration_s", 0) or 0) / 60.0
            if duration_min >= LONG_RUN_DURATION_THRESHOLD_MIN:
                long_runs.append(a)
        return long_runs

    def _derive_long_run(
        self, activities: List[Any], weeks_of_data: int
    ) -> Dict[str, Any]:
        """Derive long run baseline from duration-gated identification."""
        long_runs = self._identify_long_runs(activities)

        if not long_runs:
            return {
                "baseline_minutes": 0.0,
                "baseline_miles": 0.0,
                "max_minutes": 0.0,
                "max_miles": 0.0,
                "frequency": 0.0,
                "typical_pace": 0.0,
                "confidence": 0.0,
                "source": "tier_default",
            }

        # Sort by date (most recent first) and take last 8
        long_runs_sorted = sorted(
            long_runs, key=lambda a: a.start_time, reverse=True
        )[:8]

        durations = [(a.duration_s or 0) / 60.0 for a in long_runs_sorted]
        distances = [(a.distance_m or 0) / 1609.344 for a in long_runs_sorted]

        baseline_min = statistics.median(durations)
        baseline_mi = statistics.median(distances)
        max_min = max(durations)
        max_mi = max(distances)

        # Typical pace: median of per-run paces
        paces = []
        for a in long_runs_sorted:
            d_mi = (a.distance_m or 0) / 1609.344
            d_min = (a.duration_s or 0) / 60.0
            if d_mi > 0:
                paces.append(d_min / d_mi)
        typical_pace = statistics.median(paces) if paces else 0.0

        # Frequency: long runs per week
        frequency = len(long_runs) / max(weeks_of_data, 1)

        # Confidence: based on number of identified long runs
        if len(long_runs) >= 8:
            confidence = min(1.0, 0.6 + (len(long_runs) - 8) * 0.05)
        elif len(long_runs) >= 4:
            confidence = 0.3 + (len(long_runs) - 4) * 0.075
        else:
            confidence = len(long_runs) * 0.1

        return {
            "baseline_minutes": round(baseline_min, 1),
            "baseline_miles": round(baseline_mi, 1),
            "max_minutes": round(max_min, 1),
            "max_miles": round(max_mi, 1),
            "frequency": round(frequency, 2),
            "typical_pace": round(typical_pace, 1),
            "confidence": round(min(confidence, 1.0), 2),
            "source": "history",
        }

    # ------------------------------------------------------------------
    # Volume Derivation
    # ------------------------------------------------------------------

    def _derive_volume(
        self, activities: List[Any], goal_distance: str
    ) -> Dict[str, Any]:
        """Derive volume tier, current, peak, trend, confidence."""
        if not activities:
            return {
                "tier": VolumeTier.BUILDER,
                "current_weekly_miles": 0.0,
                "peak_weekly_miles": 0.0,
                "trend": "maintaining",
                "confidence": 0.0,
            }

        # Group by ISO week
        weekly_miles: Dict[Tuple, float] = {}
        for a in activities:
            t = a.start_time
            if t.tzinfo is None:
                t = t.replace(tzinfo=timezone.utc)
            week_key = t.isocalendar()[:2]
            miles = (getattr(a, "distance_m", 0) or 0) / 1609.344
            weekly_miles[week_key] = weekly_miles.get(week_key, 0) + miles

        if not weekly_miles:
            return {
                "tier": VolumeTier.BUILDER,
                "current_weekly_miles": 0.0,
                "peak_weekly_miles": 0.0,
                "trend": "maintaining",
                "confidence": 0.0,
            }

        # Sort weeks by (year, week) and get values
        sorted_weeks = sorted(weekly_miles.keys())
        volumes = [weekly_miles[k] for k in sorted_weeks]

        # Current = trailing 4-week average (or median of non-zero for sparse data)
        recent_4 = volumes[-4:] if len(volumes) >= 4 else volumes
        non_zero = [v for v in recent_4 if v > 0]
        current = statistics.median(non_zero) if non_zero else 0.0

        peak = max(volumes)

        # Trend: compare first half to second half
        if len(volumes) >= 4:
            first_half = statistics.median(volumes[:len(volumes) // 2])
            second_half = statistics.median(volumes[len(volumes) // 2:])
            ratio = second_half / first_half if first_half > 0 else 1.0
            if ratio > 1.10:
                trend = "building"
            elif ratio < 0.90:
                trend = "declining"
            else:
                trend = "maintaining"
        else:
            trend = "maintaining"

        # Classify tier
        tier = self._classify_tier(current, goal_distance)

        # Confidence: based on number of weeks
        n_weeks = len(volumes)
        if n_weeks >= 12:
            confidence = 0.9
        elif n_weeks >= 8:
            confidence = 0.7
        elif n_weeks >= 4:
            confidence = 0.5
        else:
            confidence = max(0.0, n_weeks * 0.15)

        return {
            "tier": tier,
            "current_weekly_miles": round(current, 1),
            "peak_weekly_miles": round(peak, 1),
            "trend": trend,
            "confidence": round(confidence, 2),
        }

    @staticmethod
    def _classify_tier(weekly_miles: float, goal_distance: str) -> VolumeTier:
        """Classify volume tier from weekly miles and goal distance."""
        try:
            dist = Distance(goal_distance)
        except ValueError:
            dist = Distance.MARATHON

        thresholds = VOLUME_TIER_THRESHOLDS.get(dist, {})

        # Walk tiers from highest to lowest
        for tier in [VolumeTier.ELITE, VolumeTier.HIGH, VolumeTier.MID,
                     VolumeTier.LOW, VolumeTier.BUILDER]:
            if tier not in thresholds:
                continue
            if weekly_miles >= thresholds[tier]["min"]:
                return tier

        return VolumeTier.BUILDER

    # ------------------------------------------------------------------
    # Recovery Derivation
    # ------------------------------------------------------------------

    def _derive_recovery(self, activities: List[Any]) -> Dict[str, Any]:
        """Derive recovery half-life and cutback frequency."""
        if len(activities) < 10:
            return {
                "half_life": 48.0,  # default
                "confidence": 0.0,
                "cutback_frequency": 4,
            }

        # Use performance_engine's recovery calculation via activity dicts
        try:
            from services.performance_engine import calculate_recovery_half_life
            activity_dicts = [
                {
                    "start_time": a.start_time,
                    "avg_hr": getattr(a, "avg_hr", None),
                    "max_hr": getattr(a, "max_hr", None),
                    "is_race_candidate": getattr(a, "is_race_candidate", False),
                    "performance_percentage": getattr(a, "performance_percentage", None),
                }
                for a in activities
            ]
            half_life = calculate_recovery_half_life(activity_dicts, lookback_days=60)
        except Exception:
            half_life = None

        if half_life is None:
            return {
                "half_life": 48.0,
                "confidence": 0.2,
                "cutback_frequency": 4,
            }

        cutback_freq = self._map_half_life_to_cutback(half_life)
        confidence = min(0.8, len(activities) / 50.0)

        return {
            "half_life": round(half_life, 1),
            "confidence": round(confidence, 2),
            "cutback_frequency": cutback_freq,
        }

    @staticmethod
    def _map_half_life_to_cutback(half_life: float) -> int:
        """Map recovery half-life (hours) to cutback frequency (weeks).

        Faster recovery → can go longer between cutbacks.
        ≤36h  → every 5 weeks (fast recoverer)
        ≤60h  → every 4 weeks (normal)
        >60h  → every 3 weeks (slow recoverer / masters)
        """
        if half_life <= 36:
            return 5
        elif half_life <= 60:
            return 4
        else:
            return 3

    # ------------------------------------------------------------------
    # Quality Tolerance Derivation
    # ------------------------------------------------------------------

    def _derive_quality_tolerance(
        self, activities: List[Any], weeks_of_data: int
    ) -> Dict[str, Any]:
        """Derive quality sessions per week and back-to-back handling."""
        if not activities or weeks_of_data == 0:
            return {
                "sessions_per_week": 0.0,
                "back_to_back": False,
                "confidence": 0.0,
            }

        # Count quality sessions
        quality_sessions = [
            a for a in activities
            if getattr(a, "workout_type", None) in QUALITY_TYPES
        ]

        sessions_per_week = len(quality_sessions) / max(weeks_of_data, 1)

        # Check for back-to-back quality days
        back_to_back = False
        if len(quality_sessions) >= 2:
            sorted_quality = sorted(quality_sessions, key=lambda a: a.start_time)
            for i in range(len(sorted_quality) - 1):
                t1 = sorted_quality[i].start_time
                t2 = sorted_quality[i + 1].start_time
                if t1.tzinfo is None:
                    t1 = t1.replace(tzinfo=timezone.utc)
                if t2.tzinfo is None:
                    t2 = t2.replace(tzinfo=timezone.utc)
                if (t2 - t1).days <= 1:
                    back_to_back = True
                    break

        # Confidence
        if len(quality_sessions) >= 10 and weeks_of_data >= 8:
            confidence = 0.8
        elif len(quality_sessions) >= 5:
            confidence = 0.5
        elif len(quality_sessions) >= 2:
            confidence = 0.3
        else:
            confidence = 0.1

        return {
            "sessions_per_week": round(sessions_per_week, 2),
            "back_to_back": back_to_back,
            "confidence": round(confidence, 2),
        }
