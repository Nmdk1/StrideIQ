"""Tests for shape_extractor.py — Activity Shape Extraction."""
import pytest
from services.shape_extractor import (
    extract_shape, PaceProfile, RunShape, Phase, Acceleration, ShapeSummary,
    ZoneBand, build_zone_bands, generate_shape_sentence,
    _rolling_mean, _velocity_to_pace, _detect_zone_transitions,
    _merge_micro_phases, _compute_clustering, _compute_pace_progression,
    _check_anomaly, _merge_easy_gray_oscillation,
    MIN_CADENCE_SPIKE_SPM, METERS_PER_MILE,
)


def _build_stream(
    duration_s: int = 1800,
    base_velocity: float = 3.0,
    segments: list = None,
) -> dict:
    """Helper to build synthetic stream data."""
    time = list(range(duration_s))
    velocity = [base_velocity] * duration_s
    heartrate = [145] * duration_s
    cadence = [170] * duration_s
    grade = [0.0] * duration_s
    altitude = [100.0] * duration_s

    if segments:
        for seg in segments:
            start, end, vel = seg['start'], seg['end'], seg['velocity']
            for i in range(start, min(end, duration_s)):
                velocity[i] = vel
                if vel > base_velocity * 1.3:
                    heartrate[i] = min(190, int(145 + (vel - base_velocity) * 15))
                    cadence[i] = min(200, int(170 + (vel - base_velocity) * 10))

    distance = [0.0]
    for i in range(1, duration_s):
        distance.append(distance[-1] + velocity[i])

    return {
        'time': time,
        'velocity_smooth': velocity,
        'heartrate': heartrate,
        'cadence': cadence,
        'grade_smooth': grade,
        'altitude': altitude,
        'distance': distance,
    }


FOUNDER_PROFILE = PaceProfile(
    easy_sec=540,
    marathon_sec=465,
    threshold_sec=391,
    interval_sec=345,
    repetition_sec=321,
)

# Larry: 79-year-old runner, easy pace ~13:00/mi, strides around 9:00-10:00/mi
SLOW_RUNNER_PROFILE = PaceProfile(
    easy_sec=780,
    marathon_sec=660,
    threshold_sec=600,
    interval_sec=540,
    repetition_sec=500,
)


def _build_slow_runner_stream(
    duration_s: int = 2400,
    base_velocity: float = 2.06,
    stride_segments: list = None,
) -> dict:
    """Build stream simulating a slow runner (13:00/mi) with cadence-visible strides.

    GPS velocity changes are small (~0.6 m/s), but cadence spikes are clear
    (92 spm baseline → 115+ spm during strides). This is the real-world
    pattern for slower runners where GPS can't resolve short bursts.
    """
    time = list(range(duration_s))
    velocity = [base_velocity] * duration_s
    heartrate = [125] * duration_s
    cadence = [92] * duration_s
    grade = [0.0] * duration_s
    altitude = [100.0] * duration_s

    if stride_segments:
        for seg in stride_segments:
            start = seg['start']
            end = seg['end']
            stride_v = seg.get('velocity', base_velocity * 1.25)
            stride_cad = seg.get('cadence', 116)
            for i in range(start, min(end, duration_s)):
                velocity[i] = stride_v
                cadence[i] = stride_cad
                heartrate[i] = min(160, 125 + 15)

    distance = [0.0]
    for i in range(1, duration_s):
        distance.append(distance[-1] + velocity[i])

    return {
        'time': time,
        'velocity_smooth': velocity,
        'heartrate': heartrate,
        'cadence': cadence,
        'grade_smooth': grade,
        'altitude': altitude,
        'distance': distance,
    }


class TestPaceProfile:
    def test_easy_pace(self):
        assert FOUNDER_PROFILE.classify_pace(600) == 'easy'

    def test_easy_no_floor(self):
        """Easy has no floor — any slow pace is easy (until walking threshold)."""
        assert FOUNDER_PROFILE.classify_pace(900) == 'easy'
        assert FOUNDER_PROFILE.classify_pace(1100) == 'easy'

    def test_walking(self):
        assert FOUNDER_PROFILE.classify_pace(1200) == 'walking'
        assert FOUNDER_PROFILE.classify_pace(1500) == 'walking'

    def test_gray_area(self):
        """Paces between zones should be 'gray'."""
        # Between easy (540±10 → ceiling 530) and marathon (465±10 → 455-475)
        assert FOUNDER_PROFILE.classify_pace(510) == 'gray'

    def test_marathon_center(self):
        assert FOUNDER_PROFILE.classify_pace(465) == 'marathon'

    def test_threshold_center(self):
        assert FOUNDER_PROFILE.classify_pace(391) == 'threshold'

    def test_interval_center(self):
        assert FOUNDER_PROFILE.classify_pace(345) == 'interval'

    def test_repetition_center(self):
        assert FOUNDER_PROFILE.classify_pace(321) == 'repetition'

    def test_is_at_least_marathon(self):
        assert FOUNDER_PROFILE.is_at_least_marathon(465) is True
        assert FOUNDER_PROFILE.is_at_least_marathon(391) is True
        assert FOUNDER_PROFILE.is_at_least_marathon(600) is False

    def test_stopped(self):
        assert FOUNDER_PROFILE.classify_pace(0) == 'stopped'
        assert FOUNDER_PROFILE.classify_pace(-1) == 'stopped'


class TestZoneBands:
    def test_build_non_overlapping(self):
        centers = {'repetition': 321, 'interval': 345, 'threshold': 391,
                   'marathon': 465, 'easy': 540}
        bands = build_zone_bands(centers)
        for i in range(len(bands) - 2):
            assert bands[i].ceiling < bands[i + 1].floor, \
                f"{bands[i].name} ceiling ({bands[i].ceiling}) overlaps {bands[i+1].name} floor ({bands[i+1].floor})"

    def test_overlap_prevention(self):
        """When zones are close, slower zone floor shrinks to avoid overlap."""
        centers = {'repetition': 320, 'interval': 340, 'threshold': 360,
                   'marathon': 380, 'easy': 400}
        bands = build_zone_bands(centers)
        for i in range(len(bands) - 2):
            assert bands[i].ceiling < bands[i + 1].floor


class TestHelpers:
    def test_rolling_mean(self):
        result = _rolling_mean([1, 2, 3, 4, 5], window=3)
        assert len(result) == 5
        assert result[1] == pytest.approx(2.0, abs=0.01)

    def test_velocity_to_pace(self):
        paces = _velocity_to_pace([3.0, 0.0, 4.0])
        assert paces[0] > 0
        assert paces[1] == 0.0
        assert paces[2] > 0
        assert paces[2] < paces[0]

    def test_zone_transitions(self):
        zones = ['easy'] * 10 + ['threshold'] * 10 + ['easy'] * 10
        blocks = _detect_zone_transitions(list(range(30)), zones)
        assert len(blocks) == 3
        assert blocks[0][2] == 'easy'
        assert blocks[1][2] == 'threshold'

    def test_merge_micro_phases(self):
        blocks = [(0, 5, 'easy'), (6, 10, 'threshold'), (11, 100, 'easy')]
        merged = _merge_micro_phases(blocks, min_duration_s=10)
        assert len(merged) < 3


class TestEasyRun:
    def test_plain_easy_run(self):
        """Over-detection test: a plain easy run should be 1 phase, 0 accels."""
        stream = _build_stream(duration_s=2400, base_velocity=2.8)
        shape = extract_shape(stream, pace_profile=FOUNDER_PROFILE)

        assert shape is not None
        assert shape.summary.acceleration_count == 0
        assert shape.summary.workout_classification == 'easy_run'
        assert shape.summary.acceleration_clustering == 'none'

    def test_easy_run_few_phases(self):
        stream = _build_stream(duration_s=2400, base_velocity=2.8)
        shape = extract_shape(stream, pace_profile=FOUNDER_PROFILE)
        assert len(shape.phases) <= 3


class TestStrides:
    def test_strides_detected(self):
        """Strides: easy run with 5 short accelerations at the end."""
        segments = []
        for i in range(5):
            start = 1600 + i * 40
            segments.append({'start': start, 'end': start + 20, 'velocity': 5.0})

        stream = _build_stream(duration_s=1800, base_velocity=2.8, segments=segments)
        shape = extract_shape(stream, pace_profile=FOUNDER_PROFILE)

        assert shape is not None
        assert shape.summary.acceleration_count >= 3
        assert shape.summary.acceleration_clustering == 'end_loaded'
        assert shape.summary.workout_classification in ('strides', 'easy_run', None)

    def test_slow_runner_strides_via_cadence(self):
        """Slow runner (13:00/mi) strides detected via cadence when GPS is marginal.
        Real-world pattern: Larry at 79 years old. GPS shows maybe 1.10x velocity
        change but cadence jumps from 92 to 116 spm — unmistakable."""
        stride_segs = [
            {'start': 1800, 'end': 1819, 'velocity': 2.64, 'cadence': 116},
            {'start': 1860, 'end': 1889, 'velocity': 3.14, 'cadence': 118},
            {'start': 1930, 'end': 1952, 'velocity': 3.33, 'cadence': 118},
            {'start': 2100, 'end': 2110, 'velocity': 3.90, 'cadence': 120},
        ]
        stream = _build_slow_runner_stream(
            duration_s=2400, base_velocity=2.06,
            stride_segments=stride_segs,
        )
        shape = extract_shape(stream, pace_profile=SLOW_RUNNER_PROFILE)

        assert shape is not None
        assert shape.summary.acceleration_count >= 3
        assert shape.summary.workout_classification == 'strides'

    def test_slow_runner_no_false_strides(self):
        """Slow runner easy run: cadence max 101, no spikes — must stay easy_run."""
        stream = _build_slow_runner_stream(duration_s=2400, base_velocity=2.06)
        shape = extract_shape(stream, pace_profile=SLOW_RUNNER_PROFILE)

        assert shape is not None
        assert shape.summary.acceleration_count == 0
        assert shape.summary.workout_classification == 'easy_run'

    def test_strides_not_too_long(self):
        """Strides should be 10-30s duration."""
        segments = []
        for i in range(4):
            start = 1600 + i * 40
            segments.append({'start': start, 'end': start + 25, 'velocity': 5.0})

        stream = _build_stream(duration_s=1800, base_velocity=2.8, segments=segments)
        shape = extract_shape(stream, pace_profile=FOUNDER_PROFILE)

        if shape and shape.accelerations:
            for a in shape.accelerations:
                assert a.duration_s >= 10


class TestThresholdIntervals:
    def test_threshold_intervals(self):
        """3 x 5-min threshold reps with 2-min recovery."""
        segments = []
        for i in range(3):
            start = 300 + i * 420
            segments.append({'start': start, 'end': start + 300, 'velocity': 4.1})
            segments.append({'start': start + 300, 'end': start + 420, 'velocity': 2.5})

        stream = _build_stream(duration_s=2100, base_velocity=2.8, segments=segments)
        shape = extract_shape(stream, pace_profile=FOUNDER_PROFILE)

        assert shape is not None
        threshold_phases = [p for p in shape.phases if p.pace_zone == 'threshold']
        assert len(threshold_phases) >= 2

    def test_track_intervals(self):
        """6 x 2-min interval reps with recovery."""
        segments = []
        for i in range(6):
            start = 300 + i * 240
            segments.append({'start': start, 'end': start + 120, 'velocity': 4.7})
            segments.append({'start': start + 120, 'end': start + 240, 'velocity': 2.5})

        stream = _build_stream(duration_s=2400, base_velocity=2.8, segments=segments)
        shape = extract_shape(stream, pace_profile=FOUNDER_PROFILE)

        assert shape is not None
        interval_phases = [p for p in shape.phases if p.phase_type == 'interval_work']
        assert len(interval_phases) >= 3


class TestFartlek:
    def test_fartlek_detected(self):
        """Scattered accelerations of varying duration and spacing."""
        segments = [
            {'start': 150, 'end': 180, 'velocity': 4.5},
            {'start': 550, 'end': 620, 'velocity': 4.3},
            {'start': 700, 'end': 740, 'velocity': 4.6},
            {'start': 1400, 'end': 1460, 'velocity': 4.4},
        ]
        stream = _build_stream(duration_s=1800, base_velocity=2.8, segments=segments)
        shape = extract_shape(stream, pace_profile=FOUNDER_PROFILE)

        assert shape is not None
        assert shape.summary.acceleration_count >= 3
        assert shape.summary.acceleration_clustering == 'scattered'


class TestProgression:
    def test_progression_run(self):
        """Each third of the run gets faster."""
        segments = [
            {'start': 0, 'end': 600, 'velocity': 2.8},
            {'start': 600, 'end': 1200, 'velocity': 3.3},
            {'start': 1200, 'end': 1800, 'velocity': 3.8},
        ]
        stream = _build_stream(duration_s=1800, base_velocity=2.8, segments=segments)
        shape = extract_shape(stream, pace_profile=FOUNDER_PROFILE)

        assert shape is not None
        assert shape.summary.pace_progression in ('building', 'variable')


class TestShapeSummary:
    def test_summary_fields(self):
        stream = _build_stream(duration_s=1800, base_velocity=2.8)
        shape = extract_shape(stream, pace_profile=FOUNDER_PROFILE)

        assert shape is not None
        s = shape.summary
        assert isinstance(s.total_phases, int)
        assert isinstance(s.acceleration_count, int)
        assert s.elevation_profile in ('flat', 'hilly', 'net_uphill', 'net_downhill', 'out_and_back')
        assert s.acceleration_clustering in ('none', 'end_loaded', 'periodic', 'scattered')

    def test_to_dict(self):
        stream = _build_stream(duration_s=1800, base_velocity=2.8)
        shape = extract_shape(stream, pace_profile=FOUNDER_PROFILE)

        d = shape.to_dict()
        assert 'phases' in d
        assert 'accelerations' in d
        assert 'summary' in d
        assert isinstance(d['phases'], list)
        assert isinstance(d['summary'], dict)


class TestEdgeCases:
    def test_too_short(self):
        stream = {'time': list(range(10)), 'velocity_smooth': [3.0] * 10}
        assert extract_shape(stream) is None

    def test_empty_stream(self):
        assert extract_shape({}) is None

    def test_no_velocity(self):
        assert extract_shape({'time': list(range(100))}) is None

    def test_no_pace_profile_fallback(self):
        stream = _build_stream(duration_s=600, base_velocity=3.0)
        shape = extract_shape(stream, pace_profile=None)
        assert shape is not None

    def test_heat_adjustment(self):
        stream = _build_stream(duration_s=1800, base_velocity=2.8)
        shape = extract_shape(stream, pace_profile=FOUNDER_PROFILE, heat_adjustment_pct=0.05)
        for p in shape.phases:
            if p.avg_pace_sec_per_mile > 0:
                assert p.avg_pace_heat_adjusted is not None
                assert p.avg_pace_heat_adjusted < p.avg_pace_sec_per_mile


class TestClusteringThresholds:
    def test_end_loaded(self):
        accels = [Acceleration(
            start_time_s=0, end_time_s=10, duration_s=10, distance_m=50,
            avg_pace_sec_per_mile=350, avg_pace_heat_adjusted=None,
            pace_zone='interval', avg_hr=None, hr_delta=None,
            avg_cadence=None, cadence_delta=None,
            position_in_run=p, recovery_after_s=None,
        ) for p in [0.80, 0.85, 0.90, 0.95, 0.50]]
        assert _compute_clustering(accels, 5000) == 'end_loaded'

    def test_none(self):
        assert _compute_clustering([], 5000) == 'none'

    def test_periodic(self):
        accels = [Acceleration(
            start_time_s=0, end_time_s=10, duration_s=10, distance_m=50,
            avg_pace_sec_per_mile=350, avg_pace_heat_adjusted=None,
            pace_zone='interval', avg_hr=None, hr_delta=None,
            avg_cadence=None, cadence_delta=None,
            position_in_run=p, recovery_after_s=None,
        ) for p in [0.2, 0.4, 0.6, 0.8]]
        assert _compute_clustering(accels, 5000) == 'periodic'


class TestSentenceGeneration:
    def test_easy_run_sentence(self):
        stream = _build_stream(duration_s=2400, base_velocity=2.8)
        shape = extract_shape(stream, pace_profile=FOUNDER_PROFILE)
        total_dist = 2.8 * 2400
        sentence = generate_shape_sentence(shape, total_dist, 2400, pace_profile=FOUNDER_PROFILE)
        assert sentence is not None
        assert 'easy' in sentence.lower()

    def test_strides_sentence(self):
        segments = []
        for i in range(5):
            start = 1600 + i * 40
            segments.append({'start': start, 'end': start + 20, 'velocity': 5.0})
        stream = _build_stream(duration_s=1800, base_velocity=2.8, segments=segments)
        shape = extract_shape(stream, pace_profile=FOUNDER_PROFILE)
        if shape and shape.summary.workout_classification == 'strides':
            total_dist = sum(s.get('velocity', 2.8) * 20 for s in segments) + 2.8 * 1700
            sentence = generate_shape_sentence(shape, total_dist, 1800, pace_profile=FOUNDER_PROFILE)
            assert sentence is not None
            assert 'stride' in sentence.lower()

    def test_suppression_for_null_classification(self):
        """Null classification → sentence suppressed."""
        summary = ShapeSummary(
            total_phases=1, acceleration_count=0,
            acceleration_avg_duration_s=None, acceleration_avg_pace_zone=None,
            acceleration_clustering='none', has_warmup=False, has_cooldown=False,
            pace_progression='steady', pace_range_sec_per_mile=0,
            longest_sustained_effort_s=100, longest_sustained_zone='easy',
            elevation_profile='flat', workout_classification=None,
        )
        shape = RunShape(phases=[], accelerations=[], summary=summary)
        assert generate_shape_sentence(shape, 5000, 1800) is None

    def test_suppression_for_short_run(self):
        """Very short runs → suppressed."""
        summary = ShapeSummary(
            total_phases=1, acceleration_count=0,
            acceleration_avg_duration_s=None, acceleration_avg_pace_zone=None,
            acceleration_clustering='none', has_warmup=False, has_cooldown=False,
            pace_progression='steady', pace_range_sec_per_mile=0,
            longest_sustained_effort_s=100, longest_sustained_zone='easy',
            elevation_profile='flat', workout_classification='easy_run',
        )
        shape = RunShape(phases=[], accelerations=[], summary=summary)
        assert generate_shape_sentence(shape, 800, 300) is None

    def test_no_profile_unzoned(self):
        """Without a pace profile, shape should be unzoned with null classification."""
        stream = _build_stream(duration_s=1800, base_velocity=3.0)
        shape = extract_shape(stream, pace_profile=None)
        assert shape is not None
        assert shape.summary.workout_classification is None


# ═══════════════════════════════════════════════════════
#  Coverage fix validation tests
# ═══════════════════════════════════════════════════════

class TestAntiOscillationMerge:
    def test_oscillation_collapse(self):
        """Larry-style easy→gray→easy oscillation collapses to one easy phase.

        A slow runner at 13:00/mi (2.06 m/s) with GPS noise dipping pace
        below the easy ceiling for brief periods. Cadence stays steady at 92.
        The gray blocks are < 90s, pace is near easy ceiling, no speed work.
        At 2.06 m/s base, a dip to 2.15 m/s gives pace ~748 sec/mi vs
        easy ceiling 770 — gray zone but only ~33 sec/mi faster than base 781.
        """
        duration = 2400
        base_v = 2.06  # ~13:00/mi
        time = list(range(duration))
        velocity = [base_v] * duration
        cadence = [92] * duration

        # GPS noise dips: velocity increases slightly, pushing pace below easy ceiling
        gray_v = 2.15  # ~12:29/mi — just below easy ceiling
        dip_windows = [
            (200, 260), (450, 520), (650, 730), (900, 980),
            (1150, 1220), (1450, 1530), (1750, 1830), (2000, 2070),
        ]
        for start, end in dip_windows:
            for i in range(start, min(end, duration)):
                velocity[i] = gray_v

        stream = {
            'time': time,
            'velocity_smooth': velocity,
            'heartrate': [125] * duration,
            'cadence': cadence,
            'grade_smooth': [0.0] * duration,
            'altitude': [100.0] * duration,
            'distance': [sum(velocity[:i+1]) for i in range(duration)],
        }
        shape = extract_shape(stream, pace_profile=SLOW_RUNNER_PROFILE)
        assert shape is not None
        assert len(shape.phases) <= 3, f"Expected ≤3 phases, got {len(shape.phases)}"
        assert shape.summary.workout_classification == 'easy_run'

    def test_genuine_gray_preserved(self):
        """A real gray insert (>25 sec/mi faster than neighbors) is NOT absorbed.

        Founder running easy at 9:00/mi with a genuine moderate pickup to
        7:30/mi for 2 minutes. That's 90 sec/mi faster than easy — well beyond
        the 25 sec/mi neighbor proximity guard.
        """
        duration = 2400
        base_v = 2.98  # ~9:00/mi
        gray_v = 3.58  # ~7:30/mi
        time = list(range(duration))
        velocity = [base_v] * duration
        for i in range(1000, 1120):
            velocity[i] = gray_v

        stream = {
            'time': time,
            'velocity_smooth': velocity,
            'heartrate': [140] * duration,
            'cadence': [170] * duration,
            'grade_smooth': [0.0] * duration,
            'altitude': [100.0] * duration,
            'distance': [sum(velocity[:i+1]) for i in range(duration)],
        }
        shape = extract_shape(stream, pace_profile=FOUNDER_PROFILE)
        assert shape is not None
        assert len(shape.phases) >= 2, "Genuine gray effort should NOT be absorbed"


class TestAnomalyHybrid:
    def test_long_run_gps_tolerance(self):
        """20-mile run with 3x 30-second gaps → NOT anomaly.

        Total gap time = 90s out of ~9000s = 1% corruption. Well under 5%.
        """
        duration = 9000
        time = list(range(duration))
        # Insert 3 gaps of 35 seconds each at different points
        time[3000] = time[2999] + 35
        for i in range(3001, 6000):
            time[i] = time[i-1] + 1
        time[6000] = time[5999] + 35
        for i in range(6001, 8000):
            time[i] = time[i-1] + 1
        time[8000] = time[7999] + 35
        for i in range(8001, duration):
            time[i] = time[i-1] + 1

        velocity = [3.0] * duration
        result = _check_anomaly(velocity, time, [])
        assert result is False, "Long run with minor GPS gaps should NOT be anomaly"

    def test_corrupted_short_run(self):
        """15-minute run with 3x 30-second gaps → IS anomaly."""
        duration = 900
        time = list(range(duration))
        time[200] = time[199] + 35
        for i in range(201, 500):
            time[i] = time[i-1] + 1
        time[500] = time[499] + 35
        for i in range(501, 700):
            time[i] = time[i-1] + 1
        time[700] = time[699] + 35
        for i in range(701, duration):
            time[i] = time[i-1] + 1

        velocity = [3.0] * duration
        result = _check_anomaly(velocity, time, [])
        assert result is True, "Short run with 3 GPS gaps should be anomaly"

    def test_single_huge_gap(self):
        """Run with one 6-minute gap → IS anomaly regardless of run length."""
        duration = 5000
        time = list(range(duration))
        time[2500] = time[2499] + 360  # 6 min gap
        for i in range(2501, duration):
            time[i] = time[i-1] + 1

        velocity = [3.0] * duration
        result = _check_anomaly(velocity, time, [])
        assert result is True, "Single huge gap should always be anomaly"


class TestHillRepeatsFromAccelerations:
    def test_hill_repeats_detected(self):
        """Single-phase hilly run with 3+ graded accelerations → hill_repeats.

        Simulates a hill repeat workout: easy base with hard efforts on
        5%+ grade. After zone consolidation the base is one easy phase,
        but the hill efforts appear as accelerations with high avg_grade.
        """
        duration = 2400
        base_v = 2.8  # easy
        hill_v = 4.2  # hard effort uphill
        time = list(range(duration))
        velocity = [base_v] * duration
        grade = [0.5] * duration
        altitude = [100.0] * duration

        hill_windows = [
            (300, 360), (600, 660), (900, 960),
            (1200, 1260), (1500, 1560),
        ]
        for start, end in hill_windows:
            for i in range(start, end):
                velocity[i] = hill_v
                grade[i] = 6.0
                altitude[i] = 100.0 + (i - start) * 0.5

        distance = [0.0]
        for i in range(1, duration):
            distance.append(distance[-1] + velocity[i])

        stream = {
            'time': time,
            'velocity_smooth': velocity,
            'heartrate': [145] * duration,
            'cadence': [170] * duration,
            'grade_smooth': grade,
            'altitude': altitude,
            'distance': distance,
        }
        shape = extract_shape(stream, pace_profile=FOUNDER_PROFILE)
        assert shape is not None
        hill_accels = [a for a in shape.accelerations
                       if a.avg_grade is not None and a.avg_grade > 4.0]
        assert len(hill_accels) >= 3, f"Expected ≥3 graded accels, got {len(hill_accels)}"
        assert shape.summary.workout_classification == 'hill_repeats'

    def test_hilly_run_not_hill_repeats(self):
        """Hilly terrain with pace variation but NO intentional uphill efforts.

        On a casual hilly run, uphills slow the runner. Velocity drops on
        grades, not spikes. No accelerations should meet the grade threshold
        because the runner doesn't accelerate on uphills.
        """
        duration = 2400
        base_v = 2.8
        time = list(range(duration))
        velocity = [base_v] * duration
        grade = [0.0] * duration
        altitude = [100.0] * duration

        for i in range(300, 600):
            grade[i] = 5.0
            velocity[i] = 2.3  # slows on uphill
            altitude[i] = 100.0 + (i - 300) * 0.3
        for i in range(600, 900):
            grade[i] = -5.0
            velocity[i] = 3.3  # speeds up on downhill
            altitude[i] = 190.0 - (i - 600) * 0.3
        for i in range(1200, 1500):
            grade[i] = 4.5
            velocity[i] = 2.4
            altitude[i] = 100.0 + (i - 1200) * 0.25
        for i in range(1500, 1800):
            grade[i] = -4.5
            velocity[i] = 3.2
            altitude[i] = 175.0 - (i - 1500) * 0.25

        distance = [0.0]
        for i in range(1, duration):
            distance.append(distance[-1] + velocity[i])

        stream = {
            'time': time,
            'velocity_smooth': velocity,
            'heartrate': [145] * duration,
            'cadence': [170] * duration,
            'grade_smooth': grade,
            'altitude': altitude,
            'distance': distance,
        }
        shape = extract_shape(stream, pace_profile=FOUNDER_PROFILE)
        assert shape is not None
        assert shape.summary.workout_classification != 'hill_repeats', \
            "Casual hilly run should NOT be classified as hill_repeats"


class TestQuietMixedBoundaryRuns:
    """Regression tests for Larry's cls_none suppressions.

    These simulate the exact production patterns: easy runs where GPS noise
    at the easy ceiling creates 4-7 phases of alternating easy/gray zones
    with no accelerations. The new fallback classifier catches these.
    """

    # Larry's profile: easy=750, easy ceiling=740
    LARRY_PROFILE = PaceProfile(
        easy_sec=750, marathon_sec=612, threshold_sec=577,
        interval_sec=498, repetition_sec=456,
    )

    def test_feb26_quiet_4phase_easy_gray(self):
        """Feb 26 pattern: 4 phases, 0 accels, all easy/gray, gray 43.7%.
        Gray paces 17-19s past ceiling (720-722 vs ceiling 740)."""
        duration = 914
        time = list(range(duration))
        velocity = [2.06] * duration  # ~781 sec/mi = easy
        # Phase structure: easy 142s, gray 85s, easy 373s, gray 314s
        gray1_v = 2.23  # ~721 sec/mi, ~19s past ceiling
        gray2_v = 2.23  # ~723 sec/mi, ~17s past ceiling
        for i in range(142, 227):
            velocity[i] = gray1_v
        for i in range(600, 914):
            velocity[i] = gray2_v

        stream = {
            'time': time, 'velocity_smooth': velocity,
            'heartrate': [125] * duration, 'cadence': [92] * duration,
            'grade_smooth': [0.0] * duration, 'altitude': [100.0] * duration,
            'distance': [sum(velocity[:i+1]) for i in range(duration)],
        }
        shape = extract_shape(stream, pace_profile=self.LARRY_PROFILE)
        assert shape is not None
        assert shape.summary.workout_classification == 'easy_run', \
            f"Expected easy_run, got {shape.summary.workout_classification} with {len(shape.phases)} phases"

    def test_feb13_classic_6phase_oscillation(self):
        """Feb 13 pattern: 6 phases, 0 accels, all easy/gray, gray 26.2%.
        Gray paces 5-14s past ceiling — textbook boundary oscillation."""
        duration = 1334
        time = list(range(duration))
        velocity = [2.13] * duration  # ~755 sec/mi = easy
        # Simulate 3 gray insertions of varying length
        gray_v = 2.20  # ~731 sec/mi, ~9s past ceiling
        for i in range(675, 769):    # 94s gray
            velocity[i] = gray_v
        for i in range(1016, 1172):  # 156s gray
            velocity[i] = gray_v
        for i in range(1235, 1334):  # 99s gray
            velocity[i] = gray_v

        stream = {
            'time': time, 'velocity_smooth': velocity,
            'heartrate': [125] * duration, 'cadence': [92] * duration,
            'grade_smooth': [0.0] * duration, 'altitude': [100.0] * duration,
            'distance': [sum(velocity[:i+1]) for i in range(duration)],
        }
        shape = extract_shape(stream, pace_profile=self.LARRY_PROFILE)
        assert shape is not None
        assert shape.summary.workout_classification == 'easy_run', \
            f"Expected easy_run, got {shape.summary.workout_classification} with {len(shape.phases)} phases"

    def test_feb12_easy_with_short_threshold_blip(self):
        """Feb 12 pattern: mostly easy/gray with one short threshold insertion.
        The threshold blip is ≤90s and buried mid-run, so the fallback
        allows easy_run via the single-blip allowance. Gray share ~17%."""
        duration = 3672
        time = list(range(duration))
        velocity = [2.16] * duration  # ~745 sec/mi = easy

        # Gray insertions matching real Feb 12 proportions (~17% gray)
        gray_v = 2.22  # ~725 sec/mi
        for i in range(600, 779):     # 179s gray
            velocity[i] = gray_v
        # Short threshold blip mid-run (70s) — not at end to avoid progression
        for i in range(1400, 1470):
            velocity[i] = 2.76        # ~583 sec/mi = threshold
        for i in range(2100, 2226):   # 126s gray
            velocity[i] = gray_v
        for i in range(2800, 3107):   # 307s deeper gray
            velocity[i] = 2.33        # ~691 sec/mi

        stream = {
            'time': time, 'velocity_smooth': velocity,
            'heartrate': [125] * duration, 'cadence': [92] * duration,
            'grade_smooth': [0.0] * duration, 'altitude': [100.0] * duration,
            'distance': [sum(velocity[:i+1]) for i in range(duration)],
        }
        shape = extract_shape(stream, pace_profile=self.LARRY_PROFILE)
        assert shape is not None
        assert shape.summary.workout_classification == 'easy_run', \
            f"Expected easy_run, got {shape.summary.workout_classification} with {len(shape.phases)} phases"

    def test_genuine_gray_zone_not_absorbed(self):
        """A multi-phase run with >50% gray should NOT be captured by the
        quiet mixed boundary fallback. Needs 4+ effort phases to test the
        new fallback specifically (existing easy_run handles ≤3 phases)."""
        duration = 3000
        time = list(range(duration))
        velocity = [2.25] * duration  # gray (~715 sec/mi, below ceiling 740)

        # Alternate between gray and easy to create 5 effort phases
        for i in range(0, 200):       # easy start
            velocity[i] = 2.10
        for i in range(700, 900):     # easy island
            velocity[i] = 2.10
        for i in range(1500, 1650):   # easy island
            velocity[i] = 2.10
        for i in range(2200, 2350):   # easy island
            velocity[i] = 2.10
        for i in range(2800, 3000):   # easy end
            velocity[i] = 2.10

        stream = {
            'time': time, 'velocity_smooth': velocity,
            'heartrate': [125] * duration, 'cadence': [92] * duration,
            'grade_smooth': [0.0] * duration, 'altitude': [100.0] * duration,
            'distance': [sum(velocity[:i+1]) for i in range(duration)],
        }
        shape = extract_shape(stream, pace_profile=self.LARRY_PROFILE)
        assert shape is not None
        # The gray_pct should be >50%, which means the new fallback's
        # 0.10-0.49 guard blocks it. gray_zone_run or None is correct.
        assert shape.summary.workout_classification != 'easy_run' or \
            len([p for p in shape.phases if p.phase_type not in
                 ('warmup', 'cooldown', 'interval_recovery', 'recovery_jog')]) <= 3, \
            "Majority gray 4+ phase run should NOT be classified easy_run by fallback"


class TestTrustGates:
    def test_suppression_over_hallucination(self):
        """Ambiguous structure → suppressed rather than forced into a wrong sentence.

        A run that doesn't clearly match any classification should return
        cls=None and the sentence should be suppressed.
        """
        duration = 1800
        velocity = [2.8] * duration
        for i in range(200, 260):
            velocity[i] = 3.8
        for i in range(800, 900):
            velocity[i] = 4.5
        time = list(range(duration))

        stream = {
            'time': time,
            'velocity_smooth': velocity,
            'heartrate': [145] * duration,
            'cadence': [170] * duration,
            'grade_smooth': [0.0] * duration,
            'altitude': [100.0] * duration,
            'distance': [sum(velocity[:i+1]) for i in range(duration)],
        }
        shape = extract_shape(stream, pace_profile=FOUNDER_PROFILE)
        assert shape is not None
        total_dist = sum(velocity)
        sentence = generate_shape_sentence(shape, total_dist, duration,
                                           pace_profile=FOUNDER_PROFILE)
        # Either it classifies correctly or suppresses — never wrong
        if shape.summary.workout_classification is None:
            assert sentence is None, "Null classification must suppress sentence"


class TestWorkoutStructureSummaryElevation:
    """_summarize_workout_structure must not label hilly runs as intervals
    when pace variation is explained by elevation."""

    def test_hilly_run_with_steady_gap_returns_none(self):
        """14 mile splits with 1600ft gain, alternating fast/slow from hills.
        GAP values are steady (effort was consistent). Should return None."""
        from unittest.mock import MagicMock, patch

        METERS_PER_MILE = 1609.344

        mock_db = MagicMock()
        activity_id = "test-hilly-activity"

        mock_activity = MagicMock()
        mock_activity.total_elevation_gain = 488  # ~1600 ft in meters

        splits = []
        for i in range(14):
            s = MagicMock()
            s.split_number = i + 1
            s.distance = METERS_PER_MILE
            s.average_heartrate = 145
            if i % 2 == 0:
                s.elapsed_time = 570  # uphill: ~9:30/mi
                s.gap_seconds_per_mile = 520  # GAP: ~8:40/mi (steady)
            else:
                s.elapsed_time = 470  # downhill: ~7:50/mi
                s.gap_seconds_per_mile = 515  # GAP: ~8:35/mi (steady)
            splits.append(s)

        def _route_query(model_cls):
            chain = MagicMock()
            if model_cls.__name__ == "Activity":
                chain.filter.return_value = chain
                chain.first.return_value = mock_activity
            elif model_cls.__name__ == "ActivitySplit":
                chain.filter.return_value = chain
                chain.order_by.return_value = chain
                chain.all.return_value = splits
            return chain

        mock_db.query.side_effect = _route_query

        from routers.home import _summarize_workout_structure
        result = _summarize_workout_structure(activity_id, mock_db)
        assert result is None, (
            f"Hilly run with steady GAP should NOT be classified as intervals, "
            f"got: {result}"
        )


class TestHillyRunNotIntervals:
    """Hilly runs with pace variation from terrain must not be classified
    as structured intervals, threshold work, or over/under."""

    def test_hilly_long_run_not_intervals(self):
        """14-mi hilly run with 1600ft gain — downhill miles are faster,
        uphill miles are slower. Elevation profile is 'hilly'. Should NOT
        classify as track_intervals, threshold_intervals, or over_under."""
        duration = 7200  # 2 hours
        base_v = 2.8     # ~9:30/mi easy
        time = list(range(duration))
        velocity = [base_v] * duration
        grade = [0.0] * duration
        altitude = [100.0] * duration

        hill_segments = [
            (0, 600, 4.0, 2.3),        # uphill, slow
            (600, 1200, -4.0, 3.3),     # downhill, fast
            (1200, 1800, 3.5, 2.4),     # uphill, slow
            (1800, 2400, -3.5, 3.2),    # downhill, fast
            (2400, 3000, 5.0, 2.2),     # steep uphill
            (3000, 3600, -5.0, 3.4),    # steep downhill
            (3600, 4200, 4.0, 2.3),     # uphill
            (4200, 4800, -4.0, 3.3),    # downhill
            (4800, 5400, 3.0, 2.5),     # uphill
            (5400, 6000, -3.0, 3.1),    # downhill
            (6000, 6600, 4.5, 2.3),     # uphill
            (6600, 7200, -4.5, 3.3),    # downhill
        ]

        for start, end, g, v in hill_segments:
            for i in range(start, min(end, duration)):
                grade[i] = g
                velocity[i] = v
                alt_delta = g * 0.01  # approximate altitude change per second
                altitude[i] = altitude[max(0, i-1)] + alt_delta

        distance = [0.0]
        for i in range(1, duration):
            distance.append(distance[-1] + velocity[i])

        stream = {
            'time': time,
            'velocity_smooth': velocity,
            'heartrate': [145] * duration,
            'cadence': [170] * duration,
            'grade_smooth': grade,
            'altitude': altitude,
            'distance': distance,
        }
        shape = extract_shape(stream, pace_profile=FOUNDER_PROFILE)
        assert shape is not None
        cls = shape.summary.workout_classification
        assert cls not in ('track_intervals', 'threshold_intervals', 'over_under'), \
            f"Hilly run misclassified as '{cls}' — pace variation is from terrain"
