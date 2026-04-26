"""
Cross-Training Coach Context Tests

Commit 4 of Cross-Training Session Detail Capture (Phase A).
Tests _build_cross_training_context function — verifies it produces
correct output format and handles edge cases.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class TestCrossTrainingCoachContextImport:
    def test_function_importable(self):
        from services.ai_coach import _build_cross_training_context
        assert callable(_build_cross_training_context)

    def test_function_returns_none_for_missing_db(self):
        """Verify the function handles graceful failure."""
        from services.ai_coach import _build_cross_training_context

        class FakeQuery:
            def filter(self, *args, **kwargs):
                return self

            def order_by(self, *args, **kwargs):
                return self

            def all(self):
                return []

        class FakeDB:
            def query(self, *args, **kwargs):
                return FakeQuery()

        result = _build_cross_training_context("fake-uuid", FakeDB())
        assert result is None

    def test_function_returns_string_with_strength_data(self):
        """Verify the function returns formatted string when strength data exists."""
        from services.ai_coach import _build_cross_training_context
        from datetime import datetime, timezone, timedelta
        from unittest.mock import MagicMock, patch
        from uuid import uuid4

        mock_activity = MagicMock()
        mock_activity.id = uuid4()
        mock_activity.sport = "strength"
        mock_activity.start_time = datetime.now(timezone.utc) - timedelta(hours=12)
        mock_activity.duration_s = 3600
        mock_activity.strength_session_type = "maximal"
        mock_activity.athlete_id = uuid4()

        class FakeQuery:
            def __init__(self, results=None):
                self._results = results or []

            def filter(self, *args, **kwargs):
                return self

            def order_by(self, *args, **kwargs):
                return self

            def all(self):
                return self._results

        call_count = [0]

        class FakeDB:
            def query(self, model):
                call_count[0] += 1
                if call_count[0] == 1:
                    return FakeQuery([mock_activity])
                return FakeQuery([])

        result = _build_cross_training_context("fake-uuid", FakeDB())
        assert result is not None
        assert "CROSS-TRAINING CONTEXT" in result
        assert "Strength: 1 session" in result
        assert "maximal session" in result
        assert "hours ago" in result

    def test_function_contains_no_prescription_note(self):
        """Verify the coach guidance note is present."""
        from services.ai_coach import _build_cross_training_context
        from datetime import datetime, timezone, timedelta
        from unittest.mock import MagicMock
        from uuid import uuid4

        mock_activity = MagicMock()
        mock_activity.id = uuid4()
        mock_activity.sport = "flexibility"
        mock_activity.start_time = datetime.now(timezone.utc) - timedelta(hours=6)
        mock_activity.duration_s = 1800

        call_count = [0]

        class FakeQuery:
            def __init__(self, results=None):
                self._results = results or []

            def filter(self, *args, **kwargs):
                return self

            def order_by(self, *args, **kwargs):
                return self

            def all(self):
                return self._results

        class FakeDB:
            def query(self, model):
                call_count[0] += 1
                if call_count[0] == 1:
                    return FakeQuery([])
                if call_count[0] == 2:
                    return FakeQuery([])
                return FakeQuery([mock_activity])

        result = _build_cross_training_context("fake-uuid", FakeDB())
        assert result is not None
        assert "does NOT prescribe strength programming" in result
