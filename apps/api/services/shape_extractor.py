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
MIN_ACCELERATION_DURATION_S = 8
MAX_VELOCITY_MPS = 11.0  # 25 mph
STOPPED_VELOCITY_THRESHOLD = 0.5  # m/s
WALKING_THRESHOLD_SEC = 1200  # 20:00/mi — slower is walking, not easy
ZONE_HALF_WIDTH = 10  # ±10 sec per mile around each zone center


@dataclass
class ZoneBand:
    """A discrete training zone band. Anything between bands is gray area."""
    name: str
    center_sec: int
    half_width: int = ZONE_HALF_WIDTH
    floor_override: Optional[int] = None

    @property
    def floor(self) -> int:
        if self.floor_override is not None:
            return self.floor_override
        return self.center_sec - self.half_width

    @property
    def ceiling(self) -> int:
        return self.center_sec + self.half_width

    def contains(self, pace_sec: float) -> bool:
        return self.floor <= pace_sec <= self.ceiling


def build_zone_bands(centers: Dict[str, int], half_width: int = ZONE_HALF_WIDTH) -> List[ZoneBand]:
    """Build non-overlapping zone bands ordered fastest to slowest.

    When two bands would overlap, the slower zone's floor shrinks to
    1 second above the faster zone's ceiling.
    """
    ordered = ['repetition', 'interval', 'threshold', 'marathon']
    bands = []
    for name in ordered:
        if name not in centers:
            continue
        band = ZoneBand(name=name, center_sec=centers[name], half_width=half_width)
        if bands:
            prev = bands[-1]
            if band.floor <= prev.ceiling:
                band.floor_override = prev.ceiling + 1
        bands.append(band)
    bands.append(ZoneBand(name='easy', center_sec=centers.get('easy', 600), half_width=half_width))
    return bands


@dataclass
class PaceProfile:
    """Athlete's pace zones in seconds per mile. Used for zone classification."""
    easy_sec: int = 600
    marathon_sec: int = 480
    threshold_sec: int = 450
    interval_sec: int = 400
    repetition_sec: int = 360
    _bands: Optional[List[ZoneBand]] = field(default=None, repr=False)

    def __post_init__(self):
        self._bands = build_zone_bands({
            'repetition': self.repetition_sec,
            'interval': self.interval_sec,
            'threshold': self.threshold_sec,
            'marathon': self.marathon_sec,
            'easy': self.easy_sec,
        })

    def classify_pace(self, pace_sec_per_mile: float) -> str:
        if pace_sec_per_mile <= 0:
            return 'stopped'
        if pace_sec_per_mile >= WALKING_THRESHOLD_SEC:
            return 'walking'
        for band in self._bands:
            if band.name == 'easy':
                continue
            if band.contains(pace_sec_per_mile):
                return band.name
        if pace_sec_per_mile >= self._easy_ceiling():
            return 'easy'
        return 'gray'

    def _easy_ceiling(self) -> int:
        """Easy has no floor — only a ceiling (the fast edge)."""
        easy_band = next((b for b in self._bands if b.name == 'easy'), None)
        if easy_band:
            return easy_band.floor
        return self.easy_sec - ZONE_HALF_WIDTH

    def is_at_least_marathon(self, pace_sec_per_mile: float) -> bool:
        mar_band = next((b for b in self._bands if b.name == 'marathon'), None)
        if mar_band:
            return 0 < pace_sec_per_mile <= mar_band.ceiling
        return 0 < pace_sec_per_mile <= self.marathon_sec + ZONE_HALF_WIDTH

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
    hr_recovery_rate: Optional[float] = None
    avg_grade: Optional[float] = None
    elevation_gain_m: Optional[float] = None

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
    median_duration_s: Optional[float] = None,
) -> Optional[RunShape]:
    """Extract the RunShape from per-second stream data.

    Args:
        stream_data: Dict mapping channel names to lists of per-second values.
            Required: 'time', 'velocity_smooth'
            Optional: 'heartrate', 'cadence', 'grade_smooth', 'altitude', 'distance'
        pace_profile: Athlete's training pace zones. Falls back to
            stream-relative percentiles if None.
        heat_adjustment_pct: If provided, computes heat-adjusted pace for each phase.
        median_duration_s: 30-day rolling median activity duration for long run detection.

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

    unzoned = pace_profile is None
    if unzoned:
        logger.warning("No pace profile available — unzoned single-phase output")
        pace_profile = PaceProfile()

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

    # Light smoothing (7s) for acceleration detection — must preserve 8-20s strides
    accel_v = _rolling_mean(velocity, window=7)
    accel_v = _clamp_velocity(accel_v)
    accel_pace = _velocity_to_pace(accel_v)

    total_time = time[-1] - time[0] if len(time) >= 2 else 0
    total_distance = _compute_total_distance(distance, velocity, time)

    # Step 2: Detect zone transitions
    raw_blocks = _detect_zone_transitions(time, zone_per_point)

    # Step 3: Merge micro-phases
    merged_blocks = _merge_micro_phases(raw_blocks, MIN_PHASE_DURATION_S)

    # Step 3b: Same-zone consolidation — adjacent phases in same zone always merge
    merged_blocks = _consolidate_same_zone(merged_blocks)

    # Step 3c: Pace-similarity merge — adjacent phases within 20 sec/mi
    # of each other get combined even if zones differ (GPS noise at boundaries)
    merged_blocks = _merge_similar_pace_blocks(
        merged_blocks, phase_pace, threshold_sec_mi=20,
    )

    # Step 3d: Final same-zone consolidation after pace merge
    merged_blocks = _consolidate_same_zone(merged_blocks)

    # Step 3e: Anti-oscillation merge — collapse easy↔gray GPS boundary noise
    merged_blocks = _merge_easy_gray_oscillation(
        merged_blocks, phase_pace, cadence, time, pace_profile,
    )
    merged_blocks = _consolidate_same_zone(merged_blocks)

    # If unzoned (no pace profile), collapse to single phase
    if unzoned and len(merged_blocks) > 1:
        merged_blocks = [(merged_blocks[0][0], merged_blocks[-1][1], 'easy')]

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
        heartrate, cadence, grade, altitude,
        phases, pace_profile,
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
        is_anomaly=is_anomaly, unzoned=unzoned,
        total_duration_s=float(total_time),
        median_duration_s=median_duration_s,
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



# _derive_profile_from_stream REMOVED — stream-relative zones produce garbage
# for steady-effort runs. Suppression over hallucination: if no profile exists,
# the extractor produces an unzoned single-phase shape with accelerations.


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


def _merge_easy_gray_oscillation(
    blocks: List[Tuple[int, int, str]],
    pace_per_point: List[float],
    cadence: List,
    time: List,
    pace_profile: PaceProfile,
) -> List[Tuple[int, int, str]]:
    """Absorb short gray blocks between easy blocks when they're GPS boundary noise.

    Targets the specific easy→gray→easy oscillation pattern caused by GPS
    pace noise near the easy zone ceiling. All six conditions must be true
    for absorption — genuine gray effort is preserved.
    """
    if len(blocks) < 3:
        return blocks

    easy_ceiling = pace_profile._easy_ceiling()
    # Proportional thresholds: at slow paces, same GPS noise in m/s produces
    # larger sec/mi deltas due to the non-linear velocity→pace conversion.
    proximity_threshold = max(25, int(pace_profile.easy_sec * 0.06))
    near_ceiling_margin = max(30, int(pace_profile.easy_sec * 0.06))

    def _avg_pace_for_block(start: int, end: int) -> float:
        paces = [p for p in pace_per_point[start:end + 1] if p > 0]
        return sum(paces) / len(paces) if paces else 0

    def _block_duration(start: int, end: int) -> float:
        if start < len(time) and end < len(time):
            return time[end] - time[start]
        return end - start

    result = list(blocks)
    changed = True
    while changed:
        changed = False
        new_result = []
        i = 0
        while i < len(result):
            if i + 2 < len(result):
                prev_s, prev_e, prev_z = result[i]
                gray_s, gray_e, gray_z = result[i + 1]
                next_s, next_e, next_z = result[i + 2]

                if prev_z == 'easy' and gray_z == 'gray' and next_z == 'easy':
                    gray_dur = _block_duration(gray_s, gray_e)
                    gray_pace = _avg_pace_for_block(gray_s, gray_e)
                    prev_pace = _avg_pace_for_block(prev_s, prev_e)
                    next_pace = _avg_pace_for_block(next_s, next_e)

                    if gray_dur < 90 and gray_pace > 0 and prev_pace > 0 and next_pace > 0:
                        close_to_prev = abs(gray_pace - prev_pace) < proximity_threshold
                        close_to_next = abs(gray_pace - next_pace) < proximity_threshold
                        near_ceiling = gray_pace >= (easy_ceiling - near_ceiling_margin)

                        has_speed_work = pace_profile.is_significant_acceleration(
                            min(p for p in pace_per_point[gray_s:gray_e + 1] if p > 0)
                        ) if any(p > 0 for p in pace_per_point[gray_s:gray_e + 1]) else False

                        cad_stable = True
                        cad_no_spike = True
                        boundary_start = max(0, gray_s - 15)
                        boundary_end = min(len(cadence) - 1, gray_e + 15)
                        boundary_cads = [c for c in cadence[boundary_start:boundary_end + 1]
                                         if c is not None and c > 0]
                        if len(boundary_cads) >= 5:
                            cad_mean = sum(boundary_cads) / len(boundary_cads)
                            if cad_mean > 0:
                                cad_std = (sum((c - cad_mean) ** 2 for c in boundary_cads) / len(boundary_cads)) ** 0.5
                                cad_stable = (cad_std / cad_mean) < 0.15
                            gray_cads = [c for c in cadence[gray_s:gray_e + 1]
                                         if c is not None and c > 0]
                            if gray_cads and boundary_cads:
                                cad_no_spike = max(gray_cads) - cad_mean < MIN_CADENCE_SPIKE_SPM

                        if (close_to_prev and close_to_next and near_ceiling
                                and cad_stable and cad_no_spike and not has_speed_work):
                            new_result.append((prev_s, gray_e, 'easy'))
                            i += 2
                            changed = True
                            continue

            new_result.append(result[i])
            i += 1

        result = new_result

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

    # Position-based overrides (only for 3+ phase runs to avoid consuming
    # the start of a 2-phase progression)
    if idx == 0 and total_phases >= 3 and zone in ('easy', 'gray', 'walking', 'stopped') and pct_of_run < 0.25:
        return 'warmup'
    if idx == total_phases - 1 and total_phases >= 3 and zone in ('easy', 'gray', 'walking', 'stopped') and pct_of_run < 0.25:
        return 'cooldown'

    # Elevation-based
    if avg_grade is not None and avg_grade > 4.0 and duration > 30:
        return 'hill_effort'

    # Effort-based refinements
    if zone == 'threshold' and duration > 180:
        return 'threshold'
    if zone in ('interval', 'repetition') and duration > 10:
        return 'interval_work'

    # Recovery between quality
    if zone in ('easy', 'gray', 'walking') and prev_phases:
        last_type = prev_phases[-1].phase_type
        if last_type in ('interval_work', 'threshold'):
            return 'interval_recovery'

    zone_to_type = {
        'easy': 'easy',
        'gray': 'steady',
        'marathon': 'steady',
        'threshold': 'tempo',
        'interval': 'interval_work',
        'repetition': 'interval_work',
        'walking': 'easy',
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
    grade: List, altitude: List,
    phases: List[Phase],
    pace_profile: PaceProfile,
    total_time: int, total_distance: float,
    heat_adj_pct: Optional[float],
) -> List[Acceleration]:
    """Detect short bursts of speed within or between phases.

    Uses two parallel detection channels:
      1. Velocity-based: detects accelerations via GPS-derived speed
      2. Cadence-based: detects accelerations via watch accelerometer
    Cadence detection catches strides that GPS misses for slower runners
    where the absolute velocity change is too small for GPS accuracy.
    Results from both channels are merged and deduplicated.
    """
    n = len(time)
    if n < 30:
        return []

    excluded_ranges = set()
    for p in phases:
        if p.phase_type in ('warmup', 'cooldown'):
            for t in range(p.start_time_s, p.end_time_s + 1):
                excluded_ranges.add(t)

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

    vel_accels = _detect_velocity_accelerations(
        time, velocity, pace, heartrate, cadence, grade, altitude,
        baseline_v, excluded_ranges, pace_profile,
        total_time, heat_adj_pct, n,
    )

    cad_accels = _detect_cadence_accelerations(
        time, velocity, pace, heartrate, cadence, grade, altitude,
        baseline_v, excluded_ranges, pace_profile,
        total_time, heat_adj_pct, n,
    )

    merged = _merge_acceleration_channels(vel_accels, cad_accels)

    for accel in merged:
        accel.hr_recovery_rate = _compute_hr_recovery_rate(
            time, heartrate, accel.end_time_s, n,
        )

    return merged


def _detect_velocity_accelerations(
    time: List, velocity: List[float], pace: List[float],
    heartrate: List, cadence: List,
    grade: List, altitude: List,
    baseline_v: float, excluded_ranges: set,
    pace_profile: PaceProfile,
    total_time: int, heat_adj_pct: Optional[float],
    n: int,
) -> List[Acceleration]:
    """Channel 1: velocity-based acceleration detection."""
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

            accel = _build_acceleration(
                time, velocity, pace, heartrate, cadence,
                grade, altitude,
                accel_start, accel_end, baseline_v, pace_profile,
                total_time, heat_adj_pct, n,
            )
            if accel:
                accelerations.append(accel)

            i = accel_end + 1
        else:
            i += 1

    return accelerations


MIN_CADENCE_SPIKE_SPM = 15

def _detect_cadence_accelerations(
    time: List, velocity: List[float], pace: List[float],
    heartrate: List, cadence: List,
    grade: List, altitude: List,
    baseline_v: float, excluded_ranges: set,
    pace_profile: PaceProfile,
    total_time: int, heat_adj_pct: Optional[float],
    n: int,
) -> List[Acceleration]:
    """Channel 2: cadence-based acceleration detection.

    Watch accelerometer measures cadence directly — not GPS-dependent.
    A stride always produces a cadence spike regardless of runner speed.
    """
    valid_cads = [c for c in cadence if c is not None and c > 0]
    if len(valid_cads) < 30:
        return []

    baseline_cad = statistics.median(valid_cads)
    cad_threshold = baseline_cad + MIN_CADENCE_SPIKE_SPM
    cad_end_threshold = baseline_cad + (MIN_CADENCE_SPIKE_SPM * 0.6)

    accelerations = []
    i = 0

    while i < n:
        if time[i] in excluded_ranges:
            i += 1
            continue

        c = cadence[i] if cadence[i] is not None else 0
        if c >= cad_threshold:
            accel_start = i
            below_count = 0
            j = i + 1
            while j < n:
                cj = cadence[j] if cadence[j] is not None else 0
                if cj < cad_end_threshold:
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

            accel = _build_acceleration(
                time, velocity, pace, heartrate, cadence,
                grade, altitude,
                accel_start, accel_end, baseline_v, pace_profile,
                total_time, heat_adj_pct, n,
            )
            if accel:
                accelerations.append(accel)

            i = accel_end + 1
        else:
            i += 1

    return accelerations


def _build_acceleration(
    time: List, velocity: List[float], pace: List[float],
    heartrate: List, cadence: List,
    grade: List, altitude: List,
    start_idx: int, end_idx: int,
    baseline_v: float, pace_profile: PaceProfile,
    total_time: int, heat_adj_pct: Optional[float],
    n: int,
) -> Optional[Acceleration]:
    """Build an Acceleration object from a detected start/end index pair."""
    duration = time[end_idx] - time[start_idx]
    if duration < MIN_ACCELERATION_DURATION_S:
        return None

    accel_paces = [p for p in pace[start_idx:end_idx + 1] if p > 0]
    accel_vels = [v for v in velocity[start_idx:end_idx + 1] if v > 0]
    accel_hrs = [h for h in heartrate[start_idx:end_idx + 1]
                 if h is not None and h > 0]
    accel_cads = [c for c in cadence[start_idx:end_idx + 1]
                  if c is not None and c > 0]

    avg_pace_val = sum(accel_paces) / len(accel_paces) if accel_paces else 0
    avg_hr_val = sum(accel_hrs) / len(accel_hrs) if accel_hrs else None
    avg_cad_val = sum(accel_cads) / len(accel_cads) if accel_cads else None
    accel_dist = sum(v * 1.0 for v in accel_vels)

    zone = pace_profile.classify_pace(avg_pace_val) if avg_pace_val > 0 else 'easy'

    hr_delta = None
    if avg_hr_val and start_idx > 30:
        pre_hrs = [h for h in heartrate[max(0, start_idx - 30):start_idx]
                   if h is not None and h > 0]
        if pre_hrs:
            hr_delta = round(avg_hr_val - sum(pre_hrs) / len(pre_hrs), 1)

    cad_delta = None
    if avg_cad_val and start_idx > 30:
        pre_cads = [c for c in cadence[max(0, start_idx - 30):start_idx]
                    if c is not None and c > 0]
        if pre_cads:
            cad_delta = round(avg_cad_val - sum(pre_cads) / len(pre_cads), 1)

    position = (time[start_idx] - time[0]) / total_time if total_time > 0 else 0

    recovery_s = None
    if end_idx < n - 5:
        for k in range(end_idx + 1, min(n, end_idx + 120)):
            if velocity[k] <= baseline_v * 1.05:
                recovery_s = time[k] - time[end_idx]
                break

    heat_adj_pace_val = None
    if heat_adj_pct and heat_adj_pct > 0 and avg_pace_val > 0:
        heat_adj_pace_val = round(avg_pace_val / (1 + heat_adj_pct), 1)

    accel_grades = [g for g in grade[start_idx:end_idx + 1]
                    if g is not None]
    accel_avg_grade = sum(accel_grades) / len(accel_grades) if accel_grades else None

    accel_elev_gain = None
    alts = altitude[start_idx:end_idx + 1]
    valid_alts = [(i, a) for i, a in enumerate(alts) if a is not None]
    if len(valid_alts) >= 2:
        gain = 0.0
        for j in range(1, len(valid_alts)):
            diff = valid_alts[j][1] - valid_alts[j - 1][1]
            if diff > 0:
                gain += diff
        accel_elev_gain = round(gain, 1)

    return Acceleration(
        start_time_s=time[start_idx],
        end_time_s=time[end_idx],
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
        avg_grade=round(accel_avg_grade, 2) if accel_avg_grade is not None else None,
        elevation_gain_m=accel_elev_gain,
    )


def _merge_acceleration_channels(
    vel_accels: List[Acceleration],
    cad_accels: List[Acceleration],
) -> List[Acceleration]:
    """Merge velocity-detected and cadence-detected accelerations.
    Deduplicates overlapping detections, preferring the one with
    longer duration (more complete capture of the stride)."""
    if not cad_accels:
        return vel_accels
    if not vel_accels:
        return cad_accels

    all_accels = vel_accels + cad_accels
    all_accels.sort(key=lambda a: a.start_time_s)

    merged = [all_accels[0]]
    for accel in all_accels[1:]:
        prev = merged[-1]
        if accel.start_time_s <= prev.end_time_s + 3:
            if accel.duration_s > prev.duration_s:
                merged[-1] = accel
        else:
            merged.append(accel)

    return merged


def _compute_hr_recovery_rate(
    time: List, heartrate: List,
    accel_end_time: int, n: int,
) -> Optional[float]:
    """Compute cardiac recovery rate (bpm/s) in the 30-60s after an accel.
    Measures how fast HR drops — the real fitness signal for interval recovery."""
    end_idx = None
    for i in range(n):
        if time[i] >= accel_end_time:
            end_idx = i
            break
    if end_idx is None or end_idx >= n - 10:
        return None

    hr_at_end = None
    for i in range(end_idx, min(end_idx + 5, n)):
        h = heartrate[i] if heartrate[i] is not None else 0
        if h > 0:
            hr_at_end = h
            break
    if hr_at_end is None:
        return None

    window_end = min(n, end_idx + 60)
    recovery_hrs = []
    for i in range(end_idx + 20, window_end):
        h = heartrate[i] if i < len(heartrate) and heartrate[i] is not None else 0
        if h > 0:
            recovery_hrs.append(h)

    if len(recovery_hrs) < 5:
        return None

    hr_at_recovery = statistics.mean(recovery_hrs[-10:]) if len(recovery_hrs) >= 10 else statistics.mean(recovery_hrs)
    hr_drop = hr_at_end - hr_at_recovery
    if hr_drop <= 0:
        return None

    elapsed = (window_end - end_idx)
    return round(hr_drop / elapsed, 2) if elapsed > 0 else None


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
    unzoned: bool = False,
    total_duration_s: float = 0.0,
    median_duration_s: Optional[float] = None,
) -> Optional[str]:
    """Derive an optional workout classification from shape structure."""
    if is_anomaly:
        return 'anomaly'
    if unzoned:
        return None

    n_phases = summary.total_phases
    n_accels = summary.acceleration_count

    effort_phases = [p for p in phases if p.phase_type not in
                     ('warmup', 'cooldown', 'interval_recovery', 'recovery_jog')]

    is_long = _is_long_run(total_duration_s, median_duration_s)
    is_medium_long = _is_medium_long(total_duration_s, median_duration_s)

    all_easy_or_gray = all(p.pace_zone in ('easy', 'gray', 'walking') for p in effort_phases) if effort_phases else True

    # Hill repeats: 3+ hill efforts from phases OR 3+ graded accelerations
    if n_accels >= 3:
        hill_efforts_from_phases = [p for p in effort_phases if p.phase_type == 'hill_effort']
        if len(hill_efforts_from_phases) >= 3:
            return 'hill_repeats'

        if summary.elevation_profile not in ('flat',):
            hill_accels = [a for a in accelerations
                           if a.avg_grade is not None and a.avg_grade > 4.0
                           and a.elevation_gain_m is not None and a.elevation_gain_m > 0]
            if len(hill_accels) >= 3:
                return 'hill_repeats'

    # Progression (3+ phases, each ≥15 sec/mi faster — clear structural pattern)
    if len(effort_phases) >= 3:
        paces = [p.avg_pace_sec_per_mile for p in effort_phases if p.avg_pace_sec_per_mile > 0]
        if len(paces) >= 3:
            all_progressing = all(
                paces[i] - paces[i + 1] >= 15
                for i in range(len(paces) - 1)
            )
            if all_progressing:
                return 'progression'

    # Strides: end-loaded accelerations at meaningful pace
    if (3 <= n_accels <= 8 and
            summary.acceleration_clustering == 'end_loaded'):
        main_body = [p for p in effort_phases
                     if p.end_time_s < accelerations[0].start_time_s]
        body_all_easy = (not main_body or
                         all(p.pace_zone in ('easy', 'gray', 'walking') for p in main_body))
        if body_all_easy:
            accel_durations = [a.duration_s for a in accelerations]
            if all(8 <= d <= 60 for d in accel_durations):
                fast_enough = all(
                    a.pace_zone in ('interval', 'repetition', 'threshold', 'marathon', 'gray')
                    or (a.cadence_delta is not None and a.cadence_delta >= MIN_CADENCE_SPIKE_SPM)
                    for a in accelerations
                )
                if fast_enough:
                    return 'strides'

    # Progression fallback: 2+ phases with clear building pattern
    # Excluded when there are end-loaded accelerations (those are strides, not progressions)
    has_stride_pattern = (n_accels >= 3 and summary.acceleration_clustering == 'end_loaded')
    if (len(effort_phases) >= 2 and summary.pace_progression == 'building'
            and not has_stride_pattern):
        first_pace = effort_phases[0].avg_pace_sec_per_mile
        last_pace = effort_phases[-1].avg_pace_sec_per_mile
        if first_pace > 0 and last_pace > 0 and first_pace - last_pace > 30:
            return 'progression'

    # Tempo: contains 1 threshold or sustained marathon phase > 12 min
    tempo_phases = [p for p in effort_phases
                    if p.pace_zone in ('threshold', 'marathon') and p.duration_s > 720]
    if len(tempo_phases) == 1:
        return 'tempo'

    # Threshold intervals: 2-5 threshold phases with recovery between
    threshold_work = [p for p in effort_phases
                      if p.pace_zone == 'threshold' and p.duration_s >= 180]
    if 2 <= len(threshold_work) <= 5:
        return 'threshold_intervals'

    # Track intervals: 4+ interval/rep phases with similar duration
    interval_work = [p for p in effort_phases
                     if p.pace_zone in ('interval', 'repetition')]
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

    # Long run: duration >= 2× median, base effort is easy/gray
    # Checked before fartlek to prevent hilly long runs from being fartlek
    if is_long and all_easy_or_gray:
        return 'long_run'

    # Medium-long run: 1.65× to 2× median
    if is_medium_long and all_easy_or_gray:
        return 'medium_long_run'

    # Fartlek: 3+ scattered accelerations (but NOT if base effort is steady
    # and qualifies as long/medium-long — those go to long_run above)
    if (n_accels >= 3 and
            summary.acceleration_clustering == 'scattered'):
        if is_long:
            return 'long_run'
        # On hilly terrain, pace variation from elevation isn't intentional fartlek
        if summary.elevation_profile in ('hilly', 'net_uphill', 'net_downhill', 'out_and_back'):
            pass  # fall through to easy/progression/gray checks below
        else:
            return 'fartlek'

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

    # Easy run: all phases easy/gray/walking, ≤3 effort phases, few accels
    if all_easy_or_gray and n_accels <= 2 and len(effort_phases) <= 3:
        return 'easy_run'

    # Gray zone run: primary phase is gray, no structured work
    if effort_phases and n_accels <= 2:
        gray_duration = sum(p.duration_s for p in effort_phases if p.pace_zone == 'gray')
        total_effort = sum(p.duration_s for p in effort_phases)
        if total_effort > 0 and gray_duration / total_effort > 0.5:
            return 'gray_zone_run'

    # Fallback easy for quiet runs
    if n_accels <= 2 and len(effort_phases) <= 3:
        return 'easy_run'

    return None


def _check_anomaly(
    velocity: List[float], time: List, phases: List[Phase],
) -> bool:
    """Hybrid anomaly detection: unrealistic velocity, single huge gap,
    proportion-based corruption, and severity on short runs."""
    n = len(time)
    total_duration = time[-1] - time[0] if n >= 2 else 0
    if total_duration <= 0:
        return True

    total_gap_time = 0
    gap_count = 0
    max_single_gap = 0
    unrealistic_count = 0

    for i in range(1, n):
        dt = time[i] - time[i - 1]
        if dt > 30:
            gap_count += 1
            total_gap_time += dt
            max_single_gap = max(max_single_gap, dt)

    for v in velocity:
        if v is not None and v > MAX_VELOCITY_MPS:
            unrealistic_count += 1

    if unrealistic_count > 0:
        return True

    if max_single_gap > 300:
        return True

    corruption_pct = total_gap_time / total_duration
    if corruption_pct > 0.05:
        return True

    if gap_count >= 3 and total_duration < 1800:
        return True

    return False


# ═══════════════════════════════════════════════════════
#  Shape Sentence Generator
# ═══════════════════════════════════════════════════════

def generate_shape_sentence(
    shape: RunShape,
    total_distance_m: float,
    total_duration_s: float,
    pace_profile: Optional[PaceProfile] = None,
    median_duration_s: Optional[float] = None,
    use_km: bool = False,
) -> Optional[str]:
    """Generate a natural language sentence from a RunShape.

    Returns None when suppression rules apply (classification is null,
    unzoned, anomaly, too short, or too many phases).
    """
    cls = shape.summary.workout_classification
    phases = shape.phases
    accels = shape.accelerations

    if _should_suppress(shape, total_distance_m, total_duration_s):
        return None

    dist_str = _format_distance(total_distance_m, use_km)
    is_long = _is_long_run(total_duration_s, median_duration_s)
    is_medium_long = _is_medium_long(total_duration_s, median_duration_s)

    effort_phases = [p for p in phases if p.phase_type not in
                     ('warmup', 'cooldown', 'interval_recovery', 'recovery_jog')]

    if cls == 'strides' or (is_long and cls == 'strides'):
        n = len(accels)
        fastest = min(accels, key=lambda a: a.avg_pace_sec_per_mile) if accels else None
        fast_str = f" (fastest {_fmt_pace(fastest.avg_pace_sec_per_mile, use_km)})" if fastest else ""
        prefix = f"{dist_str} long run" if is_long else f"{dist_str} easy"
        return f"{prefix} with {n} strides{fast_str}"

    if cls == 'tempo':
        tempo_ph = [p for p in effort_phases if p.pace_zone == 'threshold']
        if tempo_ph:
            tp = tempo_ph[0]
            dur_min = tp.duration_s // 60
            pace_str = _fmt_pace(tp.avg_pace_sec_per_mile, use_km)
            tp_dist = tp.distance_m
            clean_miles = tp_dist / METERS_PER_MILE
            if abs(clean_miles - round(clean_miles)) < 0.15 and round(clean_miles) >= 1:
                return f"{dist_str} with {int(round(clean_miles))} at tempo ({pace_str})"
            return f"{dist_str} with {dur_min}-min tempo at {pace_str}"
        return f"{dist_str} tempo"

    if cls == 'threshold_intervals':
        work_phases = [p for p in effort_phases if p.pace_zone == 'threshold']
        if work_phases:
            n = len(work_phases)
            avg_dur = sum(p.duration_s for p in work_phases) // (n * 60)
            avg_pace = sum(p.avg_pace_sec_per_mile for p in work_phases) / n
            return f"{dist_str} with {n}x{avg_dur}min at threshold ({_fmt_pace(avg_pace, use_km)})"
        return f"{dist_str} threshold intervals"

    if cls == 'track_intervals':
        work_phases = [p for p in effort_phases if p.pace_zone in ('interval', 'repetition')]
        if work_phases:
            n = len(work_phases)
            avg_dist_m = sum(p.distance_m for p in work_phases) / n
            avg_pace = sum(p.avg_pace_sec_per_mile for p in work_phases) / n
            rep_str = _format_rep_distance(avg_dist_m)
            return f"{dist_str} with {n}x{rep_str} at {_fmt_pace(avg_pace, use_km)}"
        return f"{dist_str} intervals"

    if cls == 'progression':
        if len(effort_phases) >= 2:
            start_pace = effort_phases[0].avg_pace_sec_per_mile
            end_pace = effort_phases[-1].avg_pace_sec_per_mile
            if start_pace > 0 and end_pace > 0:
                return f"{dist_str} building from {_fmt_pace(start_pace, use_km)} to {_fmt_pace(end_pace, use_km)}"
        return f"{dist_str} progression"

    if cls == 'hill_repeats':
        hill_accels = [a for a in accels
                       if a.avg_grade is not None and a.avg_grade > 4.0]
        hill_phases = [p for p in effort_phases if p.phase_type == 'hill_effort']
        hill_count = max(len(hill_accels), len(hill_phases))
        if hill_count < 3:
            hill_count = len(accels)
        return f"{dist_str} with {hill_count} hill repeats" if hill_count >= 3 else f"{dist_str} hills"

    if cls == 'fartlek':
        n = len(accels)
        avg_pace = sum(a.avg_pace_sec_per_mile for a in accels) / n if n > 0 else 0
        if n >= 3:
            return f"{dist_str} with {n} surges"
        return f"{dist_str} fartlek"

    if cls == 'long_run_with_tempo':
        tempo_ph = [p for p in effort_phases if p.pace_zone == 'threshold' and p.duration_s > 600]
        if tempo_ph:
            tp = tempo_ph[0]
            dur_min = tp.duration_s // 60
            pace_str = _fmt_pace(tp.avg_pace_sec_per_mile, use_km)
            return f"{dist_str} long run with {dur_min} minutes at tempo ({pace_str})"
        return f"{dist_str} long run with tempo"

    if cls == 'long_run_with_strides':
        n = len(accels)
        return f"{dist_str} long run with {n} strides"

    if cls == 'gray_zone_run':
        avg_pace = _overall_avg_pace(effort_phases)
        if avg_pace > 0:
            return f"{dist_str} at {_fmt_pace(avg_pace, use_km)}"
        return f"{dist_str} run"

    if cls == 'over_under':
        return f"{dist_str} over/unders"

    if cls == 'easy_run':
        if is_long:
            avg_pace = _overall_avg_pace(effort_phases)
            if avg_pace > 0 and pace_profile:
                easy_ceil = pace_profile._easy_ceiling()
                if avg_pace < easy_ceil:
                    return f"{dist_str} long run at {_fmt_pace(avg_pace, use_km)}"
            return f"{dist_str} long run"
        if is_medium_long:
            avg_pace = _overall_avg_pace(effort_phases)
            if avg_pace > 0:
                return f"{dist_str} medium-long at {_fmt_pace(avg_pace, use_km)}"
            return f"{dist_str} medium-long"
        avg_pace = _overall_avg_pace(effort_phases)
        if avg_pace > 0:
            return f"{dist_str} easy at {_fmt_pace(avg_pace, use_km)}"
        return f"{dist_str} easy"

    if cls == 'long_run':
        avg_pace = _overall_avg_pace(effort_phases)
        if avg_pace > 0:
            return f"{dist_str} long run at {_fmt_pace(avg_pace, use_km)}"
        return f"{dist_str} long run"

    if cls == 'medium_long_run':
        avg_pace = _overall_avg_pace(effort_phases)
        if avg_pace > 0:
            return f"{dist_str} medium-long at {_fmt_pace(avg_pace, use_km)}"
        return f"{dist_str} medium-long"

    return None


def _should_suppress(shape: RunShape, total_dist_m: float, total_dur_s: float) -> bool:
    """Return True when the sentence should be suppressed."""
    cls = shape.summary.workout_classification
    if cls is None:
        return True
    if cls == 'anomaly':
        return True
    if total_dist_m < METERS_PER_MILE * 0.9 or total_dur_s < 480:
        return True
    if shape.summary.total_phases > 8:
        return True
    return False


def _is_long_run(duration_s: float, median_s: Optional[float]) -> bool:
    if median_s and median_s > 0:
        return duration_s > 2.0 * median_s
    return duration_s > 5400  # 90 min fallback

def _is_medium_long(duration_s: float, median_s: Optional[float]) -> bool:
    if median_s and median_s > 0:
        return 1.65 * median_s < duration_s <= 2.0 * median_s
    return 3600 < duration_s <= 5400


def _format_distance(meters: float, use_km: bool = False) -> str:
    if use_km:
        km = meters / 1000.0
        if abs(km - round(km)) < 0.15:
            return f"{int(round(km))} km"
        return f"{round(km * 2) / 2:.1f} km".rstrip('0').rstrip('.')
    miles = meters / METERS_PER_MILE
    if abs(miles - round(miles)) < 0.15:
        return f"{int(round(miles))} mile{'s' if round(miles) != 1 else ''}"
    half = round(miles * 2) / 2
    if half == int(half):
        return f"{int(half)} miles"
    return f"{half} miles"


def _fmt_pace(sec_per_mile: float, use_km: bool = False) -> str:
    if use_km:
        sec_per_km = sec_per_mile / 1.60934
        m, s = divmod(int(sec_per_km), 60)
        return f"{m}:{s:02d}/km"
    m, s = divmod(int(sec_per_mile), 60)
    return f"{m}:{s:02d}"


def _format_rep_distance(meters: float) -> str:
    """Format rep distance to nearest standard track distance."""
    standards = [(200, "200m"), (400, "400m"), (600, "600m"), (800, "800m"),
                 (1000, "1000m"), (1200, "1200m"), (1600, "mile")]
    for std_m, label in standards:
        if abs(meters - std_m) < std_m * 0.15:
            return label
    if meters > 1400:
        miles = meters / METERS_PER_MILE
        return f"{round(miles * 2) / 2:.1f}mi".rstrip('0').rstrip('.')
    return f"{int(round(meters / 100) * 100)}m"


def _overall_avg_pace(effort_phases: List[Phase]) -> float:
    total_time = sum(p.duration_s for p in effort_phases if p.duration_s > 0)
    total_dist = sum(p.distance_m for p in effort_phases if p.distance_m > 0)
    if total_dist > 0 and total_time > 0:
        avg_velocity = total_dist / total_time
        if avg_velocity > 0:
            return METERS_PER_MILE / avg_velocity
    paces = [p.avg_pace_sec_per_mile for p in effort_phases if p.avg_pace_sec_per_mile > 0]
    return sum(paces) / len(paces) if paces else 0
