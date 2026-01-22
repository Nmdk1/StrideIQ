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
    Athlete, Activity, TrainingPlan, PlannedWorkout, 
    DailyCheckin, PersonalBest
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

## Evidence & Citations (REQUIRED)

When providing insights:
- Always cite specific evidence from tool results (run IDs, dates, and values).
- Format citations clearly in plain English, e.g.:
  - "On 2026-01-15, you ran 8.5 km @ 5:30/km (avg HR 152 bpm)."
  - "On 2026-01-12, EF was 123.4 (pace 8.10 min/mi, avg HR 150)."
- For questions like "Am I getting fitter?", you MUST use `get_efficiency_trend` and cite at least 2 EF points (earliest and latest available).
- If data is insufficient, say: "I don't have enough data to answer that."
- Never make claims (numbers, trends, training load, plan details) without tool-backed evidence.

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
                        f"Analyze what led to my {pb_count} PRs. Cite each PR date + distance + TSB day-before + activity id (from get_pb_patterns)."
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
                add(f"Review my run from today ({distance_km:.1f} km). Cite the activity id + distance + pace + avg HR (from get_recent_runs).")
        except Exception:
            pass

        # --- Fallback defaults ---
        if len(suggestions) < 3:
            add("How is my training going overall? Cite at least 2 recent runs (date + activity id + distance + pace) and my current ATL/CTL/TSB.")
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

        # Deterministic answers for high-risk questions (avoid "reckless" responses).
        lower = (message or "").lower()
        if any(phrase in lower for phrase in ("how far back", "how far can you look", "how far back can you look", "how far back do you go")):
            return {
                "response": (
                    "I can look back **up to ~2 years** (730 days) for run-history queries, and I can cite specific activities (date + activity id).\n\n"
                    "If you want a longest-run or high-volume comparison, I can pull a 365–730 day window and summarize it with receipts."
                ),
                "thread_id": self.get_or_create_thread(athlete_id),
                "error": False,
            }

        if (
            ("run today" in lower or "today's run" in lower or "today run" in lower)
            and ("suggest" in lower or "what should" in lower or "any advice" in lower or "tips" in lower)
        ) or (
            # Common follow-ups after a "today" recommendation: user disputes the plan distance.
            ("plan" in lower and ("too short" in lower or "stupid" in lower or "way too short" in lower))
        ):
            thread_id, _ = self.get_or_create_thread_with_state(athlete_id)
            return {
                "response": self._today_run_guidance(athlete_id),
                "thread_id": thread_id,
                "error": False,
            }

        # Phase 3 acceptance: if the athlete has no run data and asks about fitness trend,
        # respond explicitly with the required phrasing (avoid any implied metrics).
        try:
            if "getting fitter" in (message or "").lower():
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
                        "CITATIONS REQUIRED: When you state a fact, cite it explicitly (date + id + value), e.g. "
                        "\"On 2026-01-15 (activity <uuid>), you ran 8.5 km @ 5:30/km.\""
                    ),
                )
            
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
            max_wait = 60  # seconds
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
                    return {
                        "response": "The AI coach took too long to respond. Please try again.",
                        "error": True
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
                
                return {
                    "response": response_text,
                    "thread_id": thread_id,
                    "error": False
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
        lines.append("## Receipts")
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

        receipt_section = ("receipts" in lower) or ("citations" in lower)
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
                "- Add a final section titled 'Receipts' listing supporting evidence lines.\n"
                "- Receipts must include at least one ISO date (YYYY-MM-DD) and a human label (e.g., run name + key values).\n"
                "- Do NOT dump long UUIDs unless the user explicitly asks; keep receipts readable.\n"
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


def get_ai_coach(db: Session) -> AICoach:
    """Factory function for dependency injection."""
    return AICoach(db)
