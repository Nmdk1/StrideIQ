from datetime import date

from services.mileage_aggregation import (
    collapse_probable_provider_duplicates,
    compute_peak_and_current_weekly_miles,
    compute_weekly_mileage,
)
from tests.fixtures.golden_athlete_fixture import build_golden_activities


def test_hard_boundary_same_day_similar_runs_over_10min_are_not_collapsed():
    activities = build_golden_activities()
    # The AM/PM pair in golden fixture are >10 minutes apart.
    a = activities[2]
    b = activities[3]

    out, dropped = collapse_probable_provider_duplicates([a, b])
    assert dropped == 0
    assert len(out) == 2


def test_provider_order_invariance_for_peak_and_current_weekly():
    activities = build_golden_activities()
    one, _ = collapse_probable_provider_duplicates(activities)
    two, _ = collapse_probable_provider_duplicates(list(reversed(activities)))

    p1, c1, _ = compute_peak_and_current_weekly_miles(one, now=date(2026, 1, 31))
    p2, c2, _ = compute_peak_and_current_weekly_miles(two, now=date(2026, 1, 31))

    assert round(p1, 4) == round(p2, 4)
    assert round(c1, 4) == round(c2, 4)
    assert compute_weekly_mileage(one) == compute_weekly_mileage(two)

