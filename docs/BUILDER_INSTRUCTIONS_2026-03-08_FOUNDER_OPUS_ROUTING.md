# Builder Instructions: Fix Founder/VIP Opus Routing + Gemini Model Swap

**Priority:** URGENT — founder and VIP athletes are getting Gemini for 95% of coach conversations despite having unlimited/elevated Opus budgets; standard users are on an outdated Gemini model
**Scope:** 2 code changes, 1 env var, 2 DB updates, deploy
**Risk:** Low — additive routing logic, model string swap, no schema changes

---

## Problem

The budget system correctly identifies founder (`_is_founder`) and VIP (`is_athlete_vip`) athletes and gives them unlimited or 10x Opus allocations. But `get_model_for_query()` ignores this — it routes to Opus ONLY based on `is_high_stakes_query()` keywords or `classify_query_complexity() == "high"`. The budget bypass and the routing decision are decoupled.

Additionally, `OWNER_ATHLETE_ID` is not set in any environment configuration (not in `.env`, not in `docker-compose.prod.yml`), so `_is_founder()` always returns `False` in production.

Result: The founder pays for Opus, has code that says "founder bypasses all limits," but every normal coaching question goes to Gemini.

---

## Step 1: Fix routing for founder/VIP (ai_coach.py)

**File:** `apps/api/services/ai_coach.py`
**Function:** `get_model_for_query` (starts with `"""Select model based on query content and athlete tier`)

Insert the following block AFTER the `has_active_subscription` check and BEFORE the keyword-based routing (`is_high_stakes = is_high_stakes_query(message)`):

```python
# Founder always gets Opus — no keyword gating
if athlete_id and self._is_founder(athlete_id):
    if self.anthropic_client:
        logger.info(f"Routing to Opus: founder_bypass")
        return self.MODEL_HIGH_STAKES, True
    return self.MODEL_DEFAULT, False

# VIP athletes always get Opus (budget checked but not keyword-gated)
if athlete_id and self.is_athlete_vip(athlete_id):
    allowed, reason = self.check_budget(athlete_id, is_opus=True, is_vip=True)
    if allowed and self.anthropic_client:
        logger.info(f"Routing to Opus: vip_always, athlete={athlete_id}")
        return self.MODEL_HIGH_STAKES, True
    else:
        logger.info(f"VIP Opus fallback: reason={reason}, has_anthropic={bool(self.anthropic_client)}")
        return self.MODEL_DEFAULT, False
```

The existing keyword-based routing below this block remains unchanged — it handles standard (non-founder, non-VIP) users.

---

## Step 2: Set OWNER_ATHLETE_ID in production

**On the server**, add to the `.env` file (which `docker-compose.prod.yml` loads via `env_file: - .env`):

```bash
# Get the founder's athlete UUID
docker exec strideiq_api python -c "
from core.database import SessionLocal
from models import Athlete
db = SessionLocal()
user = db.query(Athlete).filter(Athlete.email=='mbshaf@gmail.com').first()
print(f'OWNER_ATHLETE_ID={user.id}')
db.close()
"
```

Add the output line to `/opt/strideiq/repo/.env`.

---

## Step 3: Set is_coach_vip for Larry and Belle Vignes

**On the server**, set VIP status for the founder's father and new beta tester:

```bash
docker exec strideiq_api python -c "
from core.database import SessionLocal
from models import Athlete
db = SessionLocal()

# Larry (founder's father)
larry = db.query(Athlete).filter(Athlete.email.ilike('%larry%')).first()
if larry:
    larry.is_coach_vip = True
    print(f'Larry: {larry.email} -> is_coach_vip=True')

# Belle Vignes (new beta tester — confirm email with founder if needed)
belle = db.query(Athlete).filter(Athlete.email.ilike('%belle%')).first()
if not belle:
    belle = db.query(Athlete).filter(Athlete.email.ilike('%vignes%')).first()
if belle:
    belle.is_coach_vip = True
    print(f'Belle: {belle.email} -> is_coach_vip=True')

db.commit()
db.close()
"
```

If the email search doesn't find them, check with the founder for exact emails, or use the admin panel (`/admin` → user list → set Coach VIP toggle).

---

## Step 4: Verify

After deploy, run this on the server to confirm routing:

```bash
docker logs strideiq_api --tail=200 | grep -i "routing to opus\|founder_bypass\|vip_always"
```

Then have the founder send a normal coaching message (not injury-related, e.g. "how was my week?") and confirm the log shows `Routing to Opus: founder_bypass` instead of Gemini routing.

---

## Test (local)

Add to existing test file `apps/api/tests/test_coach_model_tiering.py`:

```python
def test_founder_always_routes_opus(mock_db):
    """Founder gets Opus for ALL queries, not just high-stakes."""
    with patch.dict('os.environ', {
        'OWNER_ATHLETE_ID': str(FOUNDER_ID),
        'COACH_MODEL_ROUTING': 'on',
    }):
        coach = AICoach(mock_db)
        coach.anthropic_client = MagicMock()

        # Normal question — should still get Opus for founder
        model, is_opus = coach.get_model_for_query("low", athlete_id=FOUNDER_ID, message="how was my week?")
        assert is_opus is True
        assert model == coach.MODEL_HIGH_STAKES


def test_vip_always_routes_opus(mock_db):
    """VIP athletes get Opus for ALL queries."""
    vip_id = uuid4()
    with patch.dict('os.environ', {
        'COACH_VIP_ATHLETE_IDS': str(vip_id),
        'COACH_MODEL_ROUTING': 'on',
    }):
        coach = AICoach(mock_db)
        coach.anthropic_client = MagicMock()

        model, is_opus = coach.get_model_for_query("low", athlete_id=vip_id, message="what should I do tomorrow?")
        assert is_opus is True
        assert model == coach.MODEL_HIGH_STAKES


def test_standard_user_still_keyword_gated(mock_db):
    """Non-founder, non-VIP users still require keyword routing."""
    random_id = uuid4()
    with patch.dict('os.environ', {
        'OWNER_ATHLETE_ID': '',
        'COACH_VIP_ATHLETE_IDS': '',
        'COACH_MODEL_ROUTING': 'on',
    }):
        coach = AICoach(mock_db)
        coach.anthropic_client = MagicMock()

        # Normal question — should NOT get Opus
        model, is_opus = coach.get_model_for_query("low", athlete_id=random_id, message="how was my week?")
        assert is_opus is False
```

---

---

## Step 5: Swap Gemini 2.5 Flash → Gemini 3 Flash

The standard coaching model is being upgraded to Gemini 3 Flash (NOT 3.1 Flash Lite — Lite is optimized for bulk/classification, not reasoning-heavy coaching). Three locations must change.

**Why Gemini 3 Flash over 3.1 Flash Lite:**
- GPQA Diamond: 90.4% vs 86.9% (Lite) vs 82.8% (current 2.5 Flash)
- Improved tool calling with stricter validation (addresses current tool-use failures)
- Adjustable thinking levels (high for coaching, low for simple queries)
- Flash Lite has reported issues with early response truncation and refusing intrinsic knowledge when tools are supplied — exactly our current failure modes
- Cost: $0.50/$3.00 per 1M tokens (vs $0.30/$2.50 current) — pennies per conversation for substantially better reasoning

**File:** `apps/api/services/ai_coach.py`

### 5a: Class constant (search for `MODEL_DEFAULT =`)

```python
# BEFORE
MODEL_DEFAULT = "gemini-2.5-flash"      # Standard coaching (95%)

# AFTER
MODEL_DEFAULT = "gemini-3-flash-preview"  # Standard coaching (95%) — March 2026 upgrade
```

### 5b: First hardcoded call in `query_gemini` (search for `self.gemini_client.models.generate_content` — first occurrence, inside the initial send)

```python
# BEFORE
response = self.gemini_client.models.generate_content(
    model="gemini-2.5-flash",

# AFTER
response = self.gemini_client.models.generate_content(
    model=self.MODEL_DEFAULT,
```

### 5c: Second hardcoded call in `query_gemini` (search for `self.gemini_client.models.generate_content` — second occurrence, inside the tool-result loop)

```python
# BEFORE
response = self.gemini_client.models.generate_content(
    model="gemini-2.5-flash",

# AFTER
response = self.gemini_client.models.generate_content(
    model=self.MODEL_DEFAULT,
```

**Why use the constant instead of a new string:** Prevents this exact drift from happening again. The model string lives in one place.

### 5d: Update the cost calculation (search for `Gemini 2.5 Flash` in the cost tracking method)

```python
# BEFORE
# Gemini 2.5 Flash: $0.30/1M input, $2.50/1M output (Feb 2026)
cost_cents = int((input_tokens * 0.03 + output_tokens * 0.25) / 100)

# AFTER
# Gemini 3 Flash: $0.50/1M input, $3.00/1M output (Mar 2026)
cost_cents = int((input_tokens * 0.05 + output_tokens * 0.30) / 100)
```

### 5e: Update docstrings/comments that reference "2.5 Flash" (search for `2.5 Flash` or `Gemini 2.5`)

Update all references in `ai_coach.py` to say "Gemini 3 Flash" instead of "2.5 Flash". There are approximately 8 comment/docstring occurrences. Don't chase references in other files — those are for context, not correctness.

### 5f: Update the logger message (search for `Gemini 2.5 Flash initialized`)

```python
# BEFORE
logger.info("Gemini 2.5 Flash initialized for bulk coaching queries")

# AFTER
logger.info("Gemini 3 Flash initialized for coaching queries")
```

---

## What this does NOT change

- Standard user routing (still keyword + complexity gated)
- Budget caps for standard users (unchanged)
- Gemini prompt quality (separate audit: `docs/COACH_QUALITY_AUDIT.md`)
- Coach prompt improvements (separate audit)
- High-stakes model (still Opus 4.6)
- Standard model is now Gemini 3 Flash (upgraded from 2.5 Flash)
