# V2 Turn Guard Parity

Status: SA4 parity audit, 2026-04-26.

Scope: `GuardrailsMixin._finalize_response_with_turn_guard` in
`apps/api/services/coaching/_guardrails.py`. V2 may not call a second LLM on the
same turn, so retry rows are either skipped with reason or V2 falls back to V1.

| Check | V1 behavior | V2 current state before SA4 | Decision |
|------|------------|------------------------------|----------|
| UI normalization | Runs `_normalize_response_for_ui` to rewrite internal labels, evidence headings, UUID leakage in main prose, and fragile punctuation. | Partially covered in `core.py` visible-success branch. | route-through-guard: `_finalize_v2_response_with_turn_guard` now runs the same deterministic normalization before V2 can serve. |
| Emoji stripping | Runs `_strip_emojis` after normalization. | Covered in `core.py` visible-success branch. | route-through-guard: same deterministic strip now happens inside the V2 guard helper. |
| Intent-band inference | Infers user and assistant bands for telemetry and compatibility decisions. | Partially covered only for pass telemetry. | route-through-guard: V2 helper uses `_infer_intent_band` for the same pass/fail decision. |
| Profile-edit routing check | Profile edit questions must produce settings/profile navigation, not coaching analysis. | Not covered for V2. | route-through-guard: V2 helper uses `_response_addresses_latest_turn`; failure demotes visible V2 to V1 fallback with `v2_guardrail_failed`. |
| Correction/apology compatibility | Correction/apology turns must not drift into unrelated workout analysis. | Not covered for V2. | route-through-guard: V2 helper uses `_response_addresses_latest_turn`; failure demotes visible V2 to V1 fallback with `v2_guardrail_failed`. |
| General latest-turn compatibility | Assistant intent band must be compatible with latest user intent band. | Not covered for V2. | route-through-guard: V2 helper uses `_response_addresses_latest_turn`; failure demotes visible V2 to V1 fallback with `v2_guardrail_failed`. |
| Conversation contract validation | Runs `validate_conversation_contract_response` for race day, race strategy, correction, and other contract shapes. | Contract is injected into packet, but not measured before serving V2. | route-through-guard: V2 helper validates the same contract and demotes visible V2 to V1 fallback on mismatch. |
| Conversation contract output enforcement | Runs `enforce_conversation_contract_output` before returning a passing response. | Not covered for V2. | route-through-guard: V2 helper applies the same deterministic output enforcement on passing V2 responses. |
| Turn-guard event logging | Records pass, mismatch, contract mismatch, retry, and fallback events. | V2 recorded only `pass_v2_packet` on success. | port: V2 helper records `pass_v2_packet` on pass and `v2_guardrail_failed:<reason>` on fail. |
| LLM retry on mismatch | V1 performs one retry through Opus/Gemini when latest-turn or contract checks fail. | Intentionally absent. | skip-with-reason: Artifact 9 says only the coach-response call has LLM access; V2 cannot add same-turn retry calls. Failure routes to V1 instead. |
| Deterministic profile fallback | V1 avoids retry for profile edits and returns route guidance. | Not directly run in V2. | route-through-guard: V2 failure demotes to V1; V1 fallback path retains deterministic profile handling. |
| Generic turn-relevance fallback | V1 returns a direct "repeat your last question" fallback when retry still fails. | Not directly run in V2. | route-through-guard: V2 failure demotes to V1; V1 fallback path remains responsible for final visible answer. |
| Template phrase blocklist | Not part of V1 turn guard; Artifact 9 V2-specific voice enforcement. | Covered in `voice_enforcement.py` and `_llm.py`. | port already complete: V2 voice enforcement remains the template-phrase safety layer. |
