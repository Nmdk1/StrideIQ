from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, date
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import func

logger = logging.getLogger(__name__)

from models import Activity, Athlete
from core.date_utils import calculate_age
from services.correlation_engine import analyze_correlations
from services.insight_aggregator import get_active_insights as fetch_insights, generate_insights_for_athlete
from services.coach_tools._utils import (
    _iso, _relative_date, _preferred_units,
)


def get_correlations(db: Session, athlete_id: UUID, days: int = 30) -> Dict[str, Any]:
    """
    Correlation insights (what seems to be working / not working).
    """
    now = datetime.utcnow()
    days = max(14, min(int(days), 365))

    result = analyze_correlations(athlete_id=str(athlete_id), days=days, db=db)

    top = None
    correlations = result.get("correlations") if isinstance(result, dict) else None
    if isinstance(correlations, list) and correlations:
        top = correlations[0]

    top_value = "No significant correlations found" if not top else (
        f"{top.get('input_name')} r={top.get('correlation_coefficient')} p={top.get('p_value')} "
        f"(lag {top.get('time_lag_days')}d, n={top.get('sample_size')})"
    )

    # --- Narrative ---
    corr_list = result.get("correlations") if isinstance(result, dict) else None
    if isinstance(corr_list, list) and corr_list:
        narr_items: List[str] = []
        for c in corr_list[:3]:
            inp = c.get("input_name", "?")
            out = c.get("output_name", "?")
            r = c.get("correlation_coefficient")
            lag = c.get("time_lag_days", 0)
            interp = c.get("interpretation", "")
            r_str = f"r={r:.2f}" if r is not None else "r=?"
            narr_items.append(f"{inp} → {out} ({r_str}, lag {lag}d): {interp}")
        narrative = f"Top correlations over {days} days: " + " | ".join(narr_items)
    else:
        narrative = f"No significant correlations found over the last {days} days."

    return {
        "ok": True,
        "tool": "get_correlations",
        "generated_at": _iso(now),
        "narrative": narrative,
        "data": result,
        "evidence": [
            {
                "type": "derived",
                "id": f"correlations:{str(athlete_id)}:{days}d",
                "date": (result.get("analysis_period") or {}).get("end", _iso(now))[:10] if isinstance(result, dict) else _iso(now)[:10],
                "value": top_value,
                # Back-compat keys
                "metric_set": "correlations",
                "analysis_period": result.get("analysis_period"),
                "source": "correlation_engine.analyze_correlations",
            }
        ],
    }



def get_active_insights(db: Session, athlete_id: UUID, limit: int = 5) -> Dict[str, Any]:
    """
    Prioritized actionable insights.
    """
    from services.timezone_utils import get_athlete_timezone_from_db, athlete_local_today
    _tz = get_athlete_timezone_from_db(db, athlete_id)
    _today = athlete_local_today(_tz)
    now = datetime.utcnow()
    try:
        limit = max(1, min(int(limit), 10))
        try:
            insights = fetch_insights(db, athlete_id, limit=limit)
            source = "calendar_insight"
        except Exception:
            # Fallback: if persisted insights are unavailable (e.g., table not present in env),
            # generate fresh insights without persisting.
            try:
                db.rollback()
            except Exception:
                pass
            athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
            if not athlete:
                raise
            generated = generate_insights_for_athlete(db=db, athlete=athlete, persist=False)
            generated = sorted(generated or [], key=lambda i: getattr(i, "priority", 0), reverse=True)[:limit]
            insights = generated
            source = "generated"

        insight_rows: List[Dict[str, Any]] = []
        evidence: List[Dict[str, Any]] = []

        for ins in insights or []:
            is_calendar = source == "calendar_insight"
            insight_type = getattr(ins, "insight_type", None)
            if hasattr(insight_type, "value"):
                insight_type = insight_type.value
            message = getattr(ins, "content", None) if is_calendar else getattr(ins, "content", None)

            insight_rows.append(
                {
                    "source": source,
                    "insight_id": str(getattr(ins, "id", "")) if getattr(ins, "id", None) else None,
                    "date": (getattr(ins, "insight_date", None) or _today).isoformat()
                    if getattr(ins, "insight_date", None) or not is_calendar
                    else None,
                    "type": insight_type,
                    "priority": getattr(ins, "priority", None),
                    "title": getattr(ins, "title", None),
                    "message": message,
                    "activity_id": str(getattr(ins, "activity_id", "")) if getattr(ins, "activity_id", None) else None,
                    "generation_data": getattr(ins, "generation_data", None) if is_calendar else getattr(ins, "data", None),
                    "confidence": getattr(ins, "confidence", None) if not is_calendar else None,
                }
            )

            evidence.append(
                {
                    "type": "calendar_insight" if source == "calendar_insight" else "generated_insight",
                    "id": str(getattr(ins, "id", "")) if getattr(ins, "id", None) else None,
                    "date": (getattr(ins, "insight_date", None) or _today).isoformat(),
                    "value": getattr(ins, "title", None) or "insight",
                }
            )

        # --- Narrative ---
        if insight_rows:
            ai_parts: List[str] = [f"{len(insight_rows)} insight(s) available:"]
            for ir in insight_rows[:3]:
                title = ir.get("title") or ir.get("message") or "Insight"
                ai_parts.append(f"• {title}")
            ai_narrative = " ".join(ai_parts)
        else:
            ai_narrative = "No active insights at this time."

        return {
            "ok": True,
            "tool": "get_active_insights",
            "generated_at": _iso(now),
            "narrative": ai_narrative,
            "data": {
                "insight_count": len(insight_rows),
                "insights": insight_rows,
            },
            "evidence": evidence,
        }
    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        return {"ok": False, "tool": "get_active_insights", "error": str(e)}



