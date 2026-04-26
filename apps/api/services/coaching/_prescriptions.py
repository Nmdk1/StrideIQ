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


class PrescriptionMixin:
    """Mixin extracted from AICoach - prescriptions methods."""

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
                                "PREFETCHED DATA (last 7 days):\n" +
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
                instructions.append("RETURN CONTEXT: Compare to post-return period only. Match caution level to athlete experience.")
            else:
                instructions.append(
                    "RETURN-FROM-INJURY CONTEXT: This athlete mentioned returning from injury/break. "
                    "All comparisons should DEFAULT to the post-return period unless they explicitly specify otherwise. "
                    "Do NOT compare against pre-injury peaks without asking first. "
                    "For load recommendations, match the athlete's experience level: experienced athletes "
                    "returning from break can handle faster ramps than beginners. Use their race history and "
                    "peak volumes to calibrate, not a generic 10-15% cap."
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
        
        if self._is_prescription_request(message):
            if is_mini:
                instructions.append("PRESCRIPTION: Match load guidance to athlete's experience level and current build phase.")
            else:
                instructions.append(
                    "PRESCRIPTION REQUEST: The athlete wants workout guidance. "
                    "Match your recommendation to the athlete's experience level: for beginners or athletes "
                    "with thin history, cap at 20% weekly volume increases. For experienced athletes with proven "
                    "high-volume history, trust their capacity and match their training intent. "
                    "Check current form/fatigue data before intensity recommendations."
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
        planned_title = planned.get("title")
        planned_phase = (planned.get("phase") or "").lower() if planned.get("phase") else None
        planned_mi = planned.get("target_distance_mi")
        planned_km = planned.get("target_distance_km")

        runs = (recent_42.get("data", {}) or {}).get("runs") or []

        # Compute baseline from recent runs
        distances_mi = [r.get("distance_mi") for r in runs if r.get("distance_mi") is not None]
        max_run_mi = max(distances_mi) if distances_mi else None

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
    _SPLIT_TERMS_RE = re.compile(r"\b(split|splits|mile split|km split|negative split|pace band)\b", re.I)
    _PROFILE_TERMS_RE = re.compile(r"\b(profile|settings|birthdate|birthday|dob|age|sex|gender|height|email)\b", re.I)
    _PLANNING_TERMS_RE = re.compile(r"\b(should i|plan|tomorrow|next week|workout|rest day|taper|schedule|session)\b", re.I)
    _ANALYSIS_TERMS_RE = re.compile(r"\b(why|trend|compare|pace|heart rate|hr|fatigue|load|split|performance|improv)\b", re.I)
    _LOGISTICS_TERMS_RE = re.compile(r"\b(settings|connect|strava|garmin|billing|subscription|cancel|refund|login|password)\b", re.I)
    _APOLOGY_TERMS_RE = re.compile(r"\b(sorry|my bad|you're right|you are right|i was wrong|apolog)\b", re.I)
    _INTERNAL_LEAK_REWRITES = (
        (re.compile(r"\bsince you built the platform\b", re.I), "based on your profile settings"),
        (re.compile(r"\bdata model\b", re.I), "profile settings"),
        (re.compile(r"\bdatabase\b", re.I), "training history"),
        (re.compile(r"\bsystem prompt\b", re.I), "coach guidance"),
        (re.compile(r"\btool call\b", re.I), "data check"),
        (re.compile(r"\bmodel routing\b", re.I), "coach response path"),
    )



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



