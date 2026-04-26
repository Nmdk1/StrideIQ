"""Cardiac Signature Extraction (Discovery Engine V2 — Layer 5).

Extracts intra-workout cardiovascular signals from per-second HR traces
combined with run_shape phase identification. These signals are invisible
to pre/post-session metrics.

Pure computation: takes activity data, returns a signature dict.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, asdict
from datetime import date as date_type, timedelta
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_WORK_PHASE_TYPES = frozenset({
    "interval_work", "threshold", "tempo", "hill_effort",
})

_RECOVERY_PHASE_TYPES = frozenset({
    "interval_recovery", "recovery_jog",
})


@dataclass
class IntervalSignature:
    interval_num: int
    avg_hr: float
    peak_hr: float
    recovery_60s: Optional[float]
    time_to_peak_hr_s: Optional[int]


@dataclass
class CardiacSignature:
    hr_recovery_60s_avg: Optional[float]
    hr_recovery_degradation: Optional[float]
    hr_drift_pct: Optional[float]
    peak_hr_response: Optional[float]
    intervals: List[IntervalSignature]

    def to_dict(self) -> dict:
        return {
            "hr_recovery_60s_avg": self.hr_recovery_60s_avg,
            "hr_recovery_degradation": self.hr_recovery_degradation,
            "hr_drift_pct": self.hr_drift_pct,
            "peak_hr_response": self.peak_hr_response,
            "intervals": [asdict(i) for i in self.intervals],
        }


def extract_cardiac_signature(
    hr_data: List[int],
    time_data: List[int],
    phases: List[Dict],
) -> Optional[CardiacSignature]:
    """Extract cardiac signature from HR stream and run_shape phases.

    Args:
        hr_data: Per-second heart rate values from ActivityStream.
        time_data: Corresponding elapsed time values (seconds).
        phases: List of phase dicts from Activity.run_shape["phases"].

    Returns:
        CardiacSignature or None if insufficient data.
    """
    if not hr_data or not time_data or not phases:
        return None

    if len(hr_data) < 60:
        return None

    hr_by_time = {}
    for t, hr in zip(time_data, hr_data):
        if hr and hr > 0:
            hr_by_time[t] = hr

    work_phases = [
        p for p in phases
        if p.get("phase_type") in _WORK_PHASE_TYPES
    ]

    if not work_phases:
        return None

    interval_sigs: List[IntervalSignature] = []
    recovery_60s_values: List[float] = []

    for idx, phase in enumerate(work_phases):
        start_t = phase.get("start_time_s", 0)
        end_t = phase.get("end_time_s", 0)
        if end_t <= start_t:
            continue

        phase_hrs = [
            hr_by_time[t] for t in range(start_t, end_t + 1)
            if t in hr_by_time
        ]
        if not phase_hrs:
            continue

        avg_hr = sum(phase_hrs) / len(phase_hrs)
        peak_hr = max(phase_hrs)

        peak_time = None
        for t in range(start_t, end_t + 1):
            if hr_by_time.get(t) == peak_hr:
                peak_time = t - start_t
                break

        recovery_60s = None
        hr_at_end = hr_by_time.get(end_t)
        if hr_at_end:
            hr_60_later = hr_by_time.get(end_t + 60)
            if hr_60_later:
                recovery_60s = float(hr_at_end - hr_60_later)
                recovery_60s_values.append(recovery_60s)

        interval_sigs.append(IntervalSignature(
            interval_num=idx + 1,
            avg_hr=round(avg_hr, 1),
            peak_hr=float(peak_hr),
            recovery_60s=round(recovery_60s, 1) if recovery_60s is not None else None,
            time_to_peak_hr_s=peak_time,
        ))

    if not interval_sigs:
        return None

    hr_recovery_60s_avg = None
    if recovery_60s_values:
        hr_recovery_60s_avg = round(sum(recovery_60s_values) / len(recovery_60s_values), 1)

    hr_recovery_degradation = None
    if len(recovery_60s_values) >= 2:
        hr_recovery_degradation = round(
            recovery_60s_values[0] - recovery_60s_values[-1], 1
        )

    hr_drift_pct = _compute_hr_drift(work_phases, hr_by_time)
    peak_hr_response = max(s.peak_hr for s in interval_sigs) if interval_sigs else None

    return CardiacSignature(
        hr_recovery_60s_avg=hr_recovery_60s_avg,
        hr_recovery_degradation=hr_recovery_degradation,
        hr_drift_pct=hr_drift_pct,
        peak_hr_response=peak_hr_response,
        intervals=interval_sigs,
    )


def _compute_hr_drift(
    work_phases: List[Dict],
    hr_by_time: Dict[int, int],
) -> Optional[float]:
    """For continuous threshold/tempo efforts, compute cardiac drift.

    (HR in last 20% - HR in first 20%) / HR in first 20% × 100
    """
    tempo_threshold = [
        p for p in work_phases
        if p.get("phase_type") in ("threshold", "tempo")
        and (p.get("end_time_s", 0) - p.get("start_time_s", 0)) >= 300
    ]

    if not tempo_threshold:
        return None

    longest = max(tempo_threshold, key=lambda p: p["end_time_s"] - p["start_time_s"])
    start_t = longest["start_time_s"]
    end_t = longest["end_time_s"]
    duration = end_t - start_t

    first_end = start_t + int(duration * 0.2)
    last_start = end_t - int(duration * 0.2)

    first_hrs = [hr_by_time[t] for t in range(start_t, first_end + 1) if t in hr_by_time]
    last_hrs = [hr_by_time[t] for t in range(last_start, end_t + 1) if t in hr_by_time]

    if not first_hrs or not last_hrs:
        return None

    first_avg = sum(first_hrs) / len(first_hrs)
    last_avg = sum(last_hrs) / len(last_hrs)

    if first_avg <= 0:
        return None

    return round((last_avg - first_avg) / first_avg * 100, 2)


def compute_cardiac_signature_for_activity(
    activity_id,
    db: Session,
) -> Optional[Dict]:
    """Load stream + shape data and extract cardiac signature.

    Returns the signature dict or None.
    """
    from models import Activity, ActivityStream

    activity = db.query(Activity).filter(Activity.id == activity_id).first()
    if not activity or activity.sport != "run":
        return None

    run_shape = activity.run_shape
    if not run_shape or not isinstance(run_shape, dict):
        return None

    phases = run_shape.get("phases", [])
    if not phases:
        return None

    stream = db.query(ActivityStream).filter(
        ActivityStream.activity_id == activity_id
    ).first()
    if not stream or not stream.stream_data:
        return None

    hr_data = stream.stream_data.get("heartrate", [])
    time_data = stream.stream_data.get("time", [])

    if not hr_data or not time_data:
        return None

    sig = extract_cardiac_signature(hr_data, time_data, phases)
    if not sig:
        return None

    return sig.to_dict()


def backfill_cardiac_signatures(
    athlete_id: str,
    db: Session,
    limit: int = 500,
) -> Dict:
    """Backfill cardiac signatures for existing activities with streams.

    Stores signatures in Activity.session_detail JSONB under
    'cardiac_signature' key to avoid schema migration.
    """
    from models import Activity, ActivityStream

    activities = (
        db.query(Activity)
        .join(ActivityStream, ActivityStream.activity_id == Activity.id)
        .filter(
            Activity.athlete_id == athlete_id,
            Activity.sport == "run",
            Activity.run_shape.isnot(None),
        )
        .order_by(Activity.start_time.desc())
        .limit(limit)
        .all()
    )

    computed = 0
    skipped = 0

    for activity in activities:
        existing = (activity.session_detail or {}).get("cardiac_signature")
        if existing:
            skipped += 1
            continue

        sig = compute_cardiac_signature_for_activity(activity.id, db)
        if sig:
            detail = activity.session_detail or {}
            detail["cardiac_signature"] = sig
            activity.session_detail = detail
            computed += 1
        else:
            skipped += 1

    if computed > 0:
        db.commit()

    return {"computed": computed, "skipped": skipped, "total": len(activities)}
