import inspect
import logging
from types import SimpleNamespace
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock

from models import Activity, ActivitySplit, ActivityStream, AthleteFact, CoachChat


def _make_activity(*, athlete_id, name="Test Run"):
    return Activity(
        athlete_id=athlete_id,
        name=name,
        start_time=datetime.now(timezone.utc) - timedelta(days=1),
        sport="run",
        source="test",
        duration_s=3600,
        distance_m=10000,
    )


class TestGetMileSplitsTool:
    def test_stream_only_returns_splits_and_half_times(self, db_session, test_athlete):
        from services.coach_tools import get_mile_splits

        activity = _make_activity(athlete_id=test_athlete.id, name="Marathon Simulation")
        db_session.add(activity)
        db_session.commit()
        db_session.refresh(activity)

        distances = [
            0.0,
            804.672,
            1609.344,
            2414.016,
            3218.688,
            4023.36,
            4828.032,
        ]
        times = [0, 360, 720, 1080, 1440, 1800, 2160]
        heartrate = [130, 132, 134, 136, 138, 140, 142]
        db_session.add(
            ActivityStream(
                activity_id=activity.id,
                stream_data={"distance": distances, "time": times, "heartrate": heartrate},
                channels_available=["distance", "time", "heartrate"],
                point_count=len(times),
                source="test",
            )
        )
        db_session.commit()

        result = get_mile_splits(db_session, test_athlete.id, str(activity.id), unit="mi")
        assert result["ok"] is True
        assert result["data"]["source"] == "stream"
        assert len(result["data"]["splits"]) == 3
        assert result["data"]["summary"]["first_half_seconds"] == 1080
        assert result["data"]["summary"]["second_half_seconds"] == 1080

    def test_device_laps_fallback_when_stream_missing(self, db_session, test_athlete):
        from services.coach_tools import get_mile_splits

        activity = _make_activity(athlete_id=test_athlete.id, name="Lap Run")
        db_session.add(activity)
        db_session.commit()
        db_session.refresh(activity)

        db_session.add_all(
            [
                ActivitySplit(
                    activity_id=activity.id,
                    split_number=1,
                    distance=1609.344,
                    elapsed_time=480,
                    average_heartrate=145,
                ),
                ActivitySplit(
                    activity_id=activity.id,
                    split_number=2,
                    distance=1609.344,
                    elapsed_time=500,
                    average_heartrate=148,
                ),
            ]
        )
        db_session.commit()

        result = get_mile_splits(db_session, test_athlete.id, str(activity.id), unit="mi")
        assert result["ok"] is True
        assert result["data"]["source"] == "device_laps"
        assert len(result["data"]["device_laps"]) == 2

    def test_returns_safe_error_when_no_stream_and_no_laps(self, db_session, test_athlete):
        from services.coach_tools import get_mile_splits

        activity = _make_activity(athlete_id=test_athlete.id, name="No Split Data")
        db_session.add(activity)
        db_session.commit()
        db_session.refresh(activity)

        result = get_mile_splits(db_session, test_athlete.id, str(activity.id), unit="mi")
        assert result["ok"] is False
        assert result["data"]["source"] == "none"
        assert "No split-capable data" in result["error"]

    def test_ownership_guard_blocks_cross_athlete_ids(self, db_session, test_athlete):
        from models import Athlete
        from services.coach_tools import get_mile_splits

        other = Athlete(
            email=f"other_{uuid4()}@example.com",
            display_name="Other Athlete",
            subscription_tier="free",
            birthdate=date(1991, 1, 1),
            sex="F",
        )
        db_session.add(other)
        db_session.commit()
        db_session.refresh(other)

        foreign_activity = _make_activity(athlete_id=other.id, name="Other Athlete Run")
        db_session.add(foreign_activity)
        db_session.commit()
        db_session.refresh(foreign_activity)

        result = get_mile_splits(db_session, test_athlete.id, str(foreign_activity.id), unit="mi")
        assert result["ok"] is False
        assert "Access denied" in result["error"]

    def test_stream_hr_mapping_survives_dropped_non_monotonic_points(self, db_session, test_athlete):
        from services.coach_tools import get_mile_splits

        activity = _make_activity(athlete_id=test_athlete.id, name="Messy Stream Run")
        db_session.add(activity)
        db_session.commit()
        db_session.refresh(activity)

        # Index 2 is dropped (distance goes backwards). HR mapping must keep index alignment.
        distances = [0.0, 804.672, 700.0, 1609.344, 2414.016, 3218.688]
        times = [0, 360, 420, 720, 1080, 1440]
        heartrate = [130, 132, 220, 134, 136, 138]
        db_session.add(
            ActivityStream(
                activity_id=activity.id,
                stream_data={"distance": distances, "time": times, "heartrate": heartrate},
                channels_available=["distance", "time", "heartrate"],
                point_count=len(times),
                source="test",
            )
        )
        db_session.commit()

        result = get_mile_splits(db_session, test_athlete.id, str(activity.id), unit="mi")
        assert result["ok"] is True
        assert result["data"]["source"] == "stream"
        assert len(result["data"]["splits"]) >= 2
        first_split_hr = result["data"]["splits"][0]["average_heartrate"]
        # If index mapping is wrong, dropped-point HR=220 leaks into split average.
        assert first_split_hr is not None
        assert first_split_hr < 200


class TestFactTTLFilteringInCoachPaths:
    def test_expired_temporal_facts_excluded_from_shared_selector(self, db_session, test_athlete):
        from services.ai_coach import AICoach

        chat = CoachChat(
            athlete_id=test_athlete.id,
            context_type="open",
            messages=[],
            is_active=True,
        )
        db_session.add(chat)
        db_session.commit()
        db_session.refresh(chat)

        db_session.add_all(
            [
                AthleteFact(
                    athlete_id=test_athlete.id,
                    fact_type="upcoming_race",
                    fact_key="upcoming_race_name",
                    fact_value="Old race",
                    confidence="athlete_stated",
                    source_chat_id=chat.id,
                    source_excerpt="old race",
                    is_active=True,
                    temporal=True,
                    ttl_days=7,
                    extracted_at=datetime.now(timezone.utc) - timedelta(days=20),
                ),
                AthleteFact(
                    athlete_id=test_athlete.id,
                    fact_type="life_context",
                    fact_key="occupation",
                    fact_value="Engineer",
                    confidence="athlete_stated",
                    source_chat_id=chat.id,
                    source_excerpt="I am an engineer",
                    is_active=True,
                    temporal=False,
                    extracted_at=datetime.now(timezone.utc) - timedelta(days=60),
                ),
            ]
        )
        db_session.commit()

        coach = AICoach(db=db_session)
        selected = coach._get_fresh_athlete_facts(test_athlete.id, max_facts=10)
        selected_keys = {f.fact_key for f in selected}
        assert "upcoming_race_name" not in selected_keys
        assert "occupation" in selected_keys

    def test_selector_used_by_both_query_paths(self):
        from services.ai_coach import AICoach

        opus_source = inspect.getsource(AICoach.query_opus)
        gemini_source = inspect.getsource(AICoach.query_gemini)
        assert "_get_fresh_athlete_facts" in opus_source
        assert "_get_fresh_athlete_facts" in gemini_source


class TestAgeAndScriptGuards:
    def test_calculate_age_before_and_after_birthday(self):
        from core.date_utils import calculate_age

        birthdate = date(1980, 7, 19)
        assert calculate_age(birthdate, date(2026, 7, 18)) == 45
        assert calculate_age(birthdate, date(2026, 7, 19)) == 46

    def test_coach_paths_use_shared_age_helper(self):
        from services import ai_coach, coach_tools

        ai_source = inspect.getsource(ai_coach.AICoach._build_athlete_state_for_opus)
        brief_source = inspect.getsource(coach_tools.build_athlete_brief)
        assert "calculate_age(" in ai_source
        assert "calculate_age(" in brief_source

    def test_set_athlete_data_script_has_no_hardcoded_founder_dob(self):
        import scripts.set_athlete_data as set_athlete_data

        src = inspect.getsource(set_athlete_data)
        assert "1968, 1, 1" not in src
        assert "--force-birthdate" in src


class TestPromptAndOutputHardening:
    def test_banned_phrase_policy_present_in_both_prompts(self):
        from services.ai_coach import AICoach

        opus_source = inspect.getsource(AICoach.query_opus)
        gemini_source = inspect.getsource(AICoach.query_gemini)
        for phrase in [
            "Here's what the data actually shows",
            "Here's what the data shows",
            "Based on the data",
            "Let me break this down",
            "Great question",
            "That's a great question",
            "I'd be happy to",
        ]:
            assert phrase in opus_source
            assert phrase in gemini_source

    def test_strip_emojis_sanitizer(self):
        from services.ai_coach import _strip_emojis

        assert _strip_emojis("Great work today 💪🔥") == "Great work today "
        assert _strip_emojis("No emoji plain text.") == "No emoji plain text."

    def test_banned_phrase_policy_in_runtime_opus_prompt_payload(self):
        import asyncio
        from services.ai_coach import AICoach

        coach = AICoach.__new__(AICoach)
        coach.db = MagicMock()
        coach.track_usage = lambda **kwargs: None
        coach._get_fresh_athlete_facts = lambda athlete_id, max_facts=15: []
        coach.anthropic_client = MagicMock()

        captured = {}

        def _fake_create(**kwargs):
            captured["system"] = kwargs.get("system", "")
            return SimpleNamespace(
                stop_reason="end_turn",
                usage=SimpleNamespace(input_tokens=1, output_tokens=1),
                content=[SimpleNamespace(text="All good.")],
            )

        coach.anthropic_client.messages.create = _fake_create
        result = asyncio.run(
            coach.query_opus(
                athlete_id=uuid4(),
                message="Should I run today?",
                athlete_state="",
                conversation_context=[],
            )
        )
        assert result["error"] is False
        assert "BAN CANNED OPENERS" in captured["system"]
        assert "Here's what the data actually shows" in captured["system"]

    def test_final_chat_response_is_emoji_sanitized(self):
        import asyncio
        from services.ai_coach import AICoach

        coach = AICoach(db=MagicMock())
        coach.router = MagicMock()
        coach.router.classify = MagicMock(return_value=(None, False))
        coach.gemini_client = object()
        coach.anthropic_client = None
        coach.get_model_for_query = MagicMock(return_value=(AICoach.MODEL_DEFAULT, False))
        coach.check_budget = MagicMock(return_value=(True, "ok"))
        coach.get_or_create_thread_with_state = MagicMock(return_value=("thread-1", False))
        coach.get_thread_history = MagicMock(return_value={"messages": []})
        coach.query_gemini = AsyncMock(return_value={"response": "Great work 🔥", "error": False})
        coach._normalize_response_for_ui = MagicMock(side_effect=lambda user_message, assistant_message: assistant_message)
        coach._save_chat_messages = MagicMock()
        coach._maybe_update_units_preference = MagicMock()
        coach._maybe_update_intent_snapshot = MagicMock()

        out = asyncio.run(coach.chat(uuid4(), "How was my run?"))
        assert out["error"] is False
        assert "🔥" not in out["response"]
        coach._save_chat_messages.assert_called_once()
        saved_response = coach._save_chat_messages.call_args[0][2]
        assert "🔥" not in saved_response

    def test_split_tool_registered_for_opus_and_gemini(self):
        from services.ai_coach import AICoach

        coach = AICoach.__new__(AICoach)
        opus_tool_names = [tool["name"] for tool in coach._opus_tools()]
        assert "get_mile_splits" in opus_tool_names
        assert "get_profile_edit_paths" in opus_tool_names

        gemini_source = inspect.getsource(AICoach.query_gemini)
        assert '"name": "get_mile_splits"' in gemini_source
        assert '"name": "get_profile_edit_paths"' in gemini_source

    def test_normalize_scrubs_internal_architecture_language(self):
        from services.ai_coach import AICoach

        coach = AICoach(db=MagicMock())
        raw = "Since you built the platform, our data model and database show this pipeline."
        normalized = coach._normalize_response_for_ui(user_message="Why is this wrong?", assistant_message=raw)
        lower = normalized.lower()
        assert "since you built the platform" not in lower
        assert "data model" not in lower
        assert "database" not in lower
        assert "pipeline" not in lower

    def test_profile_turn_mismatch_falls_back_to_deterministic_path(self):
        import asyncio
        from services.ai_coach import AICoach

        coach = AICoach(db=MagicMock())
        coach.router = MagicMock()
        coach.router.classify = MagicMock(return_value=(None, False))
        coach.gemini_client = object()
        coach.anthropic_client = None
        coach.get_model_for_query = MagicMock(return_value=(AICoach.MODEL_DEFAULT, False))
        coach.check_budget = MagicMock(return_value=(True, "ok"))
        coach.get_or_create_thread_with_state = MagicMock(return_value=("thread-1", False))
        coach.get_thread_history = MagicMock(return_value={"messages": []})
        coach.query_gemini = AsyncMock(
            side_effect=[
                {"response": "Your splits looked controlled across miles.", "error": False},
                {"response": "Negative split pattern remains strong.", "error": False},
            ]
        )
        coach._save_chat_messages = MagicMock()
        coach._maybe_update_units_preference = MagicMock()
        coach._maybe_update_intent_snapshot = MagicMock()

        out = asyncio.run(coach.chat(uuid4(), "Where do I fix my age in my profile?"))
        assert out["error"] is False
        assert "/profile" in out["response"]
        assert "Personal Information" in out["response"]
        assert "Birthdate" in out["response"]
        assert "split" not in out["response"].lower()
        assert coach.query_gemini.await_count == 2

    def test_intent_band_catches_logistics_analysis_mismatch(self):
        from services.ai_coach import AICoach

        coach = AICoach(db=MagicMock())
        ok = coach._response_addresses_latest_turn(
            "How do I cancel my subscription?",
            "Your split pace trend improved after the long run.",
        )
        assert ok is False

    def test_turn_guard_emits_telemetry_events(self, caplog):
        import asyncio
        from services.ai_coach import AICoach

        coach = AICoach(db=MagicMock())
        coach.router = MagicMock()
        coach.router.classify = MagicMock(return_value=(None, False))
        coach.gemini_client = object()
        coach.anthropic_client = None
        coach.get_model_for_query = MagicMock(return_value=(AICoach.MODEL_DEFAULT, False))
        coach.check_budget = MagicMock(return_value=(True, "ok"))
        coach.get_or_create_thread_with_state = MagicMock(return_value=("thread-1", False))
        coach.get_thread_history = MagicMock(return_value={"messages": []})
        coach.query_gemini = AsyncMock(
            side_effect=[
                {"response": "Your splits looked controlled across miles.", "error": False},
                {"response": "Negative split pattern remains strong.", "error": False},
            ]
        )
        coach._save_chat_messages = MagicMock()
        coach._maybe_update_units_preference = MagicMock()
        coach._maybe_update_intent_snapshot = MagicMock()
        caplog.set_level(logging.INFO)

        out = asyncio.run(coach.chat(uuid4(), "Where do I fix my age in my profile?"))
        assert out["error"] is False
        assert "turn_guard_event event=mismatch_detected" in caplog.text
        assert "turn_guard_event event=fallback_used" in caplog.text
