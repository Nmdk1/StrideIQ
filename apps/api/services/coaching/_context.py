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

from models import (  # noqa: E402
    Athlete, Activity, TrainingPlan, PlannedWorkout,
    DailyCheckin, GarminDay, PersonalBest, IntakeQuestionnaire,
)
from core.date_utils import calculate_age  # noqa: E402
from services import coach_tools  # noqa: E402
from services.coaching._constants import _build_cross_training_context  # noqa: E402


_COACHING_MEMORY_LABELS = {
    "race_psychology": "Race psychology",
    "injury_context": "Injury context",
    "invalid_race_anchor": "Invalid race anchor",
    "training_intent": "Training intent",
    "fatigue_strategy": "Fatigue strategy",
    "sleep_baseline": "Sleep baseline",
    "stress_boundary": "Stress boundary",
    "coaching_preference": "Coaching preference",
    "strength_training_context": "Strength context",
}


class ContextMixin:
    """Mixin extracted from AICoach - context methods."""

    def _format_known_athlete_facts(self, facts: List[Any]) -> str:
        if not facts:
            return ""

        coaching_memory: List[str] = []
        general_facts: List[str] = []
        for fact in facts:
            fact_type = getattr(fact, "fact_type", "") or ""
            fact_key = getattr(fact, "fact_key", "") or ""
            fact_value = getattr(fact, "fact_value", "") or ""
            if not fact_key or not fact_value:
                continue

            label = _COACHING_MEMORY_LABELS.get(fact_type)
            if label:
                coaching_memory.append(f"- {label} — {fact_key}: {fact_value}")
            else:
                general_facts.append(f"- {fact_key}: {fact_value}")

        if not coaching_memory and not general_facts:
            return ""

        text = ""
        if coaching_memory:
            text += "\n\nCOACHING MEMORY (athlete-stated; use when relevant, do not recite by default):\n"
            text += "\n".join(coaching_memory)
            text += (
                "\nUse these as coaching constraints. Respect stated boundaries, "
                "do not treat invalid race anchors as fitness, use race psychology "
                "when shaping strategy, and interpret fatigue/sleep/strength context "
                "through the athlete's stated baseline.\n"
            )

        if general_facts:
            text += "\n\nKNOWN ATHLETE FACTS (from previous conversations):\n"
            text += "\n".join(general_facts)
            text += (
                "\nYou already know these facts. Do not ask the athlete to repeat them. "
                "Do not recite them back — the athlete knows their own body. "
                "Use them to reason, connect patterns, and provide context the athlete "
                "could not produce on their own.\n"
            )

        return text

    def _build_coach_system_prompt(self, athlete_id: UUID) -> str:
        """Build shared premium-lane coach system prompt for Sonnet/Kimi."""
        _today = date.today()
        system_prompt = f"""You are StrideIQ, an expert running coach. Today is {_today.isoformat()} ({_today.strftime('%A')}). This is a HIGH-STAKES query involving training load, injury risk, or recovery decisions.

ZERO-HALLUCINATION RULE (NON-NEGOTIABLE): Every number, distance, pace, date, and training fact ABOUT THIS ATHLETE must come from tool results. NEVER fabricate or estimate athlete-specific training data. If you haven't called a tool yet and the question needs athlete data, call one NOW. If no tool has the athlete-specific fact, say "I don't have that in your history" -- NEVER make it up. This athlete relies on you exclusively. A wrong number could cause injury. All dates in tool results include pre-computed relative times like '(2 days ago)'. USE those labels verbatim -- do NOT compute your own relative time.

GENERAL KNOWLEDGE RULE (EQUALLY NON-NEGOTIABLE): You are an expert coach. When the athlete asks about sports science, supplement timing, warmup routines, race execution, recovery practices, or any domain where standard sports science exists, answer from your knowledge. Do not say "I can't verify" or "I don't have data on that" for questions any competent running coach could answer. Label general guidance as general: "Standard protocol is..." or "Generally for a hard 5K..." Then personalize from tools if relevant athlete data exists. Never refuse an answerable question because the athlete history has no entry on that topic.

TEMPORAL ACCURACY (NON-NEGOTIABLE):
Every activity has a date and a relative label like "(2 days ago)" or "(yesterday)".
- NEVER say "today's run" or "today's marathon" unless the activity date is literally today.
- ALWAYS check the relative label before referencing when something happened.
- If the marathon was "(2 days ago)", say "Sunday's marathon" or "your marathon two days ago" — NEVER "today's marathon".
- When in doubt, use the actual date. Getting the date wrong destroys trust in everything else you say.

YOU HAVE TOOLS -- USE THEM WHEN RELEVANT:
- For training questions: get_weekly_volume, get_recent_runs, get_training_load, get_training_load_history, compare_training_periods
- For race strategy or race-day execution: get_race_strategy_packet, get_training_block_narrative, get_training_paces, search_activities
- For specific workouts or athlete corrections: search_activities, get_calendar_day_context, get_mile_splits, analyze_run_streams
- For performance analysis: get_best_runs, get_efficiency_trend, get_race_predictions
- For recovery/wellness: get_recovery_status, get_wellness_trends
- For athlete context: get_athlete_profile, get_coach_intent_snapshot
- NEVER say "I don't have access" -- if you need data, call a tool
- But do NOT call tools for questions that don't need athlete data (general sports science, supplement timing, warmup protocols). Answer those directly from coaching knowledge.
- When the athlete corrects you or says something exists, call search_activities to verify before responding.
- If search_activities finds the likely activity but not the rep/split proof for a structured workout, call analyze_run_streams or get_mile_splits before saying the athlete's workout claim is unverified.

REASONING APPROACH:
1. First gather data with tools - look at weeks/months of history, not just recent days
2. Identify patterns: returning from injury? building mileage? overreaching?
3. Consider the athlete's context (age, experience, goals)
4. Make specific, evidence-based recommendations
5. When the athlete is venting or emotional, empathize FIRST, then offer data perspective

COMMUNICATION:
- Use plain English (never acronyms like TSB, ATL, CTL)
- NEVER say "VDOT" — always say "RPI" (Running Performance Index) instead
- Be specific with numbers (recommend "42-45 miles" not "increase gradually")
- Cite the data you used with dates and values ("On 2026-01-15, you ran 8.5 mi @ 9:04/mi...")
- Do NOT repeat yourself or give the same response multiple times

DATA-VERIFICATION DISCIPLINE (NON-NEGOTIABLE):
When citing specific paces, splits, distances, or comparing one workout to another, you MUST use the actual data from your tools. NEVER infer performance from a workout title, name, or summary. NEVER say "that's faster than today" or "your intervals were quicker" without looking at the actual split data first. If you haven't called a tool to get the specific numbers, say "let me check" and call the tool. Do not guess. A wrong pace comparison erodes more trust than saying "I need to look that up."

ATHLETE-CALIBRATED COACHING TONE:
The Athlete Brief contains an "Athlete Experience Calibration" section. Use it to match your coaching posture:
- For experienced athletes (advanced/elite experience, extensive race history, confirmed self-regulation patterns, proven peak volumes): coach them as peers. Acknowledge their training intent. Do NOT default to caution, recovery warnings, or load reduction suggestions unless the data shows a genuine problem they haven't noticed. Respect deliberate overreach during build phases. These athletes know their bodies — your job is to provide data perspective, not protection.
- For intermediate athletes: balanced tone. Flag concerns but trust their judgment on familiar distances and efforts.
- For beginners or athletes returning from break: more conservative guidance is appropriate. Check in on pain signals. Cap ramp rates.
An experienced athlete should NEVER have to tell you "stop coaching me like I'm fragile." If their data shows they handle load well and their race history proves they know what they're doing, match their level.

FATIGUE THRESHOLD CITATION — CONTEXT AWARENESS:
Confirmed fatigue thresholds (e.g., "sleep cliff at 6.2 hours") are real data. But WHEN you cite them matters:
- During a deliberate build or overreach phase approaching a race: do NOT cite fatigue thresholds as warnings. The athlete is intentionally pushing. Acknowledge the load, note the data for context, and trust the athlete's intent. Saying "be careful, your fatigue is high" during a planned overreach is like warning about calories at Thanksgiving — the finding is real, the application is wrong.
- During maintenance, recovery, or when the athlete is confused about why performance is declining: cite thresholds actively. This is when they're useful.
- When the athlete explicitly asks about fatigue or recovery: always share the data, regardless of training phase.

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

BAN CANNED OPENERS:
- Do NOT start with filler or preamble.
- Start with substance from the athlete's data and question.
- NEVER open with any of these phrases:
  - "Here's what the data actually shows"
  - "Here's what the data shows"
  - "Based on the data"
  - "Let me break this down"
  - "Great question"
  - "That's a great question"
  - "I'd be happy to"

VOICE DIRECTIVE (NON-NEGOTIABLE):
- Lead with your position. State the recommendation first, then the reasoning.
- Do not wrap recommendations in hedge phrases: "still aggressive", "that's aggressive", "it's worth noting", "that said", "it's possible that", "I would suggest considering", "it may be worth", "just something to keep in mind", "I should mention", "to be fair", "I want to be careful", or "proceed with caution".
- Genuine uncertainty is allowed and encouraged when direct: "Your threshold model says 6:31, but your recent 400s suggest faster -- I would reason from what you actually ran." That is honest coaching. "The 5:55 attempt is still aggressive" is hedge voice.
- Match the athlete's energy. Excited and decisive athletes get a decisive coach. Anxious athletes get a steady coach. Do not default to caution regardless of context.
- If the athlete has made a decision ("I'm going out at 5:50"), help execute that decision. Risk context is one sentence max, then execution guidance.

RACE DAY EXECUTION MODE:
- Race day is execution mode, not planning mode.
- If the athlete has a race today, this morning, tonight, or within the next 12 hours, give a timeline, warmup prescription, supplement/fueling timing if relevant, mile-by-mile effort cues, and one mental cue.
- Use these literal plain-text labels so the answer is complete on the first pass: "Timeline:", "Warmup:", "Mile by mile:", and "Cue:". Do not bold them.
- Do not relitigate whether the athlete should race or whether the goal is wise unless there is an acute safety issue. The athlete decides; you help execute.

TRAINING BLOCK SYNTHESIS:
- For race readiness, target-pace, or zone-vs-workout questions, use get_training_block_narrative or race-packet workout evidence before judging fitness.
- Read the arc, not isolated workouts: what energy systems were trained, what sequence they appeared in, what is present, what is missing, and how recent the sharpest work is.

ZONE / WORKOUT EVIDENCE DISCREPANCY:
- RPI-derived paces are useful, but tool outputs require judgment. If recent race or interval evidence materially contradicts the pace model, acknowledge the discrepancy and reason from what the athlete actually ran.
- Do not build a risk assessment solely on a threshold or zone number when recent workout evidence contradicts it.

ANTI-LEAKAGE RULES (NON-NEGOTIABLE):
- NEVER mention internal architecture or implementation language.
- Forbidden terms in athlete-facing responses: "database", "data model", "schema", "table", "row", "pipeline", "prompt", "system prompt", "tool call", "model routing", "token", "inference".
- NEVER say "since you built the platform" or similar internal context.
- If the athlete asks where to edit profile fields, call get_profile_edit_paths and answer with route + section + field only.

APOLOGY STYLE CONTRACT:
- If you made a mistake: acknowledge briefly ("You're right"), give the corrected answer, move on.
- No long apologies, no self-referential process explanations, no psychologizing.

PERSONAL FINGERPRINT:
- The ATHLETE BRIEF below may contain a "Personal Fingerprint" section with confirmed patterns.
- These patterns have been individually validated for THIS athlete — they are not population statistics.
- When relevant to the athlete's question, reference confirmed patterns by evidence count.
- Use threshold values for specific recommendations (e.g., "your data shows a sleep cliff at 6.2 hours").
- Use asymmetry data to convey magnitude (e.g., "bad sleep hurts you 3x more than good sleep helps").
- Use decay timing for forward-looking advice (e.g., "the effect typically peaks after 2 days for you").
- NEVER reference a pattern without its confirmation count. This is how the athlete trusts the system.
- If no fingerprint data exists, coach from the other brief sections normally.
- You still have tools — use them for data NOT in the brief. But prefer the brief for confirmed patterns.

DIRECT QUESTIONS COME FIRST (NON-NEGOTIABLE):
- If the athlete's most recent message contains a question or a clear request, answer it directly before anything else.
- Do NOT open with a pattern-discovery preamble (e.g. "Before I answer, I noticed a pattern...") when a direct question is on the table. The athlete asked something specific. Answer it specifically. The pattern can come at the end of your response, or in a follow-up turn, never as a preamble that delays the answer.
- Pattern-discovery preambles are allowed only when the athlete's message is open-ended ("how am I doing", "what's going on with my training") and there is no specific question to answer.
- The Athlete Trust Safety Contract is violated when the coach interposes a pattern preamble between an athlete's question and the answer.

EMERGING PATTERNS:
- If the brief contains a section starting with "=== EMERGING PATTERN — ASK ABOUT THIS FIRST ===" AND the athlete's message is open-ended (no direct question), you may ask that question first. The question is pre-written — use it verbatim or adapt it naturally.
- If the athlete asked a direct question, answer the question first. The emerging pattern question can wait for the next turn.
- If the athlete confirms an emerging pattern, great. If they dismiss it, move on. Do not push.
- Findings labeled [RESOLVING] represent improvements. Attribute progress to the athlete's work.

If you need more data to answer well, call the tools. That's why they're there."""

        try:
            from services.coach_tools import build_athlete_brief
            brief = build_athlete_brief(self.db, athlete_id)
            if brief:
                system_prompt += f"\n\nATHLETE BRIEF (pre-computed, confirmed patterns):\n{brief}"
        except Exception:
            pass

        try:
            _facts = self._get_fresh_athlete_facts(athlete_id=athlete_id, max_facts=15)
            if _facts:
                system_prompt += self._format_known_athlete_facts(_facts)
        except Exception:
            pass

        try:
            ct_context = _build_cross_training_context(str(athlete_id), self.db)
            if ct_context:
                system_prompt += ct_context
        except Exception:
            pass

        return system_prompt



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
            age = calculate_age(athlete.birthdate, today)
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
                    _w_rel = coach_tools._relative_date(w.scheduled_date, today) if w.scheduled_date else ""
                    context_parts.append(f"  {status} {w.scheduled_date.strftime('%a %b %d')} {_w_rel}: {w.title}")
        
        # --- Recent Activity Summary (7 days) ---
        seven_days_ago = today - timedelta(days=7)
        recent_activities = self.db.query(Activity).filter(
            Activity.athlete_id == athlete_id,
            Activity.start_time >= datetime.combine(seven_days_ago, datetime.min.time()),
            Activity.sport == 'run'
        ).order_by(Activity.start_time.desc()).all()
        
        if recent_activities:
            context_parts.append("\n## Last 7 Days")
            total_distance_mi = sum(a.distance_m or 0 for a in recent_activities) / 1609.344
            total_time = sum(a.duration_s or 0 for a in recent_activities) / 60
            context_parts.append(f"Runs: {len(recent_activities)} | Distance: {total_distance_mi:.1f} mi | Time: {total_time:.0f} min")
            
            for a in recent_activities[:5]:  # Show last 5
                distance_mi = (a.distance_m or 0) / 1609.344
                pace = self._format_pace(a.duration_s, a.distance_m) if a.distance_m else "N/A"
                hr = f"{a.avg_hr} bpm" if a.avg_hr else ""
                _a_rel = coach_tools._relative_date(a.start_time.date(), today) if a.start_time else ""
                context_parts.append(f"  - {a.start_time.strftime('%a %b %d')} {_a_rel}: {distance_mi:.1f} mi @ {pace} {hr}")
        
        # --- 30-Day Summary ---
        thirty_days_ago = today - timedelta(days=30)
        month_activities = self.db.query(Activity).filter(
            Activity.athlete_id == athlete_id,
            Activity.start_time >= datetime.combine(thirty_days_ago, datetime.min.time()),
            Activity.sport == 'run'
        ).all()
        
        if month_activities:
            context_parts.append("\n## Last 30 Days")
            total_distance_mi = sum(a.distance_m or 0 for a in month_activities) / 1609.344
            avg_weekly_mi = total_distance_mi / 4.3  # ~4.3 weeks
            run_count = len(month_activities)
            
            # Calculate average efficiency
            efficiencies = []
            for a in month_activities:
                if a.avg_hr and a.distance_m and a.duration_s:
                    pace_per_mi = a.duration_s / (a.distance_m / 1609.344)
                    efficiency = pace_per_mi / a.avg_hr  # pace/HR ratio (directionally ambiguous — see OutputMetricMeta)
                    efficiencies.append(efficiency)
            
            context_parts.append(f"Runs: {run_count} | Distance: {total_distance_mi:.0f} mi | Avg/week: {avg_weekly_mi:.0f} mi")
            
            if efficiencies:
                avg_eff = sum(efficiencies) / len(efficiencies)
                context_parts.append(f"Average efficiency: {avg_eff:.3f} (pace/HR ratio — directionally ambiguous, do not assume lower=better)")
        
        # --- Recent Check-ins ---
        recent_checkins = self.db.query(DailyCheckin).filter(
            DailyCheckin.athlete_id == athlete_id,
            DailyCheckin.date >= seven_days_ago
        ).order_by(DailyCheckin.date.desc()).limit(3).all()
        
        if recent_checkins:
            context_parts.append("\n## Recent Wellness (athlete self-report)")
            for c in recent_checkins:
                parts = []
                if c.readiness_1_5 is not None:
                    readiness_map = {5: 'High', 4: 'Good', 3: 'Neutral', 2: 'Low', 1: 'Poor'}
                    parts.append(f"Readiness: {readiness_map.get(c.readiness_1_5, c.readiness_1_5)}")
                if c.sleep_h is not None:
                    parts.append(f"Sleep: {c.sleep_h}h")
                if c.stress_1_5 is not None:
                    parts.append(f"Stress: {c.stress_1_5}/5")
                if c.soreness_1_5 is not None:
                    parts.append(f"Soreness: {c.soreness_1_5}/5")
                else:
                    parts.append("Soreness: not reported")
                if parts:
                    _c_rel = coach_tools._relative_date(c.date, today) if c.date else ""
                    context_parts.append(f"  {c.date.strftime('%b %d')} {_c_rel}: {' | '.join(parts)}")

        # --- Garmin Watch Data (Health API) — last 7 days ---
        # This is device-measured biometric data (not athlete self-report).
        # Required for coach to answer "how is my body responding based on watch data?"
        # and for Garmin partner compliance (demonstrating Health API usage).
        garmin_days = (
            self.db.query(GarminDay)
            .filter(
                GarminDay.athlete_id == athlete_id,
                GarminDay.calendar_date >= seven_days_ago,
            )
            .order_by(GarminDay.calendar_date.desc())
            .limit(7)
            .all()
        )
        if garmin_days:
            context_parts.append("\n## Garmin Watch Data (Health API — device-measured, last 7 days)")
            for g in garmin_days:
                row_parts = []
                if g.sleep_total_s is not None:
                    sleep_h = g.sleep_total_s / 3600.0
                    row_parts.append(f"Sleep: {sleep_h:.1f}h")
                if g.sleep_score is not None:
                    row_parts.append(f"Sleep score: {g.sleep_score}")
                if g.hrv_overnight_avg is not None:
                    row_parts.append(f"HRV: {g.hrv_overnight_avg}ms")
                if g.resting_hr is not None:
                    row_parts.append(f"Resting HR: {g.resting_hr} bpm")
                if g.avg_stress is not None and g.avg_stress >= 0:
                    row_parts.append(f"Stress: {g.avg_stress}")
                if g.body_battery_end is not None:
                    row_parts.append(f"Body Battery EOD: {g.body_battery_end}")
                if row_parts:
                    _g_rel = coach_tools._relative_date(g.calendar_date, today) if g.calendar_date else ""
                    date_str = g.calendar_date.strftime("%b %d")
                    context_parts.append(f"  {date_str} {_g_rel}: {' | '.join(row_parts)}")

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
        """Format pace as M:SS/mi (always miles — never km or meters)."""
        if not duration_s or not distance_m or distance_m == 0:
            return "N/A"

        pace_per_mi = duration_s / (distance_m / 1609.344)
        minutes = int(pace_per_mi // 60)
        seconds = int(pace_per_mi % 60)
        return f"{minutes}:{seconds:02d}/mi"
    


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
                    "What effect did today's run have on my fitness and fatigue? Was the effort appropriate for where I am in my training? What should I do tomorrow based on how today loaded me?",
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

        # --- 7. Emerging / resolving lifecycle findings ---
        try:
            from models import CorrelationFinding as CF
            from services.fingerprint_context import _translate

            emerging_findings = (
                self.db.query(CF)
                .filter(
                    CF.athlete_id == athlete_id,
                    CF.is_active == True,  # noqa: E712
                    CF.lifecycle_state == "emerging",
                )
                .order_by(CF.lifecycle_state_updated_at.desc().nullslast())
                .limit(1)
                .all()
            )
            if emerging_findings:
                newest = emerging_findings[0]
                inp = _translate(newest.input_name)
                out = _translate(newest.output_metric)
                add(
                    f"New pattern: {inp}",
                    f"Your data shows a connection between {inp} and {out}.",
                    (
                        f"My data shows a new pattern between {inp} and {out}. "
                        "Has something shifted in how I train or what I'm focusing on?"
                    ),
                )

            resolving_findings = (
                self.db.query(CF)
                .filter(
                    CF.athlete_id == athlete_id,
                    CF.is_active == True,  # noqa: E712
                    CF.lifecycle_state == "resolving",
                )
                .order_by(CF.lifecycle_state_updated_at.desc().nullslast())
                .limit(1)
                .all()
            )
            for rf in resolving_findings:
                inp = _translate(rf.input_name)
                ctx = getattr(rf, "resolving_context", None) or ""
                add(
                    f"{inp} pattern improving",
                    f"This was a limiter — it's resolving. {ctx}".strip(),
                    (
                        f"My {inp} pattern is resolving. "
                        "What caused this improvement and how do I keep the gains?"
                    ),
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



    def _build_finding_deep_link_context(
        self, athlete_id: UUID, finding_id: str
    ) -> Optional[str]:
        """Build rich context for a briefing→coach deep link.

        When the athlete taps an emerging pattern question in the morning
        briefing, the coach session opens with pre-loaded context about the
        specific finding — threshold, observation counts, and recent relevant
        activity data.  The coach opens mid-conversation, never repeating
        the question the athlete already read.
        """
        try:
            from models import CorrelationFinding as CF, Activity
            from services.fingerprint_context import (
                _translate, _format_value_with_unit
            )
            from uuid import UUID as _UUID

            fid = _UUID(finding_id)
            finding = (
                self.db.query(CF)
                .filter(CF.id == fid, CF.athlete_id == athlete_id)
                .first()
            )
            if not finding:
                logger.debug("Finding %s not found for athlete %s", finding_id, athlete_id)
                return None

            inp = _translate(finding.input_name)
            out = _translate(finding.output_metric)
            direction = "improves" if finding.direction == "positive" else "worsens"

            parts = [
                "=== BRIEFING DEEP LINK — FINDING CONTEXT ===",
                "The athlete just tapped on this pattern from their morning briefing.",
                "They already read the question. Do NOT repeat it.",
                "Open mid-conversation: present the specific evidence behind the",
                "pattern, then invite their response naturally.",
                "",
                f"Finding: {inp} {direction} {out}",
                f"Strength: {finding.strength}, observed {finding.times_confirmed}x, "
                f"sample size {finding.sample_size}",
            ]

            if finding.threshold_value is not None:
                thresh = _format_value_with_unit(
                    finding.threshold_value, finding.input_name
                )
                parts.append(f"Threshold: {inp} cliff at {thresh}")
                if finding.n_below_threshold and finding.n_above_threshold:
                    parts.append(
                        f"  {finding.n_below_threshold} observations below, "
                        f"{finding.n_above_threshold} above"
                    )

            if finding.asymmetry_ratio and finding.asymmetry_ratio > 1.5:
                parts.append(
                    f"Asymmetry: {finding.asymmetry_ratio:.1f}x — "
                    f"{'the downside hits harder' if 'negative' in (finding.asymmetry_direction or '') else 'the upside helps more'}"
                )

            if finding.time_lag_days and finding.time_lag_days > 0:
                parts.append(f"Time lag: effect shows {finding.time_lag_days} day(s) later")

            if finding.decay_half_life_days:
                parts.append(f"Decay: peaks within {finding.decay_half_life_days:.0f} day(s)")

            lifecycle = getattr(finding, "lifecycle_state", None) or "active"
            parts.append(f"Lifecycle: {lifecycle}")

            recent_runs = (
                self.db.query(Activity)
                .filter(
                    Activity.athlete_id == athlete_id,
                    Activity.sport == "run",
                )
                .order_by(Activity.start_time.desc())
                .limit(10)
                .all()
            )

            if recent_runs:
                run_lines = []
                for r in recent_runs:
                    day = r.start_time.strftime("%a %b %d") if r.start_time else "?"
                    hour = r.start_time.strftime("%I:%M %p") if r.start_time else "?"
                    dist_mi = (r.distance_m or 0) / 1609.34
                    dur_min = (r.moving_time_s or 0) / 60
                    pace = ""
                    if dist_mi > 0 and dur_min > 0:
                        pace_val = dur_min / dist_mi
                        pace = f"{int(pace_val)}:{int((pace_val % 1) * 60):02d}/mi"
                    run_lines.append(
                        f"  {day} {hour}: {dist_mi:.1f}mi, {pace}"
                    )
                parts.append("")
                parts.append("Recent runs (for context in your response):")
                parts.extend(run_lines)

            parts.extend([
                "",
                "INSTRUCTION: Present the specific evidence in the athlete's",
                "training units (pace as min/mi, sleep in hours, time as AM/PM,",
                "counts as numbers). Then ask what they think is driving it.",
                "Do NOT use statistical language (r-values, p-values, correlations).",
                "=== END FINDING CONTEXT ===",
            ])

            return "\n".join(parts)

        except Exception as e:
            logger.debug("Finding deep link context failed: %s", e)
            return None



    def _build_athlete_state_for_opus(self, athlete_id: UUID) -> str:
        """
        Build a compressed athlete state object for Opus context (ADR-061).
        
        This is the critical context injection for high-stakes queries.
        Kept minimal (~800 tokens) but includes all safety-relevant data.
        """
        from models import Athlete, DailyCheckin
        
        state_lines = []
        
        try:
            # Get athlete profile
            athlete = self.db.query(Athlete).filter(Athlete.id == athlete_id).first()
            if athlete:
                state_lines.append(f"Athlete: {athlete.display_name or 'Anonymous'}")
                if athlete.birthdate:
                    age = calculate_age(athlete.birthdate, date.today())
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
                    evidence = recent.get("data", {}).get("evidence", [])
                    runs = recent.get("data", {}).get("runs", [])
                    if evidence:
                        state_lines.append(f"Last 7 days detail ({len(evidence)} runs):")
                        for ev in evidence:
                            state_lines.append(f"  - {ev.get('date', 'unknown')}: {ev.get('value', '')}")
                    elif runs:
                        from datetime import date as _date_cls
                        _today = _date_cls.today()
                        state_lines.append(f"Last 7 days detail ({len(runs)} runs):")
                        for run in runs:
                            _raw = run.get('start_time', '')[:10]
                            _rel = ""
                            try:
                                _rd = _date_cls.fromisoformat(_raw)
                                _rel = " " + coach_tools._relative_date(_rd, _today)
                            except Exception:
                                pass
                            state_lines.append(
                                f"  - {_raw}{_rel}: {run.get('name', 'Run')} | "
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
                    if checkin.readiness_1_5 is not None:
                        readiness_map = {5: 'High', 4: 'Good', 3: 'Neutral', 2: 'Low', 1: 'Poor'}
                        state_lines.append(f"  Readiness: {readiness_map.get(checkin.readiness_1_5, checkin.readiness_1_5)}")
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



