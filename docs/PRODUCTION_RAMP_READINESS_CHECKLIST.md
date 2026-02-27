# Production Ramp Readiness Checklist

**Purpose:** Ensure sync + home coaching remain robust as production load scales.

Use this checklist before expanding beyond founder-only usage.

---

## Gate 1 - Pre-Ramp Validation (Required)

- [ ] Founder path verified end-to-end after a real sync event:
  - Garmin or Strava sync completes
  - Activity source/provider updates correctly
  - Home briefing cache is evicted and refreshed
  - `/v1/home` returns updated `coach_briefing` or deterministic fallback
- [ ] No stale lock-in:
  - `briefing_state` does not remain `stale`/`missing` beyond one refresh window after sync
- [ ] Circuit recovery verified:
  - Force probe path can enqueue refresh even when circuit is open on real data-change events
- [ ] Deterministic fallback verified:
  - If LLM providers fail, cache still receives a refreshed fallback briefing (no stale narrative loop)
- [ ] Working tree clean and tests green for changed scope

---

## Gate 2 - Production Health Snapshot (Required)

Run on droplet:

```bash
docker ps --format "table {{.Names}}\t{{.Status}}" | egrep "strideiq_(api|worker|web|postgres|redis|caddy)"
docker logs strideiq_api --since=20m | egrep -n "garmin|strava|home briefing|briefing_state|error|exception" || true
docker logs strideiq_worker --since=20m | egrep -n "generate_home_briefing|enqueue_briefing_refresh|deterministic-fallback|garmin|strava|error|exception" || true
```

Pass criteria:
- API, worker, web are up
- No recurring crash loop signatures
- Sync and briefing refresh events appear without repeated failures

---

## Gate 3 - Canary Ramp Plan

### 3.1 Cohort Expansion

- [ ] Add **5 athletes** (canary cohort 1)
- [ ] Observe for 24 hours
- [ ] If stable, add **20 athletes** (canary cohort 2)
- [ ] Observe for 24 hours
- [ ] If stable, proceed to broader rollout

### 3.2 Cohort Success Metrics (must hold)

- [ ] Sync success rate >= 99%
- [ ] Home briefing refresh success (fresh or deterministic fallback) >= 99%
- [ ] Stale briefing incidents per athlete per day <= 0.05
- [ ] Zero unresolved one-athlete lock-in incidents

---

## Gate 4 - One-Athlete Failure Drill (Required)

For one canary athlete, intentionally verify recovery paths:

- [ ] Simulate/observe a refresh failure condition
- [ ] Confirm next real sync triggers:
  - cache dirty
  - force enqueue with probe
  - fresh or deterministic fallback payload within window
- [ ] Confirm athlete is no longer stuck in stale state

If this drill fails, rollout is **NO-GO**.

---

## GO / NO-GO Decision

### GO only if all are true

- Gate 1 fully complete
- Gate 2 healthy
- Canary metrics pass for both cohorts
- One-athlete failure drill passes

### NO-GO if any are true

- Any athlete remains stale after successful sync + refresh window
- Repeated circuit-open lock-in without probe recovery
- Repeated briefing generation failures without deterministic fallback writes
- Worker/API error signatures recur after remediation

---

## Incident Response Rule

If a one-athlete stale lock-in reappears:

1. Freeze rollout expansion.
2. Capture athlete-specific evidence (sync event, enqueue, task result, cache state).
3. Restore deterministic freshness path first (athlete-visible recovery).
4. Patch root cause with scoped diff.
5. Re-run Gate 1 and Gate 4 before resuming rollout.

