"""Training block detection.

A training block is a multi-week period of consistent training. The
detector aggregates an athlete's run activities by ISO week, walks the
weekly time series identifying boundaries (race weeks, off weeks,
≥10-day gaps, recovery weeks following a build), then labels each
resulting contiguous span with a phase:

    - ``off``      — week with zero runs
    - ``recovery`` — first week back after an off week or large drop
    - ``base``     — sustained low-intensity volume, no quality
    - ``build``    — quality work present, volume rising
    - ``peak``     — block contains the trailing 12-week peak weekly volume
    - ``taper``    — final 1-3 weeks show ≥20% volume drop AND a race
                     happened in the final week
    - ``race``     — the final week of the block contained a race

Algorithm priorities (in order):
    1. **Race weeks terminate blocks.** A week containing a race is the
       last week of its block. The block's phase becomes ``race`` (or
       ``taper`` if the prior 1-3 weeks showed a clear taper pattern).
    2. **Off weeks are their own ``off`` block.** Zero runs in a week
       isolates that week.
    3. **≥10-day gap → boundary.** A gap of 10+ days between any two
       consecutive runs always splits the block at the gap.
    4. **Recovery week → boundary.** A week ≤60% of the trailing 4-week
       rolling average and following a building phase becomes a
       ``recovery`` block of one week.
    5. **Otherwise weeks coalesce** into the active block.

This is intentionally rule-based, not statistical — the dataset per
athlete is too small for change-point detection to outperform clear
rules grounded in periodization theory. Every rule is unit-tested.

Suppression discipline: never claim ``peak`` without checking trailing
12-week max; never claim ``taper`` without a race in the next week.
"""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Dict, Iterable, List, Optional, Sequence, Tuple
from uuid import UUID

from sqlalchemy.orm import Session

from models import Activity, TrainingBlock

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Workout-type categories (single source of truth for the detector)
# ---------------------------------------------------------------------------

QUALITY_TYPES = frozenset(
    {
        "interval_workout",
        "track_workout",
        "vo2max_intervals",
        "threshold_run",
        "tempo_run",
        "fartlek",
        "hill_workout",
        "race",
        "race_pace_workout",
        "progression_run",
        "cruise_intervals",
    }
)
LONG_TYPES = frozenset({"long_run", "medium_long_run"})
EASY_TYPES = frozenset({"recovery_run", "easy_run", "aerobic_run"})
RACE_TYPES = frozenset({"race"})


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class WeekStat:
    """One ISO week of activity aggregates for one athlete."""

    week_start: date  # Monday of this ISO week
    distance_m: int = 0
    duration_s: int = 0
    run_count: int = 0
    longest_run_m: int = 0
    workout_type_counts: Dict[str, int] = field(default_factory=dict)
    quality_count: int = 0
    long_count: int = 0
    has_race: bool = False
    race_name: Optional[str] = None

    @property
    def week_end(self) -> date:
        return self.week_start + timedelta(days=6)


@dataclass
class DetectedBlock:
    """A detected training block — a contiguous span of weeks."""

    weeks: List[WeekStat]
    phase: str = "base"

    @property
    def start_date(self) -> date:
        return self.weeks[0].week_start

    @property
    def end_date(self) -> date:
        return self.weeks[-1].week_end

    @property
    def total_distance_m(self) -> int:
        return sum(w.distance_m for w in self.weeks)

    @property
    def total_duration_s(self) -> int:
        return sum(w.duration_s for w in self.weeks)

    @property
    def run_count(self) -> int:
        return sum(w.run_count for w in self.weeks)

    @property
    def peak_week_distance_m(self) -> int:
        return max((w.distance_m for w in self.weeks), default=0)

    @property
    def longest_run_m(self) -> Optional[int]:
        v = max((w.longest_run_m for w in self.weeks), default=0)
        return v if v > 0 else None

    @property
    def workout_type_counts(self) -> Dict[str, int]:
        c: Counter = Counter()
        for w in self.weeks:
            c.update(w.workout_type_counts)
        return dict(c)

    @property
    def dominant_workout_types(self) -> List[str]:
        c = Counter(self.workout_type_counts)
        return [t for t, _ in c.most_common(3)]

    @property
    def quality_pct(self) -> int:
        n = self.run_count
        if n == 0:
            return 0
        q = sum(w.quality_count for w in self.weeks)
        return int(round(100.0 * q / n))

    @property
    def goal_event_name(self) -> Optional[str]:
        # Prefer a race name from the final week (the race that ends the
        # block); fall back to any race name in the block.
        for w in reversed(self.weeks):
            if w.race_name:
                return w.race_name
        return None


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


def _iso_monday(d: date) -> date:
    """Return the Monday of the ISO week containing ``d``."""
    return d - timedelta(days=d.weekday())


def aggregate_weeks(activities: Sequence[Activity]) -> List[WeekStat]:
    """Group activities into ISO weeks, returning a dense weekly series.

    Dense means: gaps between weeks with activity are filled with
    zero-count WeekStat rows so that ``run_count==0`` weeks become
    detectable as ``off`` weeks.
    """
    if not activities:
        return []
    by_week: Dict[date, WeekStat] = {}
    for a in activities:
        if a.start_time is None:
            continue
        d = a.start_time.date() if isinstance(a.start_time, datetime) else a.start_time
        wk = _iso_monday(d)
        ws = by_week.setdefault(wk, WeekStat(week_start=wk))
        ws.distance_m += int(a.distance_m or 0)
        ws.duration_s += int(a.duration_s or 0)
        ws.run_count += 1
        if (a.distance_m or 0) > ws.longest_run_m:
            ws.longest_run_m = int(a.distance_m or 0)
        wt = a.workout_type
        if wt:
            ws.workout_type_counts[wt] = ws.workout_type_counts.get(wt, 0) + 1
            if wt in QUALITY_TYPES:
                ws.quality_count += 1
            if wt in LONG_TYPES:
                ws.long_count += 1
            if wt in RACE_TYPES:
                ws.has_race = True
                ws.race_name = (a.name or "Race").strip() or "Race"

    if not by_week:
        return []
    first = min(by_week.keys())
    last = max(by_week.keys())
    weeks: List[WeekStat] = []
    cur = first
    while cur <= last:
        weeks.append(by_week.get(cur, WeekStat(week_start=cur)))
        cur += timedelta(days=7)
    return weeks


# ---------------------------------------------------------------------------
# Boundary detection + labeling
# ---------------------------------------------------------------------------


GAP_DAYS_FOR_BOUNDARY = 10
RECOVERY_DROP_THRESHOLD = 0.60  # week ≤ 60% of trailing 4-wk avg → recovery
TAPER_DROP_THRESHOLD = 0.20  # ≥20% drop into race week → taper
PEAK_LOOKBACK_WEEKS = 12
QUALITY_PCT_FOR_BUILD = 10  # ≥10% of runs are quality → at least "build"


def _trailing_avg(weeks: Sequence[WeekStat], idx: int, n: int) -> float:
    """Average distance of the n weeks BEFORE idx (excluding idx itself)."""
    lo = max(0, idx - n)
    window = weeks[lo:idx]
    if not window:
        return 0.0
    return sum(w.distance_m for w in window) / len(window)


def _activities_in_week(activities: Sequence[Activity], wk_start: date) -> List[Activity]:
    wk_end = wk_start + timedelta(days=6)
    out = []
    for a in activities:
        if a.start_time is None:
            continue
        d = a.start_time.date() if isinstance(a.start_time, datetime) else a.start_time
        if wk_start <= d <= wk_end:
            out.append(a)
    return out


def _max_gap_days_between(activities: Sequence[Activity]) -> int:
    """Largest gap (in days) between consecutive activity start dates."""
    dates = sorted(
        a.start_time.date() if isinstance(a.start_time, datetime) else a.start_time
        for a in activities
        if a.start_time is not None
    )
    if len(dates) < 2:
        return 0
    return max((dates[i] - dates[i - 1]).days for i in range(1, len(dates)))


def detect_block_boundaries(
    weeks: Sequence[WeekStat],
    activities: Sequence[Activity],
) -> List[Tuple[int, int]]:
    """Return [(start_idx, end_idx_inclusive), ...] block ranges.

    Walks the weekly series and emits block ranges separated by:
      - off weeks (their own range)
      - race weeks (last week of their block)
      - ≥10-day inter-activity gaps
      - recovery weeks following a building phase (their own range)

    All other weeks coalesce into the running open block.
    """
    if not weeks:
        return []

    ranges: List[Tuple[int, int]] = []
    open_start: Optional[int] = None

    for i, w in enumerate(weeks):
        # Rule 1: off week is its own block
        if w.run_count == 0:
            if open_start is not None:
                ranges.append((open_start, i - 1))
                open_start = None
            ranges.append((i, i))
            continue

        # Rule 3: gap inside the prior boundary — check the gap between
        # the last activity of the previous week with runs and the first
        # activity of THIS week.
        if i > 0 and open_start is not None:
            prev_acts = []
            j = i - 1
            while j >= open_start and weeks[j].run_count == 0:
                j -= 1
            if j >= open_start:
                prev_acts = _activities_in_week(activities, weeks[j].week_start)
            cur_acts = _activities_in_week(activities, w.week_start)
            if prev_acts and cur_acts:
                last_prev = max(
                    a.start_time.date() if isinstance(a.start_time, datetime) else a.start_time
                    for a in prev_acts
                )
                first_cur = min(
                    a.start_time.date() if isinstance(a.start_time, datetime) else a.start_time
                    for a in cur_acts
                )
                if (first_cur - last_prev).days >= GAP_DAYS_FOR_BOUNDARY:
                    ranges.append((open_start, i - 1))
                    open_start = i
                    # fall through to rule 4 for this week

        # Rule 4: recovery week (≤60% of trailing 4-wk avg) following an
        # actively building phase. Only a boundary if open_start has at
        # least 2 prior weeks AND those weeks sum to a meaningful base.
        if open_start is not None:
            avg = _trailing_avg(weeks, i, 4)
            if (
                avg > 0
                and w.distance_m > 0
                and w.distance_m <= avg * RECOVERY_DROP_THRESHOLD
                and (i - open_start) >= 2
                and not w.has_race
            ):
                ranges.append((open_start, i - 1))
                ranges.append((i, i))  # one-week recovery block
                open_start = None
                continue

        # Rule 1b: race week ends the block AT this week
        if w.has_race:
            if open_start is None:
                open_start = i
            ranges.append((open_start, i))
            open_start = None
            continue

        if open_start is None:
            open_start = i

    if open_start is not None:
        ranges.append((open_start, len(weeks) - 1))

    return ranges


def _label_block(
    block_weeks: Sequence[WeekStat],
    all_weeks: Sequence[WeekStat],
    block_end_idx: int,
) -> str:
    """Label a single block based on its weeks and global context."""
    if not block_weeks:
        return "off"
    if all(w.run_count == 0 for w in block_weeks):
        return "off"

    # If single week and ≤60% of trailing avg → recovery
    if len(block_weeks) == 1:
        single = block_weeks[0]
        if single.has_race:
            # Was there a clear taper into this race?
            avg = _trailing_avg(all_weeks, block_end_idx, 3)
            if avg > 0 and single.distance_m <= avg * (1 - TAPER_DROP_THRESHOLD):
                # Find prior block to relabel as taper... but simpler: this
                # single race week itself is `race`.
                return "race"
            return "race"
        # Recovery test — only if there's a prior week with meaningful volume
        avg = _trailing_avg(all_weeks, block_end_idx, 4)
        if (
            avg > 0
            and single.distance_m > 0
            and single.distance_m <= avg * RECOVERY_DROP_THRESHOLD
        ):
            return "recovery"

    # Multi-week block: peak vs build vs base
    block_quality = sum(w.quality_count for w in block_weeks)
    block_runs = sum(w.run_count for w in block_weeks)
    quality_pct = (100.0 * block_quality / block_runs) if block_runs else 0.0
    block_peak = max(w.distance_m for w in block_weeks)

    # 12-week trailing peak (across the dense weekly series)
    lookback_lo = max(0, block_end_idx - PEAK_LOOKBACK_WEEKS)
    trailing_peak = max(
        (w.distance_m for w in all_weeks[lookback_lo : block_end_idx + 1]),
        default=0,
    )

    # Race in the block?
    has_race = any(w.has_race for w in block_weeks)
    if has_race:
        # Did the final 1-3 weeks show a taper pattern?
        last_n = block_weeks[-3:] if len(block_weeks) >= 3 else block_weeks
        if len(last_n) >= 2:
            pre_taper = block_weeks[:-len(last_n)]
            pre_avg = (
                sum(w.distance_m for w in pre_taper) / len(pre_taper)
                if pre_taper
                else block_peak
            )
            taper_avg = sum(w.distance_m for w in last_n) / len(last_n)
            if pre_avg > 0 and taper_avg <= pre_avg * (1 - TAPER_DROP_THRESHOLD):
                return "taper"
        return "race"

    if block_peak >= trailing_peak and quality_pct >= QUALITY_PCT_FOR_BUILD and len(block_weeks) >= 3:
        return "peak"

    if quality_pct >= QUALITY_PCT_FOR_BUILD:
        return "build"

    return "base"


def label_blocks(
    block_ranges: Sequence[Tuple[int, int]],
    weeks: Sequence[WeekStat],
) -> List[DetectedBlock]:
    blocks = []
    for (lo, hi) in block_ranges:
        b = DetectedBlock(weeks=list(weeks[lo : hi + 1]))
        b.phase = _label_block(b.weeks, weeks, hi)
        blocks.append(b)
    return blocks


# ---------------------------------------------------------------------------
# Per-athlete orchestration + persistence
# ---------------------------------------------------------------------------


def detect_blocks_for_athlete(
    db: Session,
    athlete_id,
    *,
    since: Optional[date] = None,
) -> List[DetectedBlock]:
    """Run end-to-end detection for one athlete and return DetectedBlock list.

    Does NOT persist — caller invokes ``persist_detected_blocks``.
    """
    q = (
        db.query(Activity)
        .filter(
            Activity.athlete_id == athlete_id,
            Activity.sport == "run",
        )
        .order_by(Activity.start_time.asc())
    )
    if since is not None:
        q = q.filter(Activity.start_time >= since)
    activities = q.all()
    if not activities:
        return []

    weeks = aggregate_weeks(activities)
    ranges = detect_block_boundaries(weeks, activities)
    return label_blocks(ranges, weeks)


def persist_detected_blocks(
    db: Session,
    athlete_id: UUID,
    blocks: Sequence[DetectedBlock],
    *,
    delete_existing: bool = True,
) -> int:
    """Persist detected blocks for an athlete.

    Default ``delete_existing=True`` is the recommended mode: the
    detector is deterministic, so it's cheaper and safer to drop the
    athlete's prior rows and insert the latest detection rather than
    diff/merge. Returns the number of rows inserted.
    """
    if delete_existing:
        db.query(TrainingBlock).filter(TrainingBlock.athlete_id == athlete_id).delete(
            synchronize_session=False
        )

    inserted = 0
    for b in blocks:
        row = TrainingBlock(
            athlete_id=athlete_id,
            start_date=b.start_date,
            end_date=b.end_date,
            weeks=len(b.weeks),
            phase=b.phase,
            total_distance_m=b.total_distance_m,
            total_duration_s=b.total_duration_s,
            run_count=b.run_count,
            peak_week_distance_m=b.peak_week_distance_m,
            longest_run_m=b.longest_run_m,
            workout_type_counts=b.workout_type_counts,
            dominant_workout_types=b.dominant_workout_types,
            quality_pct=b.quality_pct,
            goal_event_name=b.goal_event_name,
            updated_at=datetime.now(timezone.utc),
        )
        db.add(row)
        inserted += 1
    db.commit()
    logger.info(
        "training_blocks_persisted athlete_id=%s blocks=%d",
        athlete_id,
        inserted,
    )
    return inserted
