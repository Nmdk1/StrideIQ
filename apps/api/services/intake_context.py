"""
Intake Context — Structured representation of onboarding questionnaire data.

The intake questionnaire is the ONLY data source for new athletes without
synced activity history. For experienced athletes with Garmin/Strava data,
it provides self-reported context that supplements the fingerprint.

This module:
1. Defines the IntakeContext dataclass
2. Reads from the intake_questionnaire and athlete tables
3. Provides a clean interface for plan generation to consume

Every plan generation path must read IntakeContext. For beginners, it IS
the athlete profile. Generating a plan without it is irresponsible.
"""

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Dict, List, Optional
from uuid import UUID
import logging

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class PolicyStance(Enum):
    PERFORMANCE_MAXIMAL = "performance_maximal"
    DURABILITY_FIRST = "durability_first"
    RE_ENTRY = "re_entry"


class PainFlag(Enum):
    NONE = "none"
    NIGGLE = "niggle"
    PAIN = "pain"


class RunningExperience(Enum):
    JUST_STARTING = "just_starting"
    LESS_THAN_1_YEAR = "less_than_1_year"
    ONE_TO_3_YEARS = "1_to_3_years"
    THREE_PLUS_YEARS = "3_plus_years"


class SportBackground(Enum):
    SEDENTARY = "sedentary"
    GYM_FITNESS = "gym_fitness"
    TEAM_SPORT = "team_sport"
    ENDURANCE_SPORT = "endurance_sport"
    MULTI_SPORT = "multi_sport"


@dataclass
class IntakeContext:
    """Structured intake data for plan generation.

    Every field is Optional because athletes can skip stages.
    Plan generation code must handle None gracefully — but for beginners
    with no activity history, missing critical fields should block
    plan generation entirely.
    """

    # --- Identity (from Athlete model) ---
    age: Optional[int] = None
    sex: Optional[str] = None
    height_cm: Optional[float] = None

    # --- Running background (from basic_profile stage) ---
    running_experience: Optional[RunningExperience] = None
    current_runs_per_week: Optional[int] = None
    current_longest_run_miles: Optional[float] = None
    sport_background: Optional[SportBackground] = None

    # --- Training constraints (from goals stage) ---
    policy_stance: PolicyStance = PolicyStance.DURABILITY_FIRST
    days_per_week: Optional[int] = None
    time_available_min: Optional[int] = None
    weekly_mileage_target: Optional[float] = None

    # --- Health / injury (from goals stage) ---
    pain_flag: PainFlag = PainFlag.NONE
    injury_context: Optional[str] = None

    # --- Self-reported limiter ---
    limiter_primary: Optional[str] = None

    # --- Work / lifestyle (from work_setup stage) ---
    work_type: Optional[str] = None
    work_hours_per_week: Optional[int] = None

    # --- Completeness tracking ---
    basic_profile_completed: bool = False
    goals_completed: bool = False

    @property
    def has_minimum_for_plan(self) -> bool:
        """Whether enough intake data exists to generate any plan."""
        return self.basic_profile_completed and self.goals_completed

    @property
    def has_minimum_for_beginner_plan(self) -> bool:
        """Whether enough intake data exists for a beginner plan.

        Beginners have no activity history — the intake IS the profile.
        We need at minimum: age, running experience, and current capability.
        """
        return (
            self.basic_profile_completed
            and self.goals_completed
            and self.age is not None
            and self.running_experience is not None
        )

    @property
    def is_beginner_self_reported(self) -> bool:
        """Whether the athlete self-reports as a beginner."""
        if self.running_experience is None:
            return False
        return self.running_experience in (
            RunningExperience.JUST_STARTING,
            RunningExperience.LESS_THAN_1_YEAR,
        )


def get_intake_context(athlete_id: UUID, db: Session) -> IntakeContext:
    """Read intake questionnaire and athlete data, return structured IntakeContext.

    Safe to call for any athlete — returns an IntakeContext with whatever
    data is available. Fields that haven't been collected remain None.
    """
    from models import Athlete, IntakeQuestionnaire

    ctx = IntakeContext()

    athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
    if athlete is None:
        return ctx

    if athlete.birthdate:
        today = date.today()
        ctx.age = (
            today.year - athlete.birthdate.year
            - ((today.month, today.day) < (athlete.birthdate.month, athlete.birthdate.day))
        )
    ctx.sex = athlete.sex
    ctx.height_cm = float(athlete.height_cm) if athlete.height_cm else None

    intake_rows = (
        db.query(IntakeQuestionnaire)
        .filter(IntakeQuestionnaire.athlete_id == athlete_id)
        .all()
    )

    for row in intake_rows:
        responses = row.responses or {}
        stage = row.stage

        if stage == "basic_profile":
            ctx.basic_profile_completed = row.completed_at is not None

            exp = responses.get("running_experience")
            if exp:
                try:
                    ctx.running_experience = RunningExperience(exp)
                except ValueError:
                    pass

            runs_pw = responses.get("current_runs_per_week")
            if runs_pw is not None:
                ctx.current_runs_per_week = int(runs_pw)

            longest = responses.get("current_longest_run_miles")
            if longest is not None:
                ctx.current_longest_run_miles = float(longest)

            bg = responses.get("sport_background")
            if bg:
                try:
                    ctx.sport_background = SportBackground(bg)
                except ValueError:
                    pass

        elif stage == "goals":
            ctx.goals_completed = row.completed_at is not None

            stance = responses.get("policy_stance")
            if stance:
                try:
                    ctx.policy_stance = PolicyStance(stance)
                except ValueError:
                    pass

            dpw = responses.get("days_per_week")
            if dpw is not None:
                ctx.days_per_week = int(dpw)

            ta = responses.get("time_available_min")
            if ta is not None:
                ctx.time_available_min = int(ta)

            wmt = responses.get("weekly_mileage_target")
            if wmt is not None:
                ctx.weekly_mileage_target = float(wmt)

            pf = responses.get("pain_flag")
            if pf:
                try:
                    ctx.pain_flag = PainFlag(pf)
                except ValueError:
                    pass

            ctx.injury_context = responses.get("injury_context")
            ctx.limiter_primary = responses.get("limiter_primary")

        elif stage == "work_setup":
            ctx.work_type = responses.get("work_type")
            wh = responses.get("work_hours")
            if wh is not None:
                ctx.work_hours_per_week = int(wh)

    return ctx
