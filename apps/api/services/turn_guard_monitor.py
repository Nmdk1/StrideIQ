"""Turn-guard telemetry aggregation and rollout decision helpers."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

_EVENT_RE = re.compile(r"\bevent=([a-z_]+)\b")
_TURN_ID_RE = re.compile(r"\bturn_id=([^\s]+)\b")
_USER_BAND_RE = re.compile(r"\buser_band=([a-z_]+)\b")
_ASSISTANT_BAND_RE = re.compile(r"\bassistant_band=([a-z_]+)\b")
_STAGE_RE = re.compile(r"\bstage=([a-z_]+)\b")
_SYNTHETIC_RE = re.compile(r"\bis_synthetic_probe=(True|False|true|false)\b")
_ORGANIC_RE = re.compile(r"\bis_organic=(True|False|true|false)\b")


def _to_bool(value: str) -> bool:
    return str(value).lower() == "true"


def _extract_message(raw_line: str) -> str:
    line = (raw_line or "").strip()
    if not line:
        return ""
    if line.startswith("{") and '"message"' in line:
        try:
            payload = json.loads(line)
            return str(payload.get("message") or "")
        except Exception:
            return line
    return line


def parse_turn_guard_event(raw_line: str) -> Optional[Dict[str, Any]]:
    message = _extract_message(raw_line)
    if "turn_guard_event" not in message:
        return None
    event_m = _EVENT_RE.search(message)
    turn_m = _TURN_ID_RE.search(message)
    user_band_m = _USER_BAND_RE.search(message)
    assistant_band_m = _ASSISTANT_BAND_RE.search(message)
    stage_m = _STAGE_RE.search(message)
    synthetic_m = _SYNTHETIC_RE.search(message)
    organic_m = _ORGANIC_RE.search(message)
    if not event_m or not turn_m:
        return None
    return {
        "event": event_m.group(1),
        "turn_id": turn_m.group(1),
        "user_band": user_band_m.group(1) if user_band_m else "unknown",
        "assistant_band": assistant_band_m.group(1) if assistant_band_m else "unknown",
        "stage": stage_m.group(1) if stage_m else "unknown",
        "is_synthetic_probe": _to_bool(synthetic_m.group(1)) if synthetic_m else False,
        "is_organic": _to_bool(organic_m.group(1)) if organic_m else True,
        "raw": message,
    }


def _safe_rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return float(numerator) / float(denominator)


def _aggregate_turns(events: Iterable[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    turns: Dict[str, Dict[str, Any]] = {}
    for event in events:
        turn_id = event["turn_id"]
        turn = turns.get(turn_id)
        if not turn:
            turn = {
                "turn_id": turn_id,
                "events": [],
                "user_band": event.get("user_band", "unknown"),
                "assistant_band": event.get("assistant_band", "unknown"),
                "is_synthetic_probe": bool(event.get("is_synthetic_probe", False)),
                "is_organic": bool(event.get("is_organic", True)),
            }
            turns[turn_id] = turn
        turn["events"].append(event.get("event"))
        turn["assistant_band"] = event.get("assistant_band", turn["assistant_band"])
        turn["is_synthetic_probe"] = turn["is_synthetic_probe"] or bool(event.get("is_synthetic_probe", False))
        turn["is_organic"] = turn["is_organic"] and bool(event.get("is_organic", True))
    return turns


def _summarize_turns(turns: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    total_turns = 0
    mismatch_turns = 0
    retry_success_turns = 0
    fallback_turns = 0
    event_counts: Counter[str] = Counter()
    band_counts: Counter[str] = Counter()
    band_pair_counts: Counter[Tuple[str, str]] = Counter()

    for turn in turns:
        total_turns += 1
        events = set(turn.get("events") or [])
        event_counts.update(turn.get("events") or [])
        user_band = turn.get("user_band", "unknown")
        assistant_band = turn.get("assistant_band", "unknown")
        band_counts[user_band] += 1
        band_pair_counts[(user_band, assistant_band)] += 1
        if "mismatch_detected" in events:
            mismatch_turns += 1
        if "retry_success" in events:
            retry_success_turns += 1
        if "fallback_used" in events:
            fallback_turns += 1

    return {
        "total_turns": total_turns,
        "mismatch_turns": mismatch_turns,
        "retry_success_turns": retry_success_turns,
        "fallback_turns": fallback_turns,
        "event_counts": dict(event_counts),
        "band_counts": dict(band_counts),
        "band_pair_counts": {f"{k[0]}->{k[1]}": v for k, v in band_pair_counts.items()},
        "mismatch_rate": _safe_rate(mismatch_turns, total_turns),
        "retry_success_rate": _safe_rate(retry_success_turns, mismatch_turns),
        "fallback_rate": _safe_rate(fallback_turns, mismatch_turns),
    }


def build_rollout_report(
    raw_lines: Iterable[str],
    *,
    min_organic_sample: int = 50,
    min_band_sample: int = 10,
    mismatch_threshold: float = 0.08,
    retry_success_threshold: float = 0.60,
    fallback_threshold: float = 0.40,
) -> Dict[str, Any]:
    parsed = [event for event in (parse_turn_guard_event(line) for line in raw_lines) if event]
    turns_map = _aggregate_turns(parsed)
    all_turns = list(turns_map.values())
    organic_turns = [t for t in all_turns if t.get("is_organic") and (not t.get("is_synthetic_probe"))]
    synthetic_turns = [t for t in all_turns if t.get("is_synthetic_probe")]

    overall = _summarize_turns(organic_turns)

    by_band: Dict[str, Dict[str, Any]] = {}
    turns_by_band: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for turn in organic_turns:
        turns_by_band[turn.get("user_band", "unknown")].append(turn)
    for band, band_turns in turns_by_band.items():
        by_band[band] = _summarize_turns(band_turns)

    if overall["total_turns"] < min_organic_sample:
        status = "INSUFFICIENT_SAMPLE"
    elif overall["mismatch_rate"] > mismatch_threshold:
        status = "NO_GO"
    elif overall["retry_success_rate"] < retry_success_threshold:
        status = "WATCH"
    elif overall["fallback_rate"] > fallback_threshold:
        status = "WATCH"
    else:
        status = "GO"

    hot_bands: List[Dict[str, Any]] = []
    for band, band_summary in by_band.items():
        if band_summary["total_turns"] < min_band_sample:
            continue
        if band_summary["mismatch_rate"] > mismatch_threshold or band_summary["fallback_rate"] > fallback_threshold:
            hot_bands.append(
                {
                    "band": band,
                    "total_turns": band_summary["total_turns"],
                    "mismatch_rate": band_summary["mismatch_rate"],
                    "fallback_rate": band_summary["fallback_rate"],
                }
            )

    recommended_actions: List[str] = []
    if status == "INSUFFICIENT_SAMPLE":
        recommended_actions.append("Collect more organic turns before rollout decisions.")
    if status == "NO_GO":
        recommended_actions.extend(
            [
                "Freeze broad rollout and keep deterministic/fallback guardrails active.",
                "Prioritize fixes for highest-mismatch bands before changing traffic split.",
            ]
        )
    if status == "WATCH":
        recommended_actions.extend(
            [
                "Keep current rollout and tighten only failing intent bands.",
                "Add targeted regression tests for observed drift pairings.",
            ]
        )
    if status == "GO":
        recommended_actions.append("Maintain current policy and continue hourly monitoring.")
    if hot_bands:
        for hot in hot_bands:
            recommended_actions.append(
                f"Band '{hot['band']}' is hot: mismatch={hot['mismatch_rate']:.1%}, fallback={hot['fallback_rate']:.1%}."
            )

    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "thresholds": {
            "min_organic_sample": min_organic_sample,
            "min_band_sample": min_band_sample,
            "mismatch_threshold": mismatch_threshold,
            "retry_success_threshold": retry_success_threshold,
            "fallback_threshold": fallback_threshold,
        },
        "counts": {
            "total_events": len(parsed),
            "total_turns": len(all_turns),
            "organic_turns": len(organic_turns),
            "synthetic_turns": len(synthetic_turns),
        },
        "overall": overall,
        "by_band": by_band,
        "recommended_actions": recommended_actions,
    }
