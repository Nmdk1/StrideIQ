"""
Detect and label structured workout intervals from ActivitySplit data.

Algorithm:
  1. Identify "stopped" splits (very short distance = athlete stood still)
  2. Group consecutive non-stopped splits into segments
  3. Compute each segment's weighted-average pace
  4. Classify segments: fast = work, slow before first work = warm_up,
     slow after last work = cool_down
  5. Number work segments 1-indexed
  6. Generate summary like "3×9:00 at 6:25/mi avg, 2:00 rest"
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional


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
    lap_type: Optional[str] = None
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
    return (time_s / distance_m) * 1000


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


def _get(s, attr, default=None):
    if isinstance(s, dict):
        return s.get(attr, default)
    return getattr(s, attr, default)


def _to_labeled(s) -> LabeledSplit:
    dist = float(_get(s, "distance") or 0)
    et = _get(s, "elapsed_time")
    mt = _get(s, "moving_time")
    time_s = mt or et
    return LabeledSplit(
        split_number=_get(s, "split_number", 0),
        distance=dist if dist > 0 else None,
        elapsed_time=et,
        moving_time=mt,
        average_heartrate=_get(s, "average_heartrate"),
        max_heartrate=_get(s, "max_heartrate"),
        average_cadence=_get(s, "average_cadence"),
        gap_seconds_per_mile=_get(s, "gap_seconds_per_mile"),
        pace_sec_per_km=_compute_pace(dist, time_s),
    )


def _is_stopped(ls: LabeledSplit) -> bool:
    """A split where the athlete was standing still or barely moving."""
    dist = ls.distance or 0
    time_s = ls.elapsed_time or ls.moving_time or 0
    if dist < 10:
        return True
    if dist > 0 and time_s > 0:
        speed_m_s = dist / time_s
        if speed_m_s < 0.5:
            return True
        # Short segment at running pace is NOT stopped (e.g. partial mile
        # at a Garmin auto-lap boundary)
        if speed_m_s >= 1.5:
            return False
    if dist < 200 and time_s > 30:
        return True
    return False


@dataclass
class _Segment:
    splits: List[LabeledSplit] = field(default_factory=list)
    is_stopped: bool = False

    @property
    def total_distance(self) -> float:
        return sum(s.distance or 0 for s in self.splits)

    @property
    def total_time(self) -> int:
        return sum(s.moving_time or s.elapsed_time or 0 for s in self.splits)

    @property
    def total_elapsed(self) -> int:
        return sum(s.elapsed_time or s.moving_time or 0 for s in self.splits)

    @property
    def weighted_pace(self) -> Optional[float]:
        d = self.total_distance
        t = self.total_time
        if d <= 0 or t <= 0:
            return None
        return (t / d) * 1000

    @property
    def avg_hr(self) -> Optional[int]:
        hrs = [s.average_heartrate for s in self.splits if s.average_heartrate]
        return round(sum(hrs) / len(hrs)) if hrs else None


def _find_pace_gap(sorted_paces: List[float]) -> float:
    """Find the threshold that separates fast (work) from slow (warm up/cool down).

    Looks for the largest gap between consecutive sorted pace values.
    The threshold is placed in the middle of that gap.
    """
    if len(sorted_paces) < 2:
        return sorted_paces[0] if sorted_paces else 0

    best_gap = 0.0
    best_mid = sorted_paces[0]
    for i in range(len(sorted_paces) - 1):
        gap = sorted_paces[i + 1] - sorted_paces[i]
        if gap > best_gap:
            best_gap = gap
            best_mid = (sorted_paces[i] + sorted_paces[i + 1]) / 2

    if best_gap < sorted_paces[0] * 0.1:
        return sorted_paces[len(sorted_paces) // 2]

    return best_mid


def _split_mixed_segments(segments: List[_Segment]) -> List[_Segment]:
    """Split a running segment that contains a large internal pace shift.

    Example: warm-up miles at 9:00/mi followed by threshold miles at 6:30/mi
    in one continuous segment (no stop between them). We detect the transition
    and split into two segments so the warm-up gets labeled correctly.
    """
    result: List[_Segment] = []
    for seg in segments:
        if seg.is_stopped or len(seg.splits) < 3:
            result.append(seg)
            continue

        split_paces = []
        for ls in seg.splits:
            p = ls.pace_sec_per_km
            if p is not None:
                split_paces.append((ls, p))

        if len(split_paces) < 3:
            result.append(seg)
            continue

        fastest = min(p for _, p in split_paces)
        slowest = max(p for _, p in split_paces)
        if slowest <= 0 or (slowest - fastest) / slowest < 0.15:
            result.append(seg)
            continue

        threshold = (fastest + slowest) / 2
        best_split_point = None
        best_ratio = 0.0

        for k in range(1, len(seg.splits)):
            before = seg.splits[:k]
            after = seg.splits[k:]
            b_dist = sum(s.distance or 0 for s in before)
            b_time = sum(s.moving_time or s.elapsed_time or 0 for s in before)
            a_dist = sum(s.distance or 0 for s in after)
            a_time = sum(s.moving_time or s.elapsed_time or 0 for s in after)
            if b_dist <= 0 or a_dist <= 0:
                continue
            b_pace = (b_time / b_dist) * 1000
            a_pace = (a_time / a_dist) * 1000
            diff = abs(b_pace - a_pace)
            mean = (b_pace + a_pace) / 2
            if mean <= 0:
                continue
            ratio = diff / mean
            if ratio > best_ratio:
                best_ratio = ratio
                best_split_point = k

        if best_split_point is not None and best_ratio > 0.15:
            seg1 = _Segment(splits=seg.splits[:best_split_point])
            seg2 = _Segment(splits=seg.splits[best_split_point:])
            if seg1.total_distance > 200 and seg2.total_distance > 200:
                result.append(seg1)
                result.append(seg2)
            else:
                result.append(seg)
        else:
            result.append(seg)

    return result


def detect_interval_structure(splits_data: list) -> IntervalAnalysis:
    if not splits_data or len(splits_data) < 3:
        return _passthrough(splits_data or [])

    labeled = [_to_labeled(s) for s in splits_data]

    segments: List[_Segment] = []
    current = _Segment()

    for ls in labeled:
        stopped = _is_stopped(ls)
        if stopped:
            if current.splits:
                segments.append(current)
                current = _Segment()
            seg = _Segment(splits=[ls], is_stopped=True)
            segments.append(seg)
        else:
            current.splits.append(ls)

    if current.splits:
        segments.append(current)

    segments = _split_mixed_segments(segments)

    running_segments = [seg for seg in segments if not seg.is_stopped]
    if len(running_segments) < 2:
        return _passthrough_labeled(labeled)

    paces = [seg.weighted_pace for seg in running_segments if seg.weighted_pace]
    if len(paces) < 2:
        return _passthrough_labeled(labeled)

    sorted_paces = sorted(paces)
    pace_range = sorted_paces[-1] - sorted_paces[0]
    if sorted_paces[0] <= 0 or (pace_range / sorted_paces[0]) < 0.08:
        return _passthrough_labeled(labeled)

    fast_threshold = _find_pace_gap(sorted_paces)
    MIN_WORK_DISTANCE_M = 400
    for seg in running_segments:
        p = seg.weighted_pace
        if p is not None and p < fast_threshold and seg.total_distance >= MIN_WORK_DISTANCE_M:
            seg._is_fast = True
        else:
            seg._is_fast = False

    fast_indices = [i for i, seg in enumerate(segments) if not seg.is_stopped and getattr(seg, '_is_fast', False)]
    if not fast_indices:
        return _passthrough_labeled(labeled)

    first_fast = fast_indices[0]
    last_fast = fast_indices[-1]

    work_num = 0
    for i, seg in enumerate(segments):
        if seg.is_stopped:
            for ls in seg.splits:
                ls.lap_type = "rest"
        elif getattr(seg, '_is_fast', False):
            work_num += 1
            for ls in seg.splits:
                ls.lap_type = "work"
                ls.interval_number = work_num
        elif i < first_fast:
            for ls in seg.splits:
                ls.lap_type = "warm_up"
        elif i > last_fast:
            for ls in seg.splits:
                ls.lap_type = "cool_down"
        else:
            for ls in seg.splits:
                ls.lap_type = "rest"

    if work_num < 1:
        return _passthrough_labeled(labeled)

    work_segs = [seg for seg in segments if not seg.is_stopped and getattr(seg, '_is_fast', False)]
    rest_segs = [seg for seg in segments if seg.is_stopped]

    work_times = [seg.total_time for seg in work_segs]
    work_paces = [seg.weighted_pace for seg in work_segs if seg.weighted_pace]
    work_hrs = [seg.avg_hr for seg in work_segs if seg.avg_hr]
    rest_times = [seg.total_elapsed for seg in rest_segs]
    rest_hrs = [seg.avg_hr for seg in rest_segs if seg.avg_hr]

    avg_work_time = sum(work_times) / len(work_times) if work_times else 0
    avg_work_pace = sum(work_paces) / len(work_paces) if work_paces else None
    avg_rest_time = sum(rest_times) / len(rest_times) if rest_times else None

    fastest_num = None
    slowest_num = None
    if len(work_segs) >= 2:
        best_pace = min(seg.weighted_pace for seg in work_segs if seg.weighted_pace)
        worst_pace = max(seg.weighted_pace for seg in work_segs if seg.weighted_pace)
        for idx, seg in enumerate(work_segs):
            if seg.weighted_pace == best_pace and fastest_num is None:
                fastest_num = idx + 1
            if seg.weighted_pace == worst_pace:
                slowest_num = idx + 1

    desc_parts = [f"{len(work_segs)}\u00d7{_format_duration(int(round(avg_work_time)))}"]
    if avg_work_pace:
        desc_parts.append(f"at {_format_pace_imperial(avg_work_pace)} avg")
    if avg_rest_time and avg_rest_time > 0:
        desc_parts.append(f"{_format_duration(int(round(avg_rest_time)))} rest")

    description = ", ".join(desc_parts) if len(desc_parts) > 1 else desc_parts[0]

    summary = IntervalSummary(
        is_structured=True,
        workout_description=description,
        num_work_intervals=len(work_segs),
        avg_work_pace_sec_per_km=avg_work_pace,
        avg_work_hr=round(sum(work_hrs) / len(work_hrs)) if work_hrs else None,
        avg_rest_duration_s=avg_rest_time,
        avg_rest_hr=round(sum(rest_hrs) / len(rest_hrs)) if rest_hrs else None,
        fastest_interval=fastest_num,
        slowest_interval=slowest_num,
    )

    return IntervalAnalysis(labeled_splits=labeled, summary=summary)


def _passthrough(splits_data: list) -> IntervalAnalysis:
    labeled = [_to_labeled(s) for s in splits_data]
    return IntervalAnalysis(labeled_splits=labeled, summary=IntervalSummary())


def _passthrough_labeled(labeled: List[LabeledSplit]) -> IntervalAnalysis:
    return IntervalAnalysis(labeled_splits=labeled, summary=IntervalSummary())
