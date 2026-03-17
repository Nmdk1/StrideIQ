import sys
sys.path.insert(0, "/app")
from core.config import settings
from core.llm_client import resolve_briefing_model

founder = resolve_briefing_model(athlete_id="4368ec7f-c30d-45ff-a6ee-58db7716be24")
other = resolve_briefing_model(athlete_id="00000000-0000-0000-0000-000000000000")

print("CANARY_ENABLED:", settings.KIMI_CANARY_ENABLED)
print("CANARY_IDS:", settings.KIMI_CANARY_ATHLETE_IDS)
print("CANARY_MODEL:", settings.KIMI_CANARY_MODEL)
print("FOUNDER ->", founder)
print("OTHER   ->", other)

assert settings.KIMI_CANARY_ENABLED is True, "FAIL: canary not enabled"
assert "4368ec7f" in settings.KIMI_CANARY_ATHLETE_IDS, "FAIL: founder not in IDs"
assert founder == "kimi-k2-turbo-preview", f"FAIL: founder got {founder}"
assert other == "claude-sonnet-4-6", f"FAIL: other got {other}"
print("ALL ASSERTIONS PASSED")
