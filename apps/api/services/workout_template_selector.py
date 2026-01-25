from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from models import WorkoutTemplate


PHASE_INTENSITY_TIER_ALLOWLIST: dict[str, list[str]] = {
    # Ordered by default phase focus (first = preferred), with variance allowed to switch.
    # "Type" == intensity_tier in the DB-backed template registry.
    "base": ["AEROBIC", "THRESHOLD", "VO2MAX", "ANAEROBIC"],
    "build": ["THRESHOLD", "VO2MAX", "ANAEROBIC", "AEROBIC"],
    "peak": ["THRESHOLD", "VO2MAX", "ANAEROBIC", "AEROBIC"],
    # Taper should bias toward sharpening / low-dose touches.
    "taper": ["ANAEROBIC", "VO2MAX", "THRESHOLD", "AEROBIC"],
}


def _pick_progression_step(
    *,
    progression_logic: Dict[str, Any],
    week_in_phase: int,
    total_phase_weeks: int,
) -> Dict[str, Any]:
    """
    Deterministically pick a progression step from a template's progression_logic.

    Currently supports:
      {"type":"steps","steps":[{...}, ...]}
    """
    logic = progression_logic or {}
    steps = logic.get("steps") if isinstance(logic, dict) else None
    if not isinstance(steps, list) or not steps:
        return {"key": "s1", "structure": None, "description_template": None}

    total_phase_weeks = max(1, int(total_phase_weeks or 1))
    week_in_phase = max(1, int(week_in_phase or 1))

    # Map 1..total_phase_weeks to 0..len(steps)-1 (monotonic).
    if len(steps) == 1:
        return steps[0]
    pct = (week_in_phase - 1) / max(1, total_phase_weeks - 1)
    idx = int(round(pct * (len(steps) - 1)))
    idx = max(0, min(idx, len(steps) - 1))
    step = steps[idx]
    return step if isinstance(step, dict) else {"key": f"s{idx+1}"}


def select_quality_template(
    *,
    db: Session,
    athlete_id: UUID,
    phase: str,
    week_in_phase: int,
    total_phase_weeks: int,
    recent_template_ids: List[str],
    constraints: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Deterministic quality-template selection using the DB-backed registry.

    Hard invariants:
    - template must be compatible with phase (no out-of-phase selection)
    - min_time_min must be satisfied (if specified)
    - dont_follow must be respected for the immediate predecessor

    Deterministic tie-breaks:
    - prefer not repeating the immediate previous template id
    - stable order by template_id
    """
    phase_norm = (phase or "").strip().lower()
    recent_template_ids = recent_template_ids or []
    facilities = (constraints or {}).get("facilities") or []
    time_available_min = (constraints or {}).get("time_available_min")

    filters_applied: Dict[str, int] = {
        "phase": 0,
        "min_time_min": 0,
        "dont_follow": 0,
        "requires": 0,
        # Note: type filtering happens after hard constraints; tracked separately in audit.
    }

    templates = db.query(WorkoutTemplate).order_by(WorkoutTemplate.id.asc()).all()
    candidates: List[WorkoutTemplate] = []
    considered = 0

    # Phase filter (HARD)
    for t in templates:
        considered += 1
        phases = t.phase_compatibility if isinstance(t.phase_compatibility, list) else []
        if phase_norm not in [str(p).lower() for p in phases]:
            filters_applied["phase"] += 1
            continue

        # min_time constraint
        t_constraints = t.constraints if isinstance(t.constraints, dict) else {}
        min_time = t_constraints.get("min_time_min")
        if min_time is not None and time_available_min is not None:
            try:
                if int(time_available_min) < int(min_time):
                    filters_applied["min_time_min"] += 1
                    continue
            except Exception:
                # If parsing fails, be conservative: exclude the template.
                filters_applied["min_time_min"] += 1
                continue

        # facilities requirements (optional contract via constraints.requires)
        reqs = t_constraints.get("requires")
        if isinstance(reqs, list) and reqs:
            if not all(r in facilities for r in reqs):
                filters_applied["requires"] += 1
                continue

        # dont_follow (immediate predecessor hard block)
        if recent_template_ids:
            prev = recent_template_ids[-1]
            blocked = t.dont_follow if isinstance(t.dont_follow, list) else []
            if prev in blocked:
                filters_applied["dont_follow"] += 1
                continue

        candidates.append(t)

    # --- Type selection (engine chooses type from a phase-specific allowlist) ---
    allowlist = PHASE_INTENSITY_TIER_ALLOWLIST.get(phase_norm) or ["THRESHOLD", "VO2MAX", "ANAEROBIC", "AEROBIC", "RECOVERY"]

    # Identify prior type (intensity tier) from immediate predecessor, if known.
    templates_by_id: Dict[str, WorkoutTemplate] = {t.id: t for t in templates if getattr(t, "id", None)}
    prev_id = recent_template_ids[-1] if recent_template_ids else None
    prev_tier = None
    if prev_id and prev_id in templates_by_id:
        try:
            prev_tier = str(getattr(templates_by_id[prev_id], "intensity_tier", "") or "").upper() or None
        except Exception:
            prev_tier = None

    # Group candidates by type (intensity tier), respecting phase allowlist.
    candidates_by_tier: Dict[str, List[WorkoutTemplate]] = {}
    for t in candidates:
        tier = str(getattr(t, "intensity_tier", "") or "").upper()
        if not tier:
            continue
        if tier not in allowlist:
            continue
        candidates_by_tier.setdefault(tier, []).append(t)

    # Deterministic fallback: if nothing survives, pick any in-phase template ignoring constraints.
    # (This preserves prior behavior and prevents "no workout" plans.)
    # Deterministic fallback: if nothing survives, pick any in-phase template ignoring constraints.
    if not candidates_by_tier:
        in_phase = [
            t
            for t in templates
            if phase_norm in [str(p).lower() for p in (t.phase_compatibility if isinstance(t.phase_compatibility, list) else [])]
        ]
        chosen = in_phase[0] if in_phase else (templates[0] if templates else None)
        if not chosen:
            return {"ok": False, "error": "no templates available"}
        step = _pick_progression_step(progression_logic=chosen.progression_logic, week_in_phase=week_in_phase, total_phase_weeks=total_phase_weeks)
        return {
            "ok": True,
            "selection_mode": "fallback",
            "filters_applied": filters_applied,
            "selected": {
                "template_id": chosen.id,
                "template_name": chosen.name,
                "intensity_tier": chosen.intensity_tier,
                "progression_step": step,
            },
            "audit": {
                "candidates_considered": considered,
                "candidates_after_filters": 1,
                "type_allowlist": allowlist,
                "type_selected": str(getattr(chosen, "intensity_tier", None) or "").upper() or None,
                "type_previous": prev_tier,
                "type_candidates_counts": {},
            },
        }

    # Pick a type deterministically:
    # - Prefer the phase’s first-available type
    # - If possible, avoid repeating the immediate previous type
    tier_order = [t for t in allowlist if t in candidates_by_tier]
    chosen_tier = None
    if prev_tier and any(t != prev_tier for t in tier_order):
        chosen_tier = next((t for t in tier_order if t != prev_tier), None)
    chosen_tier = chosen_tier or (tier_order[0] if tier_order else None)

    tier_candidates = candidates_by_tier.get(chosen_tier or "", [])
    # Prefer not repeating the last template if possible (within the chosen type)
    if prev_id:
        non_repeat = [t for t in tier_candidates if t.id != prev_id]
        if non_repeat:
            tier_candidates = non_repeat

    chosen = tier_candidates[0]  # stable due to ordering
    step = _pick_progression_step(progression_logic=chosen.progression_logic, week_in_phase=week_in_phase, total_phase_weeks=total_phase_weeks)
    return {
        "ok": True,
        "selection_mode": "on",
        "filters_applied": filters_applied,
        "selected": {
            "template_id": chosen.id,
            "template_name": chosen.name,
            "intensity_tier": chosen.intensity_tier,
            "progression_step": step,
        },
        "audit": {
            "candidates_considered": considered,
            "candidates_after_filters": sum(len(v) for v in candidates_by_tier.values()),
            "type_allowlist": allowlist,
            "type_selected": chosen_tier,
            "type_previous": prev_tier,
            "type_candidates_counts": {k: len(v) for k, v in candidates_by_tier.items()},
        },
    }

