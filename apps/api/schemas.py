from pydantic import BaseModel, ConfigDict
from datetime import datetime, date
from uuid import UUID
from typing import Optional, List, Dict


class AthleteCreate(BaseModel):
    email: Optional[str] = None
    display_name: Optional[str] = None
    birthdate: Optional[date] = None
    sex: Optional[str] = None
    height_cm: Optional[float] = None  # Height in centimeters (required for BMI)
    subscription_tier: str = "free"


class AthleteUpdate(BaseModel):
    """Schema for updating athlete profile"""
    display_name: Optional[str] = None
    birthdate: Optional[date] = None
    sex: Optional[str] = None
    height_cm: Optional[float] = None
    email: Optional[str] = None  # Note: email changes may require verification
    onboarding_stage: Optional[str] = None
    onboarding_completed: Optional[bool] = None


class AthleteResponse(BaseModel):
    id: UUID
    created_at: datetime
    email: Optional[str]
    display_name: Optional[str]
    birthdate: Optional[date]
    sex: Optional[str]
    height_cm: Optional[float] = None  # Height in centimeters
    subscription_tier: str
    onboarding_stage: Optional[str] = None
    onboarding_completed: bool = False
    # Performance Physics Engine: Derived Signals (Manifesto Section 4)
    age_category: Optional[str] = None  # Open, Masters, Grandmasters, etc.
    durability_index: Optional[float] = None
    recovery_half_life_hours: Optional[float] = None
    consistency_index: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class ActivityCreate(BaseModel):
    athlete_id: UUID
    start_time: datetime
    sport: str = "run"
    source: str = "manual"
    duration_s: Optional[int] = None
    distance_m: Optional[int] = None
    avg_hr: Optional[int] = None
    max_hr: Optional[int] = None
    total_elevation_gain: Optional[float] = None
    average_speed: Optional[float] = None


class ActivitySplitResponse(BaseModel):
    """Schema for individual mile splits within an activity"""
    split_number: int  # Split number (mile number)
    distance: Optional[float] = None
    elapsed_time: Optional[int] = None
    moving_time: Optional[int] = None
    average_heartrate: Optional[int] = None
    max_heartrate: Optional[int] = None
    average_cadence: Optional[float] = None
    gap_seconds_per_mile: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class ActivityResponse(BaseModel):
    """Schema for activity response including all metrics and splits"""
    id: str  # UUID as string
    strava_id: Optional[int] = None
    name: str
    distance: float  # Distance in meters
    moving_time: int  # Moving time in seconds
    start_date: str  # ISO format datetime string
    average_speed: float
    max_hr: Optional[int] = None
    average_heartrate: Optional[int] = None
    average_cadence: Optional[float] = None
    total_elevation_gain: Optional[float] = None
    pace_per_mile: Optional[str] = None  # Formatted as "MM:SS/mi"
    duration_formatted: Optional[str] = None  # Formatted as "HH:MM:SS" or "MM:SS"
    splits: Optional[List[ActivitySplitResponse]] = None
    # Performance Physics Engine fields
    performance_percentage: Optional[float] = None  # Age-graded performance % (International/WMA standard)
    performance_percentage_national: Optional[float] = None  # Age-graded performance % (National standard)
    is_race_candidate: Optional[bool] = None
    race_confidence: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class DailyCheckinCreate(BaseModel):
    athlete_id: UUID
    date: date
    sleep_h: Optional[float] = None
    stress_1_5: Optional[int] = None
    soreness_1_5: Optional[int] = None
    rpe_1_10: Optional[int] = None
    notes: Optional[str] = None


class DailyCheckinResponse(BaseModel):
    id: UUID
    athlete_id: UUID
    date: date
    sleep_h: Optional[float]
    stress_1_5: Optional[int]
    soreness_1_5: Optional[int]
    rpe_1_10: Optional[int]
    notes: Optional[str]

    model_config = ConfigDict(from_attributes=True)


class PersonalBestResponse(BaseModel):
    """Schema for Personal Best response"""
    id: UUID
    athlete_id: UUID
    distance_category: str
    distance_meters: int
    time_seconds: int
    pace_per_mile: Optional[float]
    activity_id: UUID
    achieved_at: datetime
    is_race: bool
    age_at_achievement: Optional[int]

    model_config = ConfigDict(from_attributes=True)


class BodyCompositionCreate(BaseModel):
    """Schema for creating body composition entry"""
    athlete_id: UUID
    date: date
    weight_kg: Optional[float] = None
    body_fat_pct: Optional[float] = None
    muscle_mass_kg: Optional[float] = None
    measurements_json: Optional[dict] = None
    notes: Optional[str] = None
    # Note: BMI is calculated automatically in backend


class BodyCompositionResponse(BaseModel):
    """Schema for body composition response"""
    id: UUID
    athlete_id: UUID
    date: date
    weight_kg: Optional[float] = None
    body_fat_pct: Optional[float] = None
    muscle_mass_kg: Optional[float] = None
    bmi: Optional[float] = None  # Calculated automatically
    measurements_json: Optional[dict] = None
    notes: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NutritionEntryCreate(BaseModel):
    """Schema for creating nutrition entry"""
    athlete_id: UUID
    date: date
    entry_type: str  # 'pre_activity', 'during_activity', 'post_activity', 'daily'
    activity_id: Optional[UUID] = None  # Required for pre/during/post, None for daily
    calories: Optional[float] = None
    protein_g: Optional[float] = None
    carbs_g: Optional[float] = None
    fat_g: Optional[float] = None
    fiber_g: Optional[float] = None
    timing: Optional[datetime] = None  # When consumed
    notes: Optional[str] = None


class NutritionEntryResponse(BaseModel):
    """Schema for nutrition entry response"""
    id: UUID
    athlete_id: UUID
    date: date
    entry_type: str
    activity_id: Optional[UUID] = None
    calories: Optional[float] = None
    protein_g: Optional[float] = None
    carbs_g: Optional[float] = None
    fat_g: Optional[float] = None
    fiber_g: Optional[float] = None
    timing: Optional[datetime] = None
    notes: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WorkPatternCreate(BaseModel):
    """Schema for creating work pattern entry"""
    athlete_id: UUID
    date: date
    work_type: Optional[str] = None  # 'desk', 'physical', 'shift', 'travel', etc.
    hours_worked: Optional[float] = None
    stress_level: Optional[int] = None  # 1-5 scale
    notes: Optional[str] = None


class WorkPatternResponse(BaseModel):
    """Schema for work pattern response"""
    id: UUID
    athlete_id: UUID
    date: date
    work_type: Optional[str] = None
    hours_worked: Optional[float] = None
    stress_level: Optional[int] = None
    notes: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class IntakeQuestionnaireCreate(BaseModel):
    """Schema for intake questionnaire response"""
    athlete_id: UUID
    stage: str  # 'initial', 'basic_profile', 'goals', 'nutrition_setup', 'work_setup'
    responses: dict  # Flexible structure for stage-specific questions


class IntakeQuestionnaireResponse(BaseModel):
    """Schema for intake questionnaire response"""
    id: UUID
    athlete_id: UUID
    stage: str
    responses: dict
    completed_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ActivityFeedbackCreate(BaseModel):
    """Schema for creating activity feedback"""
    activity_id: UUID
    perceived_effort: Optional[int] = None  # 1-10 scale (RPE)
    leg_feel: Optional[str] = None  # 'fresh', 'normal', 'tired', 'heavy', 'sore', 'injured'
    mood_pre: Optional[str] = None  # 'energetic', 'normal', 'tired', 'stressed', 'motivated', etc.
    mood_post: Optional[str] = None
    energy_pre: Optional[int] = None  # 1-10 scale
    energy_post: Optional[int] = None  # 1-10 scale
    notes: Optional[str] = None


class ActivityFeedbackResponse(BaseModel):
    """Schema for activity feedback response"""
    id: UUID
    activity_id: UUID
    athlete_id: UUID
    perceived_effort: Optional[int] = None
    leg_feel: Optional[str] = None
    mood_pre: Optional[str] = None
    mood_post: Optional[str] = None
    energy_pre: Optional[int] = None
    energy_post: Optional[int] = None
    notes: Optional[str] = None
    submitted_at: datetime
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ActivityFeedbackUpdate(BaseModel):
    """Schema for updating activity feedback"""
    perceived_effort: Optional[int] = None
    leg_feel: Optional[str] = None
    mood_pre: Optional[str] = None
    mood_post: Optional[str] = None
    energy_pre: Optional[int] = None
    energy_post: Optional[int] = None
    notes: Optional[str] = None


class InsightFeedbackCreate(BaseModel):
    """Schema for creating insight feedback"""
    insight_type: str  # 'correlation', 'activity_insight', 'efficiency_trend', etc.
    insight_id: Optional[str] = None  # ID of the insight
    insight_text: str  # The actual insight text shown to user
    helpful: bool  # True = helpful, False = not helpful
    feedback_text: Optional[str] = None  # Optional user comment


class InsightFeedbackResponse(BaseModel):
    """Schema for insight feedback response"""
    id: UUID
    athlete_id: UUID
    insight_type: str
    insight_id: Optional[str]
    insight_text: str
    helpful: bool
    feedback_text: Optional[str]
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class TrainingAvailabilityCreate(BaseModel):
    """Schema for creating training availability entry"""
    day_of_week: int  # 0=Sunday, 1=Monday, ..., 6=Saturday
    time_block: str  # 'morning', 'afternoon', 'evening'
    status: str  # 'available', 'preferred', 'unavailable'
    notes: Optional[str] = None


class TrainingAvailabilityResponse(BaseModel):
    """Schema for training availability response"""
    id: UUID
    athlete_id: UUID
    day_of_week: int
    time_block: str
    status: str
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TrainingAvailabilityUpdate(BaseModel):
    """Schema for updating training availability"""
    status: Optional[str] = None  # 'available', 'preferred', 'unavailable'
    notes: Optional[str] = None


class TrainingAvailabilityGridResponse(BaseModel):
    """Schema for full availability grid response"""
    athlete_id: UUID
    grid: List[TrainingAvailabilityResponse]  # All 21 slots (7 days × 3 blocks)
    summary: dict  # Slot counts and statistics



