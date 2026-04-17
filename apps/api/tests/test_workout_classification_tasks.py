"""Tests for the workout-classification backfill + sweep.

The Garmin webhook used to silently leave workout_type=NULL for every
Garmin-primary athlete.  The Compare tab's tiers 3 + 4 both gate on
workout_type, so the population-level breakage was invisible from a
single founder's account (the founder had run an ops script).

These tests lock the contracts that prevent that population-level
breakage from silently recurring."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from tasks.workout_classification_tasks import (
    backfill_workout_classifications,
    sweep_unclassified_runs,
)


class _FakeActivity:
    """Minimal stand-in for the Activity ORM row; classifier only cares
    about a handful of attributes and we mock the classifier itself."""

    def __init__(self, activity_id):
        self.id = activity_id
        self.workout_type = None
        self.workout_zone = None
        self.workout_confidence = None
        self.intensity_score = None


def _make_classification(
    workout_type_value: str = "aerobic_run",
    workout_zone_value: str = "endurance",
    confidence: float = 0.78,
    intensity: float = 42.0,
):
    cls = MagicMock()
    cls.workout_type = SimpleNamespace(value=workout_type_value)
    cls.workout_zone = SimpleNamespace(value=workout_zone_value)
    cls.confidence = confidence
    cls.intensity_score = intensity
    return cls


def _make_db(athlete_ids, pending_per_athlete):
    """Wire up a SessionLocal mock that returns the given athletes and,
    for each, the given list of pending unclassified activities."""
    db = MagicMock()

    athlete_query = MagicMock()
    athlete_query.filter.return_value = athlete_query
    athlete_query.limit.return_value = athlete_query
    athlete_query.all.return_value = [(aid,) for aid in athlete_ids]

    activity_query_per_athlete = list(pending_per_athlete)
    call_state = {"i": 0}

    def query_side_effect(model, *args, **kwargs):
        # First the test calls db.query(Athlete.id), then per-athlete
        # db.query(Activity).  Distinguish by call order: first call is
        # athletes, the rest are activities (one per athlete).
        if call_state["i"] == 0:
            call_state["i"] += 1
            return athlete_query
        idx = call_state["i"] - 1
        call_state["i"] += 1
        activity_query = MagicMock()
        activity_query.filter.return_value = activity_query
        activity_query.order_by.return_value = activity_query
        activity_query.limit.return_value = activity_query
        activity_query.all.return_value = activity_query_per_athlete[idx]
        return activity_query

    db.query.side_effect = query_side_effect
    return db


def test_backfill_no_athletes_is_noop():
    db = _make_db(athlete_ids=[], pending_per_athlete=[])
    classifier = MagicMock()
    classifier.classify_activity.return_value = _make_classification()

    with patch(
        "tasks.workout_classification_tasks.SessionLocal", return_value=db
    ), patch(
        "tasks.workout_classification_tasks.WorkoutClassifierService",
        return_value=classifier,
    ):
        result = backfill_workout_classifications.run()

    assert result["status"] == "ok"
    assert result["athletes_processed"] == 0
    assert result["classified"] == 0
    classifier.classify_activity.assert_not_called()
    db.commit.assert_not_called()


def test_backfill_classifies_and_persists_for_each_pending_row():
    """REGRESSION GUARD: every pending row gets the four classification
    fields persisted, every athlete's batch commits exactly once.

    If this test fails, the backfill stopped writing back classification
    results -- which means the Compare tab silently re-breaks for the
    population the moment the webhook path stops classifying."""
    aid_a = uuid4()
    aid_b = uuid4()
    pending_a = [_FakeActivity(uuid4()), _FakeActivity(uuid4())]
    pending_b = [_FakeActivity(uuid4())]
    db = _make_db([aid_a, aid_b], [pending_a, pending_b])
    classifier = MagicMock()
    classifier.classify_activity.return_value = _make_classification(
        workout_type_value="long_run",
        workout_zone_value="endurance",
        confidence=0.91,
        intensity=55.0,
    )

    with patch(
        "tasks.workout_classification_tasks.SessionLocal", return_value=db
    ), patch(
        "tasks.workout_classification_tasks.WorkoutClassifierService",
        return_value=classifier,
    ):
        result = backfill_workout_classifications.run()

    assert result["status"] == "ok"
    assert result["athletes_processed"] == 2
    assert result["classified"] == 3
    assert result["errors"] == 0
    # Every pending row had every field populated.
    for row in pending_a + pending_b:
        assert row.workout_type == "long_run"
        assert row.workout_zone == "endurance"
        assert row.workout_confidence == 0.91
        assert row.intensity_score == 55.0
    # One commit per athlete batch (not one per row, not one global).
    assert db.commit.call_count == 2


def test_backfill_athlete_with_no_pending_skips_commit():
    """If an athlete has nothing to classify, don't pretend to process
    them and don't issue an empty commit."""
    aid = uuid4()
    db = _make_db([aid], [[]])
    classifier = MagicMock()

    with patch(
        "tasks.workout_classification_tasks.SessionLocal", return_value=db
    ), patch(
        "tasks.workout_classification_tasks.WorkoutClassifierService",
        return_value=classifier,
    ):
        result = backfill_workout_classifications.run()

    assert result["athletes_processed"] == 0
    assert result["classified"] == 0
    db.commit.assert_not_called()


def test_backfill_per_row_failure_does_not_abort_athlete_batch():
    """One classifier exception on a malformed row must not strand the
    rest of that athlete's batch (or the next athlete)."""
    aid = uuid4()
    rows = [_FakeActivity(uuid4()) for _ in range(3)]
    db = _make_db([aid], [rows])
    classifier = MagicMock()
    good = _make_classification()
    classifier.classify_activity.side_effect = [
        good,
        RuntimeError("bad row"),
        good,
    ]

    with patch(
        "tasks.workout_classification_tasks.SessionLocal", return_value=db
    ), patch(
        "tasks.workout_classification_tasks.WorkoutClassifierService",
        return_value=classifier,
    ):
        result = backfill_workout_classifications.run()

    assert result["classified"] == 2
    assert result["errors"] == 1
    db.commit.assert_called_once()
    # The two surviving rows got their fields persisted.
    survivors = [r for r in rows if r.workout_type is not None]
    assert len(survivors) == 2


def test_sweep_delegates_to_backfill_with_periodic_settings():
    """The periodic sweep is the safety net for the population-level
    breakage that started this whole investigation.  It must keep
    calling the backfill with the smaller per-athlete batch size so a
    one-time fleet-wide backfill spreads across cycles instead of
    holding the worker."""
    with patch(
        "tasks.workout_classification_tasks.backfill_workout_classifications.run"
    ) as mock_run:
        mock_run.return_value = {"status": "ok", "classified": 0}
        sweep_unclassified_runs.run()

    assert mock_run.call_count == 1
    kwargs = mock_run.call_args.kwargs
    assert kwargs["athlete_id"] is None
    assert kwargs["limit_athletes"] is None
    # Periodic version bounds per-athlete batch tighter than the one-shot.
    assert kwargs["batch_limit_per_athlete"] <= 50


def test_sweep_is_wired_in_beat_schedule():
    """REGRESSION GUARD: removing the safety-net sweep silently re-creates
    the population-level Compare-tab breakage if anything ever stops
    classifying at ingest time."""
    from celerybeat_schedule import beat_schedule

    entry = beat_schedule.get("workout-classify-sweep")
    assert entry is not None, "workout-classify-sweep must be on the beat schedule"
    assert entry["task"] == "tasks.sweep_unclassified_runs"
