"""
Periodizer — phase splitting and week assignment.

All phase structures are derived from three inputs:
  1. Total weeks available
  2. Athlete experience level
  3. Goal event (determines taper length and what "specific" means)

No hardcoded split tables. The proportions come from principles:
  - Taper: 1 week for ≤HM, 2 weeks for marathon, scaled for ultra
  - Specific: ~20-25% of training weeks (min 2)
  - Supportive: ~25-30% of training weeks (min 2 when weeks allow)
  - General: remainder
"""

from __future__ import annotations

import logging
from typing import Optional

from services.fitness_bank import ExperienceLevel

from .models import Phase, PhaseStructure

logger = logging.getLogger(__name__)


def _taper_weeks(goal_event: str) -> int:
    if goal_event in ("50_mile", "100K", "100_mile"):
        return 2
    if goal_event == "marathon":
        return 2
    return 1


def _max_quality(experience: ExperienceLevel) -> int:
    if experience in (ExperienceLevel.EXPERIENCED, ExperienceLevel.ELITE):
        return 2
    return 1


def _split_phases(weeks: int, experience: ExperienceLevel, goal_event: str) -> tuple:
    """Derive (general, supportive, specific, taper) week counts from principles.

    Beginners get proportionally more general phase time.
    Experienced athletes get more supportive and specific time.
    """
    taper = _taper_weeks(goal_event)
    training = max(4, weeks - taper)

    # Specific phase: 20-25% of training weeks, min 2
    specific_pct = 0.20 if experience == ExperienceLevel.BEGINNER else 0.25
    sp = max(2, round(training * specific_pct))

    # Supportive phase: 25-30% of training weeks, min 2 when >=8 training weeks
    supportive_pct = 0.25 if experience == ExperienceLevel.BEGINNER else 0.30
    s = max(2, round(training * supportive_pct)) if training >= 6 else 0

    # General: remainder
    g = training - s - sp

    # Safety: general must be at least 2
    if g < 2 and s > 2:
        s -= (2 - g)
        g = 2
    if g < 2:
        g = 2
        remaining = training - g
        sp = max(1, remaining // 2)
        s = remaining - sp

    return g, s, sp, taper


def build_race_phases(
    goal_event: str,
    weeks: int,
    experience: ExperienceLevel,
) -> PhaseStructure:
    """Build phase structure for any race distance.

    All distances use the same General → Supportive → Specific → Taper
    structure. The goal_event determines what "specific" means (carried
    downstream to workout selection), not the phase structure itself.
    """
    if goal_event in ("50K", "50_mile", "100K", "100_mile"):
        return _build_ultra_phases(weeks, experience, goal_event)

    g, s, sp, taper = _split_phases(weeks, experience, goal_event)
    mq = _max_quality(experience)

    phases = []

    phases.append(Phase(
        name="general", weeks=g,
        focus="Build aerobic base and full-spectrum fitness.",
        quality_density=min(mq, 1),
    ))

    if s > 0:
        phases.append(Phase(
            name="supportive", weeks=s,
            focus="Bridge to race-specific work. Threshold as primary arc.",
            quality_density=mq,
        ))

    phases.append(Phase(
        name="specific", weeks=sp,
        focus=f"Race-pace preparation for {goal_event}.",
        quality_density=mq,
    ))

    phases.append(Phase(
        name="taper", weeks=taper,
        focus="Reduce volume, maintain sharpness.",
        quality_density=1,
    ))

    return PhaseStructure(phases=phases, total_weeks=weeks, mode="race")


def _build_ultra_phases(
    weeks: int,
    experience: ExperienceLevel,
    goal_event: str = "50K",
) -> PhaseStructure:
    """Ultra uses the same derived split logic."""
    g, s, sp, taper = _split_phases(weeks, experience, goal_event)
    mq = _max_quality(experience)

    return PhaseStructure(
        phases=[
            Phase("general", g,
                  "Speed + power + aerobic base.", mq),
            Phase("supportive", s,
                  "Threshold bridge, sustained efforts.", mq),
            Phase("specific", sp,
                  f"Race-specific for {goal_event}: long sustained work, race simulation.", mq),
            Phase("taper", taper,
                  "Reduce volume, maintain one quality session.", 1),
        ],
        total_weeks=weeks,
        mode="race",
    )


def build_build_phases(
    sub_mode: str,
    weeks: int,
    experience: ExperienceLevel,
) -> PhaseStructure:
    """Build phase structure for Build mode sub-configurations."""
    if sub_mode == "build_onramp":
        return PhaseStructure(
            phases=[Phase("onramp", weeks, "Introduction to structured running", 1,
                          ["hill_strides", "flat_intervals", "easy_mod"])],
            total_weeks=weeks,
            mode="build_onramp",
        )

    if sub_mode == "build_volume":
        return PhaseStructure(
            phases=[Phase("build_volume", weeks,
                          "Aerobic development. ONE quality (Wed threshold), distance ranges.", 1,
                          ["threshold_cruise", "easy_mod", "hill_strides"])],
            total_weeks=weeks,
            mode="build_volume",
        )

    if sub_mode == "build_intensity":
        return PhaseStructure(
            phases=[Phase("build", weeks,
                          "Two quality sessions per week. Extension progression.", 2,
                          ["speed_support", "threshold_cruise", "long_fast_stepwise"])],
            total_weeks=weeks,
            mode="build_intensity",
        )

    return PhaseStructure(
        phases=[Phase("general", weeks, "General development", 1)],
        total_weeks=weeks,
        mode=sub_mode,
    )


def build_maintain_phases(weeks: int) -> PhaseStructure:
    return PhaseStructure(
        phases=[Phase("maintain", weeks,
                      "Hold fitness. Rotate quality types. Flat volume.", 1,
                      ["threshold", "intervals", "fartlek", "strides"])],
        total_weeks=weeks,
        mode="maintain",
    )
