from __future__ import annotations

import logging
from unittest.mock import MagicMock
from uuid import uuid4

from core.config import settings
from services.coaching import runtime_v2_packet
from services.coaching.ledger import VALID_FACT_FIELDS
from services.coaching.runtime_v2_packet import assemble_v2_packet


def _facts_with_coverage(field_count: int) -> dict[str, dict[str, object]]:
    return {
        field: {"value": index, "confidence": "athlete_stated"}
        for index, field in enumerate(sorted(VALID_FACT_FIELDS)[:field_count], start=1)
    }


def test_legacy_shim_threshold_respects_env_override(monkeypatch):
    monkeypatch.setattr(
        runtime_v2_packet,
        "_athlete_facts_payload",
        lambda db, athlete_id: _facts_with_coverage(9),
    )
    monkeypatch.setattr(settings, "COACH_LEDGER_COVERAGE_SHIM_THRESHOLD", 0.9)

    packet = assemble_v2_packet(
        athlete_id=uuid4(),
        db=None,
        message="Should I add volume?",
        conversation_context=[],
        legacy_athlete_state="Structured legacy context line.",
    )

    shim = packet["blocks"]["_legacy_context_bridge_deprecated"]
    assert shim["status"] == "deprecated_fallback"
    assert shim["data"]["legacy_context_bridge"] == "Structured legacy context line."
    assert shim["data"]["bridge_note"].endswith("90%.")


def test_legacy_shim_active_emits_warning_log(monkeypatch):
    monkeypatch.setattr(
        runtime_v2_packet,
        "_athlete_facts_payload",
        lambda db, athlete_id: _facts_with_coverage(1),
    )
    monkeypatch.setattr(settings, "COACH_LEDGER_COVERAGE_SHIM_THRESHOLD", 0.5)
    athlete_id = uuid4()
    warning_spy = MagicMock()
    monkeypatch.setattr(runtime_v2_packet.logger, "warning", warning_spy)

    packet = assemble_v2_packet(
        athlete_id=athlete_id,
        db=None,
        message="Should I add volume?",
        conversation_context=[],
        legacy_athlete_state="Today line removed.\nDurable legacy context.",
    )

    assert packet["blocks"]["_legacy_context_bridge_deprecated"]["status"] == "deprecated_fallback"
    warning_spy.assert_called_once()
    message, = warning_spy.call_args.args
    extra = warning_spy.call_args.kwargs["extra"]
    assert message == "coach_runtime_v2_legacy_context_shim_active"
    assert extra["athlete_id"] == str(athlete_id)
    assert extra["threshold"] == 0.5
    assert extra["ledger_field_coverage"] < 0.5
    assert extra["legacy_context_chars"] == len("Durable legacy context.")
    assert extra["removed_temporal_lines_count"] == 1


def test_legacy_shim_silent_when_coverage_high(monkeypatch, caplog):
    monkeypatch.setattr(
        runtime_v2_packet,
        "_athlete_facts_payload",
        lambda db, athlete_id: _facts_with_coverage(len(VALID_FACT_FIELDS)),
    )
    monkeypatch.setattr(settings, "COACH_LEDGER_COVERAGE_SHIM_THRESHOLD", 0.5)

    with caplog.at_level(logging.WARNING):
        packet = assemble_v2_packet(
            athlete_id=uuid4(),
            db=None,
            message="Should I add volume?",
            conversation_context=[],
            legacy_athlete_state="Durable legacy context.",
        )

    shim = packet["blocks"]["_legacy_context_bridge_deprecated"]
    assert shim["status"] == "empty"
    assert shim["data"]["legacy_context_bridge"] == ""
    assert "coach_runtime_v2_legacy_context_shim_active" not in caplog.text
