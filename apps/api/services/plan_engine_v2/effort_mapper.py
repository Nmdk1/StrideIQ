"""
Effort Mapper — internal % → athlete-facing effort text.

The athlete NEVER sees "105% MP" or "90% MP."  They see effort
language from this module.  The percentage system is how the generator
DECIDES what to prescribe; the effort terms are what the athlete READS.

For beginners (<30K/wk or training_age < 1), use sensory cues
("smooth and quick") instead of zone names ("5K effort").

Ref: Algorithm Spec §5, Sandbox doc effort_mapper section.
"""

from __future__ import annotations

from .pace_ladder import format_pace_sec_km, format_pace_range_sec_km


# ── Effort Term Table ────────────────────────────────────────────────
# Ordered from slowest to fastest.  Each entry: (pct_lo, pct_hi, term)
_EFFORT_TABLE = [
    (0,   75,  "very easy"),
    (75,  83,  "easy"),
    (83,  90,  "easy/mod"),
    (90,  94,  "moderate"),
    (94,  97,  "steady"),
    (97,  101, "marathon effort"),
    (101, 104, "half marathon effort"),
    (104, 107, "threshold"),
    (107, 112, "10K effort"),
    (112, 118, "5K effort"),
    (118, 125, "3K effort"),
    (125, 999, "mile effort"),
]

# Sensory cues for beginners (training_age < 1 or < 30K/wk).
_BEGINNER_EFFORT_TABLE = [
    (0,   83,  "easy and relaxed"),
    (83,  94,  "comfortable with purpose"),
    (94,  101, "comfortably hard"),
    (101, 107, "hard but controlled"),
    (107, 118, "smooth and quick"),
    (118, 999, "controlled fast"),
]


def map_effort(pct: int, *, is_beginner: bool = False) -> str:
    """Map internal percentage to athlete-facing effort term.

    Args:
        pct: Percentage of anchor pace (e.g. 105 = threshold-ish).
        is_beginner: Use sensory cues instead of zone names.

    Returns:
        Effort term string for athlete-facing text.
    """
    table = _BEGINNER_EFFORT_TABLE if is_beginner else _EFFORT_TABLE
    for lo, hi, term in table:
        if lo <= pct < hi:
            return term
    return "hard"


def describe_segment(
    pct: int,
    pace_sec_per_km: float,
    *,
    is_beginner: bool = False,
    unit: str = "mi",
) -> str:
    """Build an athlete-facing effort description with optional pace range.

    Returns strings like:
      "threshold (~6:20-6:40/mi)"
      "easy/mod"
      "smooth and quick"

    Paces are suppressed for easy/recovery (no pace shown per spec)
    and for strides/reps (no pace shown per spec).
    """
    effort = map_effort(pct, is_beginner=is_beginner)

    # No pace display for very easy / easy / recovery or fast strides
    if pct < 88 or pct >= 120:
        return effort

    range_sec = _pace_range_width(pct)
    pace_range = format_pace_range_sec_km(pace_sec_per_km, range_sec, unit)
    suffix = "/mi" if unit == "mi" else "/km"
    return f"{effort} (~{pace_range}{suffix})"


def _pace_range_width(pct: int) -> int:
    """Half-width of displayed pace range in seconds, by effort zone."""
    if pct < 95:
        return 15  # moderate / steady: ±15s
    return 10  # marathon effort and faster: ±10s
