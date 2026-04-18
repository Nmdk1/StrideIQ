"""
Nutrition API Endpoints

Photo parsing, barcode scanning, fueling product library, and CRUD for nutrition entries.
"""
import csv
import io
import logging
import os
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from core.auth import get_current_user
from core.cache import invalidate_athlete_cache, invalidate_correlation_cache
from core.database import get_db
from services.timezone_utils import get_athlete_timezone, athlete_local_today, to_activity_local_date
from models import (
    Activity,
    Athlete,
    AthleteFuelingProfile,
    FuelingProduct,
    NutritionEntry,
    NutritionGoal,
)
from schemas import (
    BarcodeScanRequest,
    BarcodeScanResponse,
    FuelingLogRequest,
    FuelingProductCreate,
    FuelingProductResponse,
    FuelingProfileAdd,
    FuelingProfileResponse,
    NutritionEntryCreate,
    NutritionEntryResponse,
    NutritionEntryUpdate,
    PhotoParseResponse,
    PhotoParseItemResponse,
)
from services import nutrition_parser
from services.nutrition_targets import (
    compute_daily_targets,
    get_daily_actuals,
    get_local_hour,
    get_nutrition_insights,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["nutrition"])


# ---------------------------------------------------------------------------
# Past-day add/edit window
# ---------------------------------------------------------------------------
# Athletes can backfill or correct meals up to MAX_BACKLOG_DAYS in the past.
# Future-dated entries are never accepted (would corrupt correlation analytics
# and "today vs plan" rollups).

MAX_BACKLOG_DAYS = 60


def _maybe_learn_override_from_entry(
    db: Session,
    athlete_id,
    entry: NutritionEntry,
) -> None:
    """If the entry is tied to a UPC/fdc_id/fueling_product, persist the user's
    macros as an override for that food. Best-effort: errors never bubble up.
    """
    try:
        from services.food_override_service import (
            OverrideIdentifier,
            upsert_override,
        )

        # Identifier precedence: UPC > fueling_product_id > fdc_id.
        # Only one identifier may be set per override row, so we pick the
        # most-specific available signal.
        if entry.source_upc:
            identifier = OverrideIdentifier(upc=entry.source_upc)
        elif entry.fueling_product_id is not None:
            identifier = OverrideIdentifier(
                fueling_product_id=entry.fueling_product_id
            )
        elif entry.source_fdc_id is not None:
            identifier = OverrideIdentifier(fdc_id=entry.source_fdc_id)
        else:
            return  # nothing to learn against

        def _f(v):
            return float(v) if v is not None else None

        upsert_override(
            db,
            athlete_id,
            identifier,
            food_name=entry.notes if entry.notes else None,
            calories=_f(entry.calories),
            protein_g=_f(entry.protein_g),
            carbs_g=_f(entry.carbs_g),
            fat_g=_f(entry.fat_g),
            fiber_g=_f(entry.fiber_g),
            caffeine_mg=_f(entry.caffeine_mg),
            fluid_ml=None,
            sodium_mg=None,
        )
    except Exception:
        # Auto-learn is a nice-to-have; never fail the user's edit because
        # we couldn't memoise their correction.
        try:
            db.rollback()
        except Exception:
            pass


def _validate_entry_date(entry_date: date) -> None:
    """Reject future dates and dates older than the backlog window.

    Raises:
        HTTPException(400) — with a human-readable detail message.
    """
    today = date.today()
    if entry_date > today:
        raise HTTPException(
            status_code=400,
            detail="Cannot log nutrition for a future date.",
        )
    if (today - entry_date).days > MAX_BACKLOG_DAYS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Cannot log nutrition older than {MAX_BACKLOG_DAYS} days. "
                "Older entries can only be edited or deleted, not created."
            ),
        )


# ---------------------------------------------------------------------------
# Capability checks
# ---------------------------------------------------------------------------

@router.get("/nutrition/parse/available")
def nutrition_parse_available():
    from core.config import settings
    kimi = bool(settings.KIMI_API_KEY)
    openai = bool(os.getenv("OPENAI_API_KEY"))
    return {"available": kimi or openai}


# ---------------------------------------------------------------------------
# Nutrition goal / planning
# ---------------------------------------------------------------------------

class NutritionGoalRequest(BaseModel):
    goal_type: str  # 'performance', 'maintain', 'recomp'
    calorie_target: Optional[int] = None
    protein_g_per_kg: float = 1.8
    carb_pct: Optional[float] = 0.55
    fat_pct: Optional[float] = 0.45
    caffeine_target_mg: Optional[int] = None
    load_adaptive: bool = True
    load_multipliers: Optional[Dict[str, float]] = None


class NutritionGoalResponse(BaseModel):
    id: str
    goal_type: str
    calorie_target: Optional[int] = None
    protein_g_per_kg: float
    carb_pct: Optional[float] = None
    fat_pct: Optional[float] = None
    caffeine_target_mg: Optional[int] = None
    load_adaptive: bool
    load_multipliers: Optional[Dict[str, float]] = None


class DailyTargetResponse(BaseModel):
    calorie_target: int
    protein_g: float
    carbs_g: float
    fat_g: float
    caffeine_mg: Optional[int] = None
    day_tier: str
    day_tier_label: str
    base_calories: int
    multiplier: float
    load_adaptive: bool
    goal_type: str
    workout_title: Optional[str] = None
    actual_calories: float
    actual_protein_g: float
    actual_carbs_g: float
    actual_fat_g: float
    actual_caffeine_mg: float
    time_pct: float
    insights: List[Dict[str, str]]


_TIER_LABELS = {
    "rest": "Rest day",
    "easy": "Easy day",
    "moderate": "Moderate day",
    "hard": "Hard day",
    "long": "Long run day",
}


@router.get("/nutrition/goal", response_model=Optional[NutritionGoalResponse])
def get_nutrition_goal(
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    goal = db.query(NutritionGoal).filter(NutritionGoal.athlete_id == current_user.id).first()
    if not goal:
        return None
    return NutritionGoalResponse(
        id=str(goal.id),
        goal_type=goal.goal_type,
        calorie_target=goal.calorie_target,
        protein_g_per_kg=goal.protein_g_per_kg,
        carb_pct=goal.carb_pct,
        fat_pct=goal.fat_pct,
        caffeine_target_mg=goal.caffeine_target_mg,
        load_adaptive=goal.load_adaptive,
        load_multipliers=goal.load_multipliers,
    )


@router.post("/nutrition/goal", response_model=NutritionGoalResponse, status_code=200)
def upsert_nutrition_goal(
    payload: NutritionGoalRequest,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.goal_type not in ("performance", "maintain", "recomp"):
        raise HTTPException(status_code=422, detail="goal_type must be 'performance', 'maintain', or 'recomp'")

    if payload.carb_pct is not None and payload.fat_pct is not None:
        macro_sum = payload.carb_pct + payload.fat_pct
        if not (0.99 <= macro_sum <= 1.01):
            raise HTTPException(status_code=422, detail=f"carb_pct + fat_pct must equal 1.0, got {macro_sum:.3f}")

    goal = db.query(NutritionGoal).filter(NutritionGoal.athlete_id == current_user.id).first()
    if goal:
        goal.goal_type = payload.goal_type
        goal.calorie_target = payload.calorie_target
        goal.protein_g_per_kg = payload.protein_g_per_kg
        goal.carb_pct = payload.carb_pct
        goal.fat_pct = payload.fat_pct
        goal.caffeine_target_mg = payload.caffeine_target_mg
        goal.load_adaptive = payload.load_adaptive
        goal.load_multipliers = payload.load_multipliers
    else:
        goal = NutritionGoal(
            athlete_id=current_user.id,
            goal_type=payload.goal_type,
            calorie_target=payload.calorie_target,
            protein_g_per_kg=payload.protein_g_per_kg,
            carb_pct=payload.carb_pct,
            fat_pct=payload.fat_pct,
            caffeine_target_mg=payload.caffeine_target_mg,
            load_adaptive=payload.load_adaptive,
            load_multipliers=payload.load_multipliers,
        )
        db.add(goal)

    db.commit()
    db.refresh(goal)

    return NutritionGoalResponse(
        id=str(goal.id),
        goal_type=goal.goal_type,
        calorie_target=goal.calorie_target,
        protein_g_per_kg=goal.protein_g_per_kg,
        carb_pct=goal.carb_pct,
        fat_pct=goal.fat_pct,
        caffeine_target_mg=goal.caffeine_target_mg,
        load_adaptive=goal.load_adaptive,
        load_multipliers=goal.load_multipliers,
    )


@router.get("/nutrition/daily-target", response_model=Optional[DailyTargetResponse])
def get_daily_target(
    target_date: Optional[str] = Query(None),
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from datetime import date as date_type
    td = date_type.fromisoformat(target_date) if target_date else athlete_local_today(get_athlete_timezone(current_user))

    targets = compute_daily_targets(db, current_user.id, td)
    if not targets:
        return None

    actuals = get_daily_actuals(db, current_user.id, td)
    local_hour = get_local_hour(current_user)
    time_pct = round((local_hour / 24) * 100, 1)
    insights = get_nutrition_insights(db, current_user.id, targets["day_tier"], limit=1)

    return DailyTargetResponse(
        calorie_target=targets["calorie_target"],
        protein_g=targets["protein_g"],
        carbs_g=targets["carbs_g"],
        fat_g=targets["fat_g"],
        caffeine_mg=targets["caffeine_mg"],
        day_tier=targets["day_tier"],
        day_tier_label=_TIER_LABELS.get(targets["day_tier"], targets["day_tier"]),
        base_calories=targets["base_calories"],
        multiplier=targets["multiplier"],
        load_adaptive=targets["load_adaptive"],
        goal_type=targets["goal_type"],
        workout_title=targets["workout_title"],
        actual_calories=actuals["calories"],
        actual_protein_g=actuals["protein_g"],
        actual_carbs_g=actuals["carbs_g"],
        actual_fat_g=actuals["fat_g"],
        actual_caffeine_mg=actuals["caffeine_mg"],
        time_pct=time_pct,
        insights=insights,
    )


# ---------------------------------------------------------------------------
# Text parsing
# ---------------------------------------------------------------------------

class NutritionParseRequest(BaseModel):
    text: str


@router.post("/nutrition/parse", response_model=NutritionEntryCreate, status_code=200)
def parse_nutrition(
    payload: NutritionParseRequest,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    text = (payload.text or "").strip()
    if not text:
        raise HTTPException(status_code=422, detail="text is required")

    try:
        parsed = nutrition_parser.parse_nutrition_text(text, db=db)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Nutrition parsing unavailable: {e}")

    return NutritionEntryCreate(
        athlete_id=current_user.id,
        date=athlete_local_today(get_athlete_timezone(current_user)),
        entry_type="daily",
        calories=parsed.get("calories"),
        protein_g=parsed.get("protein_g"),
        carbs_g=parsed.get("carbs_g"),
        fat_g=parsed.get("fat_g"),
        fiber_g=parsed.get("fiber_g"),
        notes=parsed.get("notes") or text,
        macro_source=parsed.get("macro_source", "llm_estimated"),
    )


# ---------------------------------------------------------------------------
# Photo parsing
# ---------------------------------------------------------------------------

@router.post("/nutrition/parse-photo", response_model=PhotoParseResponse, status_code=200)
async def parse_photo(
    image: UploadFile = File(...),
    entry_type: str = Query("daily"),
    activity_id: Optional[UUID] = Query(None),
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(status_code=422, detail="File must be an image")

    image_bytes = await image.read()
    if len(image_bytes) > 10 * 1024 * 1024:
        raise HTTPException(status_code=422, detail="Image exceeds 10MB limit")

    from services.nutrition_photo_parser import parse_food_photo
    from services.food_override_service import find_override, record_override_applied
    result = parse_food_photo(image_bytes, db)

    template_match = None
    if result.items:
        from services.meal_template_service import find_template
        food_names = [item.food for item in result.items]
        template_match = find_template(str(current_user.id), food_names, db)

    items_out: list[PhotoParseItemResponse] = []
    total_cal = total_p = total_c = total_f = total_fib = 0.0
    for item in result.items:
        is_override = False
        override_id: Optional[int] = None
        cal, p, c, f, fib = (
            item.calories, item.protein_g, item.carbs_g, item.fat_g, item.fiber_g
        )
        if item.fdc_id is not None:
            override = find_override(db, current_user.id, fdc_id=item.fdc_id)
            if override and item.grams and item.grams > 0:
                # Photo parser items are absolute (already scaled to grams).
                # Override values are stored per the *user's normal serving*
                # — which for photo parses we treat as 100g (USDAFood basis).
                # Scale override values by the same grams ratio.
                scale = item.grams / 100.0
                if override.calories is not None:
                    cal = override.calories * scale
                if override.protein_g is not None:
                    p = override.protein_g * scale
                if override.carbs_g is not None:
                    c = override.carbs_g * scale
                if override.fat_g is not None:
                    f = override.fat_g * scale
                if override.fiber_g is not None:
                    fib = override.fiber_g * scale
                is_override = True
                override_id = override.id
                record_override_applied(db, override)

        items_out.append(
            PhotoParseItemResponse(
                food=item.food,
                grams=item.grams,
                calories=cal,
                protein_g=p,
                carbs_g=c,
                fat_g=f,
                fiber_g=fib,
                macro_source=item.macro_source,
                fdc_id=item.fdc_id,
                is_athlete_override=is_override,
                override_id=override_id,
            )
        )
        total_cal += cal or 0
        total_p += p or 0
        total_c += c or 0
        total_f += f or 0
        total_fib += fib or 0

    return PhotoParseResponse(
        items=items_out,
        total_calories=total_cal,
        total_protein_g=total_p,
        total_carbs_g=total_c,
        total_fat_g=total_f,
        total_fiber_g=total_fib,
        template_match=template_match,
    )


# ---------------------------------------------------------------------------
# Barcode scanning
# ---------------------------------------------------------------------------

@router.post("/nutrition/scan-barcode", response_model=BarcodeScanResponse, status_code=200)
def scan_barcode(
    payload: BarcodeScanRequest,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from services.barcode_lookup import lookup_barcode
    from services.food_override_service import find_override, record_override_applied

    match = lookup_barcode(payload.upc, db)

    # An athlete might register an override for a UPC that we don't have in
    # the catalog yet — honour it even when the catalog lookup misses.
    override = find_override(
        db,
        current_user.id,
        upc=payload.upc,
        fdc_id=match.fdc_id if match else None,
    )

    if not match and not override:
        return BarcodeScanResponse(found=False)

    if match:
        food_name = match.description
        serving = 100
        cal = match.calories_per_100g
        p = match.protein_per_100g
        c = match.carbs_per_100g
        f = match.fat_per_100g
        fib = match.fiber_per_100g
        fdc_id = match.fdc_id
    else:
        # Pure-override hit (UPC unknown to catalog)
        food_name = None
        serving = None
        cal = p = c = f = fib = None
        fdc_id = None

    if override:
        if override.food_name is not None:
            food_name = override.food_name
        if override.serving_size_g is not None:
            serving = override.serving_size_g
        if override.calories is not None:
            cal = override.calories
        if override.protein_g is not None:
            p = override.protein_g
        if override.carbs_g is not None:
            c = override.carbs_g
        if override.fat_g is not None:
            f = override.fat_g
        if override.fiber_g is not None:
            fib = override.fiber_g
        record_override_applied(db, override)

    return BarcodeScanResponse(
        found=True,
        food_name=food_name,
        serving_size_g=serving,
        calories=cal,
        protein_g=p,
        carbs_g=c,
        fat_g=f,
        fiber_g=fib,
        macro_source="branded_barcode",
        fdc_id=fdc_id,
        upc=payload.upc,
        is_athlete_override=override is not None,
        override_id=override.id if override else None,
    )


# ---------------------------------------------------------------------------
# Fueling product catalog
# ---------------------------------------------------------------------------

@router.get("/nutrition/fueling-products", response_model=List[FuelingProductResponse])
def list_fueling_products(
    brand: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(FuelingProduct)
    if brand:
        q = q.filter(FuelingProduct.brand.ilike(f"%{brand}%"))
    if category:
        q = q.filter(FuelingProduct.category == category)
    if search:
        q = q.filter(
            (FuelingProduct.brand.ilike(f"%{search}%"))
            | (FuelingProduct.product_name.ilike(f"%{search}%"))
        )
    return q.order_by(FuelingProduct.brand, FuelingProduct.product_name).all()


@router.post("/nutrition/fueling-products", response_model=FuelingProductResponse, status_code=201)
def create_fueling_product(
    product: FuelingProductCreate,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    db_product = FuelingProduct(
        brand=product.brand,
        product_name=product.product_name,
        variant=product.variant,
        category=product.category,
        serving_size_g=product.serving_size_g,
        calories=product.calories,
        carbs_g=product.carbs_g,
        protein_g=product.protein_g,
        fat_g=product.fat_g,
        fiber_g=product.fiber_g,
        caffeine_mg=product.caffeine_mg,
        sodium_mg=product.sodium_mg,
        fluid_ml=product.fluid_ml,
        carb_source=product.carb_source,
        glucose_fructose_ratio=product.glucose_fructose_ratio,
        is_verified=False,
    )
    db.add(db_product)
    db.commit()
    db.refresh(db_product)
    return db_product


# ---------------------------------------------------------------------------
# Athlete fueling profile (shelf)
# ---------------------------------------------------------------------------

@router.get("/nutrition/fueling-profile", response_model=List[FuelingProfileResponse])
def get_fueling_profile(
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(AthleteFuelingProfile)
        .filter(
            AthleteFuelingProfile.athlete_id == current_user.id,
            AthleteFuelingProfile.is_active == True,
        )
        .all()
    )


@router.post("/nutrition/fueling-profile", response_model=FuelingProfileResponse, status_code=201)
def add_to_fueling_profile(
    payload: FuelingProfileAdd,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    product = db.query(FuelingProduct).filter(FuelingProduct.id == payload.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    existing = db.query(AthleteFuelingProfile).filter(
        AthleteFuelingProfile.athlete_id == current_user.id,
        AthleteFuelingProfile.product_id == payload.product_id,
    ).first()

    if existing:
        existing.is_active = True
        existing.usage_context = payload.usage_context
        existing.notes = payload.notes
        db.commit()
        db.refresh(existing)
        return existing

    profile = AthleteFuelingProfile(
        athlete_id=current_user.id,
        product_id=payload.product_id,
        usage_context=payload.usage_context,
        notes=payload.notes,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


@router.delete("/nutrition/fueling-profile/{product_id}", status_code=204)
def remove_from_fueling_profile(
    product_id: int,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = db.query(AthleteFuelingProfile).filter(
        AthleteFuelingProfile.athlete_id == current_user.id,
        AthleteFuelingProfile.product_id == product_id,
    ).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Product not in your shelf")
    profile.is_active = False
    db.commit()
    return None


# ---------------------------------------------------------------------------
# Fueling log (quick-log a product as a NutritionEntry)
# ---------------------------------------------------------------------------

@router.post("/nutrition/log-fueling", response_model=NutritionEntryResponse, status_code=201)
def log_fueling(
    payload: FuelingLogRequest,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    product = db.query(FuelingProduct).filter(FuelingProduct.id == payload.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    if payload.entry_type in ("pre_activity", "during_activity", "post_activity") and payload.activity_id:
        activity = db.query(Activity).filter(
            Activity.id == payload.activity_id,
            Activity.athlete_id == current_user.id,
        ).first()
        if not activity:
            raise HTTPException(status_code=404, detail="Activity not found")

    qty = payload.quantity or 1.0
    entry = NutritionEntry(
        athlete_id=current_user.id,
        date=athlete_local_today(get_athlete_timezone(current_user)),
        entry_type=payload.entry_type,
        activity_id=payload.activity_id,
        calories=Decimal(str((product.calories or 0) * qty)),
        protein_g=Decimal(str((product.protein_g or 0) * qty)),
        carbs_g=Decimal(str((product.carbs_g or 0) * qty)),
        fat_g=Decimal(str((product.fat_g or 0) * qty)),
        fiber_g=Decimal(str((product.fiber_g or 0) * qty)),
        caffeine_mg=(product.caffeine_mg or 0) * qty,
        fluid_ml=(product.fluid_ml or 0) * qty,
        carb_source=product.carb_source,
        glucose_fructose_ratio=product.glucose_fructose_ratio,
        macro_source="product_library",
        fueling_product_id=product.id,
        timing=payload.timing or datetime.now(timezone.utc),
        notes=f"{product.brand} {product.product_name}" + (f" {product.variant}" if product.variant else ""),
    )

    db.add(entry)
    db.commit()
    db.refresh(entry)

    invalidate_athlete_cache(str(current_user.id))
    invalidate_correlation_cache(str(current_user.id))

    return entry


# ---------------------------------------------------------------------------
# Reporting: summary, trends, export
# ---------------------------------------------------------------------------


class _DaySummary(BaseModel):
    date: str
    calories: float
    protein_g: float
    carbs_g: float
    fat_g: float
    fiber_g: float
    caffeine_mg: float
    entry_count: int
    has_pre_activity: bool
    has_during_activity: bool


class NutritionSummaryResponse(BaseModel):
    days: List[_DaySummary]
    period_avg_calories: float
    period_avg_protein_g: float
    period_avg_carbs_g: float
    period_avg_fat_g: float
    days_logged: int
    total_days: int


@router.get("/nutrition/summary", response_model=NutritionSummaryResponse)
def get_nutrition_summary(
    days: int = Query(7, ge=1, le=365),
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    end = athlete_local_today(get_athlete_timezone(current_user))
    start = end - timedelta(days=days - 1)

    entries = (
        db.query(NutritionEntry)
        .filter(
            NutritionEntry.athlete_id == current_user.id,
            NutritionEntry.date >= start,
            NutritionEntry.date <= end,
        )
        .all()
    )

    by_day: Dict[str, list] = defaultdict(list)
    for e in entries:
        by_day[e.date.isoformat()].append(e)

    day_summaries = []
    d = start
    while d <= end:
        ds = d.isoformat()
        day_entries = by_day.get(ds, [])
        day_summaries.append(_DaySummary(
            date=ds,
            calories=sum(float(e.calories or 0) for e in day_entries),
            protein_g=sum(float(e.protein_g or 0) for e in day_entries),
            carbs_g=sum(float(e.carbs_g or 0) for e in day_entries),
            fat_g=sum(float(e.fat_g or 0) for e in day_entries),
            fiber_g=sum(float(e.fiber_g or 0) for e in day_entries),
            caffeine_mg=sum(float(e.caffeine_mg or 0) for e in day_entries),
            entry_count=len(day_entries),
            has_pre_activity=any(e.entry_type == "pre_activity" for e in day_entries),
            has_during_activity=any(e.entry_type == "during_activity" for e in day_entries),
        ))
        d += timedelta(days=1)

    logged_days = [s for s in day_summaries if s.entry_count > 0]
    n_logged = len(logged_days)

    return NutritionSummaryResponse(
        days=day_summaries,
        period_avg_calories=round(sum(s.calories for s in logged_days) / max(n_logged, 1)),
        period_avg_protein_g=round(sum(s.protein_g for s in logged_days) / max(n_logged, 1)),
        period_avg_carbs_g=round(sum(s.carbs_g for s in logged_days) / max(n_logged, 1)),
        period_avg_fat_g=round(sum(s.fat_g for s in logged_days) / max(n_logged, 1)),
        days_logged=n_logged,
        total_days=len(day_summaries),
    )


class _ActivityNutrition(BaseModel):
    activity_id: str
    activity_name: str
    activity_date: str
    distance_mi: Optional[float] = None
    pre_entries: List[Dict[str, Any]]
    during_entries: List[Dict[str, Any]]
    post_entries: List[Dict[str, Any]]
    pre_total_carbs_g: float
    pre_total_caffeine_mg: float
    during_total_carbs_g: float


class ActivityNutritionResponse(BaseModel):
    activities: List[_ActivityNutrition]


@router.get("/nutrition/activity-linked", response_model=ActivityNutritionResponse)
def get_activity_linked_nutrition(
    days: int = Query(30, ge=1, le=365),
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _tz = get_athlete_timezone(current_user)
    cutoff = athlete_local_today(_tz) - timedelta(days=days)
    M_PER_MI = 1609.344

    linked_entries = (
        db.query(NutritionEntry)
        .filter(
            NutritionEntry.athlete_id == current_user.id,
            NutritionEntry.activity_id.isnot(None),
            NutritionEntry.date >= cutoff,
        )
        .all()
    )

    by_activity: Dict[str, list] = defaultdict(list)
    for e in linked_entries:
        by_activity[str(e.activity_id)].append(e)

    activity_ids = list(by_activity.keys())
    if not activity_ids:
        return ActivityNutritionResponse(activities=[])

    activities = (
        db.query(Activity)
        .filter(Activity.id.in_(activity_ids))
        .order_by(Activity.start_time.desc())
        .all()
    )

    result = []
    for act in activities:
        act_entries = by_activity.get(str(act.id), [])
        pre = [e for e in act_entries if e.entry_type == "pre_activity"]
        during = [e for e in act_entries if e.entry_type == "during_activity"]
        post = [e for e in act_entries if e.entry_type == "post_activity"]

        def _entry_dict(e: NutritionEntry) -> Dict[str, Any]:
            return {
                "notes": e.notes or "",
                "calories": float(e.calories or 0),
                "carbs_g": float(e.carbs_g or 0),
                "protein_g": float(e.protein_g or 0),
                "fat_g": float(e.fat_g or 0),
                "caffeine_mg": float(e.caffeine_mg or 0),
                "macro_source": e.macro_source or "",
            }

        dist = (act.distance_meters or 0) / M_PER_MI if act.distance_meters else None
        result.append(_ActivityNutrition(
            activity_id=str(act.id),
            activity_name=act.name or "Run",
            activity_date=to_activity_local_date(act, _tz).isoformat() if act.start_time else "",
            distance_mi=round(dist, 1) if dist else None,
            pre_entries=[_entry_dict(e) for e in pre],
            during_entries=[_entry_dict(e) for e in during],
            post_entries=[_entry_dict(e) for e in post],
            pre_total_carbs_g=sum(float(e.carbs_g or 0) for e in pre),
            pre_total_caffeine_mg=sum(float(e.caffeine_mg or 0) for e in pre),
            during_total_carbs_g=sum(float(e.carbs_g or 0) for e in during),
        ))

    return ActivityNutritionResponse(activities=result)


@router.get("/nutrition/export")
def export_nutrition_csv(
    start_date: str = Query(...),
    end_date: str = Query(...),
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    entries = (
        db.query(NutritionEntry)
        .filter(
            NutritionEntry.athlete_id == current_user.id,
            NutritionEntry.date >= start_date,
            NutritionEntry.date <= end_date,
        )
        .order_by(NutritionEntry.date.asc(), NutritionEntry.created_at.asc())
        .all()
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "date", "entry_type", "calories", "protein_g", "carbs_g", "fat_g",
        "fiber_g", "caffeine_mg", "fluid_ml", "notes", "macro_source", "created_at",
    ])
    for e in entries:
        writer.writerow([
            e.date.isoformat() if e.date else "",
            e.entry_type or "",
            float(e.calories) if e.calories else "",
            float(e.protein_g) if e.protein_g else "",
            float(e.carbs_g) if e.carbs_g else "",
            float(e.fat_g) if e.fat_g else "",
            float(e.fiber_g) if e.fiber_g else "",
            float(e.caffeine_mg) if e.caffeine_mg else "",
            float(e.fluid_ml) if e.fluid_ml else "",
            e.notes or "",
            e.macro_source or "",
            e.created_at.isoformat() if e.created_at else "",
        ])

    output.seek(0)
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=nutrition_{start_date}_to_{end_date}.csv"},
    )


# ---------------------------------------------------------------------------
# CRUD (existing, with new field support)
# ---------------------------------------------------------------------------

@router.post("/nutrition", response_model=NutritionEntryResponse, status_code=201)
def create_nutrition_entry(
    nutrition: NutritionEntryCreate,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _validate_entry_date(nutrition.date)

    if nutrition.entry_type in ("pre_activity", "during_activity", "post_activity"):
        if not nutrition.activity_id:
            raise HTTPException(status_code=400, detail=f"activity_id required for '{nutrition.entry_type}'")
        activity = db.query(Activity).filter(
            Activity.id == nutrition.activity_id,
            Activity.athlete_id == current_user.id,
        ).first()
        if not activity:
            raise HTTPException(status_code=404, detail="Activity not found")
    elif nutrition.entry_type == "daily":
        if nutrition.activity_id is not None:
            raise HTTPException(status_code=400, detail="activity_id must be None for 'daily'")
    else:
        raise HTTPException(status_code=400, detail=f"Invalid entry_type: '{nutrition.entry_type}'")

    db_entry = NutritionEntry(
        athlete_id=current_user.id,
        date=nutrition.date,
        entry_type=nutrition.entry_type,
        activity_id=nutrition.activity_id,
        calories=Decimal(str(nutrition.calories)) if nutrition.calories else None,
        protein_g=Decimal(str(nutrition.protein_g)) if nutrition.protein_g else None,
        carbs_g=Decimal(str(nutrition.carbs_g)) if nutrition.carbs_g else None,
        fat_g=Decimal(str(nutrition.fat_g)) if nutrition.fat_g else None,
        fiber_g=Decimal(str(nutrition.fiber_g)) if nutrition.fiber_g else None,
        caffeine_mg=nutrition.caffeine_mg,
        fluid_ml=nutrition.fluid_ml,
        carb_source=nutrition.carb_source,
        glucose_fructose_ratio=nutrition.glucose_fructose_ratio,
        macro_source=nutrition.macro_source,
        fueling_product_id=nutrition.fueling_product_id,
        source_fdc_id=nutrition.source_fdc_id,
        source_upc=nutrition.source_upc,
        timing=nutrition.timing,
        notes=nutrition.notes,
    )

    db.add(db_entry)
    db.commit()
    db.refresh(db_entry)

    if nutrition.macro_source and nutrition.notes:
        try:
            from services.meal_template_service import upsert_template
            items = [{"food": nutrition.notes, "calories": nutrition.calories}]
            upsert_template(str(current_user.id), [nutrition.notes], items, db)
        except Exception:
            pass

    invalidate_athlete_cache(str(current_user.id))
    invalidate_correlation_cache(str(current_user.id))

    return db_entry


@router.get("/nutrition", response_model=List[NutritionEntryResponse])
def get_nutrition_entries(
    current_user: Athlete = Depends(get_current_user),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    entry_type: Optional[str] = Query(None),
    activity_id: Optional[UUID] = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(NutritionEntry).filter(NutritionEntry.athlete_id == current_user.id)
    if start_date:
        query = query.filter(NutritionEntry.date >= start_date)
    if end_date:
        query = query.filter(NutritionEntry.date <= end_date)
    if entry_type:
        query = query.filter(NutritionEntry.entry_type == entry_type)
    if activity_id:
        query = query.filter(NutritionEntry.activity_id == activity_id)
    return query.order_by(NutritionEntry.date.desc(), NutritionEntry.created_at.desc()).all()


@router.get("/nutrition/{id}", response_model=NutritionEntryResponse)
def get_nutrition_entry_by_id(
    id: UUID,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    entry = db.query(NutritionEntry).filter(NutritionEntry.id == id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Nutrition entry not found")
    if entry.athlete_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    return entry


@router.put("/nutrition/{id}", response_model=NutritionEntryResponse)
def update_nutrition_entry(
    id: UUID,
    nutrition: NutritionEntryCreate,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    db_entry = db.query(NutritionEntry).filter(NutritionEntry.id == id).first()
    if not db_entry:
        raise HTTPException(status_code=404, detail="Nutrition entry not found")
    if db_entry.athlete_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    _validate_entry_date(nutrition.date)

    if nutrition.entry_type in ("pre_activity", "during_activity", "post_activity"):
        if not nutrition.activity_id:
            raise HTTPException(status_code=400, detail=f"activity_id required for '{nutrition.entry_type}'")
        activity = db.query(Activity).filter(
            Activity.id == nutrition.activity_id,
            Activity.athlete_id == current_user.id,
        ).first()
        if not activity:
            raise HTTPException(status_code=404, detail="Activity not found")
    elif nutrition.entry_type == "daily":
        if nutrition.activity_id is not None:
            raise HTTPException(status_code=400, detail="activity_id must be None for 'daily'")
    else:
        raise HTTPException(status_code=400, detail=f"Invalid entry_type: '{nutrition.entry_type}'")

    db_entry.date = nutrition.date
    db_entry.entry_type = nutrition.entry_type
    db_entry.activity_id = nutrition.activity_id
    db_entry.calories = Decimal(str(nutrition.calories)) if nutrition.calories else None
    db_entry.protein_g = Decimal(str(nutrition.protein_g)) if nutrition.protein_g else None
    db_entry.carbs_g = Decimal(str(nutrition.carbs_g)) if nutrition.carbs_g else None
    db_entry.fat_g = Decimal(str(nutrition.fat_g)) if nutrition.fat_g else None
    db_entry.fiber_g = Decimal(str(nutrition.fiber_g)) if nutrition.fiber_g else None
    db_entry.caffeine_mg = nutrition.caffeine_mg
    db_entry.fluid_ml = nutrition.fluid_ml
    db_entry.carb_source = nutrition.carb_source
    db_entry.glucose_fructose_ratio = nutrition.glucose_fructose_ratio
    db_entry.macro_source = nutrition.macro_source
    db_entry.fueling_product_id = nutrition.fueling_product_id
    if nutrition.source_fdc_id is not None:
        db_entry.source_fdc_id = nutrition.source_fdc_id
    if nutrition.source_upc is not None:
        db_entry.source_upc = nutrition.source_upc
    db_entry.timing = nutrition.timing
    db_entry.notes = nutrition.notes

    db.commit()
    db.refresh(db_entry)

    _maybe_learn_override_from_entry(db, current_user.id, db_entry)

    invalidate_athlete_cache(str(current_user.id))
    invalidate_correlation_cache(str(current_user.id))

    return db_entry


@router.patch("/nutrition/{id}", response_model=NutritionEntryResponse)
def patch_nutrition_entry(
    id: UUID,
    updates: NutritionEntryUpdate,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    db_entry = db.query(NutritionEntry).filter(NutritionEntry.id == id).first()
    if not db_entry:
        raise HTTPException(status_code=404, detail="Nutrition entry not found")
    if db_entry.athlete_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    patch_data = updates.model_dump(exclude_unset=True)
    if "date" in patch_data and patch_data["date"] is not None:
        _validate_entry_date(patch_data["date"])
    macro_touched = any(
        k in patch_data
        for k in ("calories", "protein_g", "carbs_g", "fat_g", "fiber_g", "caffeine_mg")
    )
    for field, value in patch_data.items():
        if field in ("calories", "protein_g", "carbs_g", "fat_g", "fiber_g"):
            setattr(db_entry, field, Decimal(str(value)) if value is not None else None)
        else:
            setattr(db_entry, field, value)

    db.commit()
    db.refresh(db_entry)

    if macro_touched:
        _maybe_learn_override_from_entry(db, current_user.id, db_entry)

    invalidate_athlete_cache(str(current_user.id))
    invalidate_correlation_cache(str(current_user.id))

    return db_entry


@router.delete("/nutrition/{id}", status_code=204)
def delete_nutrition_entry(
    id: UUID,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    db_entry = db.query(NutritionEntry).filter(NutritionEntry.id == id).first()
    if not db_entry:
        raise HTTPException(status_code=404, detail="Nutrition entry not found")
    if db_entry.athlete_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    db.delete(db_entry)
    db.commit()

    invalidate_athlete_cache(str(current_user.id))
    invalidate_correlation_cache(str(current_user.id))

    return None
