# Coach Release Gate Checklist

**Purpose:** Prevent regressions in StrideIQ's marquee Coach feature.

Use this checklist for any change touching:
- `apps/api/services/ai_coach.py`
- `apps/api/routers/ai_coach.py`
- `apps/web/app/coach/page.tsx`
- `apps/web/lib/api/services/ai-coach.ts`
- LLM provider initialization/routing/fallback logic

---

## Gate 1 - Pre-Merge (Code + Tests)

All items are required before merge to `main`.

- [ ] Scoped diff only (coach-related files; no unrelated edits)
- [ ] Contract tests pass:
  - `python -m pytest -q apps/api/tests/test_coach_output_contract_chat.py`
- [ ] Routing/contract tests pass (if touched):
  - `python -m pytest -q apps/api/tests/test_coach_routing.py`
  - `python -m pytest -q apps/api/tests/test_coach_contract.py`
- [ ] No fallback regression:
  - Gemini failure + Opus available => returns non-error response
  - Gemini failure + no Opus => fail-closed response
- [ ] Streaming route unchanged or explicitly tested:
  - `POST /v1/coach/chat/stream` emits `meta`, `delta`, `done`

---

## Gate 2 - Deploy Verification (Production)

Run these commands on droplet after deploy.

### 2.1 Health

```bash
docker ps --format "table {{.Names}}\t{{.Status}}" | egrep "strideiq_(api|worker|web|postgres|redis|caddy)"
```

Pass criteria:
- `strideiq_api`, `strideiq_worker`, `strideiq_web` all up
- `strideiq_postgres`, `strideiq_redis` healthy

### 2.2 Non-Streaming Coach Sanity

```bash
TOKEN=$(docker exec strideiq_api python -c "
from core.security import create_access_token
from core.database import SessionLocal
from models import Athlete
db = SessionLocal()
u = db.query(Athlete).filter(Athlete.email=='mbshaf@gmail.com').first()
print(create_access_token(data={'sub': str(u.id), 'email': u.email, 'role': u.role}))
db.close()
")
curl -s -X POST "https://strideiq.run/v1/coach/chat" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message":"Quick check: summarize my current training state in 2 short bullets.","include_context":true}' \
| python3 -c 'import json,sys; d=json.load(sys.stdin); print({"error": d.get("error"), "prefix": (d.get("response") or "")[:140]})'
```

Pass criteria:
- `error` is `False`
- response text is non-empty

### 2.3 Non-Streaming Stability (10 Samples)

```bash
for i in $(seq 1 10); do
  TOKEN=$(docker exec strideiq_api python -c "
from core.security import create_access_token
from core.database import SessionLocal
from models import Athlete
db = SessionLocal()
u = db.query(Athlete).filter(Athlete.email=='mbshaf@gmail.com').first()
print(create_access_token(data={'sub': str(u.id), 'email': u.email, 'role': u.role}))
db.close()
")
  OUT=$(curl -s -X POST "https://strideiq.run/v1/coach/chat" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"message":"Are my last 7 days trending better or worse? Keep it short.","include_context":true}')
  echo "sample=$i $(echo "$OUT" | python3 -c 'import json,sys; d=json.load(sys.stdin); r=(d.get("response") or "").lower(); print({"error": d.get("error"), "unavailable": ("temporarily unavailable" in r)})')"
  sleep 2
done
```

Pass criteria:
- 10/10 samples: `error=False`
- 0/10 samples: `"temporarily unavailable"`

### 2.4 Streaming Sanity (SSE)

```bash
TOKEN=$(docker exec strideiq_api python -c "
from core.security import create_access_token
from core.database import SessionLocal
from models import Athlete
db = SessionLocal()
u = db.query(Athlete).filter(Athlete.email=='mbshaf@gmail.com').first()
print(create_access_token(data={'sub': str(u.id), 'email': u.email, 'role': u.role}))
db.close()
")
curl -N -s -X POST "https://strideiq.run/v1/coach/chat/stream" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message":"Give me a 2-bullet status update from last 7 days.","include_context":true}' | sed -n '1,80p'
```

Pass criteria:
- Contains `event: meta`
- Contains one or more `event: delta`
- Ends with `event: done` and `timed_out: false`

### 2.5 Worker Error Signature Scan

```bash
docker logs strideiq_worker --since=15m | egrep -n "Gemini query failed|attempting Opus fallback|Coach is temporarily unavailable|AI Coach error|ModuleNotFoundError" || echo "No coach/error signatures in last 15m"
```

Pass criteria:
- No recurring crash signatures
- If fallback appears, requests still succeed and no user-facing outage

---

## Gate 3 - Release Decision

Release is **GO** only if all Gate 1 and Gate 2 criteria pass.

Release is **NO-GO** if any of the following occurs:
- Any sample returns `error=True`
- Any sample returns "temporarily unavailable"
- SSE does not emit `done`
- Worker logs show repeated coach errors after deploy

---

## Incident Rule

If Coach availability regresses:
1. Freeze non-critical merges.
2. Triage on production logs first.
3. Hotfix with scoped diff + regression tests.
4. Re-run full Gate 2 before declaring closed.

