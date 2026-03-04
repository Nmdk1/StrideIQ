"""Pydantic response models for the Racing Fingerprint API."""

from __future__ import annotations

from datetime import date
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class RaceCard(BaseModel):
    """One race candidate card — enough context to trigger recognition."""
    event_id: Optional[UUID] = None
    activity_id: UUID
    name: Optional[str] = None
    date: date
    time_of_day: Optional[str] = None
    day_of_week: Optional[str] = None
    distance_category: str
    distance_meters: int
    pace_display: str
    duration_display: str
    avg_hr: Optional[int] = None
    detection_confidence: Optional[float] = None
    detection_source: Optional[str] = None
    user_confirmed: Optional[bool] = None
    is_personal_best: bool = False

    model_config = ConfigDict(from_attributes=True)


class RacePin(BaseModel):
    event_id: UUID
    date: date
    distance_category: str
    time_seconds: int
    is_personal_best: bool
    performance_percentage: Optional[float] = None


class WeekData(BaseModel):
    week_start: date
    total_volume_km: float
    intensity: str
    activity_count: int


class RacingLifeStripData(BaseModel):
    weeks: List[WeekData]
    pins: List[RacePin]


class RaceCandidateResponse(BaseModel):
    confirmed: List[RaceCard]
    candidates: List[RaceCard]
    browse_count: int
    strip_data: RacingLifeStripData


class BrowseResponse(BaseModel):
    items: List[RaceCard]
    total: int
    offset: int
    limit: int


class RacingLifeStripResponse(BaseModel):
    strip_data: RacingLifeStripData


class FingerprintFindingOut(BaseModel):
    layer: int
    finding_type: str
    sentence: str
    evidence: dict
    statistical_confidence: float
    effect_size: float
    sample_size: int
    confidence_tier: str

    model_config = ConfigDict(from_attributes=True)


class FingerprintFindingsResponse(BaseModel):
    findings: List[FingerprintFindingOut] = []
