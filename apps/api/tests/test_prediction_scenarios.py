from unittest.mock import MagicMock

from services.constraint_aware_planner import ConstraintAwarePlanner
from tests.fixtures.golden_athlete_fixture import build_golden_injury_return_bank


def _confidence_rank(level: str) -> int:
    return {"low": 0, "medium": 1, "high": 2}.get(level, 0)


def test_prediction_returns_scenarios_and_rationale_tags():
    planner = ConstraintAwarePlanner(db=MagicMock())
    bank = build_golden_injury_return_bank(recent_quality_sessions_28d=0)

    predicted, ci, scenarios, tags, uncertainty_reason = planner._predict_race(
        bank,
        "marathon",
        None,
    )

    assert predicted == scenarios["base"]["time"]
    assert isinstance(ci, str) and ci
    assert set(scenarios.keys()) == {"conservative", "base", "aggressive"}
    assert "injury_return" in tags
    assert "quality_gap" in tags
    assert uncertainty_reason is not None


def test_confidence_monotonicity_with_quality_continuity():
    planner = ConstraintAwarePlanner(db=MagicMock())
    low_quality = build_golden_injury_return_bank(recent_quality_sessions_28d=0)
    high_quality = build_golden_injury_return_bank(recent_quality_sessions_28d=6)

    _, _, scenarios_low, _, _ = planner._predict_race(low_quality, "marathon", None)
    _, _, scenarios_high, _, _ = planner._predict_race(high_quality, "marathon", None)

    assert _confidence_rank(scenarios_high["base"]["confidence"]) >= _confidence_rank(
        scenarios_low["base"]["confidence"]
    )

