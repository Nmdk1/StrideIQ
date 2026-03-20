from unittest.mock import MagicMock, patch

from tasks.strava_tasks import _maybe_enqueue_first_session_sweep_for_athlete


def _db_with_findings(first_result):
    db = MagicMock()
    q = MagicMock()
    q.filter.return_value = q
    q.first.return_value = first_result
    db.query.return_value = q
    return db


def test_strava_trigger_enqueues_when_meaningful_batch_and_no_findings():
    db = _db_with_findings(None)
    with patch("tasks.strava_tasks._try_acquire_first_session_lock", return_value=True), \
         patch("tasks.correlation_tasks.run_athlete_first_session_sweep") as mock_sweep:
        mock_sweep.apply_async = MagicMock()
        queued = _maybe_enqueue_first_session_sweep_for_athlete(
            db,
            "athlete-1",
            created_count=2,
            updated_count=1,
        )
    assert queued is True
    mock_sweep.apply_async.assert_called_once()


def test_strava_trigger_does_not_enqueue_when_findings_exist():
    db = _db_with_findings(MagicMock())
    with patch("tasks.correlation_tasks.run_athlete_first_session_sweep") as mock_sweep:
        mock_sweep.apply_async = MagicMock()
        queued = _maybe_enqueue_first_session_sweep_for_athlete(
            db,
            "athlete-1",
            created_count=3,
            updated_count=0,
        )
    assert queued is False
    mock_sweep.apply_async.assert_not_called()


def test_strava_trigger_lock_prevents_duplicate_enqueue():
    db = _db_with_findings(None)
    with patch("tasks.strava_tasks._try_acquire_first_session_lock", return_value=False), \
         patch("tasks.correlation_tasks.run_athlete_first_session_sweep") as mock_sweep:
        mock_sweep.apply_async = MagicMock()
        queued = _maybe_enqueue_first_session_sweep_for_athlete(
            db,
            "athlete-1",
            created_count=3,
            updated_count=0,
        )
    assert queued is False
    mock_sweep.apply_async.assert_not_called()
