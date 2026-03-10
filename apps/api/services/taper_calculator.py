"""
Taper Calculator — Personalized Taper Duration (Phase 1D)

Evaluates all available taper signals and returns a recommendation.
The system uses OBSERVABLE ATHLETE BEHAVIOR as the primary signal,
not model parameters.

Signal priority hierarchy (ADR-062):
    1. Observed taper history  — what worked before this athlete's best races
    2. Recovery rebound speed  — how fast they bounce back (Phase 1C)
    3. Banister model          — τ1/τ2-based calculation (when calibrated)
    4. Population defaults     — honest about being a template

Key principle: N=1 always wins.  Every athlete preference expressed
through their actual race history overrides any model or default.

ADR: docs/ADR_062_TAPER_DEMOCRATIZATION.md
"""

import logging
from dataclasses import dataclass
from typing import Any, List, Optional

from services.plan_framework.constants import (
    TAPER_DAYS_BY_REBOUND,
    TAPER_DAYS_DEFAULT,
    Distance,
    ReboundSpeed,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------


@dataclass
class TaperRecommendation:
    """Result of taper signal evaluation."""

    taper_days: int
    source: str          # "race_history" | "recovery_rebound" | "banister" | "default"
    confidence: float    # 0.0-1.0
    rationale: str       # Human-readable explanation
    disclosure: str      # What the athlete should know


# ---------------------------------------------------------------------------
# Rebound speed classification
# ---------------------------------------------------------------------------


def classify_rebound_speed(recovery_half_life_hours: float) -> ReboundSpeed:
    """
    Classify recovery rebound speed from half-life.

    ≤ 36h  → FAST   (quick adapter, shorter taper)
    ≤ 60h  → NORMAL (standard)
    > 60h  → SLOW   (retains fitness longer, longer taper OK)
    """
    if recovery_half_life_hours <= 36:
        return ReboundSpeed.FAST
    elif recovery_half_life_hours <= 60:
        return ReboundSpeed.NORMAL
    else:
        return ReboundSpeed.SLOW


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class TaperCalculator:
    """
    Evaluate all available taper signals and return a recommendation.

    Stateless — all inputs are passed explicitly.  No database access.
    The caller (generator.py) is responsible for gathering the inputs.
    """

    def calculate(
        self,
        distance: str,
        profile: Any = None,                     # AthleteProfile (Phase 1C)
        banister_model: Any = None,               # BanisterModel (IPM)
        observed_taper: Any = None,               # ObservedTaperPattern
    ) -> TaperRecommendation:
        """
        Select the best taper signal and return a recommendation.

        Args:
            distance: Goal race distance (e.g. "marathon", "half_marathon")
            profile: AthleteProfile with recovery_half_life_hours
            banister_model: Calibrated BanisterModel (if available)
            observed_taper: ObservedTaperPattern from pre_race_fingerprinting

        Returns:
            TaperRecommendation with taper_days, source, confidence, rationale
        """
        try:
            dist = Distance(distance)
        except ValueError:
            dist = Distance.MARATHON

        # --- Priority 1: Observed taper history ---
        result = self._try_observed_taper(observed_taper, dist)
        if result is not None:
            return result

        # --- Priority 2: Recovery rebound speed ---
        result = self._try_recovery_rebound(profile, dist)
        if result is not None:
            return result

        # --- Priority 3: Banister model ---
        result = self._try_banister(banister_model, dist)
        if result is not None:
            return result

        # --- Priority 4: Population defaults ---
        return self._default_taper(dist)

    # ------------------------------------------------------------------
    # Priority 1: Observed taper history
    # ------------------------------------------------------------------

    def _try_observed_taper(
        self, observed_taper: Any, dist: Distance
    ) -> Optional[TaperRecommendation]:
        """Use pre-race taper patterns from the athlete's best races."""
        if observed_taper is None:
            return None

        # ObservedTaperPattern has .taper_days, .confidence, .rationale
        taper_days = getattr(observed_taper, "taper_days", None)
        confidence = getattr(observed_taper, "confidence", 0.0)

        if taper_days is None or confidence < 0.3:
            return None

        # Clamp to sane range (3-21 days)
        taper_days = max(3, min(21, taper_days))

        rationale = getattr(observed_taper, "rationale", "Based on your race history.")

        logger.info(
            "Taper signal: observed history → %d days (confidence=%.2f)",
            taper_days, confidence,
        )
        return TaperRecommendation(
            taper_days=taper_days,
            source="race_history",
            confidence=confidence,
            rationale=rationale,
            disclosure=(
                f"Your taper is based on what worked before your best races. "
                f"We analyzed your pre-race volume patterns and found "
                f"~{taper_days}-day tapers produced your strongest performances."
            ),
        )

    # ------------------------------------------------------------------
    # Priority 2: Recovery rebound speed
    # ------------------------------------------------------------------

    def _try_recovery_rebound(
        self, profile: Any, dist: Distance
    ) -> Optional[TaperRecommendation]:
        """Map recovery half-life to taper days.  No τ1 conversion."""
        if profile is None:
            return None

        half_life = getattr(profile, "recovery_half_life_hours", None)
        recovery_conf = getattr(profile, "recovery_confidence", 0.0)

        if half_life is None or recovery_conf < 0.4:
            return None

        rebound = classify_rebound_speed(half_life)
        taper_days = TAPER_DAYS_BY_REBOUND.get((rebound, dist))

        if taper_days is None:
            return None

        # Confidence: use the recovery confidence from the profile,
        # slightly discounted because this is a mapping, not direct observation
        confidence = min(1.0, recovery_conf * 0.9)

        speed_label = {
            ReboundSpeed.FAST: "fast",
            ReboundSpeed.NORMAL: "normal",
            ReboundSpeed.SLOW: "slower",
        }[rebound]

        logger.info(
            "Taper signal: recovery rebound (%s, %.0fh) → %d days",
            rebound.value, half_life, taper_days,
        )
        return TaperRecommendation(
            taper_days=taper_days,
            source="recovery_rebound",
            confidence=confidence,
            rationale=(
                f"Your recovery speed is {speed_label} "
                f"(half-life ~{half_life:.0f}h). "
                f"A {taper_days}-day taper lets fatigue clear without "
                f"losing the fitness you've built."
            ),
            disclosure=(
                f"Your taper length is based on how quickly you bounce back "
                f"from hard training. We measured your recovery rate from "
                f"your training history."
            ),
        )

    # ------------------------------------------------------------------
    # Priority 3: Banister model
    # ------------------------------------------------------------------

    def _try_banister(
        self, banister_model: Any, dist: Distance
    ) -> Optional[TaperRecommendation]:
        """Use Banister model's calculate_optimal_taper_days() when calibrated."""
        if banister_model is None:
            return None

        # Only use if the model has meaningful confidence
        confidence_val = getattr(banister_model, "confidence", None)
        if confidence_val is None:
            return None

        # ModelConfidence enum: high, moderate, low, uncalibrated
        conf_str = confidence_val.value if hasattr(confidence_val, "value") else str(confidence_val)
        if conf_str in ("uncalibrated", "low"):
            return None

        taper_days = banister_model.calculate_optimal_taper_days()
        taper_days = max(3, min(21, taper_days))

        # Map model confidence to numeric
        conf_numeric = 0.7 if conf_str == "high" else 0.5

        rationale_text = getattr(banister_model, "get_taper_rationale", lambda: "")()
        if not rationale_text:
            rationale_text = (
                f"Your calibrated performance model suggests a "
                f"{taper_days}-day taper based on your individual "
                f"fitness/fatigue response rates."
            )

        logger.info(
            "Taper signal: Banister model → %d days (confidence=%s)",
            taper_days, conf_str,
        )
        return TaperRecommendation(
            taper_days=taper_days,
            source="banister",
            confidence=conf_numeric,
            rationale=rationale_text,
            disclosure=(
                f"Your taper is based on a calibrated performance model "
                f"fitted to your training and race history. The model "
                f"has {conf_str} confidence."
            ),
        )

    # ------------------------------------------------------------------
    # Priority 4: Population defaults
    # ------------------------------------------------------------------

    def _default_taper(self, dist: Distance) -> TaperRecommendation:
        """Fall back to distance-appropriate population defaults."""
        taper_days = TAPER_DAYS_DEFAULT.get(dist, 14)

        logger.info(
            "Taper signal: population default → %d days for %s",
            taper_days, dist.value,
        )
        return TaperRecommendation(
            taper_days=taper_days,
            source="default",
            confidence=0.2,
            rationale=(
                f"Standard {taper_days}-day taper for {dist.value.replace('_', ' ')}. "
                f"As we learn more about your training, this will become personalized."
            ),
            disclosure=(
                f"Your taper uses a standard template — we don't yet have "
                f"enough data to personalize it. This will improve as you "
                f"train and race with the system."
            ),
        )
