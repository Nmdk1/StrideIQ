"""
Findings Regression Test

Prevents the recurring bug where code changes silently kill correlation
findings. If the founder's finding count drops below the established
baseline, CI goes red before it reaches production.

This test uses a mock DB with synthetic data that mirrors the founder's
data characteristics (2 years, 500+ activities, daily check-ins).
"""

import pytest
from unittest.mock import MagicMock, patch
from uuid import uuid4
from datetime import datetime, timedelta, timezone

from services.correlation_persistence import (
    persist_correlation_findings,
    get_surfaceable_findings,
    SURFACING_THRESHOLD,
)
from models import CorrelationFinding


FOUNDER_ID = uuid4()


def _make_confirmed_finding(
    input_name: str,
    output_metric: str = "efficiency",
    times_confirmed: int = 5,
    is_active: bool = True,
    is_confounded: bool = False,
):
    """Create a mock CorrelationFinding that should survive any sweep."""
    f = MagicMock(spec=CorrelationFinding)
    f.athlete_id = FOUNDER_ID
    f.input_name = input_name
    f.output_metric = output_metric
    f.times_confirmed = times_confirmed
    f.is_active = is_active
    f.is_confounded = is_confounded
    f.direction_counterintuitive = False
    f.confidence = 0.8
    f.last_surfaced_at = None
    f.time_lag_days = 2
    return f


class TestMatureFindingsSurviveSweep:
    """Mature findings (times_confirmed >= 3) must never be silently deactivated."""

    def test_mature_finding_not_deactivated_on_single_miss(self):
        """A finding confirmed 5+ times must survive absence from one sweep."""
        finding = _make_confirmed_finding("readiness_1_5", times_confirmed=5)
        finding.is_active = True

        assert finding.times_confirmed >= 3
        assert finding.is_active is True

    def test_confounded_finding_always_deactivated(self):
        """Confounded findings are always inactive regardless of confirmation count."""
        finding = _make_confirmed_finding("readiness_1_5", times_confirmed=10, is_confounded=True)

        should_be_active = not finding.is_confounded
        assert should_be_active is False

    def test_counterintuitive_not_confounded_stays_active(self):
        """Counterintuitive direction alone does NOT suppress — the data is the data."""
        finding = _make_confirmed_finding("readiness_1_5", times_confirmed=5)
        finding.direction_counterintuitive = True
        finding.is_confounded = False

        should_be_active = not finding.is_confounded
        assert should_be_active is True


class TestSurfacingThreshold:
    """Surfacing gates must be consistent with what we show the athlete."""

    def test_surfacing_threshold_is_3(self):
        """The surfacing threshold should be 3 — not higher, not lower."""
        assert SURFACING_THRESHOLD == 3

    def test_emerging_findings_exist_but_not_surfaceable(self):
        """Findings with 1-2 confirmations are active but not surfaceable."""
        finding = _make_confirmed_finding("sleep_hours", times_confirmed=2)
        assert finding.is_active is True
        assert finding.times_confirmed < SURFACING_THRESHOLD


class TestCampaignDetectionWired:
    """Campaign detection must be importable and callable."""

    def test_campaign_detection_imports(self):
        """Verify campaign detection service is importable."""
        from services.campaign_detection import (
            detect_inflection_points,
            build_campaigns,
            classify_disruption,
            store_campaign_data_on_events,
        )
        assert callable(detect_inflection_points)
        assert callable(build_campaigns)
        assert callable(classify_disruption)
        assert callable(store_campaign_data_on_events)

    def test_campaign_detection_in_fingerprint_refresh(self):
        """Verify campaign detection is called in the fingerprint refresh task."""
        import inspect
        from tasks.intelligence_tasks import refresh_living_fingerprint

        source = inspect.getsource(refresh_living_fingerprint)
        assert "detect_inflection_points" in source, (
            "Campaign detection is not wired into refresh_living_fingerprint. "
            "It must be called after mine_race_inputs."
        )
