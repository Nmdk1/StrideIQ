from __future__ import annotations


def test_volume_tier_classifier_skips_missing_elite_for_half_marathon(db_session):
    """
    Regression guard: half_marathon thresholds do not define ELITE tier.
    Classifier must not "match all" by falling back to default min/max.
    """
    from services.plan_framework.volume_tiers import VolumeTierClassifier
    from services.plan_framework.constants import VolumeTier

    c = VolumeTierClassifier(db_session)
    tier = c.classify(current_weekly_miles=70, goal_distance="half_marathon")
    assert tier == VolumeTier.HIGH


def test_volume_tier_classifier_skips_missing_elite_for_10k(db_session):
    from services.plan_framework.volume_tiers import VolumeTierClassifier
    from services.plan_framework.constants import VolumeTier

    c = VolumeTierClassifier(db_session)
    tier = c.classify(current_weekly_miles=50, goal_distance="10k")
    assert tier == VolumeTier.HIGH

