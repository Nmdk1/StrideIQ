"""Phase 3B/3C eligibility service.

Determines whether an athlete qualifies for:
- 3B: Contextual workout narratives (premium only)
- 3C: N=1 personalized insights (guided + premium)

FOUNDER RULE: Do NOT require 3 months in production if the athlete already
has sufficient synced history at first sync.  Gate is:
  (production-time sufficiency) OR (historical-sync sufficiency)
plus quality/statistics safeguards.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Minimum thresholds for "history sufficiency"
MIN_HISTORY_SPAN_DAYS = 90
MIN_TOTAL_RUNS = 60

# Narration quality gate (global): 90% accuracy over 4 weeks
NARRATION_QUALITY_GATE = 0.90
NARRATION_QUALITY_WINDOW_DAYS = 28

# Tiers that qualify for each feature.
# Must stay aligned with the router tier checks in routers/insights.py.
TIERS_3B = {"premium"}
TIERS_3C = {"guided", "premium", "elite", "pro"}

# Kill-switch env var (also checked via FeatureFlag table)
KILL_SWITCH_3B_ENV = "STRIDEIQ_3B_KILL_SWITCH"
KILL_SWITCH_3C_ENV = "STRIDEIQ_3C_KILL_SWITCH"


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class EligibilityResult:
    eligible: bool
    reason: str
    evidence: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    provisional: bool = False


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _is_kill_switched(key: str, db: Session) -> bool:
    """Check env var AND FeatureFlag table."""
    if os.getenv(key, "").lower() in ("1", "true", "yes"):
        return True
    try:
        from models import FeatureFlag
        flag = db.query(FeatureFlag).filter(FeatureFlag.key == key).first()
        if flag and not flag.enabled:
            return True
    except Exception:
        pass
    return False


def _get_athlete(athlete_id: UUID, db: Session):
    """Load the Athlete row."""
    from models import Athlete
    return db.query(Athlete).filter(Athlete.id == athlete_id).first()


def _history_stats(athlete_id: UUID, db: Session) -> Dict[str, Any]:
    """Return summary of *synced* (provider-backed) activity history.

    Only counts activities that came from a connected provider (Strava, Garmin,
    etc.) — not manual entries.  This ensures the statistical foundation for
    3B/3C is real device-recorded data, not thin manual backfill.

    The Activity model has:
      - source: "manual" (default) | "strava" | "garmin" | etc.
      - provider: column mirroring the ingestion provider key.
    A run counts as "synced" if source != 'manual' OR provider is set.
    """
    from models import Activity
    from sqlalchemy import or_

    synced_filter = or_(
        Activity.source != "manual",
        Activity.provider.isnot(None),
    )

    q = db.query(Activity).filter(
        Activity.athlete_id == athlete_id,
        Activity.sport == "run",
        synced_filter,
    )
    total_runs = q.count()
    if total_runs == 0:
        return {"total_runs": 0, "history_span_days": 0,
                "earliest": None, "latest": None, "synced": True}
    dates = db.query(
        func.min(Activity.start_time),
        func.max(Activity.start_time),
    ).filter(
        Activity.athlete_id == athlete_id,
        Activity.sport == "run",
        synced_filter,
    ).one()
    earliest, latest = dates
    span = (latest.date() - earliest.date()).days if earliest and latest else 0
    return {
        "total_runs": total_runs,
        "history_span_days": span,
        "earliest": earliest.isoformat() if earliest else None,
        "latest": latest.isoformat() if latest else None,
        "synced": True,
    }


def _narration_quality_score(db: Session, window_days: int = NARRATION_QUALITY_WINDOW_DAYS) -> Optional[float]:
    """Global narration accuracy over the window.  Returns None if no data."""
    from models import NarrationLog
    cutoff = date.today() - timedelta(days=window_days)
    rows = (
        db.query(NarrationLog.score)
        .filter(
            NarrationLog.trigger_date >= cutoff,
            NarrationLog.score.isnot(None),
            NarrationLog.suppressed.is_(False),
        )
        .all()
    )
    if not rows:
        return None
    return sum(r.score for r in rows) / len(rows)


def _has_planned_workout(athlete_id: UUID, target_date: date, db: Session) -> bool:
    from models import PlannedWorkout
    return db.query(PlannedWorkout).filter(
        PlannedWorkout.athlete_id == athlete_id,
        PlannedWorkout.scheduled_date == target_date,
    ).first() is not None


# ---------------------------------------------------------------------------
# 3B eligibility
# ---------------------------------------------------------------------------

def get_3b_eligibility(
    athlete_id: UUID,
    db: Session,
    as_of: Optional[date] = None,
) -> EligibilityResult:
    """Determine if athlete qualifies for Phase 3B workout narratives.

    Rules (all must pass):
    1. Tier gate: premium only.
    2. Global kill switch respected.
    3. Athlete context sufficiency:
       - history_span_days >= 90 OR total_runs >= 60
       - planned workout exists for target day
    4. Narration safety remains enforced per-narrative by scorer/suppression.
    5. 4-week global >90% gate remains preferred, but athlete-level history
       sufficiency allows provisional unlock.
    """
    if as_of is None:
        as_of = date.today()

    # Kill switch
    if _is_kill_switched(KILL_SWITCH_3B_ENV, db):
        return EligibilityResult(
            eligible=False,
            reason="3B workout narratives are globally disabled (kill switch).",
            evidence={"kill_switch": True},
        )

    # Tier gate
    athlete = _get_athlete(athlete_id, db)
    if athlete is None:
        return EligibilityResult(
            eligible=False,
            reason="Athlete not found.",
            evidence={"athlete_id": str(athlete_id)},
        )
    if athlete.subscription_tier not in TIERS_3B:
        return EligibilityResult(
            eligible=False,
            reason=f"Workout narratives require premium tier. Current: {athlete.subscription_tier}.",
            evidence={"tier": athlete.subscription_tier, "required": sorted(TIERS_3B)},
        )

    # History sufficiency
    stats = _history_stats(athlete_id, db)
    has_history = (
        stats["history_span_days"] >= MIN_HISTORY_SPAN_DAYS
        or stats["total_runs"] >= MIN_TOTAL_RUNS
    )
    if not has_history:
        return EligibilityResult(
            eligible=False,
            reason=(
                f"Insufficient training history. Need {MIN_HISTORY_SPAN_DAYS}+ days "
                f"or {MIN_TOTAL_RUNS}+ runs. "
                f"Have {stats['history_span_days']} days, {stats['total_runs']} runs."
            ),
            evidence=stats,
        )

    # Planned workout for target day
    if not _has_planned_workout(athlete_id, as_of, db):
        return EligibilityResult(
            eligible=False,
            reason="No planned workout for target date.",
            evidence={"target_date": as_of.isoformat(), **stats},
        )

    # Narration quality gate: prefer global >90% for 4 weeks.
    # If the gate hasn't been met globally yet, allow provisional access
    # for athletes with sufficient history — per-narrative safety still
    # enforced by the scorer/suppression pipeline.
    quality = _narration_quality_score(db)
    provisional = False
    if quality is None or quality < NARRATION_QUALITY_GATE:
        provisional = True

    confidence = min(1.0, stats["total_runs"] / 100) * (quality if quality else 0.7)

    return EligibilityResult(
        eligible=True,
        reason="Eligible for workout narratives.",
        evidence={
            **stats,
            "narration_quality": quality,
            "provisional": provisional,
        },
        confidence=round(confidence, 3),
        provisional=provisional,
    )


# ---------------------------------------------------------------------------
# 3C eligibility
# ---------------------------------------------------------------------------

def get_3c_eligibility(
    athlete_id: UUID,
    db: Session,
    as_of: Optional[date] = None,
) -> EligibilityResult:
    """Determine if athlete qualifies for Phase 3C N=1 personalized insights.

    Rules (all must pass):
    1. Tier gate: guided + premium.
    2. Global kill switch respected.
    3. Temporal gate: (prod_days >= 90) OR (synced_history_span_days >= 90).
    4. Statistical gate: at least one correlation passes corrected significance.
       - p < 0.05
       - |r| >= 0.3
       - n >= 10
       - Multiple-testing correction (Bonferroni) applied before surfacing.
    """
    if as_of is None:
        as_of = date.today()

    # Kill switch
    if _is_kill_switched(KILL_SWITCH_3C_ENV, db):
        return EligibilityResult(
            eligible=False,
            reason="N=1 insights are globally disabled (kill switch).",
            evidence={"kill_switch": True},
        )

    # Tier gate
    athlete = _get_athlete(athlete_id, db)
    if athlete is None:
        return EligibilityResult(
            eligible=False,
            reason="Athlete not found.",
            evidence={"athlete_id": str(athlete_id)},
        )
    if athlete.subscription_tier not in TIERS_3C:
        return EligibilityResult(
            eligible=False,
            reason=f"N=1 insights require guided, premium, elite, or pro tier. Current: {athlete.subscription_tier}.",
            evidence={"tier": athlete.subscription_tier, "required": sorted(TIERS_3C)},
        )

    # History sufficiency (production time OR synced history)
    stats = _history_stats(athlete_id, db)
    has_temporal = stats["history_span_days"] >= MIN_HISTORY_SPAN_DAYS
    if not has_temporal:
        return EligibilityResult(
            eligible=False,
            reason=(
                f"Insufficient data span. Need {MIN_HISTORY_SPAN_DAYS}+ days of "
                f"history. Have {stats['history_span_days']} days."
            ),
            evidence=stats,
        )

    # Statistical gate: run correlation engine, check if any survive Bonferroni
    try:
        from services.correlation_engine import analyze_correlations
        corr_result = analyze_correlations(
            athlete_id=str(athlete_id),
            days=min(stats["history_span_days"], 365),
            db=db,
        )
        raw_correlations = corr_result.get("correlations", [])
    except Exception as exc:
        return EligibilityResult(
            eligible=False,
            reason=f"Correlation analysis failed: {exc}",
            evidence={"error": str(exc), **stats},
        )

    # Bonferroni correction
    n_tests = max(len(raw_correlations), 1)
    significant = []
    for c in raw_correlations:
        p_adj = min(c["p_value"] * n_tests, 1.0)
        if (
            p_adj < 0.05
            and abs(c["correlation_coefficient"]) >= 0.3
            and c["sample_size"] >= 10
        ):
            significant.append({**c, "p_adjusted": p_adj})

    if not significant:
        return EligibilityResult(
            eligible=False,
            reason=(
                f"No statistically significant correlations survive correction. "
                f"Tested {n_tests} correlations with Bonferroni."
            ),
            evidence={
                "correlations_tested": n_tests,
                "significant_after_correction": 0,
                **stats,
            },
        )

    confidence = min(1.0, len(significant) / 5) * min(1.0, stats["total_runs"] / 100)

    return EligibilityResult(
        eligible=True,
        reason=f"{len(significant)} significant correlation(s) found after Bonferroni correction.",
        evidence={
            "correlations_tested": n_tests,
            "significant_after_correction": len(significant),
            "top_correlation": significant[0] if significant else None,
            **stats,
        },
        confidence=round(confidence, 3),
    )
