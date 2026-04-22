"""Soft gate contract: the quality gate is advisory, not a wall. When the
first gate fails the system ALWAYS regenerates at the safe-range midpoint and
ALWAYS returns a plan, with structured warnings describing what was adjusted.

Three branches:
  - athlete supplied no override -> warning "auto_tuned_peak_to_safe_range:N"
  - athlete supplied an override that exceeded the safe range -> warning
    "capped_requested_peak_to_safe_range:OLD->NEW"
  - even the regen fails the second gate -> still 200 with warning
    "safe_range_regen_still_outside_band" so the athlete still sees a plan

The athlete decides; the system informs.
"""
from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from core.auth import get_current_athlete
from core.database import get_db
from main import app
from models import Athlete
from routers import plan_generation as plan_router
from services.plan_quality_gate import QualityGateResult, _enrich_with_display




def _override_deps(db_session, athlete):
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_athlete] = lambda: athlete


def _clear_deps():
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_athlete, None)


def _fake_plan(total_miles: float = 58.0):
    week = SimpleNamespace(
        week_number=1,
        start_date=date.today() + timedelta(days=7),
        days=[],
        total_miles=total_miles,
        notes=[],
        to_dict=lambda: {
            "week": 1,
            "theme": "build_t",
            "start_date": (date.today() + timedelta(days=7)).isoformat(),
            "days": [],
            "total_miles": total_miles,
            "notes": [],
        },
    )
    return SimpleNamespace(
        weeks=[week],
        total_weeks=1,
        total_miles=total_miles,
        race_date=date.today() + timedelta(days=70),
        race_distance="10k",
        tune_up_races=[],
        fitness_bank={"peak": {"weekly_miles": 70.0}, "constraint": {"type": "none"}},
        tau1=36.0,
        tau2=8.0,
        model_confidence="medium",
        counter_conventional_notes=[],
        predicted_time="39:20",
        prediction_ci="-2/+2 min",
        prediction_scenarios={},
        prediction_rationale_tags=[],
        prediction_uncertainty_reason=None,
        volume_contract={
            "band_min": 18.0,
            "band_max": 24.0,
            "source": "history",
            "peak_confidence": "medium",
            "requested_peak": None,
            "applied_peak": 22.0,
            "clamped": False,
            "clamp_reason": None,
        },
        quality_gate_fallback=False,
        quality_gate_reasons=[],
    )


@pytest.fixture
def subscriber_athlete(db_session):
    athlete = Athlete(
        id=uuid4(),
        email=f"subscriber_{uuid4()}@example.com",
        display_name="Subscriber Athlete",
        subscription_tier="subscriber",
        birthdate=date(1990, 1, 1),
        sex="M",
    )
    db_session.add(athlete)
    db_session.commit()
    db_session.refresh(athlete)
    return athlete


def _patch_intake_gate(monkeypatch):
    from services.intake_context import IntakeContext
    monkeypatch.setattr(
        "services.intake_context.get_intake_context",
        lambda _aid, _db: IntakeContext(basic_profile_completed=True, goals_completed=True),
    )


def test_soft_gate_returns_200_with_warning_when_no_override_and_second_pass_passes(
    monkeypatch, db_session, subscriber_athlete
):
    _override_deps(db_session, subscriber_athlete)
    _patch_intake_gate(monkeypatch)
    client = TestClient(app)

    # First gate call returns failure with safe bounds. Second call passes.
    gate_calls = {"count": 0}

    def gate_side_effect(_plan):
        gate_calls["count"] += 1
        if gate_calls["count"] == 1:
            return _enrich_with_display(QualityGateResult(
                False,
                ["Week 1 exceeds trusted band ceiling: 30.0 > 24.0."],
                ["weekly_volume_exceeds_trusted_band"],
                {"weekly_miles": {"min": 18.0, "max": 24.0}, "long_run_miles": {"min": 8.0, "max": 14.0}},
            ))
        return _enrich_with_display(QualityGateResult(
            True, [], [], {"weekly_miles": {"min": 18.0, "max": 24.0}, "long_run_miles": {"min": 8.0, "max": 14.0}},
        ))

    monkeypatch.setattr(
        "services.plan_quality_gate.evaluate_constraint_aware_plan",
        gate_side_effect,
    )
    monkeypatch.setattr(
        "services.constraint_aware_planner.generate_constraint_aware_plan",
        lambda **_kwargs: _fake_plan(),
    )
    monkeypatch.setattr("services.plan_framework.feature_flags.FeatureFlagService.is_enabled", lambda *_: True)
    monkeypatch.setattr(plan_router, "_check_rate_limit", lambda *_: True)
    monkeypatch.setattr(plan_router, "_record_rate_limit", lambda *_: None)
    monkeypatch.setattr(plan_router, "_save_constraint_aware_plan", lambda *_args, **_kwargs: SimpleNamespace(id=uuid4()))

    resp = client.post(
        "/v2/plans/constraint-aware",
        json={
            "race_date": (date.today() + timedelta(days=70)).isoformat(),
            "race_distance": "10k",
            # Athlete supplied NO peak override.
        },
    )
    _clear_deps()
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["success"] is True
    assert "warnings" in payload
    assert isinstance(payload["warnings"], list)
    assert any("auto_tuned_peak_to_safe_range" in w for w in payload["warnings"])
    assert payload.get("soft_gate_applied_peak_weekly_miles") is not None
    # The midpoint of {18, 24} is 21.0
    assert payload["soft_gate_applied_peak_weekly_miles"] == pytest.approx(21.0, abs=0.05)


def test_soft_gate_caps_athlete_override_to_safe_range_with_warning(
    monkeypatch, db_session, subscriber_athlete
):
    """When the athlete supplies a peak that fails the gate, we still cap to
    the safe-range midpoint and surface a `capped_requested_peak_to_safe_range`
    warning so they see exactly what was changed and what they asked for."""
    _override_deps(db_session, subscriber_athlete)
    _patch_intake_gate(monkeypatch)
    client = TestClient(app)

    gate_calls = {"count": 0}

    def gate_side_effect(_plan):
        gate_calls["count"] += 1
        if gate_calls["count"] == 1:
            return _enrich_with_display(QualityGateResult(
                False,
                ["Week 1 exceeds trusted band ceiling."],
                ["weekly_volume_exceeds_trusted_band"],
                {"weekly_miles": {"min": 18.0, "max": 24.0}, "long_run_miles": {"min": 8.0, "max": 14.0}},
            ))
        return _enrich_with_display(QualityGateResult(
            True, [], [], {"weekly_miles": {"min": 18.0, "max": 24.0}, "long_run_miles": {"min": 8.0, "max": 14.0}},
        ))

    monkeypatch.setattr(
        "services.plan_quality_gate.evaluate_constraint_aware_plan",
        gate_side_effect,
    )
    monkeypatch.setattr(
        "services.constraint_aware_planner.generate_constraint_aware_plan",
        lambda **_kwargs: _fake_plan(),
    )
    monkeypatch.setattr("services.plan_framework.feature_flags.FeatureFlagService.is_enabled", lambda *_: True)
    monkeypatch.setattr(plan_router, "_check_rate_limit", lambda *_: True)
    monkeypatch.setattr(plan_router, "_record_rate_limit", lambda *_: None)
    monkeypatch.setattr(plan_router, "_save_constraint_aware_plan", lambda *_args, **_kwargs: SimpleNamespace(id=uuid4()))

    resp = client.post(
        "/v2/plans/constraint-aware",
        json={
            "race_date": (date.today() + timedelta(days=70)).isoformat(),
            "race_distance": "10k",
            "target_peak_weekly_miles": 30,
        },
    )
    _clear_deps()
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert any(
        w.startswith("capped_requested_peak_to_safe_range:") for w in payload.get("warnings", [])
    )
    assert payload.get("soft_gate_applied_peak_weekly_miles") == pytest.approx(21.0, abs=0.05)
    assert payload.get("soft_gate_requested_peak_weekly_miles") == 30


def test_soft_gate_drops_athlete_range_with_dedicated_warning(
    monkeypatch, db_session, subscriber_athlete
):
    """When the athlete supplied a peak RANGE (min/max) instead of a single
    peak and the gate fails, the cap collapses the range to a single peak.
    We surface that with `dropped_requested_range_to_safe_peak:N` so the
    athlete sees that their range intent was replaced — not silently dropped."""
    _override_deps(db_session, subscriber_athlete)
    _patch_intake_gate(monkeypatch)
    client = TestClient(app)

    gate_calls = {"count": 0}

    def gate_side_effect(_plan):
        gate_calls["count"] += 1
        if gate_calls["count"] == 1:
            return _enrich_with_display(QualityGateResult(
                False,
                ["Week 1 exceeds trusted band ceiling."],
                ["weekly_volume_exceeds_trusted_band"],
                {"weekly_miles": {"min": 18.0, "max": 24.0}, "long_run_miles": {"min": 8.0, "max": 14.0}},
            ))
        return _enrich_with_display(QualityGateResult(
            True, [], [], {"weekly_miles": {"min": 18.0, "max": 24.0}, "long_run_miles": {"min": 8.0, "max": 14.0}},
        ))

    monkeypatch.setattr(
        "services.plan_quality_gate.evaluate_constraint_aware_plan",
        gate_side_effect,
    )
    monkeypatch.setattr(
        "services.constraint_aware_planner.generate_constraint_aware_plan",
        lambda **_kwargs: _fake_plan(),
    )
    monkeypatch.setattr("services.plan_framework.feature_flags.FeatureFlagService.is_enabled", lambda *_: True)
    monkeypatch.setattr(plan_router, "_check_rate_limit", lambda *_: True)
    monkeypatch.setattr(plan_router, "_record_rate_limit", lambda *_: None)
    monkeypatch.setattr(plan_router, "_save_constraint_aware_plan", lambda *_args, **_kwargs: SimpleNamespace(id=uuid4()))

    resp = client.post(
        "/v2/plans/constraint-aware",
        json={
            "race_date": (date.today() + timedelta(days=70)).isoformat(),
            "race_distance": "10k",
            "target_peak_weekly_range": {"min": 35, "max": 45},
        },
    )
    _clear_deps()
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    warnings = payload.get("warnings") or []
    assert any(
        w.startswith("dropped_requested_range_to_safe_peak:") for w in warnings
    ), f"expected dropped_requested_range_to_safe_peak warning, got {warnings}"
    assert payload.get("soft_gate_applied_peak_weekly_miles") == pytest.approx(21.0, abs=0.05)
    assert payload.get("soft_gate_requested_peak_weekly_miles") is None


def test_soft_gate_returns_200_with_warning_when_safe_range_regen_also_fails(
    monkeypatch, db_session, subscriber_athlete
):
    """The gate is advisory, not a wall. Even when both passes fail we return
    a plan + a `safe_range_regen_still_outside_band` warning + the gate's
    display message so the athlete can see what we built and why we flagged it.
    Never 422 — the athlete decides."""
    _override_deps(db_session, subscriber_athlete)
    _patch_intake_gate(monkeypatch)
    client = TestClient(app)

    monkeypatch.setattr(
        "services.plan_quality_gate.evaluate_constraint_aware_plan",
        lambda _plan: _enrich_with_display(QualityGateResult(
            False,
            ["Persistent quality failure."],
            ["weekly_volume_exceeds_trusted_band"],
            {"weekly_miles": {"min": 18.0, "max": 24.0}, "long_run_miles": {"min": 8.0, "max": 14.0}},
        )),
    )
    monkeypatch.setattr(
        "services.constraint_aware_planner.generate_constraint_aware_plan",
        lambda **_kwargs: _fake_plan(),
    )
    monkeypatch.setattr("services.plan_framework.feature_flags.FeatureFlagService.is_enabled", lambda *_: True)
    monkeypatch.setattr(plan_router, "_check_rate_limit", lambda *_: True)
    monkeypatch.setattr(plan_router, "_record_rate_limit", lambda *_: None)

    resp = client.post(
        "/v2/plans/constraint-aware",
        json={
            "race_date": (date.today() + timedelta(days=70)).isoformat(),
            "race_distance": "10k",
        },
    )
    _clear_deps()
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["success"] is True
    warnings = payload.get("warnings") or []
    assert any("safe_range_regen_still_outside_band" in w for w in warnings)
    assert payload.get("soft_gate_display_message")
    assert "weekly_miles" in (payload.get("soft_gate_safe_bounds_km") or {})
    assert payload.get("soft_gate_reasons")
