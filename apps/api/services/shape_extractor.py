"""Activity Shape Extractor — Living Fingerprint Capability 2.

Transforms per-second stream data into a structured RunShape:
  phases (sustained effort segments with zone classification),
  accelerations (short bursts within phases),
  and a shape summary (queryable properties for investigations).

The shape describes the structure of the run. Classification is
an optional label derived from that structure.

Design:
  - Pure computation: no DB, no IO
  - Requires training zones for zone classification (falls back to
    stream-relative percentiles if unavailable)
  - Operates on the same raw stream data as the existing Segment
    detection, computed in parallel (not derived from Segments)
"""
from __future__ import annotations

import logging
import math
import statistics
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

METERS_PER_MILE = 1609.34
MIN_PHASE_DURATION_S = 60
MIN_ACCELERATION_DURATION_S = 10
MAX_VELOCITY_MPS = 11.0  # 25 mph
STOPPED_VELOCITY_THRESHOLD = 0.5  # m/s


@dataclass
class PaceProfile:
    """Athlete's pace zones in seconds per mile. Used for zone classification."""
    easy_sec: int = 600
    marathon_sec: int = 480
    threshold_sec: int = 450
    interval_sec: int = 400
    repetition_sec: int = 360

    def classify_pace(self, pace_sec_per_mile: float) -> str:
        if pace_sec_per_mile <= 0:
            return 'stopped'
        rep_int = (self.repetition_sec + self.interval_sec) // 2
        int_thr = (self.interval_sec + self.threshold_sec) // 2
        thr_mar = (self.threshold_sec + self.marathon_sec) // 2
        mar_easy = (self.marathon_sec + self.easy_sec) // 2
        if pace_sec_per_mile <= rep_int:
            return 'repetition'
        elif pace_sec_per_mile <= int_thr:
            return 'interval'
        elif pace_sec_per_mile <= thr_mar:
            return 'threshold'
        elif pace_sec_per_mile <= mar_easy:
            return 'marathon'
        else:
            return 'easy'

    def is_at_least_marathon(self, pace_sec_per_mile: float) -> bool:
        mar_easy = (self.marathon_sec + self.easy_sec) // 2
        return 0 < pace_sec_per_mile <= mar_easy

    def is_significant_acceleration(self, pace_sec_per_mile: float) -> bool:
        """True if pace is meaningfully faster than easy — at least 20% faster.
        Works for all athletes regardless of speed."""
        if pace_sec_per_mile <= 0:
            return False
        return pace_sec_per_mile < self.easy_sec * 0.85


@dataclass
class Acceleration:
    start_time_s: int
    end_time_s: int
    duration_s: int
    distance_m: float
    avg_pace_sec_per_mile: float
    avg_pace_heat_adjusted: Optional[float]
    pace_zone: str
    avg_hr: Optional[float]
    hr_delta: Optional[float]
    avg_cadence: Optional[float]
    cadence_delta: Optional[float]
    position_in_run: float
    recovery_after_s: Optional[int]

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Phase:
    start_time_s: int
    end_time_s: int
    duration_s: int
    distance_m: float
    avg_pace_sec_per_mile: float
    avg_pace_heat_adjusted: Optional[float]
    pace_zone: str
    avg_hr: Optional[float]
    avg_cadence: Optional[float]
    elevation_delta_m: float
    avg_grade: Optional[float]
    pace_cv: float
    phase_type: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ShapeSummary:
    total_phases: int
    acceleration_count: int
    acceleration_avg_duration_s: Optional[float]
    acceleration_avg_pace_zone: Optional[str]
    acceleration_clustering: str
    has_warmup: bool
    has_cooldown: bool
    pace_progression: str
    pace_range_sec_per_mile: float
    longest_sustained_effort_s: int
    longest_sustained_zone: str
    elevation_profile: str
    workout_classification: Optional[str]

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RunShape:
    phases: List[Phase]
    accelerations: List[Acceleration]
    summary: ShapeSummary

    def to_dict(self) -> dict:
        return {
            'phases': [p.to_dict() for p in self.phases],
            'accelerations': [a.to_dict() for a in self.accelerations],
            'summary': self.summary.to_dict(),
        }


def pace_profile_from_training_paces(paces_json: dict) -> Optional[PaceProfile]:
    """Build a PaceProfile from AthleteTrainingPaceProfile.paces JSONB."""
    raw = paces_json.get('_raw_seconds_per_mile')
    if raw:
        return PaceProfile(
            easy_sec=raw.get('easy_pace_low', 600),
            marathon_sec=raw.get('marathon_pace', 480),
            threshold_sec=raw.get('threshold_pace', 450),
            interval_sec=raw.get('interval_pace', 400),
            repetition_sec=raw.get('repetition_pace', 360),
        )
    return None


def pace_profile_from_rpi(rpi: float) -> Optional[PaceProfile]:
    """Derive a PaceProfile from athlete RPI using the training pace calculator."""
    if not rpi or rpi <= 0:
        return None
    try:
        from services.rpi_calculator import calculate_training_paces
        paces = calculate_training_paces(rpi)
        easy = paces.get('easy_pace_low')
        marathon = paces.get('marathon_pace')
        threshold = paces.get('threshold_pace')
        interval = paces.get('interval_pace')
        rep = paces.get('repetition_pace')
        if easy and threshold:
            return PaceProfile(
                easy_sec=int(easy),
                marathon_sec=int(marathon) if marathon else int(easy * 0.82),
                threshold_sec=int(threshold),
                interval_sec=int(interval) if interval else int(threshold * 0.88),
                repetition_sec=int(rep) if rep else int(threshold * 0.80),
            )
    except Exception:
        pass
    return None


def extract_shape(
    stream_data: Dict[str, List],
    pace_profile: Optional[PaceProfile] = None,
    heat_adjustment_pct: Optional[float] = None,
) -> Optional[RunShape]:
    """Extract the RunShape from per-second stream data.

    Args:
        stream_data: Dict mapping channel names to lists of per-second values.
            Required: 'time', 'velocity_smooth'
            Optional: 'heartrate', 'cadence', 'grade_smooth', 'altitude', 'distance'
        pace_profile: Athlete's training pace zones. Falls back to
            stream-relative percentiles if None.
        heat_adjustment_pct: If provided, computes heat-adjusted pace for each phase.

    Returns:
        RunShape or None if insufficient data.
    """
    time = stream_data.get('time')
    velocity = stream_data.get('velocity_smooth')

    if not time or not velocity or len(time) < 30:
        return None

    n = len(time)
    heartrate = stream_data.get('heartrate') or [None] * n
    cadence = stream_data.get('cadence') or [None] * n
    grade = stream_data.get('grade_smooth') or [None] * n
    altitude = stream_data.get('altitude') or [None] * n
    distance = stream_data.get('distance') or [None] * n

    if len(velocity) != n:
        return None

    heartrate = _pad(heartrate, n)
    cadence = _pad(cadence, n)
    grade = _pad(grade, n)
    altitude = _pad(altitude, n)
    distance = _pad(distance, n)

    if pace_profile is None:
        pace_profile = _derive_profile_from_stream(velocity)

    # Step 1: Smooth and compute per-point metrics
    # Heavy smoothing (30s) for stable phase detection
    phase_v = _rolling_mean(velocity, window=30)
    phase_v = _clamp_velocity(phase_v)
    phase_pace = _velocity_to_pace(phase_v)
    zone_per_point = [
        pace_profile.classify_pace(p) if p > 0 else 'stopped'
        for p in phase_pace
    ]
    zone_per_point = _stabilize_zones(zone_per_point, window=61)

    # Light smoothing (15s) for acceleration detection (preserves short bursts)
    accel_v = _rolling_mean(velocity, window=15)
    accel_v = _clamp_velocity(accel_v)
    accel_pace = _velocity_to_pace(accel_v)

    total_time = time[-1] - time[0] if len(time) >= 2 else 0
    total_distance = _compute_total_distance(distance, velocity, time)

    # Step 2: Detect zone transitions
    raw_blocks = _detect_zone_transitions(time, zone_per_point)

    # Step 3: Merge micro-phases
    merged_blocks = _merge_micro_phases(raw_blocks, MIN_PHASE_DURATION_S)

    # Step 3b: Pace-similarity merge — adjacent phases within 20 sec/mi
    # of each other get combined even if zones differ (GPS noise at boundaries)
    merged_blocks = _merge_similar_pace_blocks(
        merged_blocks, phase_pace, threshold_sec_mi=20,
    )

    # Step 4: Classify phase types and compute metrics
    phases = _build_phases(
        merged_blocks, time, phase_v, phase_pace, zone_per_point,
        heartrate, cadence, grade, altitude, distance,
        total_time, heat_adjustment_pct,
    )

    if not phases:
        return None

    # Step 5: Detect accelerations (uses light smoothing to catch short bursts)
    accelerations = _detect_accelerations(
        time, accel_v, accel_pace, zone_per_point,
        heartrate, cadence, phases, pace_profile,
        total_time, total_distance, heat_adjustment_pct,
    )

    # Step 6: Compute shape summary
    summary = _compute_summary(
        phases, accelerations, altitude, distance, total_distance,
    )

    # Step 7: Derive classification
    is_anomaly = _check_anomaly(velocity, time, phases)
    summary.workout_classification = _derive_classification(
        phases, accelerations, summary, total_distance, pace_profile,
        is_anomaly=is_anomaly,
    )

    return RunShape(phases=phases, accelerations=accelerations, summary=summary)


# ═══════════════════════════════════════════════════════
#  Step 1: Smoothing and per-point computation
# ═══════════════════════════════════════════════════════

def _pad(lst: list, n: int) -> list:
    if len(lst) >= n:
        return lst[:n]
    return lst + [None] * (n - len(lst))


def _rolling_mean(values: List, window: int = 15) -> List[float]:
    result = []
    half = window // 2
    n = len(values)
    for i in range(n):
        lo = max(0, i - half)
        hi = min(n, i + half + 1)
        valid = [v for v in values[lo:hi] if v is not None and v >= 0]
        result.append(sum(valid) / len(valid) if valid else 0.0)
    return result


def _clamp_velocity(velocities: List[float]) -> List[float]:
    result = []
    prev_valid = 0.0
    for v in velocities:
        if v > MAX_VELOCITY_MPS:
            result.append(prev_valid)
        else:
            result.append(v)
            if v > 0:
                prev_valid = v
    return result


def _velocity_to_pace(velocities: List[float]) -> List[float]:
    """Convert m/s to sec/mile. Returns 0 for stopped."""
    result = []
    for v in velocities:
        if v < STOPPED_VELOCITY_THRESHOLD:
            result.append(0.0)
        else:
            result.append(METERS_PER_MILE / v)
    return result


def _compute_total_distance(
    distance: List, velocity: List, time: List,
) -> float:
    if distance and distance[-1] is not None and distance[0] is not None:
        return float(distance[-1]) - float(distance[0])
    total = 0.0
    for i in range(1, len(time)):
        v = velocity[i] if velocity[i] is not None else 0
        dt = time[i] - time[i - 1] if i > 0 else 0
        total += v * dt
    return total


def _derive_profile_from_stream(velocity: List) -> PaceProfile:
    """Fallback: derive pace zones from stream velocity percentiles."""
    valid = [v for v in velocity if v is not None and v >= STOPPED_VELOCITY_THRESHOLD]
    if len(valid) < 30:
        return PaceProfile()

    valid.sort()
    n = len(valid)
    p90 = valid[int(n * 0.90)]
    p75 = valid[int(n * 0.75)]
    p50 = valid[int(n * 0.50)]
    p25 = valid[int(n * 0.25)]

    def v_to_pace(v):
        return int(METERS_PER_MILE / v) if v > 0 else 900

    return PaceProfile(
        easy_sec=v_to_pace(p25),
        marathon_sec=v_to_pace(p50),
        threshold_sec=v_to_pace(p75),
        interval_sec=v_to_pace(p90),
        repetition_sec=v_to_pace(valid[int(n * 0.95)]) if n > 20 else v_to_pace(p90) - 30,
    )


# ═══════════════════════════════════════════════════════
#  Step 2: Zone transition detection
# ═══════════════════════════════════════════════════════

def _stabilize_zones(zones: List[str], window: int = 31) -> List[str]:
    """Mode filter: replace each point's zone with the most common zone in
    a sliding window. Eliminates per-second oscillation at zone boundaries."""
    n = len(zones)
    if n < window:
        return zones
    half = window // 2
    stable = []
    for i in range(n):
        lo = max(0, i - half)
        hi = min(n, i + half + 1)
        chunk = zones[lo:hi]
        counts: Dict[str, int] = {}
        for z in chunk:
            counts[z] = counts.get(z, 0) + 1
        stable.append(max(counts, key=counts.get))
    return stable


def _detect_zone_transitions(
    time: List, zones: List[str],
) -> List[Tuple[int, int, str]]:
    """Return list of (start_idx, end_idx, dominant_zone) blocks."""
    if not zones:
        return []

    blocks = []
    block_start = 0
    current_zone = zones[0]

    for i in range(1, len(zones)):
        if zones[i] != current_zone:
            blocks.append((block_start, i - 1, current_zone))
            block_start = i
            current_zone = zones[i]

    blocks.append((block_start, len(zones) - 1, current_zone))
    return blocks


# ═══════════════════════════════════════════════════════
#  Step 3: Merge micro-phases
# ═══════════════════════════════════════════════════════

def _consolidate_same_zone(
    blocks: List[Tuple[int, int, str]],
) -> List[Tuple[int, int, str]]:
    """Merge adjacent blocks that share the same zone."""
    if len(blocks) <= 1:
        return blocks
    result = [blocks[0]]
    for start, end, zone in blocks[1:]:
        if zone == result[-1][2]:
            result[-1] = (result[-1][0], end, zone)
        else:
            result.append((start, end, zone))
    return result


def _merge_micro_phases(
    blocks: List[Tuple[int, int, str]],
    min_duration_s: int,
) -> List[Tuple[int, int, str]]:
    """Merge blocks shorter than min_duration into neighbors, then
    consolidate adjacent same-zone blocks."""
    if len(blocks) <= 1:
        return blocks

    merged = list(blocks)
    changed = True
    max_iterations = 50

    while changed and max_iterations > 0:
        changed = False
        max_iterations -= 1
        new_merged = []
        i = 0

        while i < len(merged):
            start, end, zone = merged[i]
            duration = end - start + 1

            if duration < min_duration_s and len(merged) > 1:
                if i > 0 and (i == len(merged) - 1 or
                              new_merged and new_merged[-1][2] == zone):
                    prev = new_merged[-1]
                    new_merged[-1] = (prev[0], end, prev[2])
                    changed = True
                elif i < len(merged) - 1:
                    next_block = merged[i + 1]
                    new_merged.append((start, next_block[1], next_block[2]))
                    i += 2
                    changed = True
                    continue
                else:
                    new_merged.append((start, end, zone))
            else:
                new_merged.append((start, end, zone))
            i += 1

        merged = new_merged

    return _consolidate_same_zone(merged)


def _merge_similar_pace_blocks(
    blocks: List[Tuple[int, int, str]],
    pace_per_point: List[float],
    threshold_sec_mi: float = 20.0,
) -> List[Tuple[int, int, str]]:
    """Merge adjacent blocks whose average pace is within threshold_sec_mi
    of the anchor (first block in the merge chain).

    Uses an anchor-based approach: tracks the pace of the first block in
    each merge chain. A new block only merges if its pace is within
    threshold of the anchor, preventing cascading merges that erase
    genuine progressions (e.g., 8:12→7:49→7:41→7:15 should NOT become
    one phase even though each adjacent pair is within 20s).
    """
    if len(blocks) <= 1:
        return blocks

    def _avg_pace(start: int, end: int) -> float:
        paces = [p for p in pace_per_point[start:end + 1] if p > 0]
        return sum(paces) / len(paces) if paces else 0

    result = [blocks[0]]
    anchor_pace = _avg_pace(blocks[0][0], blocks[0][1])

    for start, end, zone in blocks[1:]:
        prev_start, prev_end, prev_zone = result[-1]
        curr_pace = _avg_pace(start, end)

        if (anchor_pace > 0 and curr_pace > 0 and
                abs(anchor_pace - curr_pace) < threshold_sec_mi):
            keep_zone = prev_zone if (prev_end - prev_start) >= (end - start) else zone
            result[-1] = (prev_start, end, keep_zone)
        else:
            result.append((start, end, zone))
            anchor_pace = curr_pace

    return result


# ═══════════════════════════════════════════════════════
#  Step 4: Build phases with metrics
# ═══════════════════════════════════════════════════════

def _build_phases(
    blocks: List[Tuple[int, int, str]],
    time: List, velocity: List[float], pace: List[float],
    zones: List[str], heartrate: List, cadence: List,
    grade: List, altitude: List, distance: List,
    total_time: int,
    heat_adj_pct: Optional[float],
) -> List[Phase]:
    """Build Phase objects from merged blocks with full metrics."""
    phases = []

    for block_idx, (start_idx, end_idx, zone) in enumerate(blocks):
        if end_idx <= start_idx:
            continue

        start_t = time[start_idx]
        end_t = time[end_idx]
        duration = end_t - start_t
        if duration < 1:
            continue

        paces = [p for p in pace[start_idx:end_idx + 1] if p > 0]
        vels = [v for v in velocity[start_idx:end_idx + 1] if v > STOPPED_VELOCITY_THRESHOLD]
        hrs = [h for h in heartrate[start_idx:end_idx + 1] if h is not None and h > 0]
        cads = [c for c in cadence[start_idx:end_idx + 1] if c is not None and c > 0]
        grades = [g for g in grade[start_idx:end_idx + 1] if g is not None]

        avg_pace = sum(paces) / len(paces) if paces else 0
        avg_hr = sum(hrs) / len(hrs) if hrs else None
        avg_cad = sum(cads) / len(cads) if cads else None
        avg_grade_val = sum(grades) / len(grades) if grades else None

        # Elevation delta
        alt_start = _first_valid(altitude, start_idx, end_idx)
        alt_end = _last_valid(altitude, start_idx, end_idx)
        elev_delta = (alt_end - alt_start) if alt_start is not None and alt_end is not None else 0.0

        # Distance
        dist_start = _first_valid(distance, start_idx, end_idx)
        dist_end = _last_valid(distance, start_idx, end_idx)
        if dist_start is not None and dist_end is not None:
            phase_dist = float(dist_end) - float(dist_start)
        else:
            phase_dist = sum(v * 1.0 for v in vels)  # rough estimate

        # Pace CV
        pace_cv = 0.0
        if len(paces) >= 3 and avg_pace > 0:
            try:
                pace_cv = statistics.stdev(paces) / avg_pace
            except statistics.StatisticsError:
                pace_cv = 0.0

        # Heat-adjusted pace
        heat_adj_pace = None
        if heat_adj_pct is not None and heat_adj_pct > 0 and avg_pace > 0:
            heat_adj_pace = round(avg_pace / (1 + heat_adj_pct), 1)

        # Phase type classification
        phase_type = _classify_phase_type(
            zone, block_idx, len(blocks), duration, total_time,
            avg_grade_val, phases,
        )

        phases.append(Phase(
            start_time_s=start_t,
            end_time_s=end_t,
            duration_s=duration,
            distance_m=round(phase_dist, 1),
            avg_pace_sec_per_mile=round(avg_pace, 1),
            avg_pace_heat_adjusted=heat_adj_pace,
            pace_zone=zone,
            avg_hr=round(avg_hr, 1) if avg_hr else None,
            avg_cadence=round(avg_cad, 1) if avg_cad else None,
            elevation_delta_m=round(elev_delta, 1),
            avg_grade=round(avg_grade_val, 2) if avg_grade_val is not None else None,
            pace_cv=round(pace_cv, 4),
            phase_type=phase_type,
        ))

    return phases


def _classify_phase_type(
    zone: str, idx: int, total_phases: int,
    duration: int, total_time: int,
    avg_grade: Optional[float],
    prev_phases: List[Phase],
) -> str:
    """Classify a phase by zone, position, grade, and context."""
    pct_of_run = duration / total_time if total_time > 0 else 0

    # Position-based overrides
    if idx == 0 and zone in ('easy', 'recovery', 'stopped') and pct_of_run < 0.25:
        return 'warmup'
    if idx == total_phases - 1 and zone in ('easy', 'recovery', 'stopped') and pct_of_run < 0.25:
        return 'cooldown'

    # Elevation-based
    if avg_grade is not None and avg_grade > 4.0 and duration > 30:
        return 'hill_effort'

    # Effort-based refinements
    if zone == 'threshold' and duration > 240:
        return 'threshold'
    if zone in ('interval', 'repetition') and duration > 10:
        return 'interval_work'

    # Recovery between quality
    if zone in ('easy', 'recovery') and prev_phases:
        last_type = prev_phases[-1].phase_type
        if last_type in ('interval_work', 'threshold'):
            return 'interval_recovery'

    # Default to zone name
    zone_to_type = {
        'easy': 'easy',
        'recovery': 'recovery_jog',
        'marathon': 'steady',
        'threshold': 'tempo',
        'interval': 'interval_work',
        'repetition': 'interval_work',
        'stopped': 'recovery_jog',
    }
    return zone_to_type.get(zone, zone)


def _first_valid(lst: List, start: int, end: int):
    for i in range(start, min(end + 1, len(lst))):
        if lst[i] is not None:
            return float(lst[i])
    return None


def _last_valid(lst: List, start: int, end: int):
    for i in range(min(end, len(lst) - 1), start - 1, -1):
        if lst[i] is not None:
            return float(lst[i])
    return None


# ═══════════════════════════════════════════════════════
#  Step 5: Acceleration detection
# ═══════════════════════════════════════════════════════

def _detect_accelerations(
    time: List, velocity: List[float], pace: List[float],
    zones: List[str], heartrate: List, cadence: List,
    phases: List[Phase],
    pace_profile: PaceProfile,
    total_time: int, total_distance: float,
    heat_adj_pct: Optional[float],
) -> List[Acceleration]:
    """Detect short bursts of speed within or between phases."""
    n = len(time)
    if n < 30:
        return []

    # Exclude warmup/cooldown time ranges
    excluded_ranges = set()
    for p in phases:
        if p.phase_type in ('warmup', 'cooldown'):
            for t in range(p.start_time_s, p.end_time_s + 1):
                excluded_ranges.add(t)

    # Baseline velocity from easy/steady phases
    easy_vels = []
    for p in phases:
        if p.phase_type in ('easy', 'steady', 'recovery_jog'):
            for i in range(n):
                if p.start_time_s <= time[i] <= p.end_time_s:
                    if velocity[i] > STOPPED_VELOCITY_THRESHOLD:
                        easy_vels.append(velocity[i])

    if not easy_vels:
        easy_vels = [v for v in velocity if v > STOPPED_VELOCITY_THRESHOLD]

    if not easy_vels:
        return []

    baseline_v = statistics.median(easy_vels)
    accel_threshold = baseline_v * 1.15
    end_threshold = baseline_v * 1.10

    accelerations = []
    i = 0

    while i < n:
        if time[i] in excluded_ranges:
            i += 1
            continue

        if velocity[i] >= accel_threshold and pace[i] > 0:
            if not pace_profile.is_significant_acceleration(pace[i]):
                i += 1
                continue

            accel_start = i
            below_count = 0

            j = i + 1
            while j < n:
                if velocity[j] < end_threshold:
                    below_count += 1
                    if below_count >= 5:
                        break
                else:
                    below_count = 0
                j += 1

            accel_end = j - below_count if below_count >= 5 else j - 1
            if accel_end <= accel_start:
                i = j
                continue

            duration = time[accel_end] - time[accel_start]
            if duration < MIN_ACCELERATION_DURATION_S:
                i = j
                continue

            accel_paces = [p for p in pace[accel_start:accel_end + 1] if p > 0]
            accel_vels = [v for v in velocity[accel_start:accel_end + 1] if v > 0]
            accel_hrs = [h for h in heartrate[accel_start:accel_end + 1] if h is not None and h > 0]
            accel_cads = [c for c in cadence[accel_start:accel_end + 1] if c is not None and c > 0]

            avg_pace_val = sum(accel_paces) / len(accel_paces) if accel_paces else 0
            avg_hr_val = sum(accel_hrs) / len(accel_hrs) if accel_hrs else None
            avg_cad_val = sum(accel_cads) / len(accel_cads) if accel_cads else None

            accel_dist = sum(v * 1.0 for v in accel_vels)

            zone = pace_profile.classify_pace(avg_pace_val) if avg_pace_val > 0 else 'easy'

            # HR delta vs preceding 30s baseline
            hr_delta = None
            if avg_hr_val and accel_start > 30:
                pre_hrs = [h for h in heartrate[max(0, accel_start - 30):accel_start]
                           if h is not None and h > 0]
                if pre_hrs:
                    hr_delta = round(avg_hr_val - sum(pre_hrs) / len(pre_hrs), 1)

            # Cadence delta
            cad_delta = None
            if avg_cad_val and accel_start > 30:
                pre_cads = [c for c in cadence[max(0, accel_start - 30):accel_start]
                            if c is not None and c > 0]
                if pre_cads:
                    cad_delta = round(avg_cad_val - sum(pre_cads) / len(pre_cads), 1)

            # Position in run
            position = (time[accel_start] - time[0]) / total_time if total_time > 0 else 0

            # Recovery after
            recovery_s = None
            if accel_end < n - 5:
                for k in range(accel_end + 1, min(n, accel_end + 120)):
                    if velocity[k] <= baseline_v * 1.05:
                        recovery_s = time[k] - time[accel_end]
                        break

            heat_adj_pace_val = None
            if heat_adj_pct and heat_adj_pct > 0 and avg_pace_val > 0:
                heat_adj_pace_val = round(avg_pace_val / (1 + heat_adj_pct), 1)

            accelerations.append(Acceleration(
                start_time_s=time[accel_start],
                end_time_s=time[accel_end],
                duration_s=duration,
                distance_m=round(accel_dist, 1),
                avg_pace_sec_per_mile=round(avg_pace_val, 1),
                avg_pace_heat_adjusted=heat_adj_pace_val,
                pace_zone=zone,
                avg_hr=round(avg_hr_val, 1) if avg_hr_val else None,
                hr_delta=hr_delta,
                avg_cadence=round(avg_cad_val, 1) if avg_cad_val else None,
                cadence_delta=cad_delta,
                position_in_run=round(position, 3),
                recovery_after_s=recovery_s,
            ))

            i = accel_end + 1
        else:
            i += 1

    return accelerations


# ═══════════════════════════════════════════════════════
#  Step 6: Shape summary
# ═══════════════════════════════════════════════════════

def _compute_summary(
    phases: List[Phase],
    accelerations: List[Acceleration],
    altitude: List,
    distance: List,
    total_distance: float,
) -> ShapeSummary:
    """Compute queryable shape properties."""
    has_warmup = any(p.phase_type == 'warmup' for p in phases)
    has_cooldown = any(p.phase_type == 'cooldown' for p in phases)

    # Acceleration clustering
    clustering = _compute_clustering(accelerations, total_distance)

    # Pace progression
    progression = _compute_pace_progression(phases)

    # Pace range
    valid_paces = [p.avg_pace_sec_per_mile for p in phases if p.avg_pace_sec_per_mile > 0]
    pace_range = (max(valid_paces) - min(valid_paces)) if len(valid_paces) >= 2 else 0

    # Longest sustained effort
    effort_phases = [p for p in phases if p.phase_type not in
                     ('warmup', 'cooldown', 'interval_recovery', 'recovery_jog')]
    if effort_phases:
        longest = max(effort_phases, key=lambda p: p.duration_s)
        longest_s = longest.duration_s
        longest_zone = longest.pace_zone
    else:
        longest_s = 0
        longest_zone = 'easy'

    # Elevation profile
    elev_profile = _compute_elevation_profile(altitude, total_distance)

    # Acceleration averages
    accel_avg_dur = None
    accel_avg_zone = None
    if accelerations:
        accel_avg_dur = sum(a.duration_s for a in accelerations) / len(accelerations)
        zone_counts = {}
        for a in accelerations:
            zone_counts[a.pace_zone] = zone_counts.get(a.pace_zone, 0) + 1
        accel_avg_zone = max(zone_counts, key=zone_counts.get)

    return ShapeSummary(
        total_phases=len(phases),
        acceleration_count=len(accelerations),
        acceleration_avg_duration_s=round(accel_avg_dur, 1) if accel_avg_dur else None,
        acceleration_avg_pace_zone=accel_avg_zone,
        acceleration_clustering=clustering,
        has_warmup=has_warmup,
        has_cooldown=has_cooldown,
        pace_progression=progression,
        pace_range_sec_per_mile=round(pace_range, 1),
        longest_sustained_effort_s=longest_s,
        longest_sustained_zone=longest_zone,
        elevation_profile=elev_profile,
        workout_classification=None,
    )


def _compute_clustering(
    accelerations: List[Acceleration],
    total_distance: float,
) -> str:
    if len(accelerations) <= 1:
        return 'none'

    positions = [a.position_in_run for a in accelerations]

    # End-loaded: >60% in final 25%
    in_final_25 = sum(1 for p in positions if p > 0.75)
    if in_final_25 / len(positions) > 0.60:
        return 'end_loaded'

    # Periodic: evenly spaced (CV < 0.3)
    if len(positions) >= 3:
        intervals = [positions[i + 1] - positions[i] for i in range(len(positions) - 1)]
        if intervals:
            mean_interval = sum(intervals) / len(intervals)
            if mean_interval > 0:
                try:
                    cv = statistics.stdev(intervals) / mean_interval
                    if cv < 0.3:
                        return 'periodic'
                except statistics.StatisticsError:
                    pass

    return 'scattered'


def _compute_pace_progression(phases: List[Phase]) -> str:
    """Determine if pace built, faded, held steady, etc."""
    effort_phases = [p for p in phases if p.phase_type not in
                     ('warmup', 'cooldown', 'interval_recovery', 'recovery_jog')
                     and p.avg_pace_sec_per_mile > 0]

    if len(effort_phases) < 2:
        return 'steady'

    paces = [p.avg_pace_sec_per_mile for p in effort_phases]
    n = len(paces)

    # Weighted linear regression
    x = list(range(n))
    x_mean = sum(x) / n
    y_mean = sum(paces) / n

    ss_xx = sum((xi - x_mean) ** 2 for xi in x)
    ss_xy = sum((xi - x_mean) * (yi - y_mean) for xi, yi in zip(x, paces))

    if ss_xx == 0:
        return 'steady'

    slope = ss_xy / ss_xx
    y_pred = [y_mean + slope * (xi - x_mean) for xi in x]
    ss_res = sum((yi - yp) ** 2 for yi, yp in zip(paces, y_pred))
    ss_tot = sum((yi - y_mean) ** 2 for yi in paces)
    r_sq = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

    # Even split check
    mid = n // 2
    first_avg = sum(paces[:mid]) / mid if mid > 0 else paces[0]
    second_avg = sum(paces[mid:]) / len(paces[mid:])

    if abs(first_avg - second_avg) < 10:
        return 'even_split'

    if slope < -5 and r_sq > 0.6:
        return 'building'
    if slope > 5 and r_sq > 0.6:
        return 'fading'
    if abs(slope) < 5 and r_sq < 0.3:
        return 'steady'

    return 'variable'


def _compute_elevation_profile(altitude: List, total_distance: float) -> str:
    valid_alt = [a for a in altitude if a is not None]
    if len(valid_alt) < 10:
        return 'flat'

    total_gain = 0.0
    for i in range(1, len(valid_alt)):
        diff = valid_alt[i] - valid_alt[i - 1]
        if diff > 0:
            total_gain += diff

    net_elev = valid_alt[-1] - valid_alt[0]
    miles = total_distance / METERS_PER_MILE if total_distance > 0 else 1

    if total_gain < 50:
        return 'flat'
    if net_elev > 30:
        return 'net_uphill'
    if net_elev < -30:
        return 'net_downhill'
    if abs(net_elev) <= 10 and total_gain > 50:
        return 'out_and_back'
    if total_gain / miles > 30:
        return 'hilly'

    return 'flat'


# ═══════════════════════════════════════════════════════
#  Step 7: Classification
# ═══════════════════════════════════════════════════════

def _derive_classification(
    phases: List[Phase],
    accelerations: List[Acceleration],
    summary: ShapeSummary,
    total_distance: float,
    pace_profile: PaceProfile,
    is_anomaly: bool = False,
) -> Optional[str]:
    """Derive an optional workout classification from shape structure."""
    if is_anomaly:
        return 'anomaly'

    n_phases = summary.total_phases
    n_accels = summary.acceleration_count

    effort_phases = [p for p in phases if p.phase_type not in
                     ('warmup', 'cooldown', 'interval_recovery', 'recovery_jog')]

    # Easy run / recovery run: all phases easy, few accelerations, low pace CV
    all_easy = all(p.pace_zone in ('easy', 'recovery') for p in effort_phases)
    if all_easy and n_accels < 2:
        avg_cv = sum(p.pace_cv for p in effort_phases) / len(effort_phases) if effort_phases else 0
        if avg_cv < 0.15:
            if total_distance > 20000:
                return 'long_run'
            all_recovery_zone = all(p.pace_zone == 'recovery' for p in effort_phases)
            if total_distance < 8000 and all_recovery_zone:
                return 'recovery_run'
            return 'easy_run'

    # Strides: end-loaded accelerations at meaningful pace
    if (3 <= n_accels <= 8 and
            summary.acceleration_clustering == 'end_loaded'):
        main_body = [p for p in effort_phases
                     if p.end_time_s < accelerations[0].start_time_s]
        body_all_easy = (not main_body or
                         all(p.pace_zone in ('easy', 'recovery') for p in main_body))
        if body_all_easy:
            accel_durations = [a.duration_s for a in accelerations]
            if all(10 <= d <= 45 for d in accel_durations):
                fast_enough = all(
                    a.pace_zone in ('interval', 'repetition', 'threshold', 'marathon')
                    for a in accelerations
                )
                if fast_enough:
                    if total_distance > 20000:
                        return 'long_run_with_strides'
                    return 'strides'

    # Fartlek: scattered accelerations with variable duration
    if (n_accels >= 3 and
            summary.acceleration_clustering == 'scattered'):
        return 'fartlek'

    # Tempo: single sustained threshold/marathon phase with warmup/cooldown
    tempo_phases = [p for p in effort_phases
                    if p.phase_type in ('threshold', 'steady') and p.duration_s > 720]
    if len(tempo_phases) == 1 and (summary.has_warmup or summary.has_cooldown):
        return 'tempo'

    # Threshold intervals: 2-5 threshold phases with recovery between
    threshold_work = [p for p in effort_phases
                      if p.phase_type == 'threshold' and p.duration_s >= 240]
    if 2 <= len(threshold_work) <= 5:
        recovery_between = any(p.phase_type == 'interval_recovery' for p in phases)
        if recovery_between:
            return 'threshold_intervals'

    # Track intervals: 4+ interval/rep phases with similar duration
    interval_work = [p for p in effort_phases
                     if p.phase_type == 'interval_work']
    if len(interval_work) >= 4:
        durations = [p.duration_s for p in interval_work]
        avg_dur = sum(durations) / len(durations)
        if avg_dur > 0:
            try:
                cv = statistics.stdev(durations) / avg_dur
                if cv < 0.4:
                    return 'track_intervals'
            except statistics.StatisticsError:
                pass

    # Progression: successive phases getting faster with meaningful pace drop
    if len(effort_phases) >= 2 and summary.pace_progression == 'building':
        last_zone = effort_phases[-1].pace_zone
        first_pace = effort_phases[0].avg_pace_sec_per_mile
        last_pace = effort_phases[-1].avg_pace_sec_per_mile
        if (last_zone in ('marathon', 'threshold', 'interval', 'repetition')
                and first_pace > 0 and last_pace > 0
                and first_pace - last_pace > 15):
            return 'progression'

    # Over/under: alternating above/below marathon pace
    if len(effort_phases) >= 4:
        above_below = []
        for p in effort_phases:
            if pace_profile.is_at_least_marathon(p.avg_pace_sec_per_mile):
                above_below.append('above')
            else:
                above_below.append('below')
        alternating = all(
            above_below[i] != above_below[i + 1]
            for i in range(len(above_below) - 1)
        )
        if alternating:
            return 'over_under'

    # Hill repeats
    hill_efforts = [p for p in effort_phases if p.phase_type == 'hill_effort']
    if len(hill_efforts) >= 3:
        return 'hill_repeats'

    # Long run with tempo
    if total_distance > 20000:
        embedded_tempo = [p for p in effort_phases
                          if p.phase_type == 'threshold' and p.duration_s > 600]
        if embedded_tempo:
            return 'long_run_with_tempo'
        if n_accels >= 3 and summary.acceleration_clustering == 'end_loaded':
            return 'long_run_with_strides'
        return 'long_run'

    return None


def _check_anomaly(
    velocity: List[float], time: List, phases: List[Phase],
) -> bool:
    """GPS gaps > 30s AND (unrealistic velocity > 25 mph OR 3+ separate gaps).
    A single tunnel/pause is not an anomaly."""
    gaps = 0
    unrealistic_count = 0
    n = len(time)

    for i in range(1, n):
        dt = time[i] - time[i - 1]
        if dt > 30:
            gaps += 1

    for v in velocity:
        if v > MAX_VELOCITY_MPS:
            unrealistic_count += 1

    return gaps > 0 and (unrealistic_count > 0 or gaps >= 3)
