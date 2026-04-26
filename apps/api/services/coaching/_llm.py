from __future__ import annotations

import os
import asyncio
import json
import re
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional, Dict, List, Any, Tuple
from uuid import UUID, uuid4
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

ARTIFACT9_V2_SYSTEM_PROMPT = """You are StrideIQ's coach. The athlete in this turn is the same human you have coached over many sessions. The packet you receive contains the truth about this athlete: structured facts (athlete_facts), recent activities (recent_activities), recent thread summaries (recent_threads), open unknowns (unknowns), the calendar context (calendar_context), and the current conversation.

How you must behave:

1. Anchor every claim about the athlete in a named atom from the packet. Cite the specific session by date or distance, the specific ledger fact, the specific prior thread. If a claim cannot be anchored, do not make it.

2. When a required fact is in unknowns, ask the suggested question or hedge explicitly. Never fill an unknown with generic coaching.

3. Surface the unasked. On every substantive turn, name at least one pattern, risk, contradiction, or opportunity the athlete didn't ask about, drawn from recent_activities, recent_threads, or ledger trends.

4. Commit to one read. Do not enumerate possibilities when one read is more likely. State the read, give the reasoning, and accept that the athlete may push back.

5. End every substantive turn with a decision the athlete can act on. Specific. Concrete. Bounded.

6. Voice register: write as a coach who has internalized Roche, Davis, Green, Eyestone, and McMillan training philosophies and Holmer-level physiology. Direct. Scientifically grounded. Philosophy-anchored. Willing to name mechanisms (lactate, glycogen, fatigue resistance, ventilatory threshold, fueling, durability) when they explain the read. No template praise. No "consider," "you might want to," "great question," "well done." Real verbs. Honest reads. Name what is working and what is not. The bar is "Brady Holmer or David Roche reads this and says 'I couldn't do better.'"

7. Trust the athlete's stated facts. If athlete_facts shows a value with confidence athlete_stated, that wins over derived data. If the athlete corrects you, update immediately and do not repeat the corrected assumption.

8. Never invent a session, a fact, a date, or a metric. If you do not have the atom, you cannot make the claim.

9. The conversation_mode and athlete_stated_overrides in the packet are binding. Honor both.

Coach. Don't analyze."""

V2_SYSTEM_PROMPT = f"{ARTIFACT9_V2_SYSTEM_PROMPT}\n\n<!-- VOICE_CORPUS -->"

from services.coaching._constants import (  # noqa: E402
    _strip_emojis,
    _check_response_quality,
    ANTHROPIC_AVAILABLE,
    GEMINI_AVAILABLE,
    COACH_MAX_INPUT_TOKENS,
    COACH_MAX_OUTPUT_TOKENS,
)
from services.coaching._conversation_contract import (  # noqa: E402
    ConversationContract,
    ConversationContractType,
    classify_conversation_contract,
)
from services.coaching.runtime_v2_packet import packet_to_prompt  # noqa: E402
from services.coaching.voice_enforcement import (  # noqa: E402
    VoiceContractViolation,
    enforce_voice,
)
from core.config import settings  # noqa: E402
from services import coach_tools  # noqa: E402

try:
    from anthropic import Anthropic  # noqa: F401
except ImportError:
    pass

try:
    from google import genai  # noqa: F401
    from google.genai import types as genai_types  # noqa: F401
except ImportError:
    genai = None
    genai_types = None


class LLMMixin:
    """Mixin extracted from AICoach - llm methods."""

    def _conversation_contract_for_message(
        self,
        message: str,
        conversation_context: Optional[List[Dict[str, str]]] = None,
    ) -> ConversationContract | None:
        try:
            return classify_conversation_contract(
                message,
                conversation_context=conversation_context,
            )
        except Exception:
            return None

    @staticmethod
    def _coach_contract_instruction(contract: ConversationContract | None) -> str:
        if not contract:
            return ""
        if contract.contract_type == ConversationContractType.RACE_DAY:
            return (
                "This is race-day execution mode. The first answer must include "
                "the literal plain-text labels Timeline:, Warmup:, Mile by mile:, "
                "and Cue:. Include supplement/fueling timing when relevant. Do not "
                "bold the labels and do not debate whether the athlete should race."
            )
        if contract.contract_type == ConversationContractType.RACE_STRATEGY:
            return (
                "This is race-strategy mode. Ground the answer in the race strategy "
                "packet and include objective, limiter, pacing shape, course risk, "
                "execution cues, success beyond time, and post-race learning."
            )
        if contract.contract_type == ConversationContractType.CORRECTION_DISPUTE:
            return (
                "This is correction/verification mode. Verify with tools where "
                "possible, state what was searched, and do not repeat the disputed claim."
            )
        return ""

    def _requires_first_tool_call(
        self,
        message: str,
        conversation_context: Optional[List[Dict[str, str]]] = None,
    ) -> bool:
        """Whether the first Kimi turn should be forced to call a tool."""
        lower = (message or "").lower()
        general_knowledge_terms = (
            "standard protocol",
            "in general",
            "generally",
            "what is",
            "how does",
            "explain",
        )
        supplement_or_warmup_terms = (
            "bicarb",
            "maurten",
            "sodium bicarbonate",
            "warmup",
            "warm up",
            "caffeine",
        )
        has_general_frame = any(term in lower for term in general_knowledge_terms)
        has_protocol_topic = any(term in lower for term in supplement_or_warmup_terms)
        if has_general_frame and has_protocol_topic:
            return False

        contract = self._conversation_contract_for_message(
            message,
            conversation_context=conversation_context,
        )
        if contract and contract.contract_type in (
            ConversationContractType.RACE_DAY,
            ConversationContractType.RACE_STRATEGY,
            ConversationContractType.CORRECTION_DISPUTE,
        ):
            return True

        if (
            "that workout" in lower
            or "that activity" in lower
            or "16 x" in lower
            or "16x" in lower
        ):
            return True

        return bool(self._is_data_question(message))

    @staticmethod
    def _athlete_state_context_message(athlete_state: str) -> Optional[Dict[str, str]]:
        state = (athlete_state or "").strip()
        if not state:
            return None
        return {
            "role": "user",
            "content": (
                "INTERNAL COACH CONTEXT (not athlete-authored; use for reasoning, "
                "do not quote this label):\n"
                f"{state}"
            ),
        }

    async def query_opus(
        self,
        athlete_id: UUID,
        message: str,
        athlete_state: str,
        conversation_context: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """
        Query Claude Sonnet (MODEL_HIGH_STAKES) for premium-lane decisions (ADR-061).

        Uses Anthropic API with TOOL ACCESS — Sonnet can query any data it needs.
        Reserved for injury/recovery/load decisions and founder queries.
        Function name retained for compatibility — runtime model is claude-sonnet-4-6.
        """
        if not self.anthropic_client:
            return {
                "response": "High-stakes model not available. Please try again.",
                "error": True,
                "model": None,
            }

        # Build messages
        messages = []

        state_message = self._athlete_state_context_message(athlete_state)
        if state_message:
            messages.append(state_message)

        # Add conversation context (last 5 exchanges)
        if conversation_context:
            for msg in conversation_context[-10:]:
                messages.append(
                    {
                        "role": msg.get("role", "user"),
                        "content": msg.get("content", ""),
                    }
                )

        # Add current message
        messages.append({"role": "user", "content": message})

        # Contract note: _build_coach_system_prompt() internally injects
        # _get_fresh_athlete_facts + banned opener policy strings used by tests.
        # Prompt anchors kept here for structural regression tests:
        # - date grounding via _today.isoformat() / today context
        # - ZERO-HALLUCINATION rule
        # - USE THEM PROACTIVELY tool mandate
        # - PERSONAL FINGERPRINT section
        # BANNED OPENERS (must stay in premium prompt contract):
        # "Here's what the data actually shows"
        # "Here's what the data shows"
        # "Based on the data"
        # "Let me break this down"
        # "Great question"
        # "That's a great question"
        # "I'd be happy to"
        system_prompt = self._build_coach_system_prompt(athlete_id)

        try:
            total_input_tokens = 0
            total_output_tokens = 0
            tools_called: List[str] = []

            # Initial call with tools
            response = self.anthropic_client.messages.create(
                model=self.MODEL_HIGH_STAKES,
                system=system_prompt,
                messages=messages,
                max_tokens=COACH_MAX_OUTPUT_TOKENS,
                tools=self._opus_tools(),
            )

            total_input_tokens += (
                response.usage.input_tokens if hasattr(response, "usage") else 0
            )
            total_output_tokens += (
                response.usage.output_tokens if hasattr(response, "usage") else 0
            )

            # Handle tool calls in a loop (max 5 iterations to prevent runaway)
            for _ in range(5):
                if response.stop_reason != "tool_use":
                    break

                # Process tool calls
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        tool_name = block.name
                        tool_input = block.input
                        tool_id = block.id
                        tools_called.append(tool_name)

                        logger.info(
                            f"Sonnet calling tool: {tool_name} with {tool_input}"
                        )
                        result = self._execute_opus_tool(
                            athlete_id, tool_name, tool_input
                        )

                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": tool_id,
                                "content": result,
                            }
                        )

                # Continue conversation with tool results
                # Convert response.content to list of dicts for serialization
                assistant_content = []
                for block in response.content:
                    if block.type == "text":
                        assistant_content.append({"type": "text", "text": block.text})
                    elif block.type == "tool_use":
                        assistant_content.append(
                            {
                                "type": "tool_use",
                                "id": block.id,
                                "name": block.name,
                                "input": block.input,
                            }
                        )
                messages.append({"role": "assistant", "content": assistant_content})
                messages.append({"role": "user", "content": tool_results})

                response = self.anthropic_client.messages.create(
                    model=self.MODEL_HIGH_STAKES,
                    system=system_prompt,
                    messages=messages,
                    max_tokens=COACH_MAX_OUTPUT_TOKENS,
                    tools=self._opus_tools(),
                )

                total_input_tokens += (
                    response.usage.input_tokens if hasattr(response, "usage") else 0
                )
                total_output_tokens += (
                    response.usage.output_tokens if hasattr(response, "usage") else 0
                )

            # Extract final response text
            response_text = ""
            for block in response.content:
                if hasattr(block, "text"):
                    response_text += block.text
            response_text = _strip_emojis(response_text)

            # Post-response validation: data questions must have used tools
            is_valid, reason = self._validate_tool_usage(
                message, tools_called, len(tools_called)
            )
            if not is_valid:
                logger.warning(
                    "Sonnet response failed tool validation (%s) for athlete %s: "
                    "tools_called=%s, message='%.80s'",
                    reason,
                    athlete_id,
                    tools_called,
                    message,
                )

            self.track_usage(
                athlete_id=athlete_id,
                input_tokens=total_input_tokens,
                output_tokens=total_output_tokens,
                model=self.MODEL_HIGH_STAKES,
                is_opus=True,
            )

            logger.info(
                f"Sonnet query completed: athlete={athlete_id}, "
                f"tools_called={tools_called}, "
                f"input_tokens={total_input_tokens}, output_tokens={total_output_tokens}"
            )
            _check_response_quality(
                response_text, self.MODEL_HIGH_STAKES, str(athlete_id)
            )
            return {
                "response": response_text,
                "error": False,
                "model": self.MODEL_HIGH_STAKES,
                "is_high_stakes": True,
                "input_tokens": total_input_tokens,
                "output_tokens": total_output_tokens,
                "tools_called": tools_called,
            }

        except Exception as e:
            logger.error(f"Sonnet query failed for {athlete_id}: {e}")
            return {
                "response": "I encountered an error processing your request. Please try again.",
                "error": True,
                "model": self.MODEL_HIGH_STAKES,
                "error_detail": str(e),
            }

    async def query_kimi_coach(
        self,
        athlete_id: UUID,
        message: str,
        athlete_state: str,
        conversation_context: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """
        Query Kimi canary model for premium-lane tool-calling coach responses.

        Fallback contract:
        - Any Kimi exception -> Sonnet path.
        - Empty final content -> Sonnet path.
        """
        logger.info("kimi_attempt athlete_id=%s", athlete_id)
        started = datetime.now(timezone.utc)
        tools_called: List[str] = []
        model_name = settings.COACH_CANARY_MODEL

        try:
            import openai
        except ImportError:
            logger.warning(
                "kimi_fallback athlete_id=%s fallback_reason=import_error", athlete_id
            )
            return await self.query_opus(
                athlete_id=athlete_id,
                message=message,
                athlete_state=athlete_state,
                conversation_context=conversation_context,
            )

        api_key = settings.KIMI_API_KEY or os.getenv("KIMI_API_KEY")
        if not api_key:
            logger.warning(
                "kimi_fallback athlete_id=%s fallback_reason=missing_api_key",
                athlete_id,
            )
            return await self.query_opus(
                athlete_id=athlete_id,
                message=message,
                athlete_state=athlete_state,
                conversation_context=conversation_context,
            )

        client = openai.AsyncOpenAI(
            api_key=api_key,
            base_url=settings.KIMI_BASE_URL,
            timeout=120,
        )

        messages: List[Dict[str, Any]] = []
        state_message = self._athlete_state_context_message(athlete_state)
        if state_message:
            messages.append(state_message)

        if conversation_context:
            for msg in conversation_context[-10:]:
                role = msg.get("role", "user")
                if role not in ("user", "assistant"):
                    role = "user"
                messages.append({"role": role, "content": msg.get("content", "")})

        contract = self._conversation_contract_for_message(
            message,
            conversation_context=conversation_context,
        )
        contract_instruction = self._coach_contract_instruction(contract)
        messages.append(
            {
                "role": "user",
                "content": (
                    "Use tools when you need athlete-specific data. "
                    "For race strategy or race-day execution, call get_race_strategy_packet "
                    "and use get_training_block_narrative when readiness depends on recent quality work. "
                    "For athlete corrections that a workout exists, call search_activities; "
                    "if the workout is structured but the search result lacks rep proof, call analyze_run_streams before saying you cannot verify it. "
                    "For general sports science questions (supplements, warmup, nutrition timing), "
                    "answer directly from your knowledge and label it as general guidance.\n\n"
                    f"{contract_instruction}\n\n"
                    f"{message}"
                ),
            }
        )

        system_prompt = self._build_coach_system_prompt(athlete_id)

        total_input_tokens = 0
        total_output_tokens = 0
        response = None
        kimi_tools = self._kimi_tools()
        is_reasoning_model = model_name.lower() in ("kimi-k2.5", "kimi-k2.6")
        needs_tools_first = self._requires_first_tool_call(
            message,
            conversation_context=conversation_context,
        )
        for iteration in range(5):
            extra_body: dict = {}
            if is_reasoning_model:
                extra_body["thinking"] = {"type": "disabled"}
            tc = "required" if (iteration == 0 and needs_tools_first) else "auto"
            response = await client.chat.completions.create(
                model=model_name,
                messages=[{"role": "system", "content": system_prompt}] + messages,
                max_tokens=COACH_MAX_OUTPUT_TOKENS,
                tools=kimi_tools,
                tool_choice=tc,
                extra_body=extra_body if extra_body else None,
            )
            usage = getattr(response, "usage", None)
            total_input_tokens += int(getattr(usage, "prompt_tokens", 0) or 0)
            total_output_tokens += int(getattr(usage, "completion_tokens", 0) or 0)

            choice = (response.choices or [None])[0]
            assistant_message = choice.message if choice else None
            tool_calls = list(getattr(assistant_message, "tool_calls", None) or [])
            if not tool_calls:
                break

            serialized_tool_calls = []
            for tool_call in tool_calls:
                fn = getattr(tool_call, "function", None)
                name = getattr(fn, "name", "")
                raw_args = getattr(fn, "arguments", "") or "{}"
                serialized_tool_calls.append(
                    {
                        "id": tool_call.id,
                        "type": "function",
                        "function": {"name": name, "arguments": raw_args},
                    }
                )

            messages.append(
                {
                    "role": "assistant",
                    "content": getattr(assistant_message, "content", "") or "",
                    "tool_calls": serialized_tool_calls,
                    "reasoning_content": getattr(
                        assistant_message, "reasoning_content", ""
                    )
                    or "",
                }
            )

            for tool_call in tool_calls:
                fn = getattr(tool_call, "function", None)
                name = getattr(fn, "name", "")
                raw_args = getattr(fn, "arguments", "") or "{}"
                try:
                    tool_input = json.loads(raw_args)
                except Exception:
                    tool_input = {}
                tools_called.append(name)
                result = self._execute_opus_tool(athlete_id, name, tool_input)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result,
                    }
                )

        choice = (response.choices or [None])[0] if response else None
        assistant_message = choice.message if choice else None
        response_text = ((getattr(assistant_message, "content", "") or "")).strip()
        response_text = _strip_emojis(response_text)

        if not response_text:
            logger.warning(
                "kimi_fallback athlete_id=%s fallback_reason=empty_content", athlete_id
            )
            return await self.query_opus(
                athlete_id=athlete_id,
                message=message,
                athlete_state=athlete_state,
                conversation_context=conversation_context,
            )

        is_valid, reason = self._validate_tool_usage(
            message, tools_called, len(tools_called)
        )
        if not is_valid:
            logger.warning(
                "Kimi response failed tool validation (%s) for athlete %s: tools_called=%s, message='%.80s'",
                reason,
                athlete_id,
                tools_called,
                message,
            )

        self.track_usage(
            athlete_id=athlete_id,
            input_tokens=total_input_tokens,
            output_tokens=total_output_tokens,
            model=model_name,
            is_opus=True,
        )

        latency_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
        logger.info(
            "kimi_success athlete_id=%s kimi_latency_ms=%s kimi_tool_calls_count=%s",
            athlete_id,
            latency_ms,
            len(tools_called),
        )
        _check_response_quality(response_text, model_name, str(athlete_id))
        return {
            "response": response_text,
            "error": False,
            "model": model_name,
            "is_high_stakes": True,
            "input_tokens": total_input_tokens,
            "output_tokens": total_output_tokens,
            "tools_called": tools_called,
            "kimi_latency_ms": latency_ms,
            "kimi_tool_calls_count": len(tools_called),
        }

    async def _query_kimi_with_fallback(
        self,
        athlete_id: UUID,
        message: str,
        athlete_state: str,
        conversation_context: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """Primary coach query path: Kimi K2.5 with silent Sonnet fallback."""
        try:
            return await self.query_kimi_coach(
                athlete_id=athlete_id,
                message=message,
                athlete_state=athlete_state,
                conversation_context=conversation_context,
            )
        except Exception as exc:
            logger.warning(
                "kimi_fallback athlete_id=%s fallback_reason=network_error error=%s",
                athlete_id,
                exc,
            )
            return await self.query_opus(
                athlete_id=athlete_id,
                message=message,
                athlete_state=athlete_state,
                conversation_context=conversation_context,
            )

    async def query_kimi_v2_packet(
        self,
        athlete_id: UUID,
        message: str,
        packet: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Coach Runtime V2 response call: Kimi receives packet only, no tools."""

        logger.info("kimi_v2_packet_attempt athlete_id=%s", athlete_id)
        started = datetime.now(timezone.utc)
        model_name = settings.COACH_CANARY_MODEL

        try:
            import openai
        except ImportError:
            return {
                "response": "",
                "error": True,
                "model": None,
                "fallback_reason": "llm_provider_error",
                "error_class": "openai_import_error",
            }

        api_key = settings.KIMI_API_KEY or os.getenv("KIMI_API_KEY")
        if not api_key:
            return {
                "response": "",
                "error": True,
                "model": model_name,
                "fallback_reason": "llm_provider_error",
                "error_class": "missing_kimi_api_key",
            }

        client = openai.AsyncOpenAI(
            api_key=api_key,
            base_url=settings.KIMI_BASE_URL,
            timeout=120,
        )
        system_prompt = V2_SYSTEM_PROMPT
        messages = [
            {
                "role": "user",
                "content": (
                    "INTERNAL COACH STATE PACKET (not athlete-authored; use for "
                    "reasoning only, never quote this label):\n"
                    f"{packet_to_prompt(packet)}"
                ),
            },
            {"role": "user", "content": message},
        ]
        extra_body: dict = {}
        if model_name.lower() in ("kimi-k2.5", "kimi-k2.6"):
            extra_body["thinking"] = {"type": "enabled"}

        timeout_errors = [asyncio.TimeoutError]
        api_timeout_error = getattr(openai, "APITimeoutError", None)
        if api_timeout_error is not None:
            timeout_errors.append(api_timeout_error)
        try:
            response = await client.chat.completions.create(
                model=model_name,
                messages=[{"role": "system", "content": system_prompt}] + messages,
                max_tokens=COACH_MAX_OUTPUT_TOKENS,
                extra_body=extra_body if extra_body else None,
            )
        except tuple(timeout_errors) as exc:
            latency_ms = int(
                (datetime.now(timezone.utc) - started).total_seconds() * 1000
            )
            return {
                "response": "",
                "error": True,
                "model": model_name,
                "fallback_reason": "v2_timeout",
                "error_class": exc.__class__.__name__,
                "kimi_latency_ms": latency_ms,
            }
        except Exception as exc:
            latency_ms = int(
                (datetime.now(timezone.utc) - started).total_seconds() * 1000
            )
            return {
                "response": "",
                "error": True,
                "model": model_name,
                "fallback_reason": "llm_provider_error",
                "error_class": exc.__class__.__name__,
                "kimi_latency_ms": latency_ms,
            }
        usage = getattr(response, "usage", None)
        input_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
        output_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
        choice = (response.choices or [None])[0]
        assistant_message = choice.message if choice else None
        response_text = ((getattr(assistant_message, "content", "") or "")).strip()
        response_text = _strip_emojis(response_text)
        if not response_text:
            return {
                "response": "",
                "error": True,
                "model": model_name,
                "fallback_reason": "v2_empty_response",
                "error_class": "empty_response",
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            }

        async def _retry_voice(rewrite_instruction: str) -> str:
            retry_response = await client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    *messages,
                    {"role": "user", "content": rewrite_instruction},
                ],
                max_tokens=COACH_MAX_OUTPUT_TOKENS,
                extra_body=extra_body if extra_body else None,
            )
            retry_choice = (retry_response.choices or [None])[0]
            retry_message = retry_choice.message if retry_choice else None
            return _strip_emojis(
                ((getattr(retry_message, "content", "") or "")).strip()
            )

        try:
            voice_result = await enforce_voice(response_text, _retry_voice)
            response_text = voice_result["response"]
            template_phrase_count = int(voice_result["template_phrase_count"])
            template_phrase_hits = list(voice_result["template_phrase_hits"])
        except VoiceContractViolation as exc:
            logger.warning(
                "coach_runtime_v2_voice_contract_violation",
                extra={
                    "extra_fields": {
                        "event": "coach_runtime_v2_voice_contract_violation",
                        "athlete_id": str(athlete_id),
                        "template_phrase_count": len(exc.hits),
                        "template_phrase_hits": exc.hits,
                    }
                },
            )
            return {
                "response": "",
                "error": True,
                "model": model_name,
                "fallback_reason": "v2_guardrail_failed",
                "error_class": "VoiceContractViolation",
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "template_phrase_count": len(exc.hits),
                "template_phrase_hits": exc.hits,
            }

        self.track_usage(
            athlete_id=athlete_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model=model_name,
            is_opus=True,
        )
        latency_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
        _check_response_quality(response_text, model_name, str(athlete_id))
        return {
            "response": response_text,
            "error": False,
            "model": model_name,
            "is_high_stakes": True,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "tools_called": [],
            "kimi_latency_ms": latency_ms,
            "kimi_tool_calls_count": 0,
            "template_phrase_count": template_phrase_count,
            "template_phrase_hits": template_phrase_hits,
            "thinking": extra_body.get("thinking", {}).get("type"),
        }

    async def query_gemini(
        self,
        athlete_id: UUID,
        message: str,
        athlete_state: str,
        conversation_context: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """
        Query Gemini 3 Flash for coaching queries (Mar 2026 upgrade).

        Replaces GPT-4o-mini for 95% of queries. Benefits:
        - 1M context window (no more aggressive pruning)
        - Competitive pricing ($0.30/1M input, $2.50/1M output)
        - Fast inference (254 tokens/sec)

        Uses Gemini API with function calling for tool access.
        """
        if not self.gemini_client:
            logger.error("Gemini client not initialized — coach unavailable")
            return {
                "response": "Coach is temporarily unavailable. Please try again in a moment.",
                "error": True,
            }

        # Build Gemini tools (function declarations) — FULL tool suite
        function_declarations = [
            {
                "name": "get_recent_runs",
                "description": "Fetch the athlete's recent runs including dates, distances, paces, heart rates, and workout types.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "days": {
                            "type": "integer",
                            "description": "How many days back to look (default 14, max 730)",
                        }
                    },
                },
            },
            {
                "name": "search_activities",
                "description": "Search activity history by date, name, race flag, distance, sport, or workout type. Use for older activities and athlete corrections that something exists.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "start_date": {"type": "string"},
                        "end_date": {"type": "string"},
                        "name_contains": {"type": "string"},
                        "sport": {"type": "string"},
                        "workout_type": {"type": "string"},
                        "race_only": {"type": "boolean"},
                        "distance_min_m": {"type": "integer"},
                        "distance_max_m": {"type": "integer"},
                        "limit": {"type": "integer"},
                    },
                },
            },
            {
                "name": "get_calendar_day_context",
                "description": "Get plan + actual context for a specific calendar day (planned workout + completed activities with IDs).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "day": {
                            "type": "string",
                            "description": "Calendar date in YYYY-MM-DD format.",
                        }
                    },
                    "required": ["day"],
                },
            },
            {
                "name": "get_efficiency_trend",
                "description": "Get efficiency trend data over time (pace-at-HR time series + summary). Use for 'am I getting fitter?' questions.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "days": {
                            "type": "integer",
                            "description": "How many days of history to analyze (default 30, max 365)",
                        }
                    },
                },
            },
            {
                "name": "get_plan_week",
                "description": "Get the current week's planned workouts for the athlete's active training plan.",
                "parameters": {"type": "object", "properties": {}},
            },
            {
                "name": "get_weekly_volume",
                "description": "Get weekly mileage totals for the athlete over recent weeks.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "weeks": {
                            "type": "integer",
                            "description": "Number of weeks to retrieve (default 12, max 104)",
                        }
                    },
                },
            },
            {
                "name": "get_training_load",
                "description": "Get the athlete's current training load metrics: fitness, fatigue, and form.",
                "parameters": {"type": "object", "properties": {}},
            },
            {
                "name": "get_training_paces",
                "description": "Get RPI-based training paces (easy, threshold, interval, marathon). THIS IS THE AUTHORITATIVE SOURCE for training paces.",
                "parameters": {"type": "object", "properties": {}},
            },
            {
                "name": "get_correlations",
                "description": "Get correlations between wellness inputs and efficiency outputs.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "days": {
                            "type": "integer",
                            "description": "How many days of history to analyze (default 30, max 365)",
                        }
                    },
                },
            },
            {
                "name": "get_race_predictions",
                "description": "Get RPI-based equivalent race times for 5K, 10K, Half Marathon, and Marathon, plus the athlete's actual race history. These come from verified race data, not theoretical models.",
                "parameters": {"type": "object", "properties": {}},
            },
            {
                "name": "get_race_strategy_packet",
                "description": "Build the full deterministic race strategy packet before answering race plan, pacing, or execution questions.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "race_name": {"type": "string"},
                        "race_date": {"type": "string"},
                        "race_distance": {"type": "string"},
                        "lookback_days": {"type": "integer"},
                    },
                },
            },
            {
                "name": "get_training_block_narrative",
                "description": "Summarize recent quality-session structure from activities and splits. Use for race readiness, workout arc, and evidence-vs-zone questions.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "days": {"type": "integer"},
                        "limit": {"type": "integer"},
                    },
                },
            },
            {
                "name": "get_recovery_status",
                "description": "Get recovery metrics: half-life, durability index, false fitness and masked fatigue signals.",
                "parameters": {"type": "object", "properties": {}},
            },
            {
                "name": "get_active_insights",
                "description": "Get prioritized actionable insights for the athlete.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "limit": {
                            "type": "integer",
                            "description": "Max insights to return (default 5, max 10)",
                        }
                    },
                },
            },
            {
                "name": "get_pb_patterns",
                "description": "Get training patterns that preceded personal bests, including optimal form range.",
                "parameters": {"type": "object", "properties": {}},
            },
            {
                "name": "get_efficiency_by_zone",
                "description": "Get efficiency trend for specific effort zones (easy, threshold, race).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "effort_zone": {
                            "type": "string",
                            "description": "Effort zone to analyze: easy, threshold, or race (default threshold)",
                        },
                        "days": {
                            "type": "integer",
                            "description": "Days of history (default 90, max 365)",
                        },
                    },
                },
            },
            {
                "name": "get_nutrition_correlations",
                "description": "Get correlations between pre/post-activity nutrition and performance/recovery.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "days": {
                            "type": "integer",
                            "description": "Days of history (default 90, max 365)",
                        }
                    },
                },
            },
            {
                "name": "get_nutrition_log",
                "description": "Get detailed nutrition log entries. Use when the athlete asks about their food, meals, fueling, macros, or calorie intake.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "days": {
                            "type": "integer",
                            "description": "Days of history (default 7, max 90)",
                        },
                        "entry_type": {
                            "type": "string",
                            "description": "Filter: daily, pre_activity, during_activity, post_activity",
                        },
                        "activity_id": {
                            "type": "string",
                            "description": "Filter to a specific activity UUID",
                        },
                    },
                },
            },
            {
                "name": "get_best_runs",
                "description": "Get best runs by an explicit metric (efficiency, pace, distance, intensity_score), optionally filtered to an effort zone.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "days": {
                            "type": "integer",
                            "description": "History window (default 365, max 730)",
                        },
                        "metric": {
                            "type": "string",
                            "description": "Ranking metric: efficiency, pace, distance, or intensity_score",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Max results (default 5, max 10)",
                        },
                        "effort_zone": {
                            "type": "string",
                            "description": "Optional effort zone filter: easy, threshold, or race",
                        },
                    },
                },
            },
            {
                "name": "compare_training_periods",
                "description": "Compare last N days vs the previous N days (volume/run count deltas).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "days": {
                            "type": "integer",
                            "description": "Days per period (default 28, max 180)",
                        }
                    },
                },
            },
            {
                "name": "get_coach_intent_snapshot",
                "description": "Get the athlete's current self-guided intent snapshot (goals/constraints) with staleness indicator.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "ttl_days": {
                            "type": "integer",
                            "description": "How long the snapshot is considered fresh (default 7)",
                        }
                    },
                },
            },
            {
                "name": "set_coach_intent_snapshot",
                "description": "Update the athlete's self-guided intent snapshot (athlete-led) to avoid repetitive questioning.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "training_intent": {
                            "type": "string",
                            "description": "Athlete intent: through_fatigue | build_fitness | freshen_for_event",
                        },
                        "next_event_date": {
                            "type": "string",
                            "description": "Optional YYYY-MM-DD for race/benchmark",
                        },
                        "next_event_type": {
                            "type": "string",
                            "description": "Optional: race | benchmark | other",
                        },
                        "pain_flag": {
                            "type": "string",
                            "description": "none | niggle | pain",
                        },
                        "time_available_min": {
                            "type": "integer",
                            "description": "Typical time available (minutes)",
                        },
                        "weekly_mileage_target": {
                            "type": "number",
                            "description": "Athlete-stated target miles/week",
                        },
                    },
                },
            },
            {
                "name": "get_training_prescription_window",
                "description": "Deterministically prescribe training for 1-7 days (exact distances/paces/structure).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "start_date": {
                            "type": "string",
                            "description": "Start date YYYY-MM-DD (default today)",
                        },
                        "days": {
                            "type": "integer",
                            "description": "How many days (1-7)",
                        },
                        "time_available_min": {
                            "type": "integer",
                            "description": "Optional time cap for workouts (minutes)",
                        },
                        "weekly_mileage_target": {
                            "type": "number",
                            "description": "Optional athlete target miles/week",
                        },
                        "pain_flag": {
                            "type": "string",
                            "description": "none | niggle | pain",
                        },
                    },
                },
            },
            {
                "name": "get_wellness_trends",
                "description": "Get wellness trends from daily check-ins: sleep, stress, soreness, HRV, resting HR, and mindset metrics over time.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "days": {
                            "type": "integer",
                            "description": "How many days of wellness data to analyze (default 28, max 90)",
                        }
                    },
                },
            },
            {
                "name": "get_athlete_profile",
                "description": "Get athlete physiological profile: age, RPI, runner type, threshold pace, durability, and training metrics. Training paces come from get_training_paces, not from this tool.",
                "parameters": {"type": "object", "properties": {}},
            },
            {
                "name": "get_training_load_history",
                "description": "Get daily fitness/fatigue/form history showing training load progression and injury risk over time.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "days": {
                            "type": "integer",
                            "description": "How many days of load history (default 42, max 90)",
                        }
                    },
                },
            },
            {
                "name": "compute_running_math",
                "description": "Compute pace/time/distance math deterministically.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "pace_per_mile": {"type": "string"},
                        "pace_per_km": {"type": "string"},
                        "distance_miles": {"type": "number"},
                        "distance_km": {"type": "number"},
                        "time_seconds": {"type": "integer"},
                        "operation": {"type": "string"},
                    },
                    "required": ["operation"],
                },
            },
            {
                "name": "analyze_run_streams",
                "description": "Analyze per-second stream data for a run activity. Returns segment classification, cardiac/pace drift, coachable moments, and optional plan comparison. Uses the athlete's physiological profile for N=1 individualized analysis.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "activity_id": {
                            "type": "string",
                            "description": "UUID of the activity to analyze (from get_recent_runs or get_calendar_day_context).",
                        },
                    },
                    "required": ["activity_id"],
                },
            },
            {
                "name": "get_mile_splits",
                "description": "Compute mile/km splits for a specific activity using stream data first, with device laps as fallback.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "activity_id": {
                            "type": "string",
                            "description": "UUID of the activity to split (from get_recent_runs or get_calendar_day_context).",
                        },
                        "unit": {
                            "type": "string",
                            "description": "Split unit: 'mi' (default) or 'km'.",
                        },
                    },
                    "required": ["activity_id"],
                },
            },
            {
                "name": "get_profile_edit_paths",
                "description": "Get deterministic profile navigation for editing athlete fields (birthdate, sex, display name, height, email).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "field": {
                            "type": "string",
                            "description": "Profile field name, e.g. birthdate, sex, display_name, height_cm, email.",
                        }
                    },
                },
            },
        ]

        gemini_tools = genai_types.Tool(function_declarations=function_declarations)

        # ADR-16: Build rich pre-computed athlete brief
        try:
            athlete_brief = coach_tools.build_athlete_brief(self.db, athlete_id)
        except Exception as e:
            logger.warning(f"Failed to build athlete brief for {athlete_id}: {e}")
            athlete_brief = "(Brief unavailable — call tools for data.)"

        # ADR-16: System prompt — coaching persona + brief injection
        _today = date.today()
        system_instruction = f"""You are the athlete's personal running coach. Today is {_today.isoformat()} ({_today.strftime('%A')}). You have reviewed their complete file before this conversation — it's in the ATHLETE BRIEF below.

ZERO-HALLUCINATION RULE (NON-NEGOTIABLE):
Every number, distance, pace, date, and training fact ABOUT THIS ATHLETE must come from the ATHLETE BRIEF below or from a tool result. NEVER fabricate, estimate, or guess athlete-specific training data. If the brief doesn't have it and the question needs athlete data, CALL A TOOL. If no tool has it, say "I don't have that in your history" — NEVER make it up. This athlete relies on you exclusively. A wrong number could cause injury.

GENERAL KNOWLEDGE RULE (EQUALLY NON-NEGOTIABLE):
You are an expert coach. When the athlete asks about sports science, supplement timing, warmup routines, race execution, recovery practices, or any domain where standard sports science exists, answer from your knowledge. Do not say "I can't verify" or "I don't have data on that" for questions any competent running coach could answer. Label general guidance as general, then personalize from tools if relevant athlete data exists.

TEMPORAL ACCURACY (NON-NEGOTIABLE):
Every activity has a date and a relative label like "(2 days ago)" or "(yesterday)".
- NEVER say "today's run" or "today's marathon" unless the activity date is literally today.
- ALWAYS check the relative label before referencing when something happened.
- If the marathon was "(2 days ago)", say "Sunday's marathon" or "your marathon two days ago" — NEVER "today's marathon".
- When in doubt, use the actual date. Getting the date wrong destroys trust in everything else you say.

COACHING PHILOSOPHY (from Knowledge Base — NON-NEGOTIABLE):
1. EFFORT-BASED COACHING ONLY. NEVER prescribe training by heart rate zones, HR numbers, or zone numbers. NEVER say "keep your heart rate below X" or "stay in zone 2." Coach by PACE (from RPI) and EFFORT FEEL (conversational, comfortably hard, short phrases, can't talk).
2. N=1 ONLY. NEVER apply population statistics (220-age, HR zone percentages, generic formulas). Every recommendation is grounded in THIS athlete's actual data.
3. TRAINING PACES FROM RPI ONLY. Easy pace is a CEILING (do not run faster than this). Paces come from get_training_paces, derived from actual race performances.
4. RACE PREDICTIONS ARE RPI EQUIVALENTS from actual race data, not theoretical models. Always anchor on the athlete's real race history.
5. SUPPRESSION OVER HALLUCINATION. If you can't answer confidently from data, say so.

COACHING APPROACH:
- Lead with what matters. If you see something important in the brief, bring it up — don't wait to be asked.
- Be direct and sparse. Athletes don't want essays.
- Show patterns, explain what they mean, recommend what to do about them.
- All dates in the brief and tool results include pre-computed relative times like '(2 days ago)' or '(yesterday)'. USE those labels verbatim — do NOT compute your own relative time.
- NEVER compute math yourself — use the compute_running_math tool for pace/distance/time calculations.
- Conversational A->I->A requirement (chat prose, not JSON): provide an interpretive Assessment, explain the Implication, then a concrete Action.
- Do NOT output internal labels like "fact capsule", "response contract", or schema keys.

YOU HAVE TOOLS — USE THEM WHEN RELEVANT:
- For training questions: get_weekly_volume, get_recent_runs, get_training_load, get_training_load_history, compare_training_periods
- For race strategy or race-day execution: get_race_strategy_packet, get_training_block_narrative, get_training_paces, search_activities
- For specific workouts or athlete corrections: search_activities, get_calendar_day_context, get_mile_splits, analyze_run_streams
- For performance analysis: get_best_runs, get_efficiency_trend, get_race_predictions
- For recovery/wellness: get_recovery_status, get_wellness_trends
- For athlete context: get_athlete_profile, get_coach_intent_snapshot
- Call compute_running_math for ANY pace/distance/time calculation
- NEVER say "I don't have access" — if you need data, call a tool
- But do NOT call tools for questions that don't need athlete data (general sports science, supplement timing, warmup protocols). Answer those directly from coaching knowledge.
- When the athlete corrects you or says something exists, call search_activities to verify before responding.
- If search_activities finds the likely activity but not the rep/split proof for a structured workout, call analyze_run_streams or get_mile_splits before saying you cannot verify the athlete's workout claim.

TOOL OUTPUTS: Each tool returns a "narrative" field — a pre-interpreted summary. Coach from the narrative, not the raw JSON.

COMMUNICATION STYLE:
- Use plain English. No acronyms (say "fitness level" not "CTL", "fatigue" not "ATL", "form" not "TSB").
- Never say "RPI" — always say "RPI" (Running Performance Index).
- If you make an error, correct it briefly and move on. No groveling. Just "You're right" and the correct answer.
- Concise. Answer the question, give the evidence, recommend the action.
- Use the athlete's preferred units (check the brief).
- If the athlete is venting, empathize briefly, then offer data-backed perspective.
- Never recommend medical advice — refer to healthcare professionals.

DATA-VERIFICATION DISCIPLINE (NON-NEGOTIABLE):
When citing specific paces, splits, distances, or comparing one workout to another, you MUST call a tool to get the actual data first. NEVER infer performance from a workout title, name, or summary. NEVER say "that's faster than today" or "your intervals were quicker than last week" without calling get_recent_runs or get_mile_splits to verify the actual numbers. If you haven't looked up the specific data, say "let me check" and call the tool. Do not guess. A wrong pace comparison destroys more trust than saying "I need to look that up." When an athlete names a structured workout and the first activity lookup finds the likely run without rep-level confirmation, escalate to analyze_run_streams or get_mile_splits before saying the claim is unverified.

ATHLETE-CALIBRATED COACHING TONE:
The ATHLETE BRIEF contains an "Athlete Experience Calibration" section. Use it:
- Experienced athletes (advanced/elite, extensive race history, confirmed patterns, high peak volume): coach as a peer. Acknowledge their training intent. Do NOT default to caution, recovery warnings, or load reduction unless the data shows a genuine problem they haven't noticed. Respect deliberate overreach during build phases. Do not tell a BQ runner to "be cautious about tomorrow's intervals" or that a distance they've done many times is "a big ask."
- Intermediate athletes: balanced tone. Flag concerns but trust their judgment on familiar efforts.
- Beginners or returning-from-break: more conservative guidance. Check pain signals. Cap ramp rates.
An experienced athlete should NEVER have to push back on overprotective coaching. Match their level.

FATIGUE THRESHOLD CONTEXT AWARENESS:
Confirmed fatigue thresholds (e.g., "sleep cliff at 6.2 hours") are real data, but WHEN you cite them matters:
- During a deliberate build or overreach approaching a race: do NOT cite thresholds as warnings. Acknowledge the load, note the data, trust the athlete's intent.
- During maintenance, recovery, or unexplained performance decline: cite thresholds actively.
- When the athlete asks about fatigue: always share the data regardless of phase.

RESPONSE LENGTH:
- Match your response length to the question complexity.
- Yes/no question → 2-4 sentences.
- "Tell me about X" → 1-2 short paragraphs.
- "Analyze my last month" → detailed but still under 200 words.
- NEVER write more than the question warrants. If the athlete wants more, they'll ask.

FORMAT:
- This is a conversation, not a document.
- NEVER use markdown tables in chat responses.
- NEVER use markdown headers (##, ###, **Section Name**).
- NEVER use emojis.
- Write in natural sentences and short paragraphs, the way a coach talks.

BAN CANNED OPENERS:
- Do NOT start with filler or preamble.
- Start with substance from the athlete's data and question.
- NEVER open with any of these phrases:
  - "Here's what the data actually shows"
  - "Here's what the data shows"
  - "Based on the data"
  - "Let me break this down"
  - "Great question"
  - "That's a great question"
  - "I'd be happy to"

VOICE DIRECTIVE (NON-NEGOTIABLE):
- Lead with your position. State the recommendation first, then the reasoning.
- Do not wrap recommendations in hedge phrases like "still aggressive", "it's worth noting", "that said", "it's possible that", "I would suggest considering", "I want to be careful", or "proceed with caution".
- Genuine uncertainty is allowed when direct: "Your threshold model says 6:31, but your recent 400s suggest faster — I would reason from what you actually ran."
- If the athlete has made a decision, help execute that decision. Risk context is one sentence max, then execution guidance.

RACE DAY EXECUTION MODE:
- Race day is execution mode, not planning mode.
- If the athlete has a race today, this morning, tonight, or within the next 12 hours, give a timeline, warmup prescription, supplement/fueling timing if relevant, mile-by-mile effort cues, and one mental cue.
- Use these literal plain-text labels so the answer is complete on the first pass: "Timeline:", "Warmup:", "Mile by mile:", and "Cue:". Do not bold them.
- Do not relitigate whether the athlete should race or whether the goal is wise unless there is an acute safety issue.

TRAINING BLOCK SYNTHESIS:
- For race readiness, target-pace, or zone-vs-workout questions, use get_training_block_narrative or race-packet workout evidence before judging fitness.
- Read the arc, not isolated workouts: what energy systems were trained, what sequence they appeared in, what is present, what is missing, and how recent the sharpest work is.

ZONE / WORKOUT EVIDENCE DISCREPANCY:
- RPI-derived paces are useful, but tool outputs require judgment. If recent race or interval evidence materially contradicts the pace model, acknowledge the discrepancy and reason from what the athlete actually ran.

ANTI-LEAKAGE RULES (NON-NEGOTIABLE):
- NEVER mention internal architecture or implementation language.
- Forbidden terms in athlete-facing responses: "database", "data model", "schema", "table", "row", "pipeline", "prompt", "system prompt", "tool call", "model routing", "token", "inference".
- NEVER say "since you built the platform" or similar internal context.
- If the athlete asks where to edit profile fields, call get_profile_edit_paths and answer with route + section + field only.

APOLOGY STYLE CONTRACT:
- If you made a mistake: acknowledge briefly ("You're right"), give the corrected answer, move on.
- No long apologies, no self-referential process explanations, no psychologizing.

PERSONAL FINGERPRINT:
- The ATHLETE BRIEF may contain a "Personal Fingerprint" section with confirmed patterns.
- These patterns have been individually validated for THIS athlete — they are not population statistics.
- When relevant, reference confirmed patterns by evidence count.
- Use threshold values for specific recommendations (e.g., "your data shows a sleep cliff at 6.2 hours").
- Use asymmetry data to convey magnitude (e.g., "bad sleep hurts you 3x more than good sleep helps").
- Use decay timing for forward-looking advice (e.g., "the effect typically peaks after 2 days for you").
- NEVER reference a pattern without its confirmation count. This is how the athlete trusts the system.
- If no fingerprint data exists, coach from the other brief sections normally.

EMERGING PATTERNS:
- If the brief contains a section starting with "=== EMERGING PATTERN — ASK ABOUT THIS FIRST ===", you MUST ask that question before discussing any other data. The question is pre-written — use it verbatim or adapt it naturally, but ask it.
- Do NOT skip the emerging question to jump into discussing active patterns. The athlete's answer determines whether this pattern matters.
- If the athlete confirms, great. If they dismiss it, move on. Do not push.
- Findings labeled [RESOLVING] represent improvements. Attribute progress to the athlete's work.

WEEK BOUNDARY AWARENESS:
- Current week data is PARTIAL — the brief marks it clearly. Do NOT treat partial week totals as complete weeks.
- "Last week" = the most recent COMPLETED week, not the in-progress week.

ATHLETE BRIEF:
{athlete_brief}"""

        # Inject athlete-stated facts from coach memory layer 1
        try:
            _facts = self._get_fresh_athlete_facts(athlete_id=athlete_id, max_facts=15)
            if _facts:
                system_instruction += self._format_known_athlete_facts(_facts)
        except Exception:
            pass

        # Build conversation contents (last 5 exchanges = 10 messages)
        contents = []
        if conversation_context:
            for msg in conversation_context[-10:]:
                role = "user" if msg.get("role") == "user" else "model"
                contents.append(
                    genai_types.Content(
                        role=role, parts=[genai_types.Part(text=msg.get("content", ""))]
                    )
                )

        # Add current message
        contents.append(
            genai_types.Content(role="user", parts=[genai_types.Part(text=message)])
        )

        try:
            total_input_tokens = 0
            total_output_tokens = 0
            tools_called: List[str] = []

            # Temperature 0.2: Gemini docs recommend low temperature for
            # "more deterministic and reliable function calls". 0.7 caused
            # hallucination of training data (fabricated distances/volumes).
            config = genai_types.GenerateContentConfig(
                system_instruction=system_instruction,
                tools=[gemini_tools],
                max_output_tokens=COACH_MAX_OUTPUT_TOKENS,
                temperature=0.2,
            )

            # Send message with tools
            response = self.gemini_client.models.generate_content(
                model=self.MODEL_DEFAULT,
                contents=contents,
                config=config,
            )

            # Track usage
            if hasattr(response, "usage_metadata"):
                total_input_tokens += getattr(
                    response.usage_metadata, "prompt_token_count", 0
                )
                total_output_tokens += getattr(
                    response.usage_metadata, "candidates_token_count", 0
                )

            # Handle function calls in a loop (max 5 iterations)
            for _ in range(5):
                # Check if there are function calls to process
                function_calls = []
                if (
                    response.candidates
                    and response.candidates[0].content
                    and response.candidates[0].content.parts
                ):
                    for part in response.candidates[0].content.parts:
                        if hasattr(part, "function_call") and part.function_call:
                            function_calls.append(part.function_call)

                if not function_calls:
                    break

                # Append model turn to contents — strip thought parts to avoid
                # thought_signature INVALID_ARGUMENT on round-trip (google-genai <1.66.0
                # base64 encoding bug; defensive strip ensures correctness regardless).
                model_content = response.candidates[0].content
                safe_parts = [
                    p
                    for p in (model_content.parts or [])
                    if hasattr(p, "function_call") and p.function_call
                ]
                if safe_parts:
                    contents.append(genai_types.Content(role="model", parts=safe_parts))
                else:
                    contents.append(model_content)

                function_response_parts = []
                for fc in function_calls:
                    tool_name = fc.name
                    tool_args = dict(fc.args) if fc.args else {}
                    tools_called.append(tool_name)

                    logger.info(f"Gemini calling tool: {tool_name} with {tool_args}")
                    result = self._execute_opus_tool(athlete_id, tool_name, tool_args)

                    function_response_parts.append(
                        genai_types.Part(
                            function_response=genai_types.FunctionResponse(
                                name=tool_name, response={"result": result}
                            )
                        )
                    )

                # Add function results to contents
                contents.append(
                    genai_types.Content(role="user", parts=function_response_parts)
                )

                # Send function results back
                response = self.gemini_client.models.generate_content(
                    model=self.MODEL_DEFAULT,
                    contents=contents,
                    config=config,
                )

                if hasattr(response, "usage_metadata"):
                    total_input_tokens += getattr(
                        response.usage_metadata, "prompt_token_count", 0
                    )
                    total_output_tokens += getattr(
                        response.usage_metadata, "candidates_token_count", 0
                    )

            # Extract final response text
            response_text = ""
            for part in response.candidates[0].content.parts:
                if hasattr(part, "text") and part.text:
                    response_text += part.text
            response_text = _strip_emojis(response_text)

            # Post-response validation: data questions must have used tools
            is_valid, reason = self._validate_tool_usage(
                message, tools_called, len(tools_called)
            )
            if not is_valid:
                logger.warning(
                    "Gemini response failed tool validation (%s) for athlete %s: "
                    "tools_called=%s, message='%.80s'",
                    reason,
                    athlete_id,
                    tools_called,
                    message,
                )

            # Track usage with Gemini pricing
            self.track_usage(
                athlete_id=athlete_id,
                input_tokens=total_input_tokens,
                output_tokens=total_output_tokens,
                model=self.MODEL_DEFAULT,
                is_opus=False,
            )

            logger.info(
                f"Gemini query completed: athlete={athlete_id}, "
                f"tools_called={tools_called}, "
                f"input_tokens={total_input_tokens}, output_tokens={total_output_tokens}"
            )
            _check_response_quality(response_text, self.MODEL_DEFAULT, str(athlete_id))
            return {
                "response": response_text,
                "error": False,
                "model": self.MODEL_DEFAULT,
                "is_high_stakes": False,
                "input_tokens": total_input_tokens,
                "output_tokens": total_output_tokens,
                "tools_called": tools_called,
            }

        except Exception as e:
            logger.error(f"Gemini query failed for {athlete_id}: {e}")
            return {
                "response": "Coach is temporarily unavailable. Please try again in a moment.",
                "error": True,
                "error_detail": str(e),
            }
