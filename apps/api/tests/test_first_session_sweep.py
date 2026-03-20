from unittest.mock import MagicMock, patch

from tasks.correlation_tasks import ALL_OUTPUT_METRICS, run_athlete_first_session_sweep


def _mock_db_with_counts(run_count: int, findings_count: int):
    db = MagicMock()

    activity_query = MagicMock()
    activity_query.filter.return_value = activity_query
    activity_query.count.return_value = run_count

    findings_query = MagicMock()
    findings_query.filter.return_value = findings_query
    findings_query.count.return_value = findings_count

    def _query(model_attr):
        # Activity.id query for sufficiency check
        if str(model_attr).endswith("Activity.id"):
            return activity_query
        # CorrelationFinding.id query for final findings count
        return findings_query

    db.query.side_effect = _query
    return db


def test_first_session_sweep_insufficient_data():
    db = _mock_db_with_counts(run_count=5, findings_count=0)
    with patch("tasks.correlation_tasks.SessionLocal", return_value=db), \
         patch("tasks.correlation_tasks._progress_hset") as mock_progress:
        result = run_athlete_first_session_sweep.run("athlete-1")

    assert result["status"] == "insufficient_data"
    assert result["runs"] == 5
    assert mock_progress.call_count == 2
    mock_progress.assert_any_call("athlete-1", "sweep_complete", "true")
    mock_progress.assert_any_call("athlete-1", "findings_count", "0")


def test_first_session_sweep_runs_all_metrics():
    db = _mock_db_with_counts(run_count=12, findings_count=4)
    with patch("tasks.correlation_tasks.SessionLocal", return_value=db), \
         patch("services.correlation_engine.analyze_correlations") as mock_analyze, \
         patch("tasks.correlation_tasks._run_layer_pass", return_value=1), \
         patch("tasks.correlation_tasks._progress_hset"), \
         patch("tasks.correlation_tasks._refresh_living_fingerprint_for_athlete") as mock_refresh, \
         patch("services.home_briefing_cache.mark_briefing_dirty"), \
         patch("tasks.home_briefing_tasks.enqueue_briefing_refresh"):
        result = run_athlete_first_session_sweep.run("athlete-1")

    assert result["status"] == "ok"
    assert result["runs"] == 12
    assert result["findings_count"] == 4
    assert mock_analyze.call_count == len(ALL_OUTPUT_METRICS)
    mock_refresh.assert_called_once_with("athlete-1", db)


def test_first_session_sweep_does_not_trigger_global_fingerprint_refresh():
    db = _mock_db_with_counts(run_count=12, findings_count=0)
    with patch("tasks.correlation_tasks.SessionLocal", return_value=db), \
         patch("services.correlation_engine.analyze_correlations"), \
         patch("tasks.correlation_tasks._run_layer_pass", return_value=0), \
         patch("tasks.correlation_tasks._refresh_living_fingerprint_for_athlete"), \
         patch("tasks.intelligence_tasks.refresh_living_fingerprint") as mock_global_refresh, \
         patch("services.home_briefing_cache.mark_briefing_dirty"), \
         patch("tasks.home_briefing_tasks.enqueue_briefing_refresh"), \
         patch("tasks.correlation_tasks._progress_hset"):
        run_athlete_first_session_sweep.run("athlete-1")

    mock_global_refresh.delay.assert_not_called()


def test_first_session_sweep_run_count_excludes_duplicates():
    source = __import__("inspect").getsource(run_athlete_first_session_sweep)
    assert "Activity.is_duplicate == False" in source
