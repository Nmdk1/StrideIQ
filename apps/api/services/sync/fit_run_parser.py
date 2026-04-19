"""
FIT File Parser — Run / Cycle / Walk / Hike summary + lap data

Parses Garmin FIT files for endurance activities and extracts:
  - Session message: one per file, the activity-level summary
  - Lap messages:    one per lap, with per-lap aggregates

The Garmin JSON API does NOT carry running dynamics, power, or true
moving time at activity level (per garmin_adapter.py D3 contract). The
FIT file does. This parser is the only path that can populate those
columns on Activity / ActivitySplit.

WHAT WE INGEST (real, measured by sensors):
  - Power (W), avg/max
  - Cadence (spm/rpm), avg/max
  - Stride length (m)
  - Ground contact time (ms) and GCT balance (%)
  - Vertical oscillation (cm) and vertical ratio (%)
  - True moving time (s) (vs elapsed time)
  - Total ascent / descent (m)
  - Temperature (avg / min / max in °C)
  - Calories
  - Intensity minutes (moderate / vigorous)
  - Per-lap aggregates of all of the above
  - Garmin self-evaluation (feel + perceived effort) — kept as a low-confidence
    fallback. ActivityFeedback always wins when present.

WHAT WE DO NOT INGEST (proprietary models, treated as fantasy):
  - Body Battery / its impact
  - Training Effect (aerobic, anaerobic, label)
  - Garmin stress score
  - Sweat loss / fluid net (model output, not measured)
  - Race predictor / fitness age

Field names follow the Garmin FIT SDK's `session` and `lap` profile messages.
The `fitparse` library returns canonical units (meters, seconds, m/s, W, etc.)
unless otherwise noted in comments below.
"""

from __future__ import annotations

import io
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# Garmin FIT SDK feel enum (event_type=user_marker, event=user)
# Maps the integer the watch records to a human label.
_FEEL_MAP: Dict[int, str] = {
    0: "very_strong",
    25: "strong",
    50: "normal",
    75: "weak",
    100: "very_weak",
}


def parse_run_fit(fit_bytes: bytes) -> Dict[str, Any]:
    """Parse a FIT file and return whole-activity + per-lap data.

    Returns:
        {
            "session": dict | None,
            "laps":    list[dict],
        }

    `session` is None when the FIT file has no session message (rare, happens
    on partial uploads or corrupted files). `laps` is always a list (possibly
    empty). Numeric fields that are absent from the FIT file are returned as
    None so that consumers can distinguish "never recorded" from zero.
    """
    try:
        import fitparse  # local import — many envs don't have FIT data
    except ImportError:
        logger.error("fitparse not installed — cannot parse FIT files")
        return {"session": None, "laps": []}

    try:
        fit_file = fitparse.FitFile(io.BytesIO(fit_bytes))
    except Exception as exc:
        logger.warning("FIT parse failed: %s", exc)
        return {"session": None, "laps": []}

    session = _extract_session(fit_file)
    laps = _extract_laps(fit_file)

    logger.info(
        "FIT run/endurance parsed: session=%s laps=%d",
        "yes" if session else "no",
        len(laps),
    )
    return {"session": session, "laps": laps}


def _extract_session(fit_file) -> Optional[Dict[str, Any]]:
    """Pull the (single) session message and project to internal field names."""
    messages = list(fit_file.get_messages("session"))
    if not messages:
        return None
    # FIT files normally have exactly one session per file. If multiple appear
    # (multi-sport stitched), we take the first — the matching adapter is the
    # primary owner of multi-sport disaggregation, not us.
    sess = messages[0].get_values()

    return {
        # --- Sport / type ---
        "sport": _str_or_none(sess.get("sport")),
        "sub_sport": _str_or_none(sess.get("sub_sport")),
        # --- Timing ---
        "elapsed_time_s": _int_or_none(sess.get("total_elapsed_time")),
        # total_timer_time is true moving time (excludes auto-pause).
        "moving_time_s": _int_or_none(sess.get("total_timer_time")),
        # --- Distance / elevation ---
        "distance_m": _float_or_none(sess.get("total_distance")),
        "total_ascent_m": _float_or_none(sess.get("total_ascent")),
        "total_descent_m": _float_or_none(sess.get("total_descent")),
        # --- HR ---
        "avg_hr": _int_or_none(sess.get("avg_heart_rate")),
        "max_hr": _int_or_none(sess.get("max_heart_rate")),
        # --- Cadence ---
        # FIT stores running cadence as steps per minute for ONE foot (typical
        # 80–100). Total cadence is 2x. We canonicalize to total spm here.
        "avg_run_cadence_spm": _double_cadence(sess.get("avg_running_cadence")),
        "max_run_cadence_spm": _double_cadence(sess.get("max_running_cadence")),
        # Bike cadence stays as-is (already total RPM).
        "avg_cadence_rpm": _int_or_none(sess.get("avg_cadence")) if _str_or_none(sess.get("sport")) in ("cycling",) else None,
        # --- Speed (m/s) ---
        "avg_speed_mps": _float_or_none(sess.get("enhanced_avg_speed") or sess.get("avg_speed")),
        "max_speed_mps": _float_or_none(sess.get("enhanced_max_speed") or sess.get("max_speed")),
        # --- Power ---
        "avg_power_w": _int_or_none(sess.get("avg_power")),
        "max_power_w": _int_or_none(sess.get("max_power")),
        "normalized_power_w": _int_or_none(sess.get("normalized_power")),
        # --- Running dynamics ---
        # Stride length: fitparse returns meters (typical 0.9 – 1.5 m).
        "avg_stride_length_m": _float_or_none(sess.get("avg_stride_length")),
        # Stance time: ms (typical 200 – 300).
        "avg_ground_contact_ms": _float_or_none(sess.get("avg_stance_time")),
        # Stance time balance is a percent split L/R, ~50%.
        "avg_ground_contact_balance_pct": _float_or_none(sess.get("avg_stance_time_balance")),
        # Vertical oscillation: fitparse returns mm; convert to cm for display.
        "avg_vertical_oscillation_cm": _mm_to_cm(sess.get("avg_vertical_oscillation")),
        # Vertical ratio is already a percent.
        "avg_vertical_ratio_pct": _float_or_none(sess.get("avg_vertical_ratio")),
        # --- Energy ---
        "total_calories": _int_or_none(sess.get("total_calories")),
        "moderate_intensity_minutes": _int_or_none(sess.get("total_moderate_intensity_minutes")),
        "vigorous_intensity_minutes": _int_or_none(sess.get("total_vigorous_intensity_minutes")),
        # --- Environment ---
        "avg_temperature_c": _float_or_none(sess.get("avg_temperature")),
        "min_temperature_c": _float_or_none(sess.get("min_temperature")),
        "max_temperature_c": _float_or_none(sess.get("max_temperature")),
        # --- Garmin self-evaluation (low-confidence fallback) ---
        # `feel` is a 0/25/50/75/100 enum from the watch tap-rating UI.
        "garmin_feel": _decode_feel(sess.get("feel")),
        # `rpe` is the same as Garmin "perceived effort" (1–10 scale).
        # Some firmware reports under `perceived_effort`; check both.
        "garmin_perceived_effort": _int_or_none(
            sess.get("perceived_effort") or sess.get("rpe")
        ),
        # --- Counts ---
        "num_laps": _int_or_none(sess.get("num_laps")),
        "total_strides": _int_or_none(sess.get("total_strides")),
    }


def _extract_laps(fit_file) -> List[Dict[str, Any]]:
    """Pull all lap messages and project to per-lap dicts."""
    out: List[Dict[str, Any]] = []
    for idx, msg in enumerate(fit_file.get_messages("lap"), start=1):
        lap = msg.get_values()
        out.append({
            "lap_number": idx,
            # --- Timing ---
            "elapsed_time_s": _int_or_none(lap.get("total_elapsed_time")),
            "moving_time_s": _int_or_none(lap.get("total_timer_time")),
            # --- Distance / elevation ---
            "distance_m": _float_or_none(lap.get("total_distance")),
            "total_ascent_m": _float_or_none(lap.get("total_ascent")),
            "total_descent_m": _float_or_none(lap.get("total_descent")),
            # --- HR ---
            "avg_hr": _int_or_none(lap.get("avg_heart_rate")),
            "max_hr": _int_or_none(lap.get("max_heart_rate")),
            # --- Cadence (canonicalized total spm for run, rpm for bike) ---
            "avg_run_cadence_spm": _double_cadence(lap.get("avg_running_cadence")),
            "max_run_cadence_spm": _double_cadence(lap.get("max_running_cadence")),
            # --- Speed ---
            "avg_speed_mps": _float_or_none(lap.get("enhanced_avg_speed") or lap.get("avg_speed")),
            "max_speed_mps": _float_or_none(lap.get("enhanced_max_speed") or lap.get("max_speed")),
            # --- Power ---
            "avg_power_w": _int_or_none(lap.get("avg_power")),
            "max_power_w": _int_or_none(lap.get("max_power")),
            "normalized_power_w": _int_or_none(lap.get("normalized_power")),
            # --- Running dynamics ---
            "avg_stride_length_m": _float_or_none(lap.get("avg_stride_length")),
            "avg_ground_contact_ms": _float_or_none(lap.get("avg_stance_time")),
            "avg_ground_contact_balance_pct": _float_or_none(lap.get("avg_stance_time_balance")),
            "avg_vertical_oscillation_cm": _mm_to_cm(lap.get("avg_vertical_oscillation")),
            "avg_vertical_ratio_pct": _float_or_none(lap.get("avg_vertical_ratio")),
            # --- Energy / environment ---
            "total_calories": _int_or_none(lap.get("total_calories")),
            "avg_temperature_c": _float_or_none(lap.get("avg_temperature")),
            "max_temperature_c": _float_or_none(lap.get("max_temperature")),
            # --- Lap classification (manual / time / distance / position) ---
            "lap_trigger": _str_or_none(lap.get("lap_trigger")),
            # `intensity` distinguishes active / rest / warmup / cooldown when
            # the watch user marked it.
            "intensity": _str_or_none(lap.get("intensity")),
        })
    return out


# ---------------------------------------------------------------------------
# Type coercion helpers — same conventions as garmin_adapter._*
# ---------------------------------------------------------------------------


def _str_or_none(value: Any) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip()
    return s if s else None


def _int_or_none(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


def _float_or_none(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    # Reject NaN / inf — they pollute aggregates downstream.
    if f != f or f in (float("inf"), float("-inf")):
        return None
    return f


def _mm_to_cm(value: Any) -> Optional[float]:
    """fitparse returns vertical oscillation in mm; we display in cm."""
    f = _float_or_none(value)
    if f is None:
        return None
    return round(f / 10.0, 2)


def _double_cadence(value: Any) -> Optional[int]:
    """Garmin records single-foot cadence (~80–100). Athletes think in steps/min
    (~160–200). Convert if the value looks like single-foot.
    """
    raw = _float_or_none(value)
    if raw is None or raw <= 0:
        return None
    # 120 spm is well below normal running cadence; below that, treat as
    # single-foot cadence and double it. Above, treat as already total.
    return int(round(raw * 2)) if raw < 120 else int(round(raw))


def _decode_feel(value: Any) -> Optional[str]:
    """Translate Garmin `feel` enum (0/25/50/75/100) to a human label."""
    if value is None:
        return None
    if isinstance(value, str):
        # Some firmware reports the label directly.
        s = value.strip().lower()
        return s if s else None
    try:
        return _FEEL_MAP.get(int(value))
    except (TypeError, ValueError):
        return None
