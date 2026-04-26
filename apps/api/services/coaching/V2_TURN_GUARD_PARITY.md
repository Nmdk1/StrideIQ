# V2 Turn Guard Parity

Status: SA4 parity audit, 2026-04-26.

Scope: `GuardrailsMixin._finalize_response_with_turn_guard` in
`apps/api/services/coaching/_guardrails.py`. V2 may not call a second LLM on the
same turn, so retry rows are either skipped with reason or V2 falls back to V1.
Audit source: direct helper calls from the V1 finalize path are
`_normalize_response_for_ui`, `_strip_emojis`, `_infer_intent_band`,
`_response_addresses_latest_turn`, `validate_conversation_contract_response`,
`_record_turn_guard_event`, `enforce_conversation_contract_output`,
`_build_turn_relevance_fallback`, `build_conversation_contract_retry_instruction`,
`query_opus`, and `query_gemini`. `_check_kb_violations` and
`_check_response_quality` are not called by the V1 finalize path.

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
| Retry instruction builder | V1 calls `build_conversation_contract_retry_instruction` for contract failures before the second LLM call. | Intentionally absent because V2 has no same-turn retry. | skip-with-reason: the retry instruction exists only to shape the forbidden second LLM call; V2 demotes to V1 fallback instead. |
| Deterministic profile fallback | V1 avoids retry for profile edits and returns route guidance. | Not directly run in V2. | route-through-guard: V2 failure demotes to V1; V1 fallback path retains deterministic profile handling. |
| Profile path lookup helper | V1 profile fallback calls `coach_tools.get_profile_edit_paths` through `_build_turn_relevance_fallback`. | Not directly run in V2. | route-through-guard: V2 does not synthesize fallback prose; it demotes to V1, where the same helper remains responsible for route guidance. |
| Generic turn-relevance fallback | V1 returns a direct "repeat your last question" fallback when retry still fails. | Not directly run in V2. | route-through-guard: V2 failure demotes to V1; V1 fallback path remains responsible for final visible answer. |
| Template phrase blocklist | Not part of V1 turn guard; Artifact 9 V2-specific voice enforcement. | Covered in `voice_enforcement.py` and `_llm.py`. | port already complete: V2 voice enforcement remains the template-phrase safety layer. |
| KB violation scanner | `_check_kb_violations` is not invoked by `GuardrailsMixin._finalize_response_with_turn_guard`; it was stale import debt in this module. | Not part of V2 turn-guard helper. | skip-with-reason: not a V1 finalize check. V2's Artifact 9 safety for this layer is packet truth anchoring, unknown suppression, no-tools packet responses, voice blocklist enforcement, and existing non-turn-guard coach quality tests. |
| Response quality scanner | `_check_response_quality` is not invoked by `GuardrailsMixin._finalize_response_with_turn_guard`; it was stale import debt in this module. | Not part of V2 turn-guard helper. | skip-with-reason: not a V1 finalize check. V2 response quality remains enforced by the packet contract, Artifact 7 replay cases, and template-phrase blocklist, not by this V1 finalize helper. |
