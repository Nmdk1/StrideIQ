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
    COACH_MAX_REQUESTS_PER_DAY,
    COACH_MAX_OPUS_REQUESTS_PER_DAY,
    COACH_MONTHLY_TOKEN_BUDGET,
    COACH_MONTHLY_OPUS_TOKEN_BUDGET,
    COACH_MAX_OPUS_REQUESTS_PER_DAY_VIP,
    COACH_MONTHLY_OPUS_TOKEN_BUDGET_VIP,
)


class BudgetMixin:
    """Mixin extracted from AICoach - budget methods."""

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
    # P1-D: CONSENT-GATED LLM DISPATCH
    # =========================================================================



    def _dispatch_llm(self, prompt: str, athlete_id: "UUID" = None) -> str:
        """
        Central LLM dispatch point for the AI coach.

        This method exists as the testable dispatch hook so that consent
        gating tests can verify via patching that no LLM call is made when
        has_ai_consent() returns False.  The consent check in chat() runs
        before this method is ever reached.
        """
        raise NotImplementedError(
            "_dispatch_llm is a dispatch stub — real calls go through "
            "self.gemini_client or self.anthropic_client inside chat()."
        )

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
            is_opus: Whether this is a premium Anthropic lane query (Sonnet).
                     Parameter name retained for CoachUsage schema compatibility —
                     semantics are "premium Anthropic lane" (now claude-sonnet-4-6).
            is_vip: Whether athlete is VIP (gets higher premium-lane caps)
            
        Returns:
            (allowed, reason) - True if request can proceed, else False with reason
        """
        try:
            if self._is_founder(athlete_id):
                return True, "founder_bypass"

            usage = self._get_or_create_usage(athlete_id)
            
            # Daily request limit (same for VIP and standard)
            if usage.requests_today >= COACH_MAX_REQUESTS_PER_DAY:
                return False, "daily_request_limit"
            
            # Premium Anthropic lane limits (founder bypass handled above).
            # CoachUsage schema uses opus_* column names for compatibility
            if is_opus:
                max_opus_daily = (
                    COACH_MAX_OPUS_REQUESTS_PER_DAY_VIP
                    if is_vip
                    else COACH_MAX_OPUS_REQUESTS_PER_DAY
                )
                max_opus_monthly = (
                    COACH_MONTHLY_OPUS_TOKEN_BUDGET_VIP
                    if is_vip
                    else COACH_MONTHLY_OPUS_TOKEN_BUDGET
                )
                
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
            is_opus: Whether this was a premium Anthropic lane query (Sonnet).
                     Parameter/field name retained for CoachUsage schema compatibility.
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
                # Kimi K2.5: $0.383/1M input, $1.72/1M output
                cost_cents = int((input_tokens * 0.0383 + output_tokens * 0.172) / 100)
            elif "gemini" in model.lower():
                # Gemini 3 Flash: $0.50/1M input, $3.00/1M output (Mar 2026)
                cost_cents = int((input_tokens * 0.05 + output_tokens * 0.30) / 100)
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
        VIP athletes see higher premium-lane hard caps.
        """
        try:
            usage = self._get_or_create_usage(athlete_id)
            is_vip = self.is_athlete_vip(athlete_id)
            max_opus_daily = (
                COACH_MAX_OPUS_REQUESTS_PER_DAY_VIP
                if is_vip
                else COACH_MAX_OPUS_REQUESTS_PER_DAY
            )
            max_opus_monthly = (
                COACH_MONTHLY_OPUS_TOKEN_BUDGET_VIP
                if is_vip
                else COACH_MONTHLY_OPUS_TOKEN_BUDGET
            )
            
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



