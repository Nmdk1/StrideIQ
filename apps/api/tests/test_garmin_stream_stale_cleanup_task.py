from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from tasks.garmin_health_monitor_task import (
    cleanup_stale_garmin_pending_streams,
    sweep_unavailable_garmin_streams,
)


def _mock_db_with_rows(rows):
    db = MagicMock()
    exec_result = MagicMock()
    exec_result.fetchall.return_value = rows
    db.execute.return_value = exec_result
    return db


def _row(athlete_id):
    """Build a row matching the cleanup task's RETURNING clause:
    `a.id, a.athlete_id`.  Each row needs a unique activity id so the
    Strava-fallback enqueue is per-row deterministic."""
    return SimpleNamespace(id=uuid4(), athlete_id=athlete_id)


def test_cleanup_stale_garmin_pending_streams_no_rows():
    db = _mock_db_with_rows([])

    with patch("tasks.garmin_health_monitor_task.get_db_sync", return_value=db), patch(
        "tasks.garmin_health_monitor_task.logger"
    ) as mock_logger, patch(
        "tasks.strava_fallback_tasks.repair_garmin_activity_from_strava_task"
    ) as mock_task:
        result = cleanup_stale_garmin_pending_streams.run()

    assert result["status"] == "ok"
    assert result["healed"] == 0
    assert result["affected_athletes"] == 0
    assert result["fallback_enqueued"] == 0
    db.commit.assert_called_once()
    db.close.assert_called_once()
    mock_logger.warning.assert_not_called()
    mock_logger.info.assert_not_called()
    mock_task.delay.assert_not_called()


def test_cleanup_stale_garmin_pending_streams_warns_on_large_heal():
    rows = [_row("a1"), _row("a1"), _row("a2")] + [
        _row(f"a{i}") for i in range(3, 30)
    ]
    db = _mock_db_with_rows(rows)

    with patch("tasks.garmin_health_monitor_task.get_db_sync", return_value=db), patch(
        "tasks.garmin_health_monitor_task.logger"
    ) as mock_logger, patch(
        "tasks.strava_fallback_tasks.repair_garmin_activity_from_strava_task"
    ) as mock_task:
        result = cleanup_stale_garmin_pending_streams.run()

    assert result["status"] == "ok"
    assert result["healed"] == len(rows)
    assert result["affected_athletes"] == len({str(r.athlete_id) for r in rows})
    mock_logger.warning.assert_called_once()
    # Every fail-closed row gets exactly one Strava-fallback enqueue.
    assert result["fallback_enqueued"] == len(rows)
    assert mock_task.delay.call_count == len(rows)


# ---------------------------------------------------------------------------
# Self-healing sweep tests.
#
# Contract: every Garmin row marked 'unavailable' that is still eligible
# (age <= 14d, attempts < 3, sport=run) must get a fallback enqueue per
# sweep cycle, regardless of which transition path put it there.  This is
# defense-in-depth so the system never again depends on every transition
# path remembering to enqueue.
# ---------------------------------------------------------------------------


def _sweep_row():
    """The sweep query returns rows shaped as `id` (text)."""
    return SimpleNamespace(id=str(uuid4()))


def test_sweep_no_eligible_rows_is_noop():
    db = _mock_db_with_rows([])

    with patch(
        "tasks.garmin_health_monitor_task.get_db_sync", return_value=db
    ), patch(
        "tasks.strava_fallback_tasks.repair_garmin_activity_from_strava_task"
    ) as mock_task:
        result = sweep_unavailable_garmin_streams.run()

    assert result["status"] == "ok"
    assert result["candidates"] == 0
    assert result["enqueued"] == 0
    mock_task.delay.assert_not_called()
    db.close.assert_called_once()


def test_sweep_enqueues_fallback_for_every_eligible_row():
    """REGRESSION GUARD: the sweep is the safety net behind both transition
    paths.  If it ever stops enqueueing for eligible rows, athletes accumulate
    blank activity pages silently — which is exactly how Larry / Adam / Brian
    were broken before this contract existed."""
    rows = [_sweep_row() for _ in range(7)]
    db = _mock_db_with_rows(rows)

    with patch(
        "tasks.garmin_health_monitor_task.get_db_sync", return_value=db
    ), patch(
        "tasks.strava_fallback_tasks.repair_garmin_activity_from_strava_task"
    ) as mock_task:
        result = sweep_unavailable_garmin_streams.run()

    assert result["status"] == "ok"
    assert result["candidates"] == len(rows)
    assert result["enqueued"] == len(rows)
    assert mock_task.delay.call_count == len(rows)
    enqueued_ids = {call.args[0] for call in mock_task.delay.call_args_list}
    assert enqueued_ids == {r.id for r in rows}


def test_sweep_query_filters_to_eligible_population():
    """The sweep must only target Garmin run rows that are unavailable, recent,
    and not already exhausted on attempts.  Asserting on the SQL keeps the
    eligibility contract from drifting silently if someone edits the query."""
    db = _mock_db_with_rows([])

    with patch(
        "tasks.garmin_health_monitor_task.get_db_sync", return_value=db
    ), patch(
        "tasks.strava_fallback_tasks.repair_garmin_activity_from_strava_task"
    ):
        sweep_unavailable_garmin_streams.run()

    sql = str(db.execute.call_args.args[0])
    assert "provider = 'garmin'" in sql
    assert "sport = 'run'" in sql
    assert "stream_fetch_status = 'unavailable'" in sql
    assert "max_age_days" in sql
    assert "max_attempts" in sql
    # Allows a NULL fallback status (never tried) OR a retryable soft skip.
    assert "strava_fallback_status IS NULL" in sql
    assert "skipped_no_match" in sql


def test_sweep_is_wired_in_beat_schedule():
    """REGRESSION GUARD: the sweep must remain on the beat schedule.  If
    someone removes it, the safety net silently disappears and the next
    forgotten enqueue site (or future third transition path) re-creates
    the regression that broke Larry / Adam / Brian."""
    from celerybeat_schedule import beat_schedule

    entry = beat_schedule.get("garmin-fallback-sweep")
    assert entry is not None, "garmin-fallback-sweep must be on the beat schedule"
    assert entry["task"] == "tasks.sweep_unavailable_garmin_streams"


def test_sweep_enqueue_failure_does_not_abort_remaining_rows():
    """A broker hiccup on one row must not strand the rest of the batch."""
    rows = [_sweep_row(), _sweep_row(), _sweep_row()]
    db = _mock_db_with_rows(rows)

    with patch(
        "tasks.garmin_health_monitor_task.get_db_sync", return_value=db
    ), patch(
        "tasks.strava_fallback_tasks.repair_garmin_activity_from_strava_task"
    ) as mock_task:
        mock_task.delay.side_effect = [None, RuntimeError("broker"), None]
        result = sweep_unavailable_garmin_streams.run()

    assert result["status"] == "ok"
    assert result["candidates"] == 3
    assert result["enqueued"] == 2
    assert mock_task.delay.call_count == 3
