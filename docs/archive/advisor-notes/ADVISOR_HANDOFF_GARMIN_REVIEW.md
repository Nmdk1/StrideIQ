# Advisor Handoff — Garmin Integration Review

**Created:** February 16, 2026
**Last updated:** February 22, 2026 — Portal verification complete, AC revised, advisor GO on revision, builder handoff sent
**Purpose:** Persistent contract for any advisor session touching Garmin integration work.

---

## Advisor-to-Advisor Note (Strict Review Mode, No Coding)

**Operating mode:** advisory/review only.
**Do not implement code. Do not propose coding until discovery + AC are approved.**

### Current state
- Founder wants Garmin as strategic primary source long-term.
- Current immediate flow is **discovery first**, then review, then AC spec, then build.
- Builder note source: `docs/SESSION_HANDOFF_2026-02-19_GARMIN_BUILDER_NOTE.md`.
- Existing Garmin files are present but include legacy/unofficial patterns:
  - `apps/api/routers/garmin.py`
  - `apps/api/services/garmin_service.py`
  - `apps/api/tasks/garmin_tasks.py`
  - `apps/api/services/provider_import/garmin_di_connect.py`

### Verified repo constraints (important)
- CI workflow triggers on **`main` and `develop`** (`.github/workflows/ci.yml`).
- Branch isolation is required for Garmin implementation work (feature branch only).
- This work must not interfere with live production before explicit merge/deploy gates.

### Required sequence (non-negotiable)
1. Builder produces `docs/GARMIN_API_DISCOVERY.md` (no code).
2. Advisor review against:
   - Garmin compliance obligations (`docs/GARMIN_CONNECT_DEVELOPER_COMPLIANCE.md`)
   - Existing Strava architectural patterns
   - Product priorities.
3. Founder approval.
4. Builder writes `docs/PHASE2_GARMIN_INTEGRATION_AC.md`.
5. Advisor reviews AC/tests for completeness/risk.
6. Founder approval.
7. Only then implementation on feature branch.

### What your review should focus on
- Exact Garmin API inventory and field-level mapping (no hand-wavy summaries).
- Push vs pull behavior, webhook contracts, callback expiry/rate limits/scopes.
- Source-of-truth rules and dedup behavior when Garmin + Strava both connected.
- Adapter boundary integrity (provider schema isolated at ingestion boundary).
- Compliance blockers:
  - no unofficial auth/library usage for official integration,
  - no write-back scope creep,
  - attribution/notice process controls,
  - AI consent/compliance dependencies already respected.
- Production safety:
  - no accidental path to prod from feature work,
  - explicit rollback/kill paths.

### Gate style
Return only:
1. **Findings by severity** (with exact file/symbol references),
2. **Go/No-Go** decision,
3. **Must-fix checklist** before next phase.

No "looks good overall" without hard evidence.

---

## Gate Status

| Gate | Artifact | Status |
|------|----------|--------|
| 1. Discovery | `docs/GARMIN_API_DISCOVERY.md` | COMPLETE |
| 2. Advisor review of discovery | See Gate 2 Review below | **COMPLETE — GO with 10 must-fix items** |
| 3. Founder approval of discovery | Verbal sign-off | **APPROVED** |
| 4. AC specification | `docs/PHASE2_GARMIN_INTEGRATION_AC.md` | COMPLETE |
| 5. Advisor review of AC | GO — 13 must-fix items found and resolved (5 Advisor 1 + 5 Advisor 2 + 3 final) | COMPLETE |
| 6. Founder approval of AC | Approved Feb 16, 2026 | **APPROVED** |
| 0D. Portal verification | `docs/garmin-portal/` (6 files) | **ALL VERIFIED** — except D4 completion-gate unknowns |
| PV. Portal verification AC revision | `docs/ADVISOR_NOTE_2026-02-22_PORTAL_VERIFICATION.md` | **GO** — 8 must-fix applied and cleared |
| 7. Implementation | `feature/garmin-oauth` branch | **D0 + D1 COMPLETE — builder resumes at D2** |

### Gate 6 Founder Decisions (recorded)

1. **Training API:** Out of scope. Treated as permanent until three conditions met: (a) full legal review, (b) client base that supports the exploration, (c) concrete use case. No code written for it.
2. **Disconnect behavior:** Explicit disconnect deletes Garmin activities and wellness data. Soft disconnect (token expiry) preserves data.
3. **AC approved.** Implementation begins on `feature/garmin-oauth`.
4. **Women's Health:** In scope for Tier 2. Founder wants MCT for female athlete training intelligence. Separate model (not `GarminDay`).

### Portal Verification Decisions (Feb 22, 2026)

1. **Webhook topology:** Per-type routes (advisor decision, portal confirms per-type URL registration)
2. **Webhook security:** No HMAC — mandatory layered controls (header + schema + userId + rate limit + IP allowlist)
3. **Women's Health:** Tier 2, separate `GarminCycle` model
4. **Undocumented fields:** Deferred from Tier 1 adapter until real payload proof
5. **Running dynamics:** NOT in JSON API — FIT-file-only, deferred to Tier 2

---

## Gate 2 Review: Discovery Document

**Reviewer:** Primary Advisor (Opus)
**Review date:** February 16, 2026
**Decision:** GO — with 10 must-fix items resolved in the AC document

### Findings by Severity

#### CRITICAL (0)

None.

#### HIGH (4)

**H1. Field mappings reference Activity model columns that don't exist.**
Discovery doc maps Garmin fields to `garmin_aerobic_te`, `garmin_anaerobic_te`, `garmin_te_label`, `garmin_feel`, `garmin_perceived_effort` (section 2A, lines 77-90). These columns do not exist on the `Activity` model (`apps/api/models.py` lines 360-419). Many fields marked "New field" but the TE/feel fields use a `garmin_*` prefix as if they're existing targets.
**AC requirement:** Separate "existing columns to populate" from "new columns to create" with explicit Alembic migration scope.

**H2. Deduplication service operates on raw dicts with guessed field names.**
`apps/api/services/activity_deduplication.py` extracts fields using unofficial library field names (`startTimeLocal`, `distance`, `averageHeartRate`), not official API field names (`StartTimeInSeconds`, `DistanceInMeters`, `AverageHeartRateInBeatsPerMinute`). Dedup will silently fail to match if fed raw official API payloads.
**AC requirement:** Deduplication MUST operate post-adapter on internal model field names, never on raw provider payloads.

**H3. Sleep data model naming inconsistency.**
Section 2B maps to `GarminSleep.calendar_date` and `GarminHRV.calendar_date`, but section 3D recommends a single `GarminDay` table. Field mappings and architecture contradict.
**AC requirement:** Use `GarminDay` consistently (per architecture recommendation). All field mappings reference `GarminDay`.

**H4. Webhook authentication mechanism unknown.**
Section 6B item 3 lists webhook auth as an implementation detail. Strava uses HMAC-SHA256 (`verify_webhook_signature` in `apps/api/services/strava_webhook.py`). If Garmin has no webhook auth, any external party can POST fake data.
**AC requirement:** Webhook endpoints MUST validate authenticity. If Garmin provides HMAC/signature, use it. If not, implement IP allowlisting or shared-secret header check.

#### MEDIUM (5)

**M1. Takeout import uses tighter dedup thresholds than live sync.**
`garmin_di_connect.py` uses 120s / 1.5% vs live sync's 1 hour / 5%. Same activity could deduplicate differently depending on ingestion path.
**AC requirement:** Document two-threshold design as intentional. Add test: "activity imported via takeout, then same activity arrives via webhook — verify no duplicate."

**M2. Running dynamics "confirmed native in JSON" but source is MyDataHelps, not portal.**
Discovery doc claims confirmation from portal screenshots (line 524-525) but research method (line 14) acknowledges inference from MyDataHelps.
**AC requirement:** Eval environment verification step: confirm Activity Details endpoint returns stride length, GCT, vertical oscillation, power in JSON. If not, defer running dynamics to Tier 2.

**M3. OAuth token refresh strategy not specified.**
Token fields listed but no refresh strategy, expiry duration, or failure handling.
**AC requirement:** Mirror Strava `ensure_fresh_token` pattern. On refresh failure, set `garmin_connected = False` and notify athlete to reconnect.

**M4. No backfill depth limit specified.**
Section 6B item 5 lists backfill depth as implementation detail but AC needs a bounded default.
**AC requirement:** Default backfill 90 days (consistent with correlation engine window).

**M5. 30-day display format notice cannot be "retroactive."**
Discovery doc section 5 says existing visualizations "may need retroactive notice." You cannot give retroactive prior notice.
**AC requirement:** 30-day notice is a hard rollout gate. Notice sent and 30-day clock expired before `feature/garmin-oauth` merges to `main`.

#### LOW (3)

**L1.** Sleep CalendarDate edge case well-documented but needs test requirement in AC.
**L2.** Training Effect "informational only" fields need code-level guard or annotation.
**L3.** Self-evaluation import caveat is good product thinking — preserve in AC as data quality annotation.

### Founder Additions (2)

**F1. Garmin disconnect compliance gate.**
AC must require calling Garmin deregistration endpoint and verifying local purge behavior (tokens + GarminDay + Garmin-provider activities) is idempotent. Ties contractual disconnect obligations to deterministic backend behavior.

**F2. Provider precedence contract test.**
Explicit tests for "Garmin primary, Strava secondary" at both dedup-time and read-time (retrieval/query behavior when both providers have data for the same athlete). Prevents silent drift.

---

## Must-Fix Checklist for AC (10 items)

All 10 must be addressed in `docs/PHASE2_GARMIN_INTEGRATION_AC.md` before implementation approval.

1. Resolve model naming: use `GarminDay` consistently in all field mappings (H3)
2. Separate existing vs new Activity model columns with explicit migration plan (H1)
3. Specify deduplication operates post-adapter on internal field names (H2)
4. Add webhook security requirement: HMAC, IP allowlisting, or shared secret (H4)
5. Set backfill depth default to 90 days (M4)
6. Add 30-day display format notice as hard rollout gate (M5)
7. Add running dynamics JSON verification step during eval (M2)
8. Add Sleep CalendarDate wakeup-day join test case (L1)
9. Require Garmin disconnect endpoint call + idempotent local purge (F1)
10. Add provider precedence contract tests at dedup-time and read-time (F2)

---

## Expected Output Format (Every Review)

### 1. Findings by Severity

- **CRITICAL:** Blocks proceeding. Must be resolved before gate clears.
- **HIGH:** Significant risk. Should be resolved before gate clears.
- **MEDIUM:** Worth addressing but not blocking.
- **LOW:** Noted for future consideration.

Each finding must include exact file paths, symbol references, or document section citations.

### 2. Go / No-Go Decision

Binary. No hedging. If no-go, state exactly what must change.

### 3. Must-Fix Checklist

Numbered list of specific, actionable items that must be completed before the next gate opens.
