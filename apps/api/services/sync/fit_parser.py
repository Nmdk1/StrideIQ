"""
FIT File Parser — Garmin Activity Files

Parses binary FIT files (from Garmin Activity Files webhook) and extracts
exercise set data in the format expected by strength_parser.parse_exercise_sets().

FIT SDK "set" messages contain per-set exercise data:
  set_type, category, exercise_name, repetitions, weight, duration, set_order

Weight may arrive in grams (÷1000 for kg) or already in kg (heuristic).
Duration may arrive in milliseconds (÷1000 for seconds).
"""

import io
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Garmin FIT SDK category enum values → human-readable names
# https://developer.garmin.com/fit/cookbook/decoding-exercise-names/
_CATEGORY_MAP: Dict[int, str] = {
    0: "BENCH_PRESS",
    1: "CALF_RAISE",
    2: "CARDIO",
    3: "CARRY",
    4: "CHOP",
    5: "CORE",
    6: "CRUNCH",
    7: "CURL",
    8: "DEADLIFT",
    9: "FLYE",
    10: "HIP_RAISE",
    11: "HIP_STABILITY",
    12: "HIP_SWING",
    13: "HYPEREXTENSION",
    14: "LATERAL_RAISE",
    15: "LEG_CURL",
    16: "LEG_RAISE",
    17: "LUNGE",
    18: "OLYMPIC_LIFT",
    19: "PLANK",
    20: "PLYO",
    21: "PULL_UP",
    22: "PUSH_UP",
    23: "ROW",
    24: "SHOULDER_PRESS",
    25: "SHOULDER_STABILITY",
    26: "SHRUG",
    27: "SIT_UP",
    28: "SQUAT",
    29: "TOTAL_BODY",
    30: "TRICEPS_EXTENSION",
    31: "WARM_UP",
    32: "RUN",
    33: "UNKNOWN",
}

_SET_TYPE_MAP: Dict[int, str] = {
    0: "ACTIVE",
    1: "REST",
    2: "ACTIVE",  # "repeat" treated as active
}


def extract_exercise_sets_from_fit(fit_bytes: bytes) -> Dict[str, Any]:
    """Parse a FIT file and extract exercise set data.

    Returns data in the format expected by strength_parser.parse_exercise_sets():
    {
        "exerciseSets": [
            {
                "setType": "ACTIVE" | "REST",
                "exerciseCategory": "DEADLIFT",
                "exerciseName": "BARBELL_DEADLIFT",
                "repetitionCount": 5,
                "weight": 133.8,
                "duration": 45.0,
                "setOrder": 1,
            }
        ]
    }
    """
    try:
        import fitparse
    except ImportError:
        logger.error("fitparse not installed — cannot parse FIT files")
        return {"exerciseSets": []}

    fit_file = fitparse.FitFile(io.BytesIO(fit_bytes))

    sets: List[Dict[str, Any]] = []
    first_logged = False

    for message in fit_file.get_messages("set"):
        values = message.get_values()

        if not first_logged:
            logger.info(
                "FIT file first 'set' message fields: %s",
                list(values.keys()),
            )
            first_logged = True

        set_type_raw = values.get("set_type")
        if isinstance(set_type_raw, int):
            set_type = _SET_TYPE_MAP.get(set_type_raw, "ACTIVE")
        elif isinstance(set_type_raw, str):
            set_type = set_type_raw.upper()
        else:
            set_type = "ACTIVE"

        category_raw = values.get("category")
        exercise_category = _resolve_category(category_raw)

        exercise_name_raw = values.get("exercise_name")
        exercise_name = _resolve_exercise_name(exercise_name_raw, exercise_category)

        reps = values.get("repetitions")
        if reps is None:
            reps = values.get("num_reps", values.get("total_reps"))

        weight_raw = values.get("weight")
        weight_kg = _normalize_weight(weight_raw)

        duration_raw = values.get("duration")
        duration_s = _normalize_duration(duration_raw)

        set_order = values.get("set_order", values.get("order", len(sets) + 1))

        entry: Dict[str, Any] = {
            "setType": set_type,
            "exerciseCategory": exercise_category or "UNKNOWN",
            "exerciseName": exercise_name or exercise_category or "UNKNOWN",
            "repetitionCount": int(reps) if reps is not None else None,
            "weight": weight_kg,
            "duration": duration_s,
            "setOrder": int(set_order) if set_order is not None else len(sets) + 1,
        }
        sets.append(entry)

    if not sets:
        for message in fit_file.get_messages():
            msg_name = message.name
            if "set" in msg_name.lower() or "exercise" in msg_name.lower():
                logger.info(
                    "FIT file: found related message type '%s' with fields: %s",
                    msg_name,
                    list(message.get_values().keys()),
                )

    logger.info("FIT file parsed: %d exercise sets extracted", len(sets))
    return {"exerciseSets": sets}


def _resolve_category(raw: Any) -> Optional[str]:
    if raw is None:
        return None
    if isinstance(raw, int):
        return _CATEGORY_MAP.get(raw, f"CATEGORY_{raw}")
    if isinstance(raw, str):
        return raw.upper().replace(" ", "_")
    return str(raw).upper()


def _resolve_exercise_name(raw: Any, category: Optional[str]) -> Optional[str]:
    if raw is None:
        return category
    if isinstance(raw, int):
        return f"{category}_{raw}" if category else f"EXERCISE_{raw}"
    if isinstance(raw, str):
        return raw.upper().replace(" ", "_")
    return str(raw).upper()


def _normalize_weight(raw: Any) -> Optional[float]:
    """Convert weight to kg. FIT files may store in grams or 100ths of kg."""
    if raw is None:
        return None
    val = float(raw)
    if val <= 0:
        return None
    if val > 1000:
        return round(val / 1000, 2)
    return round(val, 2)


def _normalize_duration(raw: Any) -> Optional[float]:
    """Convert duration to seconds. FIT may store in ms or fractional seconds."""
    if raw is None:
        return None
    val = float(raw)
    if val <= 0:
        return None
    if val > 60000:
        return round(val / 1000, 1)
    return round(val, 1)
