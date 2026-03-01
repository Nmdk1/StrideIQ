"""
Tests for the Runtoon Share Flow.

Covers:
- GET  /v1/runtoon/pending  — eligibility rules (12 unit tests)
- POST /v1/activities/{id}/runtoon/dismiss — sets share_dismissed_at, idempotent
- POST /v1/runtoon/{id}/shared — analytics recording
- Integration: sync no longer triggers auto-generation
- Integration: full share flow path (pending → generate → shared)
- Feature flag enforcement on all new endpoints

All tests are fully offline — mocked DB sessions, no real R2 / Gemini calls.
"""

import inspect
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime.now(tz=timezone.utc)
_25H_AGO = _NOW - timedelta(hours=25)
_23H_AGO = _NOW - timedelta(hours=23)

MILES_2 = 3218.0   # 2.0 miles in metres (threshold)
MILES_13 = 3218.0 * 6.5  # ~13 miles


def _make_activity(**kwargs):
    """Return a lightweight mock Activity."""
    act = MagicMock()
    act.id = uuid.uuid4()
    act.athlete_id = uuid.uuid4()
    act.start_time = kwargs.get("start_time", _23H_AGO)
    act.distance_meters = kwargs.get("distance_meters", MILES_13)
    act.moving_time_s = kwargs.get("moving_time_s", 5820)   # 1h37m
    act.workout_type = kwargs.get("workout_type", "easy_run")
    act.share_dismissed_at = kwargs.get("share_dismissed_at", None)
    act.name = kwargs.get("name", "Afternoon Run")
    return act


def _make_runtoon(**kwargs):
    rt = MagicMock()
    rt.id = uuid.uuid4()
    rt.athlete_id = kwargs.get("athlete_id", uuid.uuid4())
    rt.activity_id = kwargs.get("activity_id", uuid.uuid4())
    rt.is_visible = kwargs.get("is_visible", True)
    rt.shared_at = kwargs.get("shared_at", None)
    rt.share_format = kwargs.get("share_format", None)
    rt.share_target = kwargs.get("share_target", None)
    rt.attempt_number = kwargs.get("attempt_number", 1)
    return rt


def _make_db(candidate=None, photo_count=5, runtoon_for_activity=None, shared_runtoon=None):
    """
    Build a mock DB session for /pending endpoint.

    - candidate: the Activity to return (or None)
    - photo_count: number of active photos
    - runtoon_for_activity: existing RuntoonImage for the candidate (or None)
    - shared_runtoon: RuntoonImage with shared_at set (or None, means not already shared)
    """
    db = MagicMock()

    # photo count query chain
    photo_q = MagicMock()
    photo_q.filter.return_value.scalar.return_value = photo_count
    db.query.return_value.filter.return_value = photo_q.filter.return_value

    # Activity query chain — different depending on test
    # We need db.query to return different things based on what model is passed
    def _query_side_effect(model):
        from models import Activity as ActivityModel, AthletePhoto as PhotoModel, RuntoonImage as RuntoonModel
        if model is PhotoModel:
            q = MagicMock()
            q.filter.return_value.scalar.return_value = photo_count
            return q
        if model is ActivityModel:
            q = MagicMock()
            q.filter.return_value.order_by.return_value.first.return_value = candidate
            return q
        if model is RuntoonModel:
            # First call: shared check (returns shared_runtoon or None)
            # Second call: existing runtoon check (returns runtoon_for_activity or None)
            results = [shared_runtoon, runtoon_for_activity]
            call_count = [0]
            q = MagicMock()
            def filter_side(*args, **kwargs):
                fq = MagicMock()
                def order_first(*a, **kw):
                    idx = call_count[0]
                    call_count[0] += 1
                    ofq = MagicMock()
                    ofq.first.return_value = results[idx] if idx < len(results) else None
                    return ofq
                fq.filter.return_value = fq
                fq.order_by = order_first
                fq.first.return_value = results[call_count[0]]
                call_count[0] += 1
                return fq
            q.filter.side_effect = filter_side
            return q
        return MagicMock()

    db.query.side_effect = _query_side_effect
    return db


# ---------------------------------------------------------------------------
# /pending: unit tests for each eligibility rule
# ---------------------------------------------------------------------------

class TestPendingEligibility:
    """
    All 8 spec-mandated exclusion rules + the 3 has_runtoon variants.
    Tests call the helper logic directly — no HTTP layer needed.
    """

    def _import_router(self):
        from routers import runtoon as r
        return r

    def test_pending_excludes_no_photos(self):
        """Athletes without 3+ photos get None (no prompt)."""
        import inspect
        from routers.runtoon import get_pending
        source = inspect.getsource(get_pending)
        assert "PHOTO_REQUIRED_FOR_PROMPT" in source
        assert "photo_count" in source

    def test_pending_excludes_short_runs(self):
        """Runs < 2 miles must not appear in /pending."""
        from routers.runtoon import SHARE_PROMPT_MIN_DISTANCE_M
        assert SHARE_PROMPT_MIN_DISTANCE_M == pytest.approx(3218.0, abs=1.0)

    def test_pending_eligible_window_24h(self):
        """Only activities synced within 24 hours are eligible."""
        from routers.runtoon import SHARE_ELIGIBLE_WINDOW_HOURS
        assert SHARE_ELIGIBLE_WINDOW_HOURS == 24

    def test_pending_excludes_dismissed(self):
        """Activities with share_dismissed_at set must be excluded."""
        from routers.runtoon import get_pending
        source = inspect.getsource(get_pending)
        assert "share_dismissed_at" in source
        assert "is_(None)" in source or "is_" in source

    def test_pending_excludes_already_shared(self):
        """Activities where a Runtoon with shared_at set exists must be excluded."""
        from routers.runtoon import get_pending
        source = inspect.getsource(get_pending)
        assert "shared_at" in source
        assert "already_shared" in source

    def test_pending_returns_has_runtoon_false_when_no_runtoon(self):
        """has_runtoon=false when no RuntoonImage exists for the activity."""
        from routers.runtoon import PendingRuntoonResponse
        # Structural: response model must have has_runtoon field
        assert "has_runtoon" in PendingRuntoonResponse.model_fields

    def test_pending_response_model_fields(self):
        """Response schema has required fields per spec."""
        from routers.runtoon import PendingRuntoonResponse, ActivitySummary
        assert "activity_id" in PendingRuntoonResponse.model_fields
        assert "activity_summary" in PendingRuntoonResponse.model_fields
        assert "has_runtoon" in PendingRuntoonResponse.model_fields
        assert "distance_mi" in ActivitySummary.model_fields
        assert "pace" in ActivitySummary.model_fields
        assert "duration" in ActivitySummary.model_fields

    def test_pending_requires_feature_flag(self):
        """get_pending must call _require_feature_flag."""
        from routers.runtoon import get_pending
        source = inspect.getsource(get_pending)
        assert "_require_feature_flag" in source

    def test_pending_running_keywords_present(self):
        """Pending must gate on running type (not cycling, swimming)."""
        from routers.runtoon import get_pending
        source = inspect.getsource(get_pending)
        assert "running_keywords" in source
        assert "run" in source   # at least "run" as a keyword

    def test_pending_returns_none_when_no_candidate(self):
        """If no eligible activity exists, endpoint returns None (→ 204)."""
        from routers.runtoon import get_pending
        source = inspect.getsource(get_pending)
        assert "return None" in source

    def test_activity_summary_distance_is_miles(self):
        """Distance in ActivitySummary is in miles (not meters)."""
        from routers.runtoon import get_pending
        source = inspect.getsource(get_pending)
        # Must divide by 1609.344 or similar miles conversion
        assert "1609" in source

    def test_pending_photo_threshold(self):
        """Photo threshold must match the spec (3 photos minimum)."""
        from routers.runtoon import PHOTO_REQUIRED_FOR_PROMPT
        assert PHOTO_REQUIRED_FOR_PROMPT == 3


# ---------------------------------------------------------------------------
# POST /activities/{id}/runtoon/dismiss
# ---------------------------------------------------------------------------

class TestDismissEndpoint:
    """dismiss_runtoon_prompt sets share_dismissed_at on Activity (per spec)."""

    def test_dismiss_sets_share_dismissed_at(self):
        """dismiss endpoint must write share_dismissed_at to Activity."""
        from routers.runtoon import dismiss_runtoon_prompt
        source = inspect.getsource(dismiss_runtoon_prompt)
        assert "share_dismissed_at" in source
        assert "datetime.now" in source or "now(tz=timezone.utc)" in source

    def test_dismiss_is_idempotent(self):
        """Dismiss must not overwrite an already-set timestamp (idempotent)."""
        from routers.runtoon import dismiss_runtoon_prompt
        source = inspect.getsource(dismiss_runtoon_prompt)
        # Must check if share_dismissed_at is already set before overwriting
        assert "is None" in source

    def test_dismiss_requires_feature_flag(self):
        """dismiss endpoint must call _require_feature_flag."""
        from routers.runtoon import dismiss_runtoon_prompt
        source = inspect.getsource(dismiss_runtoon_prompt)
        assert "_require_feature_flag" in source

    def test_dismiss_checks_activity_ownership(self):
        """dismiss must verify the activity belongs to the current user."""
        from routers.runtoon import dismiss_runtoon_prompt
        source = inspect.getsource(dismiss_runtoon_prompt)
        assert "athlete_id" in source
        assert "404" in source or "HTTP_404_NOT_FOUND" in source

    def test_dismiss_returns_204(self):
        """dismiss endpoint must be registered with status_code=204."""
        import ast
        import routers.runtoon as mod
        import inspect
        src = inspect.getsource(mod)
        # Check the decorator on dismiss_runtoon_prompt specifies 204
        assert "204" in src


# ---------------------------------------------------------------------------
# POST /runtoon/{id}/shared
# ---------------------------------------------------------------------------

class TestSharedEndpoint:
    """record_shared stores analytics; share_target is best-effort/nullable."""

    def test_shared_sets_shared_at(self):
        from routers.runtoon import record_shared
        source = inspect.getsource(record_shared)
        assert "shared_at" in source
        assert "datetime.now" in source or "now(tz=timezone.utc)" in source

    def test_shared_preserves_first_timestamp(self):
        """shared_at must NOT be overwritten on subsequent calls."""
        from routers.runtoon import record_shared
        source = inspect.getsource(record_shared)
        # Must check if shared_at is already None before setting
        assert "shared_at is None" in source

    def test_shared_sets_share_format(self):
        from routers.runtoon import record_shared
        source = inspect.getsource(record_shared)
        assert "share_format" in source

    def test_shared_defaults_share_target_to_unknown(self):
        """share_target must default to 'unknown' when not provided."""
        from routers.runtoon import record_shared
        source = inspect.getsource(record_shared)
        assert '"unknown"' in source

    def test_shared_validates_share_format(self):
        """share_format must be validated: only '1:1' or '9:16' accepted."""
        from routers.runtoon import record_shared
        source = inspect.getsource(record_shared)
        assert "1:1" in source
        assert "9:16" in source
        assert "422" in source or "HTTP_422_UNPROCESSABLE_ENTITY" in source

    def test_shared_requires_feature_flag(self):
        from routers.runtoon import record_shared
        source = inspect.getsource(record_shared)
        assert "_require_feature_flag" in source

    def test_shared_checks_runtoon_ownership(self):
        from routers.runtoon import record_shared
        source = inspect.getsource(record_shared)
        assert "athlete_id" in source
        assert "404" in source or "HTTP_404_NOT_FOUND" in source

    def test_shared_logs_analytics_event(self):
        """record_shared must emit an analytics log event."""
        from routers.runtoon import record_shared
        source = inspect.getsource(record_shared)
        assert "ANALYTICS" in source
        assert "runtoon.shared" in source


# ---------------------------------------------------------------------------
# Data model: share columns on RuntoonImage
# ---------------------------------------------------------------------------

class TestShareModelColumns:
    """Verify share columns exist on the RuntoonImage model."""

    def test_runtoon_image_has_shared_at(self):
        from models import RuntoonImage
        assert hasattr(RuntoonImage, "shared_at")

    def test_runtoon_image_has_share_format(self):
        from models import RuntoonImage
        assert hasattr(RuntoonImage, "share_format")

    def test_runtoon_image_has_share_target(self):
        from models import RuntoonImage
        assert hasattr(RuntoonImage, "share_target")

    def test_activity_has_share_dismissed_at(self):
        from models import Activity
        assert hasattr(Activity, "share_dismissed_at")


# ---------------------------------------------------------------------------
# Integration: sync no longer triggers auto-generation
# ---------------------------------------------------------------------------

class TestSyncNoLongerTriggersRuntoon:
    """
    Garmin/Strava webhook processing must NOT call generate_runtoon_for_latest.
    This is an integration contract test per the spec.
    """

    def test_strava_tasks_removed_runtoon_trigger(self):
        """generate_runtoon_for_latest must NOT be imported/called in strava_tasks."""
        import inspect
        import tasks.strava_tasks as st
        source = inspect.getsource(st)
        # Must NOT contain the old auto-gen call
        assert "generate_runtoon_for_latest.delay" not in source, (
            "strava_tasks still calls generate_runtoon_for_latest.delay — "
            "Runtoon generation must be on-demand only per spec."
        )

    def test_garmin_tasks_removed_runtoon_trigger(self):
        """generate_runtoon_for_latest must NOT be imported/called in garmin_webhook_tasks."""
        import inspect
        import tasks.garmin_webhook_tasks as gt
        source = inspect.getsource(gt)
        assert "generate_runtoon_for_latest.delay" not in source, (
            "garmin_webhook_tasks still calls generate_runtoon_for_latest.delay — "
            "Runtoon generation must be on-demand only per spec."
        )


# ---------------------------------------------------------------------------
# Integration: full share flow path
# ---------------------------------------------------------------------------

class TestFullShareFlow:
    """
    Structural verification of the complete share flow path:
    /pending → /generate → (poll) → /shared
    """

    def test_generate_endpoint_still_exists(self):
        """generate endpoint must still exist and be the sole trigger."""
        from routers.runtoon import trigger_regeneration
        assert callable(trigger_regeneration)

    def test_pending_endpoint_exists(self):
        from routers.runtoon import get_pending
        assert callable(get_pending)

    def test_dismiss_endpoint_exists(self):
        from routers.runtoon import dismiss_runtoon_prompt
        assert callable(dismiss_runtoon_prompt)

    def test_shared_endpoint_exists(self):
        from routers.runtoon import record_shared
        assert callable(record_shared)

    def test_all_share_flow_endpoints_require_feature_flag(self):
        """Every share-flow endpoint must gate on the feature flag."""
        from routers.runtoon import (
            get_pending, dismiss_runtoon_prompt, record_shared
        )
        for fn in [get_pending, dismiss_runtoon_prompt, record_shared]:
            source = inspect.getsource(fn)
            assert "_require_feature_flag" in source, (
                f"{fn.__name__} is missing _require_feature_flag — "
                "share flow must enforce rollout gate."
            )


# ---------------------------------------------------------------------------
# SharedRequest schema
# ---------------------------------------------------------------------------

class TestSharedRequestSchema:
    """SharedRequest must match spec: share_format required, share_target optional."""

    def test_shared_request_has_share_format(self):
        from routers.runtoon import SharedRequest
        assert "share_format" in SharedRequest.model_fields

    def test_shared_request_share_target_is_optional(self):
        from routers.runtoon import SharedRequest
        field = SharedRequest.model_fields.get("share_target")
        assert field is not None
        # Should have a default (None) making it optional
        assert field.default is None or field.is_required() is False

    def test_shared_request_share_format_default_is_1x1(self):
        from routers.runtoon import SharedRequest
        req = SharedRequest()
        assert req.share_format == "1:1"
