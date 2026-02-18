"""
AI Coach Service

Gemini 2.5 Flash handles bulk coaching queries.
High-stakes queries route to Claude Opus for maximum reasoning quality.

Features:
- Persistent conversation sessions per athlete (PostgreSQL-backed)
- Context injection from athlete's actual data
- Knowledge of training methodology
- Tiered context (7-day, 30-day, 120-day)
- Hybrid model routing (Gemini Flash + Claude Opus) per ADR-061
- Hard cost caps per athlete
"""

import os
import json
import re
import asyncio
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Optional, Dict, List, Any, Tuple
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import func
import logging

logger = logging.getLogger(__name__)

# =============================================================================
# ADR-061: HYBRID MODEL ARCHITECTURE WITH COST CAPS
# =============================================================================

# High-stakes signals that trigger Opus routing
class HighStakesSignal(Enum):
    """Signals that trigger Opus routing for maximum reasoning quality."""
    INJURY = "injury"
    PAIN = "pain"
    OVERTRAINING = "overtraining"
    FATIGUE = "fatigue"
    SKIP_DECISION = "skip"
    LOAD_ADJUSTMENT = "load"
    RETURN_FROM_BREAK = "return"
    ILLNESS = "illness"


# Patterns that trigger high-stakes routing to Opus
HIGH_STAKES_PATTERNS = [
    # Injury/pain signals (liability risk)
    "injury", "injured", "pain", "painful", "hurt", "hurting",
    "sore", "soreness", "ache", "aching", "sharp", "stabbing",
    "tender", "swollen", "swelling", "inflammation",
    "strain", "sprain", "tear", "stress fracture",
    "knee", "shin", "achilles", "plantar", "it band", "hip",
    "calf", "hamstring", "quad", "groin", "ankle", "foot",
    
    # Recovery concerns
    "overtrain", "overtraining", "burnout", "exhausted",
    "can't recover", "not recovering", "always tired",
    "resting heart rate", "hrv dropping", "hrv crashed",
    "legs feel dead", "no energy",
    
    # Return-from-break (high error risk)
    "coming back", "returning from", "time off", "break",
    "haven't run", "first run back", "starting again",
    "after illness", "after sick", "after covid",
    "after surgery", "post-op", "back from",
    
    # Load decisions (requires careful reasoning)
    "should i run", "safe to run", "okay to run",
    "skip", "should i skip", "take a day off",
    "reduce mileage", "cut back", "too much",
    "push through", "run through",
]

# Cost cap constants (ADR-061)
COACH_MAX_REQUESTS_PER_DAY = int(os.getenv("COACH_MAX_REQUESTS_PER_DAY", "50"))
COACH_MAX_OPUS_REQUESTS_PER_DAY = int(os.getenv("COACH_MAX_OPUS_REQUESTS_PER_DAY", "3"))
COACH_MONTHLY_TOKEN_BUDGET = int(os.getenv("COACH_MONTHLY_TOKEN_BUDGET", "1000000"))
COACH_MONTHLY_OPUS_TOKEN_BUDGET = int(os.getenv("COACH_MONTHLY_OPUS_TOKEN_BUDGET", "50000"))
COACH_MAX_INPUT_TOKENS = int(os.getenv("COACH_MAX_INPUT_TOKENS", "4000"))
# 500 tokens was causing every response to get cut off mid-sentence.
# 3000 tokens (~1200 words) allows complete, well-structured coaching responses
# with numbered points, evidence citations, and actionable recommendations
# without truncation. Previous 1500 limit was causing mid-sentence cutoffs.
COACH_MAX_OUTPUT_TOKENS = int(os.getenv("COACH_MAX_OUTPUT_TOKENS", "3000"))


def is_high_stakes_query(message: str) -> bool:
    """
    Determine if query requires Opus for maximum reasoning quality.
    
    Returns True for:
    - Injury/pain mentions
    - Return-from-break queries
    - Load adjustment decisions
    - Overtraining concerns
    
    See ADR-061 for rationale.
    """
    if not message:
        return False
    message_lower = message.lower()
    return any(pattern in message_lower for pattern in HIGH_STAKES_PATTERNS)

# Check if Anthropic is available (for Opus high-stakes routing)
try:
    from anthropic import Anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    logger.info("Anthropic not installed - high-stakes queries will use GPT-4o fallback")

# Check if Google GenAI is available (for Gemini 2.5 Flash bulk queries)
try:
    from google import genai
    from google.genai import types as genai_types
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    genai = None
    genai_types = None
    logger.info("Google GenAI not installed - bulk queries will use GPT-4o-mini fallback")

from models import (
    Athlete,
    Activity,
    TrainingPlan,
    PlannedWorkout,
    DailyCheckin,
    PersonalBest,
    IntakeQuestionnaire,
    CoachIntentSnapshot,
    CoachUsage,
    CoachChat,
)
from services import coach_tools
from services.training_load import TrainingLoadCalculator
from services.efficiency_analytics import get_efficiency_trends

# Phase 4/5 Modular Coach Components
from services.coach_modules import (
    MessageRouter,
    MessageType,
    ContextBuilder,
    ConversationQualityManager,
    DetailLevel,
)


class AICoach:
    """
    AI Coach powered by Gemini 2.5 Flash (bulk) and Claude Opus (high-stakes).
    
    Provides:
    - Persistent conversation sessions (PostgreSQL-backed)
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
- NEVER use training acronyms (TSB, ATL, CTL, EF, TRIMP, etc.) in responses - translate to plain English like "fatigue level", "fitness", "form", "efficiency"
- CRITICAL TERMINOLOGY: NEVER say "RPI" - this is a trademarked term. ALWAYS say "RPI" (Running Performance Index) instead. For example: "Your RPI of 53.2 indicates..." NOT "Your RPI value of 53.2..."
- Avoid jargon unless the athlete uses it first
- Be encouraging but never sugarcoat problems
- Format responses with clear structure (use markdown)
- Conversational A->I->A requirement (chat prose, not JSON): include an interpretive Assessment, explain the Implication, then provide a concrete Action.
- Do NOT repeat yourself or give the same canned response multiple times

## Important Rules

1. Never recommend medical advice - refer to healthcare professionals
2. Never recommend extreme diets or protocols
3. Always acknowledge when you're uncertain
4. Base recommendations on the athlete's current fitness level, not aspirational goals
5. Consider the athlete's injury history if mentioned

## CRITICAL: Tool Selection for Pace Questions

When the athlete asks about training paces (threshold pace, easy pace, interval pace, marathon pace, etc.):
- ALWAYS call get_training_paces FIRST - this is the ONLY authoritative source for training paces
- These paces are calculated from the athlete's RPI (Running Performance Index, based on their race results)
- NEVER derive paces from recent runs or efficiency data - that's what they RAN, not what they SHOULD run
- The training pace calculator is scientifically accurate - trust it over any other data

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
  - "On 2026-01-12, your efficiency was 123.4 (pace 8.10 min/mi, avg HR 150)."
- Avoid dumping full UUIDs in the main answer. Only include full activity IDs if the athlete explicitly asks.
- For questions like "Am I getting fitter?", you MUST use `get_efficiency_trend` and cite at least 2 efficiency data points (earliest and latest available).
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

    # Model tiers (ADR-061: Hybrid architecture with cost caps)
    # 95% of queries use Gemini 2.5 Flash (cost-efficient, 1M context)
    # 5% high-stakes queries use Claude Opus 4.5 (maximum reasoning quality)
    MODEL_DEFAULT = "gemini-2.5-flash"      # Standard coaching (95%)
    MODEL_HIGH_STAKES = "claude-opus-4-5-20251101"  # Injury/recovery/load decisions (5%)
    
    # Legacy aliases for backward compatibility
    MODEL_LOW = MODEL_DEFAULT
    MODEL_MEDIUM = MODEL_DEFAULT
    MODEL_HIGH = MODEL_DEFAULT
    MODEL_HIGH_VIP = MODEL_HIGH_STAKES
    MODEL_SIMPLE = MODEL_DEFAULT
    MODEL_STANDARD = MODEL_DEFAULT

    def __init__(self, db: Session):
        self.db = db
        self.anthropic_client = None
        self.gemini_client = None
        
        # Phase 4/5: Modular components
        self.router = MessageRouter()
        self.context_builder = ContextBuilder()
        self.conversation_manager = ConversationQualityManager()
        
        # ADR-061: Load VIP athletes and model routing config
        self._load_vip_athletes()
        self.model_routing_enabled = os.getenv("COACH_MODEL_ROUTING", "on").lower() == "on"
        self.high_stakes_routing_enabled = os.getenv("COACH_HIGH_STAKES_ROUTING", "on").lower() == "on"
        
        # Initialize Anthropic client for high-stakes queries (ADR-061)
        if ANTHROPIC_AVAILABLE:
            anthropic_key = os.getenv("ANTHROPIC_API_KEY")
            if anthropic_key:
                self.anthropic_client = Anthropic(api_key=anthropic_key)
                logger.info("Anthropic client initialized for high-stakes routing")
        
        # Initialize Gemini client for bulk queries (Feb 2026 migration)
        if GEMINI_AVAILABLE:
            google_key = os.getenv("GOOGLE_AI_API_KEY")
            if google_key:
                self.gemini_client = genai.Client(api_key=google_key)
                logger.info("Gemini 2.5 Flash initialized for bulk coaching queries")
            else:
                self.gemini_client = None
        else:
            self.gemini_client = None
    
    def _load_vip_athletes(self) -> None:
        """
        Load VIP athlete IDs from environment (fallback/override).
        VIPs get MODEL_HIGH_VIP (gpt-5.2) for high-complexity queries.
        
        Note: DB-based VIP status (is_coach_vip) is checked per-query
        via is_athlete_vip() for real-time admin changes.
        """
        # Load from env: comma-separated UUIDs (override/fallback)
        vip_env = os.getenv("COACH_VIP_ATHLETE_IDS", "")
        if vip_env:
            self.VIP_ATHLETE_IDS = set(aid.strip() for aid in vip_env.split(",") if aid.strip())
        else:
            self.VIP_ATHLETE_IDS = set()
        
        # Also load owner ID as implicit VIP
        owner_id = os.getenv("OWNER_ATHLETE_ID")
        if owner_id:
            self.VIP_ATHLETE_IDS.add(owner_id.strip())
    
    def is_athlete_vip(self, athlete_id: Optional[UUID]) -> bool:
        """
        Check if athlete has VIP status for premium model access.
        
        Checks in order:
        1. Environment variable override (COACH_VIP_ATHLETE_IDS, OWNER_ATHLETE_ID)
        2. Database flag (athlete.is_coach_vip)
        
        Returns True if athlete should get MODEL_HIGH_VIP for complex queries.
        """
        if not athlete_id:
            return False
        
        # Check env var override first
        if str(athlete_id) in self.VIP_ATHLETE_IDS:
            return True
        
        # Check database flag
        try:
            from models import Athlete
            athlete = self.db.query(Athlete).filter(Athlete.id == athlete_id).first()
            if athlete and getattr(athlete, 'is_coach_vip', False):
                return True
        except Exception as e:
            logger.warning(f"Failed to check VIP status for athlete {athlete_id}: {e}")
        
        return False

    # =========================================================================
    # ADR-061: BUDGET TRACKING AND COST CAPS
    # =========================================================================
    
    def _get_or_create_usage(self, athlete_id: UUID) -> "CoachUsage":
        """
        Get or create usage tracking record for athlete.
        
        Handles daily and monthly reset logic.
        """
        from models import CoachUsage
        
        today = date.today()
        current_month = today.strftime("%Y-%m")
        
        # Try to get existing record for today
        usage = (
            self.db.query(CoachUsage)
            .filter(CoachUsage.athlete_id == athlete_id, CoachUsage.date == today)
            .first()
        )
        
        if usage:
            # Check if month rolled over (reset monthly counters)
            if usage.month != current_month:
                usage.month = current_month
                usage.tokens_this_month = 0
                usage.opus_tokens_this_month = 0
                usage.cost_this_month_cents = 0
                self.db.commit()
            return usage
        
        # Create new record for today
        # Carry over monthly totals from previous day if same month
        prev_usage = (
            self.db.query(CoachUsage)
            .filter(CoachUsage.athlete_id == athlete_id, CoachUsage.month == current_month)
            .order_by(CoachUsage.date.desc())
            .first()
        )
        
        usage = CoachUsage(
            athlete_id=athlete_id,
            date=today,
            month=current_month,
            requests_today=0,
            opus_requests_today=0,
            tokens_today=0,
            opus_tokens_today=0,
            tokens_this_month=prev_usage.tokens_this_month if prev_usage else 0,
            opus_tokens_this_month=prev_usage.opus_tokens_this_month if prev_usage else 0,
            cost_today_cents=0,
            cost_this_month_cents=prev_usage.cost_this_month_cents if prev_usage else 0,
        )
        self.db.add(usage)
        self.db.commit()
        self.db.refresh(usage)
        return usage
    
    def _is_founder(self, athlete_id: UUID) -> bool:
        """Owner/founder bypasses all budget limits."""
        owner_id = os.getenv("OWNER_ATHLETE_ID", "")
        return owner_id and str(athlete_id) == owner_id.strip()

    def check_budget(self, athlete_id: UUID, is_opus: bool = False, is_vip: bool = False) -> Tuple[bool, str]:
        """
        Check if athlete has budget remaining for a query.
        
        Args:
            athlete_id: The athlete's ID
            is_opus: Whether this is an Opus (high-stakes) query
            is_vip: Whether athlete is VIP (gets 10× Opus allocation)
            
        Returns:
            (allowed, reason) - True if request can proceed, else False with reason
        """
        try:
            if self._is_founder(athlete_id):
                return True, "founder_bypass"

            usage = self._get_or_create_usage(athlete_id)
            
            # VIP multiplier for Opus allocation (ADR-061)
            vip_multiplier = 10 if is_vip else 1
            
            # Daily request limit (same for VIP and standard)
            if usage.requests_today >= COACH_MAX_REQUESTS_PER_DAY:
                return False, "daily_request_limit"
            
            # Opus-specific limits (VIP gets 10× allocation)
            if is_opus:
                max_opus_daily = COACH_MAX_OPUS_REQUESTS_PER_DAY * vip_multiplier
                max_opus_monthly = COACH_MONTHLY_OPUS_TOKEN_BUDGET * vip_multiplier
                
                if usage.opus_requests_today >= max_opus_daily:
                    return False, "daily_opus_limit"
                if usage.opus_tokens_this_month >= max_opus_monthly:
                    return False, "monthly_opus_budget"
            
            # Monthly token budget (same for VIP and standard)
            if usage.tokens_this_month >= COACH_MONTHLY_TOKEN_BUDGET:
                return False, "monthly_token_budget"
            
            return True, "ok"
        except Exception as e:
            logger.warning(f"Budget check failed for {athlete_id}: {e}")
            # Fail open - don't block on budget check errors
            return True, "error_fail_open"
    
    def track_usage(
        self,
        athlete_id: UUID,
        input_tokens: int,
        output_tokens: int,
        model: str,
        is_opus: bool = False,
    ) -> None:
        """
        Record token usage for an athlete.
        
        Args:
            athlete_id: The athlete's ID
            input_tokens: Number of input tokens used
            output_tokens: Number of output tokens used
            model: Model name used
            is_opus: Whether this was an Opus query
        """
        try:
            usage = self._get_or_create_usage(athlete_id)
            total_tokens = input_tokens + output_tokens
            
            # Update daily counters
            usage.requests_today += 1
            usage.tokens_today += total_tokens
            
            # Update monthly counters
            usage.tokens_this_month += total_tokens
            
            # Calculate cost (in cents) - approximate
            if is_opus:
                usage.opus_requests_today += 1
                usage.opus_tokens_today += total_tokens
                usage.opus_tokens_this_month += total_tokens
                # Opus: $5/1M input, $25/1M output
                cost_cents = int((input_tokens * 0.5 + output_tokens * 2.5) / 100)
            elif "gemini" in model.lower():
                # Gemini 2.5 Flash: $0.30/1M input, $2.50/1M output (Feb 2026)
                cost_cents = int((input_tokens * 0.03 + output_tokens * 0.25) / 100)
            elif "gpt-4o-mini" in model:
                # GPT-4o-mini: $0.15/1M input, $0.60/1M output
                cost_cents = int((input_tokens * 0.015 + output_tokens * 0.06) / 100)
            else:
                # GPT-4o: $2.50/1M input, $10/1M output
                cost_cents = int((input_tokens * 0.25 + output_tokens * 1.0) / 100)
            
            usage.cost_today_cents += cost_cents
            usage.cost_this_month_cents += cost_cents
            
            self.db.commit()
            
            logger.debug(
                f"Usage tracked: athlete={athlete_id}, tokens={total_tokens}, "
                f"model={model}, is_opus={is_opus}, cost_cents={cost_cents}"
            )
        except Exception as e:
            logger.warning(f"Failed to track usage for {athlete_id}: {e}")
            # Don't fail the request on tracking errors
    
    def get_budget_status(self, athlete_id: UUID) -> Dict[str, Any]:
        """
        Get current budget status for an athlete.
        
        Returns dict with usage stats and remaining budgets.
        VIP athletes see their 10× Opus allocation.
        """
        try:
            usage = self._get_or_create_usage(athlete_id)
            is_vip = self.is_athlete_vip(athlete_id)
            vip_multiplier = 10 if is_vip else 1
            
            max_opus_daily = COACH_MAX_OPUS_REQUESTS_PER_DAY * vip_multiplier
            max_opus_monthly = COACH_MONTHLY_OPUS_TOKEN_BUDGET * vip_multiplier
            
            return {
                "date": str(usage.date),
                "month": usage.month,
                "is_vip": is_vip,
                "requests_today": usage.requests_today,
                "requests_remaining_today": max(0, COACH_MAX_REQUESTS_PER_DAY - usage.requests_today),
                "opus_requests_today": usage.opus_requests_today,
                "opus_requests_limit_today": max_opus_daily,
                "opus_requests_remaining_today": max(0, max_opus_daily - usage.opus_requests_today),
                "tokens_this_month": usage.tokens_this_month,
                "tokens_remaining_this_month": max(0, COACH_MONTHLY_TOKEN_BUDGET - usage.tokens_this_month),
                "opus_tokens_this_month": usage.opus_tokens_this_month,
                "opus_tokens_limit_this_month": max_opus_monthly,
                "opus_tokens_remaining_this_month": max(0, max_opus_monthly - usage.opus_tokens_this_month),
                "cost_this_month_usd": usage.cost_this_month_cents / 100,
                "budget_healthy": (
                    usage.tokens_this_month < COACH_MONTHLY_TOKEN_BUDGET * 0.8 and
                    usage.opus_tokens_this_month < max_opus_monthly * 0.8
                ),
            }
        except Exception as e:
            logger.warning(f"Failed to get budget status for {athlete_id}: {e}")
            return {"error": str(e)}

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
                "description": "Get race time predictions for 5K, 10K, Half Marathon, and Marathon.",
                "input_schema": {
                    "type": "object",
                    "properties": {},
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
                "description": "Get athlete physiological profile: max HR, threshold paces, RPI, runner type, HR zones, and training metrics.",
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
            else:
                result = {"error": f"Unknown tool: {tool_name}"}
            return json.dumps(result, default=str)
        except Exception as e:
            logger.warning(f"Tool execution error for {tool_name}: {e}")
            return json.dumps({"error": str(e)})

    async def query_opus(
        self,
        athlete_id: UUID,
        message: str,
        athlete_state: str,
        conversation_context: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """
        Query Claude Opus for high-stakes decisions (ADR-061).
        
        Uses Anthropic API with TOOL ACCESS - Opus can query any data it needs.
        Reserved for injury/recovery/load decisions where maximum reasoning quality matters.
        """
        if not self.anthropic_client:
            return {
                "response": "High-stakes model not available. Please try again.",
                "error": True,
                "model": None,
            }
        
        # Build messages
        messages = []
        
        # Add conversation context (last 5 exchanges)
        if conversation_context:
            for msg in conversation_context[-10:]:
                messages.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", ""),
                })
        
        # Add current message
        messages.append({"role": "user", "content": message})
        
        # System prompt for high-stakes reasoning WITH tool guidance
        system_prompt = """You are StrideIQ, an expert running coach. This is a HIGH-STAKES query involving training load, injury risk, or recovery decisions.

CRITICAL: NEVER HALLUCINATE DATA. Every number, distance, pace, and date you cite MUST come from tool results. NEVER fabricate or estimate training data. If you haven't called a tool yet, call one NOW. Violating this rule destroys athlete trust.

YOU HAVE 22 TOOLS — USE THEM PROACTIVELY:
- ALWAYS call get_weekly_volume first to understand the athlete's training history
- Call get_recent_runs to see individual workout details (up to 730 days back)
- Call get_training_load for current fitness/fatigue/form
- Call get_training_load_history for load progression over time
- Call get_recovery_status for injury risk assessment
- Call get_athlete_profile for age, experience, preferences
- Call get_efficiency_trend to track fitness changes over time
- Call get_best_runs for peak performance data
- Call compare_training_periods to compare recent vs previous training
- Call get_calendar_day_context for specific day plan + actual
- Call get_wellness_trends for sleep, stress, soreness patterns
- NEVER say "I don't have access" — call the tools instead

REASONING APPROACH:
1. First gather data with tools - look at weeks/months of history, not just recent days
2. Identify patterns: returning from injury? building mileage? overreaching?
3. Consider the athlete's context (age, experience, goals)
4. Make specific, evidence-based recommendations
5. When the athlete is venting or emotional, empathize FIRST, then offer data perspective

COMMUNICATION:
- Use plain English (never acronyms like TSB, ATL, CTL)
- NEVER say "RPI" - always say "RPI" (Running Performance Index) instead
- Be specific with numbers (recommend "42-45 miles" not "increase gradually")
- Cite the data you used with dates and values ("On 2026-01-15, you ran 8.5 mi @ 9:04/mi...")
- Be conservative with injury-related advice
- Do NOT repeat yourself or give the same response multiple times

If you need more data to answer well, call the tools. That's why they're there."""
        
        try:
            total_input_tokens = 0
            total_output_tokens = 0
            
            # Initial call with tools
            response = self.anthropic_client.messages.create(
                model=self.MODEL_HIGH_STAKES,
                system=system_prompt,
                messages=messages,
                max_tokens=COACH_MAX_OUTPUT_TOKENS,
                tools=self._opus_tools(),
            )
            
            total_input_tokens += response.usage.input_tokens if hasattr(response, 'usage') else 0
            total_output_tokens += response.usage.output_tokens if hasattr(response, 'usage') else 0
            
            # Handle tool calls in a loop (max 5 iterations to prevent runaway)
            for _ in range(5):
                if response.stop_reason != "tool_use":
                    break
                
                # Process tool calls
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        tool_name = block.name
                        tool_input = block.input
                        tool_id = block.id
                        
                        logger.info(f"Opus calling tool: {tool_name} with {tool_input}")
                        result = self._execute_opus_tool(athlete_id, tool_name, tool_input)
                        
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_id,
                            "content": result,
                        })
                
                # Continue conversation with tool results
                # Convert response.content to list of dicts for serialization
                assistant_content = []
                for block in response.content:
                    if block.type == "text":
                        assistant_content.append({"type": "text", "text": block.text})
                    elif block.type == "tool_use":
                        assistant_content.append({
                            "type": "tool_use",
                            "id": block.id,
                            "name": block.name,
                            "input": block.input,
                        })
                messages.append({"role": "assistant", "content": assistant_content})
                messages.append({"role": "user", "content": tool_results})
                
                response = self.anthropic_client.messages.create(
                    model=self.MODEL_HIGH_STAKES,
                    system=system_prompt,
                    messages=messages,
                    max_tokens=COACH_MAX_OUTPUT_TOKENS,
                    tools=self._opus_tools(),
                )
                
                total_input_tokens += response.usage.input_tokens if hasattr(response, 'usage') else 0
                total_output_tokens += response.usage.output_tokens if hasattr(response, 'usage') else 0
            
            # Extract final response text
            response_text = ""
            for block in response.content:
                if hasattr(block, 'text'):
                    response_text += block.text
            
            self.track_usage(
                athlete_id=athlete_id,
                input_tokens=total_input_tokens,
                output_tokens=total_output_tokens,
                model=self.MODEL_HIGH_STAKES,
                is_opus=True,
            )
            
            logger.info(
                f"Opus query completed: athlete={athlete_id}, "
                f"input_tokens={total_input_tokens}, output_tokens={total_output_tokens}"
            )
            
            return {
                "response": response_text,
                "error": False,
                "model": self.MODEL_HIGH_STAKES,
                "is_high_stakes": True,
                "input_tokens": total_input_tokens,
                "output_tokens": total_output_tokens,
            }
            
        except Exception as e:
            logger.error(f"Opus query failed for {athlete_id}: {e}")
            return {
                "response": f"I encountered an error processing your request. Please try again.",
                "error": True,
                "model": self.MODEL_HIGH_STAKES,
                "error_detail": str(e),
            }

    async def query_gemini(
        self,
        athlete_id: UUID,
        message: str,
        athlete_state: str,
        conversation_context: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """
        Query Gemini 2.5 Flash for bulk coaching queries (Feb 2026 migration).
        
        Replaces GPT-4o-mini for 95% of queries. Benefits:
        - 1M context window (no more aggressive pruning)
        - Competitive pricing ($0.30/1M input, $2.50/1M output)
        - Fast inference (254 tokens/sec)
        
        Uses Gemini API with function calling for tool access.
        """
        if not self.gemini_client:
            logger.error("Gemini client not initialized — coach unavailable")
            return {
                "response": "Coach is temporarily unavailable. Please try again in a moment.",
                "error": True,
            }
        
        # Build Gemini tools (function declarations) — FULL tool suite
        function_declarations = [
            {
                "name": "get_recent_runs",
                "description": "Fetch the athlete's recent runs including dates, distances, paces, heart rates, and workout types.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "days": {
                            "type": "integer",
                            "description": "How many days back to look (default 14, max 730)"
                        }
                    }
                }
            },
            {
                "name": "get_calendar_day_context",
                "description": "Get plan + actual context for a specific calendar day (planned workout + completed activities with IDs).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "day": {
                            "type": "string",
                            "description": "Calendar date in YYYY-MM-DD format."
                        }
                    },
                    "required": ["day"]
                }
            },
            {
                "name": "get_efficiency_trend",
                "description": "Get efficiency trend data over time (pace-at-HR time series + summary). Use for 'am I getting fitter?' questions.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "days": {
                            "type": "integer",
                            "description": "How many days of history to analyze (default 30, max 365)"
                        }
                    }
                }
            },
            {
                "name": "get_plan_week",
                "description": "Get the current week's planned workouts for the athlete's active training plan.",
                "parameters": {"type": "object", "properties": {}}
            },
            {
                "name": "get_weekly_volume",
                "description": "Get weekly mileage totals for the athlete over recent weeks.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "weeks": {
                            "type": "integer",
                            "description": "Number of weeks to retrieve (default 12, max 104)"
                        }
                    }
                }
            },
            {
                "name": "get_training_load",
                "description": "Get the athlete's current training load metrics: fitness, fatigue, and form.",
                "parameters": {"type": "object", "properties": {}}
            },
            {
                "name": "get_training_paces",
                "description": "Get RPI-based training paces (easy, threshold, interval, marathon). THIS IS THE AUTHORITATIVE SOURCE for training paces.",
                "parameters": {"type": "object", "properties": {}}
            },
            {
                "name": "get_correlations",
                "description": "Get correlations between wellness inputs and efficiency outputs.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "days": {
                            "type": "integer",
                            "description": "How many days of history to analyze (default 30, max 365)"
                        }
                    }
                }
            },
            {
                "name": "get_race_predictions",
                "description": "Get race time predictions for 5K, 10K, Half Marathon, and Marathon.",
                "parameters": {"type": "object", "properties": {}}
            },
            {
                "name": "get_recovery_status",
                "description": "Get recovery metrics: half-life, durability index, false fitness and masked fatigue signals.",
                "parameters": {"type": "object", "properties": {}}
            },
            {
                "name": "get_active_insights",
                "description": "Get prioritized actionable insights for the athlete.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "limit": {
                            "type": "integer",
                            "description": "Max insights to return (default 5, max 10)"
                        }
                    }
                }
            },
            {
                "name": "get_pb_patterns",
                "description": "Get training patterns that preceded personal bests, including optimal form range.",
                "parameters": {"type": "object", "properties": {}}
            },
            {
                "name": "get_efficiency_by_zone",
                "description": "Get efficiency trend for specific effort zones (easy, threshold, race).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "effort_zone": {
                            "type": "string",
                            "description": "Effort zone to analyze: easy, threshold, or race (default threshold)"
                        },
                        "days": {
                            "type": "integer",
                            "description": "Days of history (default 90, max 365)"
                        }
                    }
                }
            },
            {
                "name": "get_nutrition_correlations",
                "description": "Get correlations between pre/post-activity nutrition and performance/recovery.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "days": {
                            "type": "integer",
                            "description": "Days of history (default 90, max 365)"
                        }
                    }
                }
            },
            {
                "name": "get_best_runs",
                "description": "Get best runs by an explicit metric (efficiency, pace, distance, intensity_score), optionally filtered to an effort zone.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "days": {"type": "integer", "description": "History window (default 365, max 730)"},
                        "metric": {
                            "type": "string",
                            "description": "Ranking metric: efficiency, pace, distance, or intensity_score"
                        },
                        "limit": {"type": "integer", "description": "Max results (default 5, max 10)"},
                        "effort_zone": {
                            "type": "string",
                            "description": "Optional effort zone filter: easy, threshold, or race"
                        }
                    }
                }
            },
            {
                "name": "compare_training_periods",
                "description": "Compare last N days vs the previous N days (volume/run count deltas).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "days": {"type": "integer", "description": "Days per period (default 28, max 180)"}
                    }
                }
            },
            {
                "name": "get_coach_intent_snapshot",
                "description": "Get the athlete's current self-guided intent snapshot (goals/constraints) with staleness indicator.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "ttl_days": {"type": "integer", "description": "How long the snapshot is considered fresh (default 7)"}
                    }
                }
            },
            {
                "name": "set_coach_intent_snapshot",
                "description": "Update the athlete's self-guided intent snapshot (athlete-led) to avoid repetitive questioning.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "training_intent": {"type": "string", "description": "Athlete intent: through_fatigue | build_fitness | freshen_for_event"},
                        "next_event_date": {"type": "string", "description": "Optional YYYY-MM-DD for race/benchmark"},
                        "next_event_type": {"type": "string", "description": "Optional: race | benchmark | other"},
                        "pain_flag": {"type": "string", "description": "none | niggle | pain"},
                        "time_available_min": {"type": "integer", "description": "Typical time available (minutes)"},
                        "weekly_mileage_target": {"type": "number", "description": "Athlete-stated target miles/week"}
                    }
                }
            },
            {
                "name": "get_training_prescription_window",
                "description": "Deterministically prescribe training for 1-7 days (exact distances/paces/structure).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "start_date": {"type": "string", "description": "Start date YYYY-MM-DD (default today)"},
                        "days": {"type": "integer", "description": "How many days (1-7)"},
                        "time_available_min": {"type": "integer", "description": "Optional time cap for workouts (minutes)"},
                        "weekly_mileage_target": {"type": "number", "description": "Optional athlete target miles/week"},
                        "pain_flag": {"type": "string", "description": "none | niggle | pain"}
                    }
                }
            },
            {
                "name": "get_wellness_trends",
                "description": "Get wellness trends from daily check-ins: sleep, stress, soreness, HRV, resting HR, and mindset metrics over time.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "days": {
                            "type": "integer",
                            "description": "How many days of wellness data to analyze (default 28, max 90)"
                        }
                    }
                }
            },
            {
                "name": "get_athlete_profile",
                "description": "Get athlete physiological profile: max HR, threshold paces, RPI, runner type, HR zones, and training metrics.",
                "parameters": {"type": "object", "properties": {}}
            },
            {
                "name": "get_training_load_history",
                "description": "Get daily fitness/fatigue/form history showing training load progression and injury risk over time.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "days": {
                            "type": "integer",
                            "description": "How many days of load history (default 42, max 90)"
                        }
                    }
                }
            },
            {
                "name": "compute_running_math",
                "description": "Compute pace/time/distance math deterministically.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "pace_per_mile": {"type": "string"},
                        "pace_per_km": {"type": "string"},
                        "distance_miles": {"type": "number"},
                        "distance_km": {"type": "number"},
                        "time_seconds": {"type": "integer"},
                        "operation": {"type": "string"},
                    },
                    "required": ["operation"],
                },
            },
            {
                "name": "analyze_run_streams",
                "description": "Analyze per-second stream data for a run activity. Returns segment classification, cardiac/pace drift, coachable moments, and optional plan comparison. Uses the athlete's physiological profile for N=1 individualized analysis.",
                "parameters": {
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
        ]
        
        gemini_tools = genai_types.Tool(function_declarations=function_declarations)
        
        # ADR-16: Build rich pre-computed athlete brief
        try:
            athlete_brief = coach_tools.build_athlete_brief(self.db, athlete_id)
        except Exception as e:
            logger.warning(f"Failed to build athlete brief for {athlete_id}: {e}")
            athlete_brief = "(Brief unavailable — call tools for data.)"

        # ADR-16: System prompt — coaching persona + brief injection
        system_instruction = f"""You are the athlete's personal running coach. You have reviewed their complete file before this conversation — it's in the ATHLETE BRIEF below.

COACHING APPROACH:
- Lead with what matters. If you see something important in the brief, bring it up — don't wait to be asked.
- Be direct and sparse. Athletes don't want essays.
- Show patterns, explain what they mean, recommend what to do about them.
- Every number you cite MUST come from the brief or a tool result. NEVER fabricate, estimate, or guess training data. If the brief doesn't have it and you haven't called a tool, call one.
- NEVER compute math yourself — use the compute_running_math tool for pace/distance/time calculations.
- When the brief doesn't cover something, call a tool. Read the tool's narrative summary and coach from it.
- For deeper dives, call tools — you have 24 tools available. NEVER say "I don't have access."
- Conversational A->I->A requirement (chat prose, not JSON): provide an interpretive Assessment, explain the Implication, then a concrete Action.
- Do NOT output internal labels like "fact capsule", "response contract", or schema keys.

AVAILABLE TOOLS (call as needed for details beyond the brief):
get_recent_runs, get_calendar_day_context, get_efficiency_trend, get_plan_week,
get_weekly_volume, get_training_load, get_training_paces, get_correlations,
get_race_predictions, get_recovery_status, get_active_insights, get_pb_patterns,
get_efficiency_by_zone, get_nutrition_correlations, get_best_runs,
compare_training_periods, get_coach_intent_snapshot, set_coach_intent_snapshot,
get_training_prescription_window, get_wellness_trends, get_athlete_profile,
get_training_load_history, compute_running_math, analyze_run_streams

TOOL OUTPUTS: Each tool returns a "narrative" field — a pre-interpreted summary. Coach from the narrative, not the raw JSON.

COMMUNICATION STYLE:
- Use plain English. No acronyms (say "fitness level" not "CTL", "fatigue" not "ATL", "form" not "TSB").
- Never say "RPI" — always say "RPI" (Running Performance Index).
- If you make an error, correct it briefly and move on. No groveling. Just "You're right" and the correct answer.
- Concise. Answer the question, give the evidence, recommend the action.
- Use the athlete's preferred units (check the brief).
- If the athlete is venting, empathize briefly, then offer data-backed perspective.
- Never recommend medical advice — refer to healthcare professionals.

WEEK BOUNDARY AWARENESS:
- Current week data is PARTIAL — the brief marks it clearly. Do NOT treat partial week totals as complete weeks.
- "Last week" = the most recent COMPLETED week, not the in-progress week.

ATHLETE BRIEF:
{athlete_brief}"""

        # Build conversation contents (last 5 exchanges = 10 messages)
        contents = []
        if conversation_context:
            for msg in conversation_context[-10:]:
                role = "user" if msg.get("role") == "user" else "model"
                contents.append(genai_types.Content(
                    role=role,
                    parts=[genai_types.Part(text=msg.get("content", ""))]
                ))
        
        # Add current message
        contents.append(genai_types.Content(
            role="user",
            parts=[genai_types.Part(text=message)]
        ))
        
        try:
            total_input_tokens = 0
            total_output_tokens = 0
            
            # Configure generation
            # Temperature 0.2: Gemini docs recommend low temperature for
            # "more deterministic and reliable function calls". 0.7 caused
            # hallucination of training data (fabricated distances/volumes).
            config = genai_types.GenerateContentConfig(
                system_instruction=system_instruction,
                tools=[gemini_tools],
                max_output_tokens=COACH_MAX_OUTPUT_TOKENS,
                temperature=0.2,
            )
            
            # Send message with tools
            response = self.gemini_client.models.generate_content(
                model="gemini-2.5-flash",
                contents=contents,
                config=config,
            )
            
            # Track usage
            if hasattr(response, 'usage_metadata'):
                total_input_tokens += getattr(response.usage_metadata, 'prompt_token_count', 0)
                total_output_tokens += getattr(response.usage_metadata, 'candidates_token_count', 0)
            
            # Handle function calls in a loop (max 5 iterations)
            for _ in range(5):
                # Check if there are function calls to process
                function_calls = []
                if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
                    for part in response.candidates[0].content.parts:
                        if hasattr(part, 'function_call') and part.function_call:
                            function_calls.append(part.function_call)
                
                if not function_calls:
                    break
                
                # Add assistant response to contents
                contents.append(response.candidates[0].content)
                
                # Execute function calls and build responses
                function_response_parts = []
                for fc in function_calls:
                    tool_name = fc.name
                    tool_args = dict(fc.args) if fc.args else {}
                    
                    logger.info(f"Gemini calling tool: {tool_name} with {tool_args}")
                    result = self._execute_opus_tool(athlete_id, tool_name, tool_args)
                    
                    function_response_parts.append(
                        genai_types.Part(
                            function_response=genai_types.FunctionResponse(
                                name=tool_name,
                                response={"result": result}
                            )
                        )
                    )
                
                # Add function results to contents
                contents.append(genai_types.Content(
                    role="user",
                    parts=function_response_parts
                ))
                
                # Send function results back
                response = self.gemini_client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=contents,
                    config=config,
                )
                
                if hasattr(response, 'usage_metadata'):
                    total_input_tokens += getattr(response.usage_metadata, 'prompt_token_count', 0)
                    total_output_tokens += getattr(response.usage_metadata, 'candidates_token_count', 0)
            
            # Extract final response text
            response_text = ""
            for part in response.candidates[0].content.parts:
                if hasattr(part, 'text') and part.text:
                    response_text += part.text
            
            # Track usage with Gemini pricing
            self.track_usage(
                athlete_id=athlete_id,
                input_tokens=total_input_tokens,
                output_tokens=total_output_tokens,
                model=self.MODEL_DEFAULT,
                is_opus=False,
            )
            
            logger.info(
                f"Gemini query completed: athlete={athlete_id}, "
                f"input_tokens={total_input_tokens}, output_tokens={total_output_tokens}"
            )
            
            return {
                "response": response_text,
                "error": False,
                "model": self.MODEL_DEFAULT,
                "is_high_stakes": False,
                "input_tokens": total_input_tokens,
                "output_tokens": total_output_tokens,
            }
            
        except Exception as e:
            logger.error(f"Gemini query failed for {athlete_id}: {e}")
            return {
                "response": "Coach is temporarily unavailable. Please try again in a moment.",
                "error": True,
                "error_detail": str(e),
            }

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
        Get or create a conversation session for an athlete using PostgreSQL (CoachChat).

        Returns:
            (chat_id_str, created_new)
        """
        try:
            # Find the most recent active open chat session
            chat = (
                self.db.query(CoachChat)
                .filter(
                    CoachChat.athlete_id == athlete_id,
                    CoachChat.context_type == "open",
                    CoachChat.is_active == True,
                )
                .order_by(CoachChat.updated_at.desc())
                .first()
            )
            if chat:
                return str(chat.id), False

            # Create a new chat session
            chat = CoachChat(
                athlete_id=athlete_id,
                context_type="open",
                messages=[],
                is_active=True,
            )
            self.db.add(chat)
            self.db.commit()
            return str(chat.id), True
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to get/create coach chat session: {e}")
            return None, False

    def get_thread_history(self, athlete_id: UUID, limit: int = 100) -> Dict[str, Any]:
        """
        Fetch persisted coach conversation messages from PostgreSQL (CoachChat).

        Returns:
            {"thread_id": str|None, "messages": [{"role","content","created_at"}]}
        """
        limit = max(1, min(int(limit), 500))

        try:
            chat = (
                self.db.query(CoachChat)
                .filter(
                    CoachChat.athlete_id == athlete_id,
                    CoachChat.context_type == "open",
                    CoachChat.is_active == True,
                )
                .order_by(CoachChat.updated_at.desc())
                .first()
            )
            if not chat or not chat.messages:
                return {"thread_id": str(chat.id) if chat else None, "messages": []}

            # Messages are stored chronologically in the JSONB array.
            # Return the last `limit` messages.
            all_msgs = chat.messages or []
            recent = all_msgs[-limit:] if len(all_msgs) > limit else all_msgs

            out: List[Dict[str, Any]] = []
            for m in recent:
                content = m.get("content", "")
                # Production-beta: hide internal context injections from UI/history.
                if (content or "").startswith("INTERNAL COACH CONTEXT"):
                    continue
                out.append({
                    "role": m.get("role", "assistant"),
                    "content": content,
                    "created_at": m.get("timestamp") or m.get("created_at"),
                })

            return {"thread_id": str(chat.id), "messages": out}
        except Exception as e:
            logger.warning(f"Failed to read coach chat history: {e}")
            return {"thread_id": None, "messages": []}

    def _save_chat_messages(self, athlete_id: UUID, user_message: str, assistant_response: str) -> None:
        """Save user message and assistant response to PostgreSQL CoachChat."""
        try:
            chat = (
                self.db.query(CoachChat)
                .filter(
                    CoachChat.athlete_id == athlete_id,
                    CoachChat.context_type == "open",
                    CoachChat.is_active == True,
                )
                .order_by(CoachChat.updated_at.desc())
                .first()
            )
            if not chat:
                chat = CoachChat(
                    athlete_id=athlete_id,
                    context_type="open",
                    messages=[],
                    is_active=True,
                )
                self.db.add(chat)

            now_iso = datetime.utcnow().replace(microsecond=0).isoformat()
            msgs = list(chat.messages or [])
            msgs.append({"role": "user", "content": user_message, "timestamp": now_iso})
            msgs.append({"role": "assistant", "content": assistant_response, "timestamp": now_iso})
            chat.messages = msgs
            # Force SQLAlchemy to detect the JSONB change
            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(chat, "messages")
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            logger.warning(f"Failed to save coach chat messages: {e}")
    
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
        if athlete.rpi:
            context_parts.append(f"Current RPI: {athlete.rpi:.1f}")
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
                    efficiency = pace_km / a.avg_hr  # pace/HR ratio (directionally ambiguous — see OutputMetricMeta)
                    efficiencies.append(efficiency)
            
            context_parts.append(f"Runs: {run_count} | Distance: {total_distance:.0f} km | Avg/week: {avg_weekly:.0f} km")
            
            if efficiencies:
                avg_eff = sum(efficiencies) / len(efficiencies)
                context_parts.append(f"Average efficiency: {avg_eff:.3f} (pace/HR ratio — directionally ambiguous, do not assume lower=better)")
        
        # --- Recent Check-ins ---
        recent_checkins = self.db.query(DailyCheckin).filter(
            DailyCheckin.athlete_id == athlete_id,
            DailyCheckin.date >= seven_days_ago
        ).order_by(DailyCheckin.date.desc()).limit(3).all()
        
        if recent_checkins:
            context_parts.append("\n## Recent Wellness")
            for c in recent_checkins:
                parts = []
                if c.motivation_1_5 is not None:
                    motivation_map = {5: 'Great', 4: 'Fine', 2: 'Tired', 1: 'Rough'}
                    parts.append(f"Feeling: {motivation_map.get(c.motivation_1_5, c.motivation_1_5)}")
                if c.sleep_h is not None:
                    parts.append(f"Sleep: {c.sleep_h}h")
                if c.stress_1_5 is not None:
                    parts.append(f"Stress: {c.stress_1_5}/5")
                if c.soreness_1_5 is not None:
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

    def get_dynamic_suggestions(self, athlete_id: UUID) -> List[Dict[str, str]]:
        """
        Return 3-5 data-driven suggested questions as structured objects.
        
        Each suggestion has:
        - title: Short, specific, data-driven headline
        - description: One sentence of context with actual numbers
        - prompt: Internal payload sent to the LLM (invisible to user)
        
        Sources:
        - coach_tools.get_active_insights (prioritized insights)
        - coach_tools.get_pb_patterns (recent PBs)
        - coach_tools.get_training_load (TSB state)
        - coach_tools.get_efficiency_by_zone (efficiency trends)
        - Recent activities
        - Goal race countdown
        """
        suggestions: List[Dict[str, str]] = []
        seen_titles: set = set()

        def add(title: str, description: str, prompt: str) -> None:
            if title and title not in seen_titles and len(suggestions) < 5:
                seen_titles.add(title)
                suggestions.append({"title": title, "description": description, "prompt": prompt})

        today = date.today()

        # --- 1. Recent activity (highest priority — just ran) ---
        try:
            start_of_today = datetime.combine(today, datetime.min.time())
            completed_today = (
                self.db.query(Activity)
                .filter(
                    Activity.athlete_id == athlete_id,
                    Activity.sport == "run",
                    Activity.start_time >= start_of_today,
                )
                .order_by(Activity.start_time.desc())
                .first()
            )
            if completed_today:
                dist_mi = (completed_today.distance_m or 0) / 1609.34
                dur_min = (completed_today.duration_s or 0) / 60
                pace_min = dur_min / dist_mi if dist_mi > 0 else 0
                pace_str = f"{int(pace_min)}:{int((pace_min % 1) * 60):02d}/mi" if dist_mi > 0 else "?"
                add(
                    f"Today's {dist_mi:.1f}mi run",
                    f"{pace_str} over {dist_mi:.1f}mi — what did it do for your build?",
                    f"What effect did today's run have on my fitness and fatigue? Was the effort appropriate for where I am in my training? What should I do tomorrow based on how today loaded me?",
                )
        except Exception:
            pass

        # --- 2. TSB-driven (current state) ---
        try:
            result = coach_tools.get_training_load(self.db, athlete_id)
            if result.get("ok"):
                data = result.get("data", {})
                tsb = data.get("tsb")
                atl = data.get("atl")
                ctl = data.get("ctl")
                zone = data.get("tsb_zone_label", "")
                if tsb is not None and atl is not None and ctl is not None:
                    if tsb > 20:
                        add(
                            f"TSB is +{tsb:.0f} — you're fresh",
                            f"CTL {ctl:.0f}, ATL {atl:.0f}. Ready for a hard session?",
                            "I'm feeling fresh. What's the best way to capitalize on this freshness — should I push a quality session, or is there a strategic reason to stay easy? What does my recent training suggest I'm ready for?",
                        )
                    elif tsb < -30:
                        add(
                            f"TSB is {tsb:.0f} — deep fatigue",
                            f"ATL {atl:.0f} vs CTL {ctl:.0f}. Should we ease up?",
                            "I'm carrying a lot of fatigue. Is this productive overreach that's building fitness, or am I digging a hole? What's the risk if I keep pushing, and what would a smart next 48-72 hours look like?",
                        )
                    else:
                        label = f" ({zone})" if zone else ""
                        add(
                            f"TSB is {tsb:.0f}{label}",
                            f"CTL {ctl:.0f}, ATL {atl:.0f}. Where am I in the build?",
                            "Where am I in my training build right now? Am I absorbing the load well or showing signs of stagnation? What should the next week look like to keep progressing without overreaching?",
                        )
        except Exception:
            pass

        # --- 3. Goal race countdown ---
        try:
            athlete = self.db.query(Athlete).filter(Athlete.id == athlete_id).first()
            if athlete and athlete.goal_race_date:
                days_out = (athlete.goal_race_date - today).days
                race_name = athlete.goal_race_name or "goal race"
                if 0 < days_out <= 120:
                    add(
                        f"{days_out} days to {race_name}",
                        "Are you on track? What should the next few weeks look like?",
                        f"With {days_out} days until {race_name}, am I on track? Based on my current fitness, fatigue, and recent training quality — what's the honest assessment of where I'll be on race day, and what should I prioritize in the remaining weeks?",
                    )
        except Exception:
            pass

        # --- 4. PB-driven ---
        try:
            result = coach_tools.get_pb_patterns(self.db, athlete_id)
            if result.get("ok"):
                data = result.get("data") or {}
                pbs = data.get("pbs", [])
                pb_count = data.get("pb_count", 0)
                
                if pbs:
                    # Most recent PB
                    most_recent = max(pbs, key=lambda p: p.get("date", ""))
                    cat = most_recent.get("category", "?")
                    pb_date = most_recent.get("date", "")
                    tsb_before = most_recent.get("tsb_day_before")
                    
                    # Format time
                    time_s = most_recent.get("time_seconds", 0)
                    if time_s:
                        mins = int(time_s) // 60
                        secs = int(time_s) % 60
                        time_str = f"{mins}:{secs:02d}"
                    else:
                        time_str = ""
                    
                    tsb_str = f" at TSB {tsb_before:.0f}" if tsb_before is not None else ""
                    date_str = pb_date[:10] if pb_date else ""
                    
                    if pb_count >= 2:
                        add(
                            f"{cat} PR — {time_str}" if time_str else f"{cat} PR on {date_str}",
                            f"Set on {date_str}{tsb_str}. What pattern led to your {pb_count} PRs?",
                            f"I've set {pb_count} PRs. Is there a pattern — a fatigue level, a type of training block, a volume sweet spot — that consistently produces my best performances? What can I learn from this to chase the next one?",
                        )
                    elif time_str:
                        add(
                            f"{cat} PR — {time_str}",
                            f"Set on {date_str}{tsb_str}. What can you tell me about it?",
                            f"I PR'd my {cat} with {time_str}. What in my recent training set that up? Was it the volume, the workouts, the taper, the freshness? And what does it tell me about where my fitness actually is right now?",
                        )
        except Exception:
            pass

        # --- 5. Insights ---
        try:
            result = coach_tools.get_active_insights(self.db, athlete_id, limit=3)
            if result.get("ok"):
                for ins in result.get("data", {}).get("insights", []):
                    title = ins.get("title") or ""
                    if not title:
                        continue
                    title_lower = title.lower()
                    if "improving" in title_lower:
                        add(title, "What's driving this improvement?", f"My data shows: {title}. What in my training is driving this, and how do I keep it going without overdoing it?")
                    elif "declining" in title_lower or "drop" in title_lower:
                        add(title, "Should we investigate this trend?", f"My data shows: {title}. Should I be concerned? Is this a normal training phase or a sign I need to change something? What would you recommend?")
                    elif "risk" in title_lower or "warning" in title_lower:
                        add(title, "What should I do about this?", f"My data flagged: {title}. How serious is this, what's causing it, and what concrete steps should I take in the next few days?")
                    else:
                        add(title, "Tell me more about this.", f"My data shows: {title}. What does this mean for my training, and is there anything I should do differently?")
        except Exception:
            pass

        # --- 6. Efficiency trend ---
        try:
            result = coach_tools.get_efficiency_by_zone(self.db, athlete_id, "threshold", 90)
            if result.get("ok"):
                data = result.get("data", {})
                trend = data.get("recent_trend_pct")
                current = data.get("current_efficiency")
                if trend is not None:
                    if trend < -10:
                        add(
                            f"Threshold efficiency improving {abs(trend):.0f}%",
                            f"Current: {current:.1f}. What's changing in your runs?" if current else "What's changing in your runs?",
                            "My threshold efficiency is improving. What's driving this — is it the volume, the workout structure, better recovery, or just accumulated fitness? How do I keep this trajectory going?",
                        )
                    elif trend > 10:
                        add(
                            f"Threshold efficiency down {trend:.0f}%",
                            f"Current: {current:.1f}. Worth investigating." if current else "Worth investigating.",
                            "My threshold efficiency is declining. Is this accumulated fatigue that will resolve with rest, or a sign that something in my training needs to change? What specific runs show the drop-off?",
                        )
        except Exception:
            pass

        # --- Fallback ---
        if len(suggestions) < 2:
            add(
                "How's my training going?",
                "A full read on your recent runs, load, and trajectory.",
                "Give me an honest assessment of my training. Am I building fitness, stagnating, or running myself into the ground? What's going well, what concerns you, and what would you change in the next 7 days?",
            )

        return suggestions[:5]

    def classify_query_complexity(self, message: str) -> str:
        """
        Classify query complexity for model routing (Phase 11 - ADR-060, updated for 90/10).
        
        Returns: 'low', 'medium', or 'high'
        
        HIGH = Causal OR ambiguity OR multi-factor (any one triggers Opus)
        MEDIUM = Standard coaching (rule-based with data)
        LOW = Pure lookups/definitions (no reasoning needed)
        
        Target: ~10% of queries should be HIGH (90% mini, 10% Opus)
        """
        message_lower = (message or "").lower()
        
        # LOW: Pure data retrieval, no reasoning
        low_patterns = [
            "what was my", "show me", "list my", "how far did i",
            "yesterday", "last run", "this week's", "my last",
            "what is a", "what does", "define", "what is my",
            "personal best", "pb", "pr", "my pbs",
            "what's my tsb", "what's my ctl", "what's my atl",
            "show my plan", "recent runs", "my race predictions",
            "recovery status",
        ]
        if any(p in message_lower for p in low_patterns):
            return "low"
        
        # HIGH: Any ONE of these signals triggers Opus for better reasoning
        # (Updated from AND to OR logic for 90/10 split)
        
        # 1. Causal/synthesis questions - require real reasoning
        causal_patterns = [
            "why am i", "why is my", "why do i", "why does my",
            "what's causing", "what's driving", "what caused",
            "what's holding", "what explains", "biggest factor",
            "main driver", "what's the one thing", "what's wrong",
            "what am i doing wrong", "what should i change",
            "how do i improve", "how can i get faster",
            "what's limiting", "what's preventing",
        ]
        if any(p in message_lower for p in causal_patterns):
            return "high"
        
        # 2. Ambiguity/confusion signals - need nuanced response
        ambiguity_signals = [
            "but", "despite", "even though", "however", "yet",
            "although", "not sure", "confused", "doesn't make sense",
            "i thought", "shouldn't it", "expected", "supposed to",
            "weird", "strange", "odd", "counterintuitive",
        ]
        if any(s in message_lower for s in ambiguity_signals):
            return "high"
        
        # 3. Multiple factors in one query - needs synthesis
        has_multiple_factors = (
            message_lower.count(" and ") >= 2 or
            message_lower.count(",") >= 2
        )
        if has_multiple_factors:
            return "high"
        
        # 4. Complex planning/decision queries - require judgment
        # Note: "should i" alone is too broad (catches "What pace should I run")
        # Only trigger on decision-making patterns with explicit uncertainty
        planning_patterns = [
            "should i skip", "should i rest", "should i take",
            "should i reduce", "should i increase", "should i change",
            "is it okay to run", "is it safe to",
            "would it be wise", "would it be better",
            "given that", "considering that", "taking into account",
            "what if i skip", "what if i run",
        ]
        if any(p in message_lower for p in planning_patterns):
            return "high"
        
        # MEDIUM: Everything else (standard coaching)
        return "medium"
    
    # Legacy alias for backward compatibility
    def classify_query(self, message: str) -> str:
        """Legacy: map new complexity to old simple/standard."""
        complexity = self.classify_query_complexity(message)
        return "simple" if complexity == "low" else "standard"

    def get_model_for_query(self, query_type: str, athlete_id: Optional[UUID] = None, message: str = "") -> Tuple[str, bool]:
        """
        Select model based on query content and athlete tier (ADR-061: Hybrid architecture).
        
        Routing logic - Opus for queries that MATTER:
        1. High-stakes queries (injury/pain/load) → Opus (liability risk)
        2. High-complexity queries (causal + ambiguity) → Opus (needs real reasoning)
        3. Everything else → GPT-4o-mini
        
        VIP athletes get 10× Opus allocation but same routing rules.
        
        Args:
            query_type: Legacy 'simple'/'standard' or new 'low'/'medium'/'high'
            athlete_id: Optional athlete ID for VIP and budget check
            message: Original message for classification
            
        Returns:
            Tuple of (model_name, is_opus)
        """
        # Check if high-stakes routing is enabled
        if not self.high_stakes_routing_enabled:
            return self.MODEL_DEFAULT, False
        
        # Free users always get GPT-4o-mini (no Opus for unpaid)
        if athlete_id:
            athlete = self.db.query(Athlete).filter(Athlete.id == athlete_id).first()
            if athlete and not getattr(athlete, "has_active_subscription", False):
                return self.MODEL_DEFAULT, False
        
        # Determine if query needs Opus (high-stakes OR high-complexity)
        is_high_stakes = is_high_stakes_query(message)
        complexity = self.classify_query_complexity(message)
        is_high_complexity = complexity == "high"
        
        # Route to Opus if either condition is true
        needs_opus = is_high_stakes or is_high_complexity
        
        if needs_opus and athlete_id:
            # Check Opus budget (VIP gets 10× allocation via check_budget)
            is_vip = self.is_athlete_vip(athlete_id)
            allowed, reason = self.check_budget(athlete_id, is_opus=True, is_vip=is_vip)
            
            if allowed and self.anthropic_client:
                logger.info(
                    f"Routing to Opus: is_high_stakes={is_high_stakes}, "
                    f"is_high_complexity={is_high_complexity}, is_vip={is_vip}"
                )
                return self.MODEL_HIGH_STAKES, True
            else:
                # Fallback to Gemini when Opus unavailable/budget exhausted
                logger.info(f"Opus fallback to Gemini: reason={reason}, has_anthropic={bool(self.anthropic_client)}")
                return self.MODEL_DEFAULT, False
        
        # Default: Gemini 2.5 Flash
        return self.MODEL_DEFAULT, False
    
    def get_model_for_query_legacy(self, query_type: str, athlete_id: Optional[UUID] = None, message: str = "") -> str:
        """
        Legacy method for backward compatibility.
        Returns just the model name (not the tuple).
        """
        model, _ = self.get_model_for_query(query_type, athlete_id, message)
        return model
    
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
        # If no LLM client is available, return a helpful message
        if not self.gemini_client:
            return {
                "response": "AI Coach is not configured. Please set GOOGLE_AI_API_KEY in your environment.",
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

        # ADR-16: Removed canned return-scope-clarification guardrail.
        # The rich athlete brief gives the LLM all the context it needs.
        if False and self._needs_return_scope_clarification(lower):
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
        
        # Gate 1: Use MessageRouter for classification (Phase 4 modular)
        msg_type, _skip_deterministic_shortcuts = self.router.classify(message)
        
        # OVERRIDE: Always skip deterministic shortcuts - let LLM synthesize all responses
        # for natural, contextualized, human-readable output. The shortcuts returned
        # raw data dumps that were hard to read and lacked coaching nuance.
        _skip_deterministic_shortcuts = True
        
        # ADR-16: Removed canned clarification gate. The LLM with a rich brief
        # handles return-from-injury context naturally.
        if False and msg_type == MessageType.CLARIFICATION_NEEDED:
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
# DISABLED:             if req_days >= 7 and (snap_stale or (snap_data.get("weekly_mileage_target") is None and snap_data.get("time_available_min") is None)):
# DISABLED:                 thread_id, _ = self.get_or_create_thread_with_state(athlete_id)
# DISABLED:                 return {
# DISABLED:                     "response": (
# DISABLED:                         "## Answer\n"
# DISABLED:                         "To make this **self-guided** (not imposed), give me one constraint and I’ll generate an exact 7‑day microcycle.\n\n"
# DISABLED:                         "Pick one:\n"
# DISABLED:                         "- Target weekly mileage (e.g. `45 mpw`), or\n"
# DISABLED:                         "- Typical time available per day (e.g. `45 min`).\n\n"
# DISABLED:                         "Also: any pain signals (none / niggle / pain)?\n"
# DISABLED:                     ),
# DISABLED:                     "thread_id": thread_id,
# DISABLED:                     "error": False,
# DISABLED:                 }

            # For weekly requests (7+ days), fall through to LLM for better formatting.
            # The LLM will use the prescription tool and synthesize a human-readable summary.
            if req_days >= 7:
                pass  # Fall through to LLM processing below
            else:
                # Single-day deterministic shortcut (e.g., "what should I run today?")
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
            # ADR-061: Hybrid model routing with cost caps
            complexity = self.classify_query_complexity(message)
            model, is_opus = self.get_model_for_query(complexity, athlete_id=athlete_id, message=message)
            is_vip = self.is_athlete_vip(athlete_id)
            is_high_stakes = is_high_stakes_query(message)

            # Log model selection for cost tracking
            is_high_complexity = complexity == "high"
            logger.info(
                f"Coach query: complexity={complexity}, model={model}, is_opus={is_opus}, "
                f"is_vip={is_vip}, is_high_stakes={is_high_stakes}, is_high_complexity={is_high_complexity}"
            )
            
            # Check overall budget before proceeding
            budget_ok, budget_reason = self.check_budget(athlete_id, is_opus=is_opus, is_vip=is_vip)
            if not budget_ok:
                logger.warning(f"Budget exceeded for {athlete_id}: {budget_reason}")
                return {
                    "response": (
                        "You've reached your daily coaching limit. "
                        "Your limit resets at midnight UTC. "
                        "For urgent questions, please consult a healthcare professional."
                    ),
                    "error": False,
                    "budget_exceeded": True,
                    "budget_reason": budget_reason,
                }
            
            # ADR-061: Route high-stakes queries to Opus (direct API, not Assistants)
            if is_opus and self.anthropic_client:
                # Build athlete state for Opus context
                athlete_state = self._build_athlete_state_for_opus(athlete_id)
                
                # Get recent conversation context
                thread_id, _ = self.get_or_create_thread_with_state(athlete_id)
                conversation_context = []
                if thread_id:
                    try:
                        history_data = self.get_thread_history(athlete_id, limit=10)
                        history = history_data.get("messages", [])
                        conversation_context = [
                            {"role": m.get("role"), "content": m.get("content")}
                            for m in history if m.get("role") in ("user", "assistant")
                        ]
                    except Exception:
                        pass
                
                # Query Opus directly
                opus_result = await self.query_opus(
                    athlete_id=athlete_id,
                    message=message,
                    athlete_state=athlete_state,
                    conversation_context=conversation_context,
                )
                
                # Save to PostgreSQL (CoachChat) for conversation continuity
                if not opus_result.get("error"):
                    self._save_chat_messages(athlete_id, message, opus_result.get("response", ""))
                
                opus_result["thread_id"] = thread_id
                return opus_result

            # Route default queries to Gemini 2.5 Flash (Feb 2026 migration)
            if model == self.MODEL_DEFAULT and self.gemini_client:
                # ADR-16: Brief is now built inside query_gemini() — no separate athlete_state needed
                athlete_state = ""  # Legacy param, brief is injected in query_gemini
                
                # Get recent conversation context
                thread_id, _ = self.get_or_create_thread_with_state(athlete_id)
                conversation_context = []
                if thread_id:
                    try:
                        history_data = self.get_thread_history(athlete_id, limit=10)
                        history = history_data.get("messages", [])
                        conversation_context = [
                            {"role": m.get("role"), "content": m.get("content")}
                            for m in history if m.get("role") in ("user", "assistant")
                        ]
                    except Exception:
                        pass
                
                # Query Gemini
                gemini_result = await self.query_gemini(
                    athlete_id=athlete_id,
                    message=message,
                    athlete_state=athlete_state,
                    conversation_context=conversation_context,
                )
                
                # Gemini returned a result (success or error)
                if not gemini_result.get("error"):
                    # Normalize for UI + trust contract (Coach Output Contract v1):
                    # - strip internal labels (fact capsule, response contract, etc.)
                    # - prefer "## Evidence" section naming
                    # - suppress UUID spam unless explicitly requested
                    raw_response = gemini_result.get("response", "")
                    try:
                        normalized = self._normalize_response_for_ui(
                            user_message=message,
                            assistant_message=raw_response,
                        )
                        gemini_result["response"] = normalized
                    except Exception as e:
                        logger.warning(f"Coach response normalization failed: {e}")

                    # Save to PostgreSQL (CoachChat) for conversation continuity
                    self._save_chat_messages(athlete_id, message, gemini_result.get("response", ""))
                
                gemini_result["thread_id"] = thread_id
                return gemini_result

            # Safety net: any unhandled model routes to Gemini if available
            if self.gemini_client:
                logger.warning(f"Unhandled model '{model}' — routing to Gemini as safety net")
                thread_id, _ = self.get_or_create_thread_with_state(athlete_id)
                conversation_context = []
                if thread_id:
                    try:
                        history_data = self.get_thread_history(athlete_id, limit=10)
                        history = history_data.get("messages", [])
                        conversation_context = [
                            {"role": m.get("role"), "content": m.get("content")}
                            for m in history if m.get("role") in ("user", "assistant")
                        ]
                    except Exception:
                        pass
                gemini_result = await self.query_gemini(
                    athlete_id=athlete_id,
                    message=message,
                    athlete_state="",
                    conversation_context=conversation_context,
                )
                if not gemini_result.get("error"):
                    raw_response = gemini_result.get("response", "")
                    try:
                        normalized = self._normalize_response_for_ui(
                            user_message=message,
                            assistant_message=raw_response,
                        )
                        gemini_result["response"] = normalized
                    except Exception as e:
                        logger.warning(f"Coach response normalization failed: {e}")
                    self._save_chat_messages(athlete_id, message, gemini_result.get("response", ""))
                gemini_result["thread_id"] = thread_id
                return gemini_result

            return {
                "response": "Coach is temporarily unavailable. Please try again in a moment.",
                "error": True,
                "thread_id": None,
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

            # Weekly mileage target (mpw) - expanded to catch more patterns
            m2 = re.search(r"\b(\d{2,3})\s*(mpw|miles per week|mi per week|miles?\s+(?:this|per|a)\s+week|this week)\b", ml)
            if m2:
                try:
                    updates["weekly_mileage_target"] = float(m2.group(1))
                except Exception:
                    pass
            # Also catch "running 55 this week" pattern
            if not m2:
                m2b = re.search(r"running\s+(\d{2,3})\s+(?:this|per|a)\s+week", ml)
                if m2b:
                    try:
                        updates["weekly_mileage_target"] = float(m2b.group(1))
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
    # PHASE 2 CONTEXT ARCHITECTURE: Dynamic run instructions (not user messages)
    # -------------------------------------------------------------------------
    def _build_run_instructions(self, athlete_id: UUID, message: str, model: str = "gpt-4o-mini") -> str:
        """
        Build per-run instructions based on message type and athlete state.
        
        Phase 2: These go into `additional_instructions` on the run, NOT as user messages.
        Benefits:
        - System-level instructions (higher priority than user messages)
        - Don't pollute thread history
        - Always fresh for each run
        - Can include athlete-specific context
        
        Sprint 4: For mini, keep instructions simple. Complex instructions go to Opus only.
        
        Args:
            athlete_id: The athlete's ID
            message: The user's message
            model: The model being used (for simplification decisions)
        
        Returns a string to be passed to runs.create(additional_instructions=...).
        """
        instructions: List[str] = []
        ml = (message or "").lower()
        is_mini = model == "gpt-4o-mini"
        
        # -------------------------------------------------------------------------
        # 0. ALWAYS require tool calls for data questions (fixes mini skipping tools)
        # -------------------------------------------------------------------------
        data_keywords = [
            "run", "mile", "km", "pace", "hr", "heart rate", "distance",
            "week", "today", "yesterday", "long run", "tempo", "easy",
            "training", "plan", "workout", "mileage", "volume",
            "tired", "fatigue", "recovery", "load", "fitness",
            "longest", "fastest", "slowest", "best", "worst",
            "build", "race", "goal", "target",
        ]
        is_data_question = any(kw in ml for kw in data_keywords)
        
        if is_data_question:
            instructions.append(
                "TOOL CALL REQUIRED: This question is about training data. "
                "You MUST call get_recent_runs or get_training_load BEFORE answering. "
                "Do NOT respond without first calling a tool to get actual data. "
                "If you answer without calling tools, your response will be rejected."
            )
            
            # Sprint 3: Prefetch recent runs to reduce reliance on tool calls
            # This gives mini the data it needs even if it forgets to call tools
            try:
                recent = coach_tools.get_recent_runs(self.db, athlete_id, days=7)
                if recent and not recent.get("error") and recent.get("data"):
                    runs = recent.get("data", [])
                    if runs:
                        # Compact summary for injection
                        run_summary = []
                        total_distance = 0
                        for r in runs[:7]:  # Max 7 runs
                            dist = r.get("distance_mi") or r.get("distance_km", 0)
                            pace = r.get("pace_per_mi") or r.get("pace_per_km", "")
                            name = r.get("name", "Run")
                            date = r.get("date", "")[:10] if r.get("date") else ""
                            if dist:
                                total_distance += float(dist) if isinstance(dist, (int, float, str)) and str(dist).replace('.','').isdigit() else 0
                                run_summary.append(f"{date}: {name} - {dist}mi @ {pace}")
                        
                        if run_summary:
                            instructions.append(
                                f"PREFETCHED DATA (last 7 days):\n" +
                                "\n".join(run_summary[:5]) +
                                f"\nTotal: ~{total_distance:.1f}mi in {len(runs)} runs\n"
                                "Use this data directly. You may still call tools for more detail."
                            )
            except Exception as e:
                logger.debug(f"Could not prefetch recent runs: {e}")
        
        # -------------------------------------------------------------------------
        # 1. Always include current training state (ATL/CTL/TSB)
        # -------------------------------------------------------------------------
        try:
            load = coach_tools.get_training_load(self.db, athlete_id)
            if load and not load.get("error"):
                atl = load.get("atl", 0)
                ctl = load.get("ctl", 0)
                tsb = load.get("tsb", 0)
                form_state = "fresh" if tsb > 10 else ("fatigued" if tsb < -10 else "balanced")
                instructions.append(
                    f"CURRENT TRAINING STATE: fatigue level={atl:.1f}, fitness level={ctl:.1f}, form={tsb:.1f} ({form_state}). "
                    f"Use plain English (fatigue, fitness, form) - NEVER use acronyms like ATL/CTL/TSB in your response."
                )
        except Exception as e:
            logger.debug(f"Could not fetch training load for run instructions: {e}")
        
        # -------------------------------------------------------------------------
        # 2. Question-type-specific instructions
        # Sprint 4: Simplify for mini - shorter, clearer instructions
        # -------------------------------------------------------------------------
        if self._is_judgment_question(message):
            if is_mini:
                # Simplified for mini
                instructions.append(
                    "ANSWER DIRECTLY: Give your yes/no/maybe first, then explain briefly."
                )
            else:
                instructions.append(
                    "CRITICAL JUDGMENT INSTRUCTION: The athlete is asking for your JUDGMENT or OPINION. "
                    "You MUST answer DIRECTLY first (yes/no/maybe with a confidence level like 'likely', 'unlikely', "
                    "'very possible'), THEN provide supporting evidence and any caveats. "
                    "Do NOT deflect, ask for constraints, or pivot to 'self-guided mode'. "
                    "Give your honest assessment based on their data."
                )
        
        if self._has_return_context(ml):
            if is_mini:
                instructions.append("RETURN CONTEXT: Compare to post-return period only. Be conservative.")
            else:
                instructions.append(
                    "RETURN-FROM-INJURY CONTEXT: This athlete mentioned returning from injury/break. "
                    "All comparisons should DEFAULT to the post-return period unless they explicitly specify otherwise. "
                    "Do NOT compare against pre-injury peaks without asking first. "
                    "Favor conservative load recommendations (10-15% weekly increases)."
                )
        
        # Check for benchmark references (past PR, race shape, etc.)
        # Skip for mini to reduce instruction overhead
        if not is_mini:
            benchmark_indicators = (
                "marathon shape", "race shape", "pb shape", "pr shape",
                "peak form", "was in", "used to run", "i ran a", "my best",
                "when i was", "at my peak", "my pb", "my pr",
            )
            if any(b in ml for b in benchmark_indicators):
                instructions.append(
                    "BENCHMARK REFERENCE DETECTED: The athlete referenced a past benchmark (PR, race shape, peak form). "
                    "Compare their CURRENT metrics to that benchmark and provide specific numbers and timeline estimates. "
                    "Be honest about realistic recovery timelines based on their recent training load and patterns."
                )
        
        # Prescription mode guidance
        if self._is_prescription_request(message):
            if is_mini:
                instructions.append("PRESCRIPTION: Max 20% volume increase. Check form before intensity.")
            else:
                instructions.append(
                    "PRESCRIPTION REQUEST: The athlete wants workout guidance. "
                    "Use conservative bounds: do not prescribe more than 20% weekly volume increase, "
                    "check TSB before intensity recommendations, and prioritize injury prevention."
                )
        
        # -------------------------------------------------------------------------
        # 3. Include prior context summary (flags and recent window)
        # Sprint 4: Skip context injection for mini (keep it lean)
        # -------------------------------------------------------------------------
        if not is_mini:
            try:
                context_injection = self._build_context_injection_for_message(athlete_id=athlete_id, message=message)
                if context_injection:
                    instructions.append(context_injection)
            except Exception as e:
                logger.debug(f"Could not build context injection for run instructions: {e}")
        
        if not instructions:
            return ""
        
        header = "=== DYNAMIC RUN INSTRUCTIONS (Phase 2) ===\n"
        return header + "\n\n".join(instructions)

    # -------------------------------------------------------------------------
    # PHASE 1 ROUTING FIX: Judgment question detection (routes to LLM, not shortcuts)
    # -------------------------------------------------------------------------
    def _is_data_question(self, message: str) -> bool:
        """
        Check if a question is about training data and should have called tools.
        
        Used for tool validation (Sprint 2): if this returns True but no tools
        were called, the response is likely hallucinated.
        
        Returns True if this question requires data tools to answer correctly.
        """
        ml = (message or "").lower()
        
        # Data-related keywords that require tool calls
        data_keywords = [
            "run", "mile", "km", "pace", "hr", "heart rate", "distance",
            "week", "today", "yesterday", "long run", "tempo", "easy",
            "training", "plan", "workout", "mileage", "volume",
            "tired", "fatigue", "recovery", "load", "fitness",
            "longest", "fastest", "slowest", "best", "worst",
            "build", "race", "goal", "target", "compare", "progress",
            "average", "total", "how many", "how far", "how fast",
        ]
        
        # Exclude pure definition questions (don't need tools)
        definition_patterns = [
            "what is a ", "what does ", "define ", "explain ",
            "what's the difference between",
        ]
        if any(p in ml for p in definition_patterns):
            return False
        
        return any(kw in ml for kw in data_keywords)
    
    def _validate_tool_usage(
        self,
        message: str,
        tools_called: List[str],
        tool_calls_count: int,
    ) -> tuple[bool, str]:
        """
        Validate that a data question called appropriate tools.
        
        Returns:
            (is_valid, reason) - True if tool usage was appropriate, False with reason if not.
        """
        if not self._is_data_question(message):
            # Not a data question - no tool validation needed
            return True, "not_data_question"
        
        if tool_calls_count == 0:
            return False, "no_tools_called"
        
        # Check for core data tools
        data_tools = ["get_recent_runs", "get_training_load", "get_weekly_volume", "get_best_runs"]
        if not any(t in tools_called for t in data_tools):
            return False, "no_data_tools_called"
        
        return True, "ok"

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
                lines.append(f"FYI your current load: fatigue {atl:.0f}, fitness {ctl:.0f}, form {tsb:.0f} ({zone}).")
            else:
                lines.append(f"FYI your current load: fatigue {atl:.0f}, fitness {ctl:.0f}, form {tsb:.0f}.")

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
            lines.append(f"- {today}: Training load — fatigue {atl:.0f}, fitness {ctl:.0f}, form {tsb:.0f}")

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
                lines.append(f"- {today_iso}: Training load — fatigue {atl:.0f}, fitness {ctl:.0f}, form {tsb:.0f}")
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
                lines.append(f"- {today_iso}: Training load — fatigue {atl:.0f}, fitness {ctl:.0f}, form {tsb:.0f} ({zone_label})")
            else:
                lines.append(f"- {today_iso}: Training load — fatigue {atl:.0f}, fitness {ctl:.0f}, form {tsb:.0f}")

        return "\n".join(lines)

    _UUID_RE = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I)
    _DATE_RE = re.compile(r"\b20\d{2}-\d{2}-\d{2}\b")


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
        "since physical therapy",
        "physical therapy ended",
        "since pt",
        "after being injured",
        "after being sick",
        "after illness",
        "since being sick",
        # Phase 2 additions - more patterns
        "back from a break",
        "back from break",
        "i'm back from",
        "im back from",
    )

    def _has_return_context(self, lower_message: str) -> bool:
        ml = (lower_message or "").lower()
        return any(p in ml for p in self._RETURN_CONTEXT_PHRASES)

    def _looks_like_uncited_numeric_answer(self, text: str) -> bool:
        """
        Guardrail: detect uncited athlete metric claims (ATL, CTL, TSB, mileage, pace, efficiency).
        Returns True if text appears to cite athlete data without receipts; False for prescriptions or when receipts present.
        """
        t = (text or "").strip()
        if not t:
            return False
        lower = t.lower()
        # Receipts present: inline activity ref or Receipts block
        if "receipts:" in lower:
            return False
        if re.search(r"activity\s+[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", lower):
            return False
        # Prescription patterns: instructions (do 2 runs, run 30 min, 6x20s) - not metric claims
        if re.search(r"\b(do|run)\s+\d+\s+(easy|long|recovery)\s+run", lower):
            return False
        if re.search(r"run\s+\d+\s+min", lower) or re.search(r"\d+x\d+s?\s+strides?", lower):
            return False
        # Athlete metric claims: your ATL/CTL/TSB, you ran X miles, your pace, efficiency trend
        metric_signals = (
            "atl is", "ctl is", "tsb is", "atl:", "ctl:", "tsb:",
            "you ran", "your pace", "efficiency trend", "your atl", "your ctl", "your tsb",
        )
        return any(s in lower for s in metric_signals)

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

        # Phase 2: Pull more prior user messages (20 instead of 10) for better context.
        prior_user_messages: List[str] = []
        try:
            hist = self.get_thread_history(athlete_id, limit=40) or {}
            msgs = hist.get("messages") or []
            for m in msgs:
                if (m.get("role") or "").lower() != "user":
                    continue
                c = (m.get("content") or "").strip()
                if not c:
                    continue
                prior_user_messages.append(c)
                if len(prior_user_messages) >= 20:
                    break
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

    def _build_athlete_state_for_opus(self, athlete_id: UUID) -> str:
        """
        Build a compressed athlete state object for Opus context (ADR-061).
        
        This is the critical context injection for high-stakes queries.
        Kept minimal (~800 tokens) but includes all safety-relevant data.
        """
        from models import Athlete, Activity, DailyCheckin
        
        state_lines = []
        
        try:
            # Get athlete profile
            athlete = self.db.query(Athlete).filter(Athlete.id == athlete_id).first()
            if athlete:
                state_lines.append(f"Athlete: {athlete.display_name or 'Anonymous'}")
                if athlete.birthdate:
                    age = (date.today() - athlete.birthdate).days // 365
                    state_lines.append(f"Age: {age}")
                if athlete.sex:
                    state_lines.append(f"Sex: {athlete.sex}")
            
            # Get recent training load
            try:
                load_data = coach_tools.get_training_load(self.db, athlete_id)
                if load_data.get("ok"):
                    data = load_data.get("data", {})
                    state_lines.append(f"Fitness level: {data.get('ctl', 'N/A')}")
                    state_lines.append(f"Fatigue level: {data.get('atl', 'N/A')}")
                    state_lines.append(f"Current form: {data.get('tsb', 'N/A')}")
                    state_lines.append(f"Tau2 (recovery): {data.get('tau2_hours', 'N/A')}h")
            except Exception:
                pass
            
            # Get recovery status
            try:
                recovery = coach_tools.get_recovery_status(self.db, athlete_id)
                if recovery.get("ok"):
                    data = recovery.get("data", {})
                    state_lines.append(f"Recovery status: {data.get('status', 'unknown')}")
                    state_lines.append(f"Injury risk score: {data.get('injury_risk_score', 'N/A')}")
            except Exception:
                pass
            
            # Weekly volume history - 26 weeks (6 months) for trend analysis
            try:
                weekly = coach_tools.get_weekly_volume(self.db, athlete_id, weeks=26)
                if weekly.get("ok"):
                    weeks_data = weekly.get("data", {}).get("weeks", [])
                    if weeks_data:
                        state_lines.append(f"Weekly mileage (last {len(weeks_data)} weeks):")
                        for w in weeks_data:
                            dist = w.get('total_distance_mi', 0) or w.get('total_distance_km', 0) * 0.621371
                            runs = w.get('run_count', 0)
                            state_lines.append(f"  - {w.get('week_start', 'N/A')}: {dist:.1f} mi ({runs} runs)")
            except Exception as e:
                logger.debug(f"Failed to get weekly volume for Opus context: {e}")
            
            # Recent runs - last 7 days for immediate context
            try:
                recent = coach_tools.get_recent_runs(self.db, athlete_id, days=7)
                if recent.get("ok"):
                    runs = recent.get("data", {}).get("runs", [])
                    if runs:
                        state_lines.append(f"Last 7 days detail ({len(runs)} runs):")
                        for run in runs:
                            state_lines.append(
                                f"  - {run.get('start_time', '')[:10]}: {run.get('name', 'Run')} | "
                                f"{run.get('distance_mi', 0):.1f} mi @ {run.get('pace_per_mile', 'N/A')} | "
                                f"HR avg:{run.get('avg_hr', 'N/A')} max:{run.get('max_hr', 'N/A')}"
                            )
            except Exception as e:
                logger.debug(f"Failed to get recent runs for Opus context: {e}")
            
            # Get latest checkin
            try:
                checkin = (
                    self.db.query(DailyCheckin)
                    .filter(DailyCheckin.athlete_id == athlete_id)
                    .order_by(DailyCheckin.date.desc())
                    .first()
                )
                if checkin:
                    state_lines.append(f"Last checkin ({checkin.date}):")
                    if checkin.sleep_h is not None:
                        state_lines.append(f"  Sleep: {checkin.sleep_h}h")
                    if checkin.motivation_1_5 is not None:
                        motivation_map = {5: 'Great', 4: 'Fine', 2: 'Tired', 1: 'Rough'}
                        state_lines.append(f"  Feeling: {motivation_map.get(checkin.motivation_1_5, checkin.motivation_1_5)}")
                    if checkin.soreness_1_5 is not None:
                        state_lines.append(f"  Soreness: {checkin.soreness_1_5}/5")
                    if checkin.stress_1_5 is not None:
                        state_lines.append(f"  Stress: {checkin.stress_1_5}/5")
                    if checkin.notes:
                        state_lines.append(f"  Notes: {checkin.notes[:100]}")
            except Exception:
                pass
            
            # Get intent snapshot
            try:
                intent = coach_tools.get_coach_intent_snapshot(self.db, athlete_id)
                if intent.get("ok"):
                    data = intent.get("data", {})
                    if data.get("training_intent"):
                        state_lines.append(f"Training intent: {data['training_intent']}")
                    if data.get("pain_flag") and data["pain_flag"] != "none":
                        state_lines.append(f"Pain flag: {data['pain_flag']}")
                    if data.get("next_event_date"):
                        state_lines.append(f"Next event: {data['next_event_date']} ({data.get('next_event_type', '')})")
            except Exception:
                pass
                
        except Exception as e:
            logger.warning(f"Failed to build athlete state for Opus: {e}")
            state_lines.append("(Unable to retrieve full athlete state)")
        
        return "\n".join(state_lines) if state_lines else "(No athlete data available)"

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
        - AND uses true superlative/comparison language ("longest", "fastest", "best", etc.)
        - BUT does not provide any concrete return window (date, "6 weeks", month name).

        This is a production-beta trust guardrail: ask a clarifying question instead
        of assuming an all-time scope.

        IMPORTANT: Does NOT fire on narrative/venting statements like "returning from
        injury sucks" or "I'm running slow". The plain adjectives "slow" and "fast"
        are NOT treated as comparison triggers — only true superlatives are.
        """
        lower = (lower_message or "").lower()
        if not lower:
            return False
        if not self._has_return_context(lower):
            return False

        # Only fire on TRUE superlative/comparison terms that imply a ranking/scope.
        # "slow" and "fast" are plain adjectives describing current state — NOT triggers.
        # "I'm running slow" is venting, not a comparison question.
        _SUPERLATIVE_TERMS = (
            "longest", "furthest", "fastest", "slowest",
            "best", "worst", "most", "least",
            "hardest", "toughest", "easiest",
            "biggest", "smallest",
        )
        if not any(term in lower for term in _SUPERLATIVE_TERMS):
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
        # Suppress internal prompt-contract leakage in user-facing prose.
        text = re.sub(r"(?mi)^\s*authoritative fact capsule.*$", "", text)
        text = re.sub(r"(?mi)^\s*response contract.*$", "", text)
        # Rewrite internal pace-comparison language into athlete-friendly prose.
        # Matches both standalone lines and bullet-list items (e.g. "- Recorded pace…").
        def _rewrite_pace_relation(m: re.Match) -> str:
            prefix = m.group("prefix") or ""
            direction = (m.group("direction") or "").strip().lower()
            amount = (m.group("amount") or "").strip().rstrip(".")
            if not amount:
                return ""
            if direction == "slower":
                return f"{prefix}Pace sat about {amount} off marathon rhythm — controlled effort."
            elif direction == "faster":
                return f"{prefix}Pace was about {amount} quicker than marathon rhythm."
            else:
                return f"{prefix}Pace was about {amount} relative to marathon rhythm."
        text = re.sub(
            r"(?mi)^(?P<prefix>\s*[-*]\s*)?recorded pace vs marathon pace\s*:\s*"
            r"(?P<direction>slower|faster)?\s*(?:by\s*)?(?P<amount>[0-9:]+/mi(?:le)?)?\s*\.?\s*$",
            _rewrite_pace_relation,
            text,
        )
        text = re.sub(r"(?mi)^\s*date\s*:\s*20\d{2}-\d{2}-\d{2}.*$", "", text)
        text = re.sub(r"\n{3,}", "\n\n", text).strip()

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
