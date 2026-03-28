"""
Tests for Pace Calculator Integration

Tests the full data flow:
1. RPI calculation from race times
2. Training pace generation
3. Pace description formatting
4. Plan generation with paces
"""

import pytest
from datetime import date, timedelta
from uuid import uuid4
from types import SimpleNamespace
from unittest.mock import MagicMock

from services.plan_framework.pace_engine import PaceEngine, TrainingPaces
from services.plan_framework.constants import VolumeTier
from services.model_driven_plan_generator import ModelDrivenPlanGenerator


class TestPaceEngine:
    """Tests for the PaceEngine class."""
    
    def setup_method(self):
        self.engine = PaceEngine()
    
    def test_calculate_from_5k_race(self):
        """Test RPI calculation from a 5K race time."""
        # 20:00 5K = approximately RPI 50
        paces = self.engine.calculate_from_race(
            distance="5k",
            time_seconds=1200  # 20:00
        )
        
        assert paces is not None
        assert paces.rpi is not None
        assert 48 <= paces.rpi <= 52  # Reasonable range for 20min 5K
        assert paces.easy_pace_low > 0
        assert paces.threshold_pace > 0
        assert paces.marathon_pace > 0
    
    def test_calculate_from_marathon_race(self):
        """Test RPI calculation from a marathon time."""
        # 4:00:00 marathon
        paces = self.engine.calculate_from_race(
            distance="marathon",
            time_seconds=14400  # 4 hours
        )
        
        assert paces is not None
        assert paces.rpi is not None
        assert paces.marathon_pace > 0
    
    def test_calculate_from_half_marathon(self):
        """Test RPI calculation from half marathon."""
        # 1:45:00 half marathon
        paces = self.engine.calculate_from_race(
            distance="half_marathon",
            time_seconds=6300  # 1:45:00
        )
        
        assert paces is not None
        assert paces.rpi is not None
    
    def test_invalid_distance_returns_none(self):
        """Test that invalid distance returns None."""
        paces = self.engine.calculate_from_race(
            distance="invalid",
            time_seconds=1200
        )
        
        assert paces is None
    
    def test_invalid_time_returns_none(self):
        """Test that invalid time returns None."""
        paces = self.engine.calculate_from_race(
            distance="5k",
            time_seconds=0
        )
        
        assert paces is None


class TestTrainingPaces:
    """Tests for TrainingPaces pace descriptions."""
    
    def setup_method(self):
        # Create a sample TrainingPaces object (approximately 50 RPI)
        self.paces = TrainingPaces(
            rpi=50.0,
            race_distance="5k",
            race_time_seconds=1200,
            easy_pace_low=570,   # 9:30
            easy_pace_high=600,  # 10:00
            marathon_pace=495,   # 8:15
            threshold_pace=450,  # 7:30
            interval_pace=405,   # 6:45
            repetition_pace=360, # 6:00
            easy_pace_per_km_low=354,
            easy_pace_per_km_high=373,
            marathon_pace_per_km=308,
            threshold_pace_per_km=280,
            interval_pace_per_km=252,
            repetition_pace_per_km=224,
        )
    
    def test_easy_pace_description(self):
        """Test easy pace includes effort context."""
        desc = self.paces.get_pace_description("easy")
        assert "9:30" in desc
        assert "10:00" in desc
        assert "conversational" in desc.lower()
    
    def test_long_run_pace_description(self):
        """Test long run pace includes effort context."""
        desc = self.paces.get_pace_description("long")
        assert "9:30" in desc or "10:00" in desc
        assert "easy" in desc.lower() or "sustainable" in desc.lower()
    
    def test_marathon_pace_description(self):
        """Test marathon pace includes effort context."""
        desc = self.paces.get_pace_description("marathon_pace")
        assert "8:15" in desc
        assert "goal" in desc.lower() or "race" in desc.lower()
    
    def test_threshold_pace_description(self):
        """Test threshold pace includes effort context."""
        desc = self.paces.get_pace_description("threshold")
        assert "7:30" in desc
        assert "comfortably hard" in desc.lower()
    
    def test_interval_pace_description(self):
        """Test interval pace includes effort context."""
        desc = self.paces.get_pace_description("intervals")
        assert "6:45" in desc
        assert "hard" in desc.lower()
    
    def test_strides_pace_description(self):
        """Test strides pace includes effort context."""
        desc = self.paces.get_pace_description("strides")
        assert "6:00" in desc
        assert "quick" in desc.lower() or "controlled" in desc.lower()
    
    def test_unknown_workout_type(self):
        """Test unknown workout type returns default."""
        desc = self.paces.get_pace_description("unknown_type")
        assert "conversational" in desc.lower()

    def test_enforce_pace_order_contract_corrects_inversion(self):
        self.paces.marathon_pace = 450
        self.paces.threshold_pace = 455
        self.paces.interval_pace = 460
        self.paces.repetition_pace = 465
        self.paces.enforce_pace_order_contract()
        assert self.paces.interval_pace < self.paces.threshold_pace < self.paces.marathon_pace
        assert self.paces.repetition_pace < self.paces.interval_pace


class TestPaceFormat:
    """Tests for pace formatting."""
    
    def test_format_pace_minutes_seconds(self):
        """Test pace formatting with minutes and seconds."""
        paces = TrainingPaces(
            rpi=50.0,
            race_distance="5k",
            race_time_seconds=1200,
            easy_pace_low=570,   # 9:30
            easy_pace_high=605,  # 10:05
            marathon_pace=495,
            threshold_pace=450,
            interval_pace=405,
            repetition_pace=360,
            easy_pace_per_km_low=354,
            easy_pace_per_km_high=376,
            marathon_pace_per_km=308,
            threshold_pace_per_km=280,
            interval_pace_per_km=252,
            repetition_pace_per_km=224,
        )
        
        formatted = paces._format_pace(570)
        assert formatted == "9:30"
        
        formatted = paces._format_pace(605)
        assert formatted == "10:05"
        
        formatted = paces._format_pace(360)
        assert formatted == "6:00"


class TestModelDrivenPaceContract:
    def test_model_driven_enforces_pace_order_strings(self):
        gen = ModelDrivenPlanGenerator(db=MagicMock())
        corrected = gen._enforce_pace_order_strings(
            {
                "e_pace": "9:00/mi",
                "m_pace": "8:00/mi",
                "t_pace": "8:05/mi",
                "i_pace": "8:10/mi",
                "r_pace": "8:15/mi",
            }
        )
        to_sec = lambda p: int(p.split(":")[0]) * 60 + int(p.split(":")[1].split("/")[0])
        assert to_sec(corrected["i_pace"]) < to_sec(corrected["t_pace"]) < to_sec(corrected["m_pace"])
        assert to_sec(corrected["r_pace"]) < to_sec(corrected["i_pace"])


class TestPaceOrderInvariants:
    """
    WS-D / spec test: pace order must hold across the full realistic RPI range.
    interval < threshold < marathon (lower value = faster pace in min/mi).
    Source: BUILDER_INSTRUCTIONS_2026-03-23_PLAN_INTEGRITY_SYSTEMIC_RECOVERY.md §WS-D.
    """

    RPI_RANGE = [35, 40, 45, 50, 55, 60, 65, 70]  # sec/km — spans 7:30 to ~4:45/mi easy

    @pytest.mark.parametrize("rpi", RPI_RANGE)
    def test_pace_order_invariants_hold_across_rpi_range(self, rpi):
        """For every RPI in the realistic training range, interval < threshold < marathon.
        Values are minutes/mile floats — lower = faster."""
        from services.workout_prescription import calculate_paces_from_rpi
        paces = calculate_paces_from_rpi(rpi)

        interval_mpmi = paces.get("interval")
        threshold_mpmi = paces.get("threshold")
        marathon_mpmi = paces.get("marathon")

        assert interval_mpmi is not None, f"RPI={rpi}: interval pace not set"
        assert threshold_mpmi is not None, f"RPI={rpi}: threshold pace not set"
        assert marathon_mpmi is not None, f"RPI={rpi}: marathon pace not set"

        assert interval_mpmi < threshold_mpmi, (
            f"RPI={rpi}: interval ({interval_mpmi:.2f} min/mi) must be faster than "
            f"threshold ({threshold_mpmi:.2f} min/mi)"
        )
        assert threshold_mpmi < marathon_mpmi, (
            f"RPI={rpi}: threshold ({threshold_mpmi:.2f} min/mi) must be faster than "
            f"marathon ({marathon_mpmi:.2f} min/mi)"
        )

    def test_all_generator_paths_enforce_pace_order_invariants(self):
        """
        All active generator backends must produce paces where interval < threshold < marathon.
        Tests:
          - PaceEngine raw output (standard/semi-custom basis)
          - ModelDrivenPlanGenerator._enforce_pace_order_strings
          - WorkoutPrescriptionGenerator._enforce_pace_order_contract
        """
        from services.workout_prescription import calculate_paces_from_rpi, _enforce_pace_order_contract

        rpi = 50  # Mid-range

        # 1. Raw pace engine output (used by standard/semi-custom)
        paces = calculate_paces_from_rpi(rpi)
        assert paces["interval"] < paces["threshold"] < paces["marathon"], (
            f"calculate_paces_from_rpi: order violated: {paces}"
        )

        # 2. After _enforce_pace_order_contract (used by WorkoutPrescriptionGenerator)
        enforced, diagnostics = _enforce_pace_order_contract(paces)
        assert enforced["interval"] < enforced["threshold"] < enforced["marathon"], (
            f"_enforce_pace_order_contract output: order violated: {enforced}; diagnostics: {diagnostics}"
        )

        # 3. ModelDrivenPlanGenerator path (string-based)
        gen = ModelDrivenPlanGenerator(db=MagicMock())
        from services.workout_prescription import format_pace

        pace_strs = {
            "e_pace": f"{format_pace(paces['easy'])}/mi",
            "m_pace": f"{format_pace(paces['marathon'])}/mi",
            "t_pace": f"{format_pace(paces['threshold'])}/mi",
            "i_pace": f"{format_pace(paces['interval'])}/mi",
            "r_pace": f"{format_pace(paces.get('interval', paces['interval']) * 0.93)}/mi",
        }
        corrected = gen._enforce_pace_order_strings(pace_strs)

        def str_to_sec(p: str) -> float:
            clean = p.split("/")[0].strip()
            parts = clean.split(":")
            return int(parts[0]) * 60 + float(parts[1]) if len(parts) == 2 else float(parts[0])

        assert str_to_sec(corrected["i_pace"]) < str_to_sec(corrected["t_pace"]) < str_to_sec(corrected["m_pace"]), (
            f"ModelDrivenPlanGenerator: pace order violated after enforcement: {corrected}"
        )

        # 4. WorkoutPrescriptionGenerator (constraint-aware path) — mock bank
        from services.workout_prescription import WorkoutPrescriptionGenerator

        bank = MagicMock()
        bank.best_rpi = rpi
        bank.current_long_run_miles = 14.0
        bank.average_long_run_miles = 13.0
        bank.peak_long_run_miles = 18.0
        bank.current_weekly_miles = 50.0
        bank.recent_8w_p75_long_run_miles = 14.0
        bank.recent_16w_p50_long_run_miles = 13.0
        bank.recent_16w_run_count = 48
        bank.constraint_type.value = "none"
        bank.experience_level.value = "experienced"
        bank.race_performances = []

        wpg = WorkoutPrescriptionGenerator(bank, race_distance="marathon")
        wpg_interval = wpg.paces.get("interval")
        wpg_threshold = wpg.paces.get("threshold")
        wpg_marathon = wpg.paces.get("marathon")

        assert wpg_interval is not None and wpg_threshold is not None and wpg_marathon is not None, (
            f"WorkoutPrescriptionGenerator: missing paces: {wpg.paces}"
        )
        assert wpg_interval < wpg_threshold < wpg_marathon, (
            f"WorkoutPrescriptionGenerator: pace order violated: {wpg.paces}"
        )
