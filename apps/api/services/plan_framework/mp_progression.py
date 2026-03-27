"""
MP Progression Planner (T2-3)

Produces a week-by-week MP sequence for marathon-specific and race-specific phases.

Design:
- Alternates Structure A (threshold quality + easy long) and Structure B (MP long, no T)
- MP also appears in the medium-long on select Structure A weeks (second half of block)
- Tracks estimated MP miles so the generator can assert the ≥35-mile minimum before taper
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class MPWeek:
    """Specification for a single week in the MP block."""

    week_in_phase: int
    long_type: str          # "long_mp" | "long"
    medium_long_type: str   # "medium_long_mp" | "medium_long" | "easy"
    target_mp_miles: float  # Estimated MP-pace miles in this week (for cumulative tracking)


class MPProgressionPlanner:
    """
    Builds an alternating Structure A / Structure B sequence for marathon MP phases.

    Structure A (even week_in_phase): easy long + threshold quality + optional MP medium-long
    Structure B (odd week_in_phase):  long_mp + no threshold quality + easy medium-long (recovery)

    The last week of any phase handled upstream as a cutback (T2-4); this planner
    assigns the workout type pattern regardless of cutback status.
    """

    # Estimated MP miles produced by a long_mp session, by tier
    _MP_LONG_BASE: dict = {"low": 8.0, "mid": 10.0, "high": 12.0, "elite": 14.0}
    # Estimated MP miles produced by a medium_long_mp (touch) session
    _MP_TOUCH_MILES: dict = {"low": 4.0, "mid": 6.0, "high": 8.0, "elite": 10.0}

    def build_sequence(self, tier: str, total_mp_weeks: int) -> List[MPWeek]:
        """
        Return a week-by-week MP sequence for the combined MP block
        (marathon_specific + race_specific phases).

        Args:
            tier: Volume tier string ("low", "mid", "high", "elite")
            total_mp_weeks: Total number of weeks in the MP block
        """
        sequence: List[MPWeek] = []
        # When the block starts adding MP touches to medium-long (Structure A weeks)
        ml_mp_start = max(2, total_mp_weeks // 2)

        for wip in range(1, total_mp_weeks + 1):
            structure_b = (wip % 2 == 0)  # Even → Structure B (MP long)

            if structure_b:
                long_type = "long_mp"
                # Medium-long on MP-long weeks is easy recovery (T2-5 alignment)
                ml_type = "easy"
                mp_miles = self._mp_long_miles(tier, wip, total_mp_weeks)
            else:
                long_type = "long"
                # Add MP touch to medium-long in the second half of the block
                if wip >= ml_mp_start:
                    ml_type = "medium_long_mp"
                    mp_miles = float(self._MP_TOUCH_MILES.get(tier, 6.0))
                else:
                    ml_type = "medium_long"
                    mp_miles = 0.0

            sequence.append(MPWeek(
                week_in_phase=wip,
                long_type=long_type,
                medium_long_type=ml_type,
                target_mp_miles=mp_miles,
            ))

        return sequence

    def cumulative_mp_miles(self, sequence: List[MPWeek]) -> float:
        """Sum of estimated MP miles across the entire sequence."""
        return sum(w.target_mp_miles for w in sequence)

    def _mp_long_miles(self, tier: str, wip: int, total: int) -> float:
        """Estimate MP miles in a long_mp run: ramps 0–4mi above the tier base."""
        base = float(self._MP_LONG_BASE.get(tier, 10.0))
        ramp = base + (wip / max(1, total)) * 4.0
        return round(min(ramp, 18.0), 1)
