"""
Training Logic Scenario Tests (Phase 2-PRE)

Contract-first test suite for the Daily Adaptation Engine.
These scenarios define WHAT the system should do before the code exists.

Golden rule: The system INFORMS, the athlete DECIDES.
No workout swapping in default (inform) mode. Ever.

Organization:
    1. Golden Scenario (founder's real training — test #1, must pass)
    2. Readiness Computation (signal aggregation)
    3. Intelligence Rules (7 rules, one test each minimum)
    4. Self-Regulation (planned ≠ actual tracking)
    5. Sustained Trends (timing of flag escalation)
    6. False Positive Prevention (load spikes vs real declines)
    7. Edge Cases (sparse data, no plan, mid-taper, returning from injury)

Sources:
    docs/TRAINING_PLAN_REBUILD_PLAN.md (Phase 2-PRE, 2A, 2C)
"""

import pytest
from datetime import date, timedelta

from tests.training_scenario_helpers import (
    TrainingScenario,
    MockActivity,
    MockPlannedWorkout,
    MockCheckin,
    ExpectedInsight,
    ScenarioRunner,
    assert_no_workout_swap,
    assert_readiness_in_range,
    assert_insight_present,
    assert_insight_absent,
    assert_highest_mode,
    assert_self_regulation_logged,
    days_ago,
    build_week_of_activities,
)


# ===================================================================
# Fixtures
# ===================================================================

@pytest.fixture
def runner(db_session):
    """Create a scenario runner backed by the test DB session."""
    return ScenarioRunner(db_session)


# Phase 2C intelligence engine is now implemented.
# All xfail markers removed — tests should pass directly.


# ===================================================================
# Helper: reference dates
# ===================================================================
# Use a fixed date so scenarios are deterministic across runs.
TODAY = date(2026, 2, 12)


def _mon(weeks_ago: int = 0) -> date:
    """Return Monday of N weeks ago from TODAY."""
    return TODAY - timedelta(days=TODAY.weekday()) - timedelta(weeks=weeks_ago)


# ===================================================================
# 1. GOLDEN SCENARIO — The Litmus Test
# ===================================================================

class TestGoldenScenario:
    """
    Founder's real training week: 51→60 miles.

    Week N-1: 51 miles, normal distribution.
    Week N:   60 miles, with 20mi/2300ft Sunday.
    Tuesday:  Planned 15 easy. Athlete does 10 at MP instead.
    Wednesday: Sore, self-regulates to 8 slow.
    End of week: Efficiency breakthrough.

    At NO POINT does the system override the athlete.
    """

    def _build_golden_scenario(self) -> TrainingScenario:
        mon_prev = _mon(2)  # Week N-1 (51 miles)
        mon_curr = _mon(1)  # Week N (60 miles)
        trigger = mon_curr + timedelta(days=1)  # Tuesday of week N

        # Week N-1: 51 miles, normal
        prev_week = [
            MockActivity(date=mon_prev, distance_miles=7, duration_minutes=63, avg_hr=140, workout_type="easy_run"),
            MockActivity(date=mon_prev + timedelta(days=1), distance_miles=9, duration_minutes=81, avg_hr=142, workout_type="easy_run"),
            MockActivity(date=mon_prev + timedelta(days=2), distance_miles=6, duration_minutes=54, avg_hr=138, workout_type="easy_run"),
            MockActivity(date=mon_prev + timedelta(days=3), distance_miles=8, duration_minutes=68, avg_hr=148, workout_type="tempo_run"),
            MockActivity(date=mon_prev + timedelta(days=4), distance_miles=5, duration_minutes=47, avg_hr=135, workout_type="easy_run"),
            # Rest Saturday
            MockActivity(date=mon_prev + timedelta(days=6), distance_miles=16, duration_minutes=144, avg_hr=138, workout_type="long_run"),
        ]

        # Week N: 60 miles, big Sunday
        curr_week_before_tuesday = [
            MockActivity(date=mon_curr, distance_miles=8, duration_minutes=72, avg_hr=142, workout_type="easy_run"),
            # Sunday: the monster 20-miler with 2300ft elevation
            MockActivity(
                date=mon_curr - timedelta(days=1),  # Sunday before this Monday
                distance_miles=20, duration_minutes=180, avg_hr=145,
                elevation_gain_ft=2300, workout_type="long_run",
                name="Sunday Long — 20mi/2300ft"
            ),
        ]

        # Tuesday planned: 15 easy. Athlete does 10 at MP.
        tuesday_planned = MockPlannedWorkout(
            date=trigger,
            workout_type="easy",
            target_distance_miles=15,
            target_duration_minutes=135,
            phase="build",
            week_number=8,
        )

        # The actual Tuesday activity (10 at MP — self-regulation)
        tuesday_actual = MockActivity(
            date=trigger,
            distance_miles=10,
            duration_minutes=75,  # ~7:30/mi = MP
            avg_hr=155,
            workout_type="tempo_run",
            name="Felt great — 10 at MP",
        )

        return TrainingScenario(
            name="Golden Scenario: Founder's 51→60 week",
            description=(
                "Load spike from 51→60 miles with 20mi/2300ft Sunday. "
                "Every metric says fatigued. Athlete does 10 at MP on Tuesday instead "
                "of planned 15 easy. System MUST NOT swap. System MUST inform about "
                "load spike. System MUST log self-regulation delta."
            ),
            category="golden",
            athlete_name="Michael (Founder)",
            athlete_weekly_miles=55.0,
            activities=prev_week + curr_week_before_tuesday + [tuesday_actual],
            planned_workouts=[tuesday_planned],
            check_ins=[
                MockCheckin(date=trigger, sleep_h=7.5, stress_1_5=2, soreness_1_5=3, rpe_1_10=7),
            ],
            trigger_date=trigger,
            expected_insights=[
                ExpectedInsight(rule_id="LOAD_SPIKE", mode="inform", message_contains="volume"),
                ExpectedInsight(rule_id="SELF_REG_DELTA", mode="log"),
            ],
            expect_no_swap=True,
            expected_highest_mode="inform",
            expect_self_reg_logged=True,
            expected_self_reg_delta={
                "planned_type": "easy",
                "actual_type": "tempo_run",
                "planned_distance": 15,
                "actual_distance": 10,
            },
        )

    def test_golden_no_workout_swap(self, runner):
        """The system must NEVER swap a workout in inform mode."""
        result = runner.run(self._build_golden_scenario())
        assert_no_workout_swap(result)

    def test_golden_load_spike_informed(self, runner):
        """System must surface the load spike as an INFORM insight."""
        result = runner.run(self._build_golden_scenario())
        assert_insight_present(result, "LOAD_SPIKE", "inform", message_contains="volume")

    def test_golden_self_regulation_logged(self, runner):
        """System must log the planned≠actual delta (planned easy, did MP)."""
        result = runner.run(self._build_golden_scenario())
        assert_self_regulation_logged(result)

    def test_golden_highest_mode_is_inform(self, runner):
        """Highest mode should be INFORM, never FLAG or INTERVENE."""
        result = runner.run(self._build_golden_scenario())
        assert_highest_mode(result, "inform")


# ===================================================================
# 2. READINESS COMPUTATION
# ===================================================================

class TestReadinessComputation:
    """Test that the readiness score responds correctly to signal changes."""

    def test_declining_efficiency_lowers_readiness(self, runner):
        """Declining efficiency trend should produce a lower readiness score."""
        scenario = TrainingScenario(
            name="Declining efficiency → lower readiness",
            description="3 sessions with progressively worse efficiency (slower pace, higher HR)",
            category="readiness",
            trigger_date=TODAY,
            activities=[
                MockActivity(date=days_ago(6, TODAY), distance_miles=8, duration_minutes=68, avg_hr=148),  # 8:30/mi
                MockActivity(date=days_ago(4, TODAY), distance_miles=7, duration_minutes=63, avg_hr=150),  # 9:00/mi
                MockActivity(date=days_ago(2, TODAY), distance_miles=6, duration_minutes=57, avg_hr=152),  # 9:30/mi
            ],
            # Score below 50 confirms declining efficiency drags readiness down.
            # Exact range depends on TSB interaction (new athlete → negative TSB).
            expected_readiness_range=(10, 50),  # Below midpoint
        )
        result = runner.run(scenario)
        assert_readiness_in_range(result, 10, 50)

    def test_high_completion_raises_readiness(self, runner):
        """High workout completion rate should contribute to higher readiness."""
        # Include 3 weeks of history to build baseline CTL, plus recent 7-day block.
        # Without history, a new athlete's TSB is extremely negative (ATL >> CTL=0),
        # which drags the composite score down despite 100% completion.
        history = [
            MockActivity(date=days_ago(i, TODAY), distance_miles=6, duration_minutes=54, avg_hr=140)
            for i in range(8, 22)  # 2 weeks of history before the 7-day window
        ]
        recent = [
            MockActivity(date=days_ago(i, TODAY), distance_miles=7, duration_minutes=63, avg_hr=142)
            for i in range(1, 7)
        ]
        scenario = TrainingScenario(
            name="High completion → higher readiness",
            description="Established athlete completed all 6 planned workouts in the last 7 days",
            category="readiness",
            trigger_date=TODAY,
            activities=history + recent,
            planned_workouts=[
                MockPlannedWorkout(date=days_ago(i, TODAY), workout_type="easy", completed=True)
                for i in range(1, 7)
            ],
            expected_readiness_range=(45, 100),  # Upper half
        )
        result = runner.run(scenario)
        assert_readiness_in_range(result, 45, 100)

    def test_missing_signals_graceful_degradation(self, runner):
        """With only 1-2 signals available, score should still compute with lower confidence."""
        scenario = TrainingScenario(
            name="Missing signals → graceful degradation",
            description="New athlete with only 2 activities and no check-ins or plan",
            category="readiness",
            trigger_date=TODAY,
            activities=[
                MockActivity(date=days_ago(3, TODAY), distance_miles=5, duration_minutes=45, avg_hr=150),
                MockActivity(date=days_ago(1, TODAY), distance_miles=4, duration_minutes=38, avg_hr=148),
            ],
            expected_readiness_range=(30, 70),  # Wide range, but should still compute
        )
        result = runner.run(scenario)
        assert result.readiness.confidence < 0.5, "Confidence should be low with sparse signals"
        assert result.readiness.signals_available < result.readiness.signals_total

    def test_all_signals_available_full_confidence(self, runner):
        """With all signals present, confidence should be high."""
        # Mix of easy and quality sessions to enable recovery signal detection
        activities = []
        for i in range(1, 15):
            if i % 3 == 0:
                # Quality session: higher HR, faster pace
                activities.append(MockActivity(
                    date=days_ago(i, TODAY), distance_miles=7, duration_minutes=49,
                    avg_hr=162, workout_type="tempo_run",
                ))
            elif i % 7 == 0:
                # Long run
                activities.append(MockActivity(
                    date=days_ago(i, TODAY), distance_miles=14, duration_minutes=126,
                    avg_hr=140, workout_type="long_run",
                ))
            else:
                # Easy run
                activities.append(MockActivity(
                    date=days_ago(i, TODAY), distance_miles=7, duration_minutes=63,
                    avg_hr=142, workout_type="easy_run",
                ))

        scenario = TrainingScenario(
            name="All signals → full confidence",
            description="Established athlete with complete data for all 5 cold-start signals",
            category="readiness",
            trigger_date=TODAY,
            activities=activities,
            planned_workouts=[
                MockPlannedWorkout(date=days_ago(i, TODAY), workout_type="easy", completed=True)
                for i in range(1, 8)
            ],
            check_ins=[
                MockCheckin(date=days_ago(i, TODAY), sleep_h=7.5, stress_1_5=2, soreness_1_5=2)
                for i in range(1, 8)
            ],
            expected_readiness_range=(40, 90),
        )
        result = runner.run(scenario)
        # With quality sessions in the mix, at least 4 of 5 signals should be available
        # (halflife may need more data or stored athlete value)
        assert result.readiness.confidence >= 0.6, (
            f"Confidence should be at least 0.6 with mixed quality data, "
            f"got {result.readiness.confidence} with {result.readiness.signals_available} signals"
        )


# ===================================================================
# 3. INTELLIGENCE RULES (one per rule minimum)
# ===================================================================

class TestIntelligenceRules:
    """Test each of the 7 intelligence rules individually."""

    def test_rule1_load_spike_detected(self, runner):
        """Rule 1: Volume spike → INFORM with load context."""
        # Week 1: 40 miles. Week 2: 55 miles (38% spike)
        week1 = build_week_of_activities(
            _mon(2), [7, 7, 0, 6, 5, 0, 15], base_hr=142, long_run_miles=15
        )
        week2 = build_week_of_activities(
            _mon(1), [8, 9, 7, 8, 6, 0, 17], base_hr=144, long_run_miles=17
        )
        scenario = TrainingScenario(
            name="Rule 1: Load spike detected",
            description="Volume jumped 38% week-over-week",
            category="rules",
            trigger_date=_mon(1) + timedelta(days=1),  # Tuesday of spike week
            activities=week1 + week2,
            expected_insights=[
                ExpectedInsight(rule_id="LOAD_SPIKE", mode="inform"),
            ],
            expect_no_swap=True,
        )
        result = runner.run(scenario)
        assert_no_workout_swap(result)
        assert_insight_present(result, "LOAD_SPIKE", "inform")

    def test_rule2_self_regulation_delta(self, runner):
        """Rule 2: Planned easy, did quality → LOG the delta."""
        scenario = TrainingScenario(
            name="Rule 2: Self-regulation delta (easy → quality)",
            description="Athlete had easy planned but ran threshold. Log it, don't judge.",
            category="rules",
            trigger_date=TODAY,
            planned_workouts=[
                MockPlannedWorkout(date=TODAY, workout_type="easy", target_distance_miles=8),
            ],
            activities=[
                MockActivity(date=TODAY, distance_miles=7, duration_minutes=49, avg_hr=160,
                             workout_type="tempo_run", name="Felt good, ran threshold"),
            ],
            expected_insights=[
                ExpectedInsight(rule_id="SELF_REG_DELTA", mode="log"),
            ],
            expect_self_reg_logged=True,
        )
        result = runner.run(scenario)
        assert_self_regulation_logged(result)

    def test_rule3_efficiency_breakthrough(self, runner):
        """Rule 3: Efficiency jump → INFORM the athlete."""
        # Recent activities show improving efficiency (faster pace, same or lower HR)
        scenario = TrainingScenario(
            name="Rule 3: Efficiency breakthrough detected",
            description="Pace improved 20s/mi over 2 weeks at same HR — real adaptation",
            category="rules",
            trigger_date=TODAY,
            activities=[
                # 2 weeks ago: 9:00/mi @ 148 HR
                MockActivity(date=days_ago(14, TODAY), distance_miles=8, duration_minutes=72, avg_hr=148),
                MockActivity(date=days_ago(12, TODAY), distance_miles=7, duration_minutes=63, avg_hr=149),
                # 1 week ago: 8:45/mi @ 146 HR
                MockActivity(date=days_ago(7, TODAY), distance_miles=8, duration_minutes=70, avg_hr=146),
                MockActivity(date=days_ago(5, TODAY), distance_miles=7, duration_minutes=60, avg_hr=145),
                # This week: 8:40/mi @ 144 HR
                MockActivity(date=days_ago(2, TODAY), distance_miles=8, duration_minutes=69, avg_hr=144),
                MockActivity(date=days_ago(1, TODAY), distance_miles=7, duration_minutes=59, avg_hr=143),
            ],
            expected_insights=[
                ExpectedInsight(rule_id="EFFICIENCY_BREAK", mode="inform",
                                message_contains="efficiency"),
            ],
        )
        result = runner.run(scenario)
        assert_insight_present(result, "EFFICIENCY_BREAK", "inform")

    def test_rule4_pace_improvement_lower_hr(self, runner):
        """Rule 4: Faster pace + lower HR → INFORM with pace update offer."""
        scenario = TrainingScenario(
            name="Rule 4: Pace improvement + lower HR",
            description="Athlete ran 15s/mi faster than target with lower HR. Paces may need updating.",
            category="rules",
            trigger_date=TODAY,
            planned_workouts=[
                MockPlannedWorkout(
                    date=TODAY, workout_type="threshold",
                    target_distance_miles=7,
                    target_duration_minutes=49,  # Target: 7:00/mi
                    completed=True,
                ),
            ],
            activities=[
                MockActivity(
                    date=TODAY, distance_miles=7, duration_minutes=47,  # Actual: 6:43/mi
                    avg_hr=158,  # Lower than typical threshold HR of 165
                    workout_type="tempo_run",
                ),
            ],
            expected_insights=[
                ExpectedInsight(rule_id="PACE_IMPROVEMENT", mode="inform",
                                message_contains="pace"),
            ],
        )
        result = runner.run(scenario)
        assert_insight_present(result, "PACE_IMPROVEMENT", "inform")

    def test_rule5_sustained_decline_3_weeks(self, runner):
        """Rule 5: 3+ weeks declining efficiency → FLAG."""
        activities = []
        for week_offset in range(4):
            base_pace = 9.0 + week_offset * 0.3  # Gets slower each week
            base_hr = 148 + week_offset * 2       # HR creeps up
            for day in [0, 2, 4]:
                d = days_ago(28 - week_offset * 7 - day, TODAY)
                activities.append(MockActivity(
                    date=d, distance_miles=7,
                    duration_minutes=7 * base_pace,
                    avg_hr=base_hr,
                    workout_type="easy_run",
                ))

        scenario = TrainingScenario(
            name="Rule 5: Sustained decline (3+ weeks)",
            description="Efficiency declining for 4 weeks — slower pace, higher HR each week",
            category="rules",
            trigger_date=TODAY,
            activities=activities,
            expected_insights=[
                ExpectedInsight(rule_id="SUSTAINED_DECLINE", mode="flag",
                                message_contains="declining"),
            ],
            expected_highest_mode="flag",
        )
        result = runner.run(scenario)
        assert_insight_present(result, "SUSTAINED_DECLINE", "flag")
        assert_highest_mode(result, "flag")

    def test_rule6_sustained_missed_sessions(self, runner):
        """Rule 6: Pattern of missed sessions → ASK for context."""
        planned = []
        for i in range(14):
            pw = MockPlannedWorkout(
                date=days_ago(14 - i, TODAY),
                workout_type="easy" if i % 3 != 0 else "threshold",
                week_number=i // 7 + 1,
            )
            # Miss 5 of 14 sessions
            if i in [2, 5, 8, 10, 13]:
                pw.skipped = True
            else:
                pw.completed = True
            planned.append(pw)

        scenario = TrainingScenario(
            name="Rule 6: Sustained missed sessions",
            description="5 of 14 sessions missed in 2 weeks — ask for context",
            category="rules",
            trigger_date=TODAY,
            planned_workouts=planned,
            activities=[
                MockActivity(date=days_ago(14 - i, TODAY), distance_miles=6, duration_minutes=54, avg_hr=142)
                for i in range(14) if i not in [2, 5, 8, 10, 13]
            ],
            expected_insights=[
                ExpectedInsight(rule_id="SUSTAINED_MISSED", mode="ask",
                                message_contains="missed"),
            ],
        )
        result = runner.run(scenario)
        assert_insight_present(result, "SUSTAINED_MISSED", "ask")

    def test_rule7_readiness_high_not_increasing(self, runner):
        """Rule 7: Consistently high readiness → SUGGEST increasing."""
        # 2 weeks of easy running with great check-ins — athlete is undertraining
        scenario = TrainingScenario(
            name="Rule 7: Readiness consistently high",
            description="2 weeks of easy runs, all check-ins positive, athlete not increasing",
            category="rules",
            trigger_date=TODAY,
            override_signals={"readiness_7d_avg": 85},
            activities=[
                MockActivity(date=days_ago(i, TODAY), distance_miles=5, duration_minutes=45,
                             avg_hr=130, workout_type="easy_run")
                for i in range(1, 15)
            ],
            planned_workouts=[
                MockPlannedWorkout(date=days_ago(i, TODAY), workout_type="easy", completed=True)
                for i in range(1, 15)
            ],
            check_ins=[
                MockCheckin(date=days_ago(i, TODAY), sleep_h=8, stress_1_5=1, soreness_1_5=1,
                            motivation_1_5=5, enjoyment_1_5=4)
                for i in range(1, 15)
            ],
            expected_insights=[
                ExpectedInsight(rule_id="READINESS_HIGH", mode="suggest",
                                message_contains="ready"),
            ],
        )
        result = runner.run(scenario)
        assert_insight_present(result, "READINESS_HIGH", "suggest")


# ===================================================================
# 4. SELF-REGULATION TRACKING
# ===================================================================

class TestSelfRegulation:
    """Test that planned ≠ actual is correctly detected and logged."""

    def test_planned_easy_did_quality(self, runner):
        """Planned easy, athlete ran quality — log as positive self-regulation."""
        scenario = TrainingScenario(
            name="Self-reg: easy → quality",
            description="Planned easy 8mi, athlete felt great and ran 7mi threshold",
            category="self_regulation",
            trigger_date=TODAY,
            planned_workouts=[
                MockPlannedWorkout(date=TODAY, workout_type="easy", target_distance_miles=8),
            ],
            activities=[
                MockActivity(date=TODAY, distance_miles=7, duration_minutes=49,
                             avg_hr=162, workout_type="tempo_run"),
            ],
            expect_self_reg_logged=True,
        )
        result = runner.run(scenario)
        assert_self_regulation_logged(result)

    def test_planned_quality_did_easy(self, runner):
        """Planned quality, athlete ran easy — log but don't flag (might be smart)."""
        scenario = TrainingScenario(
            name="Self-reg: quality → easy",
            description="Planned threshold, athlete felt off and ran easy instead",
            category="self_regulation",
            trigger_date=TODAY,
            planned_workouts=[
                MockPlannedWorkout(date=TODAY, workout_type="threshold", target_distance_miles=7),
            ],
            activities=[
                MockActivity(date=TODAY, distance_miles=6, duration_minutes=54,
                             avg_hr=138, workout_type="easy_run"),
            ],
            expect_self_reg_logged=True,
            expected_insights=[
                ExpectedInsight(rule_id="SELF_REG_DELTA", mode="log"),
            ],
        )
        result = runner.run(scenario)
        assert_self_regulation_logged(result)
        # Should NOT flag — one downgrade is smart self-regulation, not concerning
        assert_insight_absent(result, "SUSTAINED_DECLINE")

    def test_planned_15mi_did_10mi(self, runner):
        """Planned 15mi, did 10mi — log distance delta."""
        scenario = TrainingScenario(
            name="Self-reg: distance reduction",
            description="Planned 15mi easy, athlete stopped at 10mi. Log the delta.",
            category="self_regulation",
            trigger_date=TODAY,
            planned_workouts=[
                MockPlannedWorkout(date=TODAY, workout_type="easy", target_distance_miles=15),
            ],
            activities=[
                MockActivity(date=TODAY, distance_miles=10, duration_minutes=90,
                             avg_hr=140, workout_type="easy_run"),
            ],
            expect_self_reg_logged=True,
        )
        result = runner.run(scenario)
        assert_self_regulation_logged(result)


# ===================================================================
# 5. SUSTAINED TRENDS — Timing of Escalation
# ===================================================================

class TestSustainedTrends:
    """Verify FLAG mode fires at 3+ weeks, NOT before."""

    def test_2_week_decline_no_flag(self, runner):
        """2 weeks declining → should NOT flag (too early)."""
        activities = []
        for week_offset in range(2):
            base_pace = 9.0 + week_offset * 0.4
            base_hr = 148 + week_offset * 3
            for day in [0, 2, 4]:
                d = days_ago(14 - week_offset * 7 - day, TODAY)
                activities.append(MockActivity(
                    date=d, distance_miles=7, duration_minutes=7 * base_pace,
                    avg_hr=base_hr, workout_type="easy_run",
                ))

        scenario = TrainingScenario(
            name="2-week decline → no flag",
            description="Only 2 weeks of declining efficiency — too early to flag",
            category="sustained_trends",
            trigger_date=TODAY,
            activities=activities,
            expected_insights=[],
        )
        result = runner.run(scenario)
        assert_insight_absent(result, "SUSTAINED_DECLINE")

    def test_3_week_decline_flags(self, runner):
        """3 weeks declining → should FLAG."""
        activities = []
        for week_offset in range(3):
            base_pace = 9.0 + week_offset * 0.3
            base_hr = 148 + week_offset * 2
            for day in [0, 2, 4]:
                d = days_ago(21 - week_offset * 7 - day, TODAY)
                activities.append(MockActivity(
                    date=d, distance_miles=7, duration_minutes=7 * base_pace,
                    avg_hr=base_hr, workout_type="easy_run",
                ))

        scenario = TrainingScenario(
            name="3-week decline → flag",
            description="3 weeks of declining efficiency — system should flag this",
            category="sustained_trends",
            trigger_date=TODAY,
            activities=activities,
            expected_insights=[
                ExpectedInsight(rule_id="SUSTAINED_DECLINE", mode="flag"),
            ],
            expected_highest_mode="flag",
        )
        result = runner.run(scenario)
        assert_insight_present(result, "SUSTAINED_DECLINE", "flag")

    def test_post_load_spike_dip_1_week_no_flag(self, runner):
        """1-week dip after a load spike → normal, should NOT flag."""
        # Week 1: normal 40mi. Week 2: spike to 55mi. Week 3: dip (slower pace, higher HR)
        week1 = build_week_of_activities(_mon(3), [7, 7, 0, 6, 5, 0, 15], base_hr=142)
        week2 = build_week_of_activities(_mon(2), [8, 9, 7, 8, 6, 0, 17], base_hr=146)
        week3 = build_week_of_activities(_mon(1), [6, 6, 0, 5, 5, 0, 14], base_hr=150)

        scenario = TrainingScenario(
            name="Post-load-spike dip (1 week) → no flag",
            description="Dip after a load spike is normal supercompensation. Don't flag.",
            category="sustained_trends",
            trigger_date=_mon(1) + timedelta(days=1),
            activities=week1 + week2 + week3,
        )
        result = runner.run(scenario)
        assert_insight_absent(result, "SUSTAINED_DECLINE")


# ===================================================================
# 6. FALSE POSITIVE PREVENTION
# ===================================================================

class TestFalsePositivePrevention:
    """Ensure the system distinguishes normal patterns from real problems."""

    def test_load_spike_then_normal_recovery(self, runner):
        """Load spike + 1 week recovery dip → INFORM about spike, not FLAG."""
        week1 = build_week_of_activities(_mon(2), [7, 7, 0, 6, 5, 0, 15], base_hr=142)
        week2 = build_week_of_activities(_mon(1), [8, 9, 8, 8, 6, 0, 18], base_hr=148)

        scenario = TrainingScenario(
            name="Load spike + normal recovery → inform, not flag",
            description="Big week followed by expected fatigue markers. Inform about load, don't panic.",
            category="false_positive",
            trigger_date=_mon(1) + timedelta(days=1),
            activities=week1 + week2,
            expected_insights=[
                ExpectedInsight(rule_id="LOAD_SPIKE", mode="inform"),
            ],
            expected_highest_mode="inform",
        )
        result = runner.run(scenario)
        assert_insight_present(result, "LOAD_SPIKE", "inform")
        assert_insight_absent(result, "SUSTAINED_DECLINE")
        assert_no_workout_swap(result)

    def test_load_spike_then_3_week_decline_flags(self, runner):
        """Load spike followed by 3 weeks of decline → eventually FLAG (different from normal)."""
        activities = []
        # Week 0: normal
        activities.extend(build_week_of_activities(_mon(4), [7, 7, 0, 6, 5, 0, 15], base_hr=142))
        # Week 1: spike
        activities.extend(build_week_of_activities(_mon(3), [8, 9, 8, 8, 7, 0, 18], base_hr=148))
        # Weeks 2-4: sustained decline
        for i in range(3):
            pace = 9.2 + i * 0.3
            hr = 150 + i * 2
            week_start = _mon(2 - i)
            for day in [0, 2, 4, 6]:
                activities.append(MockActivity(
                    date=week_start + timedelta(days=day),
                    distance_miles=6, duration_minutes=6 * pace,
                    avg_hr=hr, workout_type="easy_run",
                ))

        scenario = TrainingScenario(
            name="Load spike + 3-week decline → flag",
            description="Initial spike was fine but 3 weeks later still declining — flag it",
            category="false_positive",
            trigger_date=TODAY,
            activities=activities,
            expected_insights=[
                ExpectedInsight(rule_id="SUSTAINED_DECLINE", mode="flag"),
            ],
            expected_highest_mode="flag",
        )
        result = runner.run(scenario)
        assert_insight_present(result, "SUSTAINED_DECLINE", "flag")


# ===================================================================
# 7. EDGE CASES
# ===================================================================

class TestEdgeCases:
    """Edge cases with sparse data, no plan, special training states."""

    def test_new_athlete_2_activities(self, runner):
        """New athlete with only 2 activities → conservative, mostly silent."""
        scenario = TrainingScenario(
            name="Edge: new athlete, 2 activities",
            description="Brand new athlete, 2 runs. System should compute what it can, stay silent.",
            category="edge_cases",
            trigger_date=TODAY,
            activities=[
                MockActivity(date=days_ago(3, TODAY), distance_miles=3, duration_minutes=30, avg_hr=155),
                MockActivity(date=days_ago(1, TODAY), distance_miles=4, duration_minutes=38, avg_hr=150),
            ],
            # With so little data, expect no meaningful insights
            expected_insights=[],
            expect_no_swap=True,
        )
        result = runner.run(scenario)
        assert_no_workout_swap(result)
        # Should NOT flag anything with only 2 data points
        assert_insight_absent(result, "SUSTAINED_DECLINE")
        assert_insight_absent(result, "SUSTAINED_MISSED")

    def test_athlete_no_plan(self, runner):
        """Athlete with activities but no training plan → readiness still computes."""
        scenario = TrainingScenario(
            name="Edge: no training plan",
            description="Athlete runs regularly but has no plan. Readiness should still compute.",
            category="edge_cases",
            trigger_date=TODAY,
            activities=[
                MockActivity(date=days_ago(i, TODAY), distance_miles=6, duration_minutes=54, avg_hr=142)
                for i in range(1, 8)
            ],
            planned_workouts=[],  # No plan
        )
        result = runner.run(scenario)
        # Readiness should still produce a score (TSB and efficiency still work)
        assert result.readiness.score is not None

    def test_athlete_mid_taper(self, runner):
        """Athlete in taper week → reduced volume is expected, not concerning."""
        # 3 weeks of normal + 1 week of deliberate taper
        normal = build_week_of_activities(_mon(2), [7, 8, 0, 7, 6, 0, 16], base_hr=142)
        taper = build_week_of_activities(_mon(1), [5, 0, 4, 0, 3, 0, 8], base_hr=135)

        scenario = TrainingScenario(
            name="Edge: mid-taper volume drop",
            description="Athlete is tapering — 50% volume drop is EXPECTED, not a problem",
            category="edge_cases",
            trigger_date=_mon(1) + timedelta(days=3),
            activities=normal + taper,
            planned_workouts=[
                MockPlannedWorkout(date=_mon(1) + timedelta(days=i), workout_type="easy",
                                   phase="taper", completed=True)
                for i in range(7) if i in [0, 2, 4, 6]
            ],
        )
        result = runner.run(scenario)
        # Should NOT flag the volume drop during taper
        assert_insight_absent(result, "SUSTAINED_DECLINE")
        assert_no_workout_swap(result)

    def test_athlete_returning_from_injury(self, runner):
        """Athlete returning from injury → conservative, 2-week gap in training."""
        # 2 weeks of nothing, then 3 short runs
        scenario = TrainingScenario(
            name="Edge: returning from injury",
            description="2 weeks off, just started back. System should be conservative.",
            category="edge_cases",
            trigger_date=TODAY,
            activities=[
                # Gap: nothing for 2 weeks
                MockActivity(date=days_ago(3, TODAY), distance_miles=2, duration_minutes=22, avg_hr=155),
                MockActivity(date=days_ago(2, TODAY), distance_miles=3, duration_minutes=30, avg_hr=152),
                MockActivity(date=days_ago(1, TODAY), distance_miles=3, duration_minutes=29, avg_hr=150),
            ],
        )
        result = runner.run(scenario)
        assert_no_workout_swap(result)
        # Should not produce overload warnings from 2-3 mile runs
        assert_insight_absent(result, "LOAD_SPIKE")

    def test_rest_day_skipped(self, runner):
        """Athlete skips a planned workout → log but don't overreact to one skip."""
        scenario = TrainingScenario(
            name="Edge: single skipped workout",
            description="One skipped easy run. Log it, don't flag — life happens.",
            category="edge_cases",
            trigger_date=TODAY,
            planned_workouts=[
                MockPlannedWorkout(date=days_ago(1, TODAY), workout_type="easy",
                                   target_distance_miles=6, skipped=True, skip_reason="work meeting"),
                MockPlannedWorkout(date=TODAY, workout_type="threshold",
                                   target_distance_miles=7),
            ],
        )
        result = runner.run(scenario)
        assert_no_workout_swap(result)
        # Single skip should NOT trigger sustained missed pattern
        assert_insight_absent(result, "SUSTAINED_MISSED")

    def test_unplanned_quality_session(self, runner):
        """Athlete does a quality session not in the plan → detect and log."""
        scenario = TrainingScenario(
            name="Edge: unplanned quality session",
            description="No workout planned for today, athlete runs intervals. Log it.",
            category="edge_cases",
            trigger_date=TODAY,
            planned_workouts=[],  # Nothing planned today
            activities=[
                MockActivity(date=TODAY, distance_miles=6, duration_minutes=42,
                             avg_hr=165, workout_type="tempo_run",
                             name="Felt restless, ran hard"),
            ],
        )
        result = runner.run(scenario)
        assert_no_workout_swap(result)


# ===================================================================
# Collect all scenarios for diagnostic output
# ===================================================================

ALL_SCENARIOS = {
    "golden": [
        "Golden Scenario: Founder's 51→60 week",
    ],
    "readiness": [
        "Declining efficiency → lower readiness",
        "High completion → higher readiness",
        "Missing signals → graceful degradation",
        "All signals → full confidence",
    ],
    "rules": [
        "Rule 1: Load spike detected",
        "Rule 2: Self-regulation delta",
        "Rule 3: Efficiency breakthrough",
        "Rule 4: Pace improvement + lower HR",
        "Rule 5: Sustained decline (3+ weeks)",
        "Rule 6: Sustained missed sessions",
        "Rule 7: Readiness consistently high",
    ],
    "self_regulation": [
        "Self-reg: easy → quality",
        "Self-reg: quality → easy",
        "Self-reg: distance reduction",
    ],
    "sustained_trends": [
        "2-week decline → no flag",
        "3-week decline → flag",
        "Post-load-spike dip → no flag",
    ],
    "false_positive": [
        "Load spike + normal recovery → inform, not flag",
        "Load spike + 3-week decline → flag",
    ],
    "edge_cases": [
        "New athlete, 2 activities",
        "No training plan",
        "Mid-taper volume drop",
        "Returning from injury",
        "Single skipped workout",
        "Unplanned quality session",
    ],
}
