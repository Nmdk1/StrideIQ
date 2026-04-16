from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from tasks.garmin_health_monitor_task import cleanup_stale_garmin_pending_streams


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
