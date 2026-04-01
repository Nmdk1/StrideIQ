"""
Strength Parser Tests

Commit 2 of Cross-Training Session Detail Capture (Phase A).
Tests parse_exercise_sets, write_exercise_sets, classify_and_store_session_type,
and the full process_strength_activity pipeline.
"""
import sys
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.strength_parser import parse_exercise_sets


# ---------------------------------------------------------------------------
# Fixtures: Garmin-like payloads
# ---------------------------------------------------------------------------

DEADLIFT_SESSION = {
    "exerciseSets": [
        {
            "setType": "ACTIVE",
            "exerciseCategory": "DEADLIFT",
            "exerciseName": "BARBELL_DEADLIFT",
            "repetitionCount": 5,
            "weight": 133.8,
            "duration": 45.0,
            "setOrder": 1,
        },
        {
            "setType": "REST",
            "exerciseCategory": "DEADLIFT",
            "exerciseName": "BARBELL_DEADLIFT",
            "repetitionCount": 0,
            "weight": 0.0,
            "duration": 120.0,
            "setOrder": 2,
        },
        {
            "setType": "ACTIVE",
            "exerciseCategory": "DEADLIFT",
            "exerciseName": "BARBELL_DEADLIFT",
            "repetitionCount": 5,
            "weight": 133.8,
            "duration": 48.0,
            "setOrder": 3,
        },
        {
            "setType": "ACTIVE",
            "exerciseCategory": "SQUAT",
            "exerciseName": "BACK_SQUAT",
            "repetitionCount": 8,
            "weight": 102.1,
            "duration": 55.0,
            "setOrder": 4,
        },
    ],
}

UNKNOWN_EXERCISE_SESSION = {
    "exerciseSets": [
        {
            "setType": "ACTIVE",
            "exerciseCategory": "WEIRD_MACHINE",
            "exerciseName": "UNDERWATER_BASKET_CURL",
            "repetitionCount": 10,
            "weight": 50.0,
            "duration": 30.0,
        },
    ],
}

EMPTY_SESSION = {"exerciseSets": []}

BODYWEIGHT_SESSION = {
    "exerciseSets": [
        {
            "setType": "ACTIVE",
            "exerciseCategory": "PUSH_UP",
            "exerciseName": "PUSH_UP",
            "repetitionCount": 20,
            "weight": 0.0,
            "duration": 40.0,
        },
        {
            "setType": "ACTIVE",
            "exerciseCategory": "PLANK",
            "exerciseName": "PLANK",
            "repetitionCount": None,
            "weight": 0.0,
            "duration": 60.0,
        },
    ],
}


# ---------------------------------------------------------------------------
# Parser Tests
# ---------------------------------------------------------------------------

class TestParseExerciseSets:
    def test_parses_deadlift_session(self):
        activity_id = str(uuid4())
        athlete_id = str(uuid4())
        result = parse_exercise_sets(DEADLIFT_SESSION, activity_id, athlete_id)

        assert len(result) == 4
        assert result[0]["exercise_name_raw"] == "BARBELL_DEADLIFT"
        assert result[0]["exercise_category"] == "DEADLIFT"
        assert result[0]["movement_pattern"] == "hip_hinge"
        assert result[0]["muscle_group"] == "posterior_chain"
        assert result[0]["set_type"] == "active"
        assert result[0]["reps"] == 5
        assert result[0]["weight_kg"] == 133.8
        assert result[0]["set_order"] == 1

    def test_rest_sets_classified(self):
        result = parse_exercise_sets(DEADLIFT_SESSION, str(uuid4()), str(uuid4()))
        rest_sets = [s for s in result if s["set_type"] == "rest"]
        assert len(rest_sets) == 1
        assert rest_sets[0]["set_order"] == 2

    def test_estimated_1rm_computed(self):
        result = parse_exercise_sets(DEADLIFT_SESSION, str(uuid4()), str(uuid4()))
        dl_set = result[0]
        # 133.8 * (1 + 5/30) = 133.8 * 1.1667 = 156.1
        assert dl_set["estimated_1rm_kg"] is not None
        assert 155.5 <= dl_set["estimated_1rm_kg"] <= 156.5

    def test_squat_classified_correctly(self):
        result = parse_exercise_sets(DEADLIFT_SESSION, str(uuid4()), str(uuid4()))
        squat_set = result[3]
        assert squat_set["exercise_name_raw"] == "BACK_SQUAT"
        assert squat_set["movement_pattern"] == "squat"
        assert squat_set["muscle_group"] == "quadriceps"

    def test_unknown_exercise_falls_back(self):
        result = parse_exercise_sets(UNKNOWN_EXERCISE_SESSION, str(uuid4()), str(uuid4()))
        assert len(result) == 1
        assert result[0]["movement_pattern"] == "compound_other"
        assert result[0]["muscle_group"] is None

    def test_empty_session_returns_empty(self):
        result = parse_exercise_sets(EMPTY_SESSION, str(uuid4()), str(uuid4()))
        assert result == []

    def test_bodyweight_exercise_weight_is_none(self):
        result = parse_exercise_sets(BODYWEIGHT_SESSION, str(uuid4()), str(uuid4()))
        pushup = result[0]
        assert pushup["weight_kg"] is None
        assert pushup["estimated_1rm_kg"] is None
        assert pushup["reps"] == 20

    def test_plank_has_no_reps(self):
        result = parse_exercise_sets(BODYWEIGHT_SESSION, str(uuid4()), str(uuid4()))
        plank = result[1]
        assert plank["reps"] is None
        assert plank["duration_s"] == 60.0
        assert plank["movement_pattern"] == "core"

    def test_unilateral_detected(self):
        session = {
            "exerciseSets": [
                {
                    "setType": "ACTIVE",
                    "exerciseCategory": "LUNGE",
                    "exerciseName": "WALKING_LUNGE",
                    "repetitionCount": 12,
                    "weight": 40.0,
                },
            ],
        }
        result = parse_exercise_sets(session, str(uuid4()), str(uuid4()))
        assert result[0]["is_unilateral"] is True

    def test_bilateral_detected(self):
        result = parse_exercise_sets(DEADLIFT_SESSION, str(uuid4()), str(uuid4()))
        assert result[0]["is_unilateral"] is False

    def test_activity_and_athlete_ids_propagated(self):
        aid = str(uuid4())
        atid = str(uuid4())
        result = parse_exercise_sets(DEADLIFT_SESSION, aid, atid)
        for s in result:
            assert s["activity_id"] == aid
            assert s["athlete_id"] == atid

    def test_category_fallback_when_name_unknown_but_category_known(self):
        session = {
            "exerciseSets": [
                {
                    "setType": "ACTIVE",
                    "exerciseCategory": "DEADLIFT",
                    "exerciseName": "WEIRD_DEADLIFT_VARIANT",
                    "repetitionCount": 5,
                    "weight": 100.0,
                },
            ],
        }
        result = parse_exercise_sets(session, str(uuid4()), str(uuid4()))
        assert result[0]["movement_pattern"] == "hip_hinge"

    def test_list_format_response(self):
        raw = [
            {
                "setType": "ACTIVE",
                "exerciseCategory": "SQUAT",
                "exerciseName": "BACK_SQUAT",
                "repetitionCount": 5,
                "weight": 100.0,
            },
        ]
        result = parse_exercise_sets(raw, str(uuid4()), str(uuid4()))
        assert len(result) == 1
        assert result[0]["movement_pattern"] == "squat"

    def test_idempotent_parse_produces_same_output(self):
        aid = str(uuid4())
        atid = str(uuid4())
        r1 = parse_exercise_sets(DEADLIFT_SESSION, aid, atid)
        r2 = parse_exercise_sets(DEADLIFT_SESSION, aid, atid)
        assert r1 == r2
