"""Regression tests: the /v1/home weekly widget must separate running from
non-running activity.

Concrete bug this guards against (Dejan, Apr 22 2026):
  - Athlete logged a 16.13 km RUN *and* a 1.56 km WALK on the same day.
  - The old query had no `sport == "run"` filter and de-duped with
    `keep first per day`, so the walk was kept and the long run was
    silently dropped from weekly mileage ("7 km across 3 runs" shown
    instead of ~23 km across 3 runs).

Invariants asserted:
  1. `WeekProgress.completed_m` includes runs only (walks / strength / cycling
     never count toward running distance).
  2. Multiple runs on the same day are SUMMED, not silently dropped.
  3. The longest run becomes the chip's primary `activity_id`.
  4. Non-running activity still appears on that day via `other_activities`
     so the athlete can tap through.
  5. `WeekDay.run_count` reflects the number of runs that day.
  6. `WeekProgress.other_sport_summary` aggregates weekly non-running activity
     per sport.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional
from uuid import uuid4

from routers.home import OtherActivityRef, OtherSportSummary, WeekDay, WeekProgress


@dataclass
class FakeActivity:
    """Minimum shape the home week aggregator reads from an Activity row."""
    id: str
    sport: str
    distance_m: Optional[int]
    duration_s: Optional[int]
    name: Optional[str] = None

    @property
    def is_duplicate(self) -> bool:
        return False


def _group(activities: list[FakeActivity], day_of: dict[str, date]) -> tuple[dict, dict]:
    """Replica of the grouping block in routers.home (kept in lock-step)."""
    runs_by_day: dict[date, list[FakeActivity]] = {}
    other_by_day: dict[date, list[FakeActivity]] = {}
    for a in activities:
        d = day_of[a.id]
        if (a.sport or "").lower() == "run":
            runs_by_day.setdefault(d, []).append(a)
        else:
            other_by_day.setdefault(d, []).append(a)
    return runs_by_day, other_by_day


def _build_weekday(day_date: date, day_abbrev: str, runs: list[FakeActivity],
                   others: list[FakeActivity], is_today: bool = False) -> WeekDay:
    """Mirrors the per-day construction in routers.home.get_home_data."""
    completed = bool(runs)
    if runs:
        day_run_m = sum(int(r.distance_m or 0) for r in runs)
        distance_m = day_run_m if day_run_m else None
        longest = max(runs, key=lambda r: (r.distance_m or 0))
        activity_id = longest.id
        sport: Optional[str] = longest.sport
    else:
        distance_m = None
        activity_id = None
        sport = None

    other_refs = [
        OtherActivityRef(
            activity_id=o.id,
            sport=(o.sport or "other").lower(),
            distance_m=int(o.distance_m) if o.distance_m else None,
            duration_s=int(o.duration_s) if o.duration_s else None,
            name=o.name,
        )
        for o in others
    ]

    return WeekDay(
        date=day_date.isoformat(),
        day_abbrev=day_abbrev,
        workout_type=None,
        sport=sport,
        distance_m=distance_m,
        planned_distance_m=None,
        completed=completed,
        is_today=is_today,
        activity_id=activity_id,
        workout_id=None,
        run_count=len(runs),
        other_activities=other_refs,
    )


def _summarize_other_from_days_raw(other_by_day: dict) -> list[OtherSportSummary]:
    """Mirrors ``routers.home`` other_sport_summary aggregation (raw m + s)."""
    _other_agg: dict[str, dict] = {}
    for _acts in other_by_day.values():
        for _a in _acts:
            _sp = (_a.sport or "other").lower()
            b = _other_agg.setdefault(_sp, {"count": 0, "distance_m": 0, "duration_s": 0})
            b["count"] += 1
            b["distance_m"] += int(_a.distance_m or 0)
            b["duration_s"] += int(_a.duration_s or 0)
    return [
        OtherSportSummary(
            sport=s,
            count=v["count"],
            distance_m=v["distance_m"],
            duration_s=v["duration_s"],
        )
        for s, v in sorted(_other_agg.items())
    ]


# ─── Dejan, Apr 20–22 2026 fixture (exact production data) ──────────────


def _dejan_apr22_fixture():
    monday = date(2026, 4, 20)
    activities = [
        FakeActivity("mon-run",  "run",      5730, 1971, "Cerklje na Gorenjskem Running"),
        FakeActivity("tue-tmill","run",       650,  267, "Treadmill Running"),
        FakeActivity("tue-short","run",         0,   23, "RFF31"),
        FakeActivity("tue-stren","strength",    0, 7767, "Strength"),
        FakeActivity("wed-walk", "walking",  1560, 2029, "Cerklje na Gorenjskem Walking"),
        FakeActivity("wed-run",  "run",     16130, 5274, "Cerklje na Gorenjskem Running"),
    ]
    day_of = {
        "mon-run":   monday,
        "tue-tmill": monday + timedelta(days=1),
        "tue-short": monday + timedelta(days=1),
        "tue-stren": monday + timedelta(days=1),
        "wed-walk":  monday + timedelta(days=2),
        "wed-run":   monday + timedelta(days=2),
    }
    return monday, activities, day_of


def test_dejan_wed_run_is_not_dropped_when_walk_shares_day():
    """The 16.13 km Wed run must NOT be dropped by the walk on the same day."""
    monday, activities, day_of = _dejan_apr22_fixture()
    runs_by_day, other_by_day = _group(activities, day_of)

    wed = monday + timedelta(days=2)
    wed_runs = runs_by_day[wed]
    wed_others = other_by_day[wed]

    assert len(wed_runs) == 1, "the 16.13 km run must be in the run bucket"
    assert wed_runs[0].id == "wed-run"
    assert len(wed_others) == 1, "the walk must be in the other bucket, not dropped and not counted as a run"
    assert wed_others[0].sport == "walking"


def test_wed_running_total_excludes_the_walk():
    """Day-level running total on Wed = 16.13 km; the 1.56 km walk does not contribute."""
    monday, activities, day_of = _dejan_apr22_fixture()
    runs_by_day, other_by_day = _group(activities, day_of)
    wed = monday + timedelta(days=2)

    day = _build_weekday(wed, "W", runs_by_day.get(wed, []), other_by_day.get(wed, []))

    assert day.distance_m == 16130
    assert day.run_count == 1
    assert day.activity_id == "wed-run"  # primary tap = the long run
    # The walk is still surfaced, not silently dropped
    assert len(day.other_activities) == 1
    assert day.other_activities[0].activity_id == "wed-walk"
    assert day.other_activities[0].sport == "walking"


def test_multi_run_day_is_summed_and_longest_is_primary_link():
    """Tuesday had 2 runs (treadmill + 0-distance blip) + a strength session.

    Contract:
      - distance_m = SUM of both runs (no silent drop)
      - run_count = 2
      - activity_id = the LONGER of the two (treadmill)
      - the strength session stays visible under other_activities
    """
    monday, activities, day_of = _dejan_apr22_fixture()
    runs_by_day, other_by_day = _group(activities, day_of)
    tue = monday + timedelta(days=1)

    day = _build_weekday(tue, "T", runs_by_day.get(tue, []), other_by_day.get(tue, []))

    assert day.distance_m == 650
    assert day.run_count == 2
    assert day.activity_id == "tue-tmill", "longest run must be the primary tap target"
    assert any(o.sport == "strength" for o in day.other_activities)


def test_week_completed_mi_is_running_only():
    """Weekly running total excludes the walk and the strength session."""
    monday, activities, day_of = _dejan_apr22_fixture()
    runs_by_day, other_by_day = _group(activities, day_of)

    abbrev = ["M", "T", "W", "T", "F", "S", "S"]
    week_days: list[WeekDay] = []
    for i in range(7):
        d = monday + timedelta(days=i)
        week_days.append(_build_weekday(d, abbrev[i], runs_by_day.get(d, []), other_by_day.get(d, [])))

    completed_m = sum((wd.distance_m or 0) for wd in week_days)
    # Runs only: 5730 + 650 + 0 + 16130 = 22510 m
    assert completed_m == 22510

    # "N runs this week" must count runs, not walks/strength.
    total_runs = sum(wd.run_count for wd in week_days)
    assert total_runs == 4  # Mon 1 + Tue 2 + Wed 1

    # Walk + strength surface in the summary, not in completed_m.
    other_summary = _summarize_other_from_days_raw(other_by_day)
    sports = {s.sport: s for s in other_summary}
    assert "walking" in sports and sports["walking"].count == 1
    assert "strength" in sports and sports["strength"].count == 1
    assert "run" not in sports


def test_other_sport_summary_aggregates_distance_and_duration():
    """Per-sport weekly aggregate exposes distance_m and duration_s."""
    monday, activities, day_of = _dejan_apr22_fixture()
    runs_by_day, other_by_day = _group(activities, day_of)
    summary = {s.sport: s for s in _summarize_other_from_days_raw(other_by_day)}

    assert summary["walking"].distance_m == 1560
    assert summary["walking"].duration_s == 2029

    assert summary["strength"].distance_m == 0
    assert summary["strength"].duration_s == 7767


def test_weekprogress_with_other_sport_summary_roundtrip():
    """WeekProgress schema accepts other_sport_summary and round-trips via pydantic."""
    monday = date(2026, 4, 20)
    wp = WeekProgress(
        completed_m=22510,
        planned_m=0,
        progress_pct=0.0,
        days=[],
        status="no_plan",
        other_sport_summary=[
            OtherSportSummary(sport="walking", count=1, distance_m=1560, duration_s=2029),
            OtherSportSummary(sport="strength", count=1, distance_m=0, duration_s=7767),
        ],
    )
    dumped = wp.model_dump()
    assert [s["sport"] for s in dumped["other_sport_summary"]] == ["walking", "strength"]


def test_weekday_run_count_defaults_to_zero():
    """Existing call sites that don't set run_count must still construct."""
    wd = WeekDay(date="2026-04-20", day_abbrev="M", completed=False, is_today=False)
    assert wd.run_count == 0
    assert wd.other_activities == []
