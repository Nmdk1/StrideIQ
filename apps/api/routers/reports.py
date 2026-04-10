"""
Unified Report API

Returns day-indexed data across health, activities, nutrition, and body composition
for any date range with selectable categories and metrics. Designed for athletes,
coaches, dieticians, exercise physiologists, and primary care physicians.
"""
import csv
import io
import logging
from datetime import date, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import cast, Date, func
from sqlalchemy.orm import Session

from core.auth import get_current_user
from core.database import get_db
from models import (
    Activity,
    Athlete,
    BodyComposition,
    GarminDay,
    NutritionEntry,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/reports", tags=["reports"])

# ── Curated metric sets ──────────────────────────────────────────────

HEALTH_CURATED = [
    "sleep_score", "sleep_total_s", "hrv_overnight_avg", "resting_hr",
    "avg_stress", "steps", "active_kcal",
]

HEALTH_EXTENDED = [
    "sleep_deep_s", "sleep_light_s", "sleep_rem_s", "sleep_awake_s",
    "sleep_score_qualifier", "hrv_5min_high", "min_hr", "max_hr",
    "max_stress", "stress_qualifier", "active_time_s",
    "moderate_intensity_s", "vigorous_intensity_s", "vo2max",
]

ALL_HEALTH_METRICS = HEALTH_CURATED + HEALTH_EXTENDED

ACTIVITY_CURATED = [
    "name", "sport", "workout_type", "duration_s", "distance_m",
    "avg_hr", "avg_pace_min_per_km", "active_kcal", "intensity_score",
]

ACTIVITY_EXTENDED = [
    "max_hr", "total_elevation_gain", "avg_cadence", "avg_stride_length_m",
    "avg_ground_contact_ms", "avg_vertical_oscillation_cm",
    "avg_power_w", "performance_percentage", "workout_zone",
    "temperature_f", "humidity_pct", "weather_condition",
    "shape_sentence", "moving_time_s",
]

NUTRITION_CURATED = [
    "calories", "protein_g", "carbs_g", "fat_g", "caffeine_mg",
]

NUTRITION_EXTENDED = [
    "fiber_g", "fluid_ml", "notes", "entry_type", "macro_source",
]

BODY_COMP_ALL = [
    "weight_kg", "body_fat_pct", "muscle_mass_kg", "bmi",
]


# ── Response models ──────────────────────────────────────────────────

class HealthDay(BaseModel):
    sleep_score: Optional[int] = None
    sleep_total_s: Optional[int] = None
    sleep_deep_s: Optional[int] = None
    sleep_light_s: Optional[int] = None
    sleep_rem_s: Optional[int] = None
    sleep_awake_s: Optional[int] = None
    sleep_score_qualifier: Optional[str] = None
    hrv_overnight_avg: Optional[int] = None
    hrv_5min_high: Optional[int] = None
    resting_hr: Optional[int] = None
    min_hr: Optional[int] = None
    max_hr: Optional[int] = None
    avg_stress: Optional[int] = None
    max_stress: Optional[int] = None
    stress_qualifier: Optional[str] = None
    steps: Optional[int] = None
    active_kcal: Optional[int] = None
    active_time_s: Optional[int] = None
    moderate_intensity_s: Optional[int] = None
    vigorous_intensity_s: Optional[int] = None
    vo2max: Optional[float] = None


class ActivityRow(BaseModel):
    id: str
    name: Optional[str] = None
    sport: Optional[str] = None
    start_time: Optional[str] = None
    workout_type: Optional[str] = None
    workout_zone: Optional[str] = None
    duration_s: Optional[int] = None
    distance_m: Optional[int] = None
    avg_hr: Optional[int] = None
    max_hr: Optional[int] = None
    avg_pace_min_per_km: Optional[float] = None
    active_kcal: Optional[int] = None
    intensity_score: Optional[float] = None
    total_elevation_gain: Optional[float] = None
    avg_cadence: Optional[int] = None
    avg_stride_length_m: Optional[float] = None
    avg_ground_contact_ms: Optional[float] = None
    avg_vertical_oscillation_cm: Optional[float] = None
    avg_power_w: Optional[int] = None
    performance_percentage: Optional[float] = None
    temperature_f: Optional[float] = None
    humidity_pct: Optional[float] = None
    weather_condition: Optional[str] = None
    shape_sentence: Optional[str] = None
    moving_time_s: Optional[int] = None


class NutritionRow(BaseModel):
    id: str
    entry_type: str
    calories: Optional[float] = None
    protein_g: Optional[float] = None
    carbs_g: Optional[float] = None
    fat_g: Optional[float] = None
    fiber_g: Optional[float] = None
    caffeine_mg: Optional[float] = None
    fluid_ml: Optional[float] = None
    notes: Optional[str] = None
    macro_source: Optional[str] = None


class NutritionDayTotals(BaseModel):
    calories: float = 0
    protein_g: float = 0
    carbs_g: float = 0
    fat_g: float = 0
    fiber_g: float = 0
    caffeine_mg: float = 0
    fluid_ml: float = 0
    entry_count: int = 0


class BodyCompDay(BaseModel):
    weight_kg: Optional[float] = None
    body_fat_pct: Optional[float] = None
    muscle_mass_kg: Optional[float] = None
    bmi: Optional[float] = None


class ReportDay(BaseModel):
    date: str
    health: Optional[HealthDay] = None
    activities: Optional[List[ActivityRow]] = None
    nutrition_entries: Optional[List[NutritionRow]] = None
    nutrition_totals: Optional[NutritionDayTotals] = None
    body_composition: Optional[BodyCompDay] = None


class PeriodAverages(BaseModel):
    days: int = 0
    avg_sleep_score: Optional[float] = None
    avg_sleep_hours: Optional[float] = None
    avg_hrv: Optional[float] = None
    avg_resting_hr: Optional[float] = None
    avg_stress: Optional[float] = None
    avg_steps: Optional[float] = None
    total_activities: int = 0
    total_distance_m: float = 0
    total_duration_s: int = 0
    total_active_kcal: float = 0
    avg_daily_calories: Optional[float] = None
    avg_daily_protein_g: Optional[float] = None
    avg_daily_carbs_g: Optional[float] = None
    avg_daily_fat_g: Optional[float] = None
    avg_daily_caffeine_mg: Optional[float] = None
    nutrition_days_logged: int = 0
    avg_weight_kg: Optional[float] = None


class AvailableMetrics(BaseModel):
    health_curated: List[str]
    health_extended: List[str]
    activity_curated: List[str]
    activity_extended: List[str]
    nutrition_curated: List[str]
    nutrition_extended: List[str]
    body_composition: List[str]


class ReportResponse(BaseModel):
    start_date: str
    end_date: str
    categories: List[str]
    days: List[ReportDay]
    period_averages: PeriodAverages
    available_metrics: AvailableMetrics


# ── Helpers ───────────────────────────────────────────────────────────

def _safe_float(val: Any) -> Optional[float]:
    if val is None:
        return None
    return float(val)


def _build_health_day(gd: GarminDay) -> HealthDay:
    return HealthDay(
        sleep_score=gd.sleep_score,
        sleep_total_s=gd.sleep_total_s,
        sleep_deep_s=gd.sleep_deep_s,
        sleep_light_s=gd.sleep_light_s,
        sleep_rem_s=gd.sleep_rem_s,
        sleep_awake_s=gd.sleep_awake_s,
        sleep_score_qualifier=gd.sleep_score_qualifier,
        hrv_overnight_avg=gd.hrv_overnight_avg,
        hrv_5min_high=gd.hrv_5min_high,
        resting_hr=gd.resting_hr,
        min_hr=gd.min_hr,
        max_hr=gd.max_hr,
        avg_stress=gd.avg_stress,
        max_stress=gd.max_stress,
        stress_qualifier=gd.stress_qualifier,
        steps=gd.steps,
        active_kcal=gd.active_kcal,
        active_time_s=gd.active_time_s,
        moderate_intensity_s=gd.moderate_intensity_s,
        vigorous_intensity_s=gd.vigorous_intensity_s,
        vo2max=gd.vo2max,
    )


def _build_activity_row(a: Activity) -> ActivityRow:
    return ActivityRow(
        id=str(a.id),
        name=a.name or a.athlete_title or a.shape_sentence,
        sport=a.sport,
        start_time=a.start_time.isoformat() if a.start_time else None,
        workout_type=a.workout_type,
        workout_zone=a.workout_zone,
        duration_s=a.duration_s,
        distance_m=a.distance_m,
        avg_hr=a.avg_hr,
        max_hr=a.max_hr,
        avg_pace_min_per_km=a.avg_pace_min_per_km,
        active_kcal=a.active_kcal,
        intensity_score=a.intensity_score,
        total_elevation_gain=_safe_float(a.total_elevation_gain),
        avg_cadence=a.avg_cadence,
        avg_stride_length_m=a.avg_stride_length_m,
        avg_ground_contact_ms=a.avg_ground_contact_ms,
        avg_vertical_oscillation_cm=a.avg_vertical_oscillation_cm,
        avg_power_w=a.avg_power_w,
        performance_percentage=a.performance_percentage,
        temperature_f=a.temperature_f,
        humidity_pct=a.humidity_pct,
        weather_condition=a.weather_condition,
        shape_sentence=a.shape_sentence,
        moving_time_s=a.moving_time_s,
    )


def _build_nutrition_row(ne: NutritionEntry) -> NutritionRow:
    return NutritionRow(
        id=str(ne.id),
        entry_type=ne.entry_type,
        calories=_safe_float(ne.calories),
        protein_g=_safe_float(ne.protein_g),
        carbs_g=_safe_float(ne.carbs_g),
        fat_g=_safe_float(ne.fat_g),
        fiber_g=_safe_float(ne.fiber_g),
        caffeine_mg=_safe_float(ne.caffeine_mg),
        fluid_ml=_safe_float(ne.fluid_ml),
        notes=ne.notes,
        macro_source=ne.macro_source,
    )


# ── Endpoints ─────────────────────────────────────────────────────────

@router.get("/available-metrics", response_model=AvailableMetrics)
def get_available_metrics(
    current_user: Athlete = Depends(get_current_user),
) -> AvailableMetrics:
    return AvailableMetrics(
        health_curated=HEALTH_CURATED,
        health_extended=HEALTH_EXTENDED,
        activity_curated=ACTIVITY_CURATED,
        activity_extended=ACTIVITY_EXTENDED,
        nutrition_curated=NUTRITION_CURATED,
        nutrition_extended=NUTRITION_EXTENDED,
        body_composition=BODY_COMP_ALL,
    )


@router.get("", response_model=ReportResponse)
def get_report(
    start_date: date = Query(..., description="Start date (inclusive)"),
    end_date: date = Query(..., description="End date (inclusive)"),
    categories: str = Query(
        "health,activities,nutrition,body_composition",
        description="Comma-separated: health,activities,nutrition,body_composition",
    ),
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReportResponse:
    if (end_date - start_date).days > 365:
        raise HTTPException(status_code=400, detail="Maximum range is 365 days")
    if end_date < start_date:
        raise HTTPException(status_code=400, detail="end_date must be >= start_date")

    cats = set(c.strip() for c in categories.split(",") if c.strip())
    athlete_id = current_user.id

    all_dates = []
    d = start_date
    while d <= end_date:
        all_dates.append(d)
        d += timedelta(days=1)

    # ── Fetch health data ───────────────────────────────────────
    garmin_by_date: Dict[date, GarminDay] = {}
    if "health" in cats:
        rows = (
            db.query(GarminDay)
            .filter(
                GarminDay.athlete_id == athlete_id,
                GarminDay.calendar_date >= start_date,
                GarminDay.calendar_date <= end_date,
            )
            .all()
        )
        for r in rows:
            garmin_by_date[r.calendar_date] = r

    # ── Fetch activities ────────────────────────────────────────
    activities_by_date: Dict[date, List[Activity]] = {}
    if "activities" in cats:
        rows = (
            db.query(Activity)
            .filter(
                Activity.athlete_id == athlete_id,
                cast(Activity.start_time, Date) >= start_date,
                cast(Activity.start_time, Date) <= end_date,
                Activity.is_duplicate == False,  # noqa: E712
            )
            .order_by(Activity.start_time)
            .all()
        )
        for r in rows:
            d_key = r.start_time.date() if r.start_time else None
            if d_key:
                activities_by_date.setdefault(d_key, []).append(r)

    # ── Fetch nutrition ─────────────────────────────────────────
    nutrition_by_date: Dict[date, List[NutritionEntry]] = {}
    if "nutrition" in cats:
        rows = (
            db.query(NutritionEntry)
            .filter(
                NutritionEntry.athlete_id == athlete_id,
                NutritionEntry.date >= start_date,
                NutritionEntry.date <= end_date,
            )
            .order_by(NutritionEntry.created_at)
            .all()
        )
        for r in rows:
            nutrition_by_date.setdefault(r.date, []).append(r)

    # ── Fetch body composition ──────────────────────────────────
    bodycomp_by_date: Dict[date, BodyComposition] = {}
    if "body_composition" in cats:
        rows = (
            db.query(BodyComposition)
            .filter(
                BodyComposition.athlete_id == athlete_id,
                BodyComposition.date >= start_date,
                BodyComposition.date <= end_date,
            )
            .all()
        )
        for r in rows:
            bodycomp_by_date[r.date] = r

    # ── Assemble day rows ───────────────────────────────────────
    report_days: List[ReportDay] = []

    # accumulators for averages
    sleep_scores = []
    sleep_totals = []
    hrvs = []
    resting_hrs = []
    stresses = []
    step_counts = []
    total_activities = 0
    total_distance = 0.0
    total_duration = 0
    total_active_kcal_activities = 0.0
    daily_cals = []
    daily_protein = []
    daily_carbs = []
    daily_fat = []
    daily_caffeine = []
    nutrition_days = 0
    weights = []

    for d in all_dates:
        day = ReportDay(date=d.isoformat())

        if "health" in cats and d in garmin_by_date:
            gd = garmin_by_date[d]
            day.health = _build_health_day(gd)
            if gd.sleep_score is not None:
                sleep_scores.append(gd.sleep_score)
            if gd.sleep_total_s is not None:
                sleep_totals.append(gd.sleep_total_s)
            if gd.hrv_overnight_avg is not None:
                hrvs.append(gd.hrv_overnight_avg)
            if gd.resting_hr is not None:
                resting_hrs.append(gd.resting_hr)
            if gd.avg_stress is not None and gd.avg_stress >= 0:
                stresses.append(gd.avg_stress)
            if gd.steps is not None:
                step_counts.append(gd.steps)

        if "activities" in cats and d in activities_by_date:
            acts = activities_by_date[d]
            day.activities = [_build_activity_row(a) for a in acts]
            total_activities += len(acts)
            for a in acts:
                if a.distance_m:
                    total_distance += float(a.distance_m)
                if a.duration_s:
                    total_duration += a.duration_s
                if a.active_kcal:
                    total_active_kcal_activities += float(a.active_kcal)

        if "nutrition" in cats and d in nutrition_by_date:
            nes = nutrition_by_date[d]
            day.nutrition_entries = [_build_nutrition_row(ne) for ne in nes]
            totals = NutritionDayTotals(entry_count=len(nes))
            for ne in nes:
                totals.calories += float(ne.calories or 0)
                totals.protein_g += float(ne.protein_g or 0)
                totals.carbs_g += float(ne.carbs_g or 0)
                totals.fat_g += float(ne.fat_g or 0)
                totals.fiber_g += float(ne.fiber_g or 0)
                totals.caffeine_mg += float(ne.caffeine_mg or 0)
                totals.fluid_ml += float(ne.fluid_ml or 0)
            day.nutrition_totals = totals
            if totals.calories > 0:
                daily_cals.append(totals.calories)
                daily_protein.append(totals.protein_g)
                daily_carbs.append(totals.carbs_g)
                daily_fat.append(totals.fat_g)
                daily_caffeine.append(totals.caffeine_mg)
                nutrition_days += 1

        if "body_composition" in cats and d in bodycomp_by_date:
            bc = bodycomp_by_date[d]
            day.body_composition = BodyCompDay(
                weight_kg=_safe_float(bc.weight_kg),
                body_fat_pct=_safe_float(bc.body_fat_pct),
                muscle_mass_kg=_safe_float(bc.muscle_mass_kg),
                bmi=_safe_float(bc.bmi),
            )
            if bc.weight_kg:
                weights.append(float(bc.weight_kg))

        report_days.append(day)

    # ── Period averages ─────────────────────────────────────────
    avgs = PeriodAverages(days=len(all_dates))
    if sleep_scores:
        avgs.avg_sleep_score = round(sum(sleep_scores) / len(sleep_scores), 1)
    if sleep_totals:
        avgs.avg_sleep_hours = round(sum(sleep_totals) / len(sleep_totals) / 3600, 1)
    if hrvs:
        avgs.avg_hrv = round(sum(hrvs) / len(hrvs), 1)
    if resting_hrs:
        avgs.avg_resting_hr = round(sum(resting_hrs) / len(resting_hrs), 1)
    if stresses:
        avgs.avg_stress = round(sum(stresses) / len(stresses), 1)
    if step_counts:
        avgs.avg_steps = round(sum(step_counts) / len(step_counts))
    avgs.total_activities = total_activities
    avgs.total_distance_m = round(total_distance, 1)
    avgs.total_duration_s = total_duration
    avgs.total_active_kcal = round(total_active_kcal_activities, 1)
    if daily_cals:
        avgs.avg_daily_calories = round(sum(daily_cals) / len(daily_cals), 1)
        avgs.avg_daily_protein_g = round(sum(daily_protein) / len(daily_protein), 1)
        avgs.avg_daily_carbs_g = round(sum(daily_carbs) / len(daily_carbs), 1)
        avgs.avg_daily_fat_g = round(sum(daily_fat) / len(daily_fat), 1)
        avgs.avg_daily_caffeine_mg = round(sum(daily_caffeine) / len(daily_caffeine), 1)
    avgs.nutrition_days_logged = nutrition_days
    if weights:
        avgs.avg_weight_kg = round(sum(weights) / len(weights), 1)

    return ReportResponse(
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat(),
        categories=sorted(cats),
        days=report_days,
        period_averages=avgs,
        available_metrics=AvailableMetrics(
            health_curated=HEALTH_CURATED,
            health_extended=HEALTH_EXTENDED,
            activity_curated=ACTIVITY_CURATED,
            activity_extended=ACTIVITY_EXTENDED,
            nutrition_curated=NUTRITION_CURATED,
            nutrition_extended=NUTRITION_EXTENDED,
            body_composition=BODY_COMP_ALL,
        ),
    )


@router.get("/export/csv")
def export_report_csv(
    start_date: date = Query(...),
    end_date: date = Query(...),
    categories: str = Query("health,activities,nutrition,body_composition"),
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if (end_date - start_date).days > 365:
        raise HTTPException(status_code=400, detail="Maximum range is 365 days")

    report = get_report(
        start_date=start_date,
        end_date=end_date,
        categories=categories,
        current_user=current_user,
        db=db,
    )

    cats = set(c.strip() for c in categories.split(",") if c.strip())

    buf = io.StringIO()
    writer = csv.writer(buf)

    headers = ["date"]
    if "health" in cats:
        headers += [
            "sleep_score", "sleep_hours", "sleep_deep_min", "sleep_rem_min",
            "hrv_overnight", "resting_hr", "stress_avg", "steps", "active_kcal",
        ]
    if "activities" in cats:
        headers += [
            "activity_name", "sport", "workout_type", "duration_min",
            "distance_mi", "avg_hr", "pace_min_mi", "activity_kcal",
            "intensity", "elevation_ft",
        ]
    if "nutrition" in cats:
        headers += [
            "total_calories", "total_protein_g", "total_carbs_g",
            "total_fat_g", "total_caffeine_mg", "meals_logged",
        ]
    if "body_composition" in cats:
        headers += ["weight_lbs", "body_fat_pct", "bmi"]
    writer.writerow(headers)

    for day in report.days:
        has_activities = day.activities and len(day.activities) > 0
        row_count = max(1, len(day.activities) if has_activities else 1)

        for i in range(row_count):
            row: List[Any] = [day.date]

            if "health" in cats:
                h = day.health
                if h and i == 0:
                    sleep_hrs = round(h.sleep_total_s / 3600, 1) if h.sleep_total_s else ""
                    deep_min = round(h.sleep_deep_s / 60) if h.sleep_deep_s else ""
                    rem_min = round(h.sleep_rem_s / 60) if h.sleep_rem_s else ""
                    row += [
                        h.sleep_score or "", sleep_hrs, deep_min, rem_min,
                        h.hrv_overnight_avg or "", h.resting_hr or "",
                        h.avg_stress if h.avg_stress and h.avg_stress >= 0 else "",
                        h.steps or "", h.active_kcal or "",
                    ]
                else:
                    row += [""] * 9

            if "activities" in cats:
                if has_activities and i < len(day.activities):  # type: ignore[arg-type]
                    a = day.activities[i]  # type: ignore[index]
                    dur_min = round(a.duration_s / 60, 1) if a.duration_s else ""
                    dist_mi = round(a.distance_m / 1609.34, 2) if a.distance_m else ""
                    pace = ""
                    if a.avg_pace_min_per_km:
                        pace = round(a.avg_pace_min_per_km * 1.60934, 2)
                    elev_ft = round(a.total_elevation_gain * 3.28084) if a.total_elevation_gain else ""
                    row += [
                        a.name or "", a.sport or "", a.workout_type or "",
                        dur_min, dist_mi, a.avg_hr or "", pace,
                        a.active_kcal or "",
                        round(a.intensity_score, 1) if a.intensity_score else "",
                        elev_ft,
                    ]
                else:
                    row += [""] * 10

            if "nutrition" in cats:
                t = day.nutrition_totals
                if t and i == 0:
                    row += [
                        round(t.calories), round(t.protein_g, 1),
                        round(t.carbs_g, 1), round(t.fat_g, 1),
                        round(t.caffeine_mg), t.entry_count,
                    ]
                else:
                    row += [""] * 6

            if "body_composition" in cats:
                bc = day.body_composition
                if bc and i == 0:
                    wt_lbs = round(float(bc.weight_kg) * 2.20462, 1) if bc.weight_kg else ""
                    row += [wt_lbs, bc.body_fat_pct or "", bc.bmi or ""]
                else:
                    row += [""] * 3

            writer.writerow(row)

    buf.seek(0)
    filename = f"strideiq_report_{start_date}_{end_date}.csv"
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
