"""
Narrative Translator (ADR-033)

Converts algorithmic signals into human-first sentences.

No LLM. No API calls. Just templates with dynamic anchors.
The data is already computed — this is rendering, not reasoning.

Philosophy: The skeleton can repeat. The anchors make it fresh.
"You bounced back fast" is stale by month 2.
"You bounced back from Dec 15 faster than April" is specific to this athlete.
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import List, Dict, Optional, Tuple
from uuid import UUID
import logging
import hashlib

from sqlalchemy.orm import Session

from services.fitness_bank import FitnessBank, ConstraintType, ExperienceLevel
from services.anchor_finder import (
    AnchorFinder,
    InjuryReboundAnchor,
    WorkoutAnchor,
    EfficiencyAnchor,
    LoadStateAnchor,
    RaceAnchor,
    MilestoneAnchor,
    format_date_relative,
    format_pace
)
from services.audit_logger import log_narrative_generated

logger = logging.getLogger(__name__)


# =============================================================================
# NARRATIVE DATA CLASSES
# =============================================================================

@dataclass
class Narrative:
    """A rendered narrative with metadata."""
    text: str
    signal_type: str
    priority: int  # Higher = more important
    hash: str  # For deduplication
    anchors_used: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "text": self.text,
            "signal_type": self.signal_type,
            "priority": self.priority
        }


# =============================================================================
# NARRATIVE TRANSLATOR
# =============================================================================

class NarrativeTranslator:
    """
    Translates signals into human-first sentences.
    
    Key insight: The templates are finite. The anchors are infinite.
    Each anchor references something specific in the athlete's history,
    making every sentence unique to this person, this moment.
    """
    
    def __init__(self, db: Session, athlete_id: UUID):
        self.db = db
        self.athlete_id = athlete_id
        self.anchor_finder = AnchorFinder(db, athlete_id)
    
    # =========================================================================
    # LOAD STATE NARRATIVES
    # =========================================================================
    
    def narrate_load_state(
        self,
        tsb: float,
        ctl: float,
        atl: float
    ) -> Optional[Narrative]:
        """
        Narrate current load state (TSB/form).
        
        TSB > +10: Fresh, ready to perform
        TSB -5 to +10: Balanced, normal training
        TSB < -10: Coiled, accumulated fatigue
        """
        if tsb > 10:
            # Fresh — find prior fresh day with good outcome
            anchor = self.anchor_finder.find_prior_race_at_load(ctl, tsb, 15, 10)
            
            if anchor:
                text = (
                    f"TSB is as high as before the {anchor.name}. "
                    f"The hay is in the barn — now use it."
                )
                anchors_used = [f"race:{anchor.date.isoformat()}"]
            else:
                text = "You're fresh. This is when the good sessions happen."
                anchors_used = []
            
            return Narrative(
                text=text,
                signal_type="load_state_fresh",
                priority=80,
                hash=self._hash(text),
                anchors_used=anchors_used
            )
        
        elif tsb < -10:
            # Coiled — find prior coiled day
            anchor = self.anchor_finder.find_comparable_load_state(tsb, 5, 120)
            
            if anchor:
                text = (
                    f"You're coiled like {format_date_relative(anchor.date)}. "
                    f"That day you felt heavy — today's easy should be easy."
                )
                anchors_used = [f"load_state:{anchor.date.isoformat()}"]
            else:
                text = "TSB is deep. Don't turn recovery into another workout."
                anchors_used = []
            
            return Narrative(
                text=text,
                signal_type="load_state_coiled",
                priority=85,
                hash=self._hash(text),
                anchors_used=anchors_used
            )
        
        else:
            # Balanced — less urgent, lower priority
            return Narrative(
                text="Load is balanced. Steady state — keep building.",
                signal_type="load_state_balanced",
                priority=40,
                hash=self._hash("load_balanced"),
                anchors_used=[]
            )
    
    # =========================================================================
    # WORKOUT CONTEXT NARRATIVES
    # =========================================================================
    
    def narrate_workout_context(
        self,
        workout_type: str,
        workout_name: str,
        target_pace: Optional[float] = None
    ) -> Optional[Narrative]:
        """
        Narrate context for an upcoming/planned workout.
        
        "This is the session you crushed before Philly. Trust the legs."
        """
        anchor = self.anchor_finder.find_similar_workout(workout_type, target_pace, 180)
        
        if anchor and anchor.following_race:
            # Found a similar workout followed by a race
            pace_str = f" at {format_pace(anchor.pace_per_mile)}" if anchor.pace_per_mile else ""
            text = (
                f"This is the session you ran{pace_str} "
                f"{anchor.days_to_race} days before {anchor.following_race}. "
                f"Legs remember."
            )
            anchors_used = [f"workout:{anchor.date.isoformat()}", f"race:{anchor.following_race}"]
            priority = 90
            
        elif anchor:
            # Found similar workout but no following race
            text = (
                f"You've done this before — {format_date_relative(anchor.date)}. "
                f"Same structure, same you."
            )
            anchors_used = [f"workout:{anchor.date.isoformat()}"]
            priority = 70
            
        else:
            # First time this structure
            text = (
                f"First time we've prescribed this exact structure. "
                f"Based on your history, you're ready."
            )
            anchors_used = []
            priority = 50
        
        return Narrative(
            text=text,
            signal_type="workout_context",
            priority=priority,
            hash=self._hash(text),
            anchors_used=anchors_used
        )
    
    # =========================================================================
    # INJURY REBOUND NARRATIVES
    # =========================================================================
    
    def narrate_injury_rebound(
        self,
        bank: FitnessBank,
        weeks_since_injury: int
    ) -> Optional[Narrative]:
        """
        Narrate progress in injury recovery.
        
        "Three weeks ago you couldn't run. Now at 70% — faster than the April rebuild."
        """
        if bank.constraint_type != ConstraintType.INJURY:
            return None
        
        current_pct = bank.current_weekly_miles / bank.peak_weekly_miles if bank.peak_weekly_miles > 0 else 0
        
        # Find prior rebound for comparison
        anchor = self.anchor_finder.find_previous_injury_rebound(
            current_injury_start=date.today() - timedelta(weeks=weeks_since_injury + 2)
        )
        
        if anchor:
            comparison = ""
            if weeks_since_injury < anchor.weeks_to_recover:
                comparison = f" — faster than the {format_date_relative(anchor.injury_date)} rebuild"
            elif weeks_since_injury == anchor.weeks_to_recover:
                comparison = f" — same pace as the {format_date_relative(anchor.injury_date)} comeback"
            else:
                comparison = f" — you've been patient, it's paying off"
            
            text = (
                f"{weeks_since_injury} weeks ago you were off. "
                f"Now at {current_pct:.0%} of peak{comparison}."
            )
            anchors_used = [f"rebound:{anchor.injury_date.isoformat()}"]
            priority = 95
            
        else:
            # First injury in our records
            text = (
                f"First major setback we have on record. "
                f"You're at {bank.current_weekly_miles:.0f} miles after {weeks_since_injury} weeks — "
                f"ahead of conservative projections."
            )
            anchors_used = []
            priority = 85
        
        return Narrative(
            text=text,
            signal_type="injury_rebound",
            priority=priority,
            hash=self._hash(text),
            anchors_used=anchors_used
        )
    
    # =========================================================================
    # EFFICIENCY NARRATIVES
    # =========================================================================
    
    def narrate_efficiency(
        self,
        recent_delta: Optional[float] = None
    ) -> Optional[Narrative]:
        """
        Narrate efficiency trends.
        
        "Tuesday's 8-miler was 4.2% more efficient than baseline."
        """
        # Find efficiency outlier
        anchor = self.anchor_finder.find_efficiency_outlier("high", 30)
        
        if anchor and abs(anchor.delta_from_baseline) > 3:
            direction = "more" if anchor.delta_from_baseline > 0 else "less"
            sign = "+" if anchor.delta_from_baseline > 0 else ""
            
            text = (
                f"{format_date_relative(anchor.date).capitalize()}'s {anchor.name} was "
                f"{sign}{anchor.delta_from_baseline:.1f}% {direction} efficient than your 30-day baseline. "
            )
            
            if anchor.delta_from_baseline > 5:
                text += "The aerobic work is landing."
            elif anchor.delta_from_baseline > 0:
                text += "Steady gains."
            else:
                text += "Could be fatigue, heat, or just an off day."
            
            return Narrative(
                text=text,
                signal_type="efficiency_outlier",
                priority=75,
                hash=self._hash(text),
                anchors_used=[f"efficiency:{anchor.date.isoformat()}"]
            )
        
        return None
    
    # =========================================================================
    # UNCERTAINTY NARRATIVES
    # =========================================================================
    
    def narrate_uncertainty(
        self,
        uncertainty_min: int,
        uncertainty_max: int,
        primary_source: str,
        bank: FitnessBank
    ) -> Optional[Narrative]:
        """
        Narrate prediction uncertainty.
        
        "Range is wide because of the leg. If it holds, you're at the low end."
        """
        source_explanations = {
            "injury": "the leg",
            "injury_recovery": "injury recovery uncertainty",
            "short_history": "limited race data",
            "sleep": "spotty sleep logs",
            "volume_change": "recent volume jump",
            "detraining": "time away from training",
            "conditions": "race day conditions TBD"
        }
        
        source_text = source_explanations.get(primary_source, primary_source)
        
        if primary_source in ("injury", "injury_recovery"):
            text = (
                f"Range is ±{uncertainty_min}-{uncertainty_max} min because of {source_text}. "
                f"If it holds like the last few weeks, you're at the low end."
            )
            priority = 80
        elif primary_source == "short_history":
            races_count = len(bank.race_performances)
            text = (
                f"±{uncertainty_min}-{uncertainty_max} min — we only have {races_count} races to calibrate from. "
                f"More data tightens the prediction."
            )
            priority = 60
        else:
            text = (
                f"Uncertainty is ±{uncertainty_min}-{uncertainty_max} min, driven by {source_text}. "
                f"The fitness is there — that part isn't in question."
            )
            priority = 65
        
        return Narrative(
            text=text,
            signal_type="uncertainty",
            priority=priority,
            hash=self._hash(text),
            anchors_used=[f"source:{primary_source}"]
        )
    
    # =========================================================================
    # MILESTONE NARRATIVES
    # =========================================================================
    
    def narrate_milestone(
        self,
        current_weekly_miles: float,
        peak_weekly_miles: float
    ) -> Optional[Narrative]:
        """
        Narrate volume milestones.
        
        "You're at 58 miles — same spot as Week 4 before Boston."
        """
        current_pct = current_weekly_miles / peak_weekly_miles if peak_weekly_miles > 0 else 0
        
        # Find comparable milestone
        anchor = self.anchor_finder.find_similar_milestone(current_weekly_miles, 0.1)
        
        if anchor and anchor.following_race:
            text = (
                f"You hit {current_weekly_miles:.0f} miles. "
                f"That's where you were {anchor.days_to_race} days before {anchor.following_race}."
            )
            anchors_used = [f"milestone:{anchor.date.isoformat()}", f"race:{anchor.following_race}"]
            priority = 70
            
        elif current_pct >= 0.9:
            text = (
                f"{current_weekly_miles:.0f} miles this week — "
                f"{current_pct:.0%} of your all-time peak. You're in familiar territory."
            )
            anchors_used = []
            priority = 75
            
        elif current_pct >= 0.7:
            text = (
                f"At {current_weekly_miles:.0f} miles, you're at {current_pct:.0%} of peak. "
                f"Building back steadily."
            )
            anchors_used = []
            priority = 55
            
        else:
            return None  # Not milestone-worthy
        
        return Narrative(
            text=text,
            signal_type="milestone",
            priority=priority,
            hash=self._hash(text),
            anchors_used=anchors_used
        )
    
    # =========================================================================
    # TAU CHARACTERISTICS
    # =========================================================================
    
    def narrate_tau(self, tau1: float) -> Optional[Narrative]:
        """
        Narrate individual τ characteristics.
        
        "Your τ says you snap back quick — shorter tapers work for you."
        """
        if tau1 < 30:
            text = (
                f"Your τ₁={tau1:.0f}d says you adapt faster than most. "
                f"Steeper ramps, shorter tapers — your body can handle it."
            )
            priority = 60
        elif tau1 > 45:
            text = (
                f"τ₁={tau1:.0f}d means patience pays. "
                f"Consistency over intensity — you build slow but deep."
            )
            priority = 55
        else:
            return None  # Typical tau, not worth narrating
        
        return Narrative(
            text=text,
            signal_type="tau_characteristic",
            priority=priority,
            hash=self._hash(f"tau_{tau1:.0f}"),
            anchors_used=[]
        )
    
    # =========================================================================
    # HERO SENTENCE
    # =========================================================================
    
    def get_hero_narrative(
        self,
        bank: FitnessBank,
        tsb: float,
        ctl: float,
        atl: float,
        upcoming_workout: Optional[Dict] = None
    ) -> Narrative:
        """
        Get the single best narrative for first-3-seconds impact.
        
        Priority order:
        1. Injury rebound (if applicable)
        2. Load state (if extreme)
        3. Upcoming workout context
        4. Efficiency outlier
        5. Milestone
        """
        candidates = []
        
        # 1. Injury rebound
        if bank.constraint_type == ConstraintType.INJURY:
            rebound = self.narrate_injury_rebound(bank, bank.weeks_since_peak)
            if rebound:
                candidates.append(rebound)
        
        # 2. Load state
        load_narrative = self.narrate_load_state(tsb, ctl, atl)
        if load_narrative and load_narrative.priority >= 70:
            candidates.append(load_narrative)
        
        # 3. Upcoming workout
        if upcoming_workout:
            workout_narrative = self.narrate_workout_context(
                upcoming_workout.get("workout_type", "threshold"),
                upcoming_workout.get("name", "workout"),
                upcoming_workout.get("target_pace")
            )
            if workout_narrative:
                candidates.append(workout_narrative)
        
        # 4. Efficiency
        eff_narrative = self.narrate_efficiency()
        if eff_narrative:
            candidates.append(eff_narrative)
        
        # 5. Milestone
        milestone = self.narrate_milestone(bank.current_weekly_miles, bank.peak_weekly_miles)
        if milestone:
            candidates.append(milestone)
        
        # Sort by priority
        candidates.sort(key=lambda n: n.priority, reverse=True)
        
        if candidates:
            winner = candidates[0]
            # Audit log
            log_narrative_generated(
                athlete_id=self.athlete_id,
                surface="home_hero",
                signal_type=winner.signal_type,
                narrative_hash=winner.hash,
                anchors_used=len(winner.anchors_used)
            )
            return winner
        
        # Fallback
        fallback = Narrative(
            text="Your data. Your plan. No BS.",
            signal_type="fallback",
            priority=10,
            hash=self._hash("fallback"),
            anchors_used=[]
        )
        log_narrative_generated(
            athlete_id=self.athlete_id,
            surface="home_hero",
            signal_type="fallback",
            narrative_hash=fallback.hash,
            anchors_used=0
        )
        return fallback
    
    # =========================================================================
    # BATCH NARRATIVES
    # =========================================================================
    
    def get_all_narratives(
        self,
        bank: FitnessBank,
        tsb: float,
        ctl: float,
        atl: float,
        upcoming_workout: Optional[Dict] = None,
        max_count: int = 5
    ) -> List[Narrative]:
        """
        Get all applicable narratives, sorted by priority.
        
        Useful for insight cards that show multiple items.
        """
        narratives = []
        
        # Collect all
        if bank.constraint_type == ConstraintType.INJURY:
            n = self.narrate_injury_rebound(bank, bank.weeks_since_peak)
            if n:
                narratives.append(n)
        
        n = self.narrate_load_state(tsb, ctl, atl)
        if n:
            narratives.append(n)
        
        if upcoming_workout:
            n = self.narrate_workout_context(
                upcoming_workout.get("workout_type", "threshold"),
                upcoming_workout.get("name", "workout"),
                upcoming_workout.get("target_pace")
            )
            if n:
                narratives.append(n)
        
        n = self.narrate_efficiency()
        if n:
            narratives.append(n)
        
        n = self.narrate_milestone(bank.current_weekly_miles, bank.peak_weekly_miles)
        if n:
            narratives.append(n)
        
        n = self.narrate_tau(bank.tau1)
        if n:
            narratives.append(n)
        
        # Sort and limit
        narratives.sort(key=lambda n: n.priority, reverse=True)
        return narratives[:max_count]
    
    # =========================================================================
    # HELPERS
    # =========================================================================
    
    def _hash(self, text: str) -> str:
        """Generate hash for deduplication."""
        return hashlib.md5(text.encode()).hexdigest()[:12]


# =============================================================================
# CONVENIENCE FUNCTION
# =============================================================================

def get_narrative_translator(db: Session, athlete_id: UUID) -> NarrativeTranslator:
    """Get a narrative translator for an athlete."""
    return NarrativeTranslator(db, athlete_id)
