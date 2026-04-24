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

from services.coaching._constants import (  # noqa: E402
    HighStakesSignal,
    HIGH_STAKES_PATTERNS,
    COACH_MAX_REQUESTS_PER_DAY,
    COACH_MAX_OPUS_REQUESTS_PER_DAY,
    COACH_MONTHLY_TOKEN_BUDGET,
    COACH_MONTHLY_OPUS_TOKEN_BUDGET,
    COACH_MAX_OPUS_REQUESTS_PER_DAY_VIP,
    COACH_MONTHLY_OPUS_TOKEN_BUDGET_VIP,
    COACH_MAX_INPUT_TOKENS,
    COACH_MAX_OUTPUT_TOKENS,
    _strip_emojis,
    _check_kb_violations,
    _check_response_quality,
    is_high_stakes_query,
    ANTHROPIC_AVAILABLE,
    GEMINI_AVAILABLE,
    _build_cross_training_context,
)
from services.coaching._conversation_contract import classify_conversation_contract  # noqa: E402

try:
    from anthropic import Anthropic
except ImportError:
    pass

try:
    from google import genai
    from google.genai import types as genai_types
except ImportError:
    genai = None
    genai_types = None

from models import (  # noqa: E402
    Athlete,
    Activity,
    TrainingPlan,
    PlannedWorkout,
    DailyCheckin,
    GarminDay,
    PersonalBest,
    IntakeQuestionnaire,
    CoachUsage,
    CoachChat,
)
from services import coach_tools  # noqa: E402
from core.config import settings  # noqa: E402
from services.coach_modules import (  # noqa: E402
    MessageRouter,
    MessageType,
    ContextBuilder,
    ConversationQualityManager,
)

from services.coaching._budget import BudgetMixin  # noqa: E402
from services.coaching._tools import ToolsMixin  # noqa: E402
from services.coaching._llm import LLMMixin  # noqa: E402
from services.coaching._context import ContextMixin  # noqa: E402
from services.coaching._thread import ThreadMixin  # noqa: E402
from services.coaching._guardrails import GuardrailsMixin  # noqa: E402
from services.coaching._prescriptions import PrescriptionMixin  # noqa: E402


class AICoach(BudgetMixin, ToolsMixin, LLMMixin, ContextMixin, ThreadMixin, GuardrailsMixin, PrescriptionMixin):
    """
    AI Coach powered by Kimi K2.5 (all queries) with Claude Sonnet silent fallback.

    As of Apr 2026 every query routes to Kimi K2.5.  Gemini Flash is retired
    from the coach path.  Sonnet remains as a reliability fallback only.

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
- CRITICAL TERMINOLOGY: NEVER say "VDOT" — this is a trademarked third-party term. ALWAYS say "RPI" (Running Performance Index) instead. For example: "Your RPI of 53.2 indicates..." NOT "Your VDOT value of 53.2..."
- Avoid jargon unless the athlete uses it first
- Be encouraging but never sugarcoat problems
- This is a conversation, not a document. Write in natural sentences and short paragraphs, the way a coach talks.
- Conversational A->I->A requirement (chat prose, not JSON): include an interpretive Assessment, explain the Implication, then provide a concrete Action.
- Do NOT repeat yourself or give the same canned response multiple times

TEMPORAL ACCURACY (NON-NEGOTIABLE):
Every activity has a date and a relative label like "(2 days ago)" or "(yesterday)".
- NEVER say "today's run" or "today's marathon" unless the activity date is literally today.
- ALWAYS check the relative label before referencing when something happened.
- If the marathon was "(2 days ago)", say "Sunday's marathon" or "your marathon two days ago" — NEVER "today's marathon".
- When in doubt, use the actual date: "your March 15 marathon".
Getting the date wrong destroys trust in everything else you say.

RESPONSE LENGTH:
- Match your response length to the question complexity.
- Yes/no question → 2-4 sentences.
- "Tell me about X" → 1-2 short paragraphs.
- "Analyze my last month" → detailed but still under 200 words.
- NEVER write more than the question warrants. If the athlete wants more, they'll ask.

FORMAT:
- This is a conversation, not a document.
- NEVER use markdown tables in chat responses.
- NEVER use markdown headers (##, ###, **Section Name**).
- NEVER use emojis.
- Write in natural sentences and short paragraphs, the way a coach talks.

## Important Rules

1. Never recommend medical advice - refer to healthcare professionals
2. Never recommend extreme diets or protocols
3. Always acknowledge when you're uncertain
4. Base recommendations on the athlete's current fitness level, not aspirational goals
5. Consider the athlete's injury history if mentioned

## Data-Verification Discipline (NON-NEGOTIABLE)

When citing specific paces, splits, distances, or comparing one workout to another, you MUST look up the actual data first. NEVER infer performance from a workout title, name, or summary. NEVER say "that's faster than last week" or "your intervals were quicker" without checking the actual split data. If you haven't looked up the specific numbers, say so and look them up. Do not guess. A wrong pace comparison destroys more trust than admitting "I need to check that."

## Athlete-Calibrated Coaching Tone

Match your coaching posture to the athlete's experience level (available in the context):
- Experienced athletes (advanced/elite, extensive race history, confirmed patterns, high peak volume): coach as a peer. Acknowledge their training intent. Do NOT default to caution, recovery warnings, or load suggestions unless the data shows a genuine issue they haven't noticed. Respect deliberate overreach during build phases. Do not tell a BQ runner to "be cautious about tomorrow's intervals" or that a distance they've done many times is "a big ask."
- Intermediate athletes: balanced tone. Flag concerns but trust their judgment on familiar efforts.
- Beginners or returning-from-break athletes: more conservative guidance. Check pain signals. Cap ramp rates.
An experienced athlete should NEVER have to tell you to stop being protective. Match their level.

## Fatigue Threshold Context Awareness

Confirmed fatigue thresholds are real data but WHEN you cite them matters:
- During a deliberate build or overreach approaching a race: do NOT cite fatigue thresholds as warnings. Acknowledge the load, note the data, and trust the athlete's intent.
- During maintenance, recovery, or when performance is declining unexpectedly: cite thresholds actively.
- When the athlete asks about fatigue: always share the data regardless of phase.

## CRITICAL: Tool Selection for Pace Questions

COACHING PHILOSOPHY (from Knowledge Base — NON-NEGOTIABLE):
1. EFFORT-BASED COACHING ONLY. NEVER prescribe training by heart rate zones, HR numbers, or zone numbers. NEVER say "keep your heart rate below X" or "stay in zone 2." This system coaches by PACE (from RPI) and EFFORT FEEL (conversational, comfortably hard, short phrases, can't talk). If the athlete asks about HR zones, explain that we coach by pace and perceived effort, not HR zones.
2. N=1 ONLY. NEVER apply population statistics (220-age, HR zone percentages, generic formulas) to ANY athlete. Every recommendation must be grounded in THIS athlete's actual data. Age is a variable, not a limiter.
3. TRAINING PACES COME FROM RPI ONLY. Call get_training_paces for paces. These are THE authoritative source, derived from the athlete's actual race performances. NEVER derive paces from recent runs, efficiency data, or theoretical models.
4. EASY PACE IS A CEILING, NOT A RANGE. The easy pace from RPI is the MAXIMUM pace — do not run faster than this. The athlete can run as slow as they want on easy days. Easy running should feel conversational — if you can't speak in complete sentences, you're going too fast.
5. RACE PREDICTIONS ARE RPI EQUIVALENTS. The get_race_predictions tool returns equivalent times calculated from the athlete's actual race data. They are NOT theoretical projections. Always anchor on the athlete's real race history included in the tool response. If the equivalent time contradicts a recent actual race, the actual race is the truth.
6. TOOL OUTPUTS REQUIRE YOUR JUDGMENT. Tools provide data, not coaching decisions. Before presenting any number, ask: does this match what I know about this athlete's actual performances? If a tool number contradicts the athlete's race history or training data, say so.
7. SUPPRESSION OVER HALLUCINATION. If you cannot provide a confident, data-backed answer, say "I don't have enough data to answer that reliably." NEVER guess a race time, pace, or recommendation.

TRAINING PACES:
- ALWAYS call get_training_paces FIRST - this is the ONLY authoritative source for training paces
- These paces are calculated from the athlete's RPI (Running Performance Index, based on their race results)
- NEVER derive paces from recent runs or efficiency data - that's what they RAN, not what they SHOULD run
- The training pace calculator is scientifically accurate - trust it over any other data

## Thin / Missing History Fallback (PRODUCTION BETA)

Some early users will not have enough Strava/Garmin history yet. If training data coverage is thin:
- Prefer the athlete's self-reported baseline answers (runs/week, weekly miles/minutes, longest run, return-from-break date) when present.
- Be explicit: include a short line like: "Using your answers for now — connect Strava/Garmin for better insights."
- For athletes with thin history ONLY: cap recommended ramp at ~20% week-over-week, and ask about pain signals before any hard session recommendations.
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
    # 95% of queries use Gemini 3 Flash (cost-efficient, 1M context)
    # 5% high-stakes queries use Claude Sonnet 4.6 (premium reasoning quality)
    MODEL_DEFAULT = "gemini-3-flash-preview"  # Standard coaching (95%) — March 2026; thought_signature fix applied in tool loop (defensive strip)
    MODEL_HIGH_STAKES = "claude-sonnet-4-6"  # Premium Anthropic lane — Sonnet 4.6 (was Opus)
    
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
                logger.info("Gemini 3 Flash initialized for coaching queries")
            else:
                self.gemini_client = None
        else:
            self.gemini_client = None
    


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
    
    def classify_query(self, message: str) -> str:
        """Legacy: map new complexity to old simple/standard."""
        complexity = self.classify_query_complexity(message)
        return "simple" if complexity == "low" else "standard"



    def get_model_for_query(self, query_type: str, athlete_id: Optional[UUID] = None, message: str = "") -> Tuple[str, bool]:
        """
        Select model for coach query.

        As of Apr 2026 every query routes to Kimi K2.5 via the premium
        tool-calling path (_query_kimi_with_fallback).  Sonnet remains as
        a silent fallback if Kimi errors.  Gemini Flash is retired from
        the coach path.

        Budget checks still apply per athlete tier (founder uncapped,
        VIP gets higher caps, standard gets default caps).

        Returns:
            Tuple of (model_name, is_premium) — is_premium is always True
            now that Kimi is the universal model.
        """
        if athlete_id and self._is_founder(athlete_id):
            logger.info("Routing to Kimi: founder_bypass")
            return self.MODEL_HIGH_STAKES, True

        if athlete_id and self.is_athlete_vip(athlete_id):
            allowed, reason = self.check_budget(athlete_id, is_opus=True, is_vip=True)
            if allowed:
                logger.info("Routing to Kimi: vip, athlete=%s", athlete_id)
                return self.MODEL_HIGH_STAKES, True
            logger.info("Budget exceeded for VIP %s: %s", athlete_id, reason)
            return self.MODEL_HIGH_STAKES, True

        if athlete_id:
            is_vip = self.is_athlete_vip(athlete_id)
            allowed, reason = self.check_budget(athlete_id, is_opus=True, is_vip=is_vip)
            if not allowed:
                logger.info("Budget exceeded for %s: %s", athlete_id, reason)

        logger.info("Routing to Kimi: universal")
        return self.MODEL_HIGH_STAKES, True
    


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
        include_context: bool = True,
        is_synthetic_probe: bool = False,
        finding_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Send a message to the AI coach and get a response.
        
        Args:
            athlete_id: The athlete's ID
            message: The user's message
            include_context: Whether to inject context from athlete data
            finding_id: Optional CorrelationFinding ID for briefing→coach deep link
        
        Returns:
            Dict with response text and metadata
        """
        # P1-D: Consent gate — no LLM dispatch without explicit opt-in.
        from services.consent import has_ai_consent as _has_consent
        if not _has_consent(athlete_id=athlete_id, db=self.db):
            return {
                "response": (
                    "AI coaching insights are currently disabled for your account. "
                    "To enable AI insights and unlock personalized coaching, go to "
                    "**Settings → AI Processing** and grant consent. "
                    "All other features remain fully available."
                ),
                "error": False,
                "timed_out": False,
                "history_thin": False,
                "used_baseline": False,
                "baseline_needed": False,
                "rebuild_plan_prompt": False,
            }

        # If no LLM route is available, return a helpful message.  Kimi is the
        # primary chat path; Gemini remains only as a guardrail-retry fallback.
        kimi_configured = bool(settings.KIMI_API_KEY or os.getenv("KIMI_API_KEY"))
        if not (kimi_configured or self.anthropic_client or self.gemini_client):
            return {
                "response": (
                    "AI Coach is not configured. Please set KIMI_API_KEY, "
                    "ANTHROPIC_API_KEY, or GOOGLE_AI_API_KEY in your environment."
                ),
                "error": True
            }

        # Persist units preference if the athlete explicitly requests it.
        self._maybe_update_units_preference(athlete_id, message)

        # Persist athlete-led intent/constraints if they answered them.
        # This supports self-guided coaching (collaborative, not imposed).
        self._maybe_update_intent_snapshot(athlete_id, message)

        lower = (message or "").lower()
        turn_id = str(uuid4())
        detected_synthetic_probe = bool(is_synthetic_probe) or ("[synthetic_probe]" in lower) or ("forced mismatch probe" in lower)
        is_organic = not detected_synthetic_probe

        # Deterministic short-circuit for profile edit guidance:
        # do not spend LLM latency/tokens on profile-location intents.
        if self._is_profile_edit_intent(message):
            field = self._infer_profile_field_from_message(message)
            path = coach_tools.get_profile_edit_paths(self.db, athlete_id, field=field)
            data = path.get("data", {}) if isinstance(path, dict) else {}
            route = data.get("route", "/settings")
            section = data.get("section", "Personal Information")
            field_name = data.get("field", "Birthdate")
            note = data.get("note", "")
            response = f"Go to {route} -> {section} -> {field_name}."
            if note:
                response += f" {note}"
            response = _strip_emojis(
                self._normalize_response_for_ui(
                    user_message=message,
                    assistant_message=response,
                )
            )
            thread_id, _ = self.get_or_create_thread_with_state(athlete_id)
            self._record_turn_guard_event(
                athlete_id=athlete_id,
                event="pass_initial",
                user_band="profile",
                assistant_band="profile",
                turn_id=turn_id,
                stage="initial",
                is_synthetic_probe=detected_synthetic_probe,
                is_organic=is_organic,
            )
            self._save_chat_messages(athlete_id, message, response, model="deterministic")
            return {
                "response": response,
                "thread_id": thread_id,
                "error": False,
                "timed_out": False,
                "history_thin": False,
                "used_baseline": False,
                "baseline_needed": False,
                "rebuild_plan_prompt": False,
            }

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

            # Universal Kimi K2.5 routing (Apr 2026).
            # Every query goes through Kimi with Sonnet as silent fallback.
            athlete_state = self._build_athlete_state_for_opus(athlete_id)

            conversation_contract_type = None
            try:
                contract = classify_conversation_contract(message)
                conversation_contract_type = contract.contract_type.value
                athlete_state += (
                    "\n\n=== CONVERSATION OUTCOME CONTRACT ===\n"
                    f"Type: {contract.contract_type.value}\n"
                    f"Outcome target: {contract.outcome_target}\n"
                    f"Required behavior: {contract.required_behavior}\n"
                )
                if contract.max_words:
                    athlete_state += f"Max length: {contract.max_words} words\n"
                athlete_state += "=== END CONVERSATION OUTCOME CONTRACT ==="
            except Exception:
                pass

            if finding_id:
                finding_context = self._build_finding_deep_link_context(
                    athlete_id, finding_id
                )
                if finding_context:
                    athlete_state += "\n\n" + finding_context

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

            result = await self._query_kimi_with_fallback(
                athlete_id=athlete_id,
                message=message,
                athlete_state=athlete_state,
                conversation_context=conversation_context,
            )

            if not result.get("error"):
                tools_used = list(dict.fromkeys(result.get("tools_called") or []))
                guarded_response = await self._finalize_response_with_turn_guard(
                    athlete_id=athlete_id,
                    user_message=message,
                    response_text=result.get("response", ""),
                    is_opus=True,
                    conversation_context=conversation_context,
                    turn_id=turn_id,
                    is_synthetic_probe=detected_synthetic_probe,
                    is_organic=is_organic,
                )
                result["response"] = guarded_response
                self._save_chat_messages(
                    athlete_id, message, guarded_response,
                    model=result.get("model", "unknown"),
                    tools_used=tools_used,
                    conversation_contract=conversation_contract_type,
                )
                result["tools_used"] = tools_used
                result["tool_count"] = len(tools_used)
                result["conversation_contract"] = conversation_contract_type

            result["thread_id"] = thread_id
            return result
            
        except Exception as e:
            logger.error(f"AI Coach error: {e}")
            return {
                "response": f"An error occurred: {str(e)}",
                "error": True
            }





def get_ai_coach(db: Session) -> AICoach:
    """Factory function for dependency injection."""
    return AICoach(db)
