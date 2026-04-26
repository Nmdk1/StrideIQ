"""
Plan Engine V2 — data models.

All V2-specific dataclasses live here.  These are internal to the V2
engine and never written to the DB directly — they serialize to JSON
inside plan_preview.plan_json.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional


# ── Pace Ladder ──────────────────────────────────────────────────────

@dataclass
class PaceLadder:
    """Full percentage-based pace ladder for one athlete.

    Every value is seconds-per-km.  Named Daniels zones are pinned
    from calculate_paces_from_rpi(); intermediate rungs are derived
    from the anchor pace (MP or 5K depending on mode/phase).
    """

    paces: Dict[int, float]
    # key = percentage of anchor pace
    #   (75, 80, 85, 90, 92, 94, 95, 96, 100, 103, 105, 108, 110, 115, 120)
    # value = pace in seconds per km

    anchor_pace_sec_per_km: float
    anchor_type: str  # "marathon" | "5k"

    # Named Daniels zone paces (always from calculate_paces_from_rpi)
    easy: float
    long: float
    marathon: float
    threshold: float
    interval: float
    repetition: float
    recovery: float

    def pace_for_pct(self, pct: int) -> float:
        """Return pace in sec/km for a given percentage rung."""
        if pct in self.paces:
            return self.paces[pct]
        # Linear interpolation between nearest known rungs
        rungs = sorted(self.paces.keys())
        if pct <= rungs[0]:
            return self.paces[rungs[0]]
        if pct >= rungs[-1]:
            return self.paces[rungs[-1]]
        for i in range(len(rungs) - 1):
            if rungs[i] <= pct <= rungs[i + 1]:
                lo, hi = rungs[i], rungs[i + 1]
                ratio = (pct - lo) / (hi - lo)
                return self.paces[lo] + ratio * (self.paces[hi] - self.paces[lo])
        return self.anchor_pace_sec_per_km  # fallback


# ── Segments ─────────────────────────────────────────────────────────

VALID_SEGMENT_TYPES = frozenset({
    "warmup", "cooldown", "work", "float", "jog_rest",
    "easy", "threshold", "interval", "stride", "steady",
    "hike", "fatigue_resistance", "uphill_tm", "race",
})


@dataclass
class WorkoutSegment:
    """Unified segment schema — matches Algorithm Spec §5."""

    type: str
    pace_pct_mp: int
    pace_sec_per_km: float
    description: str

    distance_km: Optional[float] = None
    duration_min: Optional[float] = None
    reps: Optional[int] = None
    rest_min: Optional[float] = None
    grade_pct: Optional[float] = None
    fueling_target_g_per_hr: Optional[int] = None

    def __post_init__(self):
        if self.type not in VALID_SEGMENT_TYPES:
            raise ValueError(f"Invalid segment type: {self.type!r}")

    def to_dict(self, units: str = "imperial") -> dict:
        from .units import dist_value, pace as fmt_pace

        d: dict = {
            "type": self.type,
            "pace_pct_mp": self.pace_pct_mp,
            "pace": fmt_pace(self.pace_sec_per_km, units),
            "description": self.description,
        }
        if self.distance_km is not None:
            d["distance"] = dist_value(self.distance_km, units)
        if self.duration_min is not None:
            d["duration_min"] = round(self.duration_min, 1)
        if self.reps is not None:
            d["reps"] = self.reps
        if self.rest_min is not None:
            d["rest_min"] = round(self.rest_min, 1)
        if self.grade_pct is not None:
            d["grade_pct"] = round(self.grade_pct, 1)
        if self.fueling_target_g_per_hr is not None:
            d["fueling_target_g_per_hr"] = self.fueling_target_g_per_hr
        return d


# ── Phase / Periodization ───────────────────────────────────────────

VALID_PHASE_NAMES = frozenset({
    "general", "supportive", "specific", "taper",
    "build", "build_volume", "onramp", "maintain",
})


@dataclass
class Phase:
    name: str
    weeks: int
    focus: str
    quality_density: int  # quality sessions per week (0-2)
    workout_pool: List[str] = field(default_factory=list)

    def __post_init__(self):
        if self.name not in VALID_PHASE_NAMES:
            raise ValueError(f"Invalid phase name: {self.name!r}")


@dataclass
class PhaseStructure:
    phases: List[Phase]
    total_weeks: int
    mode: str  # race, build_onramp, build_volume, build_intensity, maintain


# ── Tune-Up Races ────────────────────────────────────────────────────

@dataclass
class TuneUpRace:
    """A secondary race scheduled during the training plan."""
    race_date: date
    distance: str       # "5K", "10K", "half_marathon", etc.
    name: str           # "Brooklyn Half", "Turkey Trot 10K"
    purpose: str = "sharpening"  # "sharpening" | "threshold" | "confidence"

    _DISTANCE_KM = {
        "5K": 5.0, "5k": 5.0,
        "10K": 10.0, "10k": 10.0,
        "10_mile": 16.09, "10 mile": 16.09,
        "half_marathon": 21.1, "half": 21.1,
        "marathon": 42.2,
    }

    @property
    def distance_km(self) -> float:
        return self._DISTANCE_KM.get(self.distance, 16.09)


# ── Fueling ──────────────────────────────────────────────────────────

@dataclass
class FuelingPlan:
    during_run_carbs_g_per_hr: int
    notes: str


# ── Progression ──────────────────────────────────────────────────────

@dataclass
class WorkoutProgression:
    """Tracks extension state within a block for build-over-build."""
    workout_key: str
    current_duration_min: float = 0.0
    current_distance_km: float = 0.0
    current_reps: int = 0
    pace_sec_per_km: float = 0.0
    block_number: int = 1


# ── Plan Output ──────────────────────────────────────────────────────

@dataclass
class V2DayPlan:
    """A single day's workout in a V2 plan."""
    day_of_week: int  # 0=Mon, 6=Sun
    workout_type: str
    title: str
    description: str
    phase: str
    segments: Optional[List[WorkoutSegment]] = None
    target_distance_km: Optional[float] = None
    distance_range_km: Optional[tuple] = None  # (min, max) km for easy/long
    duration_range_min: Optional[tuple] = None  # (min, max) minutes for onramp
    fueling: Optional[FuelingPlan] = None

    def to_dict(self, units: str = "imperial") -> dict:
        from .units import dist_range_tuple, dist_value, localize_text, unit_label

        d: dict = {
            "day_of_week": self.day_of_week,
            "workout_type": self.workout_type,
            "title": localize_text(self.title, units),
            "description": localize_text(self.description, units),
            "phase": self.phase,
            "units": units,
        }
        if self.segments:
            d["segments"] = [s.to_dict(units=units) for s in self.segments]
        if self.target_distance_km is not None:
            d["target_distance"] = dist_value(self.target_distance_km, units)
        if self.distance_range_km is not None:
            lo, hi = dist_range_tuple(
                self.distance_range_km[0], self.distance_range_km[1], units,
            )
            d["distance_range"] = {"min": lo, "max": hi, "unit": unit_label(units)}
        if self.duration_range_min is not None:
            d["duration_range_min"] = {
                "min": round(self.duration_range_min[0], 0),
                "max": round(self.duration_range_min[1], 0),
            }
        if self.fueling:
            d["fueling"] = {
                "carbs_g_per_hr": self.fueling.during_run_carbs_g_per_hr,
                "notes": self.fueling.notes,
            }
        return d


@dataclass
class V2WeekPlan:
    week_number: int
    phase: str
    days: List[V2DayPlan]
    is_cutback: bool = False

    def to_dict(self, units: str = "imperial") -> dict:
        return {
            "week_number": self.week_number,
            "phase": self.phase,
            "days": [d.to_dict(units=units) for d in self.days],
            "is_cutback": self.is_cutback,
        }


@dataclass
class V2PlanPreview:
    """Complete V2 plan output — serializable to plan_preview.plan_json."""
    mode: str
    goal_event: Optional[str]
    total_weeks: int
    weeks: List[V2WeekPlan]
    pace_ladder: Dict[int, float]
    anchor_type: str
    athlete_type: str  # "endurance" | "balanced" | "speed"
    phase_structure: List[dict]
    units: str = "imperial"
    peak_workout_state: Optional[dict] = None
    block_number: int = 1
    quality_gate_passed: bool = False
    quality_gate_details: Optional[dict] = None

    def to_dict(self, units: Optional[str] = None) -> dict:
        from .units import pace as fmt_pace

        u = units or self.units

        ladder_display = {}
        for k, v in self.pace_ladder.items():
            ladder_display[str(k)] = fmt_pace(v, u)

        return {
            "mode": self.mode,
            "goal_event": self.goal_event,
            "total_weeks": self.total_weeks,
            "units": u,
            "weeks": [w.to_dict(units=u) for w in self.weeks],
            "pace_ladder": ladder_display,
            "anchor_type": self.anchor_type,
            "athlete_type": self.athlete_type,
            "phase_structure": self.phase_structure,
            "peak_workout_state": self.peak_workout_state,
            "block_number": self.block_number,
            "quality_gate_passed": self.quality_gate_passed,
            "quality_gate_details": self.quality_gate_details,
        }
