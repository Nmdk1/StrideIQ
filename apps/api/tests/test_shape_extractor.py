"""Tests for shape_extractor.py — Activity Shape Extraction."""
import pytest
from services.shape_extractor import (
    extract_shape, PaceProfile, RunShape, Phase, Acceleration, ShapeSummary,
    ZoneBand, build_zone_bands, generate_shape_sentence,
    _rolling_mean, _velocity_to_pace, _detect_zone_transitions,
    _merge_micro_phases, _compute_clustering, _compute_pace_progression,
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
