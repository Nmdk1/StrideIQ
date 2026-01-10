"""
Population Insights Router

"People Like You" comparisons based on research data.

Not about elites. About regular runners with jobs and lives
who want to understand their training in context.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel

from core.database import get_db
from core.auth import get_current_athlete
from models import Athlete
from services.research_data.population_comparison import (
    PopulationComparisonService,
    PeerComparison,
    ProgressionComparison,
    PopulationInsight
)

router = APIRouter(prefix="/v1/population", tags=["Population Insights"])


# ============ Response Models ============

class PeerComparisonResponse(BaseModel):
    metric_name: str
    your_value: float
    peer_average: float
    peer_median: float
    peer_p25: float
    peer_p75: float
    percentile: float
    interpretation: str
    cohort_size: int
    cohort_name: str


class ProgressionResponse(BaseModel):
    timeframe_weeks: int
    your_volume_change_pct: float
    typical_volume_change_pct: float
    your_pace_change_sec: float
    typical_pace_change_sec: float
    assessment: str
    notes: str


class InsightResponse(BaseModel):
    category: str
    insight: str
    data_point: str
    relevance: float


class PopulationSummaryResponse(BaseModel):
    your_cohort: str
    cohort_description: str
    comparisons: List[PeerComparisonResponse]
    progression: ProgressionResponse
    insights: List[InsightResponse]


# ============ Cohort Descriptions ============

COHORT_DESCRIPTIONS = {
    "beginner": "Runners typically covering 10-20 km/week, building their base",
    "recreational": "Regular runners covering 20-45 km/week with 3-5 runs",
    "local_competitive": "Solid club runners covering 45-65 km/week",
    "competitive": "Serious competitors covering 65+ km/week",
}


# ============ Endpoints ============

@router.get("/compare", response_model=List[PeerComparisonResponse])
async def compare_to_peers(
    athlete: Athlete = Depends(get_current_athlete),
    db: Session = Depends(get_db),
):
    """
    Compare your training metrics to runners at your level.
    
    Based on analysis of 36,000+ recreational runners from research data.
    NOT elite athletes - real people with jobs and lives.
    """
    service = PopulationComparisonService(db)
    comparisons = service.compare_to_peers(athlete.id)
    
    return [
        PeerComparisonResponse(
            metric_name=c.metric_name,
            your_value=c.your_value,
            peer_average=c.peer_average,
            peer_median=c.peer_median,
            peer_p25=c.peer_p25,
            peer_p75=c.peer_p75,
            percentile=c.percentile,
            interpretation=c.interpretation,
            cohort_size=c.cohort_size,
            cohort_name=c.cohort_name
        )
        for c in comparisons
    ]


@router.get("/progression", response_model=ProgressionResponse)
async def assess_progression(
    weeks: int = 8,
    athlete: Athlete = Depends(get_current_athlete),
    db: Session = Depends(get_db),
):
    """
    Assess whether your training progression is typical for runners like you.
    
    Returns:
    - Your volume change vs typical for your cohort
    - Assessment: on_track, faster_than_typical, slower_than_typical, caution
    """
    if weeks < 4:
        weeks = 4
    if weeks > 16:
        weeks = 16
    
    service = PopulationComparisonService(db)
    progression = service.assess_progression(athlete.id, weeks=weeks)
    
    return ProgressionResponse(
        timeframe_weeks=progression.timeframe_weeks,
        your_volume_change_pct=progression.your_volume_change_pct,
        typical_volume_change_pct=progression.typical_volume_change_pct,
        your_pace_change_sec=progression.your_pace_change_sec,
        typical_pace_change_sec=progression.typical_pace_change_sec,
        assessment=progression.assessment,
        notes=progression.notes
    )


@router.get("/insights", response_model=List[InsightResponse])
async def get_population_insights(
    athlete: Athlete = Depends(get_current_athlete),
    db: Session = Depends(get_db),
):
    """
    Get insights based on how you compare to runners like you.
    
    Highlights notable differences from typical patterns.
    """
    service = PopulationComparisonService(db)
    insights = service.get_insights(athlete.id)
    
    return [
        InsightResponse(
            category=i.category,
            insight=i.insight,
            data_point=i.data_point,
            relevance=i.relevance
        )
        for i in insights
    ]


@router.get("/summary", response_model=PopulationSummaryResponse)
async def get_population_summary(
    athlete: Athlete = Depends(get_current_athlete),
    db: Session = Depends(get_db),
):
    """
    Complete population comparison summary.
    
    One endpoint for:
    - Your cohort classification
    - Peer comparisons
    - Progression assessment
    - Notable insights
    """
    service = PopulationComparisonService(db)
    
    cohort = service.get_athlete_cohort(athlete.id)
    comparisons = service.compare_to_peers(athlete.id)
    progression = service.assess_progression(athlete.id)
    insights = service.get_insights(athlete.id)
    
    return PopulationSummaryResponse(
        your_cohort=cohort,
        cohort_description=COHORT_DESCRIPTIONS.get(cohort, "Runners at your training level"),
        comparisons=[
            PeerComparisonResponse(
                metric_name=c.metric_name,
                your_value=c.your_value,
                peer_average=c.peer_average,
                peer_median=c.peer_median,
                peer_p25=c.peer_p25,
                peer_p75=c.peer_p75,
                percentile=c.percentile,
                interpretation=c.interpretation,
                cohort_size=c.cohort_size,
                cohort_name=c.cohort_name
            )
            for c in comparisons
        ],
        progression=ProgressionResponse(
            timeframe_weeks=progression.timeframe_weeks,
            your_volume_change_pct=progression.your_volume_change_pct,
            typical_volume_change_pct=progression.typical_volume_change_pct,
            your_pace_change_sec=progression.your_pace_change_sec,
            typical_pace_change_sec=progression.typical_pace_change_sec,
            assessment=progression.assessment,
            notes=progression.notes
        ),
        insights=[
            InsightResponse(
                category=i.category,
                insight=i.insight,
                data_point=i.data_point,
                relevance=i.relevance
            )
            for i in insights
        ]
    )


@router.get("/cohort")
async def get_cohort_info(
    athlete: Athlete = Depends(get_current_athlete),
    db: Session = Depends(get_db),
):
    """
    Get information about your runner cohort.
    """
    service = PopulationComparisonService(db)
    cohort = service.get_athlete_cohort(athlete.id)
    
    return {
        "cohort": cohort,
        "description": COHORT_DESCRIPTIONS.get(cohort, "Runners at your training level"),
        "research_basis": "Based on analysis of 36,000+ recreational runners from research dataset",
        "note": "Cohorts are based on average weekly training volume over the past 60 days"
    }


# ============ Research Data Endpoints (powered by 26.6M records) ============

class ResearchVolumeRequest(BaseModel):
    weekly_km: float


class ResearchRaceRequest(BaseModel):
    distance: str  # '5K', '10K', 'half_marathon', 'marathon'
    finish_time_minutes: float


@router.post("/research/volume")
async def compare_volume_to_research(
    request: ResearchVolumeRequest,
    athlete: Athlete = Depends(get_current_athlete),
    db: Session = Depends(get_db),
):
    """
    Compare your weekly volume to 26.6 MILLION training records.
    
    Based on actual Strava data from 36,412 runners (2019-2020).
    Shows where you stand among runners your age and gender.
    
    Example: 45 km/week for a 35-54 male = 75th percentile
    """
    service = PopulationComparisonService(db)
    result = service.compare_weekly_volume_to_research(athlete.id, request.weekly_km)
    
    if not result:
        raise HTTPException(
            status_code=400,
            detail="Could not compare - ensure your profile has birthdate and sex set"
        )
    
    return {
        "source": "Figshare Long-Distance Running Dataset 2019-2020",
        "total_records": "26.6 million training days",
        "unique_athletes": "36,412",
        **result
    }


@router.post("/research/race")
async def compare_race_to_research(
    request: ResearchRaceRequest,
    athlete: Athlete = Depends(get_current_athlete),
    db: Session = Depends(get_db),
):
    """
    Compare your race time to research population data.
    
    Available distances:
    - '5K': 799K race-pace efforts
    - '10K': 1.1M race-pace efforts  
    - 'half_marathon': 311K race-pace efforts
    - 'marathon': 66K race-pace efforts
    
    Example: 3:42 marathon for 35-54 male = faster than 58% of cohort
    """
    valid_distances = ['5K', '10K', 'half_marathon', 'marathon']
    if request.distance not in valid_distances:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid distance. Choose from: {valid_distances}"
        )
    
    service = PopulationComparisonService(db)
    result = service.compare_race_time_to_research(
        athlete.id, 
        request.distance, 
        request.finish_time_minutes
    )
    
    if not result:
        raise HTTPException(
            status_code=400,
            detail="Could not compare - ensure your profile has birthdate and sex set"
        )
    
    return {
        "source": "Figshare Long-Distance Running Dataset 2019-2020",
        **result
    }


@router.get("/research/baselines")
async def get_research_baselines(
    db: Session = Depends(get_db),
):
    """
    Get the raw research baselines data.
    
    Returns population statistics used for comparisons:
    - Weekly volume by age/gender
    - Race times by age/gender/distance
    - Training consistency metrics
    """
    service = PopulationComparisonService(db)
    
    if not service.research_data:
        raise HTTPException(
            status_code=503,
            detail="Research baselines not loaded"
        )
    
    return service.research_data

