"""
Detect and label structured workout intervals from ActivitySplit data.

Classifies each split as warm_up / work / rest / cool_down based on pace
patterns. Generates a human-readable summary like "5×4:00 at 7:09/mi avg,
3:00 rest".
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass
class LabeledSplit:
    split_number: int
    distance: Optional[float]
    elapsed_time: Optional[int]
    moving_time: Optional[int]
    average_heartrate: Optional[int]
    max_heartrate: Optional[int]
    average_cadence: Optional[float]
    gap_seconds_per_mile: Optional[float]
    lap_type: Optional[str] = None  # warm_up, work, rest, cool_down
    interval_number: Optional[int] = None
    pace_sec_per_km: Optional[float] = None


@dataclass
class IntervalSummary:
    is_structured: bool = False
    workout_description: Optional[str] = None
    num_work_intervals: int = 0
    avg_work_pace_sec_per_km: Optional[float] = None
    avg_work_hr: Optional[int] = None
    avg_rest_duration_s: Optional[float] = None
    avg_rest_hr: Optional[int] = None
    fastest_interval: Optional[int] = None
    slowest_interval: Optional[int] = None


@dataclass
class IntervalAnalysis:
    labeled_splits: List[LabeledSplit] = field(default_factory=list)
    summary: IntervalSummary = field(default_factory=IntervalSummary)


def _compute_pace(distance_m: Optional[float], time_s: Optional[int]) -> Optional[float]:
    if not distance_m or distance_m <= 0 or not time_s or time_s <= 0:
        return None
    return (time_s / distance_m) * 1000  # sec per km


def _format_duration(seconds: int) -> str:
    m, s = divmod(seconds, 60)
    if m >= 60:
        h, m = divmod(m, 60)
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def _format_pace_imperial(sec_per_km: float) -> str:
    sec_per_mile = sec_per_km * 1.60934
    m, s = divmod(int(round(sec_per_mile)), 60)
    return f"{m}:{s:02d}/mi"


def detect_interval_structure(splits_data: list) -> IntervalAnalysis:
    """
    Analyze splits to detect and label workout structure.

    Args:
        splits_data: list of dicts or ORM objects with split fields

    Returns:
        IntervalAnalysis with labeled splits and summary.
    """
    if not splits_data or len(splits_data) < 3:
        return _passthrough(splits_data or [])

    labeled = []
    for s in splits_data:
        dist = float(getattr(s, "distance", None) or (s.get("distance") if isinstance(s, dict) else None) or 0)
        et = getattr(s, "elapsed_time", None) if not isinstance(s, dict) else s.get("elapsed_time")
        mt = getattr(s, "moving_time", None) if not isinstance(s, dict) else s.get("moving_time")
        time_s = mt or et
        ls = LabeledSplit(
            split_number=getattr(s, "split_number", None) if not isinstance(s, dict) else s.get("split_number", 0),
            distance=dist if dist > 0 else None,
            elapsed_time=et,
            moving_time=mt,
            average_heartrate=getattr(s, "average_heartrate", None) if not isinstance(s, dict) else s.get("average_heartrate"),
            max_heartrate=getattr(s, "max_heartrate", None) if not isinstance(s, dict) else s.get("max_heartrate"),
            average_cadence=getattr(s, "average_cadence", None) if not isinstance(s, dict) else s.get("average_cadence"),
            gap_seconds_per_mile=getattr(s, "gap_seconds_per_mile", None) if not isinstance(s, dict) else s.get("gap_seconds_per_mile"),
            pace_sec_per_km=_compute_pace(dist, time_s),
        )
        labeled.append(ls)

    valid = [ls for ls in labeled if ls.pace_sec_per_km is not None]
    if len(valid) < 3:
        return _passthrough_labeled(labeled)

    paces = [ls.pace_sec_per_km for ls in valid]
    mean_pace = sum(paces) / len(paces)
    variance = sum((p - mean_pace) ** 2 for p in paces) / len(paces)
    cv = (math.sqrt(variance) / mean_pace) * 100 if mean_pace > 0 else 0

    if cv < 10:
        return _passthrough_labeled(labeled)

    fast_threshold = mean_pace * 0.93
    slow_threshold = mean_pace * 1.07

    for ls in labeled:
        if ls.pace_sec_per_km is None:
            continue
        if ls.pace_sec_per_km <= fast_threshold:
            ls.lap_type = "work"
        elif ls.pace_sec_per_km >= slow_threshold:
            ls.lap_type = "rest"
        else:
            ls.lap_type = "rest" if ls.pace_sec_per_km > mean_pace else "work"

    _label_warmup_cooldown(labeled)
    _number_work_intervals(labeled)
    summary = _build_summary(labeled)

    return IntervalAnalysis(labeled_splits=labeled, summary=summary)


def _label_warmup_cooldown(labeled: List[LabeledSplit]) -> None:
    """Promote first and last slow segments to warm_up / cool_down."""
    if not labeled:
        return

    for ls in labeled:
        if ls.lap_type == "rest":
            ls.lap_type = "warm_up"
            break
        elif ls.lap_type == "work":
            break

    for ls in reversed(labeled):
        if ls.lap_type in ("rest", None) and ls.pace_sec_per_km is not None:
            time_s = ls.moving_time or ls.elapsed_time or 0
            if time_s > 60:
                ls.lap_type = "cool_down"
            break
        elif ls.lap_type == "work":
            break


def _number_work_intervals(labeled: List[LabeledSplit]) -> None:
    """Assign 1-indexed interval_number to work splits."""
    n = 0
    for ls in labeled:
        if ls.lap_type == "work":
            n += 1
            ls.interval_number = n


def _build_summary(labeled: List[LabeledSplit]) -> IntervalSummary:
    """Generate IntervalSummary from labeled splits."""
    work = [ls for ls in labeled if ls.lap_type == "work"]
    rest = [ls for ls in labeled if ls.lap_type == "rest"]

    if len(work) < 2:
        if len(work) == 1:
            return _build_tempo_summary(labeled, work[0])
        return IntervalSummary(is_structured=False)

    work_times = [ls.moving_time or ls.elapsed_time or 0 for ls in work]
    work_paces = [ls.pace_sec_per_km for ls in work if ls.pace_sec_per_km]
    work_hrs = [ls.average_heartrate for ls in work if ls.average_heartrate]
    rest_times = [ls.moving_time or ls.elapsed_time or 0 for ls in rest]
    rest_hrs = [ls.average_heartrate for ls in rest if ls.average_heartrate]

    avg_work_time = sum(work_times) / len(work_times) if work_times else 0
    avg_work_pace = sum(work_paces) / len(work_paces) if work_paces else None
    avg_rest_time = sum(rest_times) / len(rest_times) if rest_times else None

    fastest_idx = None
    slowest_idx = None
    if work_paces and len(work) >= 2:
        fastest_pace = min(ls.pace_sec_per_km for ls in work if ls.pace_sec_per_km)
        slowest_pace = max(ls.pace_sec_per_km for ls in work if ls.pace_sec_per_km)
        for ls in work:
            if ls.pace_sec_per_km == fastest_pace and fastest_idx is None:
                fastest_idx = ls.interval_number
            if ls.pace_sec_per_km == slowest_pace:
                slowest_idx = ls.interval_number

    desc_parts = [f"{len(work)}×{_format_duration(int(round(avg_work_time)))}"]
    if avg_work_pace:
        desc_parts.append(f"at {_format_pace_imperial(avg_work_pace)} avg")
    if avg_rest_time and avg_rest_time > 0:
        desc_parts.append(f"{_format_duration(int(round(avg_rest_time)))} rest")

    description = ", ".join(desc_parts) if len(desc_parts) > 1 else desc_parts[0]

    return IntervalSummary(
        is_structured=True,
        workout_description=description,
        num_work_intervals=len(work),
        avg_work_pace_sec_per_km=avg_work_pace,
        avg_work_hr=round(sum(work_hrs) / len(work_hrs)) if work_hrs else None,
        avg_rest_duration_s=avg_rest_time,
        avg_rest_hr=round(sum(rest_hrs) / len(rest_hrs)) if rest_hrs else None,
        fastest_interval=fastest_idx,
        slowest_interval=slowest_idx,
    )


def _build_tempo_summary(labeled: List[LabeledSplit], work_split: LabeledSplit) -> IntervalSummary:
    """Summary for single-segment sustained efforts (tempo, threshold)."""
    time_s = work_split.moving_time or work_split.elapsed_time or 0
    desc = _format_duration(time_s)
    if work_split.pace_sec_per_km:
        desc += f" at {_format_pace_imperial(work_split.pace_sec_per_km)}"

    return IntervalSummary(
        is_structured=True,
        workout_description=desc,
        num_work_intervals=1,
        avg_work_pace_sec_per_km=work_split.pace_sec_per_km,
        avg_work_hr=work_split.average_heartrate,
        avg_rest_duration_s=None,
        avg_rest_hr=None,
        fastest_interval=1,
        slowest_interval=1,
    )


def _passthrough(splits_data: list) -> IntervalAnalysis:
    labeled = []
    for s in splits_data:
        dist = float(getattr(s, "distance", None) or (s.get("distance") if isinstance(s, dict) else None) or 0)
        et = getattr(s, "elapsed_time", None) if not isinstance(s, dict) else s.get("elapsed_time")
        mt = getattr(s, "moving_time", None) if not isinstance(s, dict) else s.get("moving_time")
        labeled.append(LabeledSplit(
            split_number=getattr(s, "split_number", None) if not isinstance(s, dict) else s.get("split_number", 0),
            distance=dist if dist > 0 else None,
            elapsed_time=et,
            moving_time=mt,
            average_heartrate=getattr(s, "average_heartrate", None) if not isinstance(s, dict) else s.get("average_heartrate"),
            max_heartrate=getattr(s, "max_heartrate", None) if not isinstance(s, dict) else s.get("max_heartrate"),
            average_cadence=getattr(s, "average_cadence", None) if not isinstance(s, dict) else s.get("average_cadence"),
            gap_seconds_per_mile=getattr(s, "gap_seconds_per_mile", None) if not isinstance(s, dict) else s.get("gap_seconds_per_mile"),
            pace_sec_per_km=_compute_pace(dist, mt or et),
        ))
    return IntervalAnalysis(labeled_splits=labeled, summary=IntervalSummary())


def _passthrough_labeled(labeled: List[LabeledSplit]) -> IntervalAnalysis:
    return IntervalAnalysis(labeled_splits=labeled, summary=IntervalSummary())
