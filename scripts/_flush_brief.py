"""Flush briefing cache for founder and trigger regeneration."""
import redis
import os

r = redis.from_url(os.getenv("REDIS_URL", "redis://redis:6379/0"), decode_responses=True)

keys = r.keys("*briefing*4368ec7f*") + r.keys("*home_briefing*4368ec7f*")
for k in keys:
    r.delete(k)
    print(f"Deleted: {k}")
print(f"Total deleted: {len(keys)}")
