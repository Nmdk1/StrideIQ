from __future__ import annotations

import os
import json
import re
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional, Dict, List, Any, Tuple
from uuid import UUID, uuid4
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from services import coach_tools  # noqa: E402


class ToolsMixin:
    """Mixin extracted from AICoach - tools methods."""

    def _opus_tools(self) -> List[Dict[str, Any]]:
        """Define tools available to Opus (Anthropic format) — FULL tool suite."""
        return [
            {
                "name": "get_recent_runs",
                "description": "Get recent running activities with distances, paces, heart rates, and workout types.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "days": {"type": "integer", "description": "Number of days to look back (default 14, max 730)"}
                    },
                    "required": [],
                },
            },
            {
                "name": "search_activities",
                "description": "Search the athlete's activity history by date, name, race flag, distance, sport, or workout type. Use this when verifying a specific older race/activity or when the athlete says an activity exists.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "start_date": {"type": "string", "description": "Optional start date (YYYY-MM-DD or ISO datetime)."},
                        "end_date": {"type": "string", "description": "Optional end date (YYYY-MM-DD or ISO datetime)."},
                        "name_contains": {"type": "string", "description": "Optional case-insensitive title/name substring."},
                        "sport": {"type": "string", "description": "Optional sport filter, default run."},
                        "workout_type": {"type": "string", "description": "Optional workout_type filter."},
                        "race_only": {"type": "boolean", "description": "If true, only return race candidates or user-verified races."},
                        "distance_min_m": {"type": "integer", "description": "Optional minimum distance in meters."},
                        "distance_max_m": {"type": "integer", "description": "Optional maximum distance in meters."},
                        "limit": {"type": "integer", "description": "Max results (default 10, max 50)."},
                    },
                    "required": [],
                },
            },
            {
                "name": "get_calendar_day_context",
                "description": "Get plan + actual context for a specific calendar day (planned workout + completed activities with IDs).",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "day": {"type": "string", "description": "Calendar date in YYYY-MM-DD format."}
                    },
                    "required": ["day"],
                },
            },
            {
                "name": "get_efficiency_trend",
                "description": "Get efficiency trend data over time (pace-at-HR time series + summary). Use for 'am I getting fitter?' questions.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "days": {"type": "integer", "description": "How many days of history to analyze (default 30, max 365)"}
                    },
                    "required": [],
                },
            },
            {
                "name": "get_plan_week",
                "description": "Get the current week's planned workouts for the athlete's active training plan.",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
            {
                "name": "get_weekly_volume",
                "description": "Get weekly mileage totals for trend analysis.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "weeks": {"type": "integer", "description": "Number of weeks to look back (default 12, max 104)"}
                    },
                    "required": [],
                },
            },
            {
                "name": "get_training_load",
                "description": "Get current training load metrics (fitness, fatigue, form).",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
            {
                "name": "get_training_paces",
                "description": "Get RPI-based training paces (easy, threshold, interval, marathon). THIS IS THE AUTHORITATIVE SOURCE for training paces.",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
            {
                "name": "get_correlations",
                "description": "Get correlations between wellness inputs and efficiency outputs.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "days": {"type": "integer", "description": "How many days of history to analyze (default 30, max 365)"}
                    },
                    "required": [],
                },
            },
            {
                "name": "get_race_predictions",
                "description": "Get RPI-based equivalent race times for 5K, 10K, Half Marathon, and Marathon, plus the athlete's actual race history. These come from verified race data, not theoretical models.",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
            {
                "name": "get_race_strategy_packet",
                "description": "Build the full deterministic race strategy packet before answering a race plan: target race, plan week, prior course/race activity, recent race-relevant workouts, race history, anchors, invalid anchors, injury context, training load context, and athlete-stated race psychology. Use this FIRST for race strategy, race plan, pacing, or execution questions.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "race_name": {"type": "string", "description": "Optional race name from the athlete message, e.g. Mayor's Cup 5K"},
                        "race_date": {"type": "string", "description": "Optional race date YYYY-MM-DD"},
                        "race_distance": {"type": "string", "description": "Optional distance label, e.g. 5k, 10k, half marathon, marathon"},
                        "lookback_days": {"type": "integer", "description": "How far back to search for race-relevant workouts (default 120, max 365)"},
                    },
                    "required": [],
                },
            },
            {
                "name": "get_training_block_narrative",
                "description": "Summarize recent quality-session structure from activities and splits. Use for race readiness, workout arc, and evidence-vs-zone questions.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "days": {"type": "integer", "description": "Lookback window in days (default 42, max 120)"},
                        "limit": {"type": "integer", "description": "Max quality sessions to return (default 12, max 25)"},
                    },
                    "required": [],
                },
            },
            {
                "name": "get_recovery_status",
                "description": "Get recovery metrics: half-life, durability index, false fitness and masked fatigue signals.",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
            {
                "name": "get_active_insights",
                "description": "Get prioritized actionable insights for the athlete.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "description": "Max insights to return (default 5, max 10)"}
                    },
                    "required": [],
                },
            },
            {
                "name": "get_pb_patterns",
                "description": "Get training patterns that preceded personal bests, including optimal form range.",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
            {
                "name": "get_efficiency_by_zone",
                "description": "Get efficiency trend for specific effort zones (easy, threshold, race).",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "effort_zone": {"type": "string", "description": "Effort zone to analyze: easy, threshold, or race (default threshold)"},
                        "days": {"type": "integer", "description": "Days of history (default 90, max 365)"}
                    },
                    "required": [],
                },
            },
            {
                "name": "get_nutrition_correlations",
                "description": "Get correlations between pre/post-activity nutrition and performance/recovery.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "days": {"type": "integer", "description": "Days of history (default 90, max 365)"}
                    },
                    "required": [],
                },
            },
            {
                "name": "get_nutrition_log",
                "description": "Get detailed nutrition log entries. Use when the athlete asks about their food, meals, fueling, macros, or calorie intake. Returns individual entries with macros, daily summaries, and pre-run fueling patterns.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "days": {"type": "integer", "description": "Days of history to retrieve (default 7, max 90)"},
                        "entry_type": {"type": "string", "description": "Filter by type: daily, pre_activity, during_activity, post_activity (default: all)"},
                        "activity_id": {"type": "string", "description": "Filter to entries linked to a specific activity UUID"}
                    },
                    "required": [],
                },
            },
            {
                "name": "get_best_runs",
                "description": "Get best runs by an explicit metric (efficiency, pace, distance, intensity_score), optionally filtered to an effort zone.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "days": {"type": "integer", "description": "History window (default 365, max 730)"},
                        "metric": {"type": "string", "description": "Ranking metric: efficiency, pace, distance, or intensity_score"},
                        "limit": {"type": "integer", "description": "Max results (default 5, max 10)"},
                        "effort_zone": {"type": "string", "description": "Optional effort zone filter: easy, threshold, or race"}
                    },
                    "required": [],
                },
            },
            {
                "name": "compare_training_periods",
                "description": "Compare last N days vs the previous N days (volume/run count deltas).",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "days": {"type": "integer", "description": "Days per period (default 28, max 180)"}
                    },
                    "required": [],
                },
            },
            {
                "name": "get_coach_intent_snapshot",
                "description": "Get the athlete's current self-guided intent snapshot (goals/constraints) with staleness indicator.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "ttl_days": {"type": "integer", "description": "How long the snapshot is considered fresh (default 7)"}
                    },
                    "required": [],
                },
            },
            {
                "name": "set_coach_intent_snapshot",
                "description": "Update the athlete's self-guided intent snapshot (athlete-led) to avoid repetitive questioning.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "training_intent": {"type": "string", "description": "Athlete intent: through_fatigue | build_fitness | freshen_for_event"},
                        "next_event_date": {"type": "string", "description": "Optional YYYY-MM-DD for race/benchmark"},
                        "next_event_type": {"type": "string", "description": "Optional: race | benchmark | other"},
                        "pain_flag": {"type": "string", "description": "none | niggle | pain"},
                        "time_available_min": {"type": "integer", "description": "Typical time available (minutes)"},
                        "weekly_mileage_target": {"type": "number", "description": "Athlete-stated target miles/week"}
                    },
                    "required": [],
                },
            },
            {
                "name": "get_training_prescription_window",
                "description": "Deterministically prescribe training for 1-7 days (exact distances/paces/structure).",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "start_date": {"type": "string", "description": "Start date YYYY-MM-DD (default today)"},
                        "days": {"type": "integer", "description": "How many days (1-7)"},
                        "time_available_min": {"type": "integer", "description": "Optional time cap for workouts (minutes)"},
                        "weekly_mileage_target": {"type": "number", "description": "Optional athlete target miles/week"},
                        "pain_flag": {"type": "string", "description": "none | niggle | pain"}
                    },
                    "required": [],
                },
            },
            {
                "name": "get_wellness_trends",
                "description": "Get wellness trends from daily check-ins: sleep, stress, soreness, HRV, resting HR, and mindset metrics over time.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "days": {"type": "integer", "description": "How many days of wellness data to analyze (default 28, max 90)"}
                    },
                    "required": [],
                },
            },
            {
                "name": "get_athlete_profile",
                "description": "Get athlete physiological profile: age, RPI, runner type, threshold pace, durability, and training metrics. Training paces come from get_training_paces, not from this tool.",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
            {
                "name": "get_training_load_history",
                "description": "Get daily fitness/fatigue/form history showing training load progression and injury risk over time.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "days": {"type": "integer", "description": "How many days of load history (default 42, max 90)"}
                    },
                    "required": [],
                },
            },
            {
                "name": "compute_running_math",
                "description": "Compute pace/time/distance math deterministically.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "pace_per_mile": {"type": "string"},
                        "pace_per_km": {"type": "string"},
                        "distance_miles": {"type": "number"},
                        "distance_km": {"type": "number"},
                        "time_seconds": {"type": "integer"},
                        "operation": {
                            "type": "string",
                            "description": "pace_to_finish | finish_to_pace | split_calc",
                        },
                    },
                    "required": ["operation"],
                },
            },
            {
                "name": "analyze_run_streams",
                "description": "Analyze per-second stream data for a run activity. Returns segment classification, cardiac/pace drift, coachable moments, and optional plan comparison. Uses the athlete's physiological profile for N=1 individualized analysis.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "activity_id": {
                            "type": "string",
                            "description": "UUID of the activity to analyze (from get_recent_runs or get_calendar_day_context).",
                        },
                    },
                    "required": ["activity_id"],
                },
            },
            {
                "name": "get_mile_splits",
                "description": "Compute mile/km splits for a specific activity using stream data first, with device laps as fallback.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "activity_id": {
                            "type": "string",
                            "description": "UUID of the activity to split (from get_recent_runs or get_calendar_day_context).",
                        },
                        "unit": {
                            "type": "string",
                            "description": "Split unit: 'mi' (default) or 'km'.",
                        },
                    },
                    "required": ["activity_id"],
                },
            },
            {
                "name": "get_profile_edit_paths",
                "description": "Get deterministic profile navigation for editing athlete fields (birthdate, sex, display name, height, email).",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "field": {
                            "type": "string",
                            "description": "Profile field name, e.g. birthdate, sex, display_name, height_cm, email.",
                        }
                    },
                    "required": [],
                },
            },
        ]



    def _execute_opus_tool(self, athlete_id: UUID, tool_name: str, tool_input: Dict[str, Any]) -> str:
        """Execute a tool call for Opus/Gemini and return JSON result.
        
        Handles the FULL tool suite.
        Used by both query_opus() and query_gemini() code paths.
        """
        import json
        try:
            if tool_name == "get_recent_runs":
                days = tool_input.get("days", 14)
                result = coach_tools.get_recent_runs(self.db, athlete_id, days=min(days, 730))
            elif tool_name == "search_activities":
                result = coach_tools.search_activities(self.db, athlete_id, **tool_input)
            elif tool_name == "get_calendar_day_context":
                result = coach_tools.get_calendar_day_context(self.db, athlete_id, **tool_input)
            elif tool_name == "get_efficiency_trend":
                result = coach_tools.get_efficiency_trend(self.db, athlete_id, **tool_input)
            elif tool_name == "get_plan_week":
                result = coach_tools.get_plan_week(self.db, athlete_id)
            elif tool_name == "get_weekly_volume":
                weeks = tool_input.get("weeks", 12)
                result = coach_tools.get_weekly_volume(self.db, athlete_id, weeks=min(weeks, 104))
            elif tool_name == "get_training_load":
                result = coach_tools.get_training_load(self.db, athlete_id)
            elif tool_name == "get_training_paces":
                result = coach_tools.get_training_paces(self.db, athlete_id)
            elif tool_name == "get_correlations":
                result = coach_tools.get_correlations(self.db, athlete_id, **tool_input)
            elif tool_name == "get_race_predictions":
                result = coach_tools.get_race_predictions(self.db, athlete_id)
            elif tool_name == "get_race_strategy_packet":
                result = coach_tools.get_race_strategy_packet(self.db, athlete_id, **tool_input)
            elif tool_name == "get_training_block_narrative":
                result = coach_tools.get_training_block_narrative(self.db, athlete_id, **tool_input)
            elif tool_name == "get_recovery_status":
                result = coach_tools.get_recovery_status(self.db, athlete_id)
            elif tool_name == "get_active_insights":
                result = coach_tools.get_active_insights(self.db, athlete_id, **tool_input)
            elif tool_name == "get_pb_patterns":
                result = coach_tools.get_pb_patterns(self.db, athlete_id)
            elif tool_name == "get_efficiency_by_zone":
                result = coach_tools.get_efficiency_by_zone(self.db, athlete_id, **tool_input)
            elif tool_name == "get_nutrition_correlations":
                result = coach_tools.get_nutrition_correlations(self.db, athlete_id, **tool_input)
            elif tool_name == "get_nutrition_log":
                result = coach_tools.get_nutrition_log(self.db, athlete_id, **tool_input)
            elif tool_name == "get_best_runs":
                result = coach_tools.get_best_runs(self.db, athlete_id, **tool_input)
            elif tool_name == "compare_training_periods":
                result = coach_tools.compare_training_periods(self.db, athlete_id, **tool_input)
            elif tool_name == "get_coach_intent_snapshot":
                result = coach_tools.get_coach_intent_snapshot(self.db, athlete_id, **tool_input)
            elif tool_name == "set_coach_intent_snapshot":
                result = coach_tools.set_coach_intent_snapshot(self.db, athlete_id, **tool_input)
            elif tool_name == "get_training_prescription_window":
                result = coach_tools.get_training_prescription_window(self.db, athlete_id, **tool_input)
            elif tool_name == "get_wellness_trends":
                result = coach_tools.get_wellness_trends(self.db, athlete_id, **tool_input)
            elif tool_name == "get_athlete_profile":
                result = coach_tools.get_athlete_profile(self.db, athlete_id)
            elif tool_name == "get_training_load_history":
                result = coach_tools.get_training_load_history(self.db, athlete_id, **tool_input)
            elif tool_name == "compute_running_math":
                result = coach_tools.compute_running_math(self.db, athlete_id, **tool_input)
            elif tool_name == "analyze_run_streams":
                result = coach_tools.analyze_run_streams(self.db, athlete_id, **tool_input)
            elif tool_name == "get_mile_splits":
                result = coach_tools.get_mile_splits(self.db, athlete_id, **tool_input)
            elif tool_name == "get_profile_edit_paths":
                result = coach_tools.get_profile_edit_paths(self.db, athlete_id, **tool_input)
            else:
                result = {"error": f"Unknown tool: {tool_name}"}
            return json.dumps(result, default=str)
        except Exception as e:
            logger.warning(f"Tool execution error for {tool_name}: {e}")
            return json.dumps({"error": str(e)})

    @staticmethod
    def _is_temporal_fact_expired(fact: Any, now_utc: datetime) -> bool:
        if not getattr(fact, "temporal", False):
            return False
        ttl_days = getattr(fact, "ttl_days", None)
        extracted_at = getattr(fact, "extracted_at", None)
        if ttl_days is None or extracted_at is None:
            return False
        extracted = extracted_at
        if getattr(extracted, "tzinfo", None) is None:
            extracted = extracted.replace(tzinfo=timezone.utc)
        return extracted < now_utc - timedelta(days=int(ttl_days))



    def _get_fresh_athlete_facts(self, athlete_id: UUID, max_facts: int = 15) -> List[Any]:
        from models import AthleteFact as _AF

        batch_size = 50
        max_scan_rows = 500
        now_utc = datetime.now(timezone.utc)
        selected: List[Any] = []
        offset = 0

        while len(selected) < max_facts and offset < max_scan_rows:
            batch = (
                self.db.query(_AF)
                .filter(
                    _AF.athlete_id == athlete_id,
                    _AF.is_active == True,  # noqa: E712
                )
                .order_by(_AF.confirmed_by_athlete.desc(), _AF.extracted_at.desc())
                .offset(offset)
                .limit(batch_size)
                .all()
            )
            if not batch:
                break

            for fact in batch:
                if self._is_temporal_fact_expired(fact, now_utc):
                    continue
                selected.append(fact)
                if len(selected) >= max_facts:
                    break
            offset += batch_size
        return selected



    def _kimi_tools(self) -> List[Dict[str, Any]]:
        """Convert Anthropic tool schema to OpenAI-compatible function tools."""
        return [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": t["input_schema"],
                },
            }
            for t in self._opus_tools()
        ]



