"""Coach Tools Package - split from monolithic coach_tools.py."""

from ._utils import _iso, _mi_from_m, _pace_str_mi, _pace_seconds_from_text, _fmt_mmss, _relative_date, _preferred_units, _pace_str, _interpret_nutrition_correlation, _format_run_context, _guardrails_from_pain  # noqa: F401
from .activity import get_recent_runs, search_activities, get_calendar_day_context, get_best_runs, _to_float_list, _interpolate_time_at_distance, _format_duration_hms, get_mile_splits, analyze_run_streams  # noqa: F401
from .brief import build_athlete_brief, compute_running_math  # noqa: F401
from .insights import get_correlations, get_active_insights  # noqa: F401
from .load import get_training_load, get_recovery_status, get_weekly_volume, get_training_load_history  # noqa: F401
from .performance import get_efficiency_trend, get_training_paces, get_race_predictions, get_pb_patterns, get_efficiency_by_zone  # noqa: F401
from .plan import get_plan_week, get_training_prescription_window  # noqa: F401
from .profile import get_athlete_profile, get_profile_edit_paths, _get_intent_snapshot, _is_snapshot_stale, get_coach_intent_snapshot, set_coach_intent_snapshot  # noqa: F401
from .race_strategy import get_race_strategy_packet  # noqa: F401
from .wellness import get_nutrition_correlations, get_nutrition_log, compare_training_periods, get_wellness_trends  # noqa: F401
from ._utils import _M_PER_MI  # noqa: F401

__all__ = [
    "_M_PER_MI",
    "_fmt_mmss",
    "_format_duration_hms",
    "_format_run_context",
    "_get_intent_snapshot",
    "_guardrails_from_pain",
    "_interpolate_time_at_distance",
    "_interpret_nutrition_correlation",
    "_is_snapshot_stale",
    "_iso",
    "_mi_from_m",
    "_pace_seconds_from_text",
    "_pace_str",
    "_pace_str_mi",
    "_preferred_units",
    "_relative_date",
    "_to_float_list",
    "analyze_run_streams",
    "build_athlete_brief",
    "compare_training_periods",
    "compute_running_math",
    "get_active_insights",
    "get_athlete_profile",
    "get_best_runs",
    "get_calendar_day_context",
    "get_coach_intent_snapshot",
    "get_correlations",
    "get_efficiency_by_zone",
    "get_efficiency_trend",
    "get_mile_splits",
    "get_nutrition_correlations",
    "get_nutrition_log",
    "get_pb_patterns",
    "get_plan_week",
    "get_profile_edit_paths",
    "get_race_predictions",
    "get_race_strategy_packet",
    "get_recent_runs",
    "get_recovery_status",
    "get_training_load",
    "get_training_load_history",
    "get_training_paces",
    "get_training_prescription_window",
    "get_weekly_volume",
    "get_wellness_trends",
    "search_activities",
    "set_coach_intent_snapshot",
]
