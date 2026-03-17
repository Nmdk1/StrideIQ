# Kimi K2.5 Canary Activation Runbook

## Current State (as of 2026-03-17)

**Canary is OFF.** `KIMI_CANARY_ENABLED=false` in production.  
Production is running `claude-sonnet-4-6` for all athletes — zero behavior change.

## Scope of Kimi Integration

| Call site | Status |
|---|---|
| `routers/home.py` — home briefing | Wired to `call_llm` + canary routing |
| `tasks/home_briefing_tasks.py` — background briefing | Wired to `call_llm` + canary routing |
| `services/knowledge_extraction_ai.py` — knowledge extraction | Wired to `call_llm` via `KNOWLEDGE_PRIMARY_MODEL` |
| `services/ai_coach.py` — coach tool-call loop | **NOT wired** — remains on Sonnet until offline tool-parity tests pass |

Coach tool-call loop requires Anthropic tool-use format which differs from OpenAI-compatible. It will be migrated only after dedicated offline parity validation.

## Pre-Canary Health Gate

Before enabling canary, run a 50-call health probe and require:
- Success rate >= 98% (no 429 engine_overloaded sustained bursts)
- p95 latency <= 1.5x Sonnet baseline (~4-5s for briefing)
- JSON parse compliance >= 99.5% on briefing prompts

Run the probe:
```bash
ssh root@187.124.67.153
cd /opt/strideiq/repo
# Script lives at repo root — copy into container then run with STRIDEIQ_API_DIR set
docker cp scripts/compare_kimi_vs_sonnet.py strideiq_api:/tmp/compare_kimi_vs_sonnet.py
docker exec -e STRIDEIQ_API_DIR=/app -w /app -i strideiq_api python /tmp/compare_kimi_vs_sonnet.py --calls 10 --kimi-only --output-dir /tmp/kimi_probe
docker exec strideiq_api cat /tmp/kimi_probe/summary.md
```

If verdict is GO, proceed to canary activation below.

## Canary Activation (Safe Toggle Procedure)

### Step 1 — Backup current .env
```bash
ssh root@187.124.67.153
cp /opt/strideiq/repo/.env /opt/strideiq/repo/.env.backup.$(date +%Y%m%d_%H%M%S)
echo "Backup created"
```

### Step 2 — Apply changes
```bash
sed -i 's/KIMI_CANARY_ENABLED=false/KIMI_CANARY_ENABLED=true/' /opt/strideiq/repo/.env
sed -i 's/KIMI_CANARY_ATHLETE_IDS=/KIMI_CANARY_ATHLETE_IDS=4368ec7f-c30d-45ff-a6ee-58db7716be24/' /opt/strideiq/repo/.env
```

### Step 3 — Show diff before restart
```bash
diff /opt/strideiq/repo/.env.backup.* /opt/strideiq/repo/.env | grep KIMI
```
Expected output:
```
< KIMI_CANARY_ENABLED=false
< KIMI_CANARY_ATHLETE_IDS=
> KIMI_CANARY_ENABLED=true
> KIMI_CANARY_ATHLETE_IDS=4368ec7f-c30d-45ff-a6ee-58db7716be24
```

### Step 4 — Restart
```bash
cd /opt/strideiq/repo
docker compose -f docker-compose.prod.yml restart api worker
sleep 10
```

### Step 5 — Verify runtime vars in both containers
```bash
# API container
echo "from core.config import settings; print('CANARY:', settings.KIMI_CANARY_ENABLED); print('IDS:', settings.KIMI_CANARY_ATHLETE_IDS)" \
  | docker exec -i strideiq_api python

# Worker container
echo "from core.config import settings; print('CANARY:', settings.KIMI_CANARY_ENABLED); print('IDS:', settings.KIMI_CANARY_ATHLETE_IDS)" \
  | docker exec -i strideiq_worker python
```
Expected: `CANARY: True` and `IDS: 4368ec7f-c30d-45ff-a6ee-58db7716be24`

### Step 6 — Post-restart smoke check
```bash
# Verify canary routing fires for founder athlete
echo "
from core.llm_client import resolve_briefing_model
model = resolve_briefing_model(athlete_id='4368ec7f-c30d-45ff-a6ee-58db7716be24')
print('FOUNDER MODEL:', model)
model2 = resolve_briefing_model(athlete_id='00000000-0000-0000-0000-000000000000')
print('OTHER ATHLETE MODEL:', model2)
" | docker exec -i strideiq_api python
```
Expected:
```
FOUNDER MODEL: kimi-k2.5
OTHER ATHLETE MODEL: claude-sonnet-4-6
```

### Step 7 — Check API health
```bash
TOKEN=$(docker exec strideiq_api python -c "
from core.security import create_access_token
from database import SessionLocal
from models import Athlete
db = SessionLocal()
user = db.query(Athlete).filter(Athlete.email=='mbshaf@gmail.com').first()
print(create_access_token(data={'sub': str(user.id), 'email': user.email, 'role': user.role}))
db.close()
")
curl -s -H "Authorization: Bearer $TOKEN" https://strideiq.run/v1/home | python3 -m json.tool | head -20
```

## Rollback (Instant)

```bash
ssh root@187.124.67.153
# Option A: restore backup
cp /opt/strideiq/repo/.env.backup.<timestamp> /opt/strideiq/repo/.env

# Option B: flip flags inline
sed -i 's/KIMI_CANARY_ENABLED=true/KIMI_CANARY_ENABLED=false/' /opt/strideiq/repo/.env
sed -i 's/KIMI_CANARY_ATHLETE_IDS=.*/KIMI_CANARY_ATHLETE_IDS=/' /opt/strideiq/repo/.env

cd /opt/strideiq/repo
docker compose -f docker-compose.prod.yml restart api worker
echo "Rolled back. Verifying..."
echo "from core.config import settings; print('CANARY:', settings.KIMI_CANARY_ENABLED)" \
  | docker exec -i strideiq_api python
```
Expected after rollback: `CANARY: False`

## Non-Go Conditions (abort canary immediately if any occur)

- Kimi 429 rate > 2% over any 10-minute window
- Home briefing JSON parse failure on any founder-visible call
- Fallback to Sonnet triggered > 5% of founder calls
- Any hallucinated athlete fact in briefing output
- Briefing p95 latency > 15s sustained

## API Endpoint (International)

- **Base URL:** `https://api.moonshot.ai/v1` (`.ai` — international)
- **NOT:** `https://api.moonshot.cn/v1` (`.cn` — China domestic only)
- Model: `kimi-k2.5` (temperature must be 1 — reasoning model constraint)
