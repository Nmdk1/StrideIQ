# StrideIQ Protocols (Composer 2 Playbook)

**Purpose:** System prompt + runbook for agents (especially **run-fluency / knowledge-base** work).  
**Non-negotiable overlay:** `docs/FOUNDER_OPERATING_CONTRACT.md` always wins if anything conflicts.

---

## 1) Operating Protocol (How Work Is Done)

- Follow the sequence: **discuss → scope → plan → test design → build → verify → deploy → evidence handoff**.
- No “vibe-based” changes; every recommendation must tie to a file, test, or runtime behavior.
- Suppress hallucination: if uncertain, state uncertainty and verify before proceeding.
- Athlete-first principle: system informs, athlete decides; do not override athlete intent silently.
- Finish end-to-end: no partial “analysis only” handoffs unless the founder explicitly asked to pause.
- Keep changes scoped; avoid touching unrelated files during focused fixes.

---

## 2) Git Protocol (Strict)

- **Never** use `git add -A`; stage only intended files.
- Use focused commits with clear “why” in message.
- Avoid destructive commands (`reset --hard`, force-push) unless explicitly requested.
- Don’t amend commits unless explicitly requested.
- Before commit, always capture:
  - `git status`
  - `git diff` (staged + unstaged)
  - recent commit style (`git log -n …`)
- After commit: verify clean expected state with `git status`.
- Push only when ready for CI/deploy evidence.

---

## 3) CI Protocol (Source of Truth)

- CI is authoritative for integration correctness.
- Always report:
  - CI run URL
  - run ID
  - pass/fail
  - failure root cause
- If CI fails before jobs start, distinguish platform issues (e.g., billing/spend cap) from code regressions.
- Don’t claim “green” unless all required jobs actually completed successfully.

---

## 4) Production Protocol (Deploy + Smoke)

### Canonical deploy command

```bash
cd /opt/strideiq/repo && git pull origin main && docker compose -f docker-compose.prod.yml up -d --build
```

### Founder token generation (on server)

```bash
docker exec strideiq_api python -c "
from core.security import create_access_token
from database import SessionLocal
from models import Athlete
db = SessionLocal()
user = db.query(Athlete).filter(Athlete.email=='mbshaf@gmail.com').first()
print(create_access_token(data={'sub': str(user.id), 'email': user.email, 'role': user.role}))
db.close()
"
```

### Smoke check

```bash
TOKEN=$(docker exec strideiq_api python -c "
from core.security import create_access_token
from database import SessionLocal
from models import Athlete
db = SessionLocal()
user = db.query(Athlete).filter(Athlete.email=='mbshaf@gmail.com').first()
print(create_access_token(data={'sub': str(user.id), 'email': user.email, 'role': user.role}))
db.close()
") && curl -s -H "Authorization: Bearer $TOKEN" https://strideiq.run/v1/home | python3 -m json.tool
```

### Quick logs

```bash
docker logs strideiq_api --tail=50
docker logs strideiq_web --tail=50
```

---

## 5) Required Handoff Evidence (Always)

- Commit SHA + changed file list
- Exact test command output pasted (not summarized only)
- CI run URL + status
- Production deploy output snippet
- Production smoke output snippet
- Any residual risk clearly labeled (blocking vs non-blocking)

---

## 6) Proper Pathways for Run-Fluency KB Work

**Related specs:** `docs/specs/WORKOUT_FLUENCY_REGISTRY_SPEC.md`, `docs/specs/WORKOUT_FLUENCY_REGISTRY_PR_CHECKLIST.md`.

For a knowledge-base / fluency initiative, run this path:

| Path | Focus |
|------|--------|
| **A: Knowledge rules** | Canonical rules in one place (periodization, workout intent, cutback logic, safety invariants). |
| **B: Contract surface** | Explicit schema for what planner/prompt must output (fields + constraints + failure behavior). |
| **C: Enforcement** | Quality gate / fail-closed checks that block invalid outputs. |
| **D: Scenario tests** | Cohort tests by distance / experience / injury / cold-start. |
| **E: Production trace** | Verify real payload transitions and user-facing behavior under load/burst conditions. |
| **F: Iteration loop** | Gaps → spec update → tests → implementation → re-validate. |

---

## 7) Top Gotchas You’re Likely to Hit

- **PowerShell quoting/redirect quirks** break multiline ssh/python commands.
- **CI false negatives** from account/billing issues can look like code failures.
- **Dirty repo noise** can cause accidental staging of unrelated docs/scripts.
- **Fallback outputs marked as “fresh”** can stop polling too early if interim metadata is missing.
- **Webhook bursts** can thrash generation unless coalesced/debounced.
- **“Looks fine” plan quality** can still fail intent/competency without purpose-level tests.
- **Schema drift in prod** (missing migration/table) silently degrades model paths.
- **Mock-heavy tests** can pass while real endpoint/control-flow still fails; keep endpoint-level tests.

---

## 8) Composer 2 “Instruction Block” (Reuse)

- Work in this order: discuss, scope, plan, tests, build, verify, deploy, evidence.
- Stage only touched files; no `git add -A`.
- CI-first truth model; include run URL/ID in all handoffs.
- Deploy only after local + CI confidence; include smoke and logs.
- Fail closed when contracts/invariants fail; never silently downgrade user trust.
- Distinguish platform failures from code failures explicitly.
- Provide proof artifacts, not claims.

---

*Authored for StrideIQ agent sessions; align with `docs/FOUNDER_OPERATING_CONTRACT.md` and vision docs on every new feature.*
