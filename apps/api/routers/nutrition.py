"""
Nutrition API Endpoints

Photo parsing, barcode scanning, fueling product library, and CRUD for nutrition entries.
"""
import logging
import os
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.auth import get_current_user
from core.cache import invalidate_athlete_cache, invalidate_correlation_cache
from core.database import get_db
from models import (
    Activity,
    Athlete,
    AthleteFuelingProfile,
    FuelingProduct,
    NutritionEntry,
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
    PhotoParseResponse,
    PhotoParseItemResponse,
)
from services import nutrition_parser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["nutrition"])


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
        date=date.today(),
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
    result = parse_food_photo(image_bytes, db)

    template_match = None
    if result.items:
        from services.meal_template_service import find_template
        food_names = [item.food for item in result.items]
        template_match = find_template(str(current_user.id), food_names, db)

    return PhotoParseResponse(
        items=[
            PhotoParseItemResponse(
                food=item.food,
                grams=item.grams,
                calories=item.calories,
                protein_g=item.protein_g,
                carbs_g=item.carbs_g,
                fat_g=item.fat_g,
                fiber_g=item.fiber_g,
                macro_source=item.macro_source,
                fdc_id=item.fdc_id,
            )
            for item in result.items
        ],
        total_calories=result.total_calories,
        total_protein_g=result.total_protein_g,
        total_carbs_g=result.total_carbs_g,
        total_fat_g=result.total_fat_g,
        total_fiber_g=result.total_fiber_g,
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
    match = lookup_barcode(payload.upc, db)

    if not match:
        return BarcodeScanResponse(found=False)

    return BarcodeScanResponse(
        found=True,
        food_name=match.description,
        serving_size_g=100,
        calories=match.calories_per_100g,
        protein_g=match.protein_per_100g,
        carbs_g=match.carbs_per_100g,
        fat_g=match.fat_per_100g,
        fiber_g=match.fiber_per_100g,
        macro_source="branded_barcode",
        fdc_id=match.fdc_id,
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
        date=date.today(),
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
# CRUD (existing, with new field support)
# ---------------------------------------------------------------------------

@router.post("/nutrition", response_model=NutritionEntryResponse, status_code=201)
def create_nutrition_entry(
    nutrition: NutritionEntryCreate,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
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
    db_entry.timing = nutrition.timing
    db_entry.notes = nutrition.notes

    db.commit()
    db.refresh(db_entry)

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
