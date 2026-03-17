import os, urllib.request, json, time

KEY = os.environ.get("KIMI_API_KEY", "")
if not KEY:
    raise SystemExit("KIMI_API_KEY env var not set")
BASE = "https://api.moonshot.ai/v1/chat/completions"

models = [
    ("moonshot-v1-8k", 0.3),
    ("kimi-k2-turbo-preview", 0.6),
    ("kimi-k2.5", None),
]

for model, temp in models:
    try:
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": "Reply with one word: VERIFIED"}],
            "max_tokens": 20,
        }
        if temp is not None:
            payload["temperature"] = temp
        req = urllib.request.Request(
            BASE,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {KEY}"}
        )
        t0 = time.monotonic()
        resp = json.loads(urllib.request.urlopen(req, timeout=60).read())
        ms = round((time.monotonic() - t0) * 1000)
        text = resp.get("choices", [{}])[0].get("message", {}).get("content", "")[:60]
        print(f"{model}: {ms}ms | {repr(text.strip())}")
    except Exception as e:
        print(f"{model}: ERROR {type(e).__name__}: {e}")
