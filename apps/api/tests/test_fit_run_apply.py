"""
Unit tests for services/sync/fit_run_apply.

Validates the contract between FIT-parsed dicts and Activity/ActivitySplit
ORM writes:

  - Canonical fields (running dynamics, power, true moving time) overwrite
    whatever the JSON adapter previously stored.
  - "Fill if null" fields (cadence, max_cadence, total_elevation_gain) are
    only written when the column is empty.
  - Existing splits are deleted and replaced atomically by FIT laps.
  - The garmin self-eval columns are populated as a fallback only — never
    promoted to the canonical perceived-effort surface (the resolver
    handles that, not this layer).
"""

from unittest.mock import MagicMock

import pytest

from services.sync.fit_run_apply import apply_fit_run_data, _classify_lap_type


# ---------------------------------------------------------------------------
# _classify_lap_type — pure mapping
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("intensity,expected", [
    ("warmup", "warm_up"),
    ("warm_up", "warm_up"),
    ("WARMUP", "warm_up"),
    ("cooldown", "cool_down"),
    ("active", "work"),
    ("interval", "work"),
    ("rest", "rest"),
    ("recovery", "rest"),
    ("", None),
    (None, None),
    ("unknown_label", None),
])
def test_classify_lap_type(intensity, expected):
    assert _classify_lap_type({"intensity": intensity}) == expected


# ---------------------------------------------------------------------------
# apply_fit_run_data — Activity write rules
# ---------------------------------------------------------------------------


class _FakeActivity:
    """Minimal Activity stand-in (avoids touching the real ORM)."""

    def __init__(self, **initial):
        # Default every column we touch to None unless overridden.
        cols = (
            "moving_time_s", "total_descent_m", "total_elevation_gain",
            "avg_power_w", "max_power_w", "avg_stride_length_m",
            "avg_ground_contact_ms", "avg_ground_contact_balance_pct",
            "avg_vertical_oscillation_cm", "avg_vertical_ratio_pct",
            "active_kcal", "garmin_feel", "garmin_perceived_effort",
            "avg_cadence", "max_cadence",
        )
        for c in cols:
            setattr(self, c, None)
        for k, v in initial.items():
            setattr(self, k, v)
        # ID used only as a proxy for the FK on splits.
        self.id = "00000000-0000-0000-0000-000000000001"


class _FakeSession:
    """Tiny SQLAlchemy session double — collects adds/deletes for assertion."""

    def __init__(self, existing_splits=None):
        self.added = []
        self.deleted = []
        self._existing = existing_splits or []
        self._committed = False

    def query(self, _cls):
        sess = self
        existing = list(self._existing)

        class _Q:
            def filter(self, *_args, **_kwargs):
                return self

            def all(self):
                return existing

            def first(self):
                return existing[0] if existing else None

        return _Q()

    def add(self, obj):
        self.added.append(obj)

    def delete(self, obj):
        self.deleted.append(obj)

    def flush(self):
        # Once flushed, "existing" is gone (mimic real session behavior).
        self._existing = []

    def commit(self):
        self._committed = True


def test_apply_session_writes_canonical_overrides():
    activity = _FakeActivity(
        # JSON adapter populated these from the summary webhook — FIT wins.
        moving_time_s=3600,           # JSON had elapsed time as moving
        total_descent_m=None,
        avg_power_w=None,
        avg_stride_length_m=None,
    )
    parsed = {
        "session": {
            "moving_time_s": 3540,    # FIT true moving time
            "total_descent_m": 152.0,
            "avg_power_w": 285,
            "max_power_w": 420,
            "avg_stride_length_m": 1.21,
            "avg_ground_contact_ms": 248.0,
            "avg_vertical_oscillation_cm": 9.3,
            "avg_vertical_ratio_pct": 7.7,
            "total_calories": 720,
            "garmin_feel": "strong",
            "garmin_perceived_effort": 7,
        },
        "laps": [],
    }

    out = apply_fit_run_data(_FakeSession(), activity, parsed)

    assert out["session_applied"] is True
    assert out["laps_written"] == 0
    # FIT overwrites JSON-derived moving time.
    assert activity.moving_time_s == 3540
    assert activity.total_descent_m == 152.0
    assert activity.avg_power_w == 285
    assert activity.max_power_w == 420
    assert activity.avg_stride_length_m == 1.21
    assert activity.avg_ground_contact_ms == 248.0
    assert activity.avg_vertical_oscillation_cm == 9.3
    assert activity.avg_vertical_ratio_pct == 7.7
    assert activity.active_kcal == 720
    assert activity.garmin_feel == "strong"
    assert activity.garmin_perceived_effort == 7


def test_apply_session_does_not_overwrite_filled_fill_if_null_columns():
    """avg_cadence is `fill_if_null` — preserve JSON adapter's value."""
    activity = _FakeActivity(avg_cadence=170)
    parsed = {
        "session": {"avg_run_cadence_spm": 168, "max_run_cadence_spm": 190},
        "laps": [],
    }
    apply_fit_run_data(_FakeSession(), activity, parsed)
    # JSON wins because avg_cadence was already set.
    assert activity.avg_cadence == 170
    # max_cadence was unset — FIT fills.
    assert activity.max_cadence == 190


def test_apply_session_does_not_overwrite_with_none():
    """A FIT file missing a canonical field must not null-out an existing value."""
    activity = _FakeActivity(avg_power_w=300)
    parsed = {"session": {"moving_time_s": 1800}, "laps": []}  # no avg_power_w
    apply_fit_run_data(_FakeSession(), activity, parsed)
    assert activity.avg_power_w == 300  # unchanged


def test_apply_session_with_no_session_message_is_noop():
    activity = _FakeActivity(avg_power_w=300)
    out = apply_fit_run_data(_FakeSession(), activity, {"session": None, "laps": []})
    assert out == {"session_applied": False, "laps_written": 0}
    assert activity.avg_power_w == 300


# ---------------------------------------------------------------------------
# apply_fit_run_data — ActivitySplit write rules
# ---------------------------------------------------------------------------


def test_apply_laps_writes_one_split_per_lap_with_extras():
    activity = _FakeActivity()
    parsed = {
        "session": None,
        "laps": [
            {
                "lap_number": 1, "distance_m": 1609, "elapsed_time_s": 600,
                "moving_time_s": 600, "avg_hr": 142, "max_hr": 158,
                "avg_run_cadence_spm": 156, "avg_power_w": 220, "max_power_w": 280,
                "total_ascent_m": 12.0, "total_descent_m": 8.0,
                "avg_stride_length_m": 1.18, "avg_ground_contact_ms": 252.0,
                "avg_vertical_oscillation_cm": 9.6, "avg_vertical_ratio_pct": 8.1,
                # extras — go into JSONB.
                "avg_ground_contact_balance_pct": 49.7, "normalized_power_w": 235,
                "max_run_cadence_spm": 168, "avg_temperature_c": 18.0,
                "max_temperature_c": 19.0, "total_calories": 245,
                "lap_trigger": "manual", "intensity": "warmup",
            },
        ],
    }

    sess = _FakeSession(existing_splits=[])
    out = apply_fit_run_data(sess, activity, parsed)

    assert out["laps_written"] == 1
    assert len(sess.added) == 1
    s = sess.added[0]
    assert s.split_number == 1
    assert s.distance == 1609
    assert s.average_heartrate == 142
    assert s.avg_power_w == 220
    assert s.max_power_w == 280
    assert s.total_ascent_m == 12.0
    assert s.total_descent_m == 8.0
    assert s.avg_stride_length_m == 1.18
    assert s.avg_ground_contact_ms == 252.0
    assert s.avg_vertical_oscillation_cm == 9.6
    assert s.avg_vertical_ratio_pct == 8.1
    assert s.lap_type == "warm_up"
    # Extras in JSONB
    assert s.extras["avg_ground_contact_balance_pct"] == 49.7
    assert s.extras["normalized_power_w"] == 235
    assert s.extras["max_run_cadence_spm"] == 168
    assert s.extras["lap_trigger"] == "manual"
    assert s.extras["total_calories"] == 245
    # Garmin's "warmup" intensity must NOT leak into extras as a duplicate of lap_type.
    # We keep the raw value alongside the normalized lap_type for traceability.
    assert s.extras["intensity"] == "warmup"


def test_apply_laps_replaces_existing_splits():
    """If splits already exist (from JSON detail), FIT laps replace them."""
    existing = [MagicMock(name=f"existing_split_{i}") for i in range(3)]
    sess = _FakeSession(existing_splits=existing)
    activity = _FakeActivity()
    parsed = {
        "session": None,
        "laps": [
            {"lap_number": 1, "distance_m": 1000, "elapsed_time_s": 360, "intensity": "active"},
        ],
    }
    out = apply_fit_run_data(sess, activity, parsed)
    assert out["laps_written"] == 1
    # All existing rows deleted.
    assert sess.deleted == existing
    # One new row added.
    assert len(sess.added) == 1
    assert sess.added[0].lap_type == "work"


def test_apply_laps_no_laps_does_not_touch_existing_splits():
    existing = [MagicMock()]
    sess = _FakeSession(existing_splits=existing)
    activity = _FakeActivity()
    out = apply_fit_run_data(sess, activity, {"session": None, "laps": []})
    assert out["laps_written"] == 0
    assert sess.deleted == []
    assert sess.added == []


def test_apply_laps_extras_are_none_when_no_extras_present():
    """Sparse FIT laps shouldn't write an empty {} into JSONB."""
    sess = _FakeSession(existing_splits=[])
    activity = _FakeActivity()
    parsed = {
        "session": None,
        "laps": [
            {"lap_number": 1, "distance_m": 500, "elapsed_time_s": 180, "avg_hr": 140},
        ],
    }
    apply_fit_run_data(sess, activity, parsed)
    assert sess.added[0].extras is None
