"""
AI Coach Context Module (Phase 4 Refactor)

Handles context building for run instructions and thread context.
Extracted from ai_coach.py for maintainability and testability.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional
from uuid import UUID

from .routing import MessageRouter, COMPARISON_KEYWORDS, RETURN_CONTEXT_PHRASES


class ContextBuilder:
    """
    Builds context for AI Coach runs.
    
    Extracted from AICoach for testability and maintainability.
    """
    
    def __init__(self, router: Optional[MessageRouter] = None):
        self.router = router or MessageRouter()
        self._COMPARISON_KEYWORDS = COMPARISON_KEYWORDS
        self._RETURN_CONTEXT_PHRASES = RETURN_CONTEXT_PHRASES
    
    def build_run_instructions(
        self,
        message: str,
        training_load: Optional[Dict[str, Any]] = None,
        is_judgment: bool = False,
        has_return_context: bool = False,
        has_benchmark: bool = False,
        is_prescription: bool = False,
        context_injection: Optional[str] = None,
    ) -> str:
        """
        Build per-run instructions based on message type and athlete state.
        
        Phase 2: These go into `additional_instructions` on the run, NOT as user messages.
        
        Args:
            message: The user's message
            training_load: Current ATL/CTL/TSB data (optional)
            is_judgment: Whether this is a judgment question
            has_return_context: Whether return context was detected
            has_benchmark: Whether a benchmark reference was detected
            is_prescription: Whether this is a prescription request
            context_injection: Additional context to inject
            
        Returns:
            Instruction string for the run.
        """
        instructions: List[str] = []
        ml = (message or "").lower()
        
        # 1. Include current training state if available
        if training_load and not training_load.get("error"):
            atl = training_load.get("atl", 0)
            ctl = training_load.get("ctl", 0)
            tsb = training_load.get("tsb", 0)
            form_state = "fresh" if tsb > 10 else ("fatigued" if tsb < -10 else "balanced")
            instructions.append(
                f"CURRENT TRAINING STATE: ATL={atl:.1f}, CTL={ctl:.1f}, TSB={tsb:.1f} ({form_state}). "
                f"Use this for load/recovery recommendations."
            )
        
        # 2. Question-type-specific instructions
        if is_judgment:
            instructions.append(
                "CRITICAL JUDGMENT INSTRUCTION: The athlete is asking for your JUDGMENT or OPINION. "
                "You MUST answer DIRECTLY first (yes/no/maybe with a confidence level like 'likely', 'unlikely', "
                "'very possible'), THEN provide supporting evidence and any caveats. "
                "Do NOT deflect, ask for constraints, or pivot to 'self-guided mode'. "
                "Give your honest assessment based on their data."
            )
        
        if has_return_context:
            instructions.append(
                "RETURN-FROM-INJURY CONTEXT: This athlete mentioned returning from injury/break. "
                "All comparisons should DEFAULT to the post-return period unless they explicitly specify otherwise. "
                "Do NOT compare against pre-injury peaks without asking first. "
                "Favor conservative load recommendations (10-15% weekly increases)."
            )
        
        if has_benchmark:
            instructions.append(
                "BENCHMARK REFERENCE DETECTED: The athlete referenced a past benchmark (PR, race shape, peak form). "
                "Compare their CURRENT metrics to that benchmark and provide specific numbers and timeline estimates. "
                "Be honest about realistic recovery timelines based on their recent training load and patterns."
            )
        
        if is_prescription:
            instructions.append(
                "PRESCRIPTION REQUEST: The athlete wants workout guidance. "
                "Use conservative bounds: do not prescribe more than 20% weekly volume increase, "
                "check TSB before intensity recommendations, and prioritize injury prevention."
            )
        
        # 3. Include context injection if provided
        if context_injection:
            instructions.append(context_injection)
        
        if not instructions:
            return ""
        
        header = "=== DYNAMIC RUN INSTRUCTIONS (Phase 2) ===\n"
        return header + "\n\n".join(instructions)
    
    def build_context_injection(
        self,
        message: str,
        prior_user_messages: Optional[List[str]] = None,
    ) -> Optional[str]:
        """
        Build context injection for comparison/return-context messages.
        
        Args:
            message: The current user message
            prior_user_messages: Recent user messages from thread history
            
        Returns:
            Context injection string or None if not needed.
        """
        text = (message or "").strip()
        if not text:
            return None

        lower = text.lower()
        mentions_comparison = any(k in lower for k in self._COMPARISON_KEYWORDS)
        return_ctx = self.router.has_return_context(lower) or any(
            self.router.has_return_context((m or "").lower()) 
            for m in (prior_user_messages or [])
        )

        # Only inject when it matters
        if not (mentions_comparison or return_ctx):
            return None

        # Build bounded snippets from prior messages
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
            "recommended_recent_window_days": 84,
        }

        lines: List[str] = []
        lines.append("INTERNAL COACH CONTEXT (do not repeat verbatim):")
        lines.append(f"- Flags: {json.dumps(flags, separators=(',', ':'))}")

        if return_ctx:
            lines.append(
                "- User mentioned 'since coming back / after injury / recent return'. "
                "Always ask for the exact return date or injury/break details BEFORE any "
                "longest/slowest/fastest/best/worst/most/least/hardest/easiest comparisons. "
                "Do NOT assume 365-day or all-time scope."
            )
        if mentions_comparison:
            lines.append(
                "- Before answering any superlative/comparison (longest/slowest/fastest/best/worst/most/least/hardest/easiest), "
                "check the last 4-12 weeks first (use tools) and cite receipts. If scope is unclear, ask one clarifying question."
            )
        if snippets:
            lines.append("- Recent athlete messages (most recent first):")
            for s in snippets:
                lines.append(f"  - \"{s}\"")

        return "\n".join(lines).strip()
    
    def build_thin_history_injection(
        self,
        history_snapshot: Dict[str, Any],
        baseline: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Build context message for thin-history situations.
        
        Used when athlete has sparse training data.
        """
        lines: List[str] = []
        lines.append("INTERNAL COACH CONTEXT (do not repeat verbatim):")
        lines.append(f"- Training data coverage is THIN. Snapshot: {json.dumps(history_snapshot, separators=(',', ':'))}")
        
        if baseline:
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
    
    def detect_benchmark_reference(self, message: str) -> bool:
        """Check if message contains benchmark references (past PR, race shape, etc.)."""
        ml = (message or "").lower()
        benchmark_indicators = (
            "marathon shape", "race shape", "pb shape", "pr shape",
            "peak form", "was in", "used to run", "i ran a", "my best",
            "when i was", "at my peak", "my pb", "my pr",
        )
        return any(b in ml for b in benchmark_indicators)


# Singleton instance for easy import
context_builder = ContextBuilder()
