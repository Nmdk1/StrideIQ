"""
Athlete Profile Router

Includes:
- Runner typing (McMillan-inspired)
- Consistency streaks (Green-inspired)
- Mindset summary (Snow-inspired)
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import date, datetime

from core.database import get_db
from core.auth import get_current_athlete
from models import Athlete, DailyCheckin
from services.runner_typing import classify_runner_type, update_athlete_runner_type
from services.consistency_streaks import calculate_streak, update_athlete_streak

router = APIRouter(prefix="/v1/athlete-profile", tags=["Athlete Profile"])


# ============ Response Models ============

class RunnerTypeResponse(BaseModel):
    runner_type: str  # 'speedster', 'endurance_monster', 'balanced', 'unknown'
    confidence: float
    recommendation: str
    analysis: Dict


class StreakResponse(BaseModel):
    current_streak_weeks: int
    longest_streak_weeks: int
    weeks_this_year: int
    is_at_risk: bool
    message: str
    celebration: Optional[str] = None


class MindsetSummaryResponse(BaseModel):
    avg_enjoyment: Optional[float] = None
    avg_confidence: Optional[float] = None
    avg_motivation: Optional[float] = None
    trend: str  # 'improving', 'stable', 'declining', 'insufficient_data'
    insight: str
    data_points: int


class AthleteProfileSummary(BaseModel):
    runner_type: Optional[RunnerTypeResponse] = None
    streak: StreakResponse
    mindset: MindsetSummaryResponse


# ============ Endpoints ============

@router.get("/runner-type", response_model=RunnerTypeResponse)
async def get_runner_type(
    recalculate: bool = False,
    athlete: Athlete = Depends(get_current_athlete),
    db: Session = Depends(get_db),
):
    """
    Get your runner type classification.
    
    Based on McMillan's runner typing:
    - **Speedster**: Naturally faster at shorter distances
    - **Endurance Monster**: Naturally stronger at longer distances
    - **Balanced**: Consistent performance across distances
    
    This helps tailor training recommendations.
    """
    if recalculate or not athlete.runner_type:
        result = update_athlete_runner_type(db, athlete.id)
    else:
        result = classify_runner_type(db, athlete.id)
    
    if not result:
        return RunnerTypeResponse(
            runner_type='unknown',
            confidence=0.0,
            recommendation='Race more to get a classification!',
            analysis={}
        )
    
    return RunnerTypeResponse(
        runner_type=result.runner_type,
        confidence=result.confidence,
        recommendation=result.recommendation,
        analysis=result.analysis
    )


@router.get("/streak", response_model=StreakResponse)
async def get_consistency_streak(
    athlete: Athlete = Depends(get_current_athlete),
    db: Session = Depends(get_db),
):
    """
    Get your consistency streak.
    
    "Consistency is the leading indicator of success." - Jonathan Green
    
    A week counts as consistent if you meet minimum training targets
    based on your experience level.
    """
    streak = update_athlete_streak(db, athlete.id)
    
    return StreakResponse(
        current_streak_weeks=streak.current_streak_weeks,
        longest_streak_weeks=streak.longest_streak_weeks,
        weeks_this_year=streak.weeks_this_year,
        is_at_risk=streak.is_at_risk,
        message=streak.message,
        celebration=streak.celebration
    )


@router.get("/mindset", response_model=MindsetSummaryResponse)
async def get_mindset_summary(
    days: int = 30,
    athlete: Athlete = Depends(get_current_athlete),
    db: Session = Depends(get_db),
):
    """
    Get your mindset summary.
    
    "The mind is the limiter of performance." - Andrew Snow
    
    Tracks enjoyment, confidence, and motivation trends.
    """
    from datetime import timedelta
    
    cutoff = date.today() - timedelta(days=days)
    
    checkins = db.query(DailyCheckin).filter(
        DailyCheckin.athlete_id == athlete.id,
        DailyCheckin.date >= cutoff
    ).order_by(DailyCheckin.date).all()
    
    # Filter to those with mindset data
    with_enjoyment = [c for c in checkins if c.enjoyment_1_5 is not None]
    with_confidence = [c for c in checkins if c.confidence_1_5 is not None]
    with_motivation = [c for c in checkins if c.motivation_1_5 is not None]
    
    data_points = len(with_enjoyment) + len(with_confidence) + len(with_motivation)
    
    if data_points < 3:
        return MindsetSummaryResponse(
            avg_enjoyment=None,
            avg_confidence=None,
            avg_motivation=None,
            trend='insufficient_data',
            insight='Log more check-ins with enjoyment, confidence, and motivation to get insights.',
            data_points=data_points
        )
    
    # Calculate averages
    avg_enjoyment = sum(c.enjoyment_1_5 for c in with_enjoyment) / len(with_enjoyment) if with_enjoyment else None
    avg_confidence = sum(c.confidence_1_5 for c in with_confidence) / len(with_confidence) if with_confidence else None
    avg_motivation = sum(c.motivation_1_5 for c in with_motivation) / len(with_motivation) if with_motivation else None
    
    # Calculate trend (compare first half to second half)
    def get_trend(values_list, field):
        if len(values_list) < 4:
            return 'stable'
        mid = len(values_list) // 2
        first_half = sum(getattr(c, field) for c in values_list[:mid]) / mid
        second_half = sum(getattr(c, field) for c in values_list[mid:]) / (len(values_list) - mid)
        diff = second_half - first_half
        if diff > 0.5:
            return 'improving'
        elif diff < -0.5:
            return 'declining'
        return 'stable'
    
    # Get overall trend from enjoyment (primary indicator)
    trend = 'stable'
    if with_enjoyment:
        trend = get_trend(with_enjoyment, 'enjoyment_1_5')
    
    # Generate insight
    if trend == 'improving':
        insight = "Your mental state is trending up. Good sign for performance."
    elif trend == 'declining':
        insight = "Mental state declining. Consider what's draining you."
    else:
        insight = "Steady mental state. Consistency is key."
    
    # Add specific insights
    if avg_enjoyment and avg_enjoyment < 3:
        insight = "Low enjoyment scores. Are you having fun? That matters."
    if avg_confidence and avg_confidence >= 4:
        insight = "High confidence! You're ready to push."
    
    return MindsetSummaryResponse(
        avg_enjoyment=round(avg_enjoyment, 1) if avg_enjoyment else None,
        avg_confidence=round(avg_confidence, 1) if avg_confidence else None,
        avg_motivation=round(avg_motivation, 1) if avg_motivation else None,
        trend=trend,
        insight=insight,
        data_points=data_points
    )


@router.get("/summary", response_model=AthleteProfileSummary)
async def get_profile_summary(
    athlete: Athlete = Depends(get_current_athlete),
    db: Session = Depends(get_db),
):
    """
    Get complete athlete profile summary.
    
    Includes runner type, consistency streak, and mindset summary.
    """
    # Runner type
    runner_type_result = classify_runner_type(db, athlete.id)
    runner_type = None
    if runner_type_result and runner_type_result.runner_type != 'unknown':
        runner_type = RunnerTypeResponse(
            runner_type=runner_type_result.runner_type,
            confidence=runner_type_result.confidence,
            recommendation=runner_type_result.recommendation,
            analysis=runner_type_result.analysis
        )
    
    # Streak
    streak_result = calculate_streak(db, athlete.id)
    streak = StreakResponse(
        current_streak_weeks=streak_result.current_streak_weeks,
        longest_streak_weeks=streak_result.longest_streak_weeks,
        weeks_this_year=streak_result.weeks_this_year,
        is_at_risk=streak_result.is_at_risk,
        message=streak_result.message,
        celebration=streak_result.celebration
    )
    
    # Mindset (reuse the endpoint logic)
    from datetime import timedelta
    cutoff = date.today() - timedelta(days=30)
    checkins = db.query(DailyCheckin).filter(
        DailyCheckin.athlete_id == athlete.id,
        DailyCheckin.date >= cutoff
    ).all()
    
    with_enjoyment = [c for c in checkins if c.enjoyment_1_5 is not None]
    data_points = len(with_enjoyment)
    
    mindset = MindsetSummaryResponse(
        avg_enjoyment=round(sum(c.enjoyment_1_5 for c in with_enjoyment) / len(with_enjoyment), 1) if with_enjoyment else None,
        avg_confidence=None,
        avg_motivation=None,
        trend='stable' if data_points >= 3 else 'insufficient_data',
        insight='Track your mindset to get insights.' if data_points < 3 else 'Building mental data.',
        data_points=data_points
    )
    
    return AthleteProfileSummary(
        runner_type=runner_type,
        streak=streak,
        mindset=mindset
    )


