"""
Strength Taxonomy, Epley 1RM, and Session Classifier Tests

Commit 1 of Cross-Training Session Detail Capture (Phase A).
Tests the pure-function taxonomy, 1RM estimation, and session classification
from services/strength_taxonomy.py.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.strength_taxonomy import (
    MOVEMENT_PATTERN_MAP,
    UNILATERAL_EXERCISES,
    DEFAULT_MOVEMENT_PATTERN,
    lookup_movement_pattern,
    is_unilateral,
    estimate_1rm,
    classify_session_type,
)


# ---------------------------------------------------------------------------
# Taxonomy Lookup Tests
# ---------------------------------------------------------------------------

class TestMovementPatternLookup:
    def test_deadlift_maps_to_hip_hinge(self):
        assert lookup_movement_pattern("BARBELL_DEADLIFT") == ("hip_hinge", "posterior_chain")

    def test_squat_maps_to_squat(self):
        assert lookup_movement_pattern("BACK_SQUAT") == ("squat", "quadriceps")

    def test_lunge_maps_to_lunge(self):
        assert lookup_movement_pattern("WALKING_LUNGE") == ("lunge", "quadriceps")

    def test_push_maps_correctly(self):
        assert lookup_movement_pattern("BENCH_PRESS") == ("push", "chest")
        assert lookup_movement_pattern("OVERHEAD_PRESS") == ("push", "shoulders")

    def test_pull_maps_correctly(self):
        assert lookup_movement_pattern("PULL_UP") == ("pull", "lats")
        assert lookup_movement_pattern("BARBELL_ROW") == ("pull", "upper_back")

    def test_core_maps_correctly(self):
        assert lookup_movement_pattern("PLANK") == ("core", "core_anterior")
        assert lookup_movement_pattern("RUSSIAN_TWIST") == ("core", "core_rotational")
        assert lookup_movement_pattern("SIDE_PLANK") == ("core", "core_lateral")

    def test_plyometric_maps_correctly(self):
        assert lookup_movement_pattern("BOX_JUMP") == ("plyometric", "lower_body_explosive")

    def test_carry_maps_correctly(self):
        assert lookup_movement_pattern("FARMERS_WALK") == ("carry", "full_body")

    def test_calf_maps_correctly(self):
        assert lookup_movement_pattern("CALF_RAISE") == ("calf", "calves")

    def test_isolation_maps_correctly(self):
        assert lookup_movement_pattern("LEG_CURL") == ("isolation", "hamstrings")

    def test_unknown_exercise_returns_default(self):
        assert lookup_movement_pattern("UNDERWATER_BASKET_WEAVE") == DEFAULT_MOVEMENT_PATTERN

    def test_empty_string_returns_default(self):
        assert lookup_movement_pattern("") == DEFAULT_MOVEMENT_PATTERN

    def test_all_mapped_exercises_return_two_tuple(self):
        for name, (pattern, group) in MOVEMENT_PATTERN_MAP.items():
            assert isinstance(pattern, str), f"{name} pattern is not a string"
            assert group is None or isinstance(group, str), f"{name} group is not str/None"

    def test_all_taxonomy_categories_covered(self):
        patterns = {v[0] for v in MOVEMENT_PATTERN_MAP.values()}
        expected = {"hip_hinge", "squat", "lunge", "push", "pull", "core",
                    "plyometric", "carry", "calf", "isolation"}
        assert expected == patterns


class TestUnilateralClassification:
    def test_split_squat_is_unilateral(self):
        assert is_unilateral("SPLIT_SQUAT") is True

    def test_bulgarian_split_squat_is_unilateral(self):
        assert is_unilateral("BULGARIAN_SPLIT_SQUAT") is True

    def test_single_leg_deadlift_is_unilateral(self):
        assert is_unilateral("SINGLE_LEG_DEADLIFT") is True

    def test_barbell_deadlift_is_bilateral(self):
        assert is_unilateral("BARBELL_DEADLIFT") is False

    def test_back_squat_is_bilateral(self):
        assert is_unilateral("BACK_SQUAT") is False

    def test_unknown_exercise_is_bilateral(self):
        assert is_unilateral("MYSTERY_LIFT") is False


# ---------------------------------------------------------------------------
# Epley 1RM Estimation Tests
# ---------------------------------------------------------------------------

class TestEstimate1RM:
    def test_single_rep_returns_weight(self):
        assert estimate_1rm(100.0, 1) == 100.0

    def test_five_reps(self):
        # 100 * (1 + 5/30) = 100 * 1.1667 = 116.7
        assert estimate_1rm(100.0, 5) == 116.7

    def test_ten_reps(self):
        # 100 * (1 + 10/30) = 100 * 1.3333 = 133.3
        assert estimate_1rm(100.0, 10) == 133.3

    def test_eight_reps_founder_light_day(self):
        # 102.1 kg (225 lbs) × (1 + 8/30) = 102.1 × 1.2667 ≈ 129.3
        result = estimate_1rm(102.1, 8)
        assert result is not None
        assert 129.0 <= result <= 130.0

    def test_above_ten_reps_returns_none(self):
        assert estimate_1rm(100.0, 11) is None
        assert estimate_1rm(100.0, 15) is None
        assert estimate_1rm(100.0, 20) is None

    def test_zero_reps_returns_none(self):
        assert estimate_1rm(100.0, 0) is None

    def test_negative_reps_returns_none(self):
        assert estimate_1rm(100.0, -1) is None

    def test_none_reps_returns_none(self):
        assert estimate_1rm(100.0, None) is None

    def test_zero_weight_returns_none(self):
        assert estimate_1rm(0.0, 5) is None

    def test_negative_weight_returns_none(self):
        assert estimate_1rm(-10.0, 5) is None

    def test_none_weight_returns_none(self):
        assert estimate_1rm(None, 5) is None

    def test_both_none_returns_none(self):
        assert estimate_1rm(None, None) is None

    def test_result_is_rounded_to_one_decimal(self):
        result = estimate_1rm(77.7, 7)
        assert result is not None
        assert result == round(result, 1)


# ---------------------------------------------------------------------------
# Session Intensity Classification Tests
# ---------------------------------------------------------------------------

def _make_set(
    reps=5,
    weight_kg=100.0,
    movement_pattern="hip_hinge",
    exercise_category="DEADLIFT",
    set_type="active",
    estimated_1rm_kg=None,
):
    return {
        "reps": reps,
        "weight_kg": weight_kg,
        "movement_pattern": movement_pattern,
        "exercise_category": exercise_category,
        "set_type": set_type,
        "estimated_1rm_kg": estimated_1rm_kg,
    }


class TestClassifySessionType:
    def test_maximal_with_1rm(self):
        # 5 reps at 90% 1RM → maximal
        peak = {"DEADLIFT": 200.0}
        sets = [_make_set(reps=3, weight_kg=180.0)] * 5
        assert classify_session_type(sets, peak) == "maximal"

    def test_strength_endurance_with_1rm(self):
        # 8 reps at 80% 1RM → strength_endurance
        peak = {"DEADLIFT": 150.0}
        sets = [_make_set(reps=8, weight_kg=120.0)] * 4
        assert classify_session_type(sets, peak) == "strength_endurance"

    def test_hypertrophy_with_1rm(self):
        # 10 reps at 60% 1RM → hypertrophy
        peak = {"DEADLIFT": 200.0}
        sets = [_make_set(reps=10, weight_kg=120.0)] * 4
        assert classify_session_type(sets, peak) == "hypertrophy"

    def test_endurance_high_reps(self):
        # 15 reps → endurance regardless of 1RM
        sets = [_make_set(reps=15, weight_kg=50.0)] * 4
        assert classify_session_type(sets, {}) == "endurance"

    def test_power_plyometric_plus_heavy(self):
        # Box jumps + heavy deadlifts → power
        peak = {"DEADLIFT": 200.0}
        sets = [
            _make_set(reps=3, weight_kg=180.0),
            _make_set(reps=3, weight_kg=180.0),
            _make_set(reps=5, weight_kg=0.0, movement_pattern="plyometric",
                      exercise_category="BOX_JUMP"),
            _make_set(reps=5, weight_kg=0.0, movement_pattern="plyometric",
                      exercise_category="BOX_JUMP"),
        ]
        assert classify_session_type(sets, peak) == "power"

    def test_mixed_when_no_clear_category(self):
        # 8 reps, no 1RM data, some mixed exercises → mixed
        sets = [
            _make_set(reps=8, weight_kg=60.0),
            _make_set(reps=5, weight_kg=100.0, exercise_category="BENCH_PRESS",
                      movement_pattern="push"),
            _make_set(reps=12, weight_kg=30.0, exercise_category="BICEP_CURL",
                      movement_pattern="isolation"),
        ]
        assert classify_session_type(sets, {}) == "mixed"

    def test_maximal_fallback_no_1rm(self):
        # 3 reps, no 1RM history → fallback to rep-count maximal
        sets = [_make_set(reps=3, weight_kg=100.0)] * 5
        assert classify_session_type(sets, {}) == "maximal"

    def test_endurance_fallback_no_1rm(self):
        # 15 reps, no 1RM history → endurance
        sets = [_make_set(reps=15, weight_kg=30.0)] * 4
        assert classify_session_type(sets, {}) == "endurance"

    def test_empty_sets_returns_mixed(self):
        assert classify_session_type([], {}) == "mixed"

    def test_rest_sets_excluded(self):
        # Only rest sets → mixed (no active sets)
        sets = [_make_set(set_type="rest")] * 3
        assert classify_session_type(sets, {}) == "mixed"

    def test_sets_with_no_reps_returns_mixed(self):
        # Timed holds — reps=None
        sets = [_make_set(reps=None, weight_kg=0.0)] * 3
        assert classify_session_type(sets, {}) == "mixed"

    def test_founder_light_day(self):
        # 225 lbs (102.1 kg) × 8, est 1RM ~344 lbs (156.0 kg)
        # Relative intensity: 102.1 / 156.0 = 0.654 → not strength_endurance
        # Wait — founder said est 1RM was derived from their heavy day data.
        # We need to use the peak 1RM from heavy day: 295×5 → est 1RM ≈ 156.0 kg
        # 102.1 / 156.0 = 0.654 → below 0.75 threshold
        # With 8 reps and <0.75 → hypertrophy
        peak = {"DEADLIFT": 156.0}
        sets = [_make_set(reps=8, weight_kg=102.1)] * 4
        assert classify_session_type(sets, peak) == "hypertrophy"

    def test_founder_heavy_day(self):
        # 295 lbs (133.8 kg) × 5, peak 1RM from same exercise ~156 kg
        # 133.8 / 156.0 = 0.858 → ≥0.85, reps ≤5 → maximal
        peak = {"DEADLIFT": 156.0}
        sets = [_make_set(reps=5, weight_kg=133.8)] * 3
        assert classify_session_type(sets, peak) == "maximal"
