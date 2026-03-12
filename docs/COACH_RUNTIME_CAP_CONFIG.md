# Coach Runtime Cap Config — Canonical Reference

**Last updated:** March 12, 2026  
**Applies to:** `apps/api/services/ai_coach.py` — premium Anthropic lane caps

---

## Active Values (env-driven hard caps)

| Env var | Default | Semantics |
|---|---|---|
| `COACH_MAX_OPUS_REQUESTS_PER_DAY` | `3` | Non-VIP premium Anthropic lane daily request cap |
| `COACH_MONTHLY_OPUS_TOKEN_BUDGET` | `50000` | Non-VIP premium Anthropic lane monthly token cap |
| `COACH_MAX_OPUS_REQUESTS_PER_DAY_VIP` | `15` | VIP hard daily request cap (not a multiplier) |
| `COACH_MONTHLY_OPUS_TOKEN_BUDGET_VIP` | `1000000` | VIP hard monthly token cap (not a multiplier) |
| `COACH_MAX_REQUESTS_PER_DAY` | `50` | Total daily cap (all lanes) |
| `COACH_MONTHLY_TOKEN_BUDGET` | `1000000` | Total monthly token cap |

---

## Rules that must not be regressed

1. **Founder is always uncapped.** `_is_founder()` short-circuits before any cap is checked. No request limit, no token limit. Do not add caps to the founder path.

2. **VIP uses hard caps, not multipliers.** The code reads `COACH_MAX_OPUS_REQUESTS_PER_DAY_VIP` and `COACH_MONTHLY_OPUS_TOKEN_BUDGET_VIP` directly. There is no `vip_multiplier` applied to non-VIP caps. Do not reintroduce multiplier logic.

3. **Premium lane column names.** `CoachUsage` schema retains `opus_requests_today` and `opus_tokens_*` column names for DB compatibility. The semantic meaning is "premium Anthropic lane" (now `claude-sonnet-4-6`, previously Opus). Do not add a migration to rename these columns.

4. **Non-VIP caps are separate.** `COACH_MAX_OPUS_REQUESTS_PER_DAY` (default 3) is the non-VIP cap and must stay independent of VIP values.

---

## How caps are applied in code

```python
# In check_budget() — apps/api/services/ai_coach.py
if self._is_founder(athlete_id):
    return True, "founder_bypass"          # ← uncapped always

if is_opus:
    max_opus_daily = (
        COACH_MAX_OPUS_REQUESTS_PER_DAY_VIP   # hard cap for VIP
        if is_vip
        else COACH_MAX_OPUS_REQUESTS_PER_DAY   # hard cap for non-VIP
    )
    max_opus_monthly = (
        COACH_MONTHLY_OPUS_TOKEN_BUDGET_VIP
        if is_vip
        else COACH_MONTHLY_OPUS_TOKEN_BUDGET
    )
```

---

## Builder addendum block (copy into any builder instruction that touches coach model routing or cap logic)

```markdown
## Runtime Config Addendum (Apply Before Build)

Premium lane caps are env-driven hard caps and must be preserved:

- `COACH_MAX_OPUS_REQUESTS_PER_DAY_VIP=15`
- `COACH_MONTHLY_OPUS_TOKEN_BUDGET_VIP=1000000`

Context:
- Founder remains uncapped via founder bypass.
- VIP uses hard caps above (no 10x multiplier behavior).
- Non-VIP premium caps remain unchanged.

Builder requirement:
- Do not reintroduce multiplier-based VIP logic.
- Keep these as env-driven hard caps unless explicitly instructed otherwise.
- Canonical reference: `docs/COACH_RUNTIME_CAP_CONFIG.md`
```

---

## Production verification (Mar 12, 2026)

Deployment:
- Commit: `9a82a0d`
- Command: `cd /opt/strideiq/repo && git pull origin main && docker compose -f docker-compose.prod.yml up -d --build`

Live runtime checks:
- `services.ai_coach` loaded from `/app/services/ai_coach.py`
- Live constants in `strideiq_api`:
  - `COACH_MAX_OPUS_REQUESTS_PER_DAY_VIP = 15`
  - `COACH_MONTHLY_OPUS_TOKEN_BUDGET_VIP = 1000000`
- Live `get_budget_status()` smoke check on production VIP athletes returns:
  - `opus_requests_limit_today = 15`
  - `opus_tokens_limit_this_month = 1000000`
