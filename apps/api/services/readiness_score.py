"""
Readiness Score Calculator (Phase 2A)

Composite signal from existing data, computed daily. The score is a SIGNAL —
what fires from it is governed by per-athlete thresholds, not hardcoded constants.

Architecture:
    Readiness Score (0-100) = weighted signal aggregation
             ↓
    Per-Athlete Thresholds (parameters, not constants)
             ↓
    Adaptation Rules Engine (reads thresholds from athlete profile)

Cold-start weights are hypotheses that become per-athlete parameters over time.

Sources:
    - TSB from training_load.py (0.25)
    - Efficiency trend from efficiency_trending.py (0.30) — master signal
    - Completion rate from PlannedWorkout (0.20)
    - Days since last quality session (0.15)
    - Recovery half-life from individual_performance_model.py (0.10)
    - HRV: 0.00 until correlation engine proves individual direction
    - Sleep: 0.00 until correlation engine proves individual relationship
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Optional, Dict, Any, List
from uuid import UUID

import logging

logger = logging.getLogger(__name__)


@dataclass
class ReadinessComponents:
    """Breakdown of each signal's contribution to the readiness score."""
    tsb_score: Optional[float] = None         # 0-100 from TSB position
    efficiency_score: Optional[float] = None   # 0-100 from 7-day efficiency trend
    completion_score: Optional[float] = None   # 0-100 from 7-day completion rate
    recovery_score: Optional[float] = None     # 0-100 from days since last quality
    halflife_score: Optional[float] = None     # 0-100 from personal recovery speed
    hrv_score: Optional[float] = None          # Only when correlation established
    sleep_score: Optional[float] = None        # Only when correlation established


@dataclass
class DailyReadinessResult:
    """Result of a daily readiness computation."""
    athlete_id: UUID
    target_date: date
    score: float                              # 0-100 composite
    components: ReadinessComponents
    signals_available: int                    # How many signals had data
    signals_total: int = 5                    # Total possible (excl HRV/sleep)
    confidence: float = 0.0                   # 0-1, based on signal availability
    weights_used: Dict[str, float] = field(default_factory=dict)


# Cold-start weights — hypotheses to be validated against founder's data
# and eventually replaced by per-athlete learned weights.
COLD_START_WEIGHTS = {
    "tsb": 0.25,
    "efficiency": 0.30,        # Master signal — highest weight
    "completion": 0.20,
    "recovery": 0.15,
    "halflife": 0.10,
    "hrv": 0.00,               # Excluded until proven per-athlete
    "sleep": 0.00,             # Excluded until proven per-athlete
}

# Quality workout types — sessions that require recovery
QUALITY_WORKOUT_TYPES = {
    "threshold", "tempo", "tempo_run", "intervals", "interval",
    "long_run", "long_hmp", "long_mp", "race",
}

# TSB mapping constants
TSB_MIN = -30.0   # Maps to score 0
TSB_MAX = 30.0    # Maps to score 100


class ReadinessScoreCalculator:
    """
    Compute daily readiness score for an athlete.

    The score is a pure SIGNAL — it does not make decisions.
    Decisions are made by the intelligence engine using per-athlete thresholds.
    """

    def __init__(self, weights: Optional[Dict[str, float]] = None):
        self.weights = weights or COLD_START_WEIGHTS.copy()

    def compute(
        self,
        athlete_id: UUID,
        target_date: date,
        db: Any,
    ) -> DailyReadinessResult:
        """
        Compute readiness score for an athlete on a given date.

        Args:
            athlete_id: The athlete's UUID
            target_date: Date to compute readiness for
            db: Database session

        Returns:
            DailyReadinessResult with score, components, and confidence
        """
        signals: Dict[str, float] = {}
        components = ReadinessComponents()

        # Signal 1: TSB (weight 0.25)
        tsb_score = self._compute_tsb_signal(athlete_id, target_date, db)
        if tsb_score is not None:
            signals["tsb"] = tsb_score
            components.tsb_score = round(tsb_score, 1)

        # Signal 2: Efficiency trend (weight 0.30) — master signal
        eff_score = self._compute_efficiency_signal(athlete_id, target_date, db)
        if eff_score is not None:
            signals["efficiency"] = eff_score
            components.efficiency_score = round(eff_score, 1)

        # Signal 3: Completion rate (weight 0.20)
        comp_score = self._compute_completion_signal(athlete_id, target_date, db)
        if comp_score is not None:
            signals["completion"] = comp_score
            components.completion_score = round(comp_score, 1)

        # Signal 4: Days since last quality session (weight 0.15)
        rec_score = self._compute_recovery_days_signal(athlete_id, target_date, db)
        if rec_score is not None:
            signals["recovery"] = rec_score
            components.recovery_score = round(rec_score, 1)

        # Signal 5: Recovery half-life (weight 0.10)
        hl_score = self._compute_halflife_signal(athlete_id, target_date, db)
        if hl_score is not None:
            signals["halflife"] = hl_score
            components.halflife_score = round(hl_score, 1)

        # Aggregate
        if not signals:
            logger.info(
                f"Readiness {athlete_id} on {target_date}: no signals available, "
                f"returning neutral score 50.0 with confidence 0.0"
            )
            return DailyReadinessResult(
                athlete_id=athlete_id,
                target_date=target_date,
                score=50.0,
                components=components,
                signals_available=0,
                confidence=0.0,
                weights_used=self.weights,
            )

        # Weighted average with renormalization for missing signals
        active_weights = {k: self.weights[k] for k in signals}
        total_weight = sum(active_weights.values())

        if total_weight > 0:
            score = sum(signals[k] * active_weights[k] for k in signals) / total_weight
        else:
            score = 50.0

        score = max(0.0, min(100.0, score))
        signals_available = len(signals)
        confidence = signals_available / 5  # 5 cold-start signals

        logger.info(
            f"Readiness {athlete_id} on {target_date}: score={score:.1f}, "
            f"signals={signals_available}/5, confidence={confidence:.2f}, "
            f"components={signals}"
        )

        return DailyReadinessResult(
            athlete_id=athlete_id,
            target_date=target_date,
            score=round(score, 1),
            components=components,
            signals_available=signals_available,
            confidence=round(confidence, 2),
            weights_used=self.weights,
        )

    # ------------------------------------------------------------------
    # Signal 1: TSB (Training Stress Balance)
    # ------------------------------------------------------------------

    def _compute_tsb_signal(
        self, athlete_id: UUID, target_date: date, db: Any
    ) -> Optional[float]:
        """
        Compute readiness signal from Training Stress Balance.

        TSB = CTL - ATL. Maps [-30, +30] → [0, 100].
        Negative TSB (fatigued) → low score.
        Positive TSB (fresh) → high score.
        """
        try:
            from services.training_load import TrainingLoadCalculator

            calc = TrainingLoadCalculator(db)
            result = calc.calculate_training_load(athlete_id, target_date)
            tsb = result.current_tsb

            # Linear mapping: TSB_MIN → 0, TSB_MAX → 100
            score = ((tsb - TSB_MIN) / (TSB_MAX - TSB_MIN)) * 100.0
            return max(0.0, min(100.0, score))

        except Exception as e:
            logger.debug(f"TSB signal unavailable for {athlete_id}: {e}")
            return None

    # ------------------------------------------------------------------
    # Signal 2: Efficiency Trend (master signal)
    # ------------------------------------------------------------------

    def _compute_efficiency_signal(
        self, athlete_id: UUID, target_date: date, db: Any
    ) -> Optional[float]:
        """
        Compute readiness signal from recent efficiency trend.

        Uses a direct efficiency factor (speed/HR) comparison.
        If the full efficiency analytics pipeline is available, uses it.
        Falls back to a simple direct computation from recent activities.

        Improving → high score. Declining → low score.
        """
        try:
            return self._compute_efficiency_from_activities(athlete_id, target_date, db)
        except Exception as e:
            logger.debug(f"Efficiency signal unavailable for {athlete_id}: {e}")
            return None

    def _compute_efficiency_from_activities(
        self, athlete_id: UUID, target_date: date, db: Any
    ) -> Optional[float]:
        """
        Compute efficiency trend directly from recent activities.

        More robust than the full analytics pipeline for small sample sizes.
        Computes EF (speed/HR) for each activity, splits into older/newer halves,
        and compares average EF.
        """
        from models import Activity

        # Get activities with HR and speed in the last 14 days
        window_start = target_date - timedelta(days=14)
        activities = (
            db.query(Activity)
            .filter(
                Activity.athlete_id == athlete_id,
                Activity.start_time >= datetime.combine(window_start, datetime.min.time()),
                Activity.start_time < datetime.combine(target_date + timedelta(days=1), datetime.min.time()),
                Activity.avg_hr.isnot(None),
                Activity.avg_hr > 0,
                Activity.average_speed.isnot(None),
                Activity.average_speed > 0,
            )
            .order_by(Activity.start_time)
            .all()
        )

        if len(activities) < 2:
            return None

        # Compute efficiency factor (speed / HR) for each activity
        efs = []
        for a in activities:
            hr = float(a.avg_hr)
            speed = float(a.average_speed)  # m/s
            if hr > 0 and speed > 0:
                efs.append(speed / hr)

        if len(efs) < 2:
            return None

        # Split into older and newer halves
        mid = len(efs) // 2
        older_avg = sum(efs[:mid]) / mid
        newer_avg = sum(efs[mid:]) / (len(efs) - mid)

        if older_avg <= 0:
            return None

        # Percent change in EF
        pct_change = ((newer_avg - older_avg) / older_avg) * 100

        # Map percentage change to 0-100 score
        # Day-to-day EF variation of 3-5% is normal (terrain, weather, fatigue).
        # Use conservative 3x scaling so moderate fluctuations stay near midpoint.
        # -10% change → score 20 (severe decline)
        # -5% → 35
        #  0% → 50 (stable)
        # +5% → 65
        # +10% → 80
        score = 50.0 + (pct_change * 3.0)
        return max(0.0, min(100.0, score))

    # ------------------------------------------------------------------
    # Signal 3: Completion Rate (7-day)
    # ------------------------------------------------------------------

    def _compute_completion_signal(
        self, athlete_id: UUID, target_date: date, db: Any
    ) -> Optional[float]:
        """
        Compute readiness signal from workout completion rate.

        Queries planned workouts in the 7 days prior to target_date.
        Returns % completed as the score (0-100).
        """
        try:
            from models import PlannedWorkout

            window_start = target_date - timedelta(days=7)

            planned = (
                db.query(PlannedWorkout)
                .filter(
                    PlannedWorkout.athlete_id == athlete_id,
                    PlannedWorkout.scheduled_date >= window_start,
                    PlannedWorkout.scheduled_date <= target_date,
                )
                .all()
            )

            if not planned:
                return None

            completed = sum(1 for pw in planned if pw.completed)
            rate = (completed / len(planned)) * 100.0
            return max(0.0, min(100.0, rate))

        except Exception as e:
            logger.debug(f"Completion signal unavailable for {athlete_id}: {e}")
            return None

    # ------------------------------------------------------------------
    # Signal 4: Days Since Last Quality Session
    # ------------------------------------------------------------------

    def _compute_recovery_days_signal(
        self, athlete_id: UUID, target_date: date, db: Any
    ) -> Optional[float]:
        """
        Compute readiness signal from recovery adequacy.

        Finds the most recent quality session (by activity workout_type or
        by HR intensity relative to recent average). Maps days-since to a
        recovery curve: peak readiness 2-3 days after quality, decays on both sides.
        """
        try:
            days_since = self._find_days_since_quality(athlete_id, target_date, db)
            if days_since is None:
                return None

            # Recovery curve: peak at 2-3 days post-quality
            # 0 days: 30 (just did quality, absorbing)
            # 1 day:  50
            # 2 days: 75
            # 3 days: 90 (peak readiness for next quality)
            # 4 days: 85
            # 5 days: 75
            # 6 days: 65
            # 7+ days: 55 (rested but may be losing sharpness)
            recovery_curve = {
                0: 30.0,
                1: 50.0,
                2: 75.0,
                3: 90.0,
                4: 85.0,
                5: 75.0,
                6: 65.0,
            }

            if days_since in recovery_curve:
                return recovery_curve[days_since]
            elif days_since >= 7:
                # Gentle decay beyond 7 days, floor at 45
                return max(45.0, 55.0 - (days_since - 7) * 2.0)
            else:
                return 50.0

        except Exception as e:
            logger.debug(f"Recovery days signal unavailable for {athlete_id}: {e}")
            return None

    def _find_days_since_quality(
        self, athlete_id: UUID, target_date: date, db: Any
    ) -> Optional[int]:
        """
        Find days since the most recent quality session.

        Strategy:
        1. Check Activity.workout_type for known quality types
        2. If no labeled quality sessions, estimate from HR intensity:
           activities with avg_hr significantly above the athlete's median
        """
        from models import Activity

        # Strategy 1: labeled quality sessions
        labeled_quality = (
            db.query(Activity)
            .filter(
                Activity.athlete_id == athlete_id,
                Activity.start_time < datetime.combine(target_date + timedelta(days=1), datetime.min.time()),
                Activity.workout_type.in_(list(QUALITY_WORKOUT_TYPES)),
            )
            .order_by(Activity.start_time.desc())
            .first()
        )

        if labeled_quality:
            quality_date = labeled_quality.start_time.date() if hasattr(labeled_quality.start_time, 'date') else labeled_quality.start_time
            return (target_date - quality_date).days

        # Strategy 2: estimate from HR intensity
        # Get recent activities with HR
        lookback = target_date - timedelta(days=30)
        recent = (
            db.query(Activity)
            .filter(
                Activity.athlete_id == athlete_id,
                Activity.start_time >= datetime.combine(lookback, datetime.min.time()),
                Activity.start_time < datetime.combine(target_date + timedelta(days=1), datetime.min.time()),
                Activity.avg_hr.isnot(None),
                Activity.avg_hr > 0,
            )
            .order_by(Activity.start_time)
            .all()
        )

        if len(recent) < 3:
            return None

        # Compute median HR
        hrs = sorted(float(a.avg_hr) for a in recent)
        median_hr = hrs[len(hrs) // 2]

        # Activities with HR > median + 8 bpm are likely quality
        # Also activities > 90 minutes are likely long runs
        quality_candidates = [
            a for a in recent
            if (float(a.avg_hr) > median_hr + 8)
            or (a.duration_s and float(a.duration_s) > 5400)  # > 90 min
        ]

        if not quality_candidates:
            return None

        # Most recent quality candidate
        latest = quality_candidates[-1]  # Already sorted by start_time
        quality_date = latest.start_time.date() if hasattr(latest.start_time, 'date') else latest.start_time
        return (target_date - quality_date).days

    # ------------------------------------------------------------------
    # Signal 5: Recovery Half-Life
    # ------------------------------------------------------------------

    def _compute_halflife_signal(
        self, athlete_id: UUID, target_date: date, db: Any
    ) -> Optional[float]:
        """
        Compute readiness signal from personal recovery speed.

        Uses recovery_half_life_hours from the Athlete model (populated by
        recovery_metrics service), or computes it on the fly.

        Lower half-life = faster recovery = higher score.
        """
        try:
            half_life = self._get_recovery_half_life(athlete_id, db)
            if half_life is None:
                return None

            # Map half-life to 0-100
            # 24h → 100 (excellent recovery)
            # 48h → 65
            # 72h → 30
            # 96h+ → 10
            score = max(0.0, min(100.0, 100.0 - ((half_life - 24.0) / 72.0) * 90.0))
            return score

        except Exception as e:
            logger.debug(f"Halflife signal unavailable for {athlete_id}: {e}")
            return None

    def _get_recovery_half_life(self, athlete_id: UUID, db: Any) -> Optional[float]:
        """Get recovery half-life, trying stored value first then computing."""
        from models import Athlete

        # Try stored value
        athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
        if athlete and athlete.recovery_half_life_hours:
            return float(athlete.recovery_half_life_hours)

        # Try computing
        try:
            from services.recovery_metrics import calculate_recovery_half_life
            return calculate_recovery_half_life(db, str(athlete_id))
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def persist(self, result: DailyReadinessResult, db: Any) -> None:
        """
        Store a readiness result in the database.

        Upserts — if a result already exists for this athlete+date, updates it.
        """
        from models import DailyReadiness

        existing = (
            db.query(DailyReadiness)
            .filter(
                DailyReadiness.athlete_id == result.athlete_id,
                DailyReadiness.date == result.target_date,
            )
            .first()
        )

        components_dict = {
            "tsb_score": result.components.tsb_score,
            "efficiency_score": result.components.efficiency_score,
            "completion_score": result.components.completion_score,
            "recovery_score": result.components.recovery_score,
            "halflife_score": result.components.halflife_score,
            "hrv_score": result.components.hrv_score,
            "sleep_score": result.components.sleep_score,
        }

        if existing:
            existing.score = result.score
            existing.components = components_dict
            existing.signals_available = result.signals_available
            existing.confidence = result.confidence
            existing.weights_used = result.weights_used
        else:
            record = DailyReadiness(
                athlete_id=result.athlete_id,
                date=result.target_date,
                score=result.score,
                components=components_dict,
                signals_available=result.signals_available,
                signals_total=result.signals_total,
                confidence=result.confidence,
                weights_used=result.weights_used,
            )
            db.add(record)

    # ------------------------------------------------------------------
    # Threshold Calibration Logging
    # ------------------------------------------------------------------

    @staticmethod
    def log_calibration_point(
        athlete_id: UUID,
        workout_id: UUID,
        readiness_score: float,
        workout_type: str,
        outcome: str,
        db: Any,
        efficiency_delta: Optional[float] = None,
        subjective_feel: Optional[int] = None,
    ) -> None:
        """
        Log a readiness-at-decision + outcome pair for threshold calibration.

        Called every time an athlete does (or skips) a planned workout.
        Over time, this data feeds per-athlete threshold estimation.
        """
        from models import ThresholdCalibrationLog

        entry = ThresholdCalibrationLog(
            athlete_id=athlete_id,
            workout_id=workout_id,
            readiness_score=readiness_score,
            workout_type_scheduled=workout_type,
            outcome=outcome,
            efficiency_delta=efficiency_delta,
            subjective_feel=subjective_feel,
        )
        db.add(entry)

    # ------------------------------------------------------------------
    # Threshold Management
    # ------------------------------------------------------------------

    @staticmethod
    def get_or_create_thresholds(athlete_id: UUID, db: Any):
        """
        Get or create per-athlete adaptation thresholds.

        Returns the thresholds model object. Creates with cold-start defaults
        if no thresholds exist yet.
        """
        from models import AthleteAdaptationThresholds

        thresholds = (
            db.query(AthleteAdaptationThresholds)
            .filter(AthleteAdaptationThresholds.athlete_id == athlete_id)
            .first()
        )

        if not thresholds:
            thresholds = AthleteAdaptationThresholds(
                athlete_id=athlete_id,
                # Cold-start defaults from spec
                swap_quality_threshold=35.0,
                reduce_volume_threshold=25.0,
                skip_day_threshold=15.0,
                increase_volume_threshold=80.0,
            )
            db.add(thresholds)
            db.flush()

        return thresholds
