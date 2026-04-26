"""Tests for the limiter lifecycle classifier (Phase 3).

Covers:
  1. CG-12: L-SPEC context gate fires for advanced pre-race athlete
  2. CG-12: L-SPEC does not fire for beginner or no race
  3. CG-11: structural L-REC (half-life >48h + stable 90+ days)
  4. CG-11: structural monitored (half-life 36-48h + stable)
  5. CG-11: solvable L-REC (half-life <36h + recent emergence)
  6. CG-11: solvable L-REC (half-life 36-48h + recent)
  7. CG-10: fast recoverer TSB correlation = no L-REC (timing signal)
  8. CG-10: slow recoverer TSB correlation = L-REC
  9. Standard: new finding < 60 days + < 5 confirmations = emerging
 10. Standard: confirmed finding not seen in 90+ days = closed
 11. Standard: confirmed finding fading = resolving
 12. Standard: active finding (recent, confirmed)
 13. _detect_limiter: closed findings do not drive limiter
 14. _detect_limiter: active_fixed → race_specific limiter
 15. _detect_limiter: structural findings do not drive limiter
"""
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from services.plan_framework.limiter_classifier import (
    _classify_lrec,
    _classify_standard,
    _is_recent,
    _is_stable,
    _check_lspec_gate,
    STRUCTURAL_STABILITY_DAYS,
    SOLVABLE_EMERGENCE_DAYS,
    ADVANCED_PEAK_MILES_FLOOR,
)

from services.plan_framework.fingerprint_bridge import _detect_limiter

ATHLETE_ID = uuid.uuid4()
NOW = datetime(2026, 3, 29, 12, 0, 0, tzinfo=timezone.utc)


def _make_finding(**overrides):
    """Build a mock CorrelationFinding with sensible defaults."""
    defaults = {
        "id": uuid.uuid4(),
        "athlete_id": ATHLETE_ID,
        "input_name": "daily_session_stress",
        "output_metric": "efficiency",
        "direction": "negative",
        "correlation_coefficient": -0.58,
        "p_value": 0.001,
        "sample_size": 44,
        "strength": "moderate",
        "times_confirmed": 8,
        "first_detected_at": NOW - timedelta(days=200),
        "last_confirmed_at": NOW - timedelta(days=5),
        "is_active": True,
        "lifecycle_state": None,
        "lifecycle_state_updated_at": None,
    }
    defaults.update(overrides)
    finding = MagicMock()
    for k, v in defaults.items():
        setattr(finding, k, v)
    return finding


def _make_finding_dict(**overrides):
    """Build a finding dict as consumed by _detect_limiter."""
    defaults = {
        "input_name": "daily_session_stress",
        "output_metric": "efficiency",
        "direction": "negative",
        "correlation_coefficient": -0.58,
        "times_confirmed": 8,
        "sample_size": 44,
        "lifecycle_state": "active",
    }
    defaults.update(overrides)
    return defaults


# ---------------------------------------------------------------------------
# CG-11: L-REC structural discriminator
# ---------------------------------------------------------------------------

def test_cg11_structural_high_halflife_stable():
    """half-life >48h + stable 90+ days → structural"""
    finding = _make_finding(
        first_detected_at=NOW - timedelta(days=200),
        times_confirmed=10,
    )
    result = _classify_lrec(finding, half_life=51.3, now=NOW)
    assert result == "structural"


def test_cg11_structural_monitored_mid_halflife_stable():
    """half-life 36-48h + stable → structural_monitored"""
    finding = _make_finding(
        first_detected_at=NOW - timedelta(days=150),
        times_confirmed=6,
    )
    result = _classify_lrec(finding, half_life=42.0, now=NOW)
    assert result == "structural_monitored"


def test_cg11_solvable_low_halflife_recent():
    """half-life <36h + recent emergence → active (solvable)"""
    finding = _make_finding(
        first_detected_at=NOW - timedelta(days=30),
        times_confirmed=3,
    )
    result = _classify_lrec(finding, half_life=28.0, now=NOW)
    assert result == "active"


def test_cg11_solvable_mid_halflife_recent():
    """half-life 36-48h + recent emergence → active (solvable)"""
    finding = _make_finding(
        first_detected_at=NOW - timedelta(days=40),
        times_confirmed=3,
    )
    result = _classify_lrec(finding, half_life=40.0, now=NOW)
    assert result == "active"


# ---------------------------------------------------------------------------
# CG-10: CS-6/CS-7 interaction gate
# ---------------------------------------------------------------------------

def test_cg10_fast_recoverer_tsb_not_lrec():
    """TSB correlation with |r| > 0.45 and half-life ≤ 36h → not L-REC (timing signal)"""
    finding = _make_finding(
        input_name="tsb",
        correlation_coefficient=0.52,
        first_detected_at=NOW - timedelta(days=200),
        times_confirmed=10,
    )
    result = _classify_lrec(finding, half_life=23.8, now=NOW)
    assert result is None, "Fast recoverer with TSB correlation should not be classified as L-REC"


def test_cg10_slow_recoverer_tsb_is_lrec():
    """TSB correlation with |r| > 0.45 and half-life > 36h → L-REC"""
    finding = _make_finding(
        input_name="tsb",
        correlation_coefficient=0.52,
        first_detected_at=NOW - timedelta(days=200),
        times_confirmed=10,
    )
    result = _classify_lrec(finding, half_life=51.3, now=NOW)
    assert result == "structural"


# ---------------------------------------------------------------------------
# Standard lifecycle classification
# ---------------------------------------------------------------------------

def test_standard_emerging():
    """New finding < 60 days + < 5 confirmations → emerging"""
    finding = _make_finding(
        input_name="weekly_volume_km",
        first_detected_at=NOW - timedelta(days=30),
        last_confirmed_at=NOW - timedelta(days=5),
        times_confirmed=3,
        correlation_coefficient=0.45,
    )
    result = _classify_standard(finding, NOW)
    assert result == "emerging"


def test_standard_closed_not_confirmed_recently():
    """Not confirmed in 90+ days → closed"""
    finding = _make_finding(
        input_name="weekly_volume_km",
        first_detected_at=NOW - timedelta(days=300),
        last_confirmed_at=NOW - timedelta(days=95),
        times_confirmed=15,
        correlation_coefficient=0.65,
    )
    result = _classify_standard(finding, NOW)
    assert result == "closed"


def test_standard_resolving():
    """Confirmed 60-90 days ago + weakening (r < 0.40) → resolving"""
    finding = _make_finding(
        input_name="weekly_volume_km",
        first_detected_at=NOW - timedelta(days=200),
        last_confirmed_at=NOW - timedelta(days=70),
        times_confirmed=8,
        correlation_coefficient=0.35,
    )
    result = _classify_standard(finding, NOW)
    assert result == "resolving"


def test_standard_active():
    """Recently confirmed + strong correlation → active"""
    finding = _make_finding(
        input_name="weekly_volume_km",
        first_detected_at=NOW - timedelta(days=120),
        last_confirmed_at=NOW - timedelta(days=3),
        times_confirmed=12,
        correlation_coefficient=0.65,
    )
    result = _classify_standard(finding, NOW)
    assert result == "active"


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def test_is_recent_true():
    finding = _make_finding(first_detected_at=NOW - timedelta(days=30))
    assert _is_recent(finding, NOW) is True


def test_is_recent_false():
    finding = _make_finding(first_detected_at=NOW - timedelta(days=90))
    assert _is_recent(finding, NOW) is False


def test_is_stable_true():
    finding = _make_finding(
        first_detected_at=NOW - timedelta(days=120),
        times_confirmed=8,
    )
    assert _is_stable(finding, NOW) is True


def test_is_stable_false_too_new():
    finding = _make_finding(
        first_detected_at=NOW - timedelta(days=30),
        times_confirmed=8,
    )
    assert _is_stable(finding, NOW) is False


def test_is_stable_false_too_few_confirmations():
    finding = _make_finding(
        first_detected_at=NOW - timedelta(days=120),
        times_confirmed=3,
    )
    assert _is_stable(finding, NOW) is False


# ---------------------------------------------------------------------------
# _detect_limiter: lifecycle-aware filtering
# ---------------------------------------------------------------------------

def test_detect_limiter_closed_findings_ignored():
    """Closed findings do not contribute to limiter signal."""
    findings = [
        _make_finding_dict(
            input_name="long_run_ratio",
            output_metric="pace_threshold",
            correlation_coefficient=0.75,
            times_confirmed=20,
            lifecycle_state="closed",
        ),
    ]
    limiter, _ = _detect_limiter(findings)
    assert limiter is None


def test_detect_limiter_active_fixed_returns_race_specific():
    """active_fixed findings → race_specific limiter (L-SPEC)."""
    findings = [
        _make_finding_dict(
            input_name="lspec_rule_based",
            output_metric="race_readiness",
            correlation_coefficient=1.0,
            times_confirmed=3,
            lifecycle_state="active_fixed",
        ),
    ]
    limiter, _ = _detect_limiter(findings)
    assert limiter == "race_specific"


def test_detect_limiter_structural_not_counted():
    """Structural findings do not drive limiter assignment."""
    findings = [
        _make_finding_dict(
            input_name="daily_session_stress",
            output_metric="efficiency",
            correlation_coefficient=-0.58,
            times_confirmed=8,
            lifecycle_state="structural",
        ),
    ]
    limiter, _ = _detect_limiter(findings)
    assert limiter is None


def test_detect_limiter_active_volume():
    """Active L-VOL findings drive volume limiter."""
    findings = [
        _make_finding_dict(
            input_name="long_run_ratio",
            output_metric="pace_threshold",
            correlation_coefficient=0.65,
            times_confirmed=6,
            lifecycle_state="active",
        ),
    ]
    limiter, _ = _detect_limiter(findings)
    assert limiter == "volume"


def test_detect_limiter_active_recovery():
    """Active L-REC findings drive recovery limiter."""
    findings = [
        _make_finding_dict(
            input_name="daily_session_stress",
            output_metric="efficiency",
            correlation_coefficient=-0.58,
            times_confirmed=5,
            lifecycle_state="active",
        ),
    ]
    limiter, _ = _detect_limiter(findings)
    assert limiter == "recovery"


def test_detect_limiter_none_lifecycle_treated_as_active():
    """Findings without lifecycle_state (pre-Phase 3 data) are treated as active."""
    findings = [
        _make_finding_dict(
            input_name="long_run_ratio",
            output_metric="pace_threshold",
            correlation_coefficient=0.55,
            times_confirmed=5,
            lifecycle_state=None,
        ),
    ]
    limiter, _ = _detect_limiter(findings)
    assert limiter == "volume"


def test_detect_limiter_threshold():
    """Active L-THRESH findings drive threshold limiter."""
    findings = [
        _make_finding_dict(
            input_name="days_since_quality",
            output_metric="pace_threshold",
            correlation_coefficient=0.60,
            times_confirmed=5,
            lifecycle_state="active",
        ),
    ]
    limiter, _ = _detect_limiter(findings)
    assert limiter == "threshold"


def test_detect_limiter_structural_monitored_not_counted():
    """structural_monitored findings do not drive limiter assignment."""
    findings = [
        _make_finding_dict(
            input_name="daily_session_stress",
            output_metric="efficiency",
            correlation_coefficient=-0.58,
            times_confirmed=8,
            lifecycle_state="structural_monitored",
        ),
    ]
    limiter, _ = _detect_limiter(findings)
    assert limiter is None


# ---------------------------------------------------------------------------
# active_fixed resolution path
# ---------------------------------------------------------------------------

def test_active_fixed_resolves_when_lspec_gate_closes():
    """Non-synthetic active_fixed finding → closed (cleanup of old blanket override)."""
    from services.plan_framework.limiter_classifier import classify_lifecycle_states

    finding = _make_finding(
        input_name="daily_session_stress",
        lifecycle_state="active_fixed",
        lifecycle_state_updated_at=NOW - timedelta(days=14),
    )

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.all.return_value = [finding]
    mock_db.flush = MagicMock()

    with patch("services.plan_framework.limiter_classifier._get_profile") as mock_profile, \
         patch("services.plan_framework.limiter_classifier._check_lspec_gate") as mock_lspec, \
         patch("services.plan_framework.limiter_classifier._manage_lspec_finding") as mock_manage:
        mock_profile.return_value = MagicMock(
            recovery_half_life_hours=40.0,
            peak_weekly_miles=50.0,
        )
        mock_lspec.return_value = False
        mock_manage.return_value = None

        results = classify_lifecycle_states(ATHLETE_ID, mock_db)

    assert results[finding.id] == "closed"
    assert finding.lifecycle_state == "closed"


# ---------------------------------------------------------------------------
# structural_monitored bridge disclosure
# ---------------------------------------------------------------------------

def test_structural_monitored_produces_monitored_disclosure():
    """structural_monitored findings produce distinct disclosure text."""
    from services.plan_framework.fingerprint_bridge import FingerprintParams, STRUCTURAL_STATES

    assert "structural_monitored" in STRUCTURAL_STATES
    assert "structural" in STRUCTURAL_STATES


# ---------------------------------------------------------------------------
# L-SPEC synthetic finding management
# ---------------------------------------------------------------------------

def test_manage_lspec_creates_synthetic_finding():
    """L-SPEC gate active → synthetic finding created with active_fixed."""
    from services.plan_framework.limiter_classifier import (
        _manage_lspec_finding, LSPEC_INPUT_NAME,
    )

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None

    result = _manage_lspec_finding(ATHLETE_ID, mock_db, NOW, lspec_active=True)

    assert result is not None
    assert result.input_name == LSPEC_INPUT_NAME
    assert result.lifecycle_state == "active_fixed"
    assert result.correlation_coefficient == 1.0
    assert result.discovery_source == "lspec_rule"
    mock_db.add.assert_called_once()


def test_manage_lspec_reactivates_existing():
    """L-SPEC gate active + existing closed finding → reactivated."""
    from services.plan_framework.limiter_classifier import (
        _manage_lspec_finding, LSPEC_INPUT_NAME,
    )

    existing = MagicMock()
    existing.lifecycle_state = "closed"
    existing.is_active = False

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = existing

    result = _manage_lspec_finding(ATHLETE_ID, mock_db, NOW, lspec_active=True)

    assert result.lifecycle_state == "active_fixed"
    assert result.is_active is True
    mock_db.add.assert_not_called()


def test_manage_lspec_deactivates_when_gate_closes():
    """L-SPEC gate inactive + existing active_fixed → closed + deactivated."""
    from services.plan_framework.limiter_classifier import _manage_lspec_finding

    existing = MagicMock()
    existing.lifecycle_state = "active_fixed"
    existing.is_active = True

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = existing

    result = _manage_lspec_finding(ATHLETE_ID, mock_db, NOW, lspec_active=False)

    assert result.lifecycle_state == "closed"
    assert result.is_active is False


def test_manage_lspec_noop_when_inactive_no_existing():
    """L-SPEC gate inactive + no existing finding → returns None."""
    from services.plan_framework.limiter_classifier import _manage_lspec_finding

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None

    result = _manage_lspec_finding(ATHLETE_ID, mock_db, NOW, lspec_active=False)
    assert result is None


def test_lspec_does_not_override_other_findings():
    """When L-SPEC fires, other findings keep their correct lifecycle states."""
    from services.plan_framework.limiter_classifier import classify_lifecycle_states

    volume_finding = _make_finding(
        input_name="long_run_ratio",
        output_metric="pace_threshold",
        correlation_coefficient=0.65,
        times_confirmed=12,
        first_detected_at=NOW - timedelta(days=120),
        last_confirmed_at=NOW - timedelta(days=3),
        lifecycle_state="active",
    )

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.all.return_value = [volume_finding]
    mock_db.flush = MagicMock()

    lspec_finding = MagicMock()
    lspec_finding.id = uuid.uuid4()
    lspec_finding.lifecycle_state = "active_fixed"

    with patch("services.plan_framework.limiter_classifier._get_profile") as mock_profile, \
         patch("services.plan_framework.limiter_classifier._check_lspec_gate") as mock_lspec, \
         patch("services.plan_framework.limiter_classifier._manage_lspec_finding") as mock_manage:
        mock_profile.return_value = MagicMock(
            recovery_half_life_hours=40.0,
            peak_weekly_miles=50.0,
        )
        mock_lspec.return_value = True
        mock_manage.return_value = lspec_finding

        results = classify_lifecycle_states(ATHLETE_ID, mock_db)

    assert results[volume_finding.id] == "active", (
        "Volume finding should stay active when L-SPEC fires, not become active_fixed"
    )
    assert results[lspec_finding.id] == "active_fixed"


# ---------------------------------------------------------------------------
# CG-10 in _detect_limiter (bridge layer)
# ---------------------------------------------------------------------------

def test_cg10_bridge_michael_scenario():
    """Michael: TSB r=0.52 + half-life 23.8h → NOT L-REC."""
    findings = [
        _make_finding_dict(
            input_name="tsb",
            output_metric="pace_threshold",
            correlation_coefficient=0.52,
            times_confirmed=5,
            lifecycle_state="active",
        ),
    ]
    limiter, notes = _detect_limiter(findings, recovery_half_life_hours=23.8)
    assert limiter is None
    assert any("Freshness" in n for n in notes)


def test_cg10_bridge_slow_recoverer():
    """Slow recoverer: TSB r=0.55 + half-life 52h → L-REC."""
    findings = [
        _make_finding_dict(
            input_name="tsb",
            output_metric="pace_threshold",
            correlation_coefficient=0.55,
            times_confirmed=5,
            lifecycle_state="active",
        ),
    ]
    limiter, notes = _detect_limiter(findings, recovery_half_life_hours=52.0)
    assert limiter == "recovery"
    assert len(notes) == 0
