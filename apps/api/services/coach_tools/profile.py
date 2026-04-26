from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, date
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import func

logger = logging.getLogger(__name__)

from models import Activity, Athlete, TrainingPlan
from core.date_utils import calculate_age
from services.coach_tools._utils import (
    _iso, _relative_date, _preferred_units, _M_PER_MI,
)


def get_athlete_profile(db: Session, athlete_id: UUID) -> Dict[str, Any]:
    """
    Phase 3: Athlete profile with physiological thresholds and runner typing.

    Returns max_hr, threshold paces, RPI, runner type, and training metrics.
    Critical for personalized recommendations and goal setting.
    """
    from services.timezone_utils import get_athlete_timezone_from_db, athlete_local_today
    _tz = get_athlete_timezone_from_db(db, athlete_id)
    now = datetime.utcnow()

    try:
        athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
        if not athlete:
            return {"ok": False, "tool": "get_athlete_profile", "error": "Athlete not found"}

        units = (athlete.preferred_units or "metric")

        # Calculate age if birthdate available
        age = None
        if athlete.birthdate:
            today = athlete_local_today(_tz)
            age = calculate_age(athlete.birthdate, today)

        # Convert threshold pace for display
        threshold_pace_display = None
        if athlete.threshold_pace_per_km:
            if units == "imperial":
                # Convert sec/km to min:sec/mile
                sec_per_mi = athlete.threshold_pace_per_km * 1.60934
                m = int(sec_per_mi // 60)
                s = int(round(sec_per_mi % 60))
                threshold_pace_display = f"{m}:{s:02d}/mi"
            else:
                m = int(athlete.threshold_pace_per_km // 60)
                s = int(round(athlete.threshold_pace_per_km % 60))
                threshold_pace_display = f"{m}:{s:02d}/km"

        # Effort-based coaching only — NO HR zones.
        # KB: "What We Don't Do: Use zone numbers (Zone 1, Zone 2, etc.)"
        # KB: "Easy pace is NOT derived from race performance. It is derived
        #      from perceived effort: can you talk in complete sentences?"
        # Training paces come from RPI via get_training_paces() — that is the
        # authoritative source. This tool provides profile context only.

        # Build evidence
        evidence: List[Dict[str, Any]] = []
        if athlete.rpi:
            evidence.append({"type": "metric", "name": "RPI", "value": f"{athlete.rpi:.1f}"})
        if athlete.runner_type:
            evidence.append({"type": "classification", "name": "runner_type", "value": athlete.runner_type})
        if athlete.max_hr:
            evidence.append({"type": "metric", "name": "max_hr", "value": f"{athlete.max_hr} bpm"})

        # --- Narrative ---
        n_parts: List[str] = []
        if age is not None:
            n_parts.append(f"{age}-year-old")
        if athlete.sex:
            n_parts.append(f"{athlete.sex}")
        n_parts.append("runner.")
        if athlete.rpi:
            n_parts.append(f"RPI (Running Performance Index): {athlete.rpi:.1f}.")
        if athlete.runner_type:
            n_parts.append(f"Runner type: {athlete.runner_type}.")
        if athlete.max_hr:
            n_parts.append(f"Max HR: {athlete.max_hr} bpm.")
        if threshold_pace_display:
            n_parts.append(f"Threshold pace: {threshold_pace_display}.")
        if athlete.durability_index:
            n_parts.append(f"Durability index: {float(athlete.durability_index):.1f}.")
        if athlete.recovery_half_life_hours:
            rhl_days = round(float(athlete.recovery_half_life_hours) / 24.0, 1)
            n_parts.append(f"Recovery half-life: {rhl_days} days.")
        if athlete.current_streak_weeks:
            n_parts.append(f"Current training streak: {athlete.current_streak_weeks} weeks.")
        narrative = " ".join(n_parts) if n_parts else "Athlete profile data unavailable."

        return {
            "ok": True,
            "tool": "get_athlete_profile",
            "generated_at": _iso(now),
            "narrative": narrative,
            "data": {
                "preferred_units": units,
                "demographics": {
                    "age": age,
                    "sex": athlete.sex,
                    "height_cm": float(athlete.height_cm) if athlete.height_cm else None,
                },
                "physiological": {
                    "max_hr": athlete.max_hr,
                    "resting_hr": athlete.resting_hr,
                    "threshold_hr": athlete.threshold_hr,
                    "threshold_pace": threshold_pace_display,
                    "threshold_pace_sec_per_km": float(athlete.threshold_pace_per_km) if athlete.threshold_pace_per_km else None,
                    "rpi": float(athlete.rpi) if athlete.rpi else None,
                },
                "runner_typing": {
                    "type": athlete.runner_type,
                    "confidence": float(athlete.runner_type_confidence) if athlete.runner_type_confidence else None,
                    "last_calculated": _iso(athlete.runner_type_last_calculated) if athlete.runner_type_last_calculated else None,
                    "type_descriptions": {
                        "speedster": "Strong at shorter distances, may need endurance work for marathons",
                        "endurance_monster": "Excels at longer distances, may need speed work for 5K/10K",
                        "balanced": "Versatile across all distances",
                    },
                },
                "training_metrics": {
                    "durability_index": float(athlete.durability_index) if athlete.durability_index else None,
                    "recovery_half_life_hours": float(athlete.recovery_half_life_hours) if athlete.recovery_half_life_hours else None,
                    "consistency_index": float(athlete.consistency_index) if athlete.consistency_index else None,
                    "current_streak_weeks": athlete.current_streak_weeks,
                    "longest_streak_weeks": athlete.longest_streak_weeks,
                },
            },
            "evidence": evidence,
        }
    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        return {"ok": False, "tool": "get_athlete_profile", "error": str(e)}



def get_profile_edit_paths(db: Session, athlete_id: UUID, field: str = "birthdate") -> Dict[str, Any]:
    """Return deterministic UI navigation for athlete profile edits."""
    from services.timezone_utils import get_athlete_timezone_from_db, athlete_local_today
    _tz = get_athlete_timezone_from_db(db, athlete_id)
    _today = athlete_local_today(_tz)
    now = datetime.utcnow()
    normalized_field = (field or "birthdate").strip().lower()
    field_aliases = {
        "age": "birthdate",
        "dob": "birthdate",
        "birthday": "birthdate",
        "birth date": "birthdate",
        "name": "display_name",
        "display name": "display_name",
        "height": "height_cm",
        "sex": "sex",
        "gender": "sex",
    }
    canonical_field = field_aliases.get(normalized_field, normalized_field)
    mapping = {
        "birthdate": {
            "route": "/settings",
            "section": "Personal Information",
            "field": "Birthdate",
            "note": "Set your correct birthdate here; age is calculated from this field.",
        },
        "sex": {
            "route": "/settings",
            "section": "Personal Information",
            "field": "Sex",
            "note": "Update sex under Personal Information.",
        },
        "display_name": {
            "route": "/settings",
            "section": "Personal Information",
            "field": "Display Name",
            "note": "This controls how your name appears in the app.",
        },
        "height_cm": {
            "route": "/settings",
            "section": "Personal Information",
            "field": "Height",
            "note": "Enter your current height.",
        },
        "email": {
            "route": "/settings",
            "section": "Personal Information",
            "field": "Email",
            "note": "Changing email may require a verification flow.",
        },
    }
    resolved = mapping.get(canonical_field)
    if not resolved:
        resolved = {
            "route": "/settings",
            "section": "Personal Information",
            "field": "Personal Information",
            "note": "Use Settings > Personal Information for account details.",
        }

    return {
        "ok": True,
        "tool": "get_profile_edit_paths",
        "generated_at": _iso(now),
        "narrative": (
            f"To edit {canonical_field.replace('_', ' ')}, go to {resolved['route']} -> "
            f"{resolved['section']} -> {resolved['field']}."
        ),
        "data": {
            "requested_field": normalized_field,
            "resolved_field": canonical_field,
            "route": resolved["route"],
            "section": resolved["section"],
            "field": resolved["field"],
            "note": resolved["note"],
        },
        "evidence": [
            {
                "type": "ui_path",
                "id": f"profile_path:{canonical_field}",
                "date": _today.isoformat(),
                "value": f"{resolved['route']} > {resolved['section']} > {resolved['field']}",
            }
        ],
    }



def _get_intent_snapshot(db: Session, athlete_id: UUID):
    from models import CoachIntentSnapshot

    snap = db.query(CoachIntentSnapshot).filter(CoachIntentSnapshot.athlete_id == athlete_id).first()
    return snap



def _is_snapshot_stale(snapshot, ttl_days: int = 7) -> bool:
    try:
        if not snapshot or not getattr(snapshot, "updated_at", None):
            return True
        cutoff = datetime.utcnow() - timedelta(days=int(ttl_days))
        # updated_at is tz-aware in DB; compare safely by casting to naive UTC if needed.
        updated = snapshot.updated_at
        if hasattr(updated, "replace") and getattr(updated, "tzinfo", None) is not None:
            updated = updated.replace(tzinfo=None)
        return updated < cutoff
    except Exception:
        return True



def get_coach_intent_snapshot(db: Session, athlete_id: UUID, ttl_days: int = 7) -> Dict[str, Any]:
    """
    Return the athlete's current intent snapshot (self-guided coaching state).
    """
    from services.timezone_utils import get_athlete_timezone_from_db, athlete_local_today
    _tz = get_athlete_timezone_from_db(db, athlete_id)
    _today = athlete_local_today(_tz)
    now = datetime.utcnow()
    try:
        snap = _get_intent_snapshot(db, athlete_id)
        stale = _is_snapshot_stale(snap, ttl_days=ttl_days)

        data = {
            "ttl_days": int(ttl_days),
            "is_stale": bool(stale),
            "snapshot": None,
        }

        if snap:
            data["snapshot"] = {
                "training_intent": snap.training_intent,
                "next_event_date": snap.next_event_date.isoformat() if snap.next_event_date else None,
                "next_event_type": snap.next_event_type,
                "pain_flag": snap.pain_flag,
                "time_available_min": snap.time_available_min,
                "weekly_mileage_target": float(snap.weekly_mileage_target) if snap.weekly_mileage_target is not None else None,
                "what_feels_off": snap.what_feels_off,
                "updated_at": _iso(snap.updated_at) if snap.updated_at else None,
            }

        # --- Narrative ---
        if snap:
            ci_parts: List[str] = ["Athlete intent:"]
            if snap.training_intent:
                ci_parts.append(f"Intent: {snap.training_intent}.")
            if snap.next_event_date:
                ci_parts.append(f"Next event: {snap.next_event_type or 'race'} on {snap.next_event_date.isoformat()}.")
            if snap.pain_flag:
                ci_parts.append(f"Pain flag: {snap.pain_flag}.")
            if snap.weekly_mileage_target is not None:
                ci_parts.append(f"Weekly mileage target: {float(snap.weekly_mileage_target):.0f}.")
            if snap.what_feels_off:
                ci_parts.append(f"What feels off: {snap.what_feels_off}.")
            if stale:
                ci_parts.append("(Snapshot is stale — may need refresh.)")
            ci_narrative = " ".join(ci_parts)
        else:
            ci_narrative = "No athlete intent snapshot set yet."

        return {
            "ok": True,
            "tool": "get_coach_intent_snapshot",
            "generated_at": _iso(now),
            "narrative": ci_narrative,
            "data": data,
            "evidence": [
                {
                    "type": "derived",
                    "id": f"coach_intent_snapshot:{str(athlete_id)}",
                    "date": _today.isoformat(),
                    "value": "Intent snapshot present" if snap else "No intent snapshot set yet",
                }
            ],
        }
    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        return {"ok": False, "tool": "get_coach_intent_snapshot", "error": str(e)}



def set_coach_intent_snapshot(
    db: Session,
    athlete_id: UUID,
    *,
    training_intent: Optional[str] = None,
    next_event_date: Optional[str] = None,
    next_event_type: Optional[str] = None,
    pain_flag: Optional[str] = None,
    time_available_min: Optional[int] = None,
    weekly_mileage_target: Optional[float] = None,
    what_feels_off: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Update the athlete's intent snapshot.

    NOTE: This is athlete-led state. It should be set from athlete responses.
    """
    datetime.utcnow()
    try:
        from models import CoachIntentSnapshot

        snap = _get_intent_snapshot(db, athlete_id)
        if not snap:
            snap = CoachIntentSnapshot(athlete_id=athlete_id)
            db.add(snap)

        if training_intent is not None:
            snap.training_intent = (training_intent or "").strip() or None

        if next_event_date is not None:
            try:
                snap.next_event_date = date.fromisoformat(next_event_date) if next_event_date else None
            except Exception:
                # Ignore invalid date; caller should validate.
                snap.next_event_date = None

        if next_event_type is not None:
            snap.next_event_type = (next_event_type or "").strip() or None

        if pain_flag is not None:
            snap.pain_flag = (pain_flag or "").strip().lower() or None

        if time_available_min is not None:
            try:
                snap.time_available_min = int(time_available_min)
            except Exception:
                snap.time_available_min = None

        if weekly_mileage_target is not None:
            try:
                snap.weekly_mileage_target = float(weekly_mileage_target)
            except Exception:
                snap.weekly_mileage_target = None

        if what_feels_off is not None:
            snap.what_feels_off = (what_feels_off or "").strip() or None

        db.commit()

        return get_coach_intent_snapshot(db, athlete_id)
    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        return {"ok": False, "tool": "set_coach_intent_snapshot", "error": str(e)}



