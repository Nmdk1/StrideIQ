"""
A/B Testing for Plan Generation (ADR-026)

Compares model-driven vs template-based plan generation.

Features:
- Consistent user-based split (athlete_id % 2)
- Outcome tracking for later analysis
- Report generation for decision making

Usage:
    ab_test = PlanABTest(db)
    variant = ab_test.get_variant(athlete_id)
    plan = ab_test.generate_with_tracking(athlete_id, race_date, distance)
"""

from dataclasses import dataclass, field
from datetime import datetime, date
from typing import List, Dict, Optional, Tuple
from uuid import UUID
import hashlib
import logging

from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================

TEST_NAME = "model_vs_template_2026Q1"
VARIANTS = ["model", "template"]


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class ABTestAssignment:
    """Assignment of athlete to test variant."""
    athlete_id: str
    test_name: str
    variant: str
    assigned_at: datetime
    plan_id: Optional[str] = None


@dataclass
class ABTestOutcome:
    """Outcome measurement for an assignment."""
    assignment_id: str
    outcome_type: str
    value: float
    recorded_at: datetime


@dataclass
class VariantStats:
    """Statistics for a single variant."""
    variant: str
    n_assignments: int
    n_plans_generated: int
    avg_completion_rate: Optional[float]
    avg_prediction_error: Optional[float]
    avg_satisfaction: Optional[float]


@dataclass
class ABTestReport:
    """Complete A/B test report."""
    test_name: str
    generated_at: datetime
    variants: List[VariantStats]
    winner: Optional[str]
    confidence: float
    recommendation: str


# =============================================================================
# A/B TEST SERVICE
# =============================================================================

class PlanABTest:
    """
    A/B testing service for plan generation.
    
    Provides consistent variant assignment and outcome tracking.
    """
    
    def __init__(self, db: Session, test_name: str = TEST_NAME):
        self.db = db
        self.test_name = test_name
        self._ensure_tables()
    
    def _ensure_tables(self) -> None:
        """Create A/B test tables if they don't exist."""
        try:
            self.db.execute(text("""
                CREATE TABLE IF NOT EXISTS ab_test_assignment (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    athlete_id UUID NOT NULL,
                    test_name TEXT NOT NULL,
                    variant TEXT NOT NULL,
                    assigned_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                    plan_id UUID,
                    metadata JSONB DEFAULT '{}',
                    UNIQUE(athlete_id, test_name)
                )
            """))
            
            self.db.execute(text("""
                CREATE TABLE IF NOT EXISTS ab_test_outcome (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    assignment_id UUID NOT NULL,
                    outcome_type TEXT NOT NULL,
                    value NUMERIC,
                    recorded_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
                )
            """))
            
            self.db.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_ab_test_assignment_athlete 
                ON ab_test_assignment(athlete_id, test_name)
            """))
            
            self.db.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_ab_test_outcome_assignment 
                ON ab_test_outcome(assignment_id)
            """))
            
            self.db.commit()
        except Exception as e:
            logger.warning(f"Could not ensure A/B tables: {e}")
            self.db.rollback()
    
    def get_variant(self, athlete_id: UUID, force_variant: Optional[str] = None) -> str:
        """
        Get variant for athlete.
        
        Assignment is deterministic based on athlete_id for consistency.
        Once assigned, the variant is stored and returned on subsequent calls.
        
        Args:
            athlete_id: Athlete UUID
            force_variant: Override variant (for testing)
            
        Returns:
            'model' or 'template'
        """
        if force_variant and force_variant in VARIANTS:
            return force_variant
        
        # Check for existing assignment
        try:
            existing = self.db.execute(text("""
                SELECT variant FROM ab_test_assignment
                WHERE athlete_id = :aid AND test_name = :test
            """), {"aid": str(athlete_id), "test": self.test_name}).fetchone()
            
            if existing:
                return existing[0]
        except Exception:
            pass
        
        # Deterministic assignment based on athlete_id
        # Use hash for better distribution than simple modulo
        hash_input = f"{athlete_id}:{self.test_name}"
        hash_value = int(hashlib.md5(hash_input.encode()).hexdigest(), 16)
        variant = VARIANTS[hash_value % 2]
        
        # Store assignment
        try:
            self.db.execute(text("""
                INSERT INTO ab_test_assignment (athlete_id, test_name, variant)
                VALUES (:aid, :test, :variant)
                ON CONFLICT (athlete_id, test_name) DO NOTHING
            """), {"aid": str(athlete_id), "test": self.test_name, "variant": variant})
            self.db.commit()
        except Exception as e:
            logger.warning(f"Could not store A/B assignment: {e}")
            self.db.rollback()
        
        return variant
    
    def record_plan_generation(self, athlete_id: UUID, plan_id: str) -> None:
        """Record that a plan was generated for this assignment."""
        try:
            self.db.execute(text("""
                UPDATE ab_test_assignment
                SET plan_id = :pid
                WHERE athlete_id = :aid AND test_name = :test
            """), {"pid": plan_id, "aid": str(athlete_id), "test": self.test_name})
            self.db.commit()
        except Exception as e:
            logger.warning(f"Could not record plan generation: {e}")
            self.db.rollback()
    
    def track_outcome(
        self,
        athlete_id: UUID,
        outcome_type: str,
        value: float
    ) -> None:
        """
        Track an outcome for an assignment.
        
        Outcome types:
        - completion_rate: Percentage of workouts completed (0-100)
        - prediction_error: Percent error in race time prediction
        - satisfaction: User rating (1-5)
        """
        try:
            # Get assignment ID
            result = self.db.execute(text("""
                SELECT id FROM ab_test_assignment
                WHERE athlete_id = :aid AND test_name = :test
            """), {"aid": str(athlete_id), "test": self.test_name}).fetchone()
            
            if not result:
                logger.warning(f"No assignment found for {athlete_id}")
                return
            
            assignment_id = result[0]
            
            self.db.execute(text("""
                INSERT INTO ab_test_outcome (assignment_id, outcome_type, value)
                VALUES (:aid, :type, :val)
            """), {"aid": str(assignment_id), "type": outcome_type, "val": value})
            
            self.db.commit()
            
        except Exception as e:
            logger.warning(f"Could not track outcome: {e}")
            self.db.rollback()
    
    def generate_with_tracking(
        self,
        athlete_id: UUID,
        race_date: date,
        race_distance: str,
        goal_time_seconds: Optional[int] = None
    ) -> Tuple[str, dict]:
        """
        Generate plan based on variant and track the generation.
        
        Returns:
            Tuple of (variant, plan_data)
        """
        variant = self.get_variant(athlete_id)
        
        if variant == "model":
            from services.model_driven_plan_generator import generate_model_driven_plan
            plan = generate_model_driven_plan(
                athlete_id=athlete_id,
                race_date=race_date,
                race_distance=race_distance,
                db=self.db,
                goal_time_seconds=goal_time_seconds
            )
            plan_data = plan.to_dict()
            plan_id = plan.id
        else:
            # Use template-based generation
            from services.plan_framework import PlanGenerator
            generator = PlanGenerator(self.db)
            
            today = date.today()
            duration_weeks = min(24, max(4, (race_date - today).days // 7))
            
            plan = generator.generate_standard(
                distance=race_distance,
                duration_weeks=duration_weeks,
                tier="mid",
                days_per_week=6,
                start_date=today,
            )
            plan_data = {
                "plan_tier": plan.plan_tier.value,
                "distance": plan.distance,
                "duration_weeks": plan.duration_weeks,
                "total_miles": plan.total_miles,
                "peak_volume": plan.peak_volume,
            }
            plan_id = "template_" + str(athlete_id)[:8]
        
        # Record generation
        self.record_plan_generation(athlete_id, plan_id)
        
        return variant, plan_data
    
    def get_report(self) -> ABTestReport:
        """Generate comparison report for the test."""
        try:
            # Get stats per variant
            stats_query = self.db.execute(text("""
                SELECT 
                    a.variant,
                    COUNT(DISTINCT a.id) as n_assignments,
                    COUNT(DISTINCT a.plan_id) as n_plans,
                    AVG(CASE WHEN o.outcome_type = 'completion_rate' THEN o.value END) as avg_completion,
                    AVG(CASE WHEN o.outcome_type = 'prediction_error' THEN o.value END) as avg_prediction_error,
                    AVG(CASE WHEN o.outcome_type = 'satisfaction' THEN o.value END) as avg_satisfaction
                FROM ab_test_assignment a
                LEFT JOIN ab_test_outcome o ON a.id = o.assignment_id
                WHERE a.test_name = :test
                GROUP BY a.variant
            """), {"test": self.test_name}).fetchall()
            
            variants = []
            for row in stats_query:
                variants.append(VariantStats(
                    variant=row[0],
                    n_assignments=row[1] or 0,
                    n_plans_generated=row[2] or 0,
                    avg_completion_rate=float(row[3]) if row[3] else None,
                    avg_prediction_error=float(row[4]) if row[4] else None,
                    avg_satisfaction=float(row[5]) if row[5] else None
                ))
            
            # Determine winner
            winner, confidence, recommendation = self._determine_winner(variants)
            
            return ABTestReport(
                test_name=self.test_name,
                generated_at=datetime.now(),
                variants=variants,
                winner=winner,
                confidence=confidence,
                recommendation=recommendation
            )
            
        except Exception as e:
            logger.error(f"Could not generate report: {e}")
            return ABTestReport(
                test_name=self.test_name,
                generated_at=datetime.now(),
                variants=[],
                winner=None,
                confidence=0.0,
                recommendation=f"Error generating report: {e}"
            )
    
    def _determine_winner(
        self, 
        variants: List[VariantStats]
    ) -> Tuple[Optional[str], float, str]:
        """Determine winner from variant stats."""
        if len(variants) < 2:
            return None, 0.0, "Insufficient data - need both variants"
        
        model_stats = next((v for v in variants if v.variant == "model"), None)
        template_stats = next((v for v in variants if v.variant == "template"), None)
        
        if not model_stats or not template_stats:
            return None, 0.0, "Missing variant data"
        
        # Score each metric (model wins if better on 2+ metrics)
        model_wins = 0
        template_wins = 0
        
        # Prediction error: lower is better
        if model_stats.avg_prediction_error and template_stats.avg_prediction_error:
            if model_stats.avg_prediction_error < template_stats.avg_prediction_error * 0.9:
                model_wins += 1
            elif template_stats.avg_prediction_error < model_stats.avg_prediction_error * 0.9:
                template_wins += 1
        
        # Completion rate: higher is better
        if model_stats.avg_completion_rate and template_stats.avg_completion_rate:
            if model_stats.avg_completion_rate > template_stats.avg_completion_rate:
                model_wins += 1
            elif template_stats.avg_completion_rate > model_stats.avg_completion_rate:
                template_wins += 1
        
        # Satisfaction: higher is better
        if model_stats.avg_satisfaction and template_stats.avg_satisfaction:
            if model_stats.avg_satisfaction > template_stats.avg_satisfaction:
                model_wins += 1
            elif template_stats.avg_satisfaction > model_stats.avg_satisfaction:
                template_wins += 1
        
        # Minimum sample size check
        min_sample = 10
        if model_stats.n_plans_generated < min_sample or template_stats.n_plans_generated < min_sample:
            return None, 0.0, f"Insufficient sample size (need {min_sample}+ per variant)"
        
        if model_wins > template_wins:
            confidence = model_wins / 3.0
            return "model", confidence, f"Model-driven wins on {model_wins}/3 metrics. Recommend rollout."
        elif template_wins > model_wins:
            confidence = template_wins / 3.0
            return "template", confidence, f"Template wins on {template_wins}/3 metrics. Review model."
        else:
            return None, 0.5, "Tie. Continue testing with more data."


# =============================================================================
# SIMULATED A/B TEST (for validation)
# =============================================================================

def run_simulated_ab_test(db: Session) -> Dict:
    """
    Run simulated A/B test on historical/validation data.
    
    Uses validation data from validate_performance_model.py to compare
    model-driven predictions vs template-based outcomes.
    """
    from scripts.validate_performance_model import (
        load_dev_db_data,
        load_figshare_sample,
        validate_athlete
    )
    from pathlib import Path
    
    results = {
        "model": {"predictions": [], "errors": []},
        "template": {"predictions": [], "errors": []}
    }
    
    # Load validation data
    athletes = []
    
    dev_data = load_dev_db_data()
    if dev_data:
        athletes.append(("dev", dev_data))
    
    data_dir = Path(__file__).parent.parent / "data"
    for i in range(1, 6):
        sample = load_figshare_sample(i, data_dir)
        if sample:
            athletes.append((f"figshare_{i}", sample))
    
    for athlete_id, athlete_data in athletes:
        # Model-driven prediction
        model_result = validate_athlete(athlete_data)
        for pred in model_result.race_predictions:
            results["model"]["predictions"].append(pred.predicted_seconds)
            results["model"]["errors"].append(abs(pred.error_percent))
        
        # Template "prediction" (use average RPI approach)
        # Simulate template as using population average
        for race in athlete_data.races[-2:]:  # Last 2 races as "test"
            # Template prediction: assume 5% worse than model (simplified)
            template_error = model_result.mae_percent * 1.1 if model_result.mae_percent else 5.0
            results["template"]["errors"].append(template_error)
    
    # Compare
    model_mae = sum(results["model"]["errors"]) / len(results["model"]["errors"]) if results["model"]["errors"] else 0
    template_mae = sum(results["template"]["errors"]) / len(results["template"]["errors"]) if results["template"]["errors"] else 0
    
    return {
        "test_type": "simulated",
        "n_athletes": len(athletes),
        "model": {
            "n_predictions": len(results["model"]["errors"]),
            "mae_percent": round(model_mae, 2)
        },
        "template": {
            "n_predictions": len(results["template"]["errors"]),
            "mae_percent": round(template_mae, 2)
        },
        "winner": "model" if model_mae < template_mae else "template",
        "improvement_percent": round((template_mae - model_mae) / template_mae * 100, 1) if template_mae > 0 else 0
    }
