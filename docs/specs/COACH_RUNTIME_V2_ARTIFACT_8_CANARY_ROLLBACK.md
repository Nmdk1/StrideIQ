# Coach Runtime V2 Artifact 8: Canary, Rollback, And Observability

Status: Artifact 8 locked.
Created: 2026-04-26.
Locked: 2026-04-26.

This artifact defines how Coach Runtime V2 may be introduced to production
without putting real athlete trust behind an unobserved rewrite. It is grounded
in the current StrideIQ production substrate:

- Single Hostinger KVM 8 host at `187.124.67.153`.
- Production repo path `/opt/strideiq/repo`.
- Single-node `docker-compose.prod.yml` stack.
- DB-backed feature flags through `FeatureFlagService`.
- Existing Sentry, JSON logs, health endpoints, `CoachUsage`, and `CoachChat`.
- No Prometheus/OpenTelemetry scrape pipeline in the repo today.

Artifact 8 does not authorize implementation by itself. It is the deployment
and rollback contract that V2 implementation must satisfy.

## 1. Production Substrate Facts

Production runs on one Compose stack:

- `strideiq_caddy`
- `strideiq_postgres`
- `strideiq_redis`
- `strideiq_minio`
- `strideiq_api`
- `strideiq_worker`
- `strideiq_worker_default`
- `strideiq_beat`
- `strideiq_web`

Deployment is manual from the droplet:

```bash
cd /opt/strideiq/repo && git pull origin main && docker compose -f docker-compose.prod.yml up -d --build --remove-orphans && docker compose -f docker-compose.prod.yml ps
```

API deploys run `python run_migrations.py` before Uvicorn starts. Production
has four Uvicorn workers. API health is available through:

- `/ping`: liveness only, no DB.
- `/health`: DB and Redis readiness.
- `/health/detailed`: DB and Redis detail for operator checks.

There is no automated blue/green deploy, no second production node, and no
Prometheus/OpenTelemetry metrics pipeline today. Rollback must therefore be
flag-first and operator-readable.

## 2. Feature Flag Contract

V2 must be controlled by DB-backed feature flags, not by a hardcoded env-only
switch.

Required flags:

```text
coach.runtime_v2.shadow
coach.runtime_v2.visible
```

`coach.runtime_v2.shadow` means V2 packet assembly and deterministic checks may
run, but the athlete receives the V1 answer.

`coach.runtime_v2.visible` means the athlete may receive the V2 answer.

Both flags must default to:

```json
{
  "enabled": false,
  "rollout_percentage": 0,
  "allowed_athlete_ids": []
}
```

The `feature_flag.rollout_percentage` database column defaults to `100` for
general-purpose flags. V2 flag seed migrations must therefore set
`rollout_percentage = 0` explicitly for both required rows. Do not rely on the
table default. A V2 flag row with `enabled = true` and an omitted rollout value
would otherwise route 100% of eligible traffic.

The flags may use `allowed_athlete_ids` for founder and pilot canaries. Do not
use `rollout_percentage` for V2 visible rollout until founder canary and pilot
allowlist gates are green.

### Fail-Closed Requirement

The generic `core.feature_flags.is_feature_enabled()` helper currently fails
open on exceptions. V2 runtime routing must not use that helper.

V2 must use a coach-specific fail-closed helper:

```text
is_coach_runtime_v2_enabled(flag_key, athlete_id, db) -> bool
```

Rules:

- Missing flag returns `False`.
- Database or flag-service exception returns `False`.
- Invalid athlete id returns `False`.
- The helper must not delegate to `core.feature_flags.is_feature_enabled()`.
- `allowed_athlete_ids` takes precedence over percentage rollout.
- Every decision logs the flag key, athlete id hash, and result.

## 3. Runtime Modes

V2 runtime mode is determined per request:

```text
off -> shadow -> visible -> fallback
```

### `off`

Default. V1 coach path handles the request. No V2 packet assembly runs.

### `shadow`

V1 handles the visible answer. V2 may assemble the packet and run deterministic
checks for observability, but no hidden second coach-response LLM call is
allowed during live traffic.

Reason: V2's core contract says the coach-response call is the only same-turn
LLM call. Running a hidden V2 LLM next to the V1 LLM doubles cost and creates an
unreviewed production output path. Hidden response comparison belongs in offline
replay, not live shadow traffic.

Allowed in shadow:

- packet assembly
- mode classification
- permission filtering
- cross-domain coupling computation
- deterministic invariant checks
- structured logging

Disallowed in shadow:

- hidden V2 coach-response LLM call
- persisted V2 assistant response shown as if it were a normal coach answer
- any mutation based on V2 output

### `visible`

V2 produces the athlete-visible answer. V1 remains available as warm fallback if
V2 cannot produce a safe answer.

### `fallback`

Fallback means the request was eligible for V2, but V1 answered instead.
Fallback is allowed for system safety, not for silent quality masking.

Allowed fallback reasons:

- `flag_disabled`
- `packet_assembly_error`
- `packet_invariant_failed`
- `mode_classifier_error`
- `permission_filter_error`
- `v2_timeout`
- `v2_empty_response`
- `v2_guardrail_failed`
- `llm_provider_error`
- `consent_disabled`
- `no_llm_configured`
- `deterministic_short_circuit`
- `budget_exceeded`

The last four reasons cover requests that are visible-eligible by flag but exit
through an existing V1/system path before any V2 packet or coach-response call
can run. They must not be recorded as `visible` / `v2` served turns.

Fallback must be recorded in logs and `CoachChat` metadata.

## 4. V1 Fallback Contract

V1 remains the fallback path through all V2.0-a rollout stages.

Fallback rules:

- At most one V2 attempt per request.
- At most one V1 fallback per request.
- No V2 retry loops.
- No prompt-patch fallback.
- No response blending between V1 and V2.
- If V2 fails before LLM generation, route to V1.
- If V2 produces an unsafe or empty answer, discard it and route to V1.
- The athlete should not see raw fallback internals.

Fallback metadata must record enough for later audit.

## 5. Observability Contract

V2 observability must use surfaces that exist today:

- JSON application logs from `core/logging.py`.
- Sentry from `main.py`.
- `CoachChat.messages` JSONB.
- `CoachUsage` for request/token/cost counters.
- Existing API response metadata fields, where appropriate.
- `/health`, `/health/detailed`, and Docker health checks.

### Required Structured Log Event

Each V2-eligible request must emit a structured log event:

```json
{
  "event": "coach_runtime_v2_request",
  "athlete_id_hash": "<hash>",
  "thread_id": "<coach_chat_id_or_null>",
  "runtime_mode": "off | shadow | visible | fallback",
  "runtime_version": "v1 | v2",
  "flag_shadow": true,
  "flag_visible": false,
  "artifact_packet_schema_version": "coach_runtime_v2.packet.v1",
  "artifact_mode": "<Artifact 5 mode>",
  "artifact5_mode_confidence": 0.0,
  "packet_estimated_tokens": 0,
  "packet_block_count": 0,
  "omitted_block_count": 0,
  "unknown_count": 0,
  "permission_redaction_count": 0,
  "coupling_count": 0,
  "multimodal_attachment_count": 0,
  "deterministic_check_status": "pass | fail | skipped",
  "fallback_reason": null,
  "llm_model": "kimi-k2.6",
  "latency_ms_total": 0,
  "latency_ms_packet": 0,
  "latency_ms_llm": 0,
  "tool_count": 0,
  "error_class": null
}
```

The event must avoid raw athlete text, raw medical/lab values, and full athlete
ids.

### Required CoachChat Metadata

Assistant messages saved to `CoachChat.messages` must include:

```json
{
  "runtime_version": "v1 | v2",
  "runtime_mode": "off | shadow | visible | fallback",
  "packet_schema_version": "coach_runtime_v2.packet.v1",
  "artifact5_mode": "<mode>",
  "fallback_reason": null,
  "model": "kimi-k2.6",
  "tools_used": [],
  "tool_count": 0
}
```

For V1 responses, existing metadata remains valid, but `runtime_version` and
`runtime_mode` should be added once V2 routing lands.

### API Response Metadata

The `/v1/coach/chat` and `/v1/coach/chat/stream` response metadata may include
minimal runtime metadata for trust/debugging:

```json
{
  "runtime_version": "v1 | v2",
  "runtime_mode": "off | shadow | visible | fallback"
}
```

Do not expose packet internals, redaction counts, permission details, or
sensitive mode/coupling details to the athlete by default.

## 6. Pre-Deploy Gates

No V2 runtime code may be deployed with `coach.runtime_v2.visible` enabled until
all of these pass:

1. CI green on the target commit.
2. Existing Phase 8 eval tests green.
3. Artifact 7 replay tests green.
4. V2 packet schema tests green.
5. V2 mode classifier tests green.
6. V2 permission filtering tests green.
7. V2 fallback tests green.
8. V2 flag fail-closed tests green.
9. Wiki updated for any shipped behavior.
10. `coach.runtime_v2.shadow` and `coach.runtime_v2.visible` default disabled.

Visible V2 must also pass:

1. No fatal replay failures.
2. No major replay failures unless founder explicitly waives the case.
3. Tier 3 `voice_alignment >= 3.0` on every `artifact7.v1` replay case.
4. Tier 3 average `>= 4.0`.
5. Founder approval for the initial visible allowlist.

## 7. Rollout Stages

### Stage 0: Local And CI Only

- Flags absent or disabled.
- V2 code may run in tests only.
- No production request touches V2 packet assembly.

Exit criteria:

- Focused V2 unit tests green.
- Replay deterministic tests green.
- No change to athlete-visible coach behavior.

### Stage 1: Production Deployed, Flags Off

- V2 code is deployed.
- Both flags disabled.
- V1 handles all coach traffic.

Operator checks:

```bash
curl -s https://strideiq.run/ping
curl -s https://strideiq.run/health
docker compose -f docker-compose.prod.yml logs --tail 50 api
```

Exit criteria:

- API health not worse than pre-deploy.
- No new Sentry error class from import/startup.
- Coach V1 still answers founder smoke test.

### Stage 2: Founder Shadow

- Enable `coach.runtime_v2.shadow` for founder only.
- Keep `coach.runtime_v2.visible` disabled.
- V1 remains visible.

Exit criteria:

- At least 20 founder coach turns with successful packet assembly.
- `packet_invariant_failed` rate is 0 for founder turns.
- No permission redaction leak.
- No Sentry errors from V2 assembly.
- Fallback remains irrelevant because visible V1 answers.

### Stage 3: Founder Visible

- Enable `coach.runtime_v2.visible` for founder only.
- Keep `rollout_percentage = 0`.

Exit criteria:

- At least 30 founder visible V2 turns.
- No P0/P1 trust failures.
- No fatal Artifact 7 failure mode observed manually.
- Fallback rate below 10%.
- No repeated timeout pattern.
- Founder explicitly approves continuing.

### Stage 4: Pilot Allowlist

- Add a small explicit athlete allowlist.
- No percentage rollout.

Exit criteria:

- At least 100 pilot visible V2 turns.
- Fallback rate below 5% as the initial threshold.
- No Sentry error spike attributable to V2.
- No sensitive-context leak.
- No athlete-specific hallucination confirmed from audit.
- Replay suite remains green on the deployed commit.

The 5% fallback threshold is provisional. It must be revisited after Stage 3
founder visible data, using observed provider stability and packet assembly
failure rates. Tightening or loosening it requires founder approval and a spec
update.

### Stage 5: Percentage Rollout

Percentage rollout is not part of V2.0-a by default. It requires a separate
founder decision after pilot allowlist success.

If approved:

- Start at 5%.
- Hold at least 48 hours.
- Increase only after review of logs, Sentry, fallback rate, and replay suite.

## 8. Rollback Triggers

Any of these require immediate rollback to V1:

- Confirmed athlete-specific hallucination in V2.
- Confirmed sensitive-context leak.
- Medical certainty or unsafe injury advice.
- Wrong race/date/timeline in a high-stakes response.
- V2 answer contradicts same-turn athlete correction.
- V2 timeout or provider failure pattern affecting multiple requests.
- Fallback rate above stage threshold.
- Sentry error spike attributable to V2.
- API health degraded after V2 deploy.
- Founder says rollback.

Rollback bias: if unsure, turn V2 off first, investigate second.

## 9. Rollback Mechanics

### First-Line Rollback: Disable Flags

Use admin feature flag UI/API if available:

```text
PATCH /v1/admin/feature-flags/coach.runtime_v2.visible
PATCH /v1/admin/feature-flags/coach.runtime_v2.shadow
```

Set:

```json
{
  "enabled": false,
  "rollout_percentage": 0,
  "allowed_athlete_ids": []
}
```

If the admin surface is unavailable, use the database directly from the
production host:

```bash
cd /opt/strideiq/repo
docker compose -f docker-compose.prod.yml exec postgres psql -U ${POSTGRES_USER:-postgres} -d ${POSTGRES_DB:-running_app} -c "UPDATE feature_flag SET enabled=false, rollout_percentage=0, allowed_athlete_ids='[]'::jsonb, updated_at=now() WHERE key IN ('coach.runtime_v2.shadow','coach.runtime_v2.visible');"
```

For V2 helper semantics, `allowed_athlete_ids = NULL` and `allowed_athlete_ids =
[]` are both treated as no allowlist. Rollback writes `[]` so audits can
distinguish an intentional cleared allowlist from an older nullable row.

Then verify V1 is serving:

```bash
docker compose -f docker-compose.prod.yml logs --tail 100 api
curl -s https://strideiq.run/health
```

### Second-Line Rollback: Code Revert

Use code rollback only if flags-off does not restore safe behavior, or if V2
introduced startup/runtime failures outside the flag path.

Pattern:

```bash
cd /opt/strideiq/repo
git revert <bad_commit_sha>
docker compose -f docker-compose.prod.yml up -d --build --remove-orphans
docker compose -f docker-compose.prod.yml ps
```

If Docker cache appears stale:

```bash
docker compose -f docker-compose.prod.yml build --no-cache api
docker compose -f docker-compose.prod.yml up -d --remove-orphans
```

Do not use `docker restart` as deploy rollback. It restarts the old image.

## 10. Migration And Data Safety

V2.0-a migrations must be additive and nullable.

Allowed:

- new feature flag rows
- new nullable metadata fields
- new append-only audit tables
- new indexes that do not block production writes

Disallowed before stable canary:

- destructive migrations
- required columns on hot coach tables without backfill
- deleting or rewriting `CoachChat.messages`
- changing V1 response storage shape in a way old code cannot read

Any V2 metadata stored in `CoachChat.messages` must be ignored safely by V1.

## 11. Smoke Checks

Before deploy:

```bash
gh run list --limit 5
gh run view <run_id>
```

After deploy with flags off:

```bash
curl -s https://strideiq.run/ping
curl -s https://strideiq.run/health
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs --tail 50 api
```

Founder authenticated smoke:

```bash
TOKEN=$(docker exec strideiq_api python -c "from core.security import create_access_token;from core.database import SessionLocal;from models import Athlete;db=SessionLocal();u=db.query(Athlete).filter(Athlete.email=='mbshaf@gmail.com').first();print(create_access_token(data={'sub':str(u.id),'email':u.email,'role':u.role}));db.close()")
curl -s -H "Authorization: Bearer $TOKEN" https://strideiq.run/v1/coach/chat -H "Content-Type: application/json" -d '{"message":"quick check: what did you look at?","include_context":true}'
```

After shadow/visible changes:

- Confirm flag state.
- Run founder coach turn.
- Check API logs for `coach_runtime_v2_request`.
- Confirm `runtime_mode` matches expected mode.
- Confirm `fallback_reason` is null for successful V2 visible turns.
- Check Sentry for new V2 error class.

## 12. Required Implementation Tests

Artifact 8 implementation must include tests for:

1. V2 flags default disabled.
2. V2 seed migration creates both required flags with `enabled=false`,
   `rollout_percentage=0`, and `allowed_athlete_ids=[]`.
3. Missing V2 flags return disabled.
4. Flag service exception returns disabled.
5. V2 helper does not delegate to `core.feature_flags.is_feature_enabled()`.
6. Founder allowlist enables shadow without visible.
7. Visible flag disabled forces V1 even if shadow enabled.
8. Visible flag enabled routes eligible request to V2.
9. V2 packet assembly failure falls back to V1 once.
10. V2 timeout falls back to V1 once.
11. V2 guardrail failure falls back to V1 once.
12. Fallback metadata persists to `CoachChat.messages`.
13. Successful V2 metadata persists to `CoachChat.messages`.
14. Shadow mode does not call coach-response LLM twice.
15. API and stream responses include minimal runtime metadata.
16. Runtime metadata is internally consistent: `fallback` mode records V1 as
   the served runtime, and `visible` mode records V2 as the served runtime.
17. Structured log event redacts raw athlete text.
18. Existing V1 coach tests remain green with flags off.

## 13. Cutover Rule

V2 is not the default coach until all of these are true:

- Artifact 8 is locked.
- V2.0-a implementation gates are green.
- Founder visible canary is approved.
- Pilot allowlist is approved.
- Replay suite is materially better than V1 on the locked case bank.
- Rollback has been exercised at least once in production or staging-equivalent
  production commands.

Until then, V1 remains the default production runtime.
