"""Phase I — strength v1 engine input additions + surface gate.

Two responsibilities are pinned here:

  1. The new aggregators in
     ``services/intelligence/strength_v1_inputs.py`` produce the
     correct numeric series from per-set RPE rows
     (``ct_strength_avg_rpe_per_session`` /
     ``ct_strength_max_rpe_per_session``) and from
     ``BodyAreaSymptomLog`` rows (``niggle_count_28d``,
     ``ache_count_28d``, ``pain_count_28d``,
     ``injury_active_flag``). These are *additive* engine inputs —
     the correlation engine still owns finding generation; we just
     give it more candidate signals.

  2. The Personal Operating Manual applies a *strict* surface gate
     to strength-domain findings: ``sample_size >= 4 AND
     p_value < 0.05`` before any strength finding renders to the
     athlete (see ``_passes_strength_surface_gate`` in
     ``services/operating_manual.py``). Other domains are
     unaffected. Findings missing the new statistical columns
     (older snapshots) pass through unchanged.

The aggregators are pure read paths over fixture rows; e2e tests
that exercise the engine end-to-end against Postgres are skipped
locally (CI runs them).
"""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------
# Source contract
# ---------------------------------------------------------------------


class TestSourceContract:
    def test_aggregators_exist(self):
        from services.intelligence.strength_v1_inputs import (
            aggregate_per_set_rpe_inputs,
            aggregate_strength_v1_inputs,
            aggregate_symptom_inputs,
        )

        assert callable(aggregate_per_set_rpe_inputs)
        assert callable(aggregate_symptom_inputs)
        assert callable(aggregate_strength_v1_inputs)

    def test_correlation_engine_invokes_phase_i_aggregator(self):
        """Engine must merge phase I inputs at the end of the cross-training
        aggregator. We pin this by source-string check so a future refactor
        that drops the call gets caught."""
        from pathlib import Path

        engine_src = Path(
            __file__
        ).resolve().parents[1] / "services" / "intelligence" / "correlation_engine.py"
        text = engine_src.read_text(encoding="utf-8")
        assert "aggregate_strength_v1_inputs" in text

    def test_strength_surface_gate_helper_exists(self):
        from services.operating_manual import _passes_strength_surface_gate

        assert callable(_passes_strength_surface_gate)


# ---------------------------------------------------------------------
# Per-set RPE aggregator
# ---------------------------------------------------------------------


def _activity(act_id: str, when: datetime):
    return SimpleNamespace(id=act_id, start_time=when)


class TestPerSetRpeAggregator:
    """Drive the aggregator with a stubbed Session so we don't need
    Postgres. We mock both queries (Activity rows and rpe rows) and
    confirm the math + sort order."""

    def _make_db(self, activities, rpe_rows):
        db = MagicMock()
        # First .query(...).filter(...).order_by(...).all() returns
        # activities; second returns rpe rows. We chain by patching
        # the .all() side effect.
        order_by = MagicMock()
        order_by.all.return_value = activities

        first_filter = MagicMock()
        first_filter.order_by.return_value = order_by

        first_query = MagicMock()
        first_query.filter.return_value = first_filter

        second_filter = MagicMock()
        second_filter.all.return_value = rpe_rows

        second_query = MagicMock()
        second_query.filter.return_value = second_filter

        db.query.side_effect = [first_query, second_query]
        return db

    def test_no_strength_activities_returns_empty(self):
        from services.intelligence.strength_v1_inputs import (
            aggregate_per_set_rpe_inputs,
        )

        db = self._make_db(activities=[], rpe_rows=[])
        out = aggregate_per_set_rpe_inputs(
            "athlete-id",
            datetime(2026, 4, 1),
            datetime(2026, 4, 30),
            db,
        )
        assert out == {}

    def test_no_rpe_rows_returns_empty(self):
        from services.intelligence.strength_v1_inputs import (
            aggregate_per_set_rpe_inputs,
        )

        db = self._make_db(
            activities=[_activity("a1", datetime(2026, 4, 5))],
            rpe_rows=[],
        )
        out = aggregate_per_set_rpe_inputs(
            "athlete-id",
            datetime(2026, 4, 1),
            datetime(2026, 4, 30),
            db,
        )
        assert out == {}

    def test_avg_and_max_per_session(self):
        from services.intelligence.strength_v1_inputs import (
            aggregate_per_set_rpe_inputs,
        )

        a1 = _activity("a1", datetime(2026, 4, 5, 9, 0))
        a2 = _activity("a2", datetime(2026, 4, 7, 9, 0))
        rpe_rows = [
            ("a1", 7.0),
            ("a1", 8.0),
            ("a1", 9.0),  # avg 8, max 9
            ("a2", 6.0),
            ("a2", 6.5),  # avg 6.25, max 6.5
        ]
        db = self._make_db(activities=[a1, a2], rpe_rows=rpe_rows)
        out = aggregate_per_set_rpe_inputs(
            "athlete-id",
            datetime(2026, 4, 1),
            datetime(2026, 4, 30),
            db,
        )

        assert out["ct_strength_avg_rpe_per_session"] == [
            (date(2026, 4, 5), 8.0),
            (date(2026, 4, 7), 6.25),
        ]
        assert out["ct_strength_max_rpe_per_session"] == [
            (date(2026, 4, 5), 9.0),
            (date(2026, 4, 7), 6.5),
        ]

    def test_session_with_no_rpe_is_skipped_not_imputed(self):
        """A session with no RPE entries must not appear with value 0;
        imputation would teach the engine a phantom correlation."""
        from services.intelligence.strength_v1_inputs import (
            aggregate_per_set_rpe_inputs,
        )

        a1 = _activity("a1", datetime(2026, 4, 5))
        a2 = _activity("a2", datetime(2026, 4, 6))
        rpe_rows = [("a1", 7.0)]  # a2 has no RPE rows

        db = self._make_db(activities=[a1, a2], rpe_rows=rpe_rows)
        out = aggregate_per_set_rpe_inputs(
            "athlete-id",
            datetime(2026, 4, 1),
            datetime(2026, 4, 30),
            db,
        )
        avg = out["ct_strength_avg_rpe_per_session"]
        assert len(avg) == 1
        assert avg[0][0] == date(2026, 4, 5)


# ---------------------------------------------------------------------
# Symptom aggregator
# ---------------------------------------------------------------------


def _symptom_log(severity: str, started: date, resolved=None):
    return SimpleNamespace(
        severity=severity, started_at=started, resolved_at=resolved
    )


class TestSymptomAggregator:
    def _make_db(self, rows):
        # Row shape: (severity, started_at, resolved_at)
        all_rows = [(r.severity, r.started_at, r.resolved_at) for r in rows]
        db = MagicMock()
        f = MagicMock()
        f.all.return_value = all_rows
        q = MagicMock()
        q.filter.return_value = f
        db.query.return_value = q
        return db

    def test_no_logs_returns_empty(self):
        from services.intelligence.strength_v1_inputs import (
            aggregate_symptom_inputs,
        )

        db = self._make_db([])
        out = aggregate_symptom_inputs(
            "athlete-id", datetime(2026, 4, 1), datetime(2026, 4, 7), db
        )
        assert out == {}

    def test_unresolved_log_counts_through_window(self):
        from services.intelligence.strength_v1_inputs import (
            aggregate_symptom_inputs,
        )

        # Niggle started day before window opens, never resolved.
        rows = [_symptom_log("niggle", date(2026, 3, 31))]
        db = self._make_db(rows)
        out = aggregate_symptom_inputs(
            "athlete-id", datetime(2026, 4, 1), datetime(2026, 4, 3), db
        )

        assert out["niggle_count_28d"] == [
            (date(2026, 4, 1), 1.0),
            (date(2026, 4, 2), 1.0),
            (date(2026, 4, 3), 1.0),
        ]
        # No injury entries in fixture.
        assert "injury_active_flag" not in out
        assert "ache_count_28d" not in out
        assert "pain_count_28d" not in out

    def test_active_injury_flag_lights_only_while_open(self):
        from services.intelligence.strength_v1_inputs import (
            aggregate_symptom_inputs,
        )

        rows = [
            _symptom_log("injury", date(2026, 4, 2), resolved=date(2026, 4, 5)),
        ]
        db = self._make_db(rows)
        out = aggregate_symptom_inputs(
            "athlete-id", datetime(2026, 4, 1), datetime(2026, 4, 7), db
        )

        flag_by_day = dict(out["injury_active_flag"])
        assert flag_by_day[date(2026, 4, 1)] == 0.0
        assert flag_by_day[date(2026, 4, 2)] == 1.0
        assert flag_by_day[date(2026, 4, 5)] == 1.0
        assert flag_by_day[date(2026, 4, 6)] == 0.0

        # The 28-day count of pain-tier-or-higher logs persists past
        # resolution (we want correlations to see "you had an injury
        # in the last 4 weeks").
        # injury severity is not counted under pain_count_28d; pain is
        # its own bucket. So pain_count_28d not present here.
        assert "pain_count_28d" not in out

    def test_only_known_severities_are_counted(self):
        from services.intelligence.strength_v1_inputs import (
            aggregate_symptom_inputs,
        )

        rows = [
            _symptom_log("typo", date(2026, 4, 1)),  # garbage severity
            _symptom_log("ache", date(2026, 4, 2)),
        ]
        db = self._make_db(rows)
        out = aggregate_symptom_inputs(
            "athlete-id", datetime(2026, 4, 1), datetime(2026, 4, 5), db
        )
        ache = dict(out["ache_count_28d"])
        assert ache[date(2026, 4, 5)] == 1.0
        assert "niggle_count_28d" not in out

    def test_resolved_outside_lookback_is_dropped(self):
        from services.intelligence.strength_v1_inputs import (
            aggregate_symptom_inputs,
        )

        # Resolved well before window's lookback start.
        rows = [
            _symptom_log(
                "ache",
                date(2025, 1, 1),
                resolved=date(2025, 1, 10),
            )
        ]
        db = self._make_db(rows)
        out = aggregate_symptom_inputs(
            "athlete-id", datetime(2026, 4, 1), datetime(2026, 4, 5), db
        )
        assert out == {}


# ---------------------------------------------------------------------
# Surface gate (Manual)
# ---------------------------------------------------------------------


def _finding(input_name: str, output_metric: str, sample_size: int, p_value: float):
    return SimpleNamespace(
        input_name=input_name,
        output_metric=output_metric,
        sample_size=sample_size,
        p_value=p_value,
    )


class TestStrengthSurfaceGate:
    def test_strength_finding_below_n_is_blocked(self):
        from services.operating_manual import _passes_strength_surface_gate

        f = _finding("ct_lower_body_sets", "pace_easy", sample_size=3, p_value=0.01)
        assert _passes_strength_surface_gate(f) is False

    def test_strength_finding_above_p_is_blocked(self):
        from services.operating_manual import _passes_strength_surface_gate

        f = _finding("ct_lower_body_sets", "pace_easy", sample_size=20, p_value=0.07)
        assert _passes_strength_surface_gate(f) is False

    def test_strength_finding_at_threshold_passes(self):
        from services.operating_manual import _passes_strength_surface_gate

        f = _finding("ct_heavy_sets", "vo2_estimate", sample_size=4, p_value=0.04999)
        assert _passes_strength_surface_gate(f) is True

    def test_non_strength_finding_always_passes(self):
        from services.operating_manual import _passes_strength_surface_gate

        f = _finding("garmin_hrv_5min_high", "pace_easy", sample_size=2, p_value=0.5)
        assert _passes_strength_surface_gate(f) is True

    def test_missing_sample_size_or_p_value_passes(self):
        """Older engine snapshots predate these columns. We don't
        retroactively block their findings."""
        from services.operating_manual import _passes_strength_surface_gate

        f = SimpleNamespace(
            input_name="ct_lower_body_sets",
            output_metric="pace_easy",
            sample_size=None,
            p_value=None,
        )
        assert _passes_strength_surface_gate(f) is True


# ---------------------------------------------------------------------
# E2E (real Postgres). Local: skipped. CI: runs.
# ---------------------------------------------------------------------


_E2E_REASON = (
    "Phase I e2e tests require Postgres + the strength_v1 schema. "
    "Set RUN_STRENGTH_E2E=1 to enable locally; CI runs them."
)


@pytest.mark.skipif(
    os.environ.get("RUN_STRENGTH_E2E", "0") != "1", reason=_E2E_REASON
)
class TestStrengthV1InputsE2E:
    def test_engine_pulls_phase_i_inputs_when_data_present(
        self, db_session, sample_athlete
    ):
        from services.intelligence.correlation_engine import (
            aggregate_cross_training_inputs,
        )

        end = datetime.utcnow()
        start = end - timedelta(days=60)

        out = aggregate_cross_training_inputs(
            sample_athlete.id, start, end, db_session
        )
        assert isinstance(out, dict)
