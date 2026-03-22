from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from tasks.garmin_health_monitor_task import cleanup_stale_garmin_pending_streams


def _mock_db_with_rows(rows):
    db = MagicMock()
    exec_result = MagicMock()
    exec_result.fetchall.return_value = rows
    db.execute.return_value = exec_result
    return db


def test_cleanup_stale_garmin_pending_streams_no_rows():
    db = _mock_db_with_rows([])

    with patch("tasks.garmin_health_monitor_task.get_db_sync", return_value=db), patch(
        "tasks.garmin_health_monitor_task.logger"
    ) as mock_logger:
        result = cleanup_stale_garmin_pending_streams.run()

    assert result["status"] == "ok"
    assert result["healed"] == 0
    assert result["affected_athletes"] == 0
    db.commit.assert_called_once()
    db.close.assert_called_once()
    mock_logger.warning.assert_not_called()
    mock_logger.info.assert_not_called()


def test_cleanup_stale_garmin_pending_streams_warns_on_large_heal():
    rows = [
        SimpleNamespace(athlete_id="a1"),
        SimpleNamespace(athlete_id="a1"),
        SimpleNamespace(athlete_id="a2"),
    ] + [SimpleNamespace(athlete_id=f"a{i}") for i in range(3, 30)]
    db = _mock_db_with_rows(rows)

    with patch("tasks.garmin_health_monitor_task.get_db_sync", return_value=db), patch(
        "tasks.garmin_health_monitor_task.logger"
    ) as mock_logger:
        result = cleanup_stale_garmin_pending_streams.run()

    assert result["status"] == "ok"
    assert result["healed"] == len(rows)
    assert result["affected_athletes"] == len({str(r.athlete_id) for r in rows})
    mock_logger.warning.assert_called_once()
