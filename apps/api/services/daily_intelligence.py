"""
Daily Intelligence Engine (Phase 2C)

NOT a rules engine that swaps workouts. An intelligence engine that surfaces
information, learns from outcomes, and intervenes ONLY at extremes.
The athlete decides. The system learns.

Three operating modes:
    INFORM (default):  Surface data the athlete can't easily hold in their head.
    SUGGEST (earned):  Surface personal patterns from outcome data.
    INTERVENE (extreme): Flag sustained negative trends. Still not an override.

Seven intelligence rules:
    1. LOAD_SPIKE           → INFORM: volume/intensity change detected
    2. SELF_REG_DELTA       → LOG + LEARN: planned ≠ actual
    3. EFFICIENCY_BREAK     → INFORM: efficiency breakthrough detected
    4. PACE_IMPROVEMENT     → INFORM: faster pace + lower HR
    5. SUSTAINED_DECLINE    → FLAG: 3+ weeks declining efficiency
    6. SUSTAINED_MISSED     → ASK: pattern of missed sessions
    7. READINESS_HIGH       → SUGGEST: consistently high readiness, not increasing

Sources:
    - _AI_CONTEXT_/KNOWLEDGE_BASE/TRAINING_PHILOSOPHY.md
    - docs/TRAINING_PLAN_REBUILD_PLAN.md (Phase 2C spec)
"""

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Optional, List, Dict, Any
from uuid import UUID


class InsightMode(str, Enum):
    """Operating mode for an intelligence insight."""
    INFORM = "inform"       # Surface data — no action taken
    SUGGEST = "suggest"     # Surface personal patterns — earned through data
    FLAG = "flag"           # Sustained negative trend — prominent, still not override
    ASK = "ask"             # Ask the athlete for context
    LOG = "log"             # Silent logging — no user-facing output


@dataclass
class IntelligenceInsight:
    """A single intelligence insight from the daily engine."""
    rule_id: str                              # e.g., "LOAD_SPIKE"
    mode: InsightMode                         # Operating mode
    message: str                              # Human-readable insight
    data_cited: Dict[str, Any] = field(default_factory=dict)  # Evidence
    confidence: float = 0.0                   # 0-1 confidence in the insight
    workout_swap: bool = False                # MUST be False in INFORM/SUGGEST mode
    suggested_action: Optional[str] = None    # Only in SUGGEST/FLAG mode


@dataclass
class IntelligenceResult:
    """Result of running all intelligence rules for an athlete on a date."""
    athlete_id: UUID
    target_date: date
    insights: List[IntelligenceInsight] = field(default_factory=list)
    readiness_score: Optional[float] = None
    self_regulation_logged: bool = False       # Whether a planned≠actual delta was detected

    @property
    def highest_mode(self) -> Optional[InsightMode]:
        """Return the highest-severity mode across all insights."""
        if not self.insights:
            return None
        priority = {InsightMode.LOG: 0, InsightMode.INFORM: 1,
                    InsightMode.ASK: 2, InsightMode.SUGGEST: 3, InsightMode.FLAG: 4}
        return max(self.insights, key=lambda i: priority.get(i.mode, 0)).mode

    @property
    def has_workout_swap(self) -> bool:
        """Check if ANY insight attempted to swap a workout."""
        return any(i.workout_swap for i in self.insights)


# The 7 intelligence rules
INTELLIGENCE_RULES = [
    "LOAD_SPIKE",           # 1. Volume/intensity spike detected
    "SELF_REG_DELTA",       # 2. Planned ≠ actual (self-regulation)
    "EFFICIENCY_BREAK",     # 3. Efficiency breakthrough
    "PACE_IMPROVEMENT",     # 4. Faster pace + lower HR
    "SUSTAINED_DECLINE",    # 5. 3+ weeks declining efficiency
    "SUSTAINED_MISSED",     # 6. Pattern of missed sessions
    "READINESS_HIGH",       # 7. Consistently high readiness
]


class DailyIntelligenceEngine:
    """
    Run intelligence rules for an athlete on a given date.

    Default mode is INFORM — no workout swapping without explicit athlete opt-in.
    INTERVENE mode fires only on sustained (3+ week) negative trends.
    """

    def evaluate(
        self,
        athlete_id: UUID,
        target_date: date,
        db: Any,
        readiness_score: Optional[float] = None,
    ) -> IntelligenceResult:
        """
        Evaluate all intelligence rules for an athlete.

        Args:
            athlete_id: The athlete's UUID
            target_date: Date to evaluate
            db: Database session
            readiness_score: Pre-computed readiness (optional, will compute if absent)

        Returns:
            IntelligenceResult with insights and metadata
        """
        raise NotImplementedError(
            "Phase 2C: Daily intelligence engine not yet implemented. "
            "See TRAINING_PLAN_REBUILD_PLAN.md section 2C for spec."
        )
