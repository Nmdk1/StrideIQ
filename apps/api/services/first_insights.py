"""
First-Session Insights — surfaces the most impactful findings for
a new athlete whose backfill has completed.

This is the "aha moment": the first time the system speaks about
what it found in the athlete's history.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from services.fingerprint_context import COACHING_LANGUAGE

logger = logging.getLogger(__name__)


def _translate(field_name: str) -> str:
    if field_name in COACHING_LANGUAGE:
        return COACHING_LANGUAGE[field_name]
    return field_name.replace("_", " ")


def get_first_insights(athlete_id: UUID, db: Session) -> Optional[Dict[str, Any]]:
    """Return the top findings for first-session reveal.

    Returns None if there is not enough data to show a meaningful
    first-session experience (< 3 active findings).
    """
    from models import (
        CorrelationFinding as CF,
        AthleteFinding as AF,
        Activity,
    )

    activity_count = (
        db.query(Activity.id)
        .filter(Activity.athlete_id == athlete_id)
        .count()
    )

    if activity_count < 5:
        return None

    correlation_findings = (
        db.query(CF)
        .filter(
            CF.athlete_id == athlete_id,
            CF.is_active.is_(True),
            CF.times_confirmed >= 1,
        )
        .order_by(
            (CF.times_confirmed * CF.confidence).desc()
        )
        .limit(20)
        .all()
    )

    investigation_findings = (
        db.query(AF)
        .filter(
            AF.athlete_id == athlete_id,
            AF.is_active.is_(True),
        )
        .order_by(AF.last_confirmed_at.desc())
        .limit(10)
        .all()
    )

    if len(correlation_findings) < 2 and len(investigation_findings) < 1:
        return None

    top_correlations = []
    seen_inputs = set()
    for f in correlation_findings:
        if f.input_name in seen_inputs:
            continue
        seen_inputs.add(f.input_name)
        top_correlations.append({
            "headline": f.insight_text or f"{_translate(f.input_name)} affects {_translate(f.output_metric)}",
            "input": _translate(f.input_name),
            "output": _translate(f.output_metric),
            "direction": f.direction,
            "r": round(f.correlation_coefficient, 2),
            "times_confirmed": f.times_confirmed,
            "strength": f.strength,
            "threshold_label": (
                f"cliff at {f.threshold_value:.1f}"
                if f.threshold_value is not None else None
            ),
            "asymmetry_label": (
                f"{f.asymmetry_ratio:.1f}x asymmetry"
                if f.asymmetry_ratio is not None else None
            ),
        })
        if len(top_correlations) >= 3:
            break

    top_investigations = []
    for af in investigation_findings:
        top_investigations.append({
            "headline": af.sentence,
            "type": af.finding_type,
            "confidence": af.confidence,
        })
        if len(top_investigations) >= 2:
            break

    first_activity = (
        db.query(Activity.start_date)
        .filter(Activity.athlete_id == athlete_id)
        .order_by(Activity.start_date.asc())
        .first()
    )

    history_span_days = 0
    if first_activity and first_activity[0]:
        now = datetime.now(timezone.utc)
        dt = first_activity[0]
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        history_span_days = max(0, (now - dt).days)

    return {
        "ready": True,
        "activity_count": activity_count,
        "history_span_days": history_span_days,
        "correlation_count": len(correlation_findings),
        "investigation_count": len(investigation_findings),
        "top_correlations": top_correlations,
        "top_investigations": top_investigations,
    }
