"""Regression test: worker must import all symbols from routers.home."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_worker_can_import_briefing_generator():
    from routers.home import generate_coach_home_briefing

    assert callable(generate_coach_home_briefing)


def test_worker_can_import_llm_callers():
    from routers.home import _call_gemini_briefing_sync, _call_opus_briefing_sync

    assert callable(_call_gemini_briefing_sync)
    assert callable(_call_opus_briefing_sync)


def test_worker_can_import_validation():
    from routers.home import _valid_home_briefing_contract, validate_voice_output, _VOICE_FALLBACK

    assert callable(_valid_home_briefing_contract)
    assert callable(validate_voice_output)
    assert isinstance(_VOICE_FALLBACK, str)
