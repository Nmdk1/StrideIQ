"""
Progress API Router — ADR-17 Phase 3

Unified "Am I getting better?" endpoint.
Aggregates: training load deltas, period comparison, headline generation.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models import Athlete, Activity
from routers.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/progress", tags=["progress"])


# --- Response Models ---

class PeriodMetrics(BaseModel):
    run_count: int = 0
    total_distance_mi: float = 0
    total_duration_hr: float = 0
    avg_hr: Optional[float] = None


class PeriodComparison(BaseModel):
    current: PeriodMetrics
    previous: PeriodMetrics
    volume_change_pct: Optional[float] = None
    run_count_change: int = 0
    hr_change: Optional[float] = None


class ProgressHeadline(BaseModel):
    text: str  # LLM-generated coaching headline
    subtext: Optional[str] = None  # Supporting data point


class ProgressSummary(BaseModel):
    headline: Optional[ProgressHeadline] = None
    period_comparison: Optional[PeriodComparison] = None
    ctl: Optional[float] = None
    atl: Optional[float] = None
    tsb: Optional[float] = None
    ctl_trend: Optional[str] = None
    tsb_zone: Optional[str] = None
    efficiency_trend: Optional[str] = None
    efficiency_current: Optional[float] = None


# --- Endpoints ---

@router.get("/summary")
async def get_progress_summary(
    days: int = Query(default=28, ge=7, le=180),
    db: Session = Depends(get_db),
    current_user: Athlete = Depends(get_current_user),
):
    """
    Unified progress summary: headline, load metrics, period comparison.
    One call powers the entire Progress page header.
    """
    athlete_id = current_user.id
    result = ProgressSummary()

    # --- Training Load ---
    try:
        from services.training_load import TrainingLoadCalculator
        calc = TrainingLoadCalculator(db)
        load = calc.calculate_training_load(athlete_id)
        if load and load.current_ctl >= 10:
            result.ctl = round(load.current_ctl, 1)
            result.atl = round(load.current_atl, 1)
            result.tsb = round(load.current_tsb, 1)
            result.ctl_trend = load.ctl_trend

            # Get personal TSB zone
            try:
                zone = calc.get_tsb_zone(athlete_id, load.current_tsb)
                if zone:
                    result.tsb_zone = zone.zone.value if hasattr(zone.zone, 'value') else str(zone.zone)
            except Exception:
                pass
    except Exception as e:
        logger.warning(f"Progress load calculation failed: {e}")

    # --- Efficiency Trend ---
    try:
        from services.efficiency_analyzer import EfficiencyAnalyzer
        analyzer = EfficiencyAnalyzer(db)
        trends = analyzer.get_efficiency_trends(
            athlete_id=str(athlete_id),
            days=days,
            include_stability=False,
            include_load_response=False,
        )
        if trends and trends.get("summary"):
            summary = trends["summary"]
            result.efficiency_trend = summary.get("trend_direction")
            result.efficiency_current = summary.get("current_efficiency")
    except Exception as e:
        logger.warning(f"Progress efficiency trend failed: {e}")

    # --- Period Comparison ---
    try:
        now = datetime.utcnow()
        end_current = now
        start_current = now - timedelta(days=days)
        end_previous = start_current
        start_previous = start_current - timedelta(days=days)

        def fetch_period(start, end):
            acts = db.query(Activity).filter(
                Activity.athlete_id == athlete_id,
                Activity.sport == "run",
                Activity.start_time >= start,
                Activity.start_time < end,
            ).all()
            total_m = sum(float(a.distance_m or 0) for a in acts)
            total_s = sum(float(a.duration_s or 0) for a in acts)
            hrs = [int(a.avg_hr) for a in acts if a.avg_hr is not None]
            return PeriodMetrics(
                run_count=len([a for a in acts if a.distance_m]),
                total_distance_mi=round(total_m / 1609.344, 1),
                total_duration_hr=round(total_s / 3600.0, 1),
                avg_hr=round(sum(hrs) / len(hrs), 1) if hrs else None,
            )

        current = fetch_period(start_current, end_current)
        previous = fetch_period(start_previous, end_previous)

        vol_change = None
        if previous.total_distance_mi > 0:
            vol_change = round(
                ((current.total_distance_mi - previous.total_distance_mi)
                 / previous.total_distance_mi) * 100, 1
            )

        hr_change = None
        if current.avg_hr and previous.avg_hr:
            hr_change = round(current.avg_hr - previous.avg_hr, 1)

        result.period_comparison = PeriodComparison(
            current=current,
            previous=previous,
            volume_change_pct=vol_change,
            run_count_change=current.run_count - previous.run_count,
            hr_change=hr_change,
        )
    except Exception as e:
        logger.warning(f"Progress period comparison failed: {e}")

    # --- LLM Headline ---
    try:
        result.headline = _generate_headline(
            str(athlete_id), result, days
        )
    except Exception as e:
        logger.warning(f"Progress headline generation failed: {e}")

    return result


def _generate_headline(
    athlete_id: str,
    summary: ProgressSummary,
    days: int,
) -> Optional[ProgressHeadline]:
    """Generate a coaching headline using Gemini with structured output."""
    import hashlib
    import json

    # Build cache key
    cache_input = json.dumps({
        "ctl": summary.ctl, "atl": summary.atl, "tsb": summary.tsb,
        "ctl_trend": summary.ctl_trend, "eff_trend": summary.efficiency_trend,
        "eff_current": summary.efficiency_current,
        "pc": summary.period_comparison.model_dump() if summary.period_comparison else None,
    }, sort_keys=True, default=str)
    data_hash = hashlib.md5(cache_input.encode()).hexdigest()[:12]
    cache_key = f"progress_headline:{athlete_id}:{data_hash}"

    # Check Redis cache
    r = None
    try:
        import redis
        import os
        redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
        r = redis.from_url(redis_url, decode_responses=True)
        cached = r.get(cache_key)
        if cached:
            data = json.loads(cached)
            return ProgressHeadline(**data)
    except Exception:
        r = None

    # Build prompt context
    parts = [
        "You are an elite running coach. Write a single headline sentence about this athlete's progress.",
        "Be direct, specific, reference actual numbers. Sound like a coach, not a dashboard.",
        "",
    ]

    if summary.ctl is not None:
        parts.append(f"Fitness (CTL): {summary.ctl}, Fatigue (ATL): {summary.atl}, Form (TSB): {summary.tsb}")
        if summary.ctl_trend:
            parts.append(f"Fitness trend: {summary.ctl_trend}")
        if summary.tsb_zone:
            parts.append(f"TSB zone: {summary.tsb_zone}")

    if summary.efficiency_trend:
        parts.append(f"Efficiency trend: {summary.efficiency_trend}")
        if summary.efficiency_current:
            parts.append(f"Current efficiency factor: {summary.efficiency_current:.1f}")

    pc = summary.period_comparison
    if pc:
        parts.append(f"Last {days} days: {pc.current.total_distance_mi}mi ({pc.current.run_count} runs)")
        parts.append(f"Prior {days} days: {pc.previous.total_distance_mi}mi ({pc.previous.run_count} runs)")
        if pc.volume_change_pct is not None:
            parts.append(f"Volume change: {pc.volume_change_pct:+.1f}%")

    prompt = "\n".join(parts)

    try:
        from google import genai
        import os

        api_key = os.getenv("GOOGLE_AI_API_KEY")
        if not api_key:
            return None

        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=genai.types.GenerateContentConfig(
                max_output_tokens=2000,
                temperature=0.3,
                response_mime_type="application/json",
                response_schema={
                    "type": "OBJECT",
                    "properties": {
                        "text": {
                            "type": "STRING",
                            "description": "One coaching headline sentence about overall progress. Reference specific numbers.",
                        },
                        "subtext": {
                            "type": "STRING",
                            "description": "One supporting detail sentence.",
                        },
                    },
                    "required": ["text", "subtext"],
                },
            ),
        )

        data = json.loads(response.text)
        headline = ProgressHeadline(**data)

        if r:
            try:
                r.setex(cache_key, 1800, json.dumps(data))
            except Exception:
                pass

        return headline

    except Exception as e:
        logger.warning(f"Progress headline LLM failed: {type(e).__name__}: {e}")
        return None
