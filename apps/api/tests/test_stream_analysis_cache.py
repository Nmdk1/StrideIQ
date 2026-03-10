"""RSI — Stream Analysis Cache Tests

Validates the spec decision:
    "Cache full StreamAnalysisResult in DB. Compute once, serve many.
     Recompute on: new stream payload, analysis_version bump, manual reprocess."

Tests:
    1. First call computes + stores cache row
    2. Second call serves from cache (no recompute)
    3. Version bump invalidates cache
    4. invalidate_cache() removes the row
    5. Both /v1/home and /v1/activities/{id}/stream-analysis use cache
    6. _lttb_1d produces correct-length output and preserves endpoints
"""
import sys
import os
import pytest
from datetime import datetime, date, timedelta, timezone
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi.testclient import TestClient
from cryptography.fernet import Fernet
from sqlalchemy import event
from sqlalchemy.orm import Session

from main import app
from core.database import engine, get_db
from core.security import create_access_token
from models import Activity, ActivityStream, Athlete, CachedStreamAnalysis
from fixtures.stream_fixtures import make_easy_run_stream
from services.stream_analysis_cache import (
    get_or_compute_analysis,
    invalidate_cache,
    CURRENT_ANALYSIS_VERSION,
)
from routers.home import _lttb_1d


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _ensure_encryption_key():
    import services.token_encryption as te_mod
    key = Fernet.generate_key().decode()
    old_val = os.environ.get("TOKEN_ENCRYPTION_KEY")
    os.environ["TOKEN_ENCRYPTION_KEY"] = key
    te_mod._token_encryption = None
    yield
    te_mod._token_encryption = None
    if old_val is not None:
        os.environ["TOKEN_ENCRYPTION_KEY"] = old_val
    elif "TOKEN_ENCRYPTION_KEY" in os.environ:
        del os.environ["TOKEN_ENCRYPTION_KEY"]


@pytest.fixture
def db_session():
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)
    nested = connection.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(sess, trans):
        nonlocal nested
        if trans.nested and not trans._parent.nested:
            nested = connection.begin_nested()

    def _override():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = _override
    yield session
    app.dependency_overrides.pop(get_db, None)
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session):
    return TestClient(app)


@pytest.fixture
def test_athlete(db_session):
    from services.token_encryption import encrypt_token
    athlete = Athlete(
        email=f"cache_test_{uuid4()}@example.com",
        display_name="Cache Test",
        subscription_tier="premium",
        birthdate=date(1990, 1, 1),
        sex="M",
        strava_access_token=encrypt_token("fake"),
        strava_refresh_token=encrypt_token("fake_r"),
        strava_athlete_id=66001,
        max_hr=186,
        resting_hr=48,
        threshold_hr=165,
    )
    db_session.add(athlete)
    db_session.commit()
    db_session.refresh(athlete)
    return athlete


@pytest.fixture
def activity_with_stream(db_session, test_athlete):
    activity = Activity(
        athlete_id=test_athlete.id,
        name="Cache Test Run",
        start_time=datetime.now(timezone.utc) - timedelta(hours=2),
        sport="run",
        source="strava",
        provider="strava",
        external_activity_id=f"cache_{uuid4().hex[:8]}",
        duration_s=3600,
        distance_m=10000,
        avg_hr=145,
        stream_fetch_status="success",
    )
    db_session.add(activity)
    db_session.commit()

    stream_data = make_easy_run_stream(duration_s=3600)
    stream = ActivityStream(
        activity_id=activity.id,
        stream_data=stream_data,
        channels_available=list(stream_data.keys()),
        point_count=3600,
        source="strava",
    )
    db_session.add(stream)
    db_session.commit()
    db_session.refresh(activity)
    return activity


def _auth(athlete):
    token = create_access_token(data={"sub": str(athlete.id)})
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Cache behavior tests
# ---------------------------------------------------------------------------

class TestCacheComputeAndServe:
    """Verify compute-once-serve-many behavior."""

    def test_first_call_creates_cache_row(
        self, db_session, test_athlete, activity_with_stream
    ):
        """First call to get_or_compute_analysis stores a CachedStreamAnalysis row."""
        from services.run_stream_analysis import AthleteContext

        stream_row = db_session.query(ActivityStream).filter(
            ActivityStream.activity_id == activity_with_stream.id
        ).first()

        ctx = AthleteContext(max_hr=186, resting_hr=48, threshold_hr=165)

        # No cache row yet
        before = db_session.query(CachedStreamAnalysis).filter(
            CachedStreamAnalysis.activity_id == activity_with_stream.id
        ).first()
        assert before is None

        result = get_or_compute_analysis(
            activity_id=activity_with_stream.id,
            stream_row=stream_row,
            athlete_ctx=ctx,
            db=db_session,
        )

        # Cache row now exists
        after = db_session.query(CachedStreamAnalysis).filter(
            CachedStreamAnalysis.activity_id == activity_with_stream.id
        ).first()
        assert after is not None
        assert after.analysis_version == CURRENT_ANALYSIS_VERSION
        assert "segments" in after.result_json
        assert "confidence" in after.result_json

    def test_second_call_serves_from_cache(
        self, db_session, test_athlete, activity_with_stream
    ):
        """Second call does not recompute — serves from cache."""
        from services.run_stream_analysis import AthleteContext

        stream_row = db_session.query(ActivityStream).filter(
            ActivityStream.activity_id == activity_with_stream.id
        ).first()
        ctx = AthleteContext(max_hr=186, resting_hr=48, threshold_hr=165)

        # First call — computes
        result1 = get_or_compute_analysis(
            activity_id=activity_with_stream.id,
            stream_row=stream_row,
            athlete_ctx=ctx,
            db=db_session,
        )

        # Second call — should serve from cache (patch analyze_stream to detect)
        with patch("services.stream_analysis_cache.analyze_stream") as mock_analyze:
            result2 = get_or_compute_analysis(
                activity_id=activity_with_stream.id,
                stream_row=stream_row,
                athlete_ctx=ctx,
                db=db_session,
            )
            mock_analyze.assert_not_called()

        # Results should be equivalent
        assert result2["confidence"] == result1["confidence"]
        assert result2["tier_used"] == result1["tier_used"]

    def test_force_recompute_bypasses_cache(
        self, db_session, test_athlete, activity_with_stream
    ):
        """force_recompute=True runs analysis even when cache exists."""
        from services.run_stream_analysis import AthleteContext

        stream_row = db_session.query(ActivityStream).filter(
            ActivityStream.activity_id == activity_with_stream.id
        ).first()
        ctx = AthleteContext(max_hr=186, resting_hr=48, threshold_hr=165)

        # Populate cache
        get_or_compute_analysis(
            activity_id=activity_with_stream.id,
            stream_row=stream_row,
            athlete_ctx=ctx,
            db=db_session,
        )

        # Force recompute
        with patch("services.stream_analysis_cache.analyze_stream", wraps=__import__("services.run_stream_analysis", fromlist=["analyze_stream"]).analyze_stream) as mock_analyze:
            result = get_or_compute_analysis(
                activity_id=activity_with_stream.id,
                stream_row=stream_row,
                athlete_ctx=ctx,
                db=db_session,
                force_recompute=True,
            )
            mock_analyze.assert_called_once()

    def test_invalidate_cache_removes_row(
        self, db_session, test_athlete, activity_with_stream
    ):
        """invalidate_cache() removes the cached row."""
        from services.run_stream_analysis import AthleteContext

        stream_row = db_session.query(ActivityStream).filter(
            ActivityStream.activity_id == activity_with_stream.id
        ).first()
        ctx = AthleteContext(max_hr=186, resting_hr=48, threshold_hr=165)

        # Populate cache
        get_or_compute_analysis(
            activity_id=activity_with_stream.id,
            stream_row=stream_row,
            athlete_ctx=ctx,
            db=db_session,
        )

        assert db_session.query(CachedStreamAnalysis).filter(
            CachedStreamAnalysis.activity_id == activity_with_stream.id
        ).first() is not None

        # Invalidate
        invalidate_cache(activity_with_stream.id, db_session)

        assert db_session.query(CachedStreamAnalysis).filter(
            CachedStreamAnalysis.activity_id == activity_with_stream.id
        ).first() is None


class TestCacheVersionInvalidation:
    """Version bump invalidates stale cache."""

    def test_stale_version_triggers_recompute(
        self, db_session, test_athlete, activity_with_stream
    ):
        """Cache row with old version is treated as a miss."""
        from services.run_stream_analysis import AthleteContext

        stream_row = db_session.query(ActivityStream).filter(
            ActivityStream.activity_id == activity_with_stream.id
        ).first()
        ctx = AthleteContext(max_hr=186, resting_hr=48, threshold_hr=165)

        # Populate cache
        get_or_compute_analysis(
            activity_id=activity_with_stream.id,
            stream_row=stream_row,
            athlete_ctx=ctx,
            db=db_session,
        )

        # Manually set version to old value
        row = db_session.query(CachedStreamAnalysis).filter(
            CachedStreamAnalysis.activity_id == activity_with_stream.id
        ).first()
        row.analysis_version = 0  # Old version
        db_session.commit()

        # Next call should recompute (version mismatch)
        with patch("services.stream_analysis_cache.analyze_stream", wraps=__import__("services.run_stream_analysis", fromlist=["analyze_stream"]).analyze_stream) as mock_analyze:
            result = get_or_compute_analysis(
                activity_id=activity_with_stream.id,
                stream_row=stream_row,
                athlete_ctx=ctx,
                db=db_session,
            )
            mock_analyze.assert_called_once()

        # Version should be updated
        updated = db_session.query(CachedStreamAnalysis).filter(
            CachedStreamAnalysis.activity_id == activity_with_stream.id
        ).first()
        assert updated.analysis_version == CURRENT_ANALYSIS_VERSION


# ---------------------------------------------------------------------------
# Endpoint integration: both endpoints use cache
# ---------------------------------------------------------------------------

class TestEndpointsCacheIntegration:
    """Both /v1/home and /v1/activities/{id}/stream-analysis use cache."""

    def test_stream_analysis_endpoint_creates_cache(
        self, client, test_athlete, activity_with_stream, db_session
    ):
        """GET /v1/activities/{id}/stream-analysis creates cache row."""
        url = f"/v1/activities/{activity_with_stream.id}/stream-analysis"
        resp = client.get(url, headers=_auth(test_athlete))
        assert resp.status_code == 200

        row = db_session.query(CachedStreamAnalysis).filter(
            CachedStreamAnalysis.activity_id == activity_with_stream.id
        ).first()
        assert row is not None

    def test_home_endpoint_serves_from_cache(
        self, client, test_athlete, activity_with_stream, db_session
    ):
        """/v1/home serves effort_intensity from cache after /v1/activities/{id}/stream-analysis."""
        # First: hit stream-analysis to populate cache
        sa_url = f"/v1/activities/{activity_with_stream.id}/stream-analysis"
        client.get(sa_url, headers=_auth(test_athlete))

        # Verify cache exists
        assert db_session.query(CachedStreamAnalysis).filter(
            CachedStreamAnalysis.activity_id == activity_with_stream.id
        ).first() is not None

        # Now: hit /v1/home — should serve from cache, not recompute
        with patch("services.stream_analysis_cache.analyze_stream") as mock_analyze:
            resp = client.get("/v1/home", headers=_auth(test_athlete))
            assert resp.status_code == 200
            lr = resp.json().get("last_run")
            assert lr is not None
            assert lr["effort_intensity"] is not None
            mock_analyze.assert_not_called()


# ---------------------------------------------------------------------------
# LTTB 1D correctness
# ---------------------------------------------------------------------------

class TestLttb1d:
    """Validate _lttb_1d is real LTTB, not decimation."""

    def test_output_length_matches_target(self):
        """Output should be exactly target length."""
        data = list(range(2000))
        result = _lttb_1d(data, 500)
        assert len(result) == 500

    def test_preserves_first_and_last(self):
        """LTTB always preserves first and last points."""
        data = [0.1 * i for i in range(1000)]
        result = _lttb_1d(data, 100)
        assert result[0] == data[0]
        assert result[-1] == data[-1]

    def test_noop_when_below_target(self):
        """No downsampling when data is already small enough."""
        data = [0.5] * 200
        result = _lttb_1d(data, 500)
        assert len(result) == 200
        assert result == data

    def test_preserves_spike(self):
        """LTTB should preserve a significant spike in the middle.
        Decimation might miss it; LTTB picks the point with max triangle area."""
        n = 2000
        data = [0.3] * n
        spike_idx = 1000
        data[spike_idx] = 1.0  # Significant spike

        result = _lttb_1d(data, 500)

        # The spike value should be in the output
        assert 1.0 in result, "LTTB should preserve the significant spike"

    def test_not_fixed_step(self):
        """Verify output is NOT the same as simple fixed-step decimation."""
        import random
        random.seed(42)
        # Create data with interesting features that LTTB would preserve differently
        n = 2000
        data = [0.5 + 0.3 * random.gauss(0, 1) for _ in range(n)]
        # Add distinctive spikes
        data[500] = 2.0
        data[1500] = -1.0

        lttb_result = _lttb_1d(data, 500)

        # Simple decimation
        step = n / 500
        decimated = [data[int(i * step)] for i in range(500)]

        # They should differ (LTTB picks area-maximizing points, not fixed-step)
        assert lttb_result != decimated, "LTTB output should differ from fixed-step decimation"
