from core.config import settings
print("CANARY:", settings.KIMI_CANARY_ENABLED)
print("IDS:", settings.KIMI_CANARY_ATHLETE_IDS)
print("MODEL:", settings.KIMI_CANARY_MODEL)
from core.llm_client import resolve_briefing_model
founder = resolve_briefing_model(athlete_id="4368ec7f-c30d-45ff-a6ee-58db7716be24")
other = resolve_briefing_model(athlete_id="00000000-0000-0000-0000-000000000000")
print("FOUNDER MODEL:", founder)
print("OTHER MODEL:", other)
assert founder == "kimi-k2-turbo-preview", f"FAIL: expected kimi-k2-turbo-preview, got {founder}"
assert other == "claude-sonnet-4-6", f"FAIL: expected claude-sonnet-4-6, got {other}"
print("OK")
