"""
Cross-Training Sport Filter Tests

Verifies that all running-specific consumers exclude non-run activities.
Commit 1 of Cross-Training Activity Storage: downstream consumer audit.

Two fixture strategies prove filtering:
1. Mixed-sport athlete (run + cycling): running queries return ONLY the run.
2. Cycling-only athlete (5 cycling activities): running queries return empty/None.

Strategy 2 is the strongest proof. If the sport filter is missing, the cycling
activities satisfy minimum-count thresholds and functions return data. With the
filter, they see zero activities and return None/empty.
"""
import pytest
import sys
import os
from datetime import datetime, date, timedelta, timezone
from uuid import uuid4
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from models import Activity, Athlete


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def athlete_with_mixed_sports(db_session):
    """One run (4h ago) and one cycling activity (2h ago, more recent)."""
    athlete = Athlete(
        email=f"cross_train_{uuid4()}@example.com",
        display_name="Cross Training Test",
        subscription_tier="premium",
        birthdate=date(1985, 6, 15),
        sex="M",
        max_hr=185,
        resting_hr=50,
        threshold_hr=165,
    )
    db_session.add(athlete)
    db_session.commit()
    db_session.refresh(athlete)

    now = datetime.now(timezone.utc)

    run_activity = Activity(
        athlete_id=athlete.id,
        name="Morning Run",
        start_time=now - timedelta(hours=4),
        sport="run",
        source="garmin",
        provider="garmin",
        external_activity_id=f"run_{uuid4().hex[:8]}",
        duration_s=3600,
        distance_m=10000,
        avg_hr=150,
        max_hr=175,
        average_speed=2.78,
        workout_type="easy_run",
        is_duplicate=False,
    )
    cycling_activity = Activity(
        athlete_id=athlete.id,
        name="Evening Ride",
        start_time=now - timedelta(hours=2),
        sport="cycling",
        source="garmin",
        provider="garmin",
        external_activity_id=f"bike_{uuid4().hex[:8]}",
        duration_s=5400,
        distance_m=30000,
        avg_hr=135,
        max_hr=160,
        average_speed=5.56,
        workout_type="endurance",
        is_duplicate=False,
    )
    db_session.add_all([run_activity, cycling_activity])
    db_session.commit()
    db_session.refresh(run_activity)
    db_session.refresh(cycling_activity)

    return athlete, run_activity, cycling_activity


@pytest.fixture
def cycling_only_athlete(db_session):
    """Athlete with 6 cycling activities spread over 6 weeks, zero runs.

    6 activities across 6 different weeks satisfies minimum-count thresholds
    in most service functions (consistency needs 5, efficiency needs 2, etc.).
    If sport filters are missing, these functions will see data and return
    non-None. With correct filters, they see zero activities and return None.
    """
    athlete = Athlete(
        email=f"cyclist_{uuid4()}@example.com",
        display_name="Cyclist Only",
        subscription_tier="premium",
        birthdate=date(1988, 3, 20),
        sex="F",
        max_hr=180,
        resting_hr=55,
        threshold_hr=160,
    )
    db_session.add(athlete)
    db_session.commit()
    db_session.refresh(athlete)

    now = datetime.now(timezone.utc)
    activities = []
    for i in range(6):
        act = Activity(
            athlete_id=athlete.id,
            name=f"Ride {i + 1}",
            start_time=now - timedelta(days=i * 7 + 1, hours=3),
            sport="cycling",
            source="garmin",
            provider="garmin",
            external_activity_id=f"bike_{uuid4().hex[:8]}",
            duration_s=3600 + i * 300,
            distance_m=25000 + i * 2000,
            avg_hr=130 + i * 3,
            max_hr=155 + i * 3,
            average_speed=5.0 + i * 0.2,
            workout_type="endurance",
            is_duplicate=False,
        )
        activities.append(act)
    db_session.add_all(activities)
    db_session.commit()

    return athlete, activities


# ---------------------------------------------------------------------------
# Direct ORM verification
# ---------------------------------------------------------------------------

class TestDirectQueryVerification:
    """Proves the ORM filter itself works before testing service methods."""

    def test_run_filter_returns_only_runs(
        self, db_session, athlete_with_mixed_sports
    ):
        athlete, run_act, cycling_act = athlete_with_mixed_sports
        runs = db_session.query(Activity).filter(
            Activity.athlete_id == athlete.id,
            Activity.sport == "run",
        ).all()
        assert len(runs) == 1
        assert runs[0].id == run_act.id
        assert runs[0].name == "Morning Run"

    def test_no_filter_returns_both(
        self, db_session, athlete_with_mixed_sports
    ):
        athlete, run_act, cycling_act = athlete_with_mixed_sports
        all_activities = db_session.query(Activity).filter(
            Activity.athlete_id == athlete.id,
        ).all()
        assert len(all_activities) == 2
        sports = {a.sport for a in all_activities}
        assert sports == {"run", "cycling"}

    def test_cycling_only_athlete_has_zero_runs(
        self, db_session, cycling_only_athlete
    ):
        athlete, activities = cycling_only_athlete
        runs = db_session.query(Activity).filter(
            Activity.athlete_id == athlete.id,
            Activity.sport == "run",
        ).all()
        assert len(runs) == 0, "Cycling-only athlete should have zero runs"
        all_acts = db_session.query(Activity).filter(
            Activity.athlete_id == athlete.id,
        ).all()
        assert len(all_acts) == 6, "Cycling-only athlete should have 6 cycling activities"


# ---------------------------------------------------------------------------
# Training Load — cycling-only must produce empty history
# ---------------------------------------------------------------------------

class TestTrainingLoadSportFilter:
    """Training load calculations must exclude non-run activities."""

    def test_history_excludes_cycling_in_mixed(
        self, db_session, athlete_with_mixed_sports
    ):
        """With 1 run + 1 cycling: history should contain ONLY the run."""
        athlete, run_act, cycling_act = athlete_with_mixed_sports
        from services.training_load import TrainingLoadCalculator

        calc = TrainingLoadCalculator(db_session)
        history = calc.compute_training_state_history(athlete.id)

        all_activity_ids = set()
        for day_summary in history.values():
            for a in getattr(day_summary, "activities", []):
                all_activity_ids.add(a.id)

        assert cycling_act.id not in all_activity_ids, (
            "Cycling activity appeared in training load history"
        )

    def test_history_empty_for_cycling_only(
        self, db_session, cycling_only_athlete
    ):
        """With only cycling data, training load history should have no activities."""
        athlete, _ = cycling_only_athlete
        from services.training_load import TrainingLoadCalculator

        calc = TrainingLoadCalculator(db_session)
        history = calc.compute_training_state_history(athlete.id)

        all_activity_ids = set()
        for day_summary in history.values():
            for a in getattr(day_summary, "activities", []):
                all_activity_ids.add(a.id)

        assert len(all_activity_ids) == 0, (
            f"Cycling-only athlete should have empty load history, "
            f"got {len(all_activity_ids)} activities"
        )


# ---------------------------------------------------------------------------
# Correlation Engine — cycling must not appear in session stress
# ---------------------------------------------------------------------------

class TestCorrelationEngineSportFilter:
    """Correlation engine aggregate queries must exclude non-run activities."""

    def test_daily_session_stress_empty_for_cycling_only(
        self, db_session, cycling_only_athlete
    ):
        """With only cycling data, session stress should be empty."""
        athlete, _ = cycling_only_athlete
        from services.correlation_engine import CorrelationEngine

        engine = CorrelationEngine(db_session)
        today = date.today()
        result = engine.aggregate_daily_session_stress(
            athlete.id, today - timedelta(days=60), today
        )
        assert result == {} or len(result) == 0, (
            f"Cycling-only athlete should have no session stress, "
            f"got {len(result)} days"
        )


# ---------------------------------------------------------------------------
# Run Analysis Engine — cycling must not inflate week context
# ---------------------------------------------------------------------------

class TestRunAnalysisEngineSportFilter:
    """Run analysis engine must exclude non-run activities."""

    def test_week_context_excludes_cycling(
        self, db_session, athlete_with_mixed_sports
    ):
        """Week context count should be exactly 1 (the run), not 2."""
        athlete, run_act, cycling_act = athlete_with_mixed_sports
        from services.run_analysis_engine import RunAnalysisEngine

        engine = RunAnalysisEngine(db_session)
        ctx = engine._get_week_context(athlete.id, date.today())
        assert ctx["count"] == 1, (
            f"Expected 1 run in week context, got {ctx['count']}. "
            "Cycling activity may have leaked through."
        )

    def test_volume_zero_for_cycling_only(
        self, db_session, cycling_only_athlete
    ):
        """With only cycling, volume data points should be empty."""
        athlete, _ = cycling_only_athlete
        from services.run_analysis_engine import RunAnalysisEngine

        engine = RunAnalysisEngine(db_session)
        result = engine._get_volume_data_points(athlete.id, date.today() - timedelta(days=60))
        assert len(result) == 0, (
            f"Cycling-only athlete should have 0 volume data points, "
            f"got {len(result)}"
        )


# ---------------------------------------------------------------------------
# Home — cycling must not become "last run"
# ---------------------------------------------------------------------------

class TestHomeSportFilter:
    """Home page queries must show only runs."""

    def test_compute_last_run_returns_run_not_bike(
        self, db_session, athlete_with_mixed_sports
    ):
        """Cycling is more recent (2h ago) than run (4h ago).
        compute_last_run must return the run, not the bike ride."""
        athlete, run_act, cycling_act = athlete_with_mixed_sports
        from routers.home import compute_last_run

        last_run = compute_last_run(db_session, athlete)
        assert last_run is not None, "Expected a last_run (the run exists within 96h)"
        assert last_run["activity_id"] == str(run_act.id), (
            f"compute_last_run returned activity {last_run['activity_id']}, "
            f"expected run {run_act.id}, not cycling {cycling_act.id}"
        )
        assert last_run["name"] == "Morning Run"

    def test_compute_last_run_none_for_cycling_only(
        self, db_session, cycling_only_athlete
    ):
        """With only cycling data, compute_last_run should return None."""
        athlete, _ = cycling_only_athlete
        from routers.home import compute_last_run

        last_run = compute_last_run(db_session, athlete)
        assert last_run is None, (
            "Cycling-only athlete should have no last_run"
        )


# ---------------------------------------------------------------------------
# Readiness Score — cycling-only must return None
# ---------------------------------------------------------------------------

class TestReadinessScoreSportFilter:
    """Readiness score calculations must exclude non-run activities."""

    def test_efficiency_none_for_cycling_only(
        self, db_session, cycling_only_athlete
    ):
        """With 6 cycling activities and zero runs, efficiency should be None.
        Without the sport filter, the 6 cycling activities would satisfy
        the minimum count threshold and return a float."""
        athlete, _ = cycling_only_athlete
        from services.readiness_score import ReadinessScoreCalculator

        calc = ReadinessScoreCalculator()
        result = calc._compute_efficiency_from_activities(
            athlete.id, date.today(), db_session
        )
        assert result is None, (
            f"Cycling-only athlete should have None efficiency, got {result}"
        )


# ---------------------------------------------------------------------------
# Recovery Metrics — cycling-only must return None
# ---------------------------------------------------------------------------

class TestRecoveryMetricsSportFilter:
    """Recovery metrics must exclude non-run activities."""

    def test_consistency_none_for_cycling_only(
        self, db_session, cycling_only_athlete
    ):
        """With 6 cycling activities over 6 weeks and zero runs, consistency
        should be None. Without the sport filter, 6 activities over 6 weeks
        would produce a consistency index."""
        athlete, _ = cycling_only_athlete
        from services.recovery_metrics import calculate_consistency_index

        result = calculate_consistency_index(
            db_session, str(athlete.id), days=90
        )
        assert result is None, (
            f"Cycling-only athlete should have None consistency, got {result}"
        )
