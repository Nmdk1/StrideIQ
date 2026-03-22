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
from services.fitness_bank import ConstraintType, ExperienceLevel, FitnessBank, RacePerformance
from services.plan_quality_gate import QualityGateResult, _compute_personal_long_run_floor


def _override_deps(db_session, athlete):
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_athlete] = lambda: athlete


def _clear_deps():
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_athlete, None)


def _fake_plan():
    day = SimpleNamespace(
        day_of_week=1,
        workout_type="threshold",
        target_miles=8.0,
        name="Threshold",
        description="2x3mi @ T",
        intensity="hard",
        paces={"threshold": "6:10"},
        notes=[],
        tss_estimate=80.0,
    )
    week = SimpleNamespace(
        week_number=1,
        theme=SimpleNamespace(value="build_t"),
        start_date=date.today() + timedelta(days=7),
        days=[day],
        total_miles=58.0,
        notes=[],
        to_dict=lambda: {
            "week": 1,
            "theme": "build_t",
            "start_date": (date.today() + timedelta(days=7)).isoformat(),
            "days": [{
                "day_of_week": 1,
                "workout_type": "threshold",
                "name": "Threshold",
                "description": "2x3mi @ T",
                "target_miles": 8.0,
                "intensity": "hard",
                "paces": {"threshold": "6:10"},
                "notes": [],
                "tss": 80.0,
            }],
            "total_miles": 58.0,
            "notes": [],
        },
    )
    return SimpleNamespace(
        weeks=[week],
        total_weeks=1,
        total_miles=58.0,
        race_date=date.today() + timedelta(days=70),
        race_distance="10k",
        tune_up_races=[],
        fitness_bank={
            "peak": {"weekly_miles": 70.0},
            "best_rpi": 52.0,
            "volume_contract": {
                "recent_8w_p75_long_run_miles": 15.0,
                "recent_16w_p50_long_run_miles": 14.0,
                "recent_16w_run_count": 40,
            },
            "constraint": {"type": "none"},
        },
        tau1=36.0,
        tau2=8.0,
        model_confidence="medium",
        counter_conventional_notes=[],
        predicted_time="39:20",
        prediction_ci="-2/+2 min",
        prediction_scenarios={
            "conservative": {"time": "40:20", "confidence": "medium"},
            "base": {"time": "39:20", "confidence": "high"},
            "aggressive": {"time": "38:30", "confidence": "low"},
        },
        prediction_rationale_tags=["trusted_recent_band"],
        prediction_uncertainty_reason=None,
        volume_contract={
            "band_min": 52.0,
            "band_max": 64.0,
            "source": "athlete_override",
            "peak_confidence": "high",
            "requested_peak": 68.0,
            "applied_peak": 68.0,
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


def test_constraint_aware_preserves_override_on_fallback(monkeypatch, db_session, subscriber_athlete):
    _override_deps(db_session, subscriber_athlete)
    client = TestClient(app)
    race = RacePerformance(
        date=date.today() - timedelta(days=40),
        distance="10k",
        distance_m=10000.0,
        finish_time_seconds=2360,
        pace_per_mile=6.33,
        rpi=55.0,
    )
    bank = FitnessBank(
        athlete_id=str(subscriber_athlete.id),
        peak_weekly_miles=72.0,
        peak_monthly_miles=280.0,
        peak_long_run_miles=18.0,
        peak_mp_long_run_miles=12.0,
        peak_threshold_miles=8.0,
        peak_ctl=85.0,
        race_performances=[race],
        best_rpi=55.0,
        best_race=race,
        current_weekly_miles=64.0,
        current_ctl=78.0,
        current_atl=72.0,
        weeks_since_peak=6,
        current_long_run_miles=16.0,
        average_long_run_miles=15.0,
        tau1=36.0,
        tau2=8.0,
        experience_level=ExperienceLevel.EXPERIENCED,
        constraint_type=ConstraintType.NONE,
        constraint_details=None,
        is_returning_from_break=False,
        typical_long_run_day=6,
        typical_quality_day=3,
        typical_rest_days=[0],
        weeks_to_80pct_ctl=0,
        weeks_to_race_ready=2,
        sustainable_peak_weekly=68.0,
        recent_quality_sessions_28d=5,
        recent_8w_median_weekly_miles=63.0,
        recent_16w_p90_weekly_miles=68.0,
        recent_8w_p75_long_run_miles=15.5,
        recent_16w_p50_long_run_miles=14.5,
        recent_16w_run_count=40,
        peak_confidence="high",
    )

    monkeypatch.setattr("services.constraint_aware_planner.get_fitness_bank", lambda _athlete_id, _db: bank)
    monkeypatch.setattr("services.plan_framework.feature_flags.FeatureFlagService.is_enabled", lambda *_: True)
    monkeypatch.setattr(plan_router, "_check_rate_limit", lambda *_: True)
    monkeypatch.setattr(plan_router, "_record_rate_limit", lambda *_: None)
    monkeypatch.setattr(plan_router, "_save_constraint_aware_plan", lambda *_args, **_kwargs: SimpleNamespace(id=uuid4()))

    resp = client.post(
        "/v2/plans/constraint-aware",
        json={
            "race_date": (date.today() + timedelta(days=70)).isoformat(),
            "race_distance": "10k",
            "target_peak_weekly_miles": 68,
        },
    )
    _clear_deps()
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["volume_contract"]["source"] == "athlete_override"
    assert payload["volume_contract"]["requested_peak"] == 68.0


def test_quality_gate_failed_payload_contract_shape(monkeypatch, db_session, subscriber_athlete):
    _override_deps(db_session, subscriber_athlete)
    client = TestClient(app)

    monkeypatch.setattr("services.constraint_aware_planner.generate_constraint_aware_plan", lambda **_kwargs: _fake_plan())
    monkeypatch.setattr(
        "services.plan_quality_gate.evaluate_constraint_aware_plan",
        lambda _plan: QualityGateResult(
            False,
            ["quality gate hard fail"],
            ["personal_long_run_floor_breach"],
            {"weekly_miles": {"min": 50.0, "max": 64.0}, "long_run_miles": {"min": 15.0, "max": 18.0}},
        ),
    )
    monkeypatch.setattr("services.plan_framework.feature_flags.FeatureFlagService.is_enabled", lambda *_: True)
    monkeypatch.setattr(plan_router, "_check_rate_limit", lambda *_: True)
    monkeypatch.setattr(plan_router, "_record_rate_limit", lambda *_: None)

    resp = client.post(
        "/v2/plans/constraint-aware",
        json={
            "race_date": (date.today() + timedelta(days=70)).isoformat(),
            "race_distance": "10k",
            "target_peak_weekly_miles": 68,
        },
    )
    _clear_deps()
    assert resp.status_code == 422, resp.text
    detail = resp.json().get("detail", {})
    assert detail.get("error_code") == "quality_gate_failed"
    assert detail.get("quality_gate_failed") is True
    assert "reasons" in detail and isinstance(detail["reasons"], list)
    assert "invariant_conflicts" in detail and isinstance(detail["invariant_conflicts"], list)
    assert "suggested_safe_bounds" in detail and "weekly_miles" in detail["suggested_safe_bounds"]
    assert "volume_contract_snapshot" in detail
    assert detail.get("next_action") == "adjust_inputs_or_accept_safe_bounds"


def test_personal_floor_formula_matches_p75_p50_definition():
    fitness_bank = {
        "peak": {"long_run": 20.0},
        "constraint": {"type": "none"},
        "volume_contract": {
            "recent_8w_p75_long_run_miles": 15.5,
            "recent_16w_p50_long_run_miles": 14.8,
            "recent_16w_run_count": 40,
        },
    }
    floor = _compute_personal_long_run_floor(fitness_bank, race_distance="10k")
    assert floor == 15.5
