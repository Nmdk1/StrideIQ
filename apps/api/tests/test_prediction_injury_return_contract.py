from unittest.mock import MagicMock

from services.constraint_aware_planner import ConstraintAwarePlanner
from tests.fixtures.golden_athlete_fixture import build_golden_injury_return_bank


def _to_seconds(formatted: str) -> int:
    parts = [int(x) for x in formatted.split(":")]
    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    return 0


def test_injury_return_with_quality_gap_widens_prediction_range():
    planner = ConstraintAwarePlanner(db=MagicMock())
    bank = build_golden_injury_return_bank(recent_quality_sessions_28d=0)

    _, _, scenarios, tags, uncertainty_reason = planner._predict_race(bank, "marathon", None)

    conservative = _to_seconds(scenarios["conservative"]["time"])
    base = _to_seconds(scenarios["base"]["time"])
    aggressive = _to_seconds(scenarios["aggressive"]["time"])

    assert conservative > base > aggressive
    assert "injury_return" in tags
    assert "quality_gap" in tags
    assert uncertainty_reason is not None

