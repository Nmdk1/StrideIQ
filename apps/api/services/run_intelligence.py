"""
Run Intelligence Synthesis

Produces a coaching-quality summary for a single run by assembling
data from stream analysis, attribution, splits, classification,
pre-state, and historical comparison.

Deterministic — no LLM. Every sentence is grounded in specific data
from the athlete's own history.
"""

from dataclasses import dataclass, field
from datetime import timedelta
from typing import List, Dict, Optional, Any
import logging

from sqlalchemy.orm import Session

from models import Activity, ActivitySplit, CachedStreamAnalysis

logger = logging.getLogger(__name__)


@dataclass
class IntelligenceHighlight:
    label: str
    value: str
    color: str = "slate"


@dataclass
class RunIntelligenceResult:
    headline: str
    body: str
    highlights: List[IntelligenceHighlight] = field(default_factory=list)


def _fmt_pace_per_mile(seconds_per_km: float) -> str:
    spm = seconds_per_km * 1.60934
    mins = int(spm // 60)
    secs = int(spm % 60)
    return f"{mins}:{secs:02d}/mi"


def _fmt_pace_per_km(seconds_per_km: float) -> str:
    mins = int(seconds_per_km // 60)
    secs = int(seconds_per_km % 60)
    return f"{mins}:{secs:02d}/km"


def _fmt_duration(seconds: float) -> str:
    s = int(seconds)
    hrs = s // 3600
    mins = (s % 3600) // 60
    secs = s % 60
    if hrs > 0:
        return f"{hrs}:{mins:02d}:{secs:02d}"
    return f"{mins}:{secs:02d}"


def _fmt_distance_mi(meters: float) -> str:
    mi = meters / 1609.34
    if mi >= 10:
        return f"{mi:.1f}"
    return f"{mi:.1f}"


def _workout_label(wt: Optional[str]) -> str:
    if not wt:
        return "run"
    labels = {
        "easy_run": "easy run",
        "recovery": "recovery run",
        "long_run": "long run",
        "long_run_quality": "long run with quality",
        "tempo": "tempo",
        "interval": "interval session",
        "race": "race",
        "moderate": "moderate run",
        "pacing": "pacing effort",
    }
    return labels.get(wt.lower(), wt.lower().replace("_", " "))


def _is_interval_workout(activity: Activity) -> bool:
    wt = getattr(activity, "workout_type", None)
    if not wt:
        return False
    return wt.lower() in {"interval", "intervals", "track", "track_workout"}


def _get_interval_analysis(activity: Activity, db: Session) -> Optional[Dict[str, Any]]:
    """Analyze work intervals specifically: consistency, paces, HR response."""
    splits = (
        db.query(ActivitySplit)
        .filter(ActivitySplit.activity_id == activity.id)
        .order_by(ActivitySplit.split_number)
        .all()
    )

    work_splits = [
        s for s in splits
        if s.lap_type == "work"
        and s.distance and float(s.distance) > 0
        and s.elapsed_time and float(s.elapsed_time) > 0
    ]

    if len(work_splits) < 2:
        return None

    paces = [float(s.elapsed_time) / (float(s.distance) / 1000) for s in work_splits]
    avg_pace = sum(paces) / len(paces)
    distances = [float(s.distance) for s in work_splits]
    avg_dist = sum(distances) / len(distances)

    spreads = [(p - avg_pace) / avg_pace * 100 for p in paces]
    max_spread = max(abs(s) for s in spreads)
    slowest_idx = paces.index(max(paces))
    fastest_idx = paces.index(min(paces))

    hrs = [int(s.average_heartrate) for s in work_splits if s.average_heartrate]
    avg_hr = sum(hrs) / len(hrs) if hrs else None

    return {
        "type": "interval",
        "rep_count": len(work_splits),
        "avg_distance_m": round(avg_dist),
        "paces_s_km": paces,
        "avg_pace_s_km": avg_pace,
        "max_spread_pct": round(max_spread, 1),
        "slowest_rep": slowest_idx + 1,
        "fastest_rep": fastest_idx + 1,
        "avg_hr": avg_hr,
    }


def _get_split_pacing(activity: Activity, db: Session) -> Optional[Dict[str, Any]]:
    """Compute first-half / second-half pacing analysis from splits.
    Only used for continuous runs — intervals use _get_interval_analysis.
    """
    if _is_interval_workout(activity):
        return None

    splits = (
        db.query(ActivitySplit)
        .filter(ActivitySplit.activity_id == activity.id)
        .order_by(ActivitySplit.split_number)
        .all()
    )
    valid = [
        s for s in splits
        if s.distance and s.elapsed_time and float(s.elapsed_time) > 0
    ]
    if len(valid) < 3:
        return None

    paces = [float(s.elapsed_time) / (float(s.distance) / 1000) for s in valid]
    mid = len(paces) // 2
    first_avg = sum(paces[:mid]) / mid
    second_avg = sum(paces[mid:]) / (len(paces) - mid)
    decay_pct = ((second_avg - first_avg) / first_avg) * 100 if first_avg > 0 else 0

    return {
        "type": "continuous",
        "decay_pct": round(decay_pct, 1),
        "first_half_pace": first_avg,
        "second_half_pace": second_avg,
        "splits_count": len(valid),
    }


def _get_stream_drift(activity_id, db: Session) -> Optional[Dict[str, Any]]:
    """Get cardiac decoupling from cached stream analysis."""
    from services.stream_analysis_cache import CURRENT_ANALYSIS_VERSION

    row = (
        db.query(CachedStreamAnalysis.result_json)
        .filter(
            CachedStreamAnalysis.activity_id == activity_id,
            CachedStreamAnalysis.analysis_version == CURRENT_ANALYSIS_VERSION,
        )
        .first()
    )
    if not row or not row[0]:
        return None

    result = row[0]
    drift = result.get("drift")
    if not drift:
        return None

    return {
        "cardiac_pct": drift.get("cardiac_pct"),
        "pace_pct": drift.get("pace_pct"),
    }


def _get_efficiency_vs_peers(activity: Activity, db: Session) -> Optional[Dict[str, Any]]:
    """Compare efficiency against same workout-type runs in last 90 days."""
    if not activity.avg_hr or activity.avg_hr < 100:
        return None
    if not activity.distance_m or not activity.duration_s:
        return None
    if not activity.workout_type:
        return None

    speed_mps = activity.distance_m / activity.duration_s
    this_ef = speed_mps / float(activity.avg_hr)

    end_date = activity.start_time
    start_date = end_date - timedelta(days=90)

    peers = (
        db.query(Activity)
        .filter(
            Activity.athlete_id == activity.athlete_id,
            Activity.id != activity.id,
            Activity.avg_hr.isnot(None),
            Activity.avg_hr > 100,
            Activity.distance_m > 1000,
            Activity.duration_s > 0,
            Activity.start_time >= start_date,
            Activity.start_time < end_date,
            Activity.workout_type == activity.workout_type,
        )
        .all()
    )
    if len(peers) < 2:
        return None

    peer_efs = [
        (p.distance_m / p.duration_s) / float(p.avg_hr) for p in peers
    ]
    avg_ef = sum(peer_efs) / len(peer_efs)
    diff_pct = ((this_ef - avg_ef) / avg_ef) * 100 if avg_ef > 0 else 0

    return {
        "diff_pct": round(diff_pct, 1),
        "sample_size": len(peers),
        "label": activity.workout_type.lower().replace("_", " "),
    }


def _get_drift_history_avg(activity: Activity, db: Session) -> Optional[Dict[str, Any]]:
    """Average cardiac decoupling for recent controlled-steady runs."""
    from services.run_analysis_engine import CONTROLLED_STEADY_TYPES
    from services.stream_analysis_cache import CURRENT_ANALYSIS_VERSION

    wt = getattr(activity, "workout_type", None)
    if not wt or wt.lower() not in CONTROLLED_STEADY_TYPES:
        return None

    end_date = activity.start_time
    start_date = end_date - timedelta(days=90)

    rows = (
        db.query(CachedStreamAnalysis.result_json)
        .join(Activity, Activity.id == CachedStreamAnalysis.activity_id)
        .filter(
            Activity.athlete_id == activity.athlete_id,
            Activity.id != activity.id,
            Activity.start_time >= start_date,
            Activity.start_time < end_date,
            Activity.workout_type.in_(CONTROLLED_STEADY_TYPES),
            CachedStreamAnalysis.analysis_version == CURRENT_ANALYSIS_VERSION,
        )
        .all()
    )

    drifts = []
    for (rj,) in rows:
        d = rj.get("drift") if rj else None
        cp = d.get("cardiac_pct") if d else None
        if cp is not None:
            drifts.append(cp)

    if len(drifts) < 3:
        return None

    return {
        "avg_drift": round(sum(drifts) / len(drifts), 1),
        "count": len(drifts),
    }


def generate_run_intelligence(
    activity_id: str,
    athlete_id: str,
    db: Session,
) -> Optional[RunIntelligenceResult]:
    """
    Main entry point. Assembles all data sources and produces a coaching
    summary for a single run.
    """
    activity = (
        db.query(Activity)
        .filter(Activity.id == activity_id, Activity.athlete_id == athlete_id)
        .first()
    )
    if not activity:
        return None

    if not activity.distance_m or not activity.duration_s:
        return None

    try:
        return _assemble_intelligence(activity, db)
    except Exception:
        logger.exception("Failed to generate run intelligence for %s", activity_id)
        return None


def _assemble_intelligence(activity: Activity, db: Session) -> Optional[RunIntelligenceResult]:
    dist_mi = activity.distance_m / 1609.34
    pace_s_km = activity.duration_s / (activity.distance_m / 1000)
    pace_str = _fmt_pace_per_mile(pace_s_km)
    dist_str = _fmt_distance_mi(activity.distance_m)
    duration_str = _fmt_duration(activity.duration_s)
    wt_label = _workout_label(activity.workout_type)

    # Gather all available data
    drift = _get_stream_drift(activity.id, db)
    interval_data = _get_interval_analysis(activity, db) if _is_interval_workout(activity) else None
    pacing = _get_split_pacing(activity, db)
    efficiency = _get_efficiency_vs_peers(activity, db)
    drift_history = _get_drift_history_avg(activity, db)

    # --- Build headline ---
    headline = _build_headline(
        dist_str, pace_str, duration_str, wt_label, dist_mi, activity,
        interval_data,
    )

    # --- Build body sentences ---
    sentences: List[str] = []

    if interval_data:
        # Interval-specific: rep consistency and paces
        interval_sent = _interval_sentence(interval_data)
        if interval_sent:
            sentences.append(interval_sent)
    else:
        # Continuous run: half-half pacing
        pacing_sent = _pacing_sentence(pacing)
        if pacing_sent:
            sentences.append(pacing_sent)

    # 2. Cardiac coupling / drift sentence (controlled-steady only)
    coupling_sent = _coupling_sentence(drift, drift_history, activity)
    if coupling_sent:
        sentences.append(coupling_sent)

    # 3. Efficiency sentence (non-controlled-steady only)
    eff_sent = _efficiency_sentence(efficiency, activity)
    if eff_sent:
        sentences.append(eff_sent)

    # 4. Pre-state sentence
    pre_sent = _prestate_sentence(activity)
    if pre_sent:
        sentences.append(pre_sent)

    # 5. Conditions sentence
    cond_sent = _conditions_sentence(activity)
    if cond_sent:
        sentences.append(cond_sent)

    body = " ".join(sentences) if sentences else ""

    # --- Highlights ---
    highlights = _build_highlights(activity, drift, pacing, efficiency, interval_data)

    if not body and not highlights:
        return None

    return RunIntelligenceResult(
        headline=headline,
        body=body,
        highlights=highlights,
    )


# ── Sentence builders ──────────────────────────────────────────────────


def _build_headline(
    dist_str: str,
    pace_str: str,
    duration_str: str,
    wt_label: str,
    dist_mi: float,
    activity: Activity,
    interval_data: Optional[Dict] = None,
) -> str:
    """One-line opening: distance, pace, and what kind of run."""
    is_race = getattr(activity, "is_race_candidate", False) or (
        activity.workout_type and activity.workout_type.lower() == "race"
    )

    if interval_data:
        n = interval_data["rep_count"]
        avg_dist = interval_data["avg_distance_m"]
        avg_pace = _fmt_pace_per_mile(interval_data["avg_pace_s_km"])
        return f"{n}x{avg_dist}m at {avg_pace} avg — {wt_label}."

    if is_race and dist_mi >= 13.0:
        return f"{dist_str} mi in {duration_str} — {wt_label}."
    return f"{dist_str} mi at {pace_str} — {wt_label}."


def _interval_sentence(interval_data: Optional[Dict]) -> Optional[str]:
    """Describe interval rep consistency — the metric that matters for quality work."""
    if not interval_data:
        return None

    n = interval_data["rep_count"]
    spread = interval_data["max_spread_pct"]
    slowest = interval_data["slowest_rep"]
    paces = interval_data["paces_s_km"]

    pace_strs = [_fmt_pace_per_mile(p) for p in paces]
    pace_list = ", ".join(pace_strs)

    if spread <= 2.0:
        consistency = f"Very consistent across {n} reps (max {spread:.1f}% spread)."
    elif spread <= 5.0:
        consistency = f"Consistent across {n} reps ({spread:.1f}% max spread)."
    elif spread <= 10.0:
        consistency = f"Some variation across {n} reps — rep {slowest} was the slowest ({spread:.1f}% off avg)."
    else:
        consistency = f"Wide variation — rep {slowest} was {spread:.1f}% off the average."

    return f"Reps: {pace_list}. {consistency}"


def _pacing_sentence(pacing: Optional[Dict]) -> Optional[str]:
    if not pacing:
        return None
    d = pacing.get("decay_pct", 0)
    if d < -2:
        return f"Negative split — second half {abs(d):.1f}% faster."
    elif d <= 2:
        return "Even pacing throughout."
    elif d <= 5:
        return f"Slight fade in the second half ({d:.1f}% slower)."
    elif d <= 8:
        return f"Moderate pace fade ({d:.1f}%) — started faster than you finished."
    else:
        return f"Significant fade ({d:.1f}%) — may have gone out too fast."


def _coupling_sentence(
    drift: Optional[Dict],
    drift_history: Optional[Dict],
    activity: Activity,
) -> Optional[str]:
    from services.run_analysis_engine import CONTROLLED_STEADY_TYPES

    wt = getattr(activity, "workout_type", None)
    if not wt or wt.lower() not in CONTROLLED_STEADY_TYPES:
        return None
    if not drift or drift.get("cardiac_pct") is None:
        return None

    cp = drift["cardiac_pct"]
    abs_cp = abs(cp)

    if abs_cp <= 3:
        base = f"HR stayed stable relative to pace ({cp:+.1f}% drift) — aerobically controlled."
    elif abs_cp <= 5:
        base = f"Normal cardiac drift ({cp:+.1f}%) for this effort length."
    elif abs_cp <= 8:
        base = f"Moderate HR drift ({cp:+.1f}%) — body worked harder to hold pace over the distance."
    else:
        base = f"Significant HR drift ({cp:+.1f}%) — cardiovascular demand rose progressively."

    if drift_history:
        avg = drift_history["avg_drift"]
        n = drift_history["count"]
        diff = cp - avg
        if diff < -1.5:
            base += f" Coupling is tightening — your last {n} similar runs averaged {avg:.1f}%."
        elif diff > 1.5:
            base += f" Higher than your recent average of {avg:.1f}% over {n} runs."

    return base


def _efficiency_sentence(
    efficiency: Optional[Dict],
    activity: Activity,
) -> Optional[str]:
    from services.run_analysis_engine import CONTROLLED_STEADY_TYPES

    wt = getattr(activity, "workout_type", None)
    if wt and wt.lower() in CONTROLLED_STEADY_TYPES:
        return None
    if not efficiency:
        return None

    d = efficiency["diff_pct"]
    n = efficiency["sample_size"]
    label = efficiency["label"]

    if d > 5:
        return f"Efficiency {d:.1f}% above your recent {label}s ({n} runs)."
    elif d > 2:
        return f"Slightly more efficient than your recent {label}s (+{d:.1f}%)."
    elif d >= -2:
        return f"Efficiency in line with your recent {label}s."
    elif d >= -5:
        return f"Efficiency {abs(d):.1f}% below your recent {label}s."
    else:
        return f"Efficiency notably below your recent {label}s ({d:.1f}%)."


def _prestate_sentence(activity: Activity) -> Optional[str]:
    parts = []
    sleep = getattr(activity, "pre_sleep_h", None)
    if sleep is not None:
        parts.append(f"{float(sleep):.1f}h sleep")

    rhr = getattr(activity, "pre_resting_hr", None)
    if rhr is not None:
        parts.append(f"resting HR {int(rhr)}")

    hrv = getattr(activity, "pre_recovery_hrv", None)
    if hrv is not None:
        parts.append(f"HRV {int(hrv)}")

    if not parts:
        return None

    return "Going in on " + ", ".join(parts) + "."


def _conditions_sentence(activity: Activity) -> Optional[str]:
    heat = getattr(activity, "heat_adjustment_pct", None)
    temp = getattr(activity, "temperature_f", None)

    if heat and heat > 3 and temp:
        return f"Heat ({int(temp)}°F) slowed this effort ~{heat:.0f}% — real effort was better than the pace."

    elev = getattr(activity, "total_elevation_gain", None)
    elev = float(elev) if elev is not None else None
    if elev and elev > 100:
        ft = int(elev * 3.28084)
        return f"{ft:,}ft of climbing."

    return None


# ── Highlights ──────────────────────────────────────────────────────────


def _build_highlights(
    activity: Activity,
    drift: Optional[Dict],
    pacing: Optional[Dict],
    efficiency: Optional[Dict],
    interval_data: Optional[Dict] = None,
) -> List[IntelligenceHighlight]:
    hl: List[IntelligenceHighlight] = []

    if interval_data:
        spread = interval_data["max_spread_pct"]
        color = "emerald" if spread <= 2 else "green" if spread <= 5 else "yellow" if spread <= 10 else "orange"
        hl.append(IntelligenceHighlight(
            label="Rep Consistency", value=f"{spread:.1f}% spread", color=color
        ))
        hl.append(IntelligenceHighlight(
            label="Reps", value=str(interval_data["rep_count"])
        ))
        if interval_data.get("avg_hr"):
            hl.append(IntelligenceHighlight(
                label="Avg HR (work)", value=f"{int(interval_data['avg_hr'])} bpm"
            ))
    else:
        if activity.avg_hr:
            hl.append(IntelligenceHighlight(
                label="Avg HR", value=f"{int(activity.avg_hr)} bpm"
            ))

    if drift and drift.get("cardiac_pct") is not None:
        cp = drift["cardiac_pct"]
        color = "emerald" if abs(cp) <= 3 else "yellow" if abs(cp) <= 5 else "orange"
        hl.append(IntelligenceHighlight(
            label="Cardiac Drift", value=f"{cp:+.1f}%", color=color
        ))

    if pacing and pacing.get("decay_pct") is not None:
        d = pacing["decay_pct"]
        color = "emerald" if d < -1 else "green" if d <= 3 else "yellow" if d <= 6 else "orange"
        hl.append(IntelligenceHighlight(
            label="Pacing", value=f"{d:+.1f}%", color=color
        ))

    if efficiency:
        d = efficiency["diff_pct"]
        color = "emerald" if d > 3 else "green" if d > 0 else "yellow" if d > -3 else "orange"
        hl.append(IntelligenceHighlight(
            label="Efficiency", value=f"{d:+.1f}% vs recent", color=color
        ))

    elev = getattr(activity, "total_elevation_gain", None)
    if elev and float(elev) > 30:
        ft = int(float(elev) * 3.28084)
        hl.append(IntelligenceHighlight(
            label="Elevation", value=f"{ft:,}ft"
        ))

    return hl
