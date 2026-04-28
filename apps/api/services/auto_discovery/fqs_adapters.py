"""
Finding Quality Score (FQS) v1 — Origin-aware adapters.

FQS v1 is intentionally honest about what is measured exactly versus
inferred from current data structures.  Each adapter returns:

    {
        "origin": "correlation" | "investigation",
        "base_score": float,
        "final_score": float,
        "components": {
            "confidence": float,
            "specificity": float,
            "actionability": float,
            "stability": float,
            "cascade_bonus": float,
        },
        "component_quality": {
            "confidence":     "exact" | "inferred",
            "specificity":    "exact" | "inferred",
            "actionability":  "exact" | "registry_default",
            "stability":      "exact" | "inferred",
        },
    }

Cascade bonus is only awarded when the underlying chain evidence is
explicitly persisted.  If not present, it is 0 — not faked.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from models import CorrelationFinding, AthleteFinding

FQSResult = Dict[str, Any]

# Default actionability score used when no registry entry is available.
_REGISTRY_DEFAULT_ACTIONABILITY = 0.5

# Map confidence tier labels → numeric score.
_CONFIDENCE_TIER_MAP: Dict[str, float] = {
    "table_stakes": 0.3,
    "suggestive": 0.5,
    "genuine": 0.8,
}

# Recency decay: a finding confirmed > 180 days ago gets a penalty.
_RECENCY_FULL_CREDIT_DAYS = 30
_RECENCY_FLOOR = 0.1


def _recency_score(last_confirmed_at: Optional[datetime]) -> float:
    """Return a 0-1 recency factor.  Confirmed today → 1.0; very old → 0.1."""
    if last_confirmed_at is None:
        return _RECENCY_FLOOR
    now = datetime.now(timezone.utc)
    if last_confirmed_at.tzinfo is None:
        last_confirmed_at = last_confirmed_at.replace(tzinfo=timezone.utc)
    age_days = max(0, (now - last_confirmed_at).days)
    if age_days <= _RECENCY_FULL_CREDIT_DAYS:
        return 1.0
    # Exponential decay with half-life of 90 days.
    return max(_RECENCY_FLOOR, math.exp(-age_days / 90.0))


class CorrelationFindingFQSAdapter:
    """
    Scores a CorrelationFinding.

    Confidence (exact):
        Derived from times_confirmed (confirmation weight) × recency of
        last_confirmed_at × is_active indicator.

    Specificity (inferred):
        Inferred from layer richness: whether threshold, asymmetry, decay,
        and mediator data is populated.  Not a direct measurement.

    Actionability (registry_default):
        No per-input actionability metadata exists yet in Phase 0.
        Defaults to 0.5 for all inputs.

    Stability (inferred):
        Inferred from confirmation recency and is_active status.
    """

    COMPONENT_QUALITY = {
        "confidence": "exact",
        "specificity": "inferred",
        "actionability": "registry_default",
        "stability": "inferred",
    }

    def score(self, finding: "CorrelationFinding") -> FQSResult:
        confidence = self._confidence(finding)
        specificity = self._specificity(finding)
        actionability = _REGISTRY_DEFAULT_ACTIONABILITY
        stability = self._stability(finding)
        cascade_bonus = self._cascade_bonus(finding)

        components: Dict[str, float] = {
            "confidence": confidence,
            "specificity": specificity,
            "actionability": actionability,
            "stability": stability,
            "cascade_bonus": cascade_bonus,
        }

        base_score = (
            0.35 * confidence
            + 0.25 * specificity
            + 0.20 * actionability
            + 0.20 * stability
        )
        final_score = min(1.0, base_score + cascade_bonus)

        return {
            "origin": "correlation",
            "base_score": round(base_score, 4),
            "final_score": round(final_score, 4),
            "components": {k: round(v, 4) for k, v in components.items()},
            "component_quality": self.COMPONENT_QUALITY,
        }

    def score_shadow_dict(self, c: Dict[str, Any]) -> FQSResult:
        """
        Score a raw shadow correlation dict produced by the rescan loop.

        Shadow correlation dicts have no persisted layer metadata
        (threshold, asymmetry, decay) so specificity and cascade are
        inferred from available fields only.  All component_quality labels
        remain the same as for persisted findings.

        Required dict keys (from CorrelationResult.to_dict()):
            input_name, correlation_coefficient, p_value, sample_size,
            direction, time_lag_days, strength
        """
        # Confidence: derived from sample size (no times_confirmed in shadow).
        # Use |r| × log-scaled sample weight as a proxy.
        abs_r = abs(c.get("correlation_coefficient") or 0.0)
        n = c.get("sample_size") or 0
        sample_weight = min(1.0, math.log1p(max(0, n - 10)) / math.log1p(50))
        confidence = round(abs_r * sample_weight, 4)

        # Specificity: from lag presence + sample support.
        specificity = 0.0
        if (c.get("time_lag_days") or 0) > 0:
            specificity += 0.3
        if n >= 20:
            specificity += 0.2
        if abs_r >= 0.5:
            specificity += 0.2
        if c.get("strength") == "strong":
            specificity += 0.3
        elif c.get("strength") == "moderate":
            specificity += 0.15
        specificity = min(1.0, round(specificity, 4))

        actionability = _REGISTRY_DEFAULT_ACTIONABILITY
        stability = round(sample_weight * abs_r, 4)
        cascade_bonus = 0.0  # no layer evidence in shadow dicts

        components: Dict[str, float] = {
            "confidence": confidence,
            "specificity": specificity,
            "actionability": actionability,
            "stability": stability,
            "cascade_bonus": cascade_bonus,
        }

        base_score = (
            0.35 * confidence
            + 0.25 * specificity
            + 0.20 * actionability
            + 0.20 * stability
        )
        final_score = min(1.0, base_score + cascade_bonus)

        return {
            "origin": "correlation_shadow",
            "base_score": round(base_score, 4),
            "final_score": round(final_score, 4),
            "components": {k: round(v, 4) for k, v in components.items()},
            "component_quality": self.COMPONENT_QUALITY,
        }

    def _confidence(self, finding: "CorrelationFinding") -> float:
        # Logarithmic saturation: diminishing returns past ~20 confirmations.
        confirmation_weight = min(1.0, math.log1p(finding.times_confirmed) / math.log1p(20))
        recency = _recency_score(finding.last_confirmed_at)
        active_bonus = 1.0 if finding.is_active else 0.5
        return round(confirmation_weight * recency * active_bonus, 4)

    def _specificity(self, finding: "CorrelationFinding") -> float:
        # Layer richness: each populated layer adds specificity credit.
        score = 0.0
        if finding.threshold_value is not None:
            score += 0.25
        if finding.asymmetry_ratio is not None:
            score += 0.25
        if finding.decay_half_life_days is not None:
            score += 0.25
        # Mediator requires DB query; use lag precision as proxy instead.
        if finding.time_lag_days and finding.time_lag_days > 0:
            score += 0.15
        # Sample size adds modest specificity.
        if finding.sample_size and finding.sample_size >= 20:
            score += 0.10
        return min(1.0, score)

    def _stability(self, finding: "CorrelationFinding") -> float:
        recency = _recency_score(finding.last_confirmed_at)
        active_factor = 1.0 if finding.is_active else 0.4
        return round(recency * active_factor, 4)

    def _cascade_bonus(self, finding: "CorrelationFinding") -> float:
        # Only award cascade bonus when explicit layer evidence exists.
        # Threshold + asymmetry + decay all populated → full bonus.
        layers = sum([
            finding.threshold_value is not None,
            finding.asymmetry_ratio is not None,
            finding.decay_half_life_days is not None,
        ])
        if layers >= 3:
            return 0.05
        return 0.0


class AthleteFindingFQSAdapter:
    """
    Scores an AthleteFinding (investigation-derived, Living Fingerprint).

    Confidence (inferred):
        Confidence tier → numeric score, then attenuated by recency.

    Specificity (inferred):
        Receipts richness (count of receipt fields) × sentence length
        heuristic.  Both are proxies; explicitly labeled as inferred.

    Actionability (registry_default):
        No per-investigation actionability metadata exists in Phase 0
        beyond the pilot-subset extensions.  Defaults to 0.5.

    Stability (inferred):
        Inferred from supersession history (is_active, superseded_at)
        and persistence over time (last_confirmed_at age).
    """

    COMPONENT_QUALITY = {
        "confidence": "inferred",
        "specificity": "inferred",
        "actionability": "registry_default",
        "stability": "inferred",
    }

    def score(self, finding: "AthleteFinding") -> FQSResult:
        confidence = self._confidence(finding)
        specificity = self._specificity(finding)
        actionability = _REGISTRY_DEFAULT_ACTIONABILITY
        stability = self._stability(finding)
        cascade_bonus = 0.0  # No explicit chain evidence in Phase 0

        components: Dict[str, float] = {
            "confidence": confidence,
            "specificity": specificity,
            "actionability": actionability,
            "stability": stability,
            "cascade_bonus": cascade_bonus,
        }

        base_score = (
            0.35 * confidence
            + 0.25 * specificity
            + 0.20 * actionability
            + 0.20 * stability
        )
        final_score = min(1.0, base_score + cascade_bonus)

        return {
            "origin": "investigation",
            "base_score": round(base_score, 4),
            "final_score": round(final_score, 4),
            "components": {k: round(v, 4) for k, v in components.items()},
            "component_quality": self.COMPONENT_QUALITY,
        }

    def _confidence(self, finding: "AthleteFinding") -> float:
        tier_score = _CONFIDENCE_TIER_MAP.get(getattr(finding, "confidence", None), 0.4)
        recency = _recency_score(getattr(finding, "last_confirmed_at", None))
        return round(tier_score * recency, 4)

    def _specificity(self, finding: "AthleteFinding") -> float:
        # Receipts richness: number of keys in receipts dict.
        receipts = getattr(finding, "receipts", None) or {}
        receipt_count = len(receipts) if isinstance(receipts, dict) else 0
        receipt_score = min(1.0, receipt_count / 5.0)
        # Sentence length heuristic: longer sentences are usually more specific.
        sentence = getattr(finding, "sentence", None) or ""
        word_count = len(sentence.split())
        sentence_score = min(1.0, word_count / 40.0)
        return round(0.6 * receipt_score + 0.4 * sentence_score, 4)

    def _stability(self, finding: "AthleteFinding") -> float:
        # Penalise superseded findings; active findings get recency weight.
        if not getattr(finding, "is_active", True):
            return 0.2
        recency = _recency_score(getattr(finding, "last_confirmed_at", None))
        # Longevity bonus: found > 30 days ago and still active.
        first = getattr(finding, "first_detected_at", None)
        if first:
            if first.tzinfo is None:
                first = first.replace(tzinfo=timezone.utc)
            longevity_days = (datetime.now(timezone.utc) - first).days
            longevity_factor = min(1.0, longevity_days / 30.0)
        else:
            longevity_factor = 0.0
        return round(0.6 * recency + 0.4 * longevity_factor, 4)

    def score_finding_list(self, findings: list) -> float:
        """
        Aggregate FQS score for a list of AthleteFinding objects.

        Used by the tuning loop to compare baseline vs candidate finding sets.
        Returns the mean final_score, or 0.0 if findings is empty.
        """
        if not findings:
            return 0.0
        scores = [self.score(f)["final_score"] for f in findings]
        return round(sum(scores) / len(scores), 4)
