"""
Correlation Multi-Window Rescan Loop — Phase 0A (shadow only).

Rescans the full correlation universe for one athlete across six
time windows.  Uses the existing `analyze_correlations()` function;
does NOT fork discovery logic.

Safety guarantees:
- Calls `analyze_correlations()` (which internally flushes to DB)
  but the orchestrator never commits those writes.
- The caller (orchestrator) must roll back the session after recording
  the results dict.  No `db.commit()` is called here.
- Does not mutate any athlete-facing model.
- Returns raw result dicts for storage in the experiment ledger only.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional
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
                    )
                    correlations = result.get("correlations", [])
                    findings_by_metric[metric] = [
                        {
                            "input_name": c.get("input_name"),
                            "correlation_coefficient": c.get("correlation_coefficient"),
                            "p_value": c.get("p_value"),
                            "sample_size": c.get("sample_size"),
                            "direction": c.get("direction"),
                            "lag_days": c.get("lag_days"),
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
