"""
Regression: constraint-aware planner must not raise NameError when the
RPI-from-anchors/PBs fallback fires.

Background
----------
Before this fix, generate_plan() called the staticmethod
self._rpi_from_anchors_or_pbs(athlete_id, db) — but `db` is not bound in the
method scope (it is `self.db`). The bug only fired for athletes who hit the
fallback path:
  - bank.best_rpi is missing/zero (no race performance ever extracted), AND
  - goal_time is None or could not be converted into an RPI.

A production sweep of 96 athletes found 5 real users blocked by this exact
NameError. This test exercises that path explicitly so the regression cannot
return.
"""
from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from services.constraint_aware_planner import ConstraintAwarePlanner
from services.fitness_bank import (
    ConstraintType,
    ExperienceLevel,
    FitnessBank,
)


def _bank_without_rpi() -> FitnessBank:
    """A modest-but-real athlete with no race performance and no best_rpi."""
    return FitnessBank(
        athlete_id=str(uuid4()),
        peak_weekly_miles=30.0,
        peak_monthly_miles=110.0,
        peak_long_run_miles=14.0,
        peak_mp_long_run_miles=8.0,
        peak_threshold_miles=4.0,
        peak_ctl=45.0,
        race_performances=[],
        best_rpi=None,
        best_race=None,
        current_weekly_miles=18.0,
        current_ctl=35.0,
        current_atl=30.0,
        weeks_since_peak=4,
        current_long_run_miles=10.0,
        average_long_run_miles=8.0,
        tau1=42.0,
        tau2=7.0,
        experience_level=ExperienceLevel.INTERMEDIATE,
        constraint_type=ConstraintType.NONE,
        constraint_details=None,
        is_returning_from_break=False,
        typical_long_run_day=6,
        typical_quality_day=3,
        typical_rest_days=[0],
        weeks_to_80pct_ctl=0,
        weeks_to_race_ready=2,
        sustainable_peak_weekly=28.0,
        recent_quality_sessions_28d=2,
        recent_8w_median_weekly_miles=18.0,
        recent_16w_p90_weekly_miles=22.0,
        recent_8w_p75_long_run_miles=10.0,
        recent_16w_p50_long_run_miles=9.0,
        recent_16w_run_count=20,
        peak_confidence="medium",
        long_run_capability_proven=True,
    )


def test_rpi_fallback_does_not_raise_nameerror_for_athlete_without_anchors_or_pbs(
    monkeypatch,
):
    """
    Regression: an athlete with no best_rpi, no goal_time, no race anchors,
    and no eligible PBs must still receive a generated plan — not crash with
    NameError: name 'db' is not defined.
    """
    bank = _bank_without_rpi()
    athlete_id = uuid4()

    monkeypatch.setattr(
        "services.constraint_aware_planner.get_fitness_bank",
        lambda *_args, **_kwargs: bank,
    )
    monkeypatch.setattr(
        "services.constraint_aware_planner.build_load_context",
        lambda *_args, **_kwargs: SimpleNamespace(
            l30_max_easy_long_mi=10.0,
            history_override_easy_long=False,
            count_long_15plus=0,
            count_long_18plus=0,
            recency_last_18plus_days=999,
        ),
    )

    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = []

    planner = ConstraintAwarePlanner(db)

    plan = planner.generate_plan(
        athlete_id=athlete_id,
        race_date=date.today() + timedelta(weeks=10),
        race_distance="10k",
        goal_time=None,
        tune_up_races=None,
        target_peak_weekly_miles=None,
        target_peak_weekly_range=None,
        taper_weeks=None,
    )

    assert plan is not None, "Planner must return a plan, not crash"
    assert len(plan.weeks) > 0


def test_rpi_fallback_path_static_signature():
    """
    Guard the staticmethod signature so callers cannot accidentally
    re-introduce the `db` vs `self.db` mismatch via a refactor.

    _rpi_from_anchors_or_pbs(athlete_id, db) is a staticmethod and must be
    invoked with self.db (not a bare `db` name).
    """
    import inspect

    sig = inspect.signature(ConstraintAwarePlanner._rpi_from_anchors_or_pbs)
    params = list(sig.parameters)
    assert params == ["athlete_id", "db"], (
        f"Unexpected signature {params}. If you change this, update every call "
        "site in constraint_aware_planner.py to pass self.db, not bare db."
    )


def test_planner_generate_plan_passes_self_db_to_rpi_fallback():
    """
    Source-level guard: assert the call site uses `self.db`, not bare `db`,
    when invoking the RPI anchors/PBs fallback. Catches the original
    NameError before runtime.
    """
    import re

    from services import constraint_aware_planner as mod

    src = inspect_source(mod)
    assert "self._rpi_from_anchors_or_pbs(athlete_id, self.db)" in src, (
        "RPI-from-anchors/PBs fallback must pass self.db, not bare db."
    )
    bad_pattern = re.compile(
        r"self\._rpi_from_anchors_or_pbs\(\s*athlete_id\s*,\s*db\s*\)"
    )
    assert not bad_pattern.search(src), (
        "Found `self._rpi_from_anchors_or_pbs(athlete_id, db)` — `db` is not "
        "defined in generate_plan scope and will raise NameError at runtime."
    )


def inspect_source(module) -> str:
    import inspect

    return inspect.getsource(module)
