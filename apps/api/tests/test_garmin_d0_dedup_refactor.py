"""
D0: Deduplication Service Refactor — Regression Tests

Locks in the contract that activity_deduplication.py operates exclusively
on internal field names. Any reintroduction of provider-specific field
names will cause these tests to fail.

AC reference: PHASE2_GARMIN_INTEGRATION_AC.md §D0
"""

import inspect
from datetime import datetime, timezone, timedelta

import pytest


# ---------------------------------------------------------------------------
# Contract tests — source inspection
# ---------------------------------------------------------------------------

class TestDeduplicationSourceContract:
    """activity_deduplication.py must contain no provider-specific field names."""

    def _source(self):
        import services.activity_deduplication as mod
        return inspect.getsource(mod)

    def test_no_startTimeLocal(self):
        assert "startTimeLocal" not in self._source()

    def test_no_startTime_camel(self):
        # "startTime" as a field lookup — allow "start_time" (internal name)
        # Use a pattern that won't false-positive on comments or variable names
        assert '"startTime"' not in self._source()
        assert "'startTime'" not in self._source()

    def test_no_start_date_local(self):
        assert "start_date_local" not in self._source()

    def test_no_distanceInMeters(self):
        assert "distanceInMeters" not in self._source()

    def test_no_distance_bare(self):
        # "distance" as a standalone field lookup (not "distance_m")
        assert '"distance"' not in self._source()
        assert "'distance'" not in self._source()

    def test_no_averageHeartRate(self):
        assert "averageHeartRate" not in self._source()

    def test_no_avgHeartRate(self):
        assert "avgHeartRate" not in self._source()

    def test_uses_start_time(self):
        assert "start_time" in self._source()

    def test_uses_distance_m(self):
        assert "distance_m" in self._source()

    def test_uses_avg_hr(self):
        assert "avg_hr" in self._source()


# ---------------------------------------------------------------------------
# Runtime behavior tests
# ---------------------------------------------------------------------------

class TestMatchActivities:
    """match_activities must work correctly with internal field names."""

    def _act(self, start_offset_s=0, distance_m=10000.0, avg_hr=None):
        base = datetime(2026, 2, 21, 8, 0, 0, tzinfo=timezone.utc)
        act = {
            "start_time": base + timedelta(seconds=start_offset_s),
            "distance_m": distance_m,
        }
        if avg_hr is not None:
            act["avg_hr"] = avg_hr
        return act

    def test_identical_activities_match(self):
        from services.activity_deduplication import match_activities
        a = self._act()
        b = self._act()
        assert match_activities(a, b) is True

    def test_time_within_window_matches(self):
        from services.activity_deduplication import TIME_WINDOW_S, match_activities
        a = self._act(start_offset_s=0)
        b = self._act(start_offset_s=TIME_WINDOW_S - 1)  # 1 second inside window
        assert match_activities(a, b) is True

    def test_time_outside_window_no_match(self):
        from services.activity_deduplication import TIME_WINDOW_S, match_activities
        a = self._act(start_offset_s=0)
        b = self._act(start_offset_s=TIME_WINDOW_S + 1)  # 1 second outside window
        assert match_activities(a, b) is False

    def test_distance_within_tolerance_matches(self):
        from services.activity_deduplication import match_activities
        a = self._act(distance_m=10000.0)
        b = self._act(distance_m=10499.0)    # 4.99% difference
        assert match_activities(a, b) is True

    def test_distance_outside_tolerance_no_match(self):
        from services.activity_deduplication import match_activities
        a = self._act(distance_m=10000.0)
        # 11000 → |11000-10000|/11000 = 9.09% — well outside 5% tolerance
        b = self._act(distance_m=11000.0)
        assert match_activities(a, b) is False

    def test_hr_within_tolerance_matches(self):
        from services.activity_deduplication import match_activities
        a = self._act(avg_hr=150)
        b = self._act(avg_hr=155)    # exactly 5 bpm
        assert match_activities(a, b) is True

    def test_hr_outside_tolerance_no_match(self):
        from services.activity_deduplication import match_activities
        a = self._act(avg_hr=150)
        b = self._act(avg_hr=156)    # 6 bpm
        assert match_activities(a, b) is False

    def test_missing_hr_does_not_block_match(self):
        from services.activity_deduplication import match_activities
        a = self._act(avg_hr=150)
        b = self._act()   # no HR
        assert match_activities(a, b) is True

    def test_missing_start_time_no_match(self):
        from services.activity_deduplication import match_activities
        a = {"distance_m": 10000.0}   # no start_time
        b = self._act()
        assert match_activities(a, b) is False

    def test_missing_distance_no_match(self):
        from services.activity_deduplication import match_activities
        a = self._act()
        b = {"start_time": datetime(2026, 2, 21, 8, 0, 0, tzinfo=timezone.utc)}
        assert match_activities(a, b) is False

    def test_internal_field_names_required(self):
        """Runtime contract test: provider-specific field names do not match."""
        from services.activity_deduplication import match_activities
        base = datetime(2026, 2, 21, 8, 0, 0, tzinfo=timezone.utc)

        # Activity using internal names
        internal = {
            "start_time": base,
            "distance_m": 10000.0,
            "avg_hr": 150,
        }
        # Activity using Garmin API field names — must NOT match
        garmin_raw = {
            "startTimeLocal": "2026-02-21T08:00:00",
            "distanceInMeters": 10000.0,
            "averageHeartRate": 150,
        }
        # Since dedup reads only internal names, garmin_raw has no
        # start_time or distance_m → returns False (no match found)
        assert match_activities(internal, garmin_raw) is False


class TestDeduplicateActivities:
    """deduplicate_activities returns correct primary + unique_secondary."""

    def _act(self, start_offset_s=0, distance_m=10000.0, label=""):
        base = datetime(2026, 2, 21, 8, 0, 0, tzinfo=timezone.utc)
        return {
            "start_time": base + timedelta(seconds=start_offset_s),
            "distance_m": distance_m,
            "_label": label,
        }

    def test_primary_always_returned_intact(self):
        from services.activity_deduplication import deduplicate_activities
        primary = [self._act(label="garmin_run")]
        secondary = []
        out_primary, out_secondary = deduplicate_activities(primary, secondary)
        assert len(out_primary) == 1
        assert out_primary[0]["_label"] == "garmin_run"

    def test_duplicate_secondary_dropped(self):
        from services.activity_deduplication import deduplicate_activities
        primary = [self._act(distance_m=10000.0)]
        secondary = [self._act(distance_m=10050.0)]   # within 5%
        _, unique = deduplicate_activities(primary, secondary)
        assert len(unique) == 0

    def test_non_duplicate_secondary_kept(self):
        from services.activity_deduplication import deduplicate_activities
        primary = [self._act(distance_m=10000.0, start_offset_s=0)]
        secondary = [self._act(distance_m=5000.0, start_offset_s=0)]   # distance mismatch
        _, unique = deduplicate_activities(primary, secondary)
        assert len(unique) == 1

    def test_empty_primary_keeps_all_secondary(self):
        from services.activity_deduplication import deduplicate_activities
        secondary = [self._act(), self._act(start_offset_s=7200, distance_m=5000)]
        _, unique = deduplicate_activities([], secondary)
        assert len(unique) == 2

    def test_row_count_unchanged_on_garmin_strava_overlap(self):
        """
        Regression: when Garmin and Strava have the same run, deduplicate_activities
        must produce exactly one copy — the primary (Garmin) version.
        """
        from services.activity_deduplication import deduplicate_activities
        garmin = [self._act(distance_m=16093.0, label="garmin")]
        strava = [self._act(distance_m=16080.0, label="strava")]   # within 5%
        out_primary, out_secondary = deduplicate_activities(garmin, strava)
        total = len(out_primary) + len(out_secondary)
        assert total == 1, f"Expected 1 activity, got {total}"
        assert out_primary[0]["_label"] == "garmin"
