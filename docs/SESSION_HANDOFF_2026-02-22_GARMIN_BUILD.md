# Session Handoff — Phase 2 Garmin Build
**Date:** February 22, 2026
**Status:** Gate 6 cleared. Build authorized.
**Branch:** `feature/garmin-oauth`

---

## Builder Assignment

**Gate 6 cleared. Build D0 through D8 in order, tests-first, on `feature/garmin-oauth`.**

Read `docs/PHASE2_GARMIN_INTEGRATION_AC.md` — it is the complete spec. Every deliverable, every acceptance criterion, every test is defined there. Do not start from any other source.

---

## Read order before first tool call

1. `docs/FOUNDER_OPERATING_CONTRACT.md`
2. `docs/PRODUCT_MANIFESTO.md`
3. `docs/GARMIN_CONNECT_DEVELOPER_COMPLIANCE.md`
4. `docs/GARMIN_API_DISCOVERY.md`
5. `docs/PHASE2_GARMIN_INTEGRATION_AC.md` ← the spec
6. This document

---

## Gate status at handoff

| Gate | Status |
|---|---|
| 1. Discovery | COMPLETE |
| 2. Advisor review of discovery | COMPLETE — GO |
| 3. Founder approval of discovery | APPROVED |
| 4. AC specification | COMPLETE |
| 5. Advisor review of AC | COMPLETE — GO (after 3 revision rounds) |
| 6. Founder approval of AC | **APPROVED** |
| 7. Implementation | **UNBLOCKED — start now** |

---

## Build order (non-negotiable)

```
D0 → D1 → D2 → D3 → D4 → D5 → D6 → D7 → D8
```

| Deliverable | What it is | Key constraint |
|---|---|---|
| D0 | Dedup service refactor | Prerequisite for everything. Tests first. Must pass before D3. |
| D1 | Data model + migrations | Three migrations: `garmin_001`, `garmin_002`, `garmin_003`. Single `EXPECTED_HEADS` update at end. |
| D2 | OAuth 2.0 flow | **[PORTAL VERIFY] before implementing** — confirm OAuth version (2.0 vs 1.0a) in eval env first. |
| D3 | Adapter layer | All Garmin field names live here and only here. |
| D4 | Webhook endpoint | **[PORTAL VERIFY] before implementing** — confirm auth mechanism and payload format in eval env first. |
| D5 | Activity sync | Garmin primary, Strava secondary. 7 provider precedence tests required. |
| D6 | Health/wellness sync | `GarminDay` upsert. Sleep CalendarDate join test required. |
| D7 | Initial backfill | 90 days. Idempotent. Triggered on OAuth connect. |
| D8 | Attribution | `GarminBadge` component. Conditional on `provider="garmin"`. |

---

## [PORTAL VERIFY] items — founder action required

The builder cannot unblock these alone. When the builder reaches D2 or D4, the founder must log in to the Garmin developer portal (`developerportal.garmin.com` with `michael@strideiq.run`) and verify:

| Item | Needed for | What to check |
|---|---|---|
| OAuth version (2.0 or 1.0a?) | D2 | Initiate auth flow in eval env, observe redirect and callback |
| OAuth scope names | D2 | Authorization screen |
| OAuth token refresh behavior | D2.2 | Attempt token refresh in eval env |
| Webhook auth mechanism | D4.1 | Developer portal webhook config page |
| Webhook payload format | D4.2 | Receive a test webhook |
| Activity Details JSON — running dynamics fields | D5.3 | Fetch a real Activity Details response |
| Garmin deregistration endpoint | D2.3 | Developer portal docs |

Builder: when you hit a [PORTAL VERIFY] stop-gate, stop and ask the founder to run the verification. Do not proceed past the gate without the answer.

---

## Hard rules

1. **All Garmin code on `feature/garmin-oauth` only.** Never commit to `main`.
2. **Tests-first.** Write failing tests before implementation. Tests are the contract.
3. **D0 must pass before D3 begins.** The dedup refactor is a prerequisite, not optional.
4. **`garmin_service.py` is retired.** Delete it in the first commit. Replace, do not patch.
5. **Training API is permanently out of scope.** Do not build it, do not propose it.
6. **`EXPECTED_HEADS` updated once** — after all three D1 migrations are committed. Not after each one.
7. **Merge to `main` is blocked** until Gate 0A (30-day Garmin notice) clears. The founder will send this notice during the build. Development continues on feature branch.

---

## Key architectural decisions already made (do not re-open)

- `GarminDay` is the single wellness model — no separate `GarminSleep`, `GarminHRV`
- Garmin is primary source; Strava is secondary — Garmin wins dedup conflicts
- Training API permanently out of scope (compliance §4.6 IP exposure)
- Push webhook architecture preferred; ping/pull fallback if portal confirms push not supported
- 90-day backfill depth
- Dedup operates post-adapter on internal field names only
- Single webhook URL (multiplexed) unless portal reveals per-type URL requirement
- `consent_audit_log` reuses existing schema: `consent_type="integration"`, `action="garmin_connected"/"garmin_disconnected"` — no new migration

---

## Production state at handoff

- Production is healthy and on `main`
- Phase 1 (AI consent) is live and gated
- All backend and frontend tests green
- No open regressions

---

## What the next session looks like

Builder creates branch, runs D0, shows passing tests, reports back. Founder reviews. Then D1. Then a [PORTAL VERIFY] pause before D2.

No code ships to production until all 7 gates clear and the 30-day notice window closes.
