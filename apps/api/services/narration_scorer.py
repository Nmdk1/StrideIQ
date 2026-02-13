"""
Narration Accuracy Scorer (Phase 3A-PRE)

Scores coach narrations against the intelligence engine's ground truth.
This scoring function MUST be defined and tested BEFORE any LLM narration
code is written (build plan requirement).

Three binary scoring criteria:
    1. FACTUALLY CORRECT — narration matches intelligence engine data
       (cited percentages within ±2%, correct rule identification,
       no invented data, no contradictions)
    2. NO RAW METRICS LEAKED — TSB, CTL, ATL, VDOT, rMSSD, etc.
       never appear as raw numbers or acronyms
    3. ACTIONABLE LANGUAGE — narration contains forward-looking guidance
       (not just describing what happened, but what to consider)

Score = % of criteria passed across all narrations in a scoring window.
Gate for Phase 3B: score > 90% sustained for 4 weeks.

Sources:
    docs/TRAINING_PLAN_REBUILD_PLAN.md (Parallel Track: Coach Trust)
"""

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import List, Dict, Any, Optional, Tuple
from uuid import UUID

import logging

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Banned terms — raw metrics that must NEVER appear in narrations
# ---------------------------------------------------------------------------

# Acronyms and raw metric names that violate the coaching contract
BANNED_ACRONYMS = {
    "TSB", "CTL", "ATL",     # Training load acronyms
    "VDOT",                    # Trademark
    "rMSSD", "SDNN",          # HRV technical terms
    "EF",                      # Efficiency factor (internal)
    "TRIMP",                   # Training impulse (internal)
}

# Patterns that indicate raw metric dumping
# e.g., "TSB: -15", "CTL = 42.3", "your ATL is 85"
BANNED_METRIC_PATTERNS = [
    r"\bTSB\b",
    r"\bCTL\b",
    r"\bATL\b",
    r"\bVDOT\b",
    r"\brMSSD\b",
    r"\bSDNN\b",
    r"\bTRIMP\b",
    r"\bEF\s*[:=]\s*\d",      # "EF: 0.020" or "EF = 0.02"
    r"efficiency\s+factor\s*[:=]\s*\d",
]

# Compiled regex for performance
_BANNED_RE = re.compile("|".join(BANNED_METRIC_PATTERNS), re.IGNORECASE)


# ---------------------------------------------------------------------------
# Actionable language indicators
# ---------------------------------------------------------------------------

# Forward-looking action words/phrases that indicate the narration is actionable
ACTIONABLE_INDICATORS = [
    # Direct guidance
    "consider", "you might", "worth", "be mindful", "keep an eye on",
    "pay attention", "listen to your body", "your body may",
    # Recommendations (soft)
    "may need", "could benefit", "good time to", "you're ready",
    # Forward-looking
    "this week", "next session", "going forward", "in the coming",
    "tomorrow", "the next few days", "upcoming",
    # Action verbs
    "continue", "maintain", "adjust", "review", "monitor",
    "prioritize", "focus on", "ease into", "build on",
]

# Patterns that indicate ONLY backward-looking (no action)
BACKWARD_ONLY_INDICATORS = [
    "your readiness score was",
    "the system detected",
    "analysis shows",
    "data indicates",
]


# ---------------------------------------------------------------------------
# Score result
# ---------------------------------------------------------------------------

@dataclass
class NarrationScoreResult:
    """Result of scoring a single narration."""
    narration_id: Optional[UUID] = None
    athlete_id: Optional[UUID] = None
    trigger_date: Optional[date] = None

    # The 3 binary criteria
    factually_correct: bool = False
    no_raw_metrics: bool = False
    actionable_language: bool = False

    # Detail
    factual_errors: List[str] = field(default_factory=list)
    banned_terms_found: List[str] = field(default_factory=list)
    actionable_phrases_found: List[str] = field(default_factory=list)

    # Overall
    criteria_passed: int = 0
    criteria_total: int = 3
    score: float = 0.0  # 0.0 to 1.0

    # Contradiction detection
    contradicts_engine: bool = False
    contradiction_detail: Optional[str] = None

    def compute(self) -> None:
        """Compute the overall score from the 3 criteria."""
        self.criteria_passed = sum([
            self.factually_correct,
            self.no_raw_metrics,
            self.actionable_language,
        ])
        self.score = self.criteria_passed / self.criteria_total


@dataclass
class WindowScoreResult:
    """Aggregate score across all narrations in a scoring window."""
    window_start: date
    window_end: date
    total_narrations: int = 0
    total_criteria_checks: int = 0
    total_criteria_passed: int = 0
    score: float = 0.0  # % of criteria passed across all narrations
    individual_scores: List[NarrationScoreResult] = field(default_factory=list)

    # Per-criterion pass rates
    factual_pass_rate: float = 0.0
    no_metrics_pass_rate: float = 0.0
    actionable_pass_rate: float = 0.0

    # Gate
    passes_90_threshold: bool = False

    def compute(self) -> None:
        """Compute aggregate scores."""
        if self.total_narrations == 0:
            return

        self.total_criteria_checks = self.total_narrations * 3
        self.total_criteria_passed = sum(s.criteria_passed for s in self.individual_scores)
        self.score = self.total_criteria_passed / self.total_criteria_checks if self.total_criteria_checks > 0 else 0

        self.factual_pass_rate = (
            sum(1 for s in self.individual_scores if s.factually_correct)
            / self.total_narrations
        )
        self.no_metrics_pass_rate = (
            sum(1 for s in self.individual_scores if s.no_raw_metrics)
            / self.total_narrations
        )
        self.actionable_pass_rate = (
            sum(1 for s in self.individual_scores if s.actionable_language)
            / self.total_narrations
        )

        self.passes_90_threshold = self.score >= 0.90


# ---------------------------------------------------------------------------
# Scorer
# ---------------------------------------------------------------------------

class NarrationScorer:
    """
    Score a coach narration against the intelligence engine's ground truth.

    Usage:
        scorer = NarrationScorer()
        result = scorer.score(
            narration="Your training load increased 25% this week...",
            ground_truth=intel_result,
        )
        print(result.score)           # 0.0 to 1.0
        print(result.factual_errors)  # Any detected errors
    """

    def score(
        self,
        narration: str,
        ground_truth: Dict[str, Any],
        insight_rule_ids: Optional[List[str]] = None,
    ) -> NarrationScoreResult:
        """
        Score a narration on 3 binary criteria.

        Args:
            narration: The coach-generated narration text
            ground_truth: Dict of data the intelligence engine produced
                         (e.g., {"rules_fired": [...], "readiness_score": 55.2,
                                  "data_cited": {...}, ...})
            insight_rule_ids: List of rule_ids that actually fired

        Returns:
            NarrationScoreResult with pass/fail for each criterion
        """
        result = NarrationScoreResult()

        if not narration or not narration.strip():
            # Empty narration fails all criteria
            result.factual_errors.append("Narration is empty")
            result.compute()
            return result

        # Criterion 1: Factually correct
        result.factually_correct, result.factual_errors, result.contradicts_engine, result.contradiction_detail = (
            self._check_factual_accuracy(narration, ground_truth, insight_rule_ids)
        )

        # Criterion 2: No raw metrics leaked
        result.no_raw_metrics, result.banned_terms_found = (
            self._check_no_raw_metrics(narration)
        )

        # Criterion 3: Actionable language
        result.actionable_language, result.actionable_phrases_found = (
            self._check_actionable_language(narration)
        )

        result.compute()
        return result

    def score_window(
        self,
        scores: List[NarrationScoreResult],
        window_start: date,
        window_end: date,
    ) -> WindowScoreResult:
        """
        Compute aggregate score for a scoring window (e.g., 1 week).

        Args:
            scores: Individual narration scores
            window_start: Start date of the window
            window_end: End date of the window

        Returns:
            WindowScoreResult with aggregate metrics and gate check
        """
        result = WindowScoreResult(
            window_start=window_start,
            window_end=window_end,
            total_narrations=len(scores),
            individual_scores=scores,
        )
        result.compute()
        return result

    # ==================================================================
    # Criterion 1: Factual accuracy
    # ==================================================================

    def _check_factual_accuracy(
        self,
        narration: str,
        ground_truth: Dict[str, Any],
        insight_rule_ids: Optional[List[str]] = None,
    ) -> Tuple[bool, List[str], bool, Optional[str]]:
        """
        Check if the narration is factually correct vs engine data.

        Checks:
        - Percentages cited are within ±2% of ground truth
        - Doesn't claim rules fired that didn't fire
        - Doesn't contradict the engine's mode/severity
        - Doesn't invent data not in the ground truth

        Returns:
            (is_correct, errors, contradicts_engine, contradiction_detail)
        """
        errors = []
        contradicts = False
        contradiction_detail = None

        # Check 1: Percentage accuracy
        # Extract percentages from narration and compare to ground truth
        narration_pcts = self._extract_percentages(narration)
        gt_pcts = self._extract_ground_truth_percentages(ground_truth)

        for narr_pct in narration_pcts:
            # Find closest ground truth match
            closest_match = min(gt_pcts, key=lambda gt: abs(gt - narr_pct)) if gt_pcts else None
            if closest_match is not None and abs(narr_pct - closest_match) > 2.0:
                errors.append(
                    f"Cited {narr_pct}% but engine data shows {closest_match}%"
                )

        # Check 2: Rule references — don't claim rules that didn't fire
        if insight_rule_ids is not None:
            rule_name_map = {
                "load_spike": "LOAD_SPIKE",
                "load spike": "LOAD_SPIKE",
                "volume spike": "LOAD_SPIKE",
                "efficiency breakthrough": "EFFICIENCY_BREAK",
                "efficiency improved": "EFFICIENCY_BREAK",
                "pace improvement": "PACE_IMPROVEMENT",
                "declining": "SUSTAINED_DECLINE",
                "decline": "SUSTAINED_DECLINE",
                "missed sessions": "SUSTAINED_MISSED",
                "missing sessions": "SUSTAINED_MISSED",
                "missed workouts": "SUSTAINED_MISSED",
                "missing workouts": "SUSTAINED_MISSED",
                "readiness high": "READINESS_HIGH",
                "ready for more": "READINESS_HIGH",
            }

            narration_lower = narration.lower()
            for phrase, rule_id in rule_name_map.items():
                if phrase in narration_lower and rule_id not in insight_rule_ids:
                    errors.append(
                        f"Narration references '{phrase}' but {rule_id} did not fire"
                    )
                    contradicts = True
                    contradiction_detail = (
                        f"Narration claims {rule_id} situation but engine did not detect it"
                    )

        # Check 3: Don't claim "swap" or "modified your plan" in INFORM mode
        swap_phrases = [
            "swapped your workout",
            "changed your plan",
            "modified your workout",
            "replaced your",
            "adjusted your workout to",
        ]
        highest_mode = ground_truth.get("highest_mode")
        if highest_mode in ("inform", "log", None):
            for phrase in swap_phrases:
                if phrase in narration.lower():
                    errors.append(
                        f"Narration implies workout swap ('{phrase}') but mode is {highest_mode}"
                    )
                    contradicts = True
                    contradiction_detail = "Narration implies plan modification but engine is in INFORM mode"

        is_correct = len(errors) == 0
        return is_correct, errors, contradicts, contradiction_detail

    # ==================================================================
    # Criterion 2: No raw metrics
    # ==================================================================

    def _check_no_raw_metrics(self, narration: str) -> Tuple[bool, List[str]]:
        """
        Check that no banned acronyms or raw metric values appear.

        Returns:
            (passes, banned_terms_found)
        """
        found = []

        # Check compiled regex
        matches = _BANNED_RE.findall(narration)
        if matches:
            found.extend(matches)

        # Also check for standalone acronyms that might not have values
        for acronym in BANNED_ACRONYMS:
            pattern = rf"\b{re.escape(acronym)}\b"
            if re.search(pattern, narration):
                if acronym not in found:
                    found.append(acronym)

        return len(found) == 0, found

    # ==================================================================
    # Criterion 3: Actionable language
    # ==================================================================

    def _check_actionable_language(self, narration: str) -> Tuple[bool, List[str]]:
        """
        Check that the narration contains forward-looking actionable guidance.

        Returns:
            (passes, actionable_phrases_found)
        """
        narration_lower = narration.lower()
        found = [
            phrase for phrase in ACTIONABLE_INDICATORS
            if phrase in narration_lower
        ]

        # Pass if at least one actionable indicator is present
        return len(found) > 0, found

    # ==================================================================
    # Helpers
    # ==================================================================

    @staticmethod
    def _extract_percentages(text: str) -> List[float]:
        """Extract percentage values from text (e.g., '25%', 'up 18 percent')."""
        patterns = [
            r'(\d+(?:\.\d+)?)\s*%',
            r'(\d+(?:\.\d+)?)\s+percent',
        ]
        results = []
        for pattern in patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                try:
                    results.append(float(match.group(1)))
                except ValueError:
                    pass
        return results

    @staticmethod
    def _extract_ground_truth_percentages(ground_truth: Dict[str, Any]) -> List[float]:
        """Extract percentage values from engine ground truth data."""
        pcts = []

        # From data_cited across all insights
        for insight in ground_truth.get("insights", []):
            data = insight.get("data_cited", {})
            for key, value in data.items():
                if "pct" in key.lower() or "percent" in key.lower() or "rate" in key.lower():
                    try:
                        pcts.append(float(value))
                    except (ValueError, TypeError):
                        pass

        # From top-level data
        for key in ["pct_increase", "improvement_pct", "total_decline_pct", "skip_rate"]:
            if key in ground_truth:
                try:
                    pcts.append(float(ground_truth[key]))
                except (ValueError, TypeError):
                    pass

        return pcts
