"""
Training Logic Scenario Framework — Helpers (Phase 2-PRE)

Provides data structures and utilities for constructing training scenarios
that test the readiness score calculator and daily intelligence engine.

Each scenario is a self-contained unit:
    1. Setup: construct athlete state (activities, planned workouts, check-ins)
    2. Trigger: call the system (readiness + intelligence)
    3. Assert: verify output matches expected behavior

Design:
    - Scenarios are pure data — no DB dependency for DEFINING them.
    - A ScenarioLoader populates a DB session from a scenario definition.
    - Scenarios can be added without new infrastructure.

Sources:
    docs/TRAINING_PLAN_REBUILD_PLAN.md (Phase 2-PRE)
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID, uuid4


# ---------------------------------------------------------------------------
# Scenario data structures (pure data, no DB dependency)
# ---------------------------------------------------------------------------

@dataclass
class MockActivity:
    """An activity record for scenario setup."""
    date: date
    distance_miles: float
    duration_minutes: float
    avg_hr: Optional[int] = None
    elevation_gain_ft: Optional[float] = None
    workout_type: Optional[str] = None      # 'easy_run', 'tempo_run', 'long_run', 'race', etc.
    avg_pace_per_mile: Optional[float] = None  # Minutes per mile
    name: Optional[str] = None
    sport: str = "Run"


@dataclass
class MockPlannedWorkout:
    """A planned workout for scenario setup."""
    date: date
    workout_type: str                        # 'easy', 'long', 'threshold', 'intervals', etc.
    target_distance_miles: Optional[float] = None
    target_duration_minutes: Optional[int] = None
    phase: str = "build"
    week_number: int = 1
    completed: bool = False
    completed_activity_id: Optional[UUID] = None
    skipped: bool = False
    skip_reason: Optional[str] = None


@dataclass
class MockCheckin:
    """A daily check-in for scenario setup."""
    date: date
    sleep_h: Optional[float] = None
    stress_1_5: Optional[int] = None
    soreness_1_5: Optional[int] = None
    rpe_1_10: Optional[int] = None
    hrv_rmssd: Optional[float] = None
    resting_hr: Optional[int] = None
    enjoyment_1_5: Optional[int] = None
    motivation_1_5: Optional[int] = None


@dataclass
class ExpectedInsight:
    """Expected intelligence insight for assertion."""
    rule_id: str                             # Which rule should fire
    mode: str                                # "inform", "suggest", "flag", "ask", "log"
    message_contains: Optional[str] = None   # Substring that should appear in message
    message_not_contains: Optional[str] = None  # Substring that must NOT appear


@dataclass
class TrainingScenario:
    """
    A complete training scenario definition.

    Contains all setup data and expected outcomes.
    Self-contained — can be loaded into any test environment.
    """
    # Identity
    name: str
    description: str
    category: str                            # For grouping: "golden", "readiness", "rules", etc.

    # Athlete setup
    athlete_name: str = "Scenario Athlete"
    athlete_weekly_miles: float = 50.0       # Typical weekly volume

    # Training history (most recent first)
    activities: List[MockActivity] = field(default_factory=list)

    # Current plan
    planned_workouts: List[MockPlannedWorkout] = field(default_factory=list)

    # Check-in history
    check_ins: List[MockCheckin] = field(default_factory=list)

    # Pre-computed signals (when you want to test the engine with specific signal values
    # rather than deriving them from raw activities)
    override_signals: Optional[Dict[str, float]] = None

    # Trigger
    trigger_date: date = field(default_factory=date.today)

    # Expected: readiness score
    expected_readiness_range: Optional[Tuple[float, float]] = None  # (min, max)

    # Expected: intelligence insights
    expected_insights: List[ExpectedInsight] = field(default_factory=list)

    # Expected: behavioral constraints
    expect_no_swap: bool = True              # Default: system should NEVER swap
    expected_highest_mode: Optional[str] = None  # "inform", "suggest", "flag"

    # Expected: self-regulation
    expect_self_reg_logged: bool = False      # Should a planned≠actual delta be detected?
    expected_self_reg_delta: Optional[Dict[str, Any]] = None  # Details of the delta


# ---------------------------------------------------------------------------
# Scenario loader — populates DB from scenario definition
# ---------------------------------------------------------------------------

class ScenarioLoader:
    """
    Load a TrainingScenario into a database session.

    Creates Athlete, Activity, PlannedWorkout, and DailyCheckin records
    from the scenario definition. Returns IDs needed for assertions.
    """

    def __init__(self, db_session):
        self.db = db_session

    def load(self, scenario: TrainingScenario) -> Dict[str, Any]:
        """
        Load a scenario into the database.

        Returns:
            Dict with 'athlete_id', 'plan_id', 'activity_ids', etc.
        """
        from models import Athlete, Activity, DailyCheckin, PlannedWorkout, TrainingPlan

        # Create athlete
        athlete = Athlete(
            email=f"scenario_{uuid4().hex[:8]}@test.com",
            display_name=scenario.athlete_name,
            subscription_tier="guided",
            birthdate=date(1990, 6, 15),
            sex="M",
        )
        self.db.add(athlete)
        self.db.flush()

        # Create training plan (needed for PlannedWorkout FK)
        plan_start = scenario.trigger_date - timedelta(weeks=8)
        plan_end = scenario.trigger_date + timedelta(weeks=8)
        plan = TrainingPlan(
            athlete_id=athlete.id,
            name=f"Scenario Plan: {scenario.name}",
            status="active",
            goal_race_date=plan_end,
            goal_race_distance_m=42195,  # Marathon default
            plan_start_date=plan_start,
            plan_end_date=plan_end,
            total_weeks=16,
            plan_type="marathon",
            generation_method="ai",
        )
        self.db.add(plan)
        self.db.flush()

        # Create activities
        activity_ids = []
        for act in scenario.activities:
            distance_m = int(act.distance_miles * 1609.344)
            duration_s = int(act.duration_minutes * 60)
            avg_speed = distance_m / duration_s if duration_s > 0 else 0

            activity = Activity(
                athlete_id=athlete.id,
                name=act.name or f"Run {act.date}",
                start_time=datetime.combine(act.date, datetime.min.time().replace(hour=7)),
                sport=act.sport,
                source="strava",
                distance_m=distance_m,
                duration_s=duration_s,
                avg_hr=act.avg_hr,
                total_elevation_gain=act.elevation_gain_ft * 0.3048 if act.elevation_gain_ft else None,
                average_speed=avg_speed,
                workout_type=act.workout_type,
                provider="strava",
                external_activity_id=f"scenario_{uuid4().hex[:12]}",
            )
            self.db.add(activity)
            self.db.flush()
            activity_ids.append(activity.id)

        # Create planned workouts
        planned_ids = []
        for pw in scenario.planned_workouts:
            planned = PlannedWorkout(
                plan_id=plan.id,
                athlete_id=athlete.id,
                scheduled_date=pw.date,
                week_number=pw.week_number,
                day_of_week=pw.date.weekday(),
                workout_type=pw.workout_type,
                title=f"{pw.workout_type.replace('_', ' ').title()}",
                phase=pw.phase,
                target_distance_km=pw.target_distance_miles * 1.60934 if pw.target_distance_miles else None,
                target_duration_minutes=pw.target_duration_minutes,
                completed=pw.completed,
                completed_activity_id=pw.completed_activity_id,
                skipped=pw.skipped,
                skip_reason=pw.skip_reason,
            )
            self.db.add(planned)
            self.db.flush()
            planned_ids.append(planned.id)

        # Create check-ins
        for ci in scenario.check_ins:
            checkin = DailyCheckin(
                athlete_id=athlete.id,
                date=ci.date,
                sleep_h=ci.sleep_h,
                stress_1_5=ci.stress_1_5,
                soreness_1_5=ci.soreness_1_5,
                rpe_1_10=ci.rpe_1_10,
                hrv_rmssd=ci.hrv_rmssd,
                resting_hr=ci.resting_hr,
                enjoyment_1_5=ci.enjoyment_1_5,
                motivation_1_5=ci.motivation_1_5,
            )
            self.db.add(checkin)

        self.db.flush()

        return {
            "athlete_id": athlete.id,
            "plan_id": plan.id,
            "activity_ids": activity_ids,
            "planned_ids": planned_ids,
        }


# ---------------------------------------------------------------------------
# Scenario runner — executes a scenario and captures results
# ---------------------------------------------------------------------------

class ScenarioRunner:
    """
    Execute a training scenario against the readiness + intelligence services.

    Loads the scenario into the DB, calls the services, and returns results
    for assertion by the test.
    """

    def __init__(self, db_session):
        self.db = db_session
        self.loader = ScenarioLoader(db_session)

    def run(self, scenario: TrainingScenario) -> "ScenarioResult":
        """
        Run a scenario end-to-end.

        Computes readiness first, then runs intelligence rules. If the
        intelligence engine is not yet implemented (raises NotImplementedError),
        returns a partial result with empty intelligence — this allows
        readiness-only tests to pass while intelligence tests remain xfailed.

        Returns:
            ScenarioResult with readiness, insights, and metadata
        """
        from services.readiness_score import ReadinessScoreCalculator
        from services.daily_intelligence import DailyIntelligenceEngine, IntelligenceResult

        # Load scenario data into DB
        ids = self.loader.load(scenario)
        athlete_id = ids["athlete_id"]

        # Compute readiness
        readiness_calc = ReadinessScoreCalculator()
        readiness_result = readiness_calc.compute(
            athlete_id=athlete_id,
            target_date=scenario.trigger_date,
            db=self.db,
        )

        # Override readiness score if the scenario provides one
        # (allows testing intelligence rules with specific readiness values)
        effective_readiness = readiness_result.score
        if scenario.override_signals and "readiness_7d_avg" in scenario.override_signals:
            effective_readiness = scenario.override_signals["readiness_7d_avg"]

        # Run intelligence rules — graceful degradation if not yet implemented
        try:
            engine = DailyIntelligenceEngine()
            intel_result = engine.evaluate(
                athlete_id=athlete_id,
                target_date=scenario.trigger_date,
                db=self.db,
                readiness_score=effective_readiness,
            )
        except NotImplementedError:
            # Intelligence engine not yet implemented (Phase 2C).
            # Return empty result so readiness-only tests can proceed.
            intel_result = IntelligenceResult(
                athlete_id=athlete_id,
                target_date=scenario.trigger_date,
                insights=[],
                readiness_score=readiness_result.score,
                self_regulation_logged=False,
            )

        return ScenarioResult(
            scenario=scenario,
            ids=ids,
            readiness=readiness_result,
            intelligence=intel_result,
        )


@dataclass
class ScenarioResult:
    """Result of running a scenario — ready for assertions."""
    scenario: TrainingScenario
    ids: Dict[str, Any]
    readiness: Any     # DailyReadinessResult
    intelligence: Any  # IntelligenceResult


# ---------------------------------------------------------------------------
# Assertion helpers
# ---------------------------------------------------------------------------

def assert_no_workout_swap(result: ScenarioResult):
    """Verify the system did NOT swap any workout."""
    assert not result.intelligence.has_workout_swap, (
        f"Scenario '{result.scenario.name}': System attempted to swap a workout! "
        f"This violates the core principle: the system INFORMS, the athlete DECIDES."
    )


def assert_readiness_in_range(result: ScenarioResult, min_score: float, max_score: float):
    """Verify readiness score is within expected range."""
    score = result.readiness.score
    assert min_score <= score <= max_score, (
        f"Scenario '{result.scenario.name}': Readiness {score:.1f} not in "
        f"expected range [{min_score}, {max_score}]"
    )


def assert_insight_present(result: ScenarioResult, rule_id: str, mode: str,
                           message_contains: Optional[str] = None):
    """Verify a specific insight was produced."""
    matching = [
        i for i in result.intelligence.insights
        if i.rule_id == rule_id and i.mode.value == mode
    ]
    assert matching, (
        f"Scenario '{result.scenario.name}': Expected insight "
        f"rule_id={rule_id} mode={mode}, but not found. "
        f"Got: {[(i.rule_id, i.mode.value) for i in result.intelligence.insights]}"
    )
    if message_contains:
        messages = [i.message for i in matching]
        assert any(message_contains.lower() in m.lower() for m in messages), (
            f"Scenario '{result.scenario.name}': Insight {rule_id} found but "
            f"message doesn't contain '{message_contains}'. Got: {messages}"
        )


def assert_insight_absent(result: ScenarioResult, rule_id: str):
    """Verify a specific insight was NOT produced."""
    matching = [i for i in result.intelligence.insights if i.rule_id == rule_id]
    assert not matching, (
        f"Scenario '{result.scenario.name}': Expected NO insight for "
        f"rule_id={rule_id}, but found: {[(i.rule_id, i.mode.value) for i in matching]}"
    )


def assert_highest_mode(result: ScenarioResult, expected_mode: str):
    """Verify the highest-severity mode across all insights."""
    actual = result.intelligence.highest_mode
    if actual is None:
        actual_str = None
    else:
        actual_str = actual.value if hasattr(actual, 'value') else str(actual)
    assert actual_str == expected_mode, (
        f"Scenario '{result.scenario.name}': Expected highest mode "
        f"'{expected_mode}', got '{actual_str}'"
    )


def assert_self_regulation_logged(result: ScenarioResult):
    """Verify that a self-regulation delta was detected and logged."""
    assert result.intelligence.self_regulation_logged, (
        f"Scenario '{result.scenario.name}': Expected self-regulation "
        f"delta to be logged, but it wasn't."
    )


# ---------------------------------------------------------------------------
# Date helpers — for building scenarios relative to a trigger date
# ---------------------------------------------------------------------------

def days_ago(n: int, from_date: Optional[date] = None) -> date:
    """Return the date N days ago from a reference date."""
    ref = from_date or date.today()
    return ref - timedelta(days=n)


def build_week_of_activities(
    start_date: date,
    daily_miles: List[float],
    base_hr: int = 145,
    long_run_day: int = 6,  # Sunday
    long_run_miles: Optional[float] = None,
) -> List[MockActivity]:
    """
    Build a week of activities from a simple daily mileage list.

    Args:
        start_date: Monday of the week
        daily_miles: 7-element list of daily mileage (0 = rest)
        base_hr: Typical average HR
        long_run_day: Which day is the long run (0=Mon, 6=Sun)
        long_run_miles: Override long run distance

    Returns:
        List of MockActivity for non-rest days
    """
    activities = []
    for i, miles in enumerate(daily_miles):
        if miles <= 0:
            continue
        d = start_date + timedelta(days=i)
        is_long = (i == long_run_day)
        if is_long and long_run_miles:
            miles = long_run_miles

        activities.append(MockActivity(
            date=d,
            distance_miles=miles,
            duration_minutes=miles * 9.0,  # ~9 min/mile default
            avg_hr=base_hr - 5 if is_long else base_hr,
            workout_type="long_run" if is_long else "easy_run",
            name=f"{'Long Run' if is_long else 'Easy Run'} — {d.strftime('%a')}",
        ))
    return activities
