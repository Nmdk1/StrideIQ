"""
Correlation Multi-Window Rescan Loop — Phase 1 (live mutation enabled).

Rescans the full correlation universe for one athlete across six
time windows.  Uses the existing `analyze_correlations()` function;
does NOT fork discovery logic.

Phase 0 safety contract (still in force when mutation is disabled):
- Calls `analyze_correlations()` (which internally flushes to DB)
  but the orchestrator rolls back those writes unless live mutation is on.
- The caller (orchestrator) must roll back the session after recording
  the results dict when in shadow mode.

Phase 1 additions:
- `promote_deep_window_findings()`: creates real CorrelationFinding rows for
  correlations found only at windows > 90d.
- `annotate_finding_stability()`: writes stability_class + windows_confirmed
  to existing findings (annotation, not significance change).
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Canonical window definitions for Phase 0A.
# None = full history (Postgres returns all rows from 2010-01-01).
RESCAN_WINDOWS_DAYS: List[Optional[int]] = [30, 60, 90, 180, 365, None]

ALL_OUTPUT_METRICS = [
    "efficiency",
    "pace_easy",
    "pace_threshold",
    "completion",
    "efficiency_threshold",
    "efficiency_race",
    "efficiency_trend",
    "pb_events",
    "race_pace",
]

# Use a very large sentinel for "full history" when passed to analyze_correlations.
_FULL_HISTORY_DAYS = 99999

# Statistical gate thresholds (must match daily sweep)
_MIN_ABS_R = 0.3
_MAX_P = 0.05
_MIN_N = 10

# Windows considered "deep" (beyond daily sweep 90d) — eligible for Phase 1 promotion
_DEEP_WINDOWS = {180, 365, _FULL_HISTORY_DAYS}


def run_multiwindow_rescan(
    athlete_id: UUID,
    db: Session,
) -> List[Dict[str, Any]]:
    """
    Run shadow correlation rescans for the athlete across all six windows.

    Returns a list of experiment-result dicts (one per window), suitable
    for writing to `auto_discovery_experiment`.

    THE CALLER MUST ROLL BACK THE SESSION after this function returns in
    order to discard the un-committed correlation_finding flushes produced
    by analyze_correlations().  This is the shadow-mode contract.
    """
    from services.correlation_engine import analyze_correlations

    athlete_id_str = str(athlete_id)
    experiment_results: List[Dict[str, Any]] = []

    for window_days in RESCAN_WINDOWS_DAYS:
        window_label = f"{window_days}d" if window_days is not None else "full_history"
        effective_days = window_days if window_days is not None else _FULL_HISTORY_DAYS
        t0 = time.monotonic()

        findings_by_metric: Dict[str, Any] = {}
        error: Optional[str] = None

        try:
            for metric in ALL_OUTPUT_METRICS:
                try:
                    result = analyze_correlations(
                        athlete_id=athlete_id_str,
                        days=effective_days,
                        db=db,
                        include_training_load=True,
                        output_metric=metric,
                        shadow_mode=True,  # bypass production cache (WS1)
                    )
                    correlations = result.get("correlations", [])
                    findings_by_metric[metric] = [
                        {
                            "input_name": c.get("input_name"),
                            "correlation_coefficient": c.get("correlation_coefficient"),
                            "p_value": c.get("p_value"),
                            "sample_size": c.get("sample_size"),
                            "direction": c.get("direction"),
                            "time_lag_days": c.get("time_lag_days"),  # fix: was "lag_days"
                            "strength": c.get("strength"),
                        }
                        for c in correlations
                    ]
                except Exception as metric_err:
                    logger.warning(
                        "Rescan window=%s metric=%s failed: %s",
                        window_label, metric, metric_err,
                    )

        except Exception as exc:
            error = str(exc)
            logger.error("Rescan window=%s failed: %s", window_label, exc)

        runtime_ms = int((time.monotonic() - t0) * 1000)
        total_findings = sum(len(v) for v in findings_by_metric.values())

        experiment_results.append({
            "loop_type": "correlation_rescan",
            "target_name": f"multiwindow:{window_label}",
            "baseline_config": {"window_days": window_days, "window_label": window_label},
            "candidate_config": {},
            "result_summary": {
                "window_label": window_label,
                "findings_by_metric": findings_by_metric,
                "total_findings": total_findings,
                "error": error,
            },
            "failure_reason": error,
            "runtime_ms": runtime_ms,
        })
        logger.info(
            "Rescan shadow: athlete=%s window=%s findings=%d runtime_ms=%d",
            athlete_id_str, window_label, total_findings, runtime_ms,
        )

    return experiment_results


def promote_deep_window_findings(
    athlete_id: UUID,
    rescan_results: List[Dict[str, Any]],
    db: Session,
) -> Tuple[List[Dict[str, Any]], int]:
    """Phase 1 mutation: create CorrelationFinding rows for correlations that
    pass significance gates at deep windows (>90d) not covered by the daily
    sweep.

    Returns (promoted_finding_dicts, count_promoted).  Caller is responsible
    for committing/rolling back.
    """
    from models import CorrelationFinding

    athlete_id_str = str(athlete_id)
    now = datetime.now(timezone.utc)
    promoted: List[Dict[str, Any]] = []

    for window_result in rescan_results:
        baseline_cfg = window_result.get("baseline_config", {})
        window_days = baseline_cfg.get("window_days")
        effective_days = window_days if window_days is not None else _FULL_HISTORY_DAYS
        if effective_days not in _DEEP_WINDOWS:
            continue  # only promote from deep windows

        summary = window_result.get("result_summary", {})
        findings_by_metric = summary.get("findings_by_metric", {})

        for metric, candidates in findings_by_metric.items():
            for cand in candidates:
                r = cand.get("correlation_coefficient")
                p = cand.get("p_value")
                n = cand.get("sample_size")
                input_name = cand.get("input_name")
                direction = cand.get("direction") or ("positive" if (r or 0) >= 0 else "negative")
                lag_days = cand.get("time_lag_days") or 0

                if not input_name:
                    continue
                if r is None or p is None or n is None:
                    continue
                if abs(r) < _MIN_ABS_R or p > _MAX_P or n < _MIN_N:
                    continue

                # Idempotent upsert: unique key is (athlete_id, input_name, output_metric, lag_days)
                existing = (
                    db.query(CorrelationFinding)
                    .filter(
                        CorrelationFinding.athlete_id == athlete_id,
                        CorrelationFinding.input_name == input_name,
                        CorrelationFinding.output_metric == metric,
                        CorrelationFinding.time_lag_days == lag_days,
                    )
                    .first()
                )

                if existing:
                    # Update deep-window metadata only if this window provides more evidence
                    changed = False
                    if existing.discovery_source != "auto_discovery":
                        existing.discovery_source = "auto_discovery"
                        changed = True
                    if existing.discovery_window_days is None or effective_days > (existing.discovery_window_days or 0):
                        existing.discovery_window_days = effective_days
                        changed = True
                    if changed:
                        db.flush()
                    state_label = "updated_metadata"
                else:
                    strength = cand.get("strength") or _r_to_strength(abs(r))
                    new_finding = CorrelationFinding(
                        athlete_id=athlete_id,
                        input_name=input_name,
                        output_metric=metric,
                        direction=direction,
                        time_lag_days=lag_days,
                        correlation_coefficient=r,
                        p_value=p,
                        sample_size=n,
                        strength=strength,
                        times_confirmed=1,
                        first_detected_at=now,
                        last_confirmed_at=now,
                        is_active=True,
                        category="what_works" if direction == "positive" else "what_doesnt",
                        confidence=abs(r),
                        discovery_source="auto_discovery",
                        discovery_window_days=effective_days,
                    )
                    db.add(new_finding)
                    db.flush()
                    state_label = "created"

                promoted.append({
                    "input_name": input_name,
                    "output_metric": metric,
                    "direction": direction,
                    "lag_days": lag_days,
                    "window_days": effective_days,
                    "r": r,
                    "p": p,
                    "n": n,
                    "state": state_label,
                })
                logger.info(
                    "Rescan Phase 1: %s finding athlete=%s %s->%s @lag=%d window=%s",
                    state_label, athlete_id_str, input_name, metric, lag_days, effective_days,
                )

    return promoted, len(promoted)


def annotate_finding_stability(
    athlete_id: UUID,
    rescan_results: List[Dict[str, Any]],
    db: Session,
) -> int:
    """Phase 1: annotate existing CorrelationFinding rows with stability evidence.

    Writes stability_class + windows_confirmed + stability_checked_at.
    This is pure annotation — does not change significance or surfacing eligibility.

    Returns count of findings annotated.
    """
    from models import CorrelationFinding

    now = datetime.now(timezone.utc)
    stability = summarize_window_stability(rescan_results)

    def _update(finding_key: Tuple[str, str], cls: str, windows: int) -> bool:
        metric, input_name = finding_key
        row = (
            db.query(CorrelationFinding)
            .filter(
                CorrelationFinding.athlete_id == athlete_id,
                CorrelationFinding.input_name == input_name,
                CorrelationFinding.output_metric == metric,
                CorrelationFinding.is_active == True,  # noqa: E712
            )
            .first()
        )
        if not row:
            return False
        row.stability_class = cls
        row.windows_confirmed = windows
        row.stability_checked_at = now
        db.flush()
        return True

    count = 0
    for item in stability.get("stable", []):
        if _update((item["metric"], item["input"]), "stable", len(RESCAN_WINDOWS_DAYS)):
            count += 1
    for item in stability.get("recent_only", []):
        if _update((item["metric"], item["input"]), "recent_only", len(item["windows"])):
            count += 1
    for item in stability.get("strengthening", []):
        if _update((item["metric"], item["input"]), "strengthening", len(item["windows"])):
            count += 1
    for item in stability.get("unstable", []):
        if _update((item["metric"], item["input"]), "unstable", len(item["windows"])):
            count += 1

    # Flag degrading findings: exist in DB but appear in no recent window
    all_window_keys: set = set()
    for bucket in stability.values():
        for item in bucket:
            all_window_keys.add((item["metric"], item["input"]))

    active_findings = (
        db.query(CorrelationFinding)
        .filter(
            CorrelationFinding.athlete_id == athlete_id,
            CorrelationFinding.is_active == True,  # noqa: E712
        )
        .all()
    )
    for finding in active_findings:
        key = (finding.output_metric, finding.input_name)
        if key not in all_window_keys:
            finding.stability_class = "degrading"
            finding.stability_checked_at = now
            db.flush()

    return count


def _r_to_strength(abs_r: float) -> str:
    if abs_r >= 0.5:
        return "strong"
    elif abs_r >= 0.3:
        return "moderate"
    return "weak"


def summarize_window_stability(
    experiment_results: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Across window results, classify each (metric, input) finding into:
        stable      — present across all non-error windows
        recent_only — present only in shorter windows (≤90d)
        strengthening — signal grows only in longer history (≥180d)
        unstable    — appears/disappears inconsistently

    Returns a dict suitable for inclusion in the nightly report
    `stable_findings` section.
    """
    window_data: List[Dict[str, Any]] = [
        r["result_summary"]
        for r in experiment_results
        if not r.get("failure_reason")
    ]

    sets_per_window: List[set] = []
    for wd in window_data:
        keys: set = set()
        for metric, findings in wd.get("findings_by_metric", {}).items():
            for f in findings:
                keys.add((metric, f.get("input_name", "")))
        sets_per_window.append(keys)

    if not sets_per_window:
        return {"stable": [], "recent_only": [], "strengthening": [], "unstable": []}

    all_keys = set().union(*sets_per_window)
    short_indices = set(range(min(3, len(sets_per_window))))
    long_indices = set(range(min(3, len(sets_per_window)), len(sets_per_window)))

    stable, recent_only, strengthening, unstable = [], [], [], []
    for key in all_keys:
        present = frozenset(i for i, s in enumerate(sets_per_window) if key in s)
        expected_all = frozenset(range(len(sets_per_window)))

        if present == expected_all:
            stable.append({"metric": key[0], "input": key[1], "windows": "all"})
        elif present.issubset(short_indices) and len(present) >= 1:
            recent_only.append({"metric": key[0], "input": key[1], "windows": sorted(present)})
        elif long_indices and long_indices.issubset(present) and not short_indices.intersection(present):
            strengthening.append({"metric": key[0], "input": key[1], "windows": sorted(present)})
        else:
            unstable.append({"metric": key[0], "input": key[1], "windows": sorted(present)})

    return {
        "stable": stable,
        "recent_only": recent_only,
        "strengthening": strengthening,
        "unstable": unstable,
    }



def run_multiwindow_rescan(  # noqa: F811
    athlete_id: UUID,
    db: Session,
) -> List[Dict[str, Any]]:
    """
    Run shadow correlation rescans for the athlete across all six windows.

    Returns a list of experiment-result dicts (one per window), suitable
    for writing to `auto_discovery_experiment`.

    THE CALLER MUST ROLL BACK THE SESSION after this function returns in
    order to discard the un-committed correlation_finding flushes produced
    by analyze_correlations().  This is the shadow-mode contract.
    """
    from services.correlation_engine import analyze_correlations

    athlete_id_str = str(athlete_id)
    experiment_results: List[Dict[str, Any]] = []

    for window_days in RESCAN_WINDOWS_DAYS:
        window_label = f"{window_days}d" if window_days is not None else "full_history"
        effective_days = window_days if window_days is not None else _FULL_HISTORY_DAYS
        t0 = time.monotonic()

        findings_by_metric: Dict[str, Any] = {}
        error: Optional[str] = None

        try:
            for metric in ALL_OUTPUT_METRICS:
                try:
                    result = analyze_correlations(
                        athlete_id=athlete_id_str,
                        days=effective_days,
                        db=db,
                        include_training_load=True,
                        output_metric=metric,
                        shadow_mode=True,  # bypass production cache (WS1)
                    )
                    correlations = result.get("correlations", [])
                    findings_by_metric[metric] = [
                        {
                            "input_name": c.get("input_name"),
                            "correlation_coefficient": c.get("correlation_coefficient"),
                            "p_value": c.get("p_value"),
                            "sample_size": c.get("sample_size"),
                            "direction": c.get("direction"),
                            "time_lag_days": c.get("time_lag_days"),  # fix: was "lag_days"
                            "strength": c.get("strength"),
                        }
                        for c in correlations
                    ]
                except Exception as metric_err:
                    logger.warning(
                        "Rescan window=%s metric=%s failed: %s",
                        window_label, metric, metric_err,
                    )

        except Exception as exc:
            error = str(exc)
            logger.error("Rescan window=%s failed: %s", window_label, exc)

        runtime_ms = int((time.monotonic() - t0) * 1000)
        total_findings = sum(len(v) for v in findings_by_metric.values())

        experiment_results.append({
            "loop_type": "correlation_rescan",
            "target_name": f"multiwindow:{window_label}",
            "baseline_config": {"window_days": window_days, "window_label": window_label},
            "candidate_config": {},
            "result_summary": {
                "window_label": window_label,
                "findings_by_metric": findings_by_metric,
                "total_findings": total_findings,
                "error": error,
            },
            "failure_reason": error,
            "runtime_ms": runtime_ms,
        })
        logger.info(
            "Rescan shadow: athlete=%s window=%s findings=%d runtime_ms=%d",
            athlete_id_str, window_label, total_findings, runtime_ms,
        )

    return experiment_results


def summarize_window_stability(  # noqa: F811
    experiment_results: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Across window results, classify each (metric, input) finding into:
        stable      — present across all non-error windows
        recent_only — present only in shorter windows (≤90d)
        strengthening — signal grows only in longer history (≥180d)
        unstable    — appears/disappears inconsistently

    Returns a dict suitable for inclusion in the nightly report
    `stable_findings` section.
    """
    window_data: List[Dict[str, Any]] = [
        r["result_summary"]
        for r in experiment_results
        if not r.get("failure_reason")
    ]

    sets_per_window: List[set] = []
    for wd in window_data:
        keys: set = set()
        for metric, findings in wd.get("findings_by_metric", {}).items():
            for f in findings:
                keys.add((metric, f.get("input_name", "")))
        sets_per_window.append(keys)

    if not sets_per_window:
        return {"stable": [], "recent_only": [], "strengthening": [], "unstable": []}

    all_keys = set().union(*sets_per_window)
    short_indices = set(range(min(3, len(sets_per_window))))
    long_indices = set(range(min(3, len(sets_per_window)), len(sets_per_window)))

    stable, recent_only, strengthening, unstable = [], [], [], []
    for key in all_keys:
        present = frozenset(i for i, s in enumerate(sets_per_window) if key in s)
        expected_all = frozenset(range(len(sets_per_window)))

        if present == expected_all:
            stable.append({"metric": key[0], "input": key[1], "windows": "all"})
        elif present.issubset(short_indices) and len(present) >= 1:
            recent_only.append({"metric": key[0], "input": key[1], "windows": sorted(present)})
        elif long_indices and long_indices.issubset(present) and not short_indices.intersection(present):
            strengthening.append({"metric": key[0], "input": key[1], "windows": sorted(present)})
        else:
            unstable.append({"metric": key[0], "input": key[1], "windows": sorted(present)})

    return {
        "stable": stable,
        "recent_only": recent_only,
        "strengthening": strengthening,
        "unstable": unstable,
    }
