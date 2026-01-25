# ADR-057: Provider Expansion via File Import (Garmin/Coros) + Unified Adapter Seam

## Status
**Accepted (Implemented)**

## Date
2026-01-25

## Context
StrideIQ currently derives most training intelligence from Strava via asynchronous ingestion. Phase 7 expands beyond Strava to reduce provider lock-in and improve data completeness (activities + recovery signals).

Constraints:
- We must preserve the platform’s **trust contract**: deterministic, auditable, and explainable data flows.
- We must stay **viral-safe**: imports must queue and degrade gracefully (no long-running HTTP parsing).
- We must avoid high-risk auth patterns: **no credential storage** for third-party providers unless the provider offers a supported OAuth flow.
- We need a practical path now: the owner already has a **Garmin export file** ready for upload.

Reality:
- Garmin Connect “unofficial” login flows (username/password) are brittle and a security liability.
- Coros official integrations may be limited or require partner access; file import is the reliable starting point.

## Decision
Implement Phase 7 as an **import-first provider expansion**:

1) **File import v1 (Garmin first, Coros-ready seam)**  
Add a DB-backed `AthleteDataImportJob` and an async worker pipeline that ingests uploaded export files into the canonical `Activity`/`ActivitySplit` model with:
- idempotency
- bounded audit logging
- operational visibility and safe retries

2) **Unified provider seam**  
Treat “file import” as a first-class provider adapter type so Garmin/Coros can later be upgraded to OAuth/webhooks without rewriting analytics. The canonical storage remains `Activity` with `provider` + `external_activity_id` uniqueness.

3) **Deprecate credential-based Garmin Connect**  
Disable username/password Garmin “connect” endpoints by default and gate any legacy behavior behind an owner-only flag in non-prod (for emergency debugging only).

## Considered Options (Rejected)
### Option A: Keep username/password Garmin Connect as the primary integration
**Rejected:** Even encrypted, storing third-party credentials is a high-risk pattern and brittle operationally. It also violates least-privilege and expands breach blast radius.

### Option B: Wait for official Garmin/Coros OAuth integrations before shipping Phase 7
**Rejected:** Blocks near-term value despite an available export file, and delays validation of multi-provider normalization. File import provides a safe, immediate “value unlock.”

### Option C: Store uploaded exports in the DB as blobs
**Rejected (for v1):** Can create large DB bloat and complicate backups/retention. Prefer a shared uploads directory (or object storage in production) with strict size limits and deletion after processing.

## Consequences
### Positive
- Immediate Garmin value (calendar populated, PBs computable) without waiting on third-party APIs.
- Deterministic, auditable ingestion: every import is traceable to a job id and a bounded audit payload.
- Establishes the adapter seam for future OAuth/webhook providers.

### Negative
- Parsing multiple export formats is non-trivial (ZIP/TCX/GPX/FIT); we must implement format detection and bounded failure modes.
- Cross-provider duplicates may occur; we must implement a conservative dedup policy to prevent analytics corruption.

## Rationale (N=1, no population averages)
Provider expansion is not about “more data for population modeling.” It is about improving the N=1 signal by:
- increasing completeness (training history + recovery signals)
- improving receipts (athlete can trace claims back to imported activities)
- keeping ingestion deterministic and testable

## Audit Logging Requirements (Minimum)
Every import job must emit append-only events (or a bounded job payload) containing:
- `job_id`, `athlete_id`, `provider` (garmin|coros)
- `created_at`, `started_at`, `finished_at`, `status` (queued|running|success|error)
- `original_filename`, `file_size_bytes`, `sha256`
- `parser_types_used` (e.g., ["fit","tcx"] or ["garmin_di_connect_summarized_activities_json"])
- `activities_parsed`, `activities_inserted`, `activities_updated`, `activities_skipped_duplicate`, `splits_inserted`
- `errors_count` + a bounded list of error codes (no raw file content)

## Security / Privacy Considerations
- Upload endpoints require authentication; an athlete can only import for themselves.
- Strict file size caps; refuse suspicious ZIPs (path traversal; zip bombs).
- Uploaded files are stored only temporarily (delete after processing or after retention window).
- Logs are **metadata-only** (counts, ids, hashes) — no sensitive file contents.
- Credential-based Garmin connect is disabled by default; if ever enabled for debugging, it must be owner-only and audited.

## Feature Flags
- `integrations.garmin_file_import_v1`: off → hide UI and block endpoints; on → enable file import
- `integrations.coros_file_import_v1`: same semantics
- `integrations.garmin_password_connect_legacy`: default off; admin-only escape hatch in non-prod

## Implementation Notes (as shipped)
- **Garmin**: v1 supports the DI_CONNECT export (`*_summarizedActivities.json`) inside the uploaded ZIP.
- **Coros**: the seam/flags are present; a Coros parser is not implemented in v1 (deferred until we have a concrete export format sample).
- **Idempotency**: DB-level `ON CONFLICT DO NOTHING` on `(provider, external_activity_id)` prevents repeat-upload failures.
- **Dedup**: importer uses time+distance matching to avoid importing a second copy when Strava already has the run; Calendar also collapses probable cross-provider duplicates for display safety.

## Test Strategy
### Unit
- ZIP safety: reject `..` paths and oversized extracts.
- Parser invariants: start_time required; distance/duration non-negative; provider/external id stable.
- Idempotency: re-import same file does not create duplicate activities.
- Dedup: cross-provider duplicate detection prevents double-counting.

### Integration
- Upload → job created → worker processes → activities visible in calendar API.
- Failure path: parse error marks job failed, does not partially corrupt DB.

## Rebuild / Verify Process
1. Enable import flag for allowlisted athlete(s).
2. Run import on known Garmin export and verify:
   - calendar populated
   - PBs reasonable
   - no duplicate explosion vs Strava
3. Verify audit/job record exists with correct counts and no sensitive payload.
4. Expand rollout to more athletes.

## Related
- Phase plan: `docs/PHASED_WORK_PLAN.md`
- Viral-safe ingestion policy: `docs/adr/ADR-054-viral-safe-ingestion-resilience-and-emergency-brake.md`

