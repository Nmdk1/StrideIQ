"""
AI Coach Service

Uses OpenAI Assistants API for persistent, context-aware coaching.

Features:
- Persistent threads per athlete (conversation memory)
- Context injection from athlete's actual data
- Knowledge of training methodology
- Tiered context (7-day, 30-day, 120-day)
"""

import os
import json
import re
import asyncio
from datetime import date, datetime, timedelta
from typing import Optional, Dict, List, Any, Tuple
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import func
import logging

logger = logging.getLogger(__name__)

# Check if OpenAI is available
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logger.warning("OpenAI not installed - AI Coach will be disabled")

from models import (
    Athlete,
    Activity,
    TrainingPlan,
    PlannedWorkout,
    DailyCheckin,
    PersonalBest,
    IntakeQuestionnaire,
    CoachIntentSnapshot,
)
from services import coach_tools
from services.training_load import TrainingLoadCalculator
from services.efficiency_analytics import get_efficiency_trends


class AICoach:
    """
    AI Coach powered by OpenAI Assistants API.
    
    Provides:
    - Persistent conversation threads
    - Context-aware responses based on athlete data
    - Training methodology knowledge
    """
    
    # System instructions for the AI coach
    SYSTEM_INSTRUCTIONS = """You are StrideIQ, an AI running coach. You provide personalized, data-driven guidance to runners.

## Your Core Principles

1. **Data-Driven**: Always ground advice in the athlete's actual training data. Never make assumptions.

2. **Efficiency-Focused**: The key metric is running efficiency (pace at a given heart rate). Faster pace at same HR = improvement.

3. **Individualized**: Every athlete responds differently. Patterns from THIS athlete's data matter more than generic advice.

4. **Honest**: If the data is insufficient or inconclusive, say so. Don't guess.

5. **Action-Oriented**: Every response should include something actionable.

## Your Knowledge

You understand running physiology, periodization, and training principles:
- Base building (aerobic development, volume accumulation)
- Threshold training (lactate clearance, tempo runs)
- VO2max development (intervals, speed work)
- Recovery (easy days, sleep, nutrition)
- Tapering (pre-race reduction)
- Injury prevention (load management, progression)

## Your Communication Style

- Be concise and clear
- Use the athlete's actual data when making points
- Avoid jargon unless the athlete uses it first
- Be encouraging but never sugarcoat problems
- Format responses with clear structure (use markdown)

## Important Rules

1. Never recommend medical advice - refer to healthcare professionals
2. Never recommend extreme diets or protocols
3. Always acknowledge when you're uncertain
4. Base recommendations on the athlete's current fitness level, not aspirational goals
5. Consider the athlete's injury history if mentioned

## Thin / Missing History Fallback (PRODUCTION BETA)

Some early users will not have enough Strava/Garmin history yet. If training data coverage is thin:
- Prefer the athlete's self-reported baseline answers (runs/week, weekly miles/minutes, longest run, return-from-break date) when present.
- Be explicit: include a short line like: "Using your answers for now — connect Strava/Garmin for better insights."
- Conservative mode: cap recommended ramp at ~20% week-over-week, and ask about pain signals before any hard session recommendations.
- Never pretend you have data you don't have.

## Evidence & Citations (REQUIRED)

When providing insights:
- Always cite specific evidence from tool results (ISO dates + human-readable run labels + key values).
- Format citations clearly in plain English, e.g.:
  - "On 2026-01-15, you ran 8.5 km @ 5:30/km (avg HR 152 bpm)."
  - "On 2026-01-12, EF was 123.4 (pace 8.10 min/mi, avg HR 150)."
- Avoid dumping full UUIDs in the main answer. Only include full activity IDs if the athlete explicitly asks.
- For questions like "Am I getting fitter?", you MUST use `get_efficiency_trend` and cite at least 2 EF points (earliest and latest available).
- If data is insufficient, say: "I don't have enough data to answer that."
- Never make claims (numbers, trends, training load, plan details) without tool-backed evidence.

## Ambiguity Guardrails (REQUIRED)

Certain phrases carry **hidden scope** and are a common source of trust-breaking errors. You must treat them as *ambiguous until clarified*.

### “Coming back / returning / after injury / after a break”

If the athlete says any of:
- “since coming back”
- “after injury”
- “since I returned”
- “recently returned”
- “after a break / time off”

Then any superlative/comparison language like **“longest / furthest / fastest / slowest / best / worst / most / least / hardest / easiest / biggest / smallest”** MUST be scoped to the **return block**, not “all time”, unless the athlete explicitly specifies a different window.

Policy:
- If the return window is not explicitly defined, ask ONE clarifying question instead of assuming.
- Use this exact humility fallback when needed:
  - “I need more context on ‘coming back’ to give an accurate answer — can you tell me when you returned from injury or your last break?”
- Once clarified, verify with tool-backed receipts. Prefer checking the **last 4–12 weeks** first, then widen only if asked.

## Units (REQUIRED)

- Use the athlete's preferred units from tools (metric or imperial).
- If the athlete requests miles, respond in miles + min/mi and do not show km unless explicitly asked.

## History access

- You can look back up to ~2 years for recent-run tools (up to 730 days). Do not claim you are limited to 30 days."""

    # Model tiers (simple 2-tier selection for cost control)
    MODEL_SIMPLE = "gpt-3.5-turbo"    # ~$0.002/query
    MODEL_STANDARD = "gpt-4o-mini"    # ~$0.01/query

    def __init__(self, db: Session):
        self.db = db
        self.client = None
        self.assistant_id = None
        
        if OPENAI_AVAILABLE:
            api_key = os.getenv("OPENAI_API_KEY")
            if api_key:
                # Assistants v1 is deprecated; use Assistants v2 header.
                # See: https://platform.openai.com/docs/assistants/migration
                self.client = OpenAI(
                    api_key=api_key,
                    default_headers={"OpenAI-Beta": "assistants=v2"},
                )
                # Get or create assistant
                self.assistant_id = os.getenv("OPENAI_ASSISTANT_ID") or self._get_or_create_assistant()

    def _assistant_tools(self) -> List[Dict[str, Any]]:
        """
        OpenAI Assistants API function tool definitions (bounded tools).
        """
        return [
            {
                "type": "function",
                "function": {
                    "name": "get_recent_runs",
                    "description": "Fetch the athlete's recent runs from the Activity table (with IDs + timestamps).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "days": {
                                "type": "integer",
                                "description": "How many days back to look (default 7).",
                                "minimum": 1,
                                "maximum": 730,
                            }
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_calendar_day_context",
                    "description": "Get plan + actual context for a specific calendar day (planned workout + activities with IDs).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "day": {
                                "type": "string",
                                "description": "Calendar date in YYYY-MM-DD.",
                            }
                        },
                        "required": ["day"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_efficiency_trend",
                    "description": "Get efficiency trend data over time (EF time series + summary).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "days": {
                                "type": "integer",
                                "description": "How many days of history to analyze (default 30).",
                                "minimum": 7,
                                "maximum": 365,
                            }
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_plan_week",
                    "description": "Get the current week's planned workouts for the athlete's active plan.",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_training_load",
                    "description": "Get current ATL/CTL/TSB and personalized TSB zone info.",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_correlations",
                    "description": "Get correlations between wellness inputs and efficiency outputs.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "days": {
                                "type": "integer",
                                "description": "How many days of history to analyze (default 30).",
                                "minimum": 14,
                                "maximum": 365,
                            }
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_race_predictions",
                    "description": "Get race time predictions for 5K, 10K, Half Marathon, and Marathon.",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_recovery_status",
                    "description": "Get recovery metrics: half-life, durability index, false fitness and masked fatigue signals.",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_active_insights",
                    "description": "Get prioritized actionable insights for the athlete.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "limit": {
                                "type": "integer",
                                "description": "Max insights to return (default 5, max 10).",
                                "minimum": 1,
                                "maximum": 10,
                            }
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_pb_patterns",
                    "description": "Get training patterns that preceded personal bests, including optimal TSB range.",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_efficiency_by_zone",
                    "description": "Get efficiency trend for specific effort zones (easy, threshold, race).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "effort_zone": {
                                "type": "string",
                                "enum": ["easy", "threshold", "race"],
                                "description": "Effort zone to analyze (default threshold).",
                            },
                            "days": {
                                "type": "integer",
                                "description": "Days of history (default 90, max 365).",
                                "minimum": 30,
                                "maximum": 365,
                            }
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_nutrition_correlations",
                    "description": "Get correlations between pre/post-activity nutrition and performance/recovery.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "days": {
                                "type": "integer",
                                "description": "Days of history (default 90, max 365).",
                                "minimum": 30,
                                "maximum": 365,
                            }
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_weekly_volume",
                    "description": "Weekly rollups of run volume (distance/time/count) for the last N weeks.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "weeks": {
                                "type": "integer",
                                "description": "How many weeks back (default 12, max 104).",
                                "minimum": 1,
                                "maximum": 104,
                            }
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_best_runs",
                    "description": "Get best runs by an explicit metric (efficiency, pace, distance, intensity_score), optionally filtered to an effort zone.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "days": {"type": "integer", "description": "History window (default 365, max 730).", "minimum": 7, "maximum": 730},
                            "metric": {
                                "type": "string",
                                "description": "Ranking metric.",
                                "enum": ["efficiency", "pace", "distance", "intensity_score"],
                            },
                            "limit": {"type": "integer", "description": "Max results (default 5, max 10).", "minimum": 1, "maximum": 10},
                            "effort_zone": {
                                "type": "string",
                                "description": "Optional effort zone filter based on athlete max HR.",
                                "enum": ["easy", "threshold", "race"],
                            },
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "compare_training_periods",
                    "description": "Compare last N days vs the previous N days (volume/run count deltas).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "days": {"type": "integer", "description": "Days per period (default 28, max 180).", "minimum": 7, "maximum": 180}
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_coach_intent_snapshot",
                    "description": "Get the athlete's current self-guided intent snapshot (goals/constraints) with staleness indicator.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "ttl_days": {"type": "integer", "description": "How long the snapshot is considered fresh (default 7).", "minimum": 1, "maximum": 30}
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "set_coach_intent_snapshot",
                    "description": "Update the athlete's self-guided intent snapshot (athlete-led) to avoid repetitive questioning.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "training_intent": {"type": "string", "description": "Athlete intent: through_fatigue | build_fitness | freshen_for_event (free text accepted)."},
                            "next_event_date": {"type": "string", "description": "Optional YYYY-MM-DD for race/benchmark."},
                            "next_event_type": {"type": "string", "description": "Optional: race | benchmark | other."},
                            "pain_flag": {"type": "string", "description": "none | niggle | pain."},
                            "time_available_min": {"type": "integer", "description": "Typical time available (minutes).", "minimum": 0, "maximum": 300},
                            "weekly_mileage_target": {"type": "number", "description": "Athlete-stated target miles/week for current period.", "minimum": 0, "maximum": 250},
                            "what_feels_off": {"type": "string", "description": "Optional: legs | lungs | motivation | life_stress | other."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_training_prescription_window",
                    "description": "Deterministically prescribe training for 1-7 days (exact distances/paces/structure) using athlete history + intent snapshot.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "start_date": {"type": "string", "description": "Start date YYYY-MM-DD (default today)."},
                            "days": {"type": "integer", "description": "How many days (1-7).", "minimum": 1, "maximum": 7},
                            "time_available_min": {"type": "integer", "description": "Optional time cap for workouts (minutes).", "minimum": 0, "maximum": 300},
                            "weekly_mileage_target": {"type": "number", "description": "Optional athlete target miles/week (overrides derived).", "minimum": 0, "maximum": 250},
                            "facilities": {"type": "array", "items": {"type": "string"}, "description": "Optional facilities: road/treadmill/track/hills."},
                            "pain_flag": {"type": "string", "description": "none | niggle | pain (overrides snapshot)."},
                        },
                        "required": [],
                    },
                },
            },
        ]
    
    def _get_or_create_assistant(self) -> Optional[str]:
        """Get existing assistant or create a new one."""
        if not self.client:
            return None
        
        try:
            # Try to find existing assistant by name
            assistants = self.client.beta.assistants.list(limit=20)
            for assistant in assistants.data:
                if assistant.name == "StrideIQ Coach":
                    logger.info(f"Using existing assistant: {assistant.id}")
                    # Ensure tool definitions are up to date (idempotent).
                    try:
                        self.client.beta.assistants.update(
                            assistant_id=assistant.id,
                            instructions=self.SYSTEM_INSTRUCTIONS
                            + "\n\n## Tool Use Policy\n"
                            + "- You MUST use the provided tools for athlete data.\n"
                            + "- Do NOT invent metrics. If unavailable, say so.\n"
                            + "- When you cite numbers (dates, distances, EF, CTL/ATL/TSB), they must come from tool outputs.\n",
                            tools=self._assistant_tools(),
                        )
                    except Exception as e:
                        logger.warning(f"Failed to update assistant tools/instructions: {e}")
                    return assistant.id
            
            # Create new assistant
            assistant = self.client.beta.assistants.create(
                name="StrideIQ Coach",
                instructions=self.SYSTEM_INSTRUCTIONS
                + "\n\n## Tool Use Policy\n"
                + "- You MUST use the provided tools for athlete data.\n"
                + "- Do NOT invent metrics. If unavailable, say so.\n"
                + "- When you cite numbers (dates, distances, EF, CTL/ATL/TSB), they must come from tool outputs.\n",
                model="gpt-4o",  # or "gpt-4-turbo-preview" for cost savings
                tools=self._assistant_tools(),
            )
            logger.info(f"Created new assistant: {assistant.id}")
            return assistant.id
            
        except Exception as e:
            logger.error(f"Failed to get/create assistant: {e}")
            return None
    
    def get_or_create_thread(self, athlete_id: UUID) -> Optional[str]:
        """
        Get or create a conversation thread for an athlete.
        
        Thread IDs are persisted on the Athlete record so conversation
        context survives across requests and page refreshes.
        """
        thread_id, _created = self.get_or_create_thread_with_state(athlete_id)
        return thread_id

    def get_or_create_thread_with_state(self, athlete_id: UUID) -> Tuple[Optional[str], bool]:
        """
        Get or create a conversation thread for an athlete.

        Returns:
            (thread_id, created_new)
        """
        if not self.client:
            return None, False

        athlete = self.db.query(Athlete).filter(Athlete.id == athlete_id).first()
        if not athlete:
            return None, False

        if athlete.coach_thread_id:
            return athlete.coach_thread_id, False

        try:
            thread = self.client.beta.threads.create()
            athlete.coach_thread_id = thread.id
            self.db.add(athlete)
            self.db.commit()
            return thread.id, True
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to create/persist thread: {e}")
            return None, False

    def get_thread_history(self, athlete_id: UUID, limit: int = 50) -> Dict[str, Any]:
        """
        Fetch persisted coach thread messages for this athlete.

        Returns:
            {"thread_id": str|None, "messages": [{"role","content","created_at"}]}
        """
        limit = max(1, min(int(limit), 200))

        athlete = self.db.query(Athlete).filter(Athlete.id == athlete_id).first()
        thread_id = athlete.coach_thread_id if athlete else None
        if not self.client or not thread_id:
            return {"thread_id": thread_id, "messages": []}

        try:
            msgs = self.client.beta.threads.messages.list(thread_id=thread_id, order="desc", limit=limit)
            out: List[Dict[str, Any]] = []
            for m in msgs.data or []:
                # Assistants API message content can be multiple parts; we take the first text part.
                content_text = ""
                try:
                    if m.content and hasattr(m.content[0], "text"):
                        content_text = m.content[0].text.value
                    else:
                        content_text = str(m.content[0]) if m.content else ""
                except Exception:
                    content_text = ""

                # Production-beta: hide internal context injections from UI/history.
                if (content_text or "").startswith("INTERNAL COACH CONTEXT"):
                    continue

                created_at = None
                try:
                    # created_at is unix seconds
                    if getattr(m, "created_at", None):
                        created_at = datetime.utcfromtimestamp(int(m.created_at)).replace(microsecond=0).isoformat()
                except Exception:
                    created_at = None

                out.append(
                    {
                        "role": getattr(m, "role", None) or "assistant",
                        "content": content_text,
                        "created_at": created_at,
                    }
                )

            out.reverse()  # chronological
            return {"thread_id": thread_id, "messages": out}
        except Exception as e:
            logger.warning(f"Failed to read coach thread history: {e}")
            return {"thread_id": thread_id, "messages": []}
    
    def build_context(self, athlete_id: UUID, window_days: int = 30) -> str:
        """
        Build context from athlete's data for injection into conversation.
        
        Context tiers:
        - 7 days: Detailed daily data
        - 30 days: Weekly summaries
        - 120+ days: Phase/block summaries
        """
        athlete = self.db.query(Athlete).filter(Athlete.id == athlete_id).first()
        if not athlete:
            return "No athlete data available."
        
        context_parts = []
        today = date.today()
        
        # --- Athlete Profile ---
        context_parts.append("## Athlete Profile")
        if athlete.display_name:
            context_parts.append(f"Name: {athlete.display_name}")
        if athlete.birthdate:
            age = (today - athlete.birthdate).days // 365
            context_parts.append(f"Age: {age}")
        if athlete.vdot:
            context_parts.append(f"Current VDOT: {athlete.vdot:.1f}")
        if athlete.resting_hr:
            context_parts.append(f"Resting HR: {athlete.resting_hr} bpm")
        if athlete.max_hr:
            context_parts.append(f"Max HR: {athlete.max_hr} bpm")
        
        # --- Personal Bests ---
        pbs = self.db.query(PersonalBest).filter(
            PersonalBest.athlete_id == athlete_id
        ).order_by(PersonalBest.achieved_at.desc()).limit(5).all()
        
        if pbs:
            context_parts.append("\n## Personal Bests")
            for pb in pbs:
                time_str = self._format_time(pb.time_seconds)
                achieved = pb.achieved_at.strftime("%b %d, %Y")
                context_parts.append(f"- {pb.distance_category}: {time_str} ({achieved})")
        
        # --- Current Training Plan ---
        plan = self.db.query(TrainingPlan).filter(
            TrainingPlan.athlete_id == athlete_id,
            TrainingPlan.status == "active"
        ).first()
        
        if plan:
            context_parts.append("\n## Current Training Plan")
            context_parts.append(f"Goal: {plan.goal_race_name}")
            context_parts.append(f"Race Date: {plan.goal_race_date}")
            context_parts.append(f"Week: {self._get_plan_week(plan)} of {plan.total_weeks}")
            
            # This week's workouts
            week_start = today - timedelta(days=today.weekday())
            week_end = week_start + timedelta(days=6)
            
            workouts = self.db.query(PlannedWorkout).filter(
                PlannedWorkout.plan_id == plan.id,
                PlannedWorkout.scheduled_date >= week_start,
                PlannedWorkout.scheduled_date <= week_end
            ).order_by(PlannedWorkout.scheduled_date).all()
            
            if workouts:
                context_parts.append("\nThis week's plan:")
                for w in workouts:
                    status = "✓" if w.completed else "○"
                    context_parts.append(f"  {status} {w.scheduled_date.strftime('%a')}: {w.title}")
        
        # --- Recent Activity Summary (7 days) ---
        seven_days_ago = today - timedelta(days=7)
        recent_activities = self.db.query(Activity).filter(
            Activity.athlete_id == athlete_id,
            Activity.start_time >= datetime.combine(seven_days_ago, datetime.min.time()),
            Activity.sport == 'run'
        ).order_by(Activity.start_time.desc()).all()
        
        if recent_activities:
            context_parts.append("\n## Last 7 Days")
            total_distance = sum(a.distance_m or 0 for a in recent_activities) / 1000
            total_time = sum(a.duration_s or 0 for a in recent_activities) / 60
            context_parts.append(f"Runs: {len(recent_activities)} | Distance: {total_distance:.1f} km | Time: {total_time:.0f} min")
            
            for a in recent_activities[:5]:  # Show last 5
                distance_km = (a.distance_m or 0) / 1000
                pace = self._format_pace(a.duration_s, a.distance_m) if a.distance_m else "N/A"
                hr = f"{a.avg_hr} bpm" if a.avg_hr else ""
                context_parts.append(f"  - {a.start_time.strftime('%a %m/%d')}: {distance_km:.1f} km @ {pace} {hr}")
        
        # --- 30-Day Summary ---
        thirty_days_ago = today - timedelta(days=30)
        month_activities = self.db.query(Activity).filter(
            Activity.athlete_id == athlete_id,
            Activity.start_time >= datetime.combine(thirty_days_ago, datetime.min.time()),
            Activity.sport == 'run'
        ).all()
        
        if month_activities:
            context_parts.append("\n## Last 30 Days")
            total_distance = sum(a.distance_m or 0 for a in month_activities) / 1000
            avg_weekly = total_distance / 4.3  # ~4.3 weeks
            run_count = len(month_activities)
            
            # Calculate average efficiency
            efficiencies = []
            for a in month_activities:
                if a.avg_hr and a.distance_m and a.duration_s:
                    pace_km = a.duration_s / (a.distance_m / 1000)
                    efficiency = pace_km / a.avg_hr  # Lower is better
                    efficiencies.append(efficiency)
            
            context_parts.append(f"Runs: {run_count} | Distance: {total_distance:.0f} km | Avg/week: {avg_weekly:.0f} km")
            
            if efficiencies:
                avg_eff = sum(efficiencies) / len(efficiencies)
                context_parts.append(f"Average efficiency: {avg_eff:.3f} (pace/HR ratio - lower is better)")
        
        # --- Recent Check-ins ---
        recent_checkins = self.db.query(DailyCheckin).filter(
            DailyCheckin.athlete_id == athlete_id,
            DailyCheckin.date >= seven_days_ago
        ).order_by(DailyCheckin.date.desc()).limit(3).all()
        
        if recent_checkins:
            context_parts.append("\n## Recent Wellness")
            for c in recent_checkins:
                parts = []
                if c.sleep_h:
                    parts.append(f"Sleep: {c.sleep_h}h")
                if c.stress_1_5:
                    parts.append(f"Stress: {c.stress_1_5}/5")
                if c.soreness_1_5:
                    parts.append(f"Soreness: {c.soreness_1_5}/5")
                if parts:
                    context_parts.append(f"  {c.date.strftime('%m/%d')}: {' | '.join(parts)}")
        
        return "\n".join(context_parts)
    
    def _format_time(self, seconds: int) -> str:
        """Format seconds as H:MM:SS or M:SS."""
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        
        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        return f"{minutes}:{secs:02d}"
    
    def _format_pace(self, duration_s: Optional[int], distance_m: Optional[int]) -> str:
        """Format pace as M:SS/km."""
        if not duration_s or not distance_m or distance_m == 0:
            return "N/A"
        
        pace_per_km = duration_s / (distance_m / 1000)
        minutes = int(pace_per_km // 60)
        seconds = int(pace_per_km % 60)
        return f"{minutes}:{seconds:02d}/km"
    
    def _get_plan_week(self, plan: TrainingPlan) -> int:
        """Calculate current week of the plan."""
        today = date.today()
        if today < plan.plan_start_date:
            return 0
        if today > plan.plan_end_date:
            return plan.total_weeks + 1
        
        days_in = (today - plan.plan_start_date).days
        return (days_in // 7) + 1

    def get_dynamic_suggestions(self, athlete_id: UUID) -> List[str]:
        """
        Return 3-5 data-driven suggested questions.
        
        Sources:
        - coach_tools.get_active_insights (prioritized insights)
        - coach_tools.get_pb_patterns (recent PBs)
        - coach_tools.get_training_load (TSB state)
        - coach_tools.get_efficiency_by_zone (efficiency trends)
        """
        suggestions: List[str] = []

        def add(q: str) -> None:
            if q and q not in suggestions and len(suggestions) < 5:
                suggestions.append(q)

        today = date.today()

        # --- 1. Insights from coach_tools.get_active_insights ---
        try:
            result = coach_tools.get_active_insights(self.db, athlete_id, limit=3)
            if result.get("ok"):
                for ins in result.get("data", {}).get("insights", []):
                    q = self._insight_to_question(ins)
                    if q:
                        add(q)
        except Exception:
            pass

        # --- 2. PB-driven suggestions ---
        try:
            result = coach_tools.get_pb_patterns(self.db, athlete_id)
            if result.get("ok"):
                data = result.get("data") or {}
                pb_count = data.get("pb_count", 0)
                tsb_min = data.get("tsb_min")
                tsb_max = data.get("tsb_max")
                pbs = data.get("pbs", [])
                
                if pb_count >= 2 and tsb_min is not None and tsb_max is not None:
                    add(
                        f"Analyze what led to my {pb_count} PRs. Cite each PR date + distance + TSB day-before (from get_pb_patterns)."
                    )
                
                # Add specific extreme TSB suggestion if there's an outlier
                if pbs:
                    extreme = min(pbs, key=lambda p: p.get("tsb_day_before") or 0)
                    if extreme.get("tsb_day_before") is not None and extreme.get("tsb_day_before") < -30:
                        add(
                            f"Explain my {extreme['category']} PR on {extreme['date']} when TSB was {extreme['tsb_day_before']:.0f}. Cite the PR details and compare to my typical PR TSB range."
                        )
        except Exception:
            pass

        # --- 3. TSB-driven suggestions ---
        try:
            result = coach_tools.get_training_load(self.db, athlete_id)
            if result.get("ok"):
                tsb = result.get("data", {}).get("tsb")
                if tsb is not None:
                    if tsb > 20:
                        add(f"Am I fresh enough for a hard workout? Cite my current ATL/CTL/TSB and explain what that implies for today.")
                    elif tsb < -30:
                        add(f"Am I overreaching? Cite my current ATL/CTL/TSB and give a recovery plan for the next 48 hours.")
                    else:
                        add(f"Summarize my current training load status. Cite current ATL/CTL/TSB and the TSB zone label.")
        except Exception:
            pass

        # --- 4. Efficiency-driven suggestions ---
        try:
            result = coach_tools.get_efficiency_by_zone(self.db, athlete_id, "threshold", 90)
            if result.get("ok"):
                trend = result.get("data", {}).get("recent_trend_pct")
                if trend is not None:
                    if trend < -10:
                        add("Is my threshold efficiency improving? Use get_efficiency_by_zone and cite the current value + trend%, and also cite 2 specific recent runs from get_efficiency_trend.")
                    elif trend > 10:
                        add("My threshold efficiency looks worse. Use get_efficiency_by_zone and get_efficiency_trend to identify 2 concrete examples (date + activity id) showing the change.")
        except Exception:
            pass

        # --- 5. Recent activity suggestions ---
        try:
            start_of_today = datetime.combine(today, datetime.min.time())
            completed_today = (
                self.db.query(Activity)
                .filter(
                    Activity.athlete_id == athlete_id,
                    Activity.sport == "run",
                    Activity.start_time >= start_of_today,
                )
                .first()
            )
            if completed_today:
                distance_km = (completed_today.distance_m or 0) / 1000
                add(f"Review my run from today ({distance_km:.1f} km). Cite the date + run label + distance + pace + avg HR (from get_recent_runs).")
        except Exception:
            pass

        # --- Fallback defaults ---
        if len(suggestions) < 3:
            add("How is my training going overall? Cite at least 2 recent runs (date + run label + distance + pace) and my current ATL/CTL/TSB.")
            add("Am I on track for my goal race? Use get_plan_week and get_training_load and cite specific workouts + current load.")

        return suggestions[:5]

    def _insight_to_question(self, insight: Dict[str, Any]) -> Optional[str]:
        """Convert an insight dict to a question format."""
        title = insight.get("title") or ""
        if not title:
            return None

        title_lower = title.lower()
        if "improving" in title_lower:
            return f"{title} — what's driving this?"
        elif "declining" in title_lower or "drop" in title_lower:
            return f"{title} — should we investigate?"
        elif "pattern" in title_lower:
            return f"{title} — is this intentional?"
        elif "risk" in title_lower or "warning" in title_lower:
            return f"{title} — what should I do?"
        else:
            return f"{title} — tell me more?"

    def classify_query(self, message: str) -> str:
        """
        Classify query to select appropriate model.

        Returns: 'simple' or 'standard'
        """
        message_lower = (message or "").lower()

        # Simple: Direct data lookups (single tool call, minimal reasoning)
        simple_patterns = [
            "what's my tsb", "what is my tsb",
            "what's my ctl", "what is my ctl",
            "what's my atl", "what is my atl",
            "show my plan", "this week's plan",
            "my last run", "recent runs",
            "my race predictions", "predicted times",
            "recovery status", "am i recovering",
        ]
        if any(p in message_lower for p in simple_patterns):
            return "simple"

        # Everything else: Standard
        return "standard"

    def get_model_for_query(self, query_type: str) -> str:
        """Map query type to model."""
        if query_type == "simple":
            return self.MODEL_SIMPLE
        return self.MODEL_STANDARD
    
    async def chat(
        self, 
        athlete_id: UUID, 
        message: str,
        include_context: bool = True
    ) -> Dict[str, Any]:
        """
        Send a message to the AI coach and get a response.
        
        Args:
            athlete_id: The athlete's ID
            message: The user's message
            include_context: Whether to inject context from athlete data
        
        Returns:
            Dict with response text and metadata
        """
        # If OpenAI not available, return a helpful message
        if not self.client or not self.assistant_id:
            return {
                "response": "AI Coach is not configured. Please set OPENAI_API_KEY in your environment.",
                "error": True
            }

        # Persist units preference if the athlete explicitly requests it.
        self._maybe_update_units_preference(athlete_id, message)

        # Persist athlete-led intent/constraints if they answered them.
        # This supports self-guided coaching (collaborative, not imposed).
        self._maybe_update_intent_snapshot(athlete_id, message)

        lower = (message or "").lower()

        # Thin-history detection + baseline intake (production-beta fallback).
        history_thin = False
        history_snapshot: dict = {}
        baseline: Optional[dict] = None
        baseline_needed = False
        used_baseline = False
        try:
            history_thin, history_snapshot, baseline, baseline_needed = self._thin_history_and_baseline_flags(athlete_id)
            used_baseline = bool(history_thin and baseline and (not baseline_needed))
        except Exception:
            history_thin = False
            history_snapshot = {}
            baseline = None
            baseline_needed = False
            used_baseline = False

        # Production-beta: ambiguity hard stop for return-from-injury/break comparisons.
        # Runs BEFORE any deterministic shortcuts so it cannot be bypassed.
        if self._needs_return_scope_clarification(lower):
            thread_id, _ = self.get_or_create_thread_with_state(athlete_id)
            return {
                "response": (
                    "## Answer\n"
                    "I can help, but I need one quick anchor so I don’t mis-scope **“since coming back”**.\n\n"
                    "**When did you return from injury/break?** Even a rough estimate is fine (e.g., “6 weeks ago” or “early December”).\n\n"
                    "While you confirm that, here are **safe adjustments** that don’t depend on the exact date:\n"
                    "- Keep the next 48–72 hours truly easy (talk-test), especially after your current longest-since-return run.\n"
                    "- If you feel “slow,” treat it as a **signal**, not a verdict: check sleep, fueling, and if legs are heavy/sore, reduce volume before touching pace.\n"
                    "- For any “progressive” finishes: cap them at **easy→steady** (not race effort) until we confirm how deep into the comeback you are.\n"
                    "- If you have a long run planned this week: prioritize **time on feet** and finish feeling like you could do 10–15 more minutes.\n\n"
                    "Reply with your return anchor and I’ll:\n"
                    "1) confirm whether today was your longest **since that date** (with evidence), and\n"
                    "2) recommend specific mileage/effort tweaks for your next 7 days.\n"
                ),
                "thread_id": thread_id,
                "error": False,
                "timed_out": False,
                "history_thin": bool(history_thin),
                "used_baseline": bool(used_baseline),
                "baseline_needed": bool(baseline_needed),
                "rebuild_plan_prompt": False,
            }

        # =========================================================================
        # PHASE 1 ROUTING FIX: Judgment questions and clarification gates FIRST
        # =========================================================================
        # These checks MUST run before any deterministic shortcuts to prevent
        # hijacking of opinion/timeline questions by keyword-based routing.
        
        # Gate 1: Judgment/opinion questions → set flag to skip shortcuts
        # These require nuanced reasoning that hardcoded responses can't provide.
        _skip_deterministic_shortcuts = self._is_judgment_question(message)
        
        # Gate 2: Return context + comparison language → force clarification
        # This prevents scope errors like "longest run" defaulting to all-time
        # when the athlete is clearly in a post-injury context.
        # Only applies if NOT a judgment question (judgment questions go to LLM with full context)
        if not _skip_deterministic_shortcuts and self._needs_return_clarification(message, athlete_id):
            thread_id, _ = self.get_or_create_thread_with_state(athlete_id)
            return {
                "response": (
                    "## Clarification Needed\n\n"
                    "I see you're in a **return-from-injury/break** context and asking about comparisons.\n\n"
                    "To give you an accurate answer, I need to know: **When did you return from injury or your last break?**\n\n"
                    "Even roughly is fine (e.g., \"early January\", \"about 6 weeks ago\", \"January 10th\").\n\n"
                    "Once I know that, I'll scope my answer to your post-return period and give you evidence-backed receipts."
                ),
                "thread_id": thread_id,
                "error": False,
                "timed_out": False,
                "history_thin": bool(history_thin),
                "used_baseline": bool(used_baseline),
                "baseline_needed": bool(baseline_needed),
                "rebuild_plan_prompt": False,
            }
        
        # =========================================================================
        # DETERMINISTIC SHORTCUTS (skipped for judgment questions)
        # =========================================================================

        # Deterministic prescriptions (exact sessions) for "today / this week".
        # IMPORTANT: fatigue can trigger a conversation, but never auto-imposes taper.
        if not _skip_deterministic_shortcuts and self._is_prescription_request(message):
            # Load state (N=1 personalized zones) and intent snapshot freshness.
            load = coach_tools.get_training_load(self.db, athlete_id)
            zone = (((load.get("data") or {}).get("tsb_zone") or {}).get("zone") or "").lower()

            snap = coach_tools.get_coach_intent_snapshot(self.db, athlete_id, ttl_days=7)
            snap_data = (snap.get("data") or {}).get("snapshot") or {}
            snap_stale = bool((snap.get("data") or {}).get("is_stale", True))

            # Fatigue-triggered collaboration gate: ask before prescribing if intent is missing/stale.
            if zone in ("overreaching", "overtraining_risk") and (snap_stale or not snap_data.get("training_intent")):
                thread_id, _ = self.get_or_create_thread_with_state(athlete_id)
                return {
                    "response": (
                        "## Answer\n"
                        "Before I prescribe this week, I need one quick check so this stays **athlete-led**.\n\n"
                        "1) Are you deliberately **training through cumulative fatigue**, or are you trying to **freshen up for a race/benchmark** in the next 2–3 weeks?\n"
                        "2) Any pain signals right now (none / niggle / pain)?\n\n"
                        "## Evidence\n"
                        f"- {date.today().isoformat()}: Load state is **{zone.replace('_', ' ')}** for you (from ATL/CTL/TSB zone).\n"
                    ),
                    "thread_id": thread_id,
                    "error": False,
                }

            # Weekly prescriptions need athlete target mileage/time when available.
            start_iso, req_days = self._extract_prescription_window(message)
            if req_days >= 7 and (snap_stale or (snap_data.get("weekly_mileage_target") is None and snap_data.get("time_available_min") is None)):
                thread_id, _ = self.get_or_create_thread_with_state(athlete_id)
                return {
                    "response": (
                        "## Answer\n"
                        "To make this **self-guided** (not imposed), give me one constraint and I’ll generate an exact 7‑day microcycle.\n\n"
                        "Pick one:\n"
                        "- Target weekly mileage (e.g. `45 mpw`), or\n"
                        "- Typical time available per day (e.g. `45 min`).\n\n"
                        "Also: any pain signals (none / niggle / pain)?\n"
                    ),
                    "thread_id": thread_id,
                    "error": False,
                }

            tool_out = coach_tools.get_training_prescription_window(
                self.db,
                athlete_id,
                start_date=start_iso,
                days=req_days,
            )
            thread_id, _ = self.get_or_create_thread_with_state(athlete_id)
            return {
                "response": self._format_prescription_window(tool_out),
                "thread_id": thread_id,
                "error": False if tool_out.get("ok") else True,
            }

        # Deterministic answers for high-risk questions (avoid "reckless" responses).
        if not _skip_deterministic_shortcuts and any(phrase in lower for phrase in ("how far back", "how far can you look", "how far back can you look", "how far back do you go")):
            return {
                "response": (
                    "I can look back **up to ~2 years** (730 days) for run-history queries, and I can cite specific activities (date + activity id).\n\n"
                    "If you want a longest-run or high-volume comparison, I can pull a 365–730 day window and summarize it with receipts."
                ),
                "thread_id": self.get_or_create_thread(athlete_id),
                "error": False,
            }

        # Deterministic: analyze today's completed run (NOT a prescription).
        if not _skip_deterministic_shortcuts and ("run today" in lower or "today's run" in lower or "my run today" in lower or "today felt" in lower) and any(
            k in lower for k in ("what effect", "what did it do", "how did it go", "what impact", "what changed", "did it help")
        ):
            thread_id, _ = self.get_or_create_thread_with_state(athlete_id)
            return {
                "response": self._today_run_effect(athlete_id),
                "thread_id": thread_id,
                "error": False,
            }

        if not _skip_deterministic_shortcuts and (
            (
                ("run today" in lower or "today's run" in lower or "today run" in lower)
                and ("suggest" in lower or "what should" in lower or "any advice" in lower or "tips" in lower)
            ) or (
                # Common follow-ups after a "today" recommendation: user disputes the plan distance.
                ("plan" in lower and ("too short" in lower or "stupid" in lower or "way too short" in lower))
            )
        ):
            # Production-beta reasoning hardening:
            # If the athlete mentions a return-from-injury/break context AND any comparison language
            # (e.g. "longest since coming back", "I feel slow"), do NOT route to the deterministic
            # "today guidance" shortcut. That shortcut is good for pure prescription, but it can
            # bypass ambiguity guardrails and create trust-breaking scope errors.
            if self._has_return_context(lower) and (
                "longest" in lower
                or "furthest" in lower
                or "slow" in lower
                or "fast" in lower
                or "best" in lower
                or "worst" in lower
            ):
                # Fall through to the normal assistant flow (with context injection + ambiguity guardrails).
                pass
            else:
                thread_id, _ = self.get_or_create_thread_with_state(athlete_id)
                return {
                    "response": self._today_run_guidance(athlete_id),
                    "thread_id": thread_id,
                    "error": False,
                }

        # Deterministic "most impactful run" to prevent vague/hallucinated definitions.
        # Guardrail: only run deterministically when the athlete is asking (avoid narrative misfires).
        if not _skip_deterministic_shortcuts and "most impactful" in lower and "run" in lower:
            if "?" in (message or "") or lower.startswith(("what", "which", "how", "show", "tell")):
                days = self._extract_days_lookback(lower) or 7
                thread_id, _ = self.get_or_create_thread_with_state(athlete_id)
                return {
                    "response": self._most_impactful_run(athlete_id, days=days),
                    "thread_id": thread_id,
                    "error": False,
                }

        # Deterministic "longest run" (common high-signal question).
        if not _skip_deterministic_shortcuts and ("longest" in lower or "furthest" in lower) and "run" in lower:
            # Production-beta hardening:
            # Only answer this deterministically when it looks like an explicit QUESTION.
            # Otherwise, this can misfire on narrative messages like "That was my longest since coming back"
            # and create a trust-breaking scope error (e.g., defaulting to 365-day maxima).
            if self._looks_like_direct_comparison_question(message, keyword="longest", noun="run"):
                # If the athlete is in a return-from-injury / return-from-break context, do not assume window.
                if self._has_return_context(lower) or self._thread_mentions_return_context(athlete_id):
                    thread_id, _ = self.get_or_create_thread_with_state(athlete_id)
                    return {
                        "response": (
                            "## Answer\n"
                            "I need more context on **“coming back”** to give an accurate answer — can you tell me **when you returned from injury or your last break**?\n\n"
                            "Once you tell me that (even roughly, like “early December” or “about 6 weeks ago”), I’ll confirm your **longest run since then** with receipts.\n"
                        ),
                        "thread_id": thread_id,
                        "error": False,
                    }

                days = self._extract_days_lookback(lower) or 365
                thread_id, _ = self.get_or_create_thread_with_state(athlete_id)
                return {
                    "response": self._top_run_by(athlete_id, days=days, metric="distance", label="longest"),
                    "thread_id": thread_id,
                    "error": False,
                }

        # Deterministic "hardest run" / "hardest workout" (ambiguous; we define it explicitly).
        if not _skip_deterministic_shortcuts and ("hardest" in lower or "toughest" in lower) and ("run" in lower or "workout" in lower):
            # Same misfire class as "longest": only do deterministic comparisons when asked.
            if self._looks_like_direct_comparison_question(message, keyword="hardest", noun="run"):
                # If the athlete is in a return-from-break context, "hardest" can be ambiguous (relative to return block).
                if self._has_return_context(lower) or self._thread_mentions_return_context(athlete_id):
                    thread_id, _ = self.get_or_create_thread_with_state(athlete_id)
                    return {
                        "response": (
                            "## Answer\n"
                            "When you say **“hardest”** in a return-from-break context, I don’t want to guess the scope.\n\n"
                            "Do you mean **hardest since coming back**, or hardest in the last **30 days** / **year**?\n"
                        ),
                        "thread_id": thread_id,
                        "error": False,
                    }

                days = self._extract_days_lookback(lower) or 30
                thread_id, _ = self.get_or_create_thread_with_state(athlete_id)
                return {
                    "response": self._top_run_by(athlete_id, days=days, metric="stress_proxy", label="hardest"),
                    "thread_id": thread_id,
                    "error": False,
                }

        # Phase 3 acceptance: if the athlete has no run data and asks about fitness trend,
        # respond explicitly with the required phrasing (avoid any implied metrics).
        try:
            if not _skip_deterministic_shortcuts and "getting fitter" in (message or "").lower():
                has_any_run = (
                    self.db.query(Activity.id)
                    .filter(Activity.athlete_id == athlete_id, Activity.sport == "run")
                    .limit(1)
                    .first()
                    is not None
                )
                if not has_any_run:
                    thread_id, _ = self.get_or_create_thread_with_state(athlete_id)
                    return {
                        "response": "I don't have enough data to answer that.",
                        "thread_id": thread_id,
                        "error": False,
                    }
        except Exception:
            # Never block chat on this precheck; fall back to normal flow.
            pass
        
        try:
            # Classify query and get model
            query_type = self.classify_query(message)
            model = self.get_model_for_query(query_type)

            # Log model selection for cost tracking
            logger.info(f"Coach query: type={query_type}, model={model}")

            thread_id, is_new_thread = self.get_or_create_thread_with_state(athlete_id)
            if not thread_id:
                return {
                    "response": "Unable to start coach conversation (thread creation failed).",
                    "error": True,
                }
            
            # New thread kickoff: reinforce bounded-tool policy (no data injection).
            if is_new_thread:
                self.client.beta.threads.messages.create(
                    thread_id=thread_id,
                    role="user",
                    content=(
                        "You are the athlete's coach.\n\n"
                        "IMPORTANT: Use tools for ALL athlete-specific facts (dates, distances, EF, CTL/ATL/TSB, plan details). "
                        "Do not guess or invent metrics. If data is missing, say so.\n\n"
                        "UNITS: Use the athlete's preferred units from tools. If they request miles, respond in miles + min/mi.\n\n"
                        "EVIDENCE REQUIRED: When you state a fact with numbers, cite it explicitly (ISO date + human label + key values). "
                        "Do not dump long UUIDs unless the athlete explicitly asks."
                    ),
                )

            # Production-beta context injection (belt-and-suspenders):
            # The Assistants thread already contains history, but for ambiguous comparison language we
            # inject recent athlete snippets + scope flags right before the new message so it can't be missed.
            try:
                if history_thin:
                    thin_injected = self._build_thin_history_injection(history_snapshot=history_snapshot, baseline=baseline)
                    if thin_injected:
                        self.client.beta.threads.messages.create(
                            thread_id=thread_id,
                            role="user",
                            content=thin_injected,
                        )

                injected = self._build_context_injection_for_message(athlete_id=athlete_id, message=message)
                if injected:
                    self.client.beta.threads.messages.create(
                        thread_id=thread_id,
                        role="user",
                        content=injected,
                    )
            except Exception as e:
                logger.info("Coach context injection skipped: %s", str(e))
            
            # Add the user's message
            self.client.beta.threads.messages.create(
                thread_id=thread_id,
                role="user",
                content=message
            )
            
            # Run the assistant
            run = self.client.beta.threads.runs.create(
                thread_id=thread_id,
                assistant_id=self.assistant_id,
                model=model,  # Override model per query
            )
            
            # Wait for completion (with timeout)
            import time
            max_wait = int(os.getenv("COACH_MAX_WAIT_S") or "120")
            max_wait = max(30, min(max_wait, 240))
            start = time.time()
            
            while True:
                run_status = self.client.beta.threads.runs.retrieve(
                    thread_id=thread_id,
                    run_id=run.id
                )
                
                if run_status.status == "completed":
                    break
                elif run_status.status == "requires_action":
                    required = getattr(run_status, "required_action", None)
                    submit = getattr(required, "submit_tool_outputs", None) if required else None
                    tool_calls = getattr(submit, "tool_calls", None) if submit else None

                    if not tool_calls:
                        return {
                            "response": "AI coach requested tools, but no tool calls were provided.",
                            "error": True,
                        }

                    logger.info(
                        "AI coach requires_action: %s tool call(s) requested",
                        len(tool_calls),
                    )
                    tool_outputs = []
                    for call in tool_calls:
                        try:
                            fn = call.function
                            tool_name = fn.name
                            raw_args = fn.arguments or "{}"
                            args = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
                            logger.info("AI coach tool_call requested: %s args=%s", tool_name, raw_args)

                            if tool_name == "get_recent_runs":
                                output = coach_tools.get_recent_runs(self.db, athlete_id, **args)
                            elif tool_name == "get_calendar_day_context":
                                output = coach_tools.get_calendar_day_context(self.db, athlete_id, **args)
                            elif tool_name == "get_efficiency_trend":
                                output = coach_tools.get_efficiency_trend(self.db, athlete_id, **args)
                            elif tool_name == "get_plan_week":
                                output = coach_tools.get_plan_week(self.db, athlete_id)
                            elif tool_name == "get_training_load":
                                output = coach_tools.get_training_load(self.db, athlete_id)
                            elif tool_name == "get_correlations":
                                output = coach_tools.get_correlations(self.db, athlete_id, **args)
                            elif tool_name == "get_race_predictions":
                                output = coach_tools.get_race_predictions(self.db, athlete_id)
                            elif tool_name == "get_recovery_status":
                                output = coach_tools.get_recovery_status(self.db, athlete_id)
                            elif tool_name == "get_active_insights":
                                output = coach_tools.get_active_insights(self.db, athlete_id, **args)
                            elif tool_name == "get_pb_patterns":
                                output = coach_tools.get_pb_patterns(self.db, athlete_id)
                            elif tool_name == "get_efficiency_by_zone":
                                output = coach_tools.get_efficiency_by_zone(self.db, athlete_id, **args)
                            elif tool_name == "get_nutrition_correlations":
                                output = coach_tools.get_nutrition_correlations(self.db, athlete_id, **args)
                            elif tool_name == "get_weekly_volume":
                                output = coach_tools.get_weekly_volume(self.db, athlete_id, **args)
                            elif tool_name == "get_best_runs":
                                output = coach_tools.get_best_runs(self.db, athlete_id, **args)
                            elif tool_name == "compare_training_periods":
                                output = coach_tools.compare_training_periods(self.db, athlete_id, **args)
                            elif tool_name == "get_coach_intent_snapshot":
                                output = coach_tools.get_coach_intent_snapshot(self.db, athlete_id, **args)
                            elif tool_name == "set_coach_intent_snapshot":
                                output = coach_tools.set_coach_intent_snapshot(self.db, athlete_id, **args)
                            elif tool_name == "get_training_prescription_window":
                                output = coach_tools.get_training_prescription_window(self.db, athlete_id, **args)
                            else:
                                output = {
                                    "ok": False,
                                    "tool": tool_name,
                                    "generated_at": datetime.utcnow().replace(microsecond=0).isoformat(),
                                    "error": f"Unknown tool: {tool_name}",
                                    "data": {},
                                    "evidence": [],
                                }

                            # Log a bounded view of the tool output for verification.
                            try:
                                output_preview = json.dumps(output)[:1200]
                            except Exception:
                                output_preview = str(output)[:1200]
                            logger.info("AI coach tool_call output: %s %s", tool_name, output_preview)

                            tool_outputs.append(
                                {
                                    "tool_call_id": call.id,
                                    "output": json.dumps(output),
                                }
                            )
                        except Exception as e:
                            tool_outputs.append(
                                {
                                    "tool_call_id": call.id,
                                    "output": json.dumps(
                                        {
                                            "ok": False,
                                            "tool": getattr(getattr(call, "function", None), "name", "unknown"),
                                            "generated_at": datetime.utcnow().replace(microsecond=0).isoformat(),
                                            "error": f"Tool execution error: {str(e)}",
                                            "data": {},
                                            "evidence": [],
                                        }
                                    ),
                                }
                            )

                    self.client.beta.threads.runs.submit_tool_outputs(
                        thread_id=thread_id,
                        run_id=run.id,
                        tool_outputs=tool_outputs,
                    )
                elif run_status.status in ["failed", "cancelled", "expired"]:
                    return {
                        "response": f"The AI coach encountered an error: {run_status.status}",
                        "error": True
                    }
                
                if time.time() - start > max_wait:
                    # Best-effort partial: if the assistant has already posted something, return it.
                    partial = ""
                    try:
                        msgs = self.client.beta.threads.messages.list(thread_id=thread_id, order="desc", limit=1)
                        if msgs.data:
                            c = msgs.data[0].content[0]
                            if hasattr(c, "text"):
                                partial = (c.text.value or "").strip()
                            else:
                                partial = str(c).strip()
                    except Exception:
                        partial = ""
                    if partial:
                        partial = (
                            partial.strip()
                            + "\n\n---\n"
                            + "_Thinking took too long — here’s what I have so far. You can retry, or ask again with a smaller scope._"
                        )
                    else:
                        partial = (
                            "Thinking took too long — here’s what I have so far: (no partial output yet).\n\n"
                            "Retry, or ask again with a smaller scope."
                        )
                    return {
                        "response": partial,
                        "thread_id": thread_id,
                        "error": False,
                        "timed_out": True,
                        "history_thin": bool(history_thin),
                        "used_baseline": bool(used_baseline),
                        "baseline_needed": bool(baseline_needed),
                        "rebuild_plan_prompt": False,
                    }
                
                time.sleep(1)
            
            # Get the response
            messages = self.client.beta.threads.messages.list(
                thread_id=thread_id,
                order="desc",
                limit=1
            )
            
            if messages.data:
                response_content = messages.data[0].content[0]
                if hasattr(response_content, 'text'):
                    response_text = response_content.text.value
                else:
                    response_text = str(response_content)

                # Enforce citations contract: if the answer contains numeric claims,
                # it must include receipts (dates and/or activity ids). If not, force a rewrite.
                try:
                    response_text = await self._enforce_citations_contract(
                        thread_id=thread_id,
                        prior_response=response_text,
                        athlete_id=athlete_id,
                        model=model,
                    )
                except Exception as e:
                    # Never fail the whole request; return the original response.
                    logger.warning(f"Citations enforcement failed: {e}")

                # Normalize for UI + trust contract:
                # - prefer "## Evidence" section naming
                # - collapse-friendly output (heading present when applicable)
                # - suppress UUID spam unless explicitly requested
                try:
                    response_text = self._normalize_response_for_ui(
                        user_message=message,
                        assistant_message=response_text,
                    )
                except Exception as e:
                    logger.warning(f"Coach response normalization failed: {e}")

                # "Rebuild plan?" prompt: only when history transitions from thin -> not thin.
                rebuild_plan_prompt = False
                try:
                    snap = self.db.query(CoachIntentSnapshot).filter(CoachIntentSnapshot.athlete_id == athlete_id).first()
                    if not snap:
                        snap = CoachIntentSnapshot(athlete_id=athlete_id)
                        self.db.add(snap)
                        self.db.flush()
                    extra = snap.extra or {}
                    prev_thin = bool(extra.get("history_thin_last_seen", False))
                    if prev_thin and (not history_thin):
                        rebuild_plan_prompt = True
                    extra["history_thin_last_seen"] = bool(history_thin)
                    extra["history_run_count_28d_last_seen"] = int((history_snapshot or {}).get("run_count_28d") or 0)
                    extra["history_last_seen_at"] = datetime.utcnow().isoformat()
                    snap.extra = extra
                    self.db.commit()
                except Exception:
                    try:
                        self.db.rollback()
                    except Exception:
                        pass

                return {
                    "response": response_text,
                    "thread_id": thread_id,
                    "error": False,
                    "timed_out": False,
                    "history_thin": bool(history_thin),
                    "used_baseline": bool(used_baseline),
                    "baseline_needed": bool(baseline_needed),
                    "rebuild_plan_prompt": bool(rebuild_plan_prompt),
                }
            
            return {
                "response": "No response received from AI coach.",
                "error": True
            }
            
        except Exception as e:
            logger.error(f"AI Coach error: {e}")
            return {
                "response": f"An error occurred: {str(e)}",
                "error": True
            }

    def _maybe_update_units_preference(self, athlete_id: UUID, message: str) -> None:
        try:
            ml = (message or "").lower()
            wants_miles = ("miles" in ml) and ("always" in ml or "not kilometers" in ml or "not km" in ml)
            wants_km = ("kilometers" in ml or "km" in ml) and ("always" in ml or "not miles" in ml)

            if not (wants_miles or wants_km):
                return

            athlete = self.db.query(Athlete).filter(Athlete.id == athlete_id).first()
            if not athlete:
                return

            target = "imperial" if wants_miles else "metric"
            if athlete.preferred_units != target:
                athlete.preferred_units = target
                self.db.commit()
        except Exception:
            try:
                self.db.rollback()
            except Exception:
                pass

    def _maybe_update_intent_snapshot(self, athlete_id: UUID, message: str) -> None:
        """
        Best-effort extraction of athlete intent/constraints from free text.

        This supports self-guided coaching without requiring a rigid UI flow:
        when the athlete answers an intent/pain/time question, we persist it.
        """
        try:
            text = (message or "").strip()
            if not text:
                return

            ml = text.lower()
            updates: Dict[str, Any] = {}

            # Intent keywords (athlete-led)
            if any(k in ml for k in ("train through", "through fatigue", "cumulative fatigue", "build fatigue", "stack fatigue")):
                updates["training_intent"] = "through_fatigue"
            elif any(k in ml for k in ("freshen", "taper", "peak", "sharpen", "race soon", "benchmark")):
                updates["training_intent"] = "freshen_for_event"

            # Pain flags
            if "niggle" in ml:
                updates["pain_flag"] = "niggle"
            if "pain" in ml and "no pain" not in ml:
                updates["pain_flag"] = "pain"
            if any(k in ml for k in ("no pain", "pain-free", "pain free")):
                updates["pain_flag"] = "none"

            # Time available (minutes)
            m = re.search(r"\b(\d{2,3})\s*(min|mins|minutes)\b", ml)
            if m:
                try:
                    updates["time_available_min"] = int(m.group(1))
                except Exception:
                    pass

            # Weekly mileage target (mpw)
            m2 = re.search(r"\b(\d{2,3})\s*(mpw|miles per week|mi per week)\b", ml)
            if m2:
                try:
                    updates["weekly_mileage_target"] = float(m2.group(1))
                except Exception:
                    pass

            # Optional event date (YYYY-MM-DD)
            m3 = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", ml)
            if m3:
                updates["next_event_date"] = m3.group(1)
                if "race" in ml:
                    updates["next_event_type"] = "race"
                elif "benchmark" in ml or "time trial" in ml:
                    updates["next_event_type"] = "benchmark"

            if not updates:
                return

            coach_tools.set_coach_intent_snapshot(self.db, athlete_id, **updates)
        except Exception:
            # Never block chat on snapshot parsing.
            try:
                self.db.rollback()
            except Exception:
                pass

    def _is_prescription_request(self, message: str) -> bool:
        ml = (message or "").lower()
        # Keep intentionally narrow to avoid hijacking analytic questions.
        explicit = any(
            k in ml
            for k in (
                "what should i do",
                "what do i do",
                "what should i run",
                "give me a workout",
                "plan my week",
                "this week",
                "next week",
            )
        )
        if explicit:
            return True

        # "today/tomorrow" only counts as a prescription request if paired with an explicit decision verb.
        # IMPORTANT: do NOT treat generic "run today" analysis ("what effect did it have?") as prescription.
        if ("today" in ml or "tomorrow" in ml) and any(k in ml for k in ("what should", "should i", "workout", "do today", "do tomorrow", "prescribe")):
            return True

        return False

    # -------------------------------------------------------------------------
    # PHASE 1 ROUTING FIX: Judgment question detection (routes to LLM, not shortcuts)
    # -------------------------------------------------------------------------
    def _is_judgment_question(self, message: str) -> bool:
        """
        Detect opinion/judgment/timeline questions that MUST go to the LLM.
        
        These questions require nuanced reasoning, not hardcoded shortcuts:
        - "Would it be reasonable to think I'll hit 3:08 by March?"
        - "Do you think I can get back to my old pace?"
        - "Am I on track for my goal?"
        - "Is it realistic to run a marathon in 8 weeks?"
        
        Returns True if this should bypass all deterministic shortcuts.
        """
        ml = (message or "").lower()
        
        # Opinion-seeking patterns (require LLM reasoning)
        opinion_patterns = (
            "would it be reasonable",
            "do you think",
            "what do you think",
            "is it realistic",
            "is it reasonable",
            "am i on track",
            "will i make it",
            "will i be ready",
            "can i make it",
            "can i achieve",
            "can i get back to",
            "can i return to",
            "should i be worried",
            "is it possible",
            "your opinion",
            "your assessment",
            "your thoughts",
            "what's your take",
            "how likely",
            "odds of",
            "chances of",
            "be there in time",
            "ready in time",
            "ready by",
            "fit enough",
            "strong enough",
        )
        
        # Past benchmark references (need comparison to current state)
        benchmark_indicators = (
            "marathon shape",
            "half marathon shape",
            "race shape",
            "pb shape",
            "pr shape",
            "personal best",
            "personal record",
            "was in shape",
            "used to run",
            "used to be",
            "before my injury",
            "before injury",
            "at my peak",
            "at my best",
            "my old pace",
            "my previous",
            "i was running",
            "i ran a",
            "probably much faster",
            "probably faster",
            "shape in december",
            "shape in january",
            "shape in february",
            "shape last year",
            "shape last month",
        )
        
        # Goal/timeline references
        goal_timeline_patterns = (
            "by march",
            "by april",
            "by may",
            "by june",
            "by july",
            "by august",
            "by september",
            "by october",
            "by november",
            "by december",
            "by the race",
            "by the marathon",
            "by race day",
            "for the marathon",
            "for the race",
            "in time for",
            "before the race",
            "before the marathon",
        )
        
        # Check for opinion patterns (strong signal)
        has_opinion = any(p in ml for p in opinion_patterns)
        if has_opinion:
            return True
        
        # Check for benchmark + timeline combination
        has_benchmark = any(p in ml for p in benchmark_indicators)
        has_timeline = any(p in ml for p in goal_timeline_patterns)
        if has_benchmark and has_timeline:
            return True
        
        # Check for benchmark + return context (comparing past to now)
        if has_benchmark and self._has_return_context(ml):
            return True
        
        return False

    def _needs_return_clarification(self, message: str, athlete_id: UUID) -> bool:
        """
        Production-beta guardrail: if return-context is detected AND comparison language,
        force clarification before answering.
        
        Returns True if we should ask "When did you return?" before proceeding.
        """
        ml = (message or "").lower()
        
        # Check if return context is present (current message or recent thread)
        has_return = self._has_return_context(ml) or self._thread_mentions_return_context(athlete_id, limit=15)
        if not has_return:
            return False
        
        # Check for comparison/superlative language
        comparison_words = (
            "longest", "furthest", "fastest", "slowest",
            "best", "worst", "most", "least",
            "hardest", "toughest", "easiest",
            "biggest", "smallest", "highest", "lowest",
            "slow", "fast", "hard", "easy",  # relative comparisons
        )
        has_comparison = any(w in ml for w in comparison_words)
        if not has_comparison:
            return False
        
        # Check if user already provided a return date/timeframe in this message
        # If they did, no need to ask again
        import re
        has_date = bool(re.search(r"\b(january|february|march|april|may|june|july|august|september|october|november|december)\b", ml, re.I))
        has_relative = bool(re.search(r"\b\d{1,3}\s*(day|days|week|weeks|month|months)\s*(ago|back)\b", ml, re.I))
        has_iso_date = bool(re.search(r"\b20\d{2}-\d{2}-\d{2}\b", ml))
        
        if has_date or has_relative or has_iso_date:
            return False
        
        return True

    def _extract_prescription_window(self, message: str) -> Tuple[Optional[str], int]:
        """
        Return (start_date_iso_or_none, days).
        - 'this week'/'next week' => 7 days
        - 'tomorrow' => start tomorrow, 1 day
        - default => today, 1 day
        """
        ml = (message or "").lower()
        if "next week" in ml or "this week" in ml or "plan my week" in ml:
            return (date.today().isoformat(), 7)
        if "tomorrow" in ml:
            return ((date.today() + timedelta(days=1)).isoformat(), 1)
        return (date.today().isoformat(), 1)

    def _format_prescription_window(self, payload: Dict[str, Any]) -> str:
        """
        Convert tool output into a coach-facing, athlete-readable response.
        """
        data = (payload or {}).get("data") or {}
        window = (data.get("window") or {})
        days = window.get("days") or []
        preferred_units = data.get("preferred_units") or "metric"

        lines: List[str] = []
        lines.append("## Answer")

        if not days:
            lines.append("I don't have enough data to answer that.")
            return "\n".join(lines)

        for d in days:
            primary = d.get("primary") or {}
            day_label = d.get("day_of_week") or ""
            date_label = d.get("date") or ""
            title = primary.get("title") or primary.get("name") or "Workout"
            desc = (primary.get("description") or "").strip()

            # Distances: prefer units already aligned by tool descriptions.
            dist_mi = primary.get("target_distance_mi")
            dist_km = primary.get("target_distance_km")
            if preferred_units == "imperial" and isinstance(dist_mi, (int, float)) and dist_mi > 0:
                dist_str = f"{dist_mi:.1f} mi"
            elif preferred_units != "imperial" and isinstance(dist_km, (int, float)) and dist_km > 0:
                dist_str = f"{dist_km:.1f} km"
            elif isinstance(dist_mi, (int, float)) and dist_mi > 0:
                dist_str = f"{dist_mi:.1f} mi"
            else:
                dist_str = None

            headline = f"**{day_label.title()} ({date_label})** — {title}"
            if dist_str:
                headline += f" — {dist_str}"
            lines.append(headline)
            if desc:
                lines.append(f"- {desc}")

            variants = d.get("variants") or []
            if variants:
                lines.append("  - Variants:")
                for v in variants[:3]:
                    lines.append(f"    - {v.get('name')}: {v.get('description')}")

            guardrails = d.get("guardrails") or []
            if guardrails:
                lines.append("  - Guardrails:")
                for g in guardrails[:3]:
                    lines.append(f"    - {g}")

        # Evidence (facts only)
        lines.append("")
        lines.append("## Evidence")
        for e in (payload.get("evidence") or [])[:6]:
            if e.get("date") and e.get("value"):
                lines.append(f"- {e['date']}: {e['value']}")

        return "\n".join(lines)

    def _today_run_guidance(self, athlete_id: UUID) -> str:
        """
        Deterministic run-today guidance:
        - uses plan + recent run history + load
        - uses preferred units
        - includes receipts
        """
        today = date.today().isoformat()
        day_ctx = coach_tools.get_calendar_day_context(self.db, athlete_id, day=today)
        recent_42 = coach_tools.get_recent_runs(self.db, athlete_id, days=42)
        load = coach_tools.get_training_load(self.db, athlete_id)

        units = (day_ctx.get("data", {}) or {}).get("preferred_units") or (recent_42.get("data", {}) or {}).get("preferred_units") or "metric"

        planned = (day_ctx.get("data", {}) or {}).get("planned_workout") or {}
        planned_id = planned.get("planned_workout_id")
        planned_title = planned.get("title")
        planned_phase = (planned.get("phase") or "").lower() if planned.get("phase") else None
        planned_mi = planned.get("target_distance_mi")
        planned_km = planned.get("target_distance_km")

        runs = (recent_42.get("data", {}) or {}).get("runs") or []

        # Compute baseline from recent runs
        distances_mi = [r.get("distance_mi") for r in runs if r.get("distance_mi") is not None]
        max_run_mi = max(distances_mi) if distances_mi else None
        total_14_mi = None
        try:
            recent_14 = coach_tools.get_recent_runs(self.db, athlete_id, days=14)
            total_14_mi = (recent_14.get("data", {}) or {}).get("total_distance_mi")
        except Exception:
            total_14_mi = None

        # Detect plan/history mismatch (very conservative planned distance vs known baseline)
        plan_conflict = False
        if planned_mi is not None and max_run_mi is not None and max_run_mi >= 10 and planned_mi <= (0.5 * max_run_mi):
            plan_conflict = True

        # Build guidance in a conversational format (receipts are expandable in the UI).
        lines: List[str] = []
        lines.append(f"Here’s what I’d do **today ({today})**.")

        if planned_title:
            if units == "imperial" and planned_mi is not None:
                lines.append(f"Your plan has **{planned_mi:.1f} mi easy** ({planned_title}).")
            elif planned_km is not None:
                lines.append(f"Your plan has **{planned_km:.1f} km easy** ({planned_title}).")
            else:
                lines.append(f"Your plan has: {planned_title}.")
        else:
            lines.append("I don’t see a planned workout for today.")

        if plan_conflict:
            lines.append("")
            lines.append(
                "That distance also looks **conservative vs your recent baseline**. If you’re returning from injury, that may be intentional; "
                "if it feels wrong, we should fix the plan logic (not just override it ad‑hoc)."
            )

        if planned_phase and planned_phase.startswith("rebuild"):
            lines.append("")
            lines.append("Context: you’re in **REBUILD** — smooth, controlled, no hero pace.")

        lines.append("")
        lines.append("**My suggestion:**")
        if units == "imperial":
            target = planned_mi if planned_mi is not None else 6.0
            # Offer options (tight/normal/extra) without pretending certainty.
            lines.append(f"- If you want to keep it conservative: **{max(3.0, float(target)):.0f}–{max(4.0, float(target)):.0f} mi easy**.")
            lines.append(f"- If you feel stable and want a bit more: **{max(5.0, float(target)):.0f}–{max(6.0, float(target)):.0f} mi easy**.")
            lines.append("- Optional (only if everything feels good): **4–6 × 20s relaxed strides** with full recovery jog.")
        else:
            target = planned_km if planned_km is not None else 10.0
            lines.append(f"- Conservative: **{max(5.0, float(target)):.0f}–{max(6.0, float(target)):.0f} km easy**.")
            lines.append(f"- If you feel stable: **{max(8.0, float(target)):.0f}–{max(10.0, float(target)):.0f} km easy**.")
            lines.append("- Optional (only if everything feels good): **4–6 × 20s relaxed strides** with full recovery jog.")

        # Load context
        tsb = (load.get("data", {}) or {}).get("tsb")
        atl = (load.get("data", {}) or {}).get("atl")
        ctl = (load.get("data", {}) or {}).get("ctl")
        zone = (load.get("data", {}) or {}).get("tsb_zone_label")
        if tsb is not None and atl is not None and ctl is not None:
            lines.append("")
            if zone:
                lines.append(f"FYI your current load is ATL {atl:.0f}, CTL {ctl:.0f}, TSB {tsb:.0f} ({zone}).")
            else:
                lines.append(f"FYI your current load is ATL {atl:.0f}, CTL {ctl:.0f}, TSB {tsb:.0f}.")

        # Receipts: cite planned workout + a couple of recent runs
        lines.append("")
        lines.append("## Evidence")
        if planned_title:
            if units == "imperial" and planned_mi is not None:
                lines.append(f"- {today}: Planned — {planned_title} ({planned_mi:.1f} mi)")
            elif planned_km is not None:
                lines.append(f"- {today}: Planned — {planned_title} ({planned_km:.1f} km)")
            else:
                lines.append(f"- {today}: Planned — {planned_title}")

        # Use evidence lines already formatted in preferred units (coach_tools does this now).
        ev = recent_42.get("evidence") or []
        for e in ev[:3]:
            if e.get("type") == "activity":
                # Keep receipts human-readable; do not dump UUIDs unless explicitly requested.
                lines.append(f"- {e.get('date')}: {e.get('value')}")
        if tsb is not None and atl is not None and ctl is not None:
            lines.append(f"- {today}: Training load — ATL {atl:.0f}, CTL {ctl:.0f}, TSB {tsb:.0f}")

        return "\n".join(lines)

    def _today_run_effect(self, athlete_id: UUID) -> str:
        """
        Deterministic "what effect did my run today have?" analysis.

        Uses:
        - calendar day context (planned + actual)
        - training load snapshot
        - per-activity estimated TSS for the completed run
        """
        today_iso = date.today().isoformat()
        day_ctx = coach_tools.get_calendar_day_context(self.db, athlete_id, day=today_iso)
        load = coach_tools.get_training_load(self.db, athlete_id)

        units = (day_ctx.get("data", {}) or {}).get("preferred_units") or "metric"
        planned = (day_ctx.get("data", {}) or {}).get("planned_workout") or {}
        acts = (day_ctx.get("data", {}) or {}).get("activities") or []

        lines: List[str] = []
        lines.append("## Answer")

        if not acts:
            if planned.get("title"):
                lines.append(
                    f"I don’t see a completed run logged for **today ({today_iso})** yet. I *do* see a planned workout: **{planned.get('title')}**."
                )
            else:
                lines.append(f"I don’t see a completed run logged for **today ({today_iso})** yet.")
            lines.append("")
            lines.append("## Evidence")
            if planned.get("title"):
                lines.append(f"- {today_iso}: Planned — {planned.get('title')} ({planned.get('workout_type')})")
            tsb = ((load.get("data") or {}).get("tsb"))
            atl = ((load.get("data") or {}).get("atl"))
            ctl = ((load.get("data") or {}).get("ctl"))
            if tsb is not None and atl is not None and ctl is not None:
                lines.append(f"- {today_iso}: Training load — ATL {atl:.0f}, CTL {ctl:.0f}, TSB {tsb:.0f}")
            return "\n".join(lines)

        # Choose the most recent activity (by start_time)
        act = sorted(acts, key=lambda a: a.get("start_time") or "")[-1]
        name = (act.get("name") or "").strip() or "Run"
        avg_hr = act.get("avg_hr")
        pace_km = act.get("pace_per_km")
        pace_mi = act.get("pace_per_mile")
        dist_km = act.get("distance_km")
        dist_mi = act.get("distance_mi")

        if units == "imperial":
            dist_str = f"{dist_mi:.1f} mi" if isinstance(dist_mi, (int, float)) else "distance n/a"
            pace_str = pace_mi or "pace n/a"
        else:
            dist_str = f"{dist_km:.1f} km" if isinstance(dist_km, (int, float)) else "distance n/a"
            pace_str = pace_km or "pace n/a"

        hr_str = f", avg HR {int(avg_hr)} bpm" if avg_hr is not None else ""
        lines.append(f"Today you ran **{name} — {dist_str} @ {pace_str}**{hr_str}.")

        # If plan exists and is materially different, call it out explicitly.
        plan_title = planned.get("title")
        plan_mi = planned.get("target_distance_mi")
        plan_km = planned.get("target_distance_km")
        if plan_title and ((plan_mi is not None and dist_mi is not None and float(dist_mi) >= float(plan_mi) * 1.25) or (plan_km is not None and dist_km is not None and float(dist_km) >= float(plan_km) * 1.25)):
            lines.append("")
            lines.append("## Why")
            if units == "imperial" and plan_mi is not None and dist_mi is not None:
                lines.append(f"Your plan called for **{float(plan_mi):.1f} mi** today, but you ran **{float(dist_mi):.1f} mi**. That implies you’re intentionally overriding the plan (or the plan logic is too conservative for your return-from-injury reality).")
            elif plan_km is not None and dist_km is not None:
                lines.append(f"Your plan called for **{float(plan_km):.1f} km** today, but you ran **{float(dist_km):.1f} km**. That implies you’re intentionally overriding the plan (or the plan logic is too conservative for your return-from-injury reality).")
            else:
                lines.append("Your completed run differs materially from the planned workout, which suggests plan mismatch or deliberate override.")

        # Estimated TSS for this activity (impact proxy).
        tss = None
        try:
            from services.training_load import TrainingLoadCalculator
            from models import Activity

            arow = (
                self.db.query(Activity)
                .filter(Activity.id == UUID(str(act.get("activity_id"))))
                .first()
            )
            if arow:
                athlete = self.db.query(Athlete).filter(Athlete.id == athlete_id).first()
                if athlete:
                    calc = TrainingLoadCalculator(self.db)
                    stress = calc.calculate_workout_tss(arow, athlete)
                    tss = stress.tss
        except Exception:
            tss = None

        lines.append("")
        lines.append("## What to do next")
        if tss is not None:
            lines.append(
                "- That run likely added a **moderate amount of training stress** today — meaning mostly **short‑term fatigue** over the next 24–72 hours."
            )
            lines.append(
                f"- If you want the numeric score (for tracking), it’s about **{tss:.0f}**."
            )
        else:
            lines.append(
                "- That run likely added a **moderate amount of training stress** today — meaning mostly **short‑term fatigue** over the next 24–72 hours."
            )

        lines.append(
            "- Quick intent check (so this stays athlete‑led): are you **training through cumulative fatigue**, or trying to **freshen up** for a race/benchmark in the next 2–3 weeks?"
        )

        lines.append("")
        lines.append("## Evidence")
        lines.append(f"- {today_iso}: Actual — {name} {dist_str} @ {pace_str}{hr_str}")
        if plan_title:
            if units == "imperial" and plan_mi is not None:
                lines.append(f"- {today_iso}: Planned — {plan_title} ({float(plan_mi):.1f} mi)")
            elif plan_km is not None:
                lines.append(f"- {today_iso}: Planned — {plan_title} ({float(plan_km):.1f} km)")
            else:
                lines.append(f"- {today_iso}: Planned — {plan_title}")
        tsb = ((load.get("data") or {}).get("tsb"))
        atl = ((load.get("data") or {}).get("atl"))
        ctl = ((load.get("data") or {}).get("ctl"))
        zone_label = (((load.get("data") or {}).get("tsb_zone") or {}).get("label"))
        if tsb is not None and atl is not None and ctl is not None:
            if zone_label:
                lines.append(f"- {today_iso}: Training load — ATL {atl:.0f}, CTL {ctl:.0f}, TSB {tsb:.0f} ({zone_label})")
            else:
                lines.append(f"- {today_iso}: Training load — ATL {atl:.0f}, CTL {ctl:.0f}, TSB {tsb:.0f}")

        return "\n".join(lines)

    _UUID_RE = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I)
    _DATE_RE = re.compile(r"\b20\d{2}-\d{2}-\d{2}\b")

    def _looks_like_uncited_numeric_answer(self, text: str) -> bool:
        """
        Heuristic gate (refined):
        - We MUST not block prescription, exploration, or hypothesis generation.
        - We DO enforce receipts for athlete-specific factual/causal claims (metrics, trends, correlations),
          because those are trust-breaking when uncited.

        Trigger only when:
        - There are digits AND the answer appears to make athlete-specific factual/causal claims
          (TSB/ATL/CTL/EF/pace/HR/volume/% trends, “last X days”, “you ran”, etc.)
        - AND there are no receipt markers (ISO date / UUID / explicit Receipts/Citations section).
        """
        if not text:
            return False

        lower = text.lower()

        # Only treat explicit headings as satisfying the contract; the word "evidence" may appear in normal prose.
        receipt_section = bool(re.search(r"(^|\n)##\s*(evidence|receipts)\b", lower))
        has_date = bool(self._DATE_RE.search(text))
        has_uuid = bool(self._UUID_RE.search(text))
        if receipt_section or has_date or has_uuid:
            return False

        has_digits = any(ch.isdigit() for ch in text)
        if not has_digits:
            return False

        # Signals that the response is describing athlete-specific facts/metrics rather than prescribing.
        metric_tokens = (
            "tsb",
            "atl",
            "ctl",
            "ef",
            "efficiency",
            "vdot",
            "bpm",
            "avg hr",
            "heart rate",
            "pace",
            "min/mi",
            "min/km",
            "mi",
            "miles",
            "km",
            "kilometer",
            "kilometre",
            "%",
            "percent",
            "pr",
            "pb",
            "personal best",
            "trend",
            "correlat",
        )

        past_context = (
            "you ran" in lower
            or "you did" in lower
            or "you averaged" in lower
            or "in the last" in lower
            or "last " in lower
            or "past " in lower
            or "recent" in lower
            or "since " in lower
            or "this week" in lower
            or "last week" in lower
            or "over the" in lower
        )

        causal_language = (
            "caus" in lower
            or "caused" in lower
            or "drives" in lower
            or "drive " in lower
            or "led to" in lower
            or "because" in lower
            or "resulted" in lower
        )

        looks_like_metric_claim = any(tok in lower for tok in metric_tokens) and (past_context or "your " in lower)
        looks_like_causal_claim = causal_language and any(tok in lower for tok in metric_tokens)

        # If this is pure prescription (“do 2 easy runs”, “run 30 min easy”), do not enforce receipts.
        # We only enforce when it reads like analysis of the athlete’s data.
        return looks_like_metric_claim or looks_like_causal_claim

    async def _enforce_citations_contract(self, *, thread_id: str, prior_response: str, athlete_id: UUID, model: str) -> str:
        """
        If the model returned numeric claims without receipts, force a rewrite in the same thread.
        """
        if not self._looks_like_uncited_numeric_answer(prior_response):
            return prior_response

        # Ask for a rewrite with receipts. This stays inside the same thread so the
        # assistant can reference tool outputs already generated during the run.
        self.client.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=(
                "Rewrite your last answer to comply with the Evidence & Citations rules.\n\n"
                "Rules:\n"
                "- If you include any numbers (distances, times, paces, HR, EF, ATL/CTL/TSB, percentages), you MUST include receipts.\n"
                "- Add a final section titled '## Evidence' listing supporting evidence lines.\n"
                "- Evidence lines must include at least one ISO date (YYYY-MM-DD) and a human label (e.g., run name + key values).\n"
                "- Do NOT dump long UUIDs unless the athlete explicitly asks; keep evidence readable.\n"
                "- Do not add new claims; only restate with proper receipts.\n"
                "- If you cannot cite the data, reply exactly: \"I don't have enough data to answer that.\""
            ),
        )

        run = self.client.beta.threads.runs.create(
            thread_id=thread_id,
            assistant_id=self.assistant_id,
            model=model,
        )

        import time

        max_wait = 45
        start = time.time()
        while True:
            run_status = self.client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run.id)

            if run_status.status == "completed":
                break
            elif run_status.status == "requires_action":
                required = getattr(run_status, "required_action", None)
                submit = getattr(required, "submit_tool_outputs", None) if required else None
                tool_calls = getattr(submit, "tool_calls", None) if submit else None

                if not tool_calls:
                    break

                tool_outputs = []
                for call in tool_calls:
                    try:
                        fn = call.function
                        tool_name = fn.name
                        raw_args = fn.arguments or "{}"
                        args = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})

                        # Tool dispatch (same as main run loop)
                        if tool_name == "get_recent_runs":
                            output = coach_tools.get_recent_runs(self.db, athlete_id, **args)
                        elif tool_name == "get_calendar_day_context":
                            output = coach_tools.get_calendar_day_context(self.db, athlete_id, **args)
                        elif tool_name == "get_efficiency_trend":
                            output = coach_tools.get_efficiency_trend(self.db, athlete_id, **args)
                        elif tool_name == "get_plan_week":
                            output = coach_tools.get_plan_week(self.db, athlete_id)
                        elif tool_name == "get_training_load":
                            output = coach_tools.get_training_load(self.db, athlete_id)
                        elif tool_name == "get_correlations":
                            output = coach_tools.get_correlations(self.db, athlete_id, **args)
                        elif tool_name == "get_race_predictions":
                            output = coach_tools.get_race_predictions(self.db, athlete_id)
                        elif tool_name == "get_recovery_status":
                            output = coach_tools.get_recovery_status(self.db, athlete_id)
                        elif tool_name == "get_active_insights":
                            output = coach_tools.get_active_insights(self.db, athlete_id, **args)
                        elif tool_name == "get_pb_patterns":
                            output = coach_tools.get_pb_patterns(self.db, athlete_id)
                        elif tool_name == "get_efficiency_by_zone":
                            output = coach_tools.get_efficiency_by_zone(self.db, athlete_id, **args)
                        elif tool_name == "get_nutrition_correlations":
                            output = coach_tools.get_nutrition_correlations(self.db, athlete_id, **args)
                        elif tool_name == "get_weekly_volume":
                            output = coach_tools.get_weekly_volume(self.db, athlete_id, **args)
                        elif tool_name == "get_best_runs":
                            output = coach_tools.get_best_runs(self.db, athlete_id, **args)
                        elif tool_name == "compare_training_periods":
                            output = coach_tools.compare_training_periods(self.db, athlete_id, **args)
                        elif tool_name == "get_coach_intent_snapshot":
                            output = coach_tools.get_coach_intent_snapshot(self.db, athlete_id, **args)
                        elif tool_name == "set_coach_intent_snapshot":
                            output = coach_tools.set_coach_intent_snapshot(self.db, athlete_id, **args)
                        elif tool_name == "get_training_prescription_window":
                            output = coach_tools.get_training_prescription_window(self.db, athlete_id, **args)
                        else:
                            output = {
                                "ok": False,
                                "tool": tool_name,
                                "generated_at": datetime.utcnow().replace(microsecond=0).isoformat(),
                                "error": f"Unknown tool: {tool_name}",
                                "data": {},
                                "evidence": [],
                            }

                        tool_outputs.append({"tool_call_id": call.id, "output": json.dumps(output)})
                    except Exception as e:
                        tool_outputs.append(
                            {
                                "tool_call_id": call.id,
                                "output": json.dumps(
                                    {
                                        "ok": False,
                                        "tool": getattr(getattr(call, "function", None), "name", "unknown"),
                                        "generated_at": datetime.utcnow().replace(microsecond=0).isoformat(),
                                        "error": f"Tool execution error: {str(e)}",
                                        "data": {},
                                        "evidence": [],
                                    }
                                ),
                            }
                        )

                self.client.beta.threads.runs.submit_tool_outputs(thread_id=thread_id, run_id=run.id, tool_outputs=tool_outputs)
            elif run_status.status in ["failed", "cancelled", "expired"]:
                break

            if time.time() - start > max_wait:
                break
            time.sleep(1)

        # Pull the latest assistant message after the rewrite attempt.
        rewritten = self.client.beta.threads.messages.list(thread_id=thread_id, order="desc", limit=1)
        if rewritten.data:
            content = rewritten.data[0].content[0]
            if hasattr(content, "text"):
                candidate = content.text.value
            else:
                candidate = str(content)

            # Only accept the rewrite if it now has receipts (or is the explicit "not enough data").
            if candidate.strip() == "I don't have enough data to answer that.":
                return candidate
            if not self._looks_like_uncited_numeric_answer(candidate):
                return candidate

        # If rewrite failed, return a safe refusal instead of uncited numbers.
        return "I don't have enough data to answer that."

    def _extract_days_lookback(self, lower_message: str) -> Optional[int]:
        """
        Best-effort extraction of a lookback window from natural language like:
          - "last 7 days"
          - "past 14 days"
          - "in the last 30"
        """
        try:
            m = re.search(r"(last|past|previous)\s+(\d{1,3})\s*(day|days|d)\b", lower_message)
            if not m:
                m = re.search(r"\b(\d{1,3})\s*(day|days|d)\b", lower_message)
            if not m:
                return None
            days = int(m.group(2) if m.lastindex and m.lastindex >= 2 else m.group(1))
            if days < 1:
                return None
            return max(1, min(days, 730))
        except Exception:
            return None

    # -------------------------------------------------------------------------
    # PHASE 1 ROUTING FIX: Expanded return-context phrases (ADR-compliant)
    # -------------------------------------------------------------------------
    _RETURN_CONTEXT_PHRASES = (
        # Original phrases
        "since coming back",
        "since i came back",
        "since coming back from",
        "coming back from",
        "back from injury",
        "after injury",
        "after my injury",
        "since injury",
        "since my injury",
        "after a break",
        "after my break",
        "after time off",
        "since a break",
        "since my break",
        "since time off",
        "since returning",
        "since i returned",
        "recently returned",
        "returning from injury",
        "returning from a break",
        # Phase 1 additions - expanded coverage
        "post-injury",
        "post injury",
        "post-break",
        "post break",
        "recovery phase",
        "in recovery",
        "since i started running again",
        "since starting again",
        "first week back",
        "first run back",
        "first time back",
        "just started back",
        "just came back",
        "just got back",
        "getting back into",
        "easing back into",
        "building back",
        "ramping back up",
        "after surgery",
        "after my surgery",
        "since surgery",
        "after rehab",
        "since rehab",
        "after physical therapy",
        "since pt",
        "after being injured",
        "after being sick",
        "after illness",
        "since being sick",
    )

    def _has_return_context(self, lower_message: str) -> bool:
        ml = (lower_message or "").lower()
        return any(p in ml for p in self._RETURN_CONTEXT_PHRASES)

    def _thread_mentions_return_context(self, athlete_id: UUID, limit: int = 10) -> bool:
        """
        Conversation context awareness (production beta):
        If the athlete has been talking about injury/return/break recently, we must not
        interpret superlatives as all-time maxima without clarifying.
        """
        try:
            hist = self.get_thread_history(athlete_id, limit=limit) or {}
            msgs = hist.get("messages") or []
            for m in msgs:
                if (m.get("role") or "").lower() != "user":
                    continue
                content = (m.get("content") or "").lower()
                if self._has_return_context(content):
                    return True
            return False
        except Exception:
            return False

    def _looks_like_direct_comparison_question(self, message: str, *, keyword: str, noun: str) -> bool:
        """
        Guardrail: only run deterministic comparison answers when the athlete is asking.
        Avoid misfiring on narrative statements like "That was my longest since coming back".
        """
        text = (message or "").strip()
        lower = text.lower()
        if not text:
            return False

        # Strong signal: question mark / interrogative starters.
        if "?" in text:
            return True
        if lower.startswith(("what", "which", "how", "show", "tell", "did", "was", "is")):
            return True

        # Explicit ask patterns.
        stems = (
            f"my {keyword} {noun}",
            f"what's my {keyword} {noun}",
            f"what is my {keyword} {noun}",
            f"which {noun} was my {keyword}",
            f"when was my {keyword} {noun}",
            f"find my {keyword} {noun}",
        )
        if any(s in lower for s in stems):
            # But still avoid declaratives like "my longest run was today".
            if any(k in lower for k in (" was ", " today", " this morning", " yesterday")) and not lower.startswith(
                ("what", "which", "how", "show", "tell")
            ):
                return False
            return True

        return False

    _COMPARISON_KEYWORDS = (
        "longest",
        "furthest",
        "fastest",
        "slowest",
        "best",
        "worst",
        "most",
        "least",
        "hardest",
        "toughest",
        "easiest",
        "biggest",
        "smallest",
    )

    def _build_context_injection_for_message(self, *, athlete_id: UUID, message: str) -> Optional[str]:
        """
        Inject a compact, high-signal “recent context + scope flags” preamble.

        Goal:
        - Improve conversation-context awareness for ambiguous comparisons (production beta).
        - Avoid dumping full history or sensitive data; keep it short and actionable.
        - Encourage the assistant to ask clarifying questions instead of assuming.
        """
        text = (message or "").strip()
        if not text:
            return None

        # Pull last N user messages (best-effort). Keep this small to reduce latency/token pressure.
        prior_user_messages: List[str] = []
        try:
            hist = self.get_thread_history(athlete_id, limit=10) or {}
            msgs = hist.get("messages") or []
            for m in msgs:
                if (m.get("role") or "").lower() != "user":
                    continue
                c = (m.get("content") or "").strip()
                if not c:
                    continue
                prior_user_messages.append(c)
        except Exception:
            prior_user_messages = []

        return self._build_context_injection_pure(message=text, prior_user_messages=prior_user_messages)

    def _thin_history_and_baseline_flags(self, athlete_id: UUID) -> Tuple[bool, dict, Optional[dict], bool]:
        """
        Returns:
        - history_thin: bool
        - history_snapshot: dict (safe summary)
        - baseline: dict|None (self-reported baseline intake)
        - baseline_needed: bool (thin history AND missing baseline)
        """
        from datetime import datetime, timedelta, timezone

        now = datetime.now(timezone.utc)
        cutoff_28d = now - timedelta(days=28)
        cutoff_14d = now - timedelta(days=14)

        runs = (
            self.db.query(Activity)
            .filter(Activity.athlete_id == athlete_id, Activity.sport.ilike("run"), Activity.start_time >= cutoff_28d)
            .order_by(Activity.start_time.desc())
            .all()
        )
        run_count_28d = len(runs)
        total_distance_m_28d = sum(int(r.distance_m or 0) for r in runs if r.distance_m)
        last_run_at = runs[0].start_time if runs else None

        reasons: list[str] = []
        if run_count_28d < 6:
            reasons.append("low_run_count_28d")
        if total_distance_m_28d < int(1609.344 * 10):
            reasons.append("low_volume_28d")
        if (last_run_at is None) or (last_run_at < cutoff_14d):
            reasons.append("no_recent_run_14d")

        history_thin = bool(reasons)
        history_snapshot = {
            "run_count_28d": int(run_count_28d),
            "total_distance_m_28d": int(total_distance_m_28d),
            "last_run_at": last_run_at.isoformat() if last_run_at else None,
            "reasons": reasons,
        }

        baseline_row = (
            self.db.query(IntakeQuestionnaire)
            .filter(IntakeQuestionnaire.athlete_id == athlete_id, IntakeQuestionnaire.stage == "baseline")
            .order_by(IntakeQuestionnaire.created_at.desc())
            .first()
        )
        baseline = baseline_row.responses if (baseline_row and isinstance(baseline_row.responses, dict)) else None
        baseline_completed = bool(baseline_row and baseline_row.completed_at)
        baseline_needed = bool(history_thin and (not baseline_completed))
        return history_thin, history_snapshot, baseline, baseline_needed

    def _build_thin_history_injection(self, *, history_snapshot: dict, baseline: Optional[dict]) -> str:
        """
        Build an INTERNAL COACH CONTEXT message for thin-history situations.
        """
        lines: List[str] = []
        lines.append("INTERNAL COACH CONTEXT (do not repeat verbatim):")
        lines.append(f"- Training data coverage is THIN. Snapshot: {json.dumps(history_snapshot, separators=(',', ':'))}")
        if baseline:
            # Keep payload minimal; avoid PII.
            allow = {
                "runs_per_week_4w": baseline.get("runs_per_week_4w"),
                "weekly_volume_value": baseline.get("weekly_volume_value"),
                "weekly_volume_unit": baseline.get("weekly_volume_unit"),
                "longest_run_last_month": baseline.get("longest_run_last_month"),
                "longest_run_unit": baseline.get("longest_run_unit"),
                "returning_from_break": baseline.get("returning_from_break"),
                "return_date_approx": baseline.get("return_date_approx"),
            }
            lines.append(f"- Athlete self-reported baseline (use until data is connected): {json.dumps(allow, separators=(',', ':'))}")
            lines.append('- Include a short banner line in your answer: "Using your answers for now — connect Strava/Garmin for better insights."')
            lines.append("- Conservative mode: ramp recommendations <= ~20% week-over-week; ask about pain signals before hard sessions.")
        else:
            lines.append("- Baseline intake is missing. Ask the athlete to provide: runs/week (last 4 weeks), typical weekly miles/minutes, longest run last month, and whether they are returning from a break/injury (rough date).")
        return "\n".join(lines).strip()

    def _build_context_injection_pure(self, *, message: str, prior_user_messages: List[str]) -> Optional[str]:
        """
        PURE context builder (unit-testable):
        input message + prior user messages → injected context string (or None).
        """
        text = (message or "").strip()
        if not text:
            return None

        lower = text.lower()
        mentions_comparison = any(k in lower for k in self._COMPARISON_KEYWORDS)
        return_ctx = self._has_return_context(lower) or any(self._has_return_context((m or "").lower()) for m in (prior_user_messages or []))

        # Only inject when it matters (avoid spamming every message).
        if not (mentions_comparison or return_ctx):
            return None

        # Build bounded snippets from prior messages (most recent first if provided that way).
        snippets: List[str] = []
        for raw in (prior_user_messages or []):
            c = (raw or "").strip()
            if not c:
                continue
            if c.strip() == text:
                continue
            c = c.replace("\n", " ").strip()
            if len(c) > 160:
                c = c[:157].rstrip() + "…"
            snippets.append(c)
            if len(snippets) >= 8:
                break

        flags = {
            "return_context_detected": bool(return_ctx),
            "comparison_language_detected": bool(mentions_comparison),
            # Default “recent block” window we want for comparisons unless athlete specifies otherwise.
            "recommended_recent_window_days": 84,
        }

        lines: List[str] = []
        lines.append("INTERNAL COACH CONTEXT (do not repeat verbatim):")
        lines.append(f"- Flags: {json.dumps(flags, separators=(',', ':'))}")

        if return_ctx:
            # User-requested explicitness: this must be unambiguous and strong.
            lines.append(
                "- User mentioned “since coming back / after injury / recent return”. "
                "Always ask for the exact return date or injury/break details BEFORE any "
                "longest/slowest/fastest/best/worst/most/least/hardest/easiest comparisons. "
                "Do NOT assume 365-day or all-time scope."
            )
        if mentions_comparison:
            lines.append(
                "- Before answering any superlative/comparison (longest/slowest/fastest/best/worst/most/least/hardest/easiest), "
                "check the last 4–12 weeks first (use tools) and cite receipts. If scope is unclear, ask one clarifying question."
            )
        if snippets:
            lines.append("- Recent athlete messages (most recent first):")
            for s in snippets:
                lines.append(f"  - “{s}”")

        return "\n".join(lines).strip()

    def _needs_return_scope_clarification(self, lower_message: str) -> bool:
        """
        True when:
        - The athlete uses return-context language ("since coming back", "after injury", etc.)
        - AND also uses comparison/superlative language ("longest", "slow", etc.)
        - BUT does not provide any concrete return window (date, \"6 weeks\", month name).

        This is a production-beta trust guardrail: ask a clarifying question instead of assuming.
        """
        lower = (lower_message or "").lower()
        if not lower:
            return False
        if not self._has_return_context(lower):
            return False

        # Comparison/superlative tokens (include common sentiment like "slow").
        if not (
            "longest" in lower
            or "furthest" in lower
            or "fastest" in lower
            or "slowest" in lower
            or "best" in lower
            or "worst" in lower
            or "most" in lower
            or "least" in lower
            or "hardest" in lower
            or "toughest" in lower
            or "easiest" in lower
            or "slow" in lower
            or "fast" in lower
        ):
            return False

        has_iso_date = bool(re.search(r"\b20\d{2}-\d{2}-\d{2}\b", lower))
        has_relative = bool(re.search(r"\b(\d{1,3})\s*(day|days|d|week|weeks|wk|wks|month|months|mo)\b", lower))
        has_month_name = bool(re.search(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)\b", lower))
        return not (has_iso_date or has_relative or has_month_name)

    def _user_explicitly_requested_ids(self, user_message: str) -> bool:
        ml = (user_message or "").lower()
        # If the athlete asks for IDs, we should allow them (debugging / audit use cases).
        return any(
            k in ml
            for k in (
                "activity id",
                "activity_id",
                "uuid",
                "full id",
                "full uuid",
                "show ids",
                "show id",
            )
        )

    def _normalize_response_for_ui(self, *, user_message: str, assistant_message: str) -> str:
        """
        Make coach output consistent and readable across *all* questions.

        Goals:
        - If there's an evidence/receipts block, ensure it is headed by '## Evidence' so the UI can collapse it.
        - Prefer 'Evidence' wording over 'Receipts' wording.
        - Suppress full UUID dumps in the main answer unless explicitly requested.
        """
        text = (assistant_message or "").strip()
        if not text:
            return text

        wants_ids = self._user_explicitly_requested_ids(user_message)

        # Normalize headings: 'Receipts' -> 'Evidence'
        text = re.sub(r"(?mi)(^|\n)##\s*Receipts\s*$", r"\1## Evidence", text)

        # If the model wrote a trailing "Receipts" or "Evidence" label without a markdown heading,
        # convert it into a collapsible heading.
        # Examples:
        #   "Receipts\n- 2026-...: ...\n"
        #   "Evidence:\n- 2026-...: ...\n"
        text = re.sub(r"(?mi)(^|\n)(receipts|evidence)\s*:\s*\n", r"\1## Evidence\n", text)
        text = re.sub(r"(?mi)(^|\n)(receipts|evidence)\s*\n(?=\s*[-*]\s*20\d{2}-\d{2}-\d{2})", r"\1## Evidence\n", text)

        if wants_ids:
            return text

        # Split into main vs evidence to avoid leaking UUIDs into the conversational flow.
        m = re.search(r"(?mi)(^|\n)##\s*Evidence\s*\n", text)
        if m and m.start() is not None:
            split_idx = m.start() + (1 if m.group(1) == "\n" else 0)
            main = text[:split_idx].rstrip()
            evidence = text[split_idx:].lstrip()
        else:
            main, evidence = text, ""

        # Remove UUIDs from main. Prefer removing the whole "(activity id: ...)" clause if present.
        main = re.sub(r"(?i)\s*\(?(planned workout|activity)\s*(id)?\s*:\s*%s\)?\s*" % self._UUID_RE.pattern, "", main)
        main = re.sub(self._UUID_RE, "", main)
        # Clean double spaces left behind.
        main = re.sub(r"[ \t]{2,}", " ", main).strip()

        if evidence:
            # In evidence: keep things readable; replace UUIDs with short refs.
            def _uuid_to_ref(match: re.Match) -> str:
                u = match.group(0)
                return f"{u[:8]}…"

            evidence = re.sub(self._UUID_RE, _uuid_to_ref, evidence)
            # Also normalize any "Receipts" mention lingering inside evidence blocks.
            evidence = re.sub(r"(?mi)(^|\n)##\s*Receipts\s*\n", r"\1## Evidence\n", evidence)
            return (main + "\n\n" + evidence.strip()).strip()

        return main

    def _most_impactful_run(self, athlete_id: UUID, days: int = 7) -> str:
        """
        Deterministic: define and compute "impactful" so we don't hallucinate.

        Definition (current):
          - impact_score = intensity_score * duration_s (proxy for stress)
          - fallback: duration_s, then distance
        """
        days = max(1, min(int(days), 730))
        recent = coach_tools.get_recent_runs(self.db, athlete_id, days=days)
        runs = (recent.get("data", {}) or {}).get("runs") or []
        units = (recent.get("data", {}) or {}).get("preferred_units") or "metric"

        if not runs:
            return "I don't have enough data to answer that."

        def impact_score(r: Dict[str, Any]) -> float:
            intensity = r.get("intensity_score")
            dur = r.get("duration_s") or 0
            dist_m = r.get("distance_m") or 0
            if intensity is not None and dur:
                return float(intensity) * float(dur)
            if dur:
                return float(dur)
            return float(dist_m)

        ranked = sorted(runs, key=impact_score, reverse=True)
        top = ranked[0]

        # Compose a human-readable headline, strictly from tool output.
        dt = (top.get("start_time") or "")[:10] or "unknown-date"
        name = (top.get("name") or "").strip() or "Run"
        avg_hr = top.get("avg_hr")

        if units == "imperial":
            dist = top.get("distance_mi")
            pace = top.get("pace_per_mile")
            dist_str = f"{dist:.1f} mi" if isinstance(dist, (int, float)) else "distance n/a"
            pace_str = pace or "pace n/a"
        else:
            dist = top.get("distance_km")
            pace = top.get("pace_per_km")
            dist_str = f"{dist:.1f} km" if isinstance(dist, (int, float)) else "distance n/a"
            pace_str = pace or "pace n/a"

        hr_str = f", avg HR {int(avg_hr)} bpm" if avg_hr is not None else ""

        lines: List[str] = []
        lines.append(f"Interpreting **“most impactful”** as: **highest estimated training stress** in the last {days} days.")
        lines.append("Right now that’s computed as **intensity_score × duration** (a proxy for how hard the session was), using tool data.")
        lines.append("")
        lines.append(f"**Most impactful run:** {dt} — {name} — **{dist_str} @ {pace_str}**{hr_str}")

        # Show a short ranked list for context (no UUID dumps).
        lines.append("")
        lines.append("**Next most impactful (for context):**")
        for r in ranked[1:4]:
            d = (r.get("start_time") or "")[:10] or "unknown-date"
            n = (r.get("name") or "").strip() or "Run"
            if units == "imperial":
                dd = r.get("distance_mi")
                pp = r.get("pace_per_mile")
                dd_str = f"{dd:.1f} mi" if isinstance(dd, (int, float)) else "n/a"
            else:
                dd = r.get("distance_km")
                pp = r.get("pace_per_km")
                dd_str = f"{dd:.1f} km" if isinstance(dd, (int, float)) else "n/a"
            pp_str = pp or "n/a"
            lines.append(f"- {d} — {n} — {dd_str} @ {pp_str}")

        # Evidence (use the already-formatted evidence lines from tools)
        lines.append("")
        lines.append("## Evidence")
        ev = recent.get("evidence") or []
        for e in ev[:6]:
            if e.get("type") == "activity":
                # Keep human-readable. Short ref is OK for disambiguation.
                ref = e.get("ref")
                suffix = f" (ref {ref})" if ref else ""
                lines.append(f"- {e.get('date')}: {e.get('value')}{suffix}")

        return "\n".join(lines)

    def _top_run_by(self, athlete_id: UUID, *, days: int, metric: str, label: str) -> str:
        """
        Deterministic "top run" selector to support many high-signal questions.

        Supported metrics:
          - distance: max distance
          - stress_proxy: intensity_score × duration_s (fallback duration, then distance)
        """
        days = max(1, min(int(days), 730))
        recent = coach_tools.get_recent_runs(self.db, athlete_id, days=days)
        runs = (recent.get("data", {}) or {}).get("runs") or []
        units = (recent.get("data", {}) or {}).get("preferred_units") or "metric"

        if not runs:
            return "I don't have enough data to answer that."

        def score(r: Dict[str, Any]) -> float:
            if metric == "distance":
                return float(r.get("distance_m") or 0)
            if metric == "stress_proxy":
                intensity = r.get("intensity_score")
                dur = r.get("duration_s") or 0
                dist_m = r.get("distance_m") or 0
                if intensity is not None and dur:
                    return float(intensity) * float(dur)
                if dur:
                    return float(dur)
                return float(dist_m)
            return 0.0

        ranked = sorted(runs, key=score, reverse=True)
        top = ranked[0]

        dt = (top.get("start_time") or "")[:10] or "unknown-date"
        name = (top.get("name") or "").strip() or "Run"
        avg_hr = top.get("avg_hr")

        if units == "imperial":
            dist = top.get("distance_mi")
            pace = top.get("pace_per_mile")
            dist_str = f"{dist:.1f} mi" if isinstance(dist, (int, float)) else "distance n/a"
            pace_str = pace or "pace n/a"
        else:
            dist = top.get("distance_km")
            pace = top.get("pace_per_km")
            dist_str = f"{dist:.1f} km" if isinstance(dist, (int, float)) else "distance n/a"
            pace_str = pace or "pace n/a"

        hr_str = f", avg HR {int(avg_hr)} bpm" if avg_hr is not None else ""

        lines: List[str] = []
        if metric == "distance":
            lines.append(f"Interpreting **“{label}”** as: **maximum distance** in the last {days} days.")
        elif metric == "stress_proxy":
            lines.append(
                f"Interpreting **“{label}”** as: **highest estimated training stress** in the last {days} days."
            )
            lines.append("Computed as **intensity_score × duration** (proxy), using tool data.")
        else:
            lines.append(f"Interpreting **“{label}”** as: top by {metric} in the last {days} days.")

        lines.append("")
        lines.append(f"**{label.capitalize()} run:** {dt} — {name} — **{dist_str} @ {pace_str}**{hr_str}")

        lines.append("")
        lines.append("## Evidence")
        ev = recent.get("evidence") or []
        for e in ev[:6]:
            if e.get("type") == "activity":
                ref = e.get("ref")
                suffix = f" (ref {ref})" if ref else ""
                lines.append(f"- {e.get('date')}: {e.get('value')}{suffix}")

        return "\n".join(lines)


def get_ai_coach(db: Session) -> AICoach:
    """Factory function for dependency injection."""
    return AICoach(db)
