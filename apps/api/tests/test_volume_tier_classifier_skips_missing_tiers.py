from __future__ import annotations


def test_volume_tier_classifier_half_marathon_high(db_session):
    """
    70 mpw is HIGH tier (60-80 range) for all distances.
    Tier boundaries are universal — mileage is mileage.
    """
    from services.plan_framework.volume_tiers import VolumeTierClassifier
    from services.plan_framework.constants import VolumeTier

    c = VolumeTierClassifier(db_session)
    tier = c.classify(current_weekly_miles=70, goal_distance="half_marathon")
    assert tier == VolumeTier.HIGH


def test_volume_tier_classifier_10k_mid(db_session):
    """
    50 mpw is MID tier (45-60 range) for all distances.
    Previously 10K had lower thresholds (HIGH at 45mpw) — corrected to
    universal boundaries in Phase 1C.
    """
    from services.plan_framework.volume_tiers import VolumeTierClassifier
    from services.plan_framework.constants import VolumeTier

    c = VolumeTierClassifier(db_session)
    tier = c.classify(current_weekly_miles=50, goal_distance="10k")
    assert tier == VolumeTier.MID


def test_volume_tier_classifier_universal_boundaries(db_session):
    """
    Tier classification is distance-independent.
    The same mileage produces the same tier for every distance.
    """
    from services.plan_framework.volume_tiers import VolumeTierClassifier
    from services.plan_framework.constants import VolumeTier

    c = VolumeTierClassifier(db_session)
    for distance in ["marathon", "half_marathon", "10k", "5k"]:
        assert c.classify(current_weekly_miles=25, goal_distance=distance) == VolumeTier.BUILDER
        assert c.classify(current_weekly_miles=40, goal_distance=distance) == VolumeTier.LOW
        assert c.classify(current_weekly_miles=50, goal_distance=distance) == VolumeTier.MID
        assert c.classify(current_weekly_miles=70, goal_distance=distance) == VolumeTier.HIGH
        assert c.classify(current_weekly_miles=90, goal_distance=distance) == VolumeTier.ELITE
