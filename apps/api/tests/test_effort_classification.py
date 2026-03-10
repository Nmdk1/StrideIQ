"""
Tests for N=1 Effort Classification

Covers all three tiers, eligibility gates, RPE disagreement logging,
bulk classification, and threshold computation/caching.
"""

import uuid
from datetime import datetime, date, timedelta
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from services.effort_classification import (
    classify_effort,
    classify_effort_bulk,
    get_effort_thresholds,
    log_rpe_disagreement,
    invalidate_effort_cache,
    compute_activity_gap,
    _compute_thresholds,
    _classify_tier1,
    _classify_tier2,
    _classify_tier3,
    _classify_from_tpp,
    _combine_tpp_hr,
    _percentile,
    _rpe_to_tier,
    TPP_HARD,
    TPP_MODERATE,
    TIER_1_HARD_PERCENTILE,
    TIER_1_EASY_PERCENTILE,
    TIER_2_MIN_ACTIVITIES,
    TIER_2_MIN_HARD_SESSIONS,
)

ATHLETE_ID = str(uuid.uuid4())


def _mock_activity(avg_hr=150, max_hr=170, workout_type=None, start_time=None):
    act = MagicMock()
    act.id = uuid.uuid4()
    act.avg_hr = avg_hr
    act.max_hr = max_hr
    act.workout_type = workout_type
    act.start_time = start_time or datetime.utcnow()
    act.athlete_id = ATHLETE_ID
    return act


def _make_thresholds(
    tier="percentile", p80=160, p40=135, peak=185, resting=50,
    count=50, hard=12, threshold_pace=None, five_k_pace=None,
    hr_tier=None,
):
    return {
        "p80_hr": p80,
        "p40_hr": p40,
        "tier": tier,
        "hr_tier": hr_tier or tier,
        "threshold_pace": threshold_pace,
        "five_k_pace": five_k_pace,
        "observed_peak_hr": peak,
        "resting_hr": resting,
        "activity_count": count,
        "hard_count": hard,
    }


# ═══════════════════════════════════════════════════════════════════
# Test 1: Tier 1 — hard at P85
# ═══════════════════════════════════════════════════════════════════
def test_tier1_hard():
    t = _make_thresholds(p80=160, p40=135)
    assert _classify_tier1(165, t) == "hard"


# ═══════════════════════════════════════════════════════════════════
# Test 2: Tier 1 — moderate at P60
# ═══════════════════════════════════════════════════════════════════
def test_tier1_moderate():
    t = _make_thresholds(p80=160, p40=135)
    assert _classify_tier1(150, t) == "moderate"


# ═══════════════════════════════════════════════════════════════════
# Test 3: Tier 1 — easy at P20
# ═══════════════════════════════════════════════════════════════════
def test_tier1_easy():
    t = _make_thresholds(p80=160, p40=135)
    assert _classify_tier1(120, t) == "easy"


# ═══════════════════════════════════════════════════════════════════
# Test 4: Works with zero athlete.max_hr set
# ═══════════════════════════════════════════════════════════════════
def test_works_without_max_hr():
    thresholds = _make_thresholds(tier="percentile", p80=160, p40=135)
    with patch("services.effort_classification.get_effort_thresholds", return_value=thresholds):
        act = _mock_activity(avg_hr=170)
        result = classify_effort(act, ATHLETE_ID, MagicMock())

    assert result == "hard"


# ═══════════════════════════════════════════════════════════════════
# Test 5: Tier 2 NOT activated with < 20 activities
# ═══════════════════════════════════════════════════════════════════
def test_tier2_not_activated_few_activities():
    from services.effort_classification import _select_tier
    tier = _select_tier(activity_count=15, hard_count=5, observed_peak_hr=190, resting_hr=50)
    assert tier == "percentile"


# ═══════════════════════════════════════════════════════════════════
# Test 6: Tier 2 NOT activated without 3 hard sessions
# ═══════════════════════════════════════════════════════════════════
def test_tier2_not_activated_few_hard():
    from services.effort_classification import _select_tier
    tier = _select_tier(activity_count=25, hard_count=2, observed_peak_hr=190, resting_hr=50)
    assert tier == "percentile"


# ═══════════════════════════════════════════════════════════════════
# Test 7: Tier 2 activated and correct classification
# ═══════════════════════════════════════════════════════════════════
def test_tier2_activated_correct():
    t = _make_thresholds(tier="hrr", peak=190, resting=50)
    # HRR = (170 - 50) / (190 - 50) = 120/140 = 0.857 → hard
    assert _classify_tier2(170, t) == "hard"
    # HRR = (130 - 50) / (190 - 50) = 80/140 = 0.571 → moderate
    assert _classify_tier2(130, t) == "moderate"
    # HRR = (100 - 50) / (190 - 50) = 50/140 = 0.357 → easy
    assert _classify_tier2(100, t) == "easy"


# ═══════════════════════════════════════════════════════════════════
# Test 8: Tier 3 — workout_type "race" → hard
# ═══════════════════════════════════════════════════════════════════
def test_tier3_race_hard():
    act = _mock_activity(avg_hr=None, workout_type="race")
    db = MagicMock()
    assert _classify_tier3(act, ATHLETE_ID, db) == "hard"


# ═══════════════════════════════════════════════════════════════════
# Test 9: Tier 3 — RPE >= 7 → hard
# ═══════════════════════════════════════════════════════════════════
def test_tier3_rpe_hard():
    act = _mock_activity(avg_hr=None, workout_type="general")
    db = MagicMock()
    checkin = MagicMock()
    checkin.rpe_1_10 = 8
    db.query.return_value.filter.return_value.first.return_value = checkin
    assert _classify_tier3(act, ATHLETE_ID, db) == "hard"


# ═══════════════════════════════════════════════════════════════════
# Test 10: Tier 3 — ambiguous → moderate
# ═══════════════════════════════════════════════════════════════════
def test_tier3_moderate():
    act = _mock_activity(avg_hr=None, workout_type="general")
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    assert _classify_tier3(act, ATHLETE_ID, db) == "moderate"


# ═══════════════════════════════════════════════════════════════════
# Test 11: RPE disagreement logged when gap > 1 tier
# ═══════════════════════════════════════════════════════════════════
def test_rpe_disagreement_logged():
    db = MagicMock()
    with patch("services.effort_classification.logger") as mock_logger:
        log_rpe_disagreement(ATHLETE_ID, uuid.uuid4(), "hard", 3, db)
    mock_logger.info.assert_called_once()
    call_args = mock_logger.info.call_args[0][0]
    assert "rpe_disagreement" in call_args


# ═══════════════════════════════════════════════════════════════════
# Test 12: RPE disagreement NOT logged when gap <= 1
# ═══════════════════════════════════════════════════════════════════
def test_rpe_disagreement_not_logged(caplog):
    import logging
    with caplog.at_level(logging.INFO, logger="services.effort_classification"):
        db = MagicMock()
        log_rpe_disagreement(ATHLETE_ID, uuid.uuid4(), "hard", 7, db)
    assert "rpe_disagreement" not in caplog.text


# ═══════════════════════════════════════════════════════════════════
# Test 13: classify_effort_bulk returns dict mapping IDs
# ═══════════════════════════════════════════════════════════════════
def test_classify_effort_bulk():
    activities = [_mock_activity(avg_hr=hr) for hr in [165, 150, 120]]
    t = _make_thresholds(p80=160, p40=135)
    with patch("services.effort_classification.get_effort_thresholds", return_value=t):
        result = classify_effort_bulk(activities, ATHLETE_ID, MagicMock())
    assert len(result) == 3
    ids = [a.id for a in activities]
    assert result[ids[0]] == "hard"
    assert result[ids[1]] == "moderate"
    assert result[ids[2]] == "easy"


# ═══════════════════════════════════════════════════════════════════
# Test 14: get_effort_thresholds returns correct structure
# ═══════════════════════════════════════════════════════════════════
def test_get_effort_thresholds_structure():
    with patch("services.effort_classification._compute_thresholds") as mock_ct:
        mock_ct.return_value = _make_thresholds()
        with patch("core.cache.get_redis_client", return_value=None):
            result = get_effort_thresholds(ATHLETE_ID, MagicMock())

    assert "p80_hr" in result
    assert "p40_hr" in result
    assert "tier" in result
    assert "observed_peak_hr" in result
    assert "resting_hr" in result
    assert "activity_count" in result
    assert "hard_count" in result


# ═══════════════════════════════════════════════════════════════════
# Test 15: cached result matches fresh computation
# ═══════════════════════════════════════════════════════════════════
def test_cached_matches_fresh():
    import json
    expected = _make_thresholds()
    mock_redis = MagicMock()
    mock_redis.get.return_value = json.dumps(expected)

    with patch("core.cache.get_redis_client", return_value=mock_redis):
        result = get_effort_thresholds(ATHLETE_ID, MagicMock())

    assert result == expected


# ═══════════════════════════════════════════════════════════════════
# Test: _percentile
# ═══════════════════════════════════════════════════════════════════
def test_percentile_computation():
    vals = list(range(100, 201))  # 100..200
    p80 = _percentile(vals, 80)
    assert abs(p80 - 180) < 1


# ═══════════════════════════════════════════════════════════════════
# Test: _rpe_to_tier
# ═══════════════════════════════════════════════════════════════════
def test_rpe_to_tier():
    assert _rpe_to_tier(9) == "hard"
    assert _rpe_to_tier(7) == "hard"
    assert _rpe_to_tier(5) == "moderate"
    assert _rpe_to_tier(4) == "easy"
    assert _rpe_to_tier(2) == "easy"


# ═══════════════════════════════════════════════════════════════════
# Tier 0 (TPP) Tests
# ═══════════════════════════════════════════════════════════════════


def _mock_split(distance, gap_sec_per_mile):
    s = MagicMock()
    s.distance = distance
    s.gap_seconds_per_mile = gap_sec_per_mile
    return s


# Test T0-1: compute_activity_gap correct distance-weighted average
def test_compute_activity_gap_weighted():
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = [
        (1000, 480.0),  # 8:00/mi GAP
        (2000, 540.0),  # 9:00/mi GAP
    ]
    result = compute_activity_gap(uuid.uuid4(), db)
    # Weighted: (1000*480 + 2000*540) / 3000 = 1560000/3000 = 520.0
    assert result == pytest.approx(520.0)


# Test T0-2: compute_activity_gap returns None when no splits
def test_compute_activity_gap_no_splits():
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = []
    assert compute_activity_gap(uuid.uuid4(), db) is None


# Test T0-3: Tier 0 activates when athlete has RPI and activity has GAP
def test_tier0_activates():
    t = _make_thresholds(tier="tpp", threshold_pace=450, hr_tier="percentile")
    with patch("services.effort_classification.get_effort_thresholds", return_value=t):
        with patch("services.effort_classification.compute_activity_gap", return_value=600.0):
            act = _mock_activity(avg_hr=140)
            result = classify_effort(act, ATHLETE_ID, MagicMock())
    # TPP = 450/600 = 0.75 → easy (no HR upgrade: 140 < p80=160)
    assert result == "easy"


# Test T0-4: Falls through to Tier 1 when RPI is null
def test_tier0_fallthrough_no_rpi():
    t = _make_thresholds(tier="percentile", threshold_pace=None)
    with patch("services.effort_classification.get_effort_thresholds", return_value=t):
        act = _mock_activity(avg_hr=165)
        result = classify_effort(act, ATHLETE_ID, MagicMock())
    assert result == "hard"


# Test T0-5: Falls through to Tier 1 when no split GAP data
def test_tier0_fallthrough_no_gap():
    t = _make_thresholds(tier="tpp", threshold_pace=450, hr_tier="percentile")
    with patch("services.effort_classification.get_effort_thresholds", return_value=t):
        with patch("services.effort_classification.compute_activity_gap", return_value=None):
            act = _mock_activity(avg_hr=120)
            result = classify_effort(act, ATHLETE_ID, MagicMock())
    assert result == "easy"


# Test T0-6: TPP 0.75 → easy
def test_tpp_easy():
    assert _classify_from_tpp(0.75) == "easy"
    assert _classify_from_tpp(0.50) == "easy"
    assert _classify_from_tpp(0.77) == "easy"


# Test T0-7: TPP 0.88 → moderate
def test_tpp_moderate():
    assert _classify_from_tpp(0.88) == "moderate"
    assert _classify_from_tpp(0.78) == "moderate"
    assert _classify_from_tpp(0.91) == "moderate"


# Test T0-8: TPP 0.97 → hard
def test_tpp_hard():
    assert _classify_from_tpp(0.97) == "hard"
    assert _classify_from_tpp(0.92) == "hard"
    assert _classify_from_tpp(1.05) == "hard"


# Test T0-9: Combined — moderate TPP + hard HR → hard (environmental stress)
def test_combine_moderate_tpp_hard_hr():
    assert _combine_tpp_hr("moderate", "hard") == "hard"


# Test T0-10: Combined — hard TPP + easy HR → hard (no downgrade)
def test_combine_hard_tpp_easy_hr():
    assert _combine_tpp_hr("hard", "easy") == "hard"


# Test T0-11: Combined — easy TPP + hard HR → moderate (anomaly)
def test_combine_easy_tpp_hard_hr():
    assert _combine_tpp_hr("easy", "hard") == "moderate"


# Test T0-11b: Combined — easy TPP + moderate HR → easy (minor elevation)
def test_combine_easy_tpp_moderate_hr():
    assert _combine_tpp_hr("easy", "moderate") == "easy"


# Test T0-12: Disagreement logged when TPP and HR differ
def test_tpp_hr_disagreement_logged():
    t = _make_thresholds(tier="tpp", threshold_pace=450, hr_tier="percentile")
    with patch("services.effort_classification.get_effort_thresholds", return_value=t):
        with patch("services.effort_classification.compute_activity_gap", return_value=510.0):
            with patch("services.effort_classification.logger") as mock_logger:
                # TPP = 450/510 = 0.88 → moderate, HR 165 > p80=160 → hard
                act = _mock_activity(avg_hr=165)
                result = classify_effort(act, ATHLETE_ID, MagicMock())
    assert result == "hard"
    mock_logger.info.assert_called_once()
    assert "tpp_hr_disagreement" in mock_logger.info.call_args[0][0]


# Test T0-13: Disagreement NOT logged when TPP and HR agree
def test_tpp_hr_agreement_not_logged():
    t = _make_thresholds(tier="tpp", threshold_pace=450, hr_tier="percentile")
    with patch("services.effort_classification.get_effort_thresholds", return_value=t):
        with patch("services.effort_classification.compute_activity_gap", return_value=600.0):
            with patch("services.effort_classification.logger") as mock_logger:
                # TPP = 450/600 = 0.75 → easy, HR 120 < p40=135 → easy
                act = _mock_activity(avg_hr=120)
                classify_effort(act, ATHLETE_ID, MagicMock())
    mock_logger.info.assert_not_called()


# Test T0-14: Formula verification — exact spec examples
def test_tpp_formula_verification():
    # 450/600 = 0.75 → easy
    assert _classify_from_tpp(450 / 600) == "easy"
    # 450/465 = 0.968 → hard
    assert _classify_from_tpp(450 / 465) == "hard"
    # 450/510 = 0.882 → moderate
    assert _classify_from_tpp(450 / 510) == "moderate"
