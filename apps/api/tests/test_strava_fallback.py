"""Unit + integration tests for the Garmin -> Strava structural fallback.

Mirrors the test plan locked in `docs/specs/garmin_strava_fallback_plan.md`
section 8.  Every test exercises a real branch of
`services.sync.strava_fallback.repair_garmin_activity_from_strava` against
the transactional test database -- the Strava API surface is mocked via
the function's `*_module` injection points so no network calls happen.

Naming convention: `test_<scenario>_<expected_outcome>`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


def _stale_garmin_activity(db_session, athlete, *, age_minutes: int = 60):
    """Create a Garmin activity in the exact state our fallback expects:
    provider=garmin, stream_fetch_status='unavailable',
    error='garmin_detail_missing_timeout_30m', no ActivityStream row."""
    from models import Activity

    start_time = datetime.now(timezone.utc) - timedelta(minutes=age_minutes)
    activity = Activity(
        athlete_id=athlete.id,
        provider="garmin",
        external_activity_id=str(uuid4()),
        garmin_activity_id=12345678,
        sport="run",
        start_time=start_time,
        distance_m=10000.0,
        duration_s=3000,
        avg_hr=150,
        stream_fetch_status="unavailable",
        stream_fetch_error="garmin_detail_missing_timeout_30m",
    )
    db_session.add(activity)
    db_session.commit()
    db_session.refresh(activity)
    return activity


def _athlete_with_strava(db_session, athlete):
    """Equip the test athlete with Strava OAuth state so the eligibility
    check passes.  Tokens are opaque blobs from `repair_*`'s perspective --
    the real refresh call is mocked away."""
    athlete.strava_access_token = "encrypted_access_token"
    athlete.strava_refresh_token = "encrypted_refresh_token"
    athlete.strava_token_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    db_session.add(athlete)
    db_session.commit()
    return athlete


@dataclass
class _FakeStreamResult:
    outcome: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


def _make_strava_module(
    *,
    poll_response: Optional[List[Dict[str, Any]]] = None,
    stream_result: Optional[_FakeStreamResult] = None,
    laps_response: Optional[List[Dict[str, Any]]] = None,
    refresh_raises: Optional[Exception] = None,
    poll_raises: Optional[Exception] = None,
    streams_raises: Optional[Exception] = None,
    laps_raises: Optional[Exception] = None,
):
    """Build a duck-typed `strava_service` module the fallback can call.

    Only the surface the fallback touches is implemented.  Tracking of
    calls is exposed on the returned object as `.calls` for assertions.
    """
    calls: Dict[str, int] = {
        "ensure_fresh_token": 0,
        "poll_activities_page": 0,
        "get_activity_streams": 0,
        "get_activity_laps": 0,
    }

    class _RateLimitedError(Exception):
        def __init__(self, msg, retry_after_s=900):
            super().__init__(msg)
            self.retry_after_s = retry_after_s

    def ensure_fresh_token(athlete, db):
        calls["ensure_fresh_token"] += 1
        if refresh_raises:
            raise refresh_raises

    def poll_activities_page(athlete, **kw):
        calls["poll_activities_page"] += 1
        if poll_raises:
            raise poll_raises
        return list(poll_response or [])

    def get_activity_streams(athlete, activity_id, **kw):
        calls["get_activity_streams"] += 1
        if streams_raises:
            raise streams_raises
        return stream_result or _FakeStreamResult(outcome="failed", error="no_mock")

    def get_activity_laps(athlete, activity_id, **kw):
        calls["get_activity_laps"] += 1
        if laps_raises:
            raise laps_raises
        return list(laps_response or [])

    mod = SimpleNamespace(
        ensure_fresh_token=ensure_fresh_token,
        poll_activities_page=poll_activities_page,
        get_activity_streams=get_activity_streams,
        get_activity_laps=get_activity_laps,
        StravaRateLimitError=_RateLimitedError,
        calls=calls,
    )
    return mod


def _basic_streams() -> Dict[str, List]:
    """200-point synthetic stream payload covering the channels the
    activity page consumes."""
    n = 200
    return {
        "time": list(range(n)),
        "distance": [i * 5.0 for i in range(n)],
        "heartrate": [140 + (i % 10) for i in range(n)],
        "velocity_smooth": [3.2 + (i % 5) * 0.05 for i in range(n)],
        "latlng": [[40.0 + i * 1e-5, -74.0 + i * 1e-5] for i in range(n)],
        "altitude": [100 + (i % 30) for i in range(n)],
    }


def _strava_summary(
    *,
    strava_id: int,
    start_time: datetime,
    distance_m: float,
    avg_hr: Optional[int] = 150,
    activity_type: str = "Run",
) -> Dict[str, Any]:
    return {
        "id": strava_id,
        "type": activity_type,
        "start_date": start_time.astimezone(timezone.utc)
        .strftime("%Y-%m-%dT%H:%M:%SZ"),
        "distance": distance_m,
        "average_heartrate": avg_hr,
    }


# --------------------------------------------------------------------------- #
# Happy path
# --------------------------------------------------------------------------- #


def test_happy_path_streams_and_laps_writes_success(db_session, test_athlete):
    """End-to-end success: tokens present, single matching Strava run,
    streams + laps returned -> ActivityStream row appears with
    source='strava_fallback', activity flips to success, fallback
    columns reflect the win, splits land via interval detector."""
    from services.sync.strava_fallback import repair_garmin_activity_from_strava
    from models import Activity, ActivityStream, ActivitySplit

    athlete = _athlete_with_strava(db_session, test_athlete)
    activity = _stale_garmin_activity(db_session, athlete)

    summary = _strava_summary(
        strava_id=99887766,
        start_time=activity.start_time,
        distance_m=activity.distance_m,
    )
    laps = [
        {"lap_index": i + 1, "distance": 1609.34, "elapsed_time": 360,
         "moving_time": 360, "average_heartrate": 145 + i, "max_heartrate": 160 + i,
         "average_cadence": 80, "average_speed": 4.5}
        for i in range(6)
    ]
    strava_mod = _make_strava_module(
        poll_response=[summary],
        stream_result=_FakeStreamResult(outcome="success", data=_basic_streams()),
        laps_response=laps,
    )

    result = repair_garmin_activity_from_strava(
        activity.id,
        db_session,
        strava_service_module=strava_mod,
    )

    assert result.status == "succeeded"
    assert result.strava_activity_id == 99887766
    assert result.point_count == 200
    assert result.splits_written > 0

    db_session.expire_all()
    refreshed = db_session.query(Activity).filter(Activity.id == activity.id).one()
    assert refreshed.stream_fetch_status == "success"
    assert refreshed.strava_fallback_status == "succeeded"
    assert refreshed.strava_fallback_strava_activity_id == 99887766
    assert refreshed.provider == "garmin", "provider must NOT flip to strava"
    assert refreshed.distance_m == pytest.approx(10000.0), "Garmin summary preserved"

    stream = db_session.query(ActivityStream).filter(
        ActivityStream.activity_id == activity.id
    ).one()
    assert stream.source == "strava_fallback"
    assert stream.point_count == 200
    assert "heartrate" in (stream.channels_available or [])

    splits = db_session.query(ActivitySplit).filter(
        ActivitySplit.activity_id == activity.id
    ).all()
    assert len(splits) >= 1


def test_happy_path_streams_only_no_laps_still_succeeds(db_session, test_athlete):
    """Strava returns streams but no usable laps -> still success; chart
    renders even without splits.  Per founder answer #2 we never block on
    laps when streams are present."""
    from services.sync.strava_fallback import repair_garmin_activity_from_strava
    from models import Activity

    athlete = _athlete_with_strava(db_session, test_athlete)
    activity = _stale_garmin_activity(db_session, athlete)

    summary = _strava_summary(
        strava_id=11111,
        start_time=activity.start_time,
        distance_m=activity.distance_m,
    )
    strava_mod = _make_strava_module(
        poll_response=[summary],
        stream_result=_FakeStreamResult(outcome="success", data=_basic_streams()),
        laps_response=[],
    )

    result = repair_garmin_activity_from_strava(
        activity.id, db_session, strava_service_module=strava_mod,
    )

    assert result.status == "succeeded"
    assert result.point_count == 200
    assert result.splits_written == 0

    refreshed = db_session.query(Activity).filter(Activity.id == activity.id).one()
    assert refreshed.stream_fetch_status == "success"
    assert refreshed.strava_fallback_status == "succeeded"


# --------------------------------------------------------------------------- #
# Skip / failure paths
# --------------------------------------------------------------------------- #


def test_no_strava_tokens_skips_without_api_calls(db_session, test_athlete):
    """Athlete with no Strava connection -> skipped_no_strava and zero
    Strava API calls.  Confirms the eligibility gate fires before any
    network IO."""
    from services.sync.strava_fallback import repair_garmin_activity_from_strava

    activity = _stale_garmin_activity(db_session, test_athlete)
    test_athlete.strava_access_token = None
    test_athlete.strava_refresh_token = None
    db_session.commit()

    strava_mod = _make_strava_module()

    result = repair_garmin_activity_from_strava(
        activity.id, db_session, strava_service_module=strava_mod,
    )

    assert result.status == "skipped_no_strava"
    assert strava_mod.calls["ensure_fresh_token"] == 0
    assert strava_mod.calls["poll_activities_page"] == 0
    assert strava_mod.calls["get_activity_streams"] == 0


def test_token_refresh_failure_marks_failed(db_session, test_athlete):
    """`ensure_fresh_token` raising -> terminal `failed` with the error
    string captured for ops triage."""
    from services.sync.strava_fallback import repair_garmin_activity_from_strava
    from models import Activity

    athlete = _athlete_with_strava(db_session, test_athlete)
    activity = _stale_garmin_activity(db_session, athlete)
    strava_mod = _make_strava_module(
        refresh_raises=RuntimeError("strava_oauth_500"),
    )

    result = repair_garmin_activity_from_strava(
        activity.id, db_session, strava_service_module=strava_mod,
    )

    assert result.status == "failed"
    assert "strava_oauth_500" in (result.error or "")

    refreshed = db_session.query(Activity).filter(Activity.id == activity.id).one()
    assert refreshed.strava_fallback_status == "failed"


def test_no_strava_match_marks_no_match_with_retry(db_session, test_athlete):
    """No candidate inside the +/-30 min window -> skipped_no_match,
    persisted as `failed` so the row is re-claimable on the next cycle
    (founder answer #4: retry once after 2h)."""
    from services.sync.strava_fallback import (
        repair_garmin_activity_from_strava,
        SKIPPED_NO_MATCH_RETRY_DELAY_SECONDS,
    )
    from models import Activity

    athlete = _athlete_with_strava(db_session, test_athlete)
    activity = _stale_garmin_activity(db_session, athlete)

    strava_mod = _make_strava_module(poll_response=[])

    result = repair_garmin_activity_from_strava(
        activity.id, db_session, strava_service_module=strava_mod,
    )

    assert result.status == "skipped_no_match"
    assert result.retry_after_s == SKIPPED_NO_MATCH_RETRY_DELAY_SECONDS

    refreshed = db_session.query(Activity).filter(Activity.id == activity.id).one()
    assert refreshed.strava_fallback_status == "failed"
    assert "no_matching_strava_activity" in (refreshed.strava_fallback_error or "")


def test_strava_streams_unavailable_marks_terminal(db_session, test_athlete):
    """Strava confirms no streams (404) -> skipped_strava_no_streams,
    terminal."""
    from services.sync.strava_fallback import repair_garmin_activity_from_strava
    from models import Activity

    athlete = _athlete_with_strava(db_session, test_athlete)
    activity = _stale_garmin_activity(db_session, athlete)
    summary = _strava_summary(
        strava_id=42, start_time=activity.start_time, distance_m=activity.distance_m,
    )

    strava_mod = _make_strava_module(
        poll_response=[summary],
        stream_result=_FakeStreamResult(outcome="unavailable", error="404"),
    )

    result = repair_garmin_activity_from_strava(
        activity.id, db_session, strava_service_module=strava_mod,
    )

    assert result.status == "skipped_strava_no_streams"

    refreshed = db_session.query(Activity).filter(Activity.id == activity.id).one()
    assert refreshed.stream_fetch_status == "unavailable", (
        "Activity stream lifecycle stays unavailable -- nothing was repaired"
    )
    assert refreshed.strava_fallback_status == "skipped_strava_no_streams"
    assert refreshed.strava_fallback_strava_activity_id == 42


def test_strava_streams_failed_marks_terminal_failed(db_session, test_athlete):
    """`StreamFetchResult.failed` -> terminal `failed`."""
    from services.sync.strava_fallback import repair_garmin_activity_from_strava
    from models import Activity

    athlete = _athlete_with_strava(db_session, test_athlete)
    activity = _stale_garmin_activity(db_session, athlete)
    summary = _strava_summary(
        strava_id=7, start_time=activity.start_time, distance_m=activity.distance_m,
    )
    strava_mod = _make_strava_module(
        poll_response=[summary],
        stream_result=_FakeStreamResult(outcome="failed", error="channel_length_mismatch:hr"),
    )

    result = repair_garmin_activity_from_strava(
        activity.id, db_session, strava_service_module=strava_mod,
    )

    assert result.status == "failed"
    assert "channel_length_mismatch" in (result.error or "")

    refreshed = db_session.query(Activity).filter(Activity.id == activity.id).one()
    assert refreshed.strava_fallback_status == "failed"


def test_already_succeeded_is_noop_no_api_calls(db_session, test_athlete):
    """Idempotency: a row already marked `succeeded` is not claimable
    and triggers zero Strava API calls."""
    from services.sync.strava_fallback import repair_garmin_activity_from_strava

    athlete = _athlete_with_strava(db_session, test_athlete)
    activity = _stale_garmin_activity(db_session, athlete)
    activity.strava_fallback_status = "succeeded"
    db_session.commit()

    strava_mod = _make_strava_module()

    result = repair_garmin_activity_from_strava(
        activity.id, db_session, strava_service_module=strava_mod,
    )

    assert result.status == "skipped_not_claimable"
    assert strava_mod.calls["ensure_fresh_token"] == 0
    assert strava_mod.calls["poll_activities_page"] == 0


def test_non_run_sport_is_skipped(db_session, test_athlete):
    """Bike / swim activities are out of scope for v1 -> skipped_not_run."""
    from services.sync.strava_fallback import repair_garmin_activity_from_strava

    athlete = _athlete_with_strava(db_session, test_athlete)
    activity = _stale_garmin_activity(db_session, athlete)
    activity.sport = "bike"
    db_session.commit()

    strava_mod = _make_strava_module()

    result = repair_garmin_activity_from_strava(
        activity.id, db_session, strava_service_module=strava_mod,
    )

    assert result.status == "skipped_not_run"
    assert strava_mod.calls["poll_activities_page"] == 0


def test_too_old_activity_is_skipped(db_session, test_athlete):
    """Activities older than MAX_FALLBACK_AGE_DAYS -> skipped_too_old.
    Founder answer #5: 14 days."""
    from services.sync.strava_fallback import (
        repair_garmin_activity_from_strava,
        MAX_FALLBACK_AGE_DAYS,
    )

    athlete = _athlete_with_strava(db_session, test_athlete)
    activity = _stale_garmin_activity(
        db_session, athlete, age_minutes=60 * 24 * (MAX_FALLBACK_AGE_DAYS + 2)
    )
    strava_mod = _make_strava_module()

    result = repair_garmin_activity_from_strava(
        activity.id, db_session, strava_service_module=strava_mod,
    )

    assert result.status == "skipped_too_old"
    assert strava_mod.calls["poll_activities_page"] == 0


# --------------------------------------------------------------------------- #
# Matching semantics
# --------------------------------------------------------------------------- #


def test_multiple_candidates_picks_closest_start_time(db_session, test_athlete):
    """Two valid matches inside the window -> the one whose start_time
    is closest to the Garmin start_time wins.  Locked deterministic
    choice rather than Strava's list ordering."""
    from services.sync.strava_fallback import repair_garmin_activity_from_strava
    from models import Activity

    athlete = _athlete_with_strava(db_session, test_athlete)
    activity = _stale_garmin_activity(db_session, athlete)

    far = _strava_summary(
        strava_id=10001,
        start_time=activity.start_time + timedelta(minutes=15),
        distance_m=activity.distance_m,
    )
    near = _strava_summary(
        strava_id=10002,
        start_time=activity.start_time + timedelta(minutes=2),
        distance_m=activity.distance_m,
    )
    strava_mod = _make_strava_module(
        poll_response=[far, near],
        stream_result=_FakeStreamResult(outcome="success", data=_basic_streams()),
    )

    result = repair_garmin_activity_from_strava(
        activity.id, db_session, strava_service_module=strava_mod,
    )

    assert result.status == "succeeded"
    assert result.strava_activity_id == 10002


def test_distance_outside_5pct_is_rejected(db_session, test_athlete):
    """Distance mismatch beyond 5% -> not a match -> skipped_no_match.
    Tightens the dedup tolerance for fallback-only per founder answer #1."""
    from services.sync.strava_fallback import repair_garmin_activity_from_strava

    athlete = _athlete_with_strava(db_session, test_athlete)
    activity = _stale_garmin_activity(db_session, athlete)

    bad = _strava_summary(
        strava_id=999,
        start_time=activity.start_time,
        distance_m=activity.distance_m * 1.10,  # 10% off
    )
    strava_mod = _make_strava_module(poll_response=[bad])

    result = repair_garmin_activity_from_strava(
        activity.id, db_session, strava_service_module=strava_mod,
    )

    assert result.status == "skipped_no_match"


def test_outside_30min_window_is_rejected(db_session, test_athlete):
    """A Strava activity that is the right distance but starts >30 min
    from the Garmin start_time is rejected.  Defends against the
    pathological "two same-distance runs same morning" case."""
    from services.sync.strava_fallback import repair_garmin_activity_from_strava

    athlete = _athlete_with_strava(db_session, test_athlete)
    activity = _stale_garmin_activity(db_session, athlete)

    far = _strava_summary(
        strava_id=12345,
        start_time=activity.start_time + timedelta(hours=2),
        distance_m=activity.distance_m,
    )
    strava_mod = _make_strava_module(poll_response=[far])

    result = repair_garmin_activity_from_strava(
        activity.id, db_session, strava_service_module=strava_mod,
    )

    assert result.status == "skipped_no_match"


def test_non_run_strava_candidates_are_filtered(db_session, test_athlete):
    """A bike ride with the same distance/time should not be picked as
    a fallback for a Garmin run.  Strava `type` filter must apply."""
    from services.sync.strava_fallback import repair_garmin_activity_from_strava

    athlete = _athlete_with_strava(db_session, test_athlete)
    activity = _stale_garmin_activity(db_session, athlete)

    bike = _strava_summary(
        strava_id=55,
        start_time=activity.start_time,
        distance_m=activity.distance_m,
        activity_type="Ride",
    )
    strava_mod = _make_strava_module(poll_response=[bike])

    result = repair_garmin_activity_from_strava(
        activity.id, db_session, strava_service_module=strava_mod,
    )

    assert result.status == "skipped_no_match"


# --------------------------------------------------------------------------- #
# Persistence invariants
# --------------------------------------------------------------------------- #


def test_existing_activity_stream_row_is_overwritten_not_duplicated(
    db_session, test_athlete
):
    """If an empty/partial ActivityStream row already exists for the
    Garmin activity, the fallback updates it in place rather than
    creating a second row (one stream per activity is the contract)."""
    from services.sync.strava_fallback import repair_garmin_activity_from_strava
    from models import ActivityStream

    athlete = _athlete_with_strava(db_session, test_athlete)
    activity = _stale_garmin_activity(db_session, athlete)

    db_session.add(
        ActivityStream(
            activity_id=activity.id,
            stream_data={"time": [0, 1, 2]},
            channels_available=["time"],
            point_count=3,
            source="garmin",
        )
    )
    db_session.commit()

    summary = _strava_summary(
        strava_id=4242,
        start_time=activity.start_time,
        distance_m=activity.distance_m,
    )
    strava_mod = _make_strava_module(
        poll_response=[summary],
        stream_result=_FakeStreamResult(outcome="success", data=_basic_streams()),
    )

    result = repair_garmin_activity_from_strava(
        activity.id, db_session, strava_service_module=strava_mod,
    )
    assert result.status == "succeeded"

    rows = db_session.query(ActivityStream).filter(
        ActivityStream.activity_id == activity.id
    ).all()
    assert len(rows) == 1
    assert rows[0].source == "strava_fallback"
    assert rows[0].point_count == 200


def test_garmin_summary_fields_are_not_overwritten(db_session, test_athlete):
    """Per spec section 4 'Does not': do not overwrite Garmin summary
    fields (distance, duration, HR).  Only fill streams + splits + shape."""
    from services.sync.strava_fallback import repair_garmin_activity_from_strava
    from models import Activity

    athlete = _athlete_with_strava(db_session, test_athlete)
    activity = _stale_garmin_activity(db_session, athlete)
    original_distance = float(activity.distance_m)
    original_duration = activity.duration_s
    original_avg_hr = activity.avg_hr

    # Strava returns slightly different summary numbers; the fallback
    # should ignore them when copying the streams.
    summary = _strava_summary(
        strava_id=8001,
        start_time=activity.start_time,
        distance_m=original_distance + 50,
        avg_hr=152,
    )
    strava_mod = _make_strava_module(
        poll_response=[summary],
        stream_result=_FakeStreamResult(outcome="success", data=_basic_streams()),
    )

    result = repair_garmin_activity_from_strava(
        activity.id, db_session, strava_service_module=strava_mod,
    )
    assert result.status == "succeeded"

    refreshed = db_session.query(Activity).filter(Activity.id == activity.id).one()
    assert refreshed.distance_m == pytest.approx(original_distance)
    assert refreshed.duration_s == original_duration
    assert refreshed.avg_hr == original_avg_hr


def test_provider_and_external_activity_id_unchanged(db_session, test_athlete):
    """The activity must remain provider='garmin' with its original
    external_activity_id after a successful fallback.  The audit trail
    only adds the Strava id to the fallback columns."""
    from services.sync.strava_fallback import repair_garmin_activity_from_strava
    from models import Activity

    athlete = _athlete_with_strava(db_session, test_athlete)
    activity = _stale_garmin_activity(db_session, athlete)
    original_external_id = activity.external_activity_id
    original_garmin_id = activity.garmin_activity_id

    summary = _strava_summary(
        strava_id=77777,
        start_time=activity.start_time,
        distance_m=activity.distance_m,
    )
    strava_mod = _make_strava_module(
        poll_response=[summary],
        stream_result=_FakeStreamResult(outcome="success", data=_basic_streams()),
    )

    repair_garmin_activity_from_strava(
        activity.id, db_session, strava_service_module=strava_mod,
    )

    refreshed = db_session.query(Activity).filter(Activity.id == activity.id).one()
    assert refreshed.provider == "garmin"
    assert refreshed.external_activity_id == original_external_id
    assert refreshed.garmin_activity_id == original_garmin_id
    assert refreshed.strava_fallback_strava_activity_id == 77777


# --------------------------------------------------------------------------- #
# Adapter unit tests (no DB)
# --------------------------------------------------------------------------- #


def test_adapt_strava_laps_translates_to_internal_dict_shape():
    """Strava lap payload -> internal dict with the keys
    `interval_detector.detect_interval_structure` consumes."""
    from services.sync.strava_fallback import _adapt_strava_laps

    laps = [
        {
            "lap_index": 1,
            "distance": 1609.34,
            "elapsed_time": 360,
            "moving_time": 358,
            "average_heartrate": 150,
            "max_heartrate": 165,
            "average_cadence": 82.5,
            "average_speed": 4.47,
        },
        {
            # Garbage row should be silently dropped, not crash.
            "lap_index": "junk",
            "distance": "x",
        },
    ]
    out = _adapt_strava_laps(laps)
    assert len(out) == 1
    one = out[0]
    assert one["split_number"] == 1
    assert one["distance"] == pytest.approx(1609.34)
    assert one["elapsed_time"] == 360
    assert one["moving_time"] == 358
    assert one["average_heartrate"] == 150
    assert one["max_heartrate"] == 165
    assert one["average_cadence"] == pytest.approx(82.5)
    assert one["gap_seconds_per_mile"] is None


# --------------------------------------------------------------------------- #
# Cleanup task -> fallback enqueue wiring
# --------------------------------------------------------------------------- #


def test_cleanup_stale_garmin_enqueues_fallback_for_each_row(monkeypatch):
    """`cleanup_stale_garmin_pending_streams` must enqueue exactly one
    `repair_garmin_activity_from_strava_task` per fail-closed row.

    We do not need a real DB here -- we patch `get_db_sync` to return a
    stub session whose `.execute().fetchall()` yields two synthetic rows.
    """
    from tasks import garmin_health_monitor_task as ghm

    fake_rows = [
        SimpleNamespace(id=uuid4(), athlete_id=uuid4()),
        SimpleNamespace(id=uuid4(), athlete_id=uuid4()),
    ]

    class _StubDB:
        def execute(self, *a, **kw):
            return SimpleNamespace(fetchall=lambda: fake_rows)

        def commit(self):
            pass

        def rollback(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr(ghm, "get_db_sync", lambda: _StubDB())

    enqueued: List[str] = []

    class _StubTask:
        @staticmethod
        def delay(activity_id):
            enqueued.append(activity_id)

    monkeypatch.setattr(
        "tasks.strava_fallback_tasks.repair_garmin_activity_from_strava_task",
        _StubTask,
    )
    monkeypatch.setattr(
        "tasks.beat_startup_dispatch.record_task_run", lambda *a, **kw: None,
        raising=False,
    )

    result = ghm.cleanup_stale_garmin_pending_streams()

    assert result["healed"] == 2
    assert result["fallback_enqueued"] == 2
    assert sorted(enqueued) == sorted(str(r.id) for r in fake_rows)


# --------------------------------------------------------------------------- #
# Migration / schema invariant
# --------------------------------------------------------------------------- #


def test_activity_table_has_strava_fallback_columns(db_session):
    """Regression for the new migration: after `alembic upgrade head` the
    activity table must expose the four fallback columns the service
    writes to.  Catches drift between the model and the migration."""
    from sqlalchemy import text

    rows = db_session.execute(
        text(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'activity'
              AND column_name LIKE 'strava_fallback%'
            ORDER BY column_name
            """
        )
    ).fetchall()
    names = {r[0] for r in rows}

    assert names >= {
        "strava_fallback_status",
        "strava_fallback_attempted_at",
        "strava_fallback_strava_activity_id",
        "strava_fallback_error",
        "strava_fallback_attempt_count",
    }


def test_partial_index_for_fallback_eligibility_exists(db_session):
    """The migration's partial index keeps the eligibility scan cheap.
    Asserting it exists prevents an ops drift where the index is
    dropped manually and never recreated."""
    from sqlalchemy import text

    rows = db_session.execute(
        text(
            """
            SELECT indexname FROM pg_indexes
            WHERE tablename = 'activity'
              AND indexname = 'ix_activity_strava_fallback_eligible'
            """
        )
    ).fetchall()
    assert rows, "ix_activity_strava_fallback_eligible missing"
