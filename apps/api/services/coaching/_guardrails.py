from __future__ import annotations

import os
import json
import re
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional, Dict, List, Any, Tuple
from uuid import UUID, uuid4
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from services.coaching._constants import (
    _strip_emojis,
    _check_response_quality,
)  # noqa: E402
from services import coach_tools  # noqa: E402
from services.coaching._conversation_contract import (  # noqa: E402
    build_conversation_contract_retry_instruction,
    enforce_conversation_contract_output,
    validate_conversation_contract_response,
)


class GuardrailsMixin:
    """Mixin extracted from AICoach - guardrails methods."""

    def _maybe_update_units_preference(self, athlete_id: UUID, message: str) -> None:
        try:
            ml = (message or "").lower()
            wants_miles = ("miles" in ml) and (
                "always" in ml or "not kilometers" in ml or "not km" in ml
            )
            wants_km = ("kilometers" in ml or "km" in ml) and (
                "always" in ml or "not miles" in ml
            )

            if not (wants_miles or wants_km):
                return

            athlete = self.db.query(Athlete).filter(Athlete.id == athlete_id).first()
            if not athlete:
                return

            target = "imperial" if wants_miles else "metric"
            if athlete.preferred_units != target:
                athlete.preferred_units = target
                athlete.preferred_units_set_explicitly = True
                self.db.commit()
        except Exception:
            try:
                self.db.rollback()
            except Exception:
                pass

    def _maybe_update_intent_snapshot(self, athlete_id: UUID, message: str) -> None:
        """
        Best-effort extraction of athlete intent/constraints from free text.

        This supports self-guided coaching without requiring a rigid UI flow:
        when the athlete answers an intent/pain/time question, we persist it.
        """
        try:
            text = (message or "").strip()
            if not text:
                return

            ml = text.lower()
            updates: Dict[str, Any] = {}

            # Intent keywords (athlete-led)
            if any(
                k in ml
                for k in (
                    "train through",
                    "through fatigue",
                    "cumulative fatigue",
                    "build fatigue",
                    "stack fatigue",
                )
            ):
                updates["training_intent"] = "through_fatigue"
            elif any(
                k in ml
                for k in (
                    "freshen",
                    "taper",
                    "peak",
                    "sharpen",
                    "race soon",
                    "benchmark",
                )
            ):
                updates["training_intent"] = "freshen_for_event"

            # Pain flags
            if "niggle" in ml:
                updates["pain_flag"] = "niggle"
            if "pain" in ml and "no pain" not in ml:
                updates["pain_flag"] = "pain"
            if any(k in ml for k in ("no pain", "pain-free", "pain free")):
                updates["pain_flag"] = "none"

            # Time available (minutes)
            m = re.search(r"\b(\d{2,3})\s*(min|mins|minutes)\b", ml)
            if m:
                try:
                    updates["time_available_min"] = int(m.group(1))
                except Exception:
                    pass

            # Weekly mileage target (mpw) - expanded to catch more patterns
            m2 = re.search(
                r"\b(\d{2,3})\s*(mpw|miles per week|mi per week|miles?\s+(?:this|per|a)\s+week|this week)\b",
                ml,
            )
            if m2:
                try:
                    updates["weekly_mileage_target"] = float(m2.group(1))
                except Exception:
                    pass
            # Also catch "running 55 this week" pattern
            if not m2:
                m2b = re.search(r"running\s+(\d{2,3})\s+(?:this|per|a)\s+week", ml)
                if m2b:
                    try:
                        updates["weekly_mileage_target"] = float(m2b.group(1))
                    except Exception:
                        pass

            # Optional event date (YYYY-MM-DD)
            m3 = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", ml)
            if m3:
                updates["next_event_date"] = m3.group(1)
                if "race" in ml:
                    updates["next_event_type"] = "race"
                elif "benchmark" in ml or "time trial" in ml:
                    updates["next_event_type"] = "benchmark"

            if not updates:
                return

            coach_tools.set_coach_intent_snapshot(self.db, athlete_id, **updates)
        except Exception:
            # Never block chat on snapshot parsing.
            try:
                self.db.rollback()
            except Exception:
                pass

    def _validate_tool_usage(
        self,
        message: str,
        tools_called: List[str],
        tool_calls_count: int,
    ) -> tuple[bool, str]:
        """
        Validate that a data question called appropriate tools.

        Returns:
            (is_valid, reason) - True if tool usage was appropriate, False with reason if not.
        """
        if not self._is_data_question(message):
            # Not a data question - no tool validation needed
            return True, "not_data_question"

        if tool_calls_count == 0:
            return False, "no_tools_called"

        # Check for core data tools
        data_tools = [
            "get_recent_runs",
            "search_activities",
            "get_calendar_day_context",
            "get_training_load",
            "get_weekly_volume",
            "get_training_paces",
            "get_race_predictions",
            "get_race_strategy_packet",
            "get_training_block_narrative",
            "get_nutrition_log",
            "get_nutrition_correlations",
            "get_best_runs",
            "get_mile_splits",
            "analyze_run_streams",
        ]
        if not any(t in tools_called for t in data_tools):
            return False, "no_data_tools_called"

        return True, "ok"

    def _is_profile_edit_intent(self, user_message: str) -> bool:
        lower = (user_message or "").lower()
        if not lower:
            return False
        asks_location = any(
            token in lower
            for token in (
                "where",
                "how do i change",
                "how do i edit",
                "update my",
                "fix my",
            )
        )
        return bool(self._PROFILE_TERMS_RE.search(lower)) and asks_location

    def _infer_profile_field_from_message(self, user_message: str) -> str:
        lower = (user_message or "").lower()
        if any(k in lower for k in ("birthdate", "birthday", "dob", "age")):
            return "birthdate"
        if any(k in lower for k in ("sex", "gender")):
            return "sex"
        if "height" in lower:
            return "height_cm"
        if "email" in lower:
            return "email"
        if any(k in lower for k in ("name", "display name")):
            return "display_name"
        return "birthdate"

    def _infer_intent_band(self, text: str, *, is_user: bool) -> str:
        lower = (text or "").lower().strip()
        if not lower:
            return "unknown"

        if self._is_profile_edit_intent(lower):
            return "profile"
        if self._LOGISTICS_TERMS_RE.search(lower):
            return "logistics"
        if self._PLANNING_TERMS_RE.search(lower):
            return "planning"
        if self._ANALYSIS_TERMS_RE.search(lower):
            return "analysis"

        # Allow assistant correction style to be identified as apology.
        if self._APOLOGY_TERMS_RE.search(lower):
            return "apology"
        if is_user and any(
            t in lower for t in ("wrong answer", "off topic", "not what i asked")
        ):
            return "apology"
        return "general"

    def _intent_bands_compatible(self, user_band: str, assistant_band: str) -> bool:
        compatibility = {
            "profile": {"profile", "logistics"},
            "logistics": {"logistics", "profile"},
            "planning": {"planning", "analysis", "general"},
            "analysis": {"analysis", "planning", "general"},
            "apology": {
                "apology",
                "general",
                "analysis",
                "planning",
                "logistics",
                "profile",
            },
            "general": {
                "general",
                "analysis",
                "planning",
                "logistics",
                "profile",
                "apology",
            },
            "unknown": {
                "general",
                "analysis",
                "planning",
                "logistics",
                "profile",
                "apology",
            },
        }
        return assistant_band in compatibility.get(user_band, {"general"})

    def _record_turn_guard_event(
        self,
        *,
        athlete_id: UUID,
        event: str,
        user_band: str,
        assistant_band: str,
        turn_id: str,
        stage: str,
        is_synthetic_probe: bool,
        is_organic: bool,
    ) -> None:
        logger.info(
            "turn_guard_event event=%s turn_id=%s stage=%s athlete_id=%s user_band=%s assistant_band=%s is_synthetic_probe=%s is_organic=%s",
            event,
            turn_id,
            stage,
            athlete_id,
            user_band,
            assistant_band,
            is_synthetic_probe,
            is_organic,
        )

    def _response_addresses_latest_turn(
        self, user_message: str, assistant_message: str
    ) -> bool:
        """Heuristic guardrail using intent bands to catch turn-mismatch responses."""
        user_lower = (user_message or "").lower().strip()
        assistant_lower = (assistant_message or "").lower().strip()
        if not assistant_lower:
            return False

        user_band = self._infer_intent_band(user_message, is_user=True)
        assistant_band = self._infer_intent_band(assistant_message, is_user=False)

        # Profile edit questions must produce deterministic navigation guidance.
        if self._is_profile_edit_intent(user_message):
            has_profile_path = ("/settings" in assistant_lower) or (
                "personal information" in assistant_lower
            )
            return has_profile_path and self._intent_bands_compatible(
                user_band, assistant_band
            )

        # Correction/apology turns should not drift into unrelated workout analysis.
        if any(t in user_lower for t in ("sorry", "my bad", "apolog")):
            return self._intent_bands_compatible(user_band, assistant_band)

        return self._intent_bands_compatible(user_band, assistant_band)

    def _build_turn_relevance_fallback(
        self, athlete_id: UUID, user_message: str
    ) -> str:
        if self._is_profile_edit_intent(user_message):
            field = self._infer_profile_field_from_message(user_message)
            path = coach_tools.get_profile_edit_paths(self.db, athlete_id, field=field)
            data = path.get("data", {}) if isinstance(path, dict) else {}
            route = data.get("route", "/settings")
            section = data.get("section", "Personal Information")
            field_name = data.get("field", "Birthdate")
            note = data.get("note", "")
            base = f"Go to {route} -> {section} -> {field_name}."
            if note:
                base += f" {note}"
            return base

        return (
            "You're right. I answered the wrong thing. "
            "Please repeat your last question in one line and I'll answer it directly."
        )

    async def _finalize_response_with_turn_guard(
        self,
        *,
        athlete_id: UUID,
        user_message: str,
        response_text: str,
        is_opus: bool,
        conversation_context: List[Dict[str, str]],
        turn_id: str,
        is_synthetic_probe: bool,
        is_organic: bool,
    ) -> str:
        """Normalize/sanitize output and enforce latest-turn relevance with one retry."""
        try:
            normalized = self._normalize_response_for_ui(
                user_message=user_message,
                assistant_message=response_text or "",
            )
        except Exception as e:
            logger.warning(f"Coach response normalization failed: {e}")
            normalized = response_text or ""
        candidate = _strip_emojis(normalized)
        user_band = self._infer_intent_band(user_message, is_user=True)
        candidate_band = self._infer_intent_band(candidate, is_user=False)

        addresses_latest_turn = self._response_addresses_latest_turn(
            user_message, candidate
        )
        contract_ok, contract_reason = validate_conversation_contract_response(
            user_message,
            candidate,
            conversation_context=conversation_context,
        )

        if addresses_latest_turn and contract_ok:
            self._record_turn_guard_event(
                athlete_id=athlete_id,
                event="pass_initial",
                user_band=user_band,
                assistant_band=candidate_band,
                turn_id=turn_id,
                stage="initial",
                is_synthetic_probe=is_synthetic_probe,
                is_organic=is_organic,
            )
            return enforce_conversation_contract_output(
                user_message,
                candidate,
                conversation_context=conversation_context,
            )

        if addresses_latest_turn and not contract_ok:
            self._record_turn_guard_event(
                athlete_id=athlete_id,
                event=f"contract_mismatch:{contract_reason}",
                user_band=user_band,
                assistant_band=candidate_band,
                turn_id=turn_id,
                stage="initial",
                is_synthetic_probe=is_synthetic_probe,
                is_organic=is_organic,
            )
        else:
            self._record_turn_guard_event(
                athlete_id=athlete_id,
                event="mismatch_detected",
                user_band=user_band,
                assistant_band=candidate_band,
                turn_id=turn_id,
                stage="initial",
                is_synthetic_probe=is_synthetic_probe,
                is_organic=is_organic,
            )
        # Profile intents are deterministic; do not burn retry latency/tokens.
        if user_band == "profile":
            fallback = self._build_turn_relevance_fallback(athlete_id, user_message)
            fallback_band = self._infer_intent_band(fallback, is_user=False)
            self._record_turn_guard_event(
                athlete_id=athlete_id,
                event="fallback_used",
                user_band=user_band,
                assistant_band=fallback_band,
                turn_id=turn_id,
                stage="fallback",
                is_synthetic_probe=is_synthetic_probe,
                is_organic=is_organic,
            )
            return fallback

        if addresses_latest_turn and not contract_ok:
            logger.warning(
                "Conversation contract mismatch for athlete %s (%s); retrying once",
                athlete_id,
                contract_reason,
            )
            retry_instruction = build_conversation_contract_retry_instruction(
                user_message,
                contract_reason,
                conversation_context=conversation_context,
            )
        else:
            logger.warning(
                "Turn mismatch detected for athlete %s; retrying once", athlete_id
            )
            retry_instruction = (
                "Answer ONLY the athlete's latest message directly. "
                "Do not continue prior topics. "
                "If this is a profile edit question, provide route + section + field."
            )
        retry_message = f"{user_message}\n\nSYSTEM CORRECTION: {retry_instruction}"

        try:
            if is_opus and self.anthropic_client:
                retry_result = await self.query_opus(
                    athlete_id=athlete_id,
                    message=retry_message,
                    athlete_state=self._build_athlete_state_for_opus(athlete_id),
                    conversation_context=conversation_context,
                )
            else:
                retry_result = await self.query_gemini(
                    athlete_id=athlete_id,
                    message=retry_message,
                    athlete_state="",
                    conversation_context=conversation_context,
                )
            if not retry_result.get("error"):
                retried = _strip_emojis(
                    self._normalize_response_for_ui(
                        user_message=user_message,
                        assistant_message=retry_result.get("response", ""),
                    )
                )
                retried_band = self._infer_intent_band(retried, is_user=False)
                retried_contract_ok, retried_contract_reason = (
                    validate_conversation_contract_response(
                        user_message,
                        retried,
                        conversation_context=conversation_context,
                    )
                )
                if (
                    self._response_addresses_latest_turn(user_message, retried)
                    and retried_contract_ok
                ):
                    self._record_turn_guard_event(
                        athlete_id=athlete_id,
                        event="retry_success",
                        user_band=user_band,
                        assistant_band=retried_band,
                        turn_id=turn_id,
                        stage="retry",
                        is_synthetic_probe=is_synthetic_probe,
                        is_organic=is_organic,
                    )
                    return enforce_conversation_contract_output(
                        user_message,
                        retried,
                        conversation_context=conversation_context,
                    )
                self._record_turn_guard_event(
                    athlete_id=athlete_id,
                    event=(
                        "retry_still_mismatch"
                        if retried_contract_ok
                        else f"retry_contract_mismatch:{retried_contract_reason}"
                    ),
                    user_band=user_band,
                    assistant_band=retried_band,
                    turn_id=turn_id,
                    stage="retry",
                    is_synthetic_probe=is_synthetic_probe,
                    is_organic=is_organic,
                )
        except Exception as e:
            logger.warning(f"Turn-guard retry failed: {e}")

        fallback = self._build_turn_relevance_fallback(athlete_id, user_message)
        fallback_band = self._infer_intent_band(fallback, is_user=False)
        self._record_turn_guard_event(
            athlete_id=athlete_id,
            event="fallback_used",
            user_band=user_band,
            assistant_band=fallback_band,
            turn_id=turn_id,
            stage="fallback",
            is_synthetic_probe=is_synthetic_probe,
            is_organic=is_organic,
        )
        return fallback

    def _normalize_response_for_ui(
        self, *, user_message: str, assistant_message: str
    ) -> str:
        """
        Make coach output consistent and readable across *all* questions.

        Goals:
        - If there's an evidence/receipts block, ensure it is headed by '## Evidence' so the UI can collapse it.
        - Prefer 'Evidence' wording over 'Receipts' wording.
        - Suppress full UUID dumps in the main answer unless explicitly requested.
        """
        text = (assistant_message or "").strip()
        if not text:
            return text

        # Normalize fragile typography before UI rendering/log copying. Some
        # clients display UTF-8 punctuation mojibake as replacement glyphs.
        text = (
            text.replace("\u2014", " - ")
            .replace("\u2013", " - ")
            .replace("\u2011", "-")
            .replace("\u2018", "'")
            .replace("\u2019", "'")
            .replace("\u201c", '"')
            .replace("\u201d", '"')
            .replace("\ufffd??", "-")
            .replace("\ufffd", "")
        )

        for pattern, replacement in self._INTERNAL_LEAK_REWRITES:
            text = pattern.sub(replacement, text)
        text = re.sub(
            r"(?i)\b(schema|table|row|pipeline|prompt|token|inference)\b",
            "training data",
            text,
        )

        wants_ids = self._user_explicitly_requested_ids(user_message)

        # Normalize headings: 'Receipts' -> 'Evidence'
        text = re.sub(r"(?mi)(^|\n)##\s*Receipts\s*$", r"\1## Evidence", text)
        # Suppress internal prompt-contract leakage in user-facing prose.
        text = re.sub(r"(?mi)^\s*authoritative fact capsule.*$", "", text)
        text = re.sub(r"(?mi)^\s*response contract.*$", "", text)

        # Rewrite internal pace-comparison language into athlete-friendly prose.
        # Matches both standalone lines and bullet-list items (e.g. "- Recorded pace…").
        def _rewrite_pace_relation(m: re.Match) -> str:
            prefix = m.group("prefix") or ""
            direction = (m.group("direction") or "").strip().lower()
            amount = (m.group("amount") or "").strip().rstrip(".")
            if not amount:
                return ""
            if direction == "slower":
                return f"{prefix}Pace sat about {amount} off marathon rhythm — controlled effort."
            elif direction == "faster":
                return f"{prefix}Pace was about {amount} quicker than marathon rhythm."
            else:
                return f"{prefix}Pace was about {amount} relative to marathon rhythm."

        text = re.sub(
            r"(?mi)^(?P<prefix>\s*[-*]\s*)?recorded pace vs marathon pace\s*:\s*"
            r"(?P<direction>slower|faster)?\s*(?:by\s*)?(?P<amount>[0-9:]+/mi(?:le)?)?\s*\.?\s*$",
            _rewrite_pace_relation,
            text,
        )
        text = re.sub(r"(?mi)^\s*date\s*:\s*20\d{2}-\d{2}-\d{2}.*$", "", text)
        # The chat contract asks for conversational prose, not markdown section
        # labels. Preserve the label text while removing visual markup.
        text = re.sub(r"\*\*([^*\n]{1,80}:)\*\*", r"\1", text)
        text = re.sub(r"\*\*([^*\n]{1,120})\*\*", r"\1", text)
        text = re.sub(r"\n{3,}", "\n\n", text).strip()

        # If the model wrote a trailing "Receipts" or "Evidence" label without a markdown heading,
        # convert it into a collapsible heading.
        # Examples:
        #   "Receipts\n- 2026-...: ...\n"
        #   "Evidence:\n- 2026-...: ...\n"
        text = re.sub(
            r"(?mi)(^|\n)(receipts|evidence)\s*:\s*\n", r"\1## Evidence\n", text
        )
        text = re.sub(
            r"(?mi)(^|\n)(receipts|evidence)\s*\n(?=\s*[-*]\s*20\d{2}-\d{2}-\d{2})",
            r"\1## Evidence\n",
            text,
        )

        if wants_ids:
            return text

        # Split into main vs evidence to avoid leaking UUIDs into the conversational flow.
        m = re.search(r"(?mi)(^|\n)##\s*Evidence\s*\n", text)
        if m and m.start() is not None:
            split_idx = m.start() + (1 if m.group(1) == "\n" else 0)
            main = text[:split_idx].rstrip()
            evidence = text[split_idx:].lstrip()
        else:
            main, evidence = text, ""

        # Remove UUIDs from main. Prefer removing the whole "(activity id: ...)" clause if present.
        main = re.sub(
            r"(?i)\s*\(?(planned workout|activity)\s*(id)?\s*:\s*%s\)?\s*"
            % self._UUID_RE.pattern,
            "",
            main,
        )
        main = re.sub(self._UUID_RE, "", main)
        # Clean double spaces left behind.
        main = re.sub(r"[ \t]{2,}", " ", main).strip()

        if evidence:
            # In evidence: keep things readable; replace UUIDs with short refs.
            def _uuid_to_ref(match: re.Match) -> str:
                u = match.group(0)
                return f"{u[:8]}…"

            evidence = re.sub(self._UUID_RE, _uuid_to_ref, evidence)
            # Also normalize any "Receipts" mention lingering inside evidence blocks.
            evidence = re.sub(
                r"(?mi)(^|\n)##\s*Receipts\s*\n", r"\1## Evidence\n", evidence
            )
            return (main + "\n\n" + evidence.strip()).strip()

        return main
