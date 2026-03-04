"""Tests for single-pass EMA training load (Racing Fingerprint Pre-Work P3)."""

import uuid
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from services.training_load import TrainingLoadCalculator, LoadSummary, WorkoutStress


def _make_activity(start_date: date, distance_m=10000, duration_s=3600, avg_hr=150, is_dup=False):
    act = MagicMock()
    act.id = uuid.uuid4()
    act.athlete_id = uuid.uuid4()
    act.start_time = datetime.combine(start_date, datetime.min.time())
    act.distance_m = distance_m
    act.duration_s = duration_s
    act.avg_hr = avg_hr
    act.max_hr = 185
    act.average_speed = distance_m / duration_s if duration_s else 0
    act.is_duplicate = is_dup
    act.intensity_score = None
    act.workout_type = None
    type(act).pace_per_mile = PropertyMock(
        return_value=26.8224 / (distance_m / duration_s) if duration_s and distance_m else None
    )
    return act


def _make_athlete():
    a = MagicMock()
    a.id = uuid.uuid4()
    a.max_hr = 190
    a.threshold_pace = None
    a.resting_hr = 55
    return a


class TestSinglePassEMA:
    def test_converges_with_full_history(self):
        """180 days of activities produces non-zero CTL."""
        athlete = _make_athlete()
        base = date(2025, 1, 1)
        activities = [_make_activity(base + timedelta(days=i)) for i in range(180)]

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = athlete
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = activities

        svc = TrainingLoadCalculator(db)

        with patch.object(svc, 'calculate_workout_tss') as mock_tss:
            mock_tss.return_value = WorkoutStress(
                activity_id=uuid.uuid4(), date=base, tss=50.0,
                duration_minutes=60, intensity_factor=0.8, calculation_method="estimated",
            )

            def tss_side_effect(act, ath):
                return WorkoutStress(
                    activity_id=act.id, date=act.start_time.date(), tss=50.0,
                    duration_minutes=60, intensity_factor=0.8, calculation_method="estimated",
                )
            mock_tss.side_effect = tss_side_effect

            target = base + timedelta(days=179)
            results = svc.compute_training_state_history(athlete.id, target_dates=[target])

            assert target in results
            assert results[target].current_ctl > 10

    def test_matches_manual_ema(self):
        """Known TSS sequence matches hand-computed EMA."""
        athlete = _make_athlete()
        base = date(2025, 6, 1)

        tss_values = [100, 0, 50, 0, 75, 0, 0]
        activities = [_make_activity(base + timedelta(days=i)) for i in range(len(tss_values)) if tss_values[i] > 0]

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = athlete
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = activities

        svc = TrainingLoadCalculator(db)

        tss_idx = 0
        act_tss_map = {}
        for i, v in enumerate(tss_values):
            if v > 0:
                act_tss_map[activities[tss_idx].id] = (base + timedelta(days=i), v)
                tss_idx += 1

        def tss_side_effect(act, ath):
            d, t = act_tss_map[act.id]
            return WorkoutStress(
                activity_id=act.id, date=d, tss=t,
                duration_minutes=60, intensity_factor=0.8, calculation_method="estimated",
            )

        with patch.object(svc, 'calculate_workout_tss', side_effect=tss_side_effect):
            target = base + timedelta(days=6)
            results = svc.compute_training_state_history(athlete.id, target_dates=[target])

            atl_alpha = 2 / (7 + 1)
            ctl_alpha = 2 / (42 + 1)
            atl = 0.0
            ctl = 0.0
            for v in tss_values:
                atl = atl * (1 - atl_alpha) + v * atl_alpha
                ctl = ctl * (1 - ctl_alpha) + v * ctl_alpha

            assert abs(results[target].current_atl - round(atl, 1)) <= 0.2
            assert abs(results[target].current_ctl - round(ctl, 1)) <= 0.2

    def test_returns_values_at_multiple_dates(self):
        """Request 5 dates in one call, all returned."""
        athlete = _make_athlete()
        base = date(2025, 3, 1)
        activities = [_make_activity(base + timedelta(days=i)) for i in range(60)]

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = athlete
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = activities

        svc = TrainingLoadCalculator(db)

        def tss_se(act, ath):
            return WorkoutStress(
                activity_id=act.id, date=act.start_time.date(), tss=40.0,
                duration_minutes=50, intensity_factor=0.7, calculation_method="estimated",
            )

        with patch.object(svc, 'calculate_workout_tss', side_effect=tss_se):
            targets = [base + timedelta(days=d) for d in [10, 20, 30, 40, 50]]
            results = svc.compute_training_state_history(athlete.id, target_dates=targets)

            assert len(results) == 5
            for d in targets:
                assert d in results
                assert isinstance(results[d], LoadSummary)

            ctl_values = [results[d].current_ctl for d in targets]
            for i in range(1, len(ctl_values)):
                assert ctl_values[i] > ctl_values[i - 1], "CTL should increase with consistent training"

    def test_rest_days_decay_correctly(self):
        """Activity then 14 rest days: ATL/CTL decay."""
        athlete = _make_athlete()
        base = date(2025, 7, 1)
        activities = [_make_activity(base)]

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = athlete
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = activities

        svc = TrainingLoadCalculator(db)

        def tss_se(act, ath):
            return WorkoutStress(
                activity_id=act.id, date=base, tss=100.0,
                duration_minutes=60, intensity_factor=0.9, calculation_method="estimated",
            )

        with patch.object(svc, 'calculate_workout_tss', side_effect=tss_se):
            day_1 = base
            day_14 = base + timedelta(days=14)
            results = svc.compute_training_state_history(athlete.id, target_dates=[day_1, day_14])

            assert results[day_14].current_atl < results[day_1].current_atl
            assert results[day_14].current_ctl < results[day_1].current_ctl

    def test_backward_compatible(self):
        """calculate_training_load() still returns LoadSummary."""
        athlete = _make_athlete()
        base = date(2025, 5, 1)
        activities = [_make_activity(base + timedelta(days=i)) for i in range(30)]

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = athlete
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = activities

        svc = TrainingLoadCalculator(db)

        def tss_se(act, ath):
            return WorkoutStress(
                activity_id=act.id, date=act.start_time.date(), tss=50.0,
                duration_minutes=60, intensity_factor=0.8, calculation_method="estimated",
            )

        with patch.object(svc, 'calculate_workout_tss', side_effect=tss_se):
            with patch('core.cache.get_cache', return_value=None):
                with patch('core.cache.set_cache'):
                    target = base + timedelta(days=29)
                    result = svc.calculate_training_load(athlete.id, target_date=target)
                    assert isinstance(result, LoadSummary)
                    assert result.current_ctl > 0

    def test_no_activities_returns_empty(self):
        """Athlete with no activities gets empty LoadSummary at each target."""
        athlete = _make_athlete()
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = athlete
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []

        svc = TrainingLoadCalculator(db)
        targets = [date(2025, 6, 1), date(2025, 7, 1)]
        results = svc.compute_training_state_history(athlete.id, target_dates=targets)
        assert len(results) == 2
        for d in targets:
            assert results[d].current_ctl == 0.0
