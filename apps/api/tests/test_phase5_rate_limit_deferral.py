import pytest
from uuid import uuid4
from datetime import datetime, timezone

from core.database import SessionLocal
from models import Athlete, AthleteIngestionState


def test_rate_limit_defers_and_retries_index_task(monkeypatch):
    """
    Phase 5 armor: a Strava 429 in the index backfill must be treated as deferral (not error)
    and the task must self.retry with a countdown.
    """
    from tasks.strava_tasks import backfill_strava_activity_index_task
    from services.strava_service import StravaRateLimitError

    db = SessionLocal()
    athlete = Athlete(
        email=f"rate_limit_{uuid4()}@example.com",
        display_name="RL",
        role="athlete",
        subscription_tier="free",
        strava_access_token="dummy",  # presence check only; Strava call is mocked
    )
    db.add(athlete)
    db.commit()
    db.refresh(athlete)
    db.close()

    # Force the Strava poll to raise a typed rate limit error.
    def _raise(*args, **kwargs):
        raise StravaRateLimitError("429", retry_after_s=900)

    monkeypatch.setattr("tasks.strava_tasks.poll_activities_page", _raise)

    called = {"countdown": None}

    def _retry(*args, **kwargs):
        called["countdown"] = kwargs.get("countdown")
        from celery.exceptions import Retry

        raise Retry("retried", None, None)

    # Patch retry on the task instance
    monkeypatch.setattr(backfill_strava_activity_index_task, "retry", _retry)

    from celery.exceptions import Retry

    with pytest.raises(Retry) as e:
        backfill_strava_activity_index_task.run(str(athlete.id), pages=1)
    assert "retried" in str(e.value)
    assert called["countdown"] is not None
    assert called["countdown"] >= 60

    # Verify ingestion state marked as deferred and not errored.
    db = SessionLocal()
    try:
        st = (
            db.query(AthleteIngestionState)
            .filter(AthleteIngestionState.athlete_id == athlete.id, AthleteIngestionState.provider == "strava")
            .first()
        )
        assert st is not None
        assert st.last_index_status == "deferred"
        assert st.last_index_error is None
        assert st.deferred_reason == "rate_limit"
        assert st.deferred_until is not None
        assert st.deferred_until > datetime.now(timezone.utc)
    finally:
        db.query(AthleteIngestionState).filter(AthleteIngestionState.athlete_id == athlete.id).delete(synchronize_session=False)
        db.query(Athlete).filter(Athlete.id == athlete.id).delete(synchronize_session=False)
        db.commit()
        db.close()

