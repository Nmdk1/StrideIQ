"""
Effort resolver — single source of truth for "what effort did this run feel like?"

Founder rule (binding): the athlete's own subjective score takes full weight.
Garmin's self-eval (perceived effort 1-10 + "feel" enum) is a low-confidence
fallback, only used when the athlete has not reflected via the StrideIQ
FeedbackModal. We never blend the two; whichever source we use, we attribute.

Used by:
  - apps/api/services/coach_tools/activity.py — get_recent_runs / get_calendar_day_context
  - apps/api/services/intelligence/* — anywhere that previously read
    Activity.garmin_perceived_effort directly
  - apps/web/components/activities/GarminEffortFallback.tsx — the UI applies the
    same rule client-side; this server function is what the LLM and the
    correlation engine read.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from models import Activity, ActivityFeedback


# Garmin FIT feel enum -> a coarse 1-10 RPE we can compare across athletes.
# These are deliberately wide buckets; they're used only as a fallback when
# the athlete hasn't logged their own RPE. The mapping mirrors the FIT SDK's
# 5-point scale (very strong / strong / normal / weak / very weak) which we
# already decode in services/sync/fit_run_parser._decode_feel.
_FEEL_TO_RPE: dict = {
    "very_strong": 3,   # felt strong — perceived effort low for the work done
    "strong": 4,
    "normal": 6,
    "weak": 8,
    "very_weak": 9,     # felt awful — perceived effort very high
}


@dataclass(frozen=True)
class ResolvedEffort:
    """The effort the athlete felt for this run, with provenance.

    Attributes:
        rpe: 1-10 perceived effort (None when no source has data).
        source: One of "athlete_feedback" | "garmin_self_eval" | None.
        feel_label: Human-readable label, e.g. "strong" / "normal".
            Populated for both sources when available; from feedback.leg_feel
            when athlete provided it, else from Garmin feel enum.
        confidence: "high" (athlete logged it), "low" (Garmin watch), or
            "none" (we have nothing).
    """
    rpe: Optional[int]
    source: Optional[str]
    feel_label: Optional[str]
    confidence: str


def resolve_effort(activity: Activity, feedback: Optional[ActivityFeedback]) -> ResolvedEffort:
    """Resolve the perceived effort for a single activity.

    Pure function — no DB I/O. Hand it the activity and (optionally) the
    feedback row you've already loaded. See `resolve_effort_for_activity`
    for the lookup-by-id convenience helper.

    Order:
        1. ActivityFeedback.perceived_effort (athlete's own RPE) — full weight.
        2. Garmin self-eval on the Activity (perceived effort + feel) — low
           confidence fallback.
        3. None — nothing to say.
    """
    # --- 1. Athlete's own RPE wins outright. ---
    if feedback is not None:
        athlete_rpe = getattr(feedback, "perceived_effort", None)
        if isinstance(athlete_rpe, int) and 1 <= athlete_rpe <= 10:
            return ResolvedEffort(
                rpe=int(athlete_rpe),
                source="athlete_feedback",
                feel_label=getattr(feedback, "leg_feel", None) or None,
                confidence="high",
            )

    # --- 2. Garmin self-eval as fallback. ---
    g_rpe = getattr(activity, "garmin_perceived_effort", None)
    g_feel = getattr(activity, "garmin_feel", None)

    rpe: Optional[int] = None
    if isinstance(g_rpe, int) and 1 <= g_rpe <= 10:
        rpe = int(g_rpe)
    elif isinstance(g_feel, str) and g_feel in _FEEL_TO_RPE:
        # Athlete picked feel on the watch but not numeric RPE — derive a
        # bucketed RPE so downstream consumers always have a number. The
        # `feel_label` keeps the original string so we never lose nuance.
        rpe = _FEEL_TO_RPE[g_feel]

    if rpe is not None or (isinstance(g_feel, str) and g_feel):
        return ResolvedEffort(
            rpe=rpe,
            source="garmin_self_eval",
            feel_label=g_feel if isinstance(g_feel, str) else None,
            confidence="low",
        )

    # --- 3. Nothing recorded. ---
    return ResolvedEffort(rpe=None, source=None, feel_label=None, confidence="none")


def resolve_effort_for_activity(db: Session, activity: Activity) -> ResolvedEffort:
    """Convenience: load the feedback row by activity_id and resolve.

    Cheap single-row lookup. Use the pure `resolve_effort` instead when you
    already have the feedback row in scope (e.g., in batch fetches that
    pre-load feedback to avoid N+1).
    """
    if activity is None:
        return ResolvedEffort(rpe=None, source=None, feel_label=None, confidence="none")

    feedback = (
        db.query(ActivityFeedback)
        .filter(ActivityFeedback.activity_id == activity.id)
        .first()
    )
    return resolve_effort(activity, feedback)


def to_dict(resolved: ResolvedEffort) -> dict:
    """Serialize for tool envelopes / API responses."""
    return {
        "rpe": resolved.rpe,
        "source": resolved.source,
        "feel_label": resolved.feel_label,
        "confidence": resolved.confidence,
    }
