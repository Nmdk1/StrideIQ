"""
Insight Feed Service

Produces a small set of ranked, evidence-backed insight "cards" for the Insights page.
This is intentionally deterministic (no LLM calls) and built on existing analytics engines.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from models import Athlete
from services.efficiency_analytics import get_efficiency_trends
from services.athlete_diagnostic import get_data_quality_assessment, get_personal_best_profile
from services.insight_aggregator import InsightAggregator


def _confidence_score(label: str) -> float:
    label = (label or "").lower().strip()
    if label == "high":
        return 0.9
    if label == "moderate":
        return 0.6
    if label == "low":
        return 0.35
    return 0.1


def build_insight_feed_cards(
    db: Session,
    athlete: Athlete,
    max_cards: int = 5,
) -> Dict[str, Any]:
    """
    Build a ranked feed of insight cards.

    Returns:
        dict with generated_at + cards[]
    """
    cards: List[Dict[str, Any]] = []

    # -------------------------------------------------------------------------
    # Card: Efficiency trend (engine output)
    # -------------------------------------------------------------------------
    try:
        eff = get_efficiency_trends(
            athlete_id=str(athlete.id),
            db=db,
            days=90,
            include_stability=True,
            include_load_response=True,
            include_annotations=False,
        )
        if "error" not in eff:
            ta = eff.get("trend_analysis") or {}
            summary = eff.get("summary") or {}

            direction = (ta.get("direction") or "stable").replace("_", " ")
            conf_label = ta.get("confidence") or "insufficient"
            conf_score = _confidence_score(conf_label)

            change_pct = ta.get("change_percent")
            sample_size = ta.get("sample_size")
            period_days = ta.get("period_days")

            title = f"Efficiency trend: {direction}"
            if isinstance(change_pct, (int, float)):
                title = f"Efficiency trend: {direction} ({change_pct:+.1f}%)"

            cards.append(
                {
                    "key": "efficiency_trend_90d",
                    "type": "trend",
                    "priority": 90 if ta.get("is_actionable") else 65,
                    "title": title,
                    "summary": ta.get("insight_text")
                    or "Efficiency trend computed from GAP-aware splits and HR.",
                    "confidence": {
                        "label": conf_label,
                        "score": conf_score,
                        "details": f"n={sample_size}, days={period_days}, p={ta.get('p_value')}, r²={ta.get('r_squared')}",
                    },
                    "evidence": [
                        {"label": "Sample", "value": f"{sample_size} runs"},
                        {"label": "Window", "value": f"{period_days} days"},
                        {"label": "Current EF", "value": str(summary.get("current_efficiency"))},
                        {"label": "Percentile", "value": str(summary.get("efficiency_percentile"))},
                    ],
                    "actions": [
                        {"label": "Open Analytics", "href": "/analytics"},
                        {"label": "Open Load → Response", "href": "/training-load"},
                    ],
                }
            )

            # -----------------------------------------------------------------
            # Card: Latest load-response week (engine output)
            # -----------------------------------------------------------------
            lr = eff.get("load_response") or []
            if isinstance(lr, list) and lr:
                latest = lr[-1] or {}
                load_type = latest.get("load_type") or "neutral"
                week_start = latest.get("week_start")
                activity_count = latest.get("activity_count") or 0
                eff_delta = latest.get("efficiency_delta")

                # Rough confidence: more activities -> more stable weekly signal
                lr_conf = "high" if activity_count >= 5 else "moderate" if activity_count >= 3 else "low"
                # Neutral labels — efficiency (pace/HR) is directionally ambiguous.
                # See Athlete Trust Safety Contract in n1_insight_generator.py.
                lr_priority = 70 if load_type in ("adaptation_signal", "load_signal") else 55

                if load_type == "adaptation_signal":
                    lr_summary = "Your efficiency ratio shifted this week. Tap to explore what changed."
                    lr_actions = [{"label": "See details", "href": "/training-load"}]
                elif load_type == "load_signal":
                    lr_summary = "Your efficiency ratio shifted this week. Check recovery context."
                    lr_actions = [{"label": "See details", "href": "/training-load"}]
                elif load_type == "stable":
                    lr_summary = "Efficiency ratio was stable week over week."
                    lr_actions = [{"label": "Open Training Load", "href": "/training-load"}]
                else:
                    lr_summary = "Load response is neutral this week."
                    lr_actions = [{"label": "Open Training Load", "href": "/training-load"}]

                cards.append(
                    {
                        "key": "load_response_latest_week",
                        "type": "load_response",
                        "priority": lr_priority,
                        "title": f"Load → Response: {load_type.replace('_', ' ')}",
                        "summary": lr_summary,
                        "confidence": {
                            "label": lr_conf,
                            "score": _confidence_score(lr_conf),
                            "details": f"week_start={week_start}, activities={activity_count}",
                        },
                        "evidence": [
                            {"label": "Week start", "value": str(week_start)},
                            {"label": "Activities", "value": str(activity_count)},
                            {"label": "Volume (mi)", "value": str(latest.get("total_distance_miles"))},
                            {"label": "EF Δ", "value": str(eff_delta)},
                        ],
                        "actions": lr_actions,
                    }
                )
    except Exception:
        # Feed is best-effort; other cards may still render.
        pass

    # -------------------------------------------------------------------------
    # Card: Plan context (action surface)
    # -------------------------------------------------------------------------
    try:
        bs = InsightAggregator(db, athlete).get_build_status()
        if bs:
            title = f"Plan: Week {bs.current_week} of {bs.total_weeks}"
            if bs.days_to_race is not None and bs.days_to_race >= 0:
                title = f"Plan: {bs.days_to_race} days to race"

            summary = "Your next key session is ready."
            if bs.key_session:
                summary = f"Key session: {bs.key_session}"

            cards.append(
                {
                    "key": "plan_context",
                    "type": "plan",
                    "priority": 60,
                    "title": title,
                    "summary": summary,
                    "confidence": {"label": "high", "score": 0.9, "details": "Active plan"},
                    "evidence": [
                        {"label": "Plan", "value": bs.plan_name},
                        {"label": "Phase", "value": bs.current_phase},
                    ],
                    "actions": [{"label": "Open Calendar", "href": "/calendar"}],
                }
            )
    except Exception:
        pass

    # -------------------------------------------------------------------------
    # Card: Data readiness (trust & unlocks)
    # -------------------------------------------------------------------------
    try:
        dq = get_data_quality_assessment(str(athlete.id), db)
        missing_keys = list((dq.missing or {}).keys())

        readiness = "good"
        if "daily_checkins" in missing_keys or "heart_rate" not in (dq.available or {}):
            readiness = "limited"

        summary = "Your data is ready for core Insights."
        if readiness != "good":
            summary = "Some key inputs are missing; Insights will be less precise until you fill them."

        actions = []
        if "daily_checkins" in missing_keys:
            actions.append({"label": "Start check-ins", "href": "/checkin"})
        if "heart_rate" not in (dq.available or {}):
            actions.append({"label": "Use HR for more runs", "href": "/settings"})
        if not actions:
            actions = [{"label": "View Diagnostics", "href": "/diagnostic"}]

        cards.append(
            {
                "key": "data_readiness",
                "type": "readiness",
                "priority": 75 if readiness != "good" else 45,
                "title": f"Readiness: {readiness}",
                "summary": summary,
                "confidence": {"label": "high", "score": 0.9, "details": "Direct counts"},
                "evidence": [
                    {"label": "Activities", "value": str((dq.available or {}).get("activities", {}).count)},
                    {"label": "Runs w/ HR", "value": str((dq.available or {}).get("heart_rate", {}).count)},
                    {"label": "PBs", "value": str((dq.available or {}).get("personal_bests", {}).count)},
                ],
                "actions": actions,
            }
        )
    except Exception:
        pass

    # -------------------------------------------------------------------------
    # Card: PB profile snapshot (single home + link)
    # -------------------------------------------------------------------------
    try:
        pbs = get_personal_best_profile(str(athlete.id), db)
        if pbs:
            best = pbs[0]
            cards.append(
                {
                    "key": "pb_profile",
                    "type": "personal_bests",
                    "priority": 40,
                    "title": f"Personal Bests: {len(pbs)} distances",
                    "summary": f"Fastest benchmark: {best.distance} in {int(best.time_seconds)}s ({best.pace_per_km}/km).",
                    "confidence": {"label": "high", "score": 0.9, "details": "Stored PB table"},
                    "evidence": [
                        {"label": "PB count", "value": str(len(pbs))},
                        {"label": "Example", "value": f"{best.distance} • {best.pace_per_km}/km"},
                    ],
                    "actions": [{"label": "Open Personal Bests", "href": "/personal-bests"}],
                }
            )
    except Exception:
        pass

    # Rank and trim
    cards.sort(key=lambda c: int(c.get("priority") or 0), reverse=True)
    cards = cards[: max_cards]

    return {"generated_at": datetime.now(timezone.utc).isoformat(), "cards": cards}

