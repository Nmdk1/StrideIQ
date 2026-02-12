"""
Plan Validation Helpers — Shared assertion functions for plan quality.

These encode the coaching rules from the knowledge base as executable assertions.
Every rule has a unique ID that traces back to the KB source.

Usage:
    from tests.plan_validation_helpers import PlanValidator

    plan = generator.generate_standard(distance="marathon", ...)

    # 1-PRE: relaxed mode (documents gaps without drowning in failures)
    validator = PlanValidator(plan, strict=False)
    validator.assert_all()

    # 1B: strict mode (spec values from the build plan)
    validator = PlanValidator(plan, strict=True)
    validator.assert_all()

Sources:
    - _AI_CONTEXT_/KNOWLEDGE_BASE/PLAN_GENERATION_FRAMEWORK.md (Part 4 checklist)
    - _AI_CONTEXT_/KNOWLEDGE_BASE/coaches/source_B/PHILOSOPHY.md (volume limits)
    - _AI_CONTEXT_/KNOWLEDGE_BASE/02_PERIODIZATION.md (phase rules)
    - _AI_CONTEXT_/KNOWLEDGE_BASE/TRAINING_METHODOLOGY.md (distance emphasis)
    - _AI_CONTEXT_/KNOWLEDGE_BASE/coaches/verde_tc/PHILOSOPHY.md (philosophy)
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Set
import re


# Workout type classifications
QUALITY_TYPES = {
    "threshold", "threshold_intervals", "intervals",
    "long_mp", "hills", "repetitions", "tempo",
}
# long_mp is already in QUALITY_TYPES; HARD_TYPES is an alias here,
# kept separate for clarity if the sets ever diverge.
HARD_TYPES = QUALITY_TYPES.copy()
EASY_TYPES = {"easy", "easy_strides", "recovery", "medium_long", "strides"}
REST_TYPES = {"rest"}
# long_mp is race-specific quality — the MP portion is checked under MP
# limits.  Only easy long runs are subject to the long-run % rule.
LONG_TYPES = {"long"}
THRESHOLD_TYPES = {"threshold", "threshold_intervals", "tempo"}
INTERVAL_TYPES = {"intervals"}
MP_TYPES = {"long_mp"}

# Phases where threshold work should NOT appear
NO_THRESHOLD_PHASES = {"base", "base_speed"}
# Phases where MP long runs are expected (marathon only)
MP_LONG_PHASES = {"marathon_specific", "race_specific"}


# ------------------------------------------------------------------
# Thresholds: spec values (strict) vs relaxed values (1-PRE)
# ------------------------------------------------------------------

# Strict = exact values from PLAN_GENERATION_FRAMEWORK.md / Source B.
# Relaxed = wider band so 1-PRE catches structural gaps without
# drowning in "14% > 10%" noise from the current generator.
# Phase 1B MUST use strict=True when the generator is fixed.
_THRESHOLDS = {
    "strict": {
        "long_run_pct": 0.30,       # Source B: long ≤ 30%
        "threshold_pct": 0.10,      # Source B: T ≤ 10%
        "interval_pct": 0.08,       # Source B: I ≤ 8%
        "interval_abs_mi": 6.2,     # Source B: I ≤ 10K
        "mp_pct": 0.20,             # Source B: MP ≤ 20%
        "mp_abs_mi": 18,            # Source B: MP ≤ 18mi
        "easy_floor_pct": 0.65,     # Source B: easy ≥ 65%
        "volume_jump_pct": 0.15,    # B4: ≤ 15%/week
        "mp_total_min_mi": 40,      # MP-TOTAL: ≥ 40mi
    },
    "relaxed": {
        "long_run_pct": 0.35,       # +5% buffer for current generator
        "threshold_pct": 0.12,      # +2% buffer
        "interval_pct": 0.10,       # +2% buffer
        "interval_abs_mi": 6.5,     # +0.3mi buffer
        "mp_pct": 0.25,             # +5% buffer
        "mp_abs_mi": 20,            # +2mi buffer
        "easy_floor_pct": 0.55,     # -10% buffer
        "volume_jump_pct": 0.20,    # +5% buffer
        "mp_total_min_mi": 20,      # -20mi buffer (current gen ~40-50)
    },
}


@dataclass
class ValidationFailure:
    """A single validation failure with context."""
    rule_id: str
    message: str
    week: Optional[int] = None
    day: Optional[int] = None
    details: Optional[Dict] = None


@dataclass
class ValidationResult:
    """Result of running all validations on a plan."""
    plan_description: str
    failures: List[ValidationFailure] = field(default_factory=list)
    warnings: List[ValidationFailure] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return len(self.failures) == 0

    def summary(self) -> str:
        lines = [f"Plan: {self.plan_description}"]
        lines.append(f"  Failures: {len(self.failures)}")
        lines.append(f"  Warnings: {len(self.warnings)}")
        for f in self.failures:
            week_ctx = f"  Week {f.week}" if f.week else ""
            lines.append(f"  FAIL [{f.rule_id}]{week_ctx}: {f.message}")
        for w in self.warnings:
            week_ctx = f"  Week {w.week}" if w.week else ""
            lines.append(f"  WARN [{w.rule_id}]{week_ctx}: {w.message}")
        return "\n".join(lines)


class PlanValidator:
    """
    Validates a GeneratedPlan against all coaching rules from the KB.

    Each assert_* method checks one or more rules and appends failures
    to the result. Call assert_all() to run every rule.

    Args:
        plan: A GeneratedPlan object from the framework generator.
        strict: If True, use exact spec values from the build plan.
                If False (default), use relaxed values for 1-PRE gap discovery.
                Phase 1B MUST flip this to True.
    """

    def __init__(self, plan, *, strict: bool = False, profile=None):
        self.plan = plan
        self.strict = strict
        self.profile = profile  # Optional AthleteProfile for N=1 overrides
        self._t = _THRESHOLDS["strict"] if strict else _THRESHOLDS["relaxed"]
        self.result = ValidationResult(
            plan_description=(
                f"{plan.distance} | {plan.volume_tier} | "
                f"{plan.duration_weeks}w | {plan.days_per_week}d/w"
                f"{' [STRICT]' if strict else ''}"
                f"{' [N=1]' if profile else ''}"
            )
        )

    def _fail(self, rule_id: str, message: str, week: int = None,
              day: int = None, details: Dict = None):
        self.result.failures.append(
            ValidationFailure(rule_id, message, week, day, details)
        )

    def _warn(self, rule_id: str, message: str, week: int = None,
              day: int = None, details: Dict = None):
        self.result.warnings.append(
            ValidationFailure(rule_id, message, week, day, details)
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_week_workouts(self, week_num: int):
        return [w for w in self.plan.workouts if w.week == week_num]

    def _get_non_rest_workouts(self, week_num: int):
        return [w for w in self._get_week_workouts(week_num)
                if w.workout_type not in REST_TYPES]

    def _get_phase_for_week(self, week_num: int) -> Optional[str]:
        for phase in self.plan.phases:
            if week_num in phase.weeks:
                return phase.phase_type.value
        return None

    def _week_total_miles(self, week_num: int) -> float:
        return sum(
            w.distance_miles or 0
            for w in self._get_week_workouts(week_num)
        )

    def _week_workout_miles_by_type(self, week_num: int, types: Set[str]) -> float:
        return sum(
            w.distance_miles or 0
            for w in self._get_week_workouts(week_num)
            if w.workout_type in types
        )

    def _is_quality_day(self, workout) -> bool:
        return workout.workout_type in QUALITY_TYPES

    def _is_hard_day(self, workout) -> bool:
        return workout.workout_type in HARD_TYPES

    @staticmethod
    def _quality_miles(workout, quality_paces: Set[str]) -> float:
        """Extract quality-specific miles from segments when available.

        In coaching science, Source B limits (T ≤ 10%, I ≤ 8%, MP ≤ 20%)
        apply to the INTENSITY-SPECIFIC volume, not the total session.
        A threshold session with 2mi warmup + 5mi at T + 1.5mi cooldown
        is 8.5mi total but only 5mi of threshold WORK.  Warmup/cooldown
        are easy running.

        When segments are available, sum only those whose ``pace`` is in
        *quality_paces*.  Fall back to ``distance_miles`` when segments
        are absent (conservative).
        """
        segs = getattr(workout, "segments", None)
        if segs:
            total = 0.0
            for s in segs:
                pace = (s.get("pace") or "").lower()
                if pace in quality_paces:
                    total += s.get("distance_miles", 0) or 0
            if total > 0:
                return total
        # Fallback: use total distance (conservative)
        return workout.distance_miles or 0

    # ------------------------------------------------------------------
    # RULE GROUP: Source B Volume Limits
    # ------------------------------------------------------------------

    def assert_source_b_limits(self):
        """
        Rules B1-*: Source B workout volume limits per session.

        Spec values (strict=True):
            Long run ≤ 30%, Threshold ≤ 10%, Intervals ≤ 8% (& ≤ 6.2mi),
            MP ≤ 20% (& ≤ 18mi).

        Relaxed values (strict=False, 1-PRE):
            Long run ≤ 35%, Threshold ≤ 12%, Intervals ≤ 10% (& ≤ 6.5mi),
            MP ≤ 25% (& ≤ 20mi).

        N=1 overrides (when profile is provided):
            - LR%: relaxed to 35% when profile shows established long run practice
            - MP%: relaxed to 30% for builder/low tier (MP sessions can't be
              shorter than useful; low volume inflates the percentage)
        """
        lr_cap = self._t["long_run_pct"]
        t_cap = self._t["threshold_pct"]
        i_cap = self._t["interval_pct"]
        i_abs = self._t["interval_abs_mi"]
        mp_cap = self._t["mp_pct"]
        mp_abs = self._t["mp_abs_mi"]

        # N=1 profile overrides for tier-aware limits
        if self.profile:
            tier_val = self.profile.volume_tier.value
            # MP%: builder/low tiers at low volume can't avoid high MP%
            # because the MP session has a coaching-correct minimum length.
            if tier_val in ("builder", "low"):
                mp_cap = max(mp_cap, 0.30)
            # LR%: if athlete has established long run practice, allow up to 35%
            if self.profile.long_run_confidence >= 0.6:
                lr_cap = max(lr_cap, 0.35)

        for week in range(1, self.plan.duration_weeks + 1):
            week_miles = self._week_total_miles(week)
            if week_miles <= 0:
                continue

            # Long run % is a build/peak guideline.  Skip for:
            # - Taper/race weeks (volume is deliberately low)
            # - Cutback weeks (recovery structure, not a training gap)
            # - Very low volume weeks (<30mi) where a 10mi long run is
            #   the floor for meaningful marathon training, not a bug.
            phase = self._get_phase_for_week(week)
            skip_lr_pct = phase in {"taper", "race"} or week_miles < 30

            workouts = self._get_week_workouts(week)

            for w in workouts:
                total_miles = w.distance_miles or 0
                if total_miles <= 0:
                    continue

                wtype = w.workout_type

                # Long run ≤ spec%  (total distance is correct — the whole
                # run is at long-run effort, no warmup/cooldown split)
                if wtype in LONG_TYPES and not skip_lr_pct and total_miles > week_miles * lr_cap:
                    self._fail(
                        "B1-LR-PCT",
                        f"Long run {total_miles:.1f}mi > {lr_cap*100:.0f}% of weekly "
                        f"{week_miles:.1f}mi ({total_miles/week_miles*100:.0f}%)",
                        week=week
                    )

                # Threshold ≤ spec%  (quality miles only — warmup/cooldown
                # are easy running and count toward easy volume)
                if wtype in THRESHOLD_TYPES:
                    q_miles = self._quality_miles(w, {"threshold", "t"})
                    if q_miles > week_miles * t_cap:
                        self._fail(
                            "B1-T-PCT",
                            f"Threshold work {q_miles:.1f}mi > {t_cap*100:.0f}% of weekly "
                            f"{week_miles:.1f}mi ({q_miles/week_miles*100:.0f}%)",
                            week=week
                        )

                # Intervals ≤ spec% and ≤ abs mi (quality miles only)
                if wtype in INTERVAL_TYPES:
                    q_miles = self._quality_miles(w, {"interval", "intervals", "vo2max", "vo2"})
                    if q_miles > week_miles * i_cap:
                        self._fail(
                            "B1-I-PCT",
                            f"Intervals work {q_miles:.1f}mi > {i_cap*100:.0f}% of weekly "
                            f"{week_miles:.1f}mi",
                            week=week
                        )
                    if q_miles > i_abs:
                        self._fail(
                            "B1-I-ABS",
                            f"Intervals work {q_miles:.1f}mi > {i_abs}mi absolute limit",
                            week=week
                        )

                # MP ≤ spec% and ≤ abs mi (quality miles only)
                if wtype in MP_TYPES:
                    q_miles = self._quality_miles(w, {"mp", "marathon_pace"})
                    if q_miles > week_miles * mp_cap:
                        self._fail(
                            "B1-MP-PCT",
                            f"MP work {q_miles:.1f}mi > {mp_cap*100:.0f}% of weekly "
                            f"{week_miles:.1f}mi",
                            week=week
                        )
                    if q_miles > mp_abs:
                        self._fail(
                            "B1-MP-ABS",
                            f"MP work {q_miles:.1f}mi > {mp_abs}mi absolute limit",
                            week=week
                        )

    # ------------------------------------------------------------------
    # RULE GROUP: Easy Running Distribution
    # ------------------------------------------------------------------

    def assert_easy_distribution(self):
        """
        Rule B2/C1/VAL-EASY-PCT: Easy running ≥ spec% of weekly volume.

        Spec (strict): ≥ 65%.  Relaxed (1-PRE): ≥ 55%.

        Counts ALL easy-effort running including warmup/cooldown segments
        from quality sessions.  A threshold session with 2mi WU + 5mi T +
        1.5mi CD contributes 3.5mi to easy volume.
        """
        easy_floor = self._t["easy_floor_pct"]

        # Paces that count as easy effort in segments
        _EASY_PACES = {"easy", "recovery", "warmup", "cooldown"}

        for week in range(1, self.plan.duration_weeks + 1):
            week_miles = self._week_total_miles(week)
            if week_miles < 5:
                continue  # Skip very low volume weeks

            # Explicit parentheses: (EASY_TYPES | LONG_TYPES) - MP_TYPES
            easy_eligible = (EASY_TYPES | LONG_TYPES) - MP_TYPES

            easy_miles = 0.0
            for w in self._get_week_workouts(week):
                if w.workout_type in easy_eligible:
                    # Entire workout is easy effort
                    easy_miles += w.distance_miles or 0
                elif w.workout_type in (QUALITY_TYPES | MP_TYPES):
                    # Quality session — count only easy segments (WU/CD)
                    segs = getattr(w, "segments", None)
                    if segs:
                        for s in segs:
                            pace = (s.get("pace") or "").lower()
                            seg_type = (s.get("type") or "").lower()
                            if pace in _EASY_PACES or seg_type in {"warmup", "cooldown"}:
                                easy_miles += s.get("distance_miles", 0) or 0

            easy_pct = easy_miles / week_miles if week_miles > 0 else 1.0

            if easy_pct < easy_floor:
                self._fail(
                    "B2-EASY-LOW",
                    f"Easy running {easy_pct*100:.0f}% < {easy_floor*100:.0f}% minimum "
                    f"({easy_miles:.1f}/{week_miles:.1f}mi)",
                    week=week
                )

    # ------------------------------------------------------------------
    # RULE GROUP: Weekly Structure — Hard-Easy Pattern
    # ------------------------------------------------------------------

    def assert_hard_easy_pattern(self):
        """
        Rule A3/VAL-HARD-RECOVERY: Hard day must be followed by easy or rest.
        Never back-to-back hard days.
        """
        for week in range(1, self.plan.duration_weeks + 1):
            workouts = sorted(
                self._get_week_workouts(week), key=lambda w: w.day
            )
            for i, w in enumerate(workouts):
                if self._is_hard_day(w) and i + 1 < len(workouts):
                    next_w = workouts[i + 1]
                    if self._is_hard_day(next_w):
                        self._fail(
                            "A3-HARD-EASY",
                            f"Back-to-back hard days: {w.day_name} ({w.workout_type}) "
                            f"-> {next_w.day_name} ({next_w.workout_type})",
                            week=week
                        )

    # ------------------------------------------------------------------
    # RULE GROUP: Quality Day Limit
    # ------------------------------------------------------------------

    def assert_quality_day_limit(self):
        """
        Rule A3/VAL-NO-3-QUALITY: Never 3 quality days in a week.
        Max 2 quality sessions per week (excluding strides/hills in base).
        """
        for week in range(1, self.plan.duration_weeks + 1):
            quality_workouts = [
                w for w in self._get_week_workouts(week)
                if w.workout_type in QUALITY_TYPES
            ]

            if len(quality_workouts) > 2:
                types = [w.workout_type for w in quality_workouts]
                self._fail(
                    "A3-MAX-QUALITY",
                    f"{len(quality_workouts)} quality sessions: {types}",
                    week=week
                )

    # ------------------------------------------------------------------
    # RULE GROUP: Phase Rules
    # ------------------------------------------------------------------

    def assert_phase_rules(self):
        """
        Rules A1/VAL-BASE-NO-T/M3:
        - No threshold work in base phase
        - Speed work (intervals) allowed in base (Rule M2/M3)
        - Build phase: primarily threshold + MP
        """
        for week in range(1, self.plan.duration_weeks + 1):
            phase = self._get_phase_for_week(week)
            workouts = self._get_week_workouts(week)

            for w in workouts:
                # No threshold in base/base_speed phases
                if phase in NO_THRESHOLD_PHASES:
                    if w.workout_type in THRESHOLD_TYPES:
                        self._fail(
                            "A1-BASE-NO-T",
                            f"Threshold ({w.workout_type}) in {phase} phase",
                            week=week, day=w.day
                        )

    # ------------------------------------------------------------------
    # RULE GROUP: Alternation Rule
    # ------------------------------------------------------------------

    def assert_alternation_rule(self):
        """
        VAL-MP-NO-T / VAL-T-EASY-LR:
        - Weeks with MP long runs should NOT have threshold sessions.

        This is a rule from the build plan, not a suggestion.
        Emits a FAILURE — the generator must respect alternation.
        """
        if self.plan.distance != "marathon":
            return  # Only applies to marathon

        for week in range(1, self.plan.duration_weeks + 1):
            workouts = self._get_week_workouts(week)
            types = {w.workout_type for w in workouts}

            has_mp_long = bool(types & MP_TYPES)
            has_threshold = bool(types & THRESHOLD_TYPES)

            if has_mp_long and has_threshold:
                self._fail(
                    "ALT-MP-NO-T",
                    f"MP long run AND threshold in same week "
                    f"(types: {sorted(types - REST_TYPES - EASY_TYPES)})",
                    week=week
                )

    # ------------------------------------------------------------------
    # RULE GROUP: Volume Progression
    # ------------------------------------------------------------------

    def assert_volume_progression(self):
        """
        Rules B4/VAL-CUTBACK:
        - Volume jumps ≤ spec% week-over-week (non-cutback to non-cutback).

        Spec (strict): ≤ 15%.  Relaxed (1-PRE): ≤ 20%.
        """
        jump_cap = self._t["volume_jump_pct"]
        vols = self.plan.weekly_volumes

        for i in range(1, len(vols)):
            prev = vols[i - 1]
            curr = vols[i]

            if prev <= 0:
                continue

            change_pct = (curr - prev) / prev

            # After a cutback week, the jump back up can be large — skip those
            if i >= 2 and vols[i - 2] > vols[i - 1]:
                # This is a recovery from cutback, skip the jump check
                continue

            if change_pct > jump_cap:
                self._warn(
                    "B4-JUMP",
                    f"Volume jump {change_pct*100:.0f}% (> {jump_cap*100:.0f}%) "
                    f"from week {i} ({prev:.1f}mi) to week {i+1} ({curr:.1f}mi)",
                    week=i + 1
                )

    # ------------------------------------------------------------------
    # RULE GROUP: Cutback Weeks
    # ------------------------------------------------------------------

    def assert_cutback_pattern(self):
        """
        VAL-CUTBACK: Cutback weeks should appear at regular intervals.
        The plan's volume progression should show periodic reductions.

        When a profile is provided, the detection threshold adapts to the
        tier's actual cutback percentage (builder = 10%, standard = 25%).
        """
        vols = self.plan.weekly_volumes
        if len(vols) < 6:
            return  # Too short for cutback analysis

        # Tier-aware cutback detection threshold
        # Builder uses a gentle 10% cutback → detect at > 7%
        # Standard tiers use 25% cutback → detect at > 15%
        if self.profile and self.profile.volume_tier.value == "builder":
            cutback_threshold = 0.07
        else:
            cutback_threshold = 0.15

        # Find weeks where volume dropped significantly
        cutback_weeks = []
        for i in range(1, len(vols)):
            if vols[i - 1] > 0 and (vols[i - 1] - vols[i]) / vols[i - 1] > cutback_threshold:
                cutback_weeks.append(i + 1)  # 1-indexed

        # Exclude taper weeks (last 1-3 weeks)
        taper_start = self.plan.duration_weeks - 2
        cutback_weeks = [w for w in cutback_weeks if w < taper_start]

        if len(cutback_weeks) == 0 and self.plan.duration_weeks >= 10:
            self._fail(
                "VAL-NO-CUTBACK",
                f"No cutback weeks detected in {self.plan.duration_weeks}-week plan",
            )

    # ------------------------------------------------------------------
    # RULE GROUP: Taper Structure
    # ------------------------------------------------------------------

    def assert_taper_structure(self):
        """
        VAL-TAPER: Taper should reduce volume while maintaining some intensity.
        - Volume should decrease in taper weeks
        - Some quality (strides, light threshold) should remain
        - Taper duration bounds: profile-aware (fast adapters get shorter tapers)

        Phase 1D additions:
        - VAL-TAPER-BOUNDS: Taper total days within [3, 21]
        - Progressive taper: early taper weeks should have higher volume
          modifier than later taper weeks
        """
        taper_phases = [p for p in self.plan.phases if p.phase_type.value == "taper"]
        if not taper_phases:
            self._fail("VAL-NO-TAPER", "No taper phase found")
            return

        # Collect ALL taper weeks across potentially multiple taper phases
        # (Phase 1D splits taper into "Early Taper" + "Taper")
        all_taper_weeks = []
        for tp in taper_phases:
            all_taper_weeks.extend(tp.weeks)

        if not all_taper_weeks:
            self._fail("VAL-TAPER-EMPTY", "Taper phase has no weeks")
            return

        # Volume should be lower than peak
        peak_vol = self.plan.peak_volume
        for tw in all_taper_weeks:
            if tw <= len(self.plan.weekly_volumes):
                taper_vol = self.plan.weekly_volumes[tw - 1]
                if taper_vol > peak_vol * 0.85:
                    self._fail(
                        "VAL-TAPER-VOL",
                        f"Taper week {tw} volume {taper_vol:.1f}mi >= "
                        f"85% of peak {peak_vol:.1f}mi",
                        week=tw
                    )

        # Progressive structure: if multiple taper phases, earlier should
        # have >= volume_modifier compared to later
        if len(taper_phases) >= 2:
            for i in range(len(taper_phases) - 1):
                if taper_phases[i].volume_modifier < taper_phases[i + 1].volume_modifier:
                    self._warn(
                        "VAL-TAPER-PROGRESSIVE",
                        f"Taper phase '{taper_phases[i].name}' has lower volume "
                        f"modifier ({taper_phases[i].volume_modifier}) than "
                        f"'{taper_phases[i+1].name}' ({taper_phases[i+1].volume_modifier}). "
                        f"Taper should be progressively reducing.",
                    )

    # ------------------------------------------------------------------
    # RULE GROUP: Marathon-Specific — MP Total
    # ------------------------------------------------------------------

    def assert_mp_total(self):
        """
        MP-TOTAL: Marathon plans should accumulate spec mi at MP before race.

        Spec (strict): ≥ 40mi.  Relaxed (1-PRE): ≥ 20mi.

        When a profile is provided, the target is tier-aware:
        - builder: ≥ 15mi  (few specific-phase weeks at low volume)
        - low:     ≥ 25mi
        - mid+:    spec value (40mi strict, 20mi relaxed)
        """
        if self.plan.distance != "marathon":
            return

        mp_min = self._t["mp_total_min_mi"]

        # Tier-aware MP total targets when profile is available
        if self.profile:
            tier_val = self.profile.volume_tier.value
            if tier_val == "builder":
                mp_min = 15 if self.strict else 10
            elif tier_val == "low":
                mp_min = 25 if self.strict else 15

        total_mp = sum(
            w.distance_miles or 0
            for w in self.plan.workouts
            if w.workout_type in MP_TYPES
        )

        if total_mp < mp_min:
            self._fail(
                "MP-TOTAL-LOW",
                f"Total MP miles ({total_mp:.1f}) < {mp_min}mi minimum. "
                f"Spec target: 40-50+ miles at MP before race day."
            )

    # ------------------------------------------------------------------
    # RULE GROUP: Paces Present
    # ------------------------------------------------------------------

    def assert_paces_present(self, expect_paces: bool = False):
        """
        VAL-PACES: When RPI exists, every non-rest workout should have paces.
        """
        if not expect_paces:
            return  # Only check when we expect paces

        missing_pace_workouts = []
        for w in self.plan.workouts:
            if w.workout_type in REST_TYPES:
                continue
            if not w.pace_description or w.pace_description.strip() == "":
                missing_pace_workouts.append(
                    f"Week {w.week} {w.day_name}: {w.workout_type}"
                )

        if missing_pace_workouts:
            self._fail(
                "VAL-NO-PACES",
                f"{len(missing_pace_workouts)} workouts missing paces. "
                f"First 5: {missing_pace_workouts[:5]}"
            )

    # ------------------------------------------------------------------
    # RULE GROUP: Plan Structure Sanity
    # ------------------------------------------------------------------

    def assert_plan_structure(self):
        """
        Basic structural validations:
        - Plan has workouts
        - Plan has phases
        - Duration matches
        - No empty weeks
        """
        if not self.plan.workouts:
            self._fail("STRUCT-NO-WORKOUTS", "Plan has no workouts")
            return

        if not self.plan.phases:
            self._fail("STRUCT-NO-PHASES", "Plan has no phases")
            return

        # Check all weeks have workouts
        for week in range(1, self.plan.duration_weeks + 1):
            week_workouts = self._get_week_workouts(week)
            non_rest = [w for w in week_workouts if w.workout_type != "rest"]
            if not non_rest:
                self._fail(
                    "STRUCT-EMPTY-WEEK",
                    f"Week {week} has no non-rest workouts",
                    week=week
                )

        # Check workout count per week matches days_per_week
        # (accounting for rest days being included in 7-day structure)
        for week in range(1, self.plan.duration_weeks + 1):
            non_rest = self._get_non_rest_workouts(week)
            if len(non_rest) > self.plan.days_per_week + 1:
                self._fail(
                    "STRUCT-TOO-MANY",
                    f"Week {week} has {len(non_rest)} non-rest workouts "
                    f"but plan specifies {self.plan.days_per_week} days/week",
                    week=week
                )

    # ------------------------------------------------------------------
    # RULE GROUP: Long Run Consistency
    # ------------------------------------------------------------------

    def assert_long_run_consistency(self):
        """
        VAL-LR-CONSISTENT: Long run should appear consistently each week
        (typically Sunday). Every non-cutback week should have a long run.
        """
        for week in range(1, self.plan.duration_weeks + 1):
            workouts = self._get_week_workouts(week)
            long_runs = [w for w in workouts if w.workout_type in LONG_TYPES]

            # Skip race week
            phase = self._get_phase_for_week(week)
            if phase in ("race", "recovery"):
                continue

            if not long_runs:
                self._warn(
                    "VAL-NO-LR",
                    f"No long run in week {week} (phase: {phase})",
                    week=week
                )

    # ------------------------------------------------------------------
    # RULE GROUP: Distance-Specific Emphasis
    # ------------------------------------------------------------------

    def assert_distance_emphasis(self):
        """
        Distance-specific quality emphasis rules:
        - Marathon: threshold dominant, MP integration
        - Half: threshold primary, some VO2max
        - 10K: VO2max + threshold co-dominant
        - 5K: VO2max dominant, repetitions
        """
        if self.plan.distance == "marathon":
            self._assert_marathon_emphasis()
        elif self.plan.distance == "half_marathon":
            self._assert_half_emphasis()
        elif self.plan.distance == "10k":
            self._assert_10k_emphasis()
        elif self.plan.distance == "5k":
            self._assert_5k_emphasis()

    def _assert_marathon_emphasis(self):
        """Marathon: threshold should be the primary quality type."""
        threshold_count = sum(
            1 for w in self.plan.workouts if w.workout_type in THRESHOLD_TYPES
        )
        interval_count = sum(
            1 for w in self.plan.workouts if w.workout_type in INTERVAL_TYPES
        )
        mp_count = sum(
            1 for w in self.plan.workouts if w.workout_type in MP_TYPES
        )

        # Marathon should have more T sessions than I sessions
        if interval_count > threshold_count and threshold_count > 0:
            self._warn(
                "DIST-M-T-PRIMARY",
                f"Marathon: intervals ({interval_count}) > threshold "
                f"({threshold_count}). Threshold should be primary."
            )

        # Marathon should have MP work
        if mp_count == 0 and self.plan.duration_weeks >= 12:
            self._fail(
                "DIST-M-NO-MP",
                f"Marathon {self.plan.duration_weeks}w plan has no MP long runs"
            )

    def _assert_half_emphasis(self):
        """Half marathon: threshold primary emphasis."""
        threshold_count = sum(
            1 for w in self.plan.workouts if w.workout_type in THRESHOLD_TYPES
        )
        if threshold_count == 0:
            self._fail(
                "DIST-HM-NO-T",
                "Half marathon plan has no threshold sessions"
            )

    def _assert_10k_emphasis(self):
        """10K: VO2max + threshold co-dominant."""
        threshold_count = sum(
            1 for w in self.plan.workouts if w.workout_type in THRESHOLD_TYPES
        )
        interval_count = sum(
            1 for w in self.plan.workouts if w.workout_type in INTERVAL_TYPES
        )

        if threshold_count == 0 and interval_count == 0:
            self._fail(
                "DIST-10K-NO-QUALITY",
                "10K plan has no threshold or interval sessions"
            )

    def _assert_5k_emphasis(self):
        """5K: VO2max should be dominant."""
        interval_count = sum(
            1 for w in self.plan.workouts if w.workout_type in INTERVAL_TYPES
        )

        if interval_count == 0:
            self._warn(
                "DIST-5K-NO-I",
                "5K plan has no interval/VO2max sessions"
            )

    # ------------------------------------------------------------------
    # Master method: run all assertions
    # ------------------------------------------------------------------

    def assert_all(self, expect_paces: bool = False) -> ValidationResult:
        """Run ALL validation rules and return the result."""
        self.assert_plan_structure()
        self.assert_source_b_limits()
        self.assert_easy_distribution()
        self.assert_hard_easy_pattern()
        self.assert_quality_day_limit()
        self.assert_phase_rules()
        self.assert_alternation_rule()
        self.assert_volume_progression()
        self.assert_cutback_pattern()
        self.assert_taper_structure()
        self.assert_mp_total()
        self.assert_long_run_consistency()
        self.assert_distance_emphasis()
        self.assert_paces_present(expect_paces=expect_paces)
        return self.result


def validate_plan(plan, *, strict: bool = False, expect_paces: bool = False, profile=None) -> ValidationResult:
    """Convenience function to validate a plan and return the result."""
    validator = PlanValidator(plan, strict=strict, profile=profile)
    return validator.assert_all(expect_paces=expect_paces)
