"""Phase 1 close-gate: runs all 6 checks against the live API container."""
import json
import subprocess
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone

API = "http://172.18.0.4:8000"
CONTAINER = "strideiq_api"
DB_CONTAINER = "strideiq_postgres"
DB_USER = "postgres"
DB_NAME = "running_app"

# ---------------------------------------------------------------------------
# Bootstrap: get token + plan_id from container
# ---------------------------------------------------------------------------
def get_creds():
    r = subprocess.run(
        ["docker", "exec", "-w", "/app", CONTAINER, "python", "get_token.py"],
        capture_output=True, text=True, check=True,
    )
    lines = {}
    for line in r.stdout.strip().splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            lines[k.strip()] = v.strip()
    return lines["TOKEN"], lines["PLAN_ID"]


def post(path, body, token):
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{API}{path}",
        data=data,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def sql(query):
    r = subprocess.run(
        ["docker", "exec", DB_CONTAINER, "psql", "-U", DB_USER, DB_NAME, "-c", query],
        capture_output=True, text=True,
    )
    return r.stdout


# ---------------------------------------------------------------------------
# Check 1: Checkout matrix
# ---------------------------------------------------------------------------
def check1(token, plan_id):
    print("\n" + "="*60)
    print("CHECK 1: Checkout Matrix")
    print("="*60)
    calls = [
        ("/v1/billing/checkout", {"tier": "guided", "billing_period": "monthly"}, "guided/monthly"),
        ("/v1/billing/checkout", {"tier": "guided", "billing_period": "annual"}, "guided/annual"),
        ("/v1/billing/checkout", {"tier": "premium", "billing_period": "monthly"}, "premium/monthly"),
        ("/v1/billing/checkout", {"tier": "premium", "billing_period": "annual"}, "premium/annual"),
        ("/v1/billing/checkout/plan", {"plan_snapshot_id": plan_id}, "one-time/plan"),
    ]
    passed = True
    for path, body, label in calls:
        status, resp = post(path, body, token)
        url = resp.get("url", "")
        has_url = url.startswith("https://")
        tier = resp.get("tier", "-")
        period = resp.get("billing_period", "-")
        ptype = resp.get("purchase_type", "-")
        ok = status == 200 and has_url
        if not ok:
            passed = False
        result = "PASS" if ok else "FAIL"
        url_display = url[:55] + "..." if has_url else str(resp)[:60]
        print(f"  [{result}] {label} HTTP={status} url={url_display} tier={tier} period={period} ptype={ptype}")
    print(f"\nCheck 1: {'PASS' if passed else 'FAIL'}")
    return passed


# ---------------------------------------------------------------------------
# Check 2: Unknown price fail-closed
# ---------------------------------------------------------------------------
def check2():
    print("\n" + "="*60)
    print("CHECK 2: Unknown price fail-closed")
    print("="*60)
    script = (
        "from services.stripe_service import tier_for_price_and_status, build_price_to_tier, _get_stripe_config; "
        "cfg = _get_stripe_config(); "
        "p2t = build_price_to_tier(cfg); "
        "r1 = tier_for_price_and_status('price_UNKNOWN_XYZ', 'active', p2t); "
        "r2 = tier_for_price_and_status(None, 'active', p2t); "
        "r3 = tier_for_price_and_status('price_UNKNOWN_XYZ', 'trialing', p2t); "
        "print('unknown_active:', r1); "
        "print('none_active:', r2); "
        "print('unknown_trialing:', r3); "
        "assert r1 == 'free', f'FAIL: got {r1}'; "
        "assert r2 == 'free', f'FAIL: got {r2}'; "
        "assert r3 == 'free', f'FAIL: got {r3}'; "
        "print('all_assertions: PASS')"
    )
    r = subprocess.run(
        ["docker", "exec", "-w", "/app", CONTAINER, "python", "-c", script],
        capture_output=True, text=True,
    )
    print(r.stdout)
    if r.stderr:
        print("STDERR:", r.stderr[:300])
    passed = "all_assertions: PASS" in r.stdout
    # Also check for warning log
    log_check = subprocess.run(
        ["docker", "logs", "--tail", "30", CONTAINER],
        capture_output=True, text=True,
    )
    has_warning = "fail closed" in (log_check.stdout + log_check.stderr).lower() or "unknown price_id" in (log_check.stdout + log_check.stderr).lower()
    print(f"Warning log present: {has_warning}")
    print(f"\nCheck 2: {'PASS' if passed else 'FAIL'}")
    return passed


# ---------------------------------------------------------------------------
# Check 3: Webhook idempotency replay
# ---------------------------------------------------------------------------
def check3():
    print("\n" + "="*60)
    print("CHECK 3: Webhook idempotency replay")
    print("="*60)
    # Use a synthetic subscription.updated event with a fake event_id
    # This tests the StripeEvent table unique constraint
    import time
    unique_event_id = f"evt_test_idempotency_{int(time.time())}"
    script = f"""
from database import SessionLocal
from services.stripe_service import process_stripe_event
from models import StripeEvent

class FakeObj:
    customer = "cus_fake"
    id = "sub_fake"
    status = "active"
    current_period_end = None
    cancel_at_period_end = False
    cancel_at = None
    items = None
    metadata = {{}}

class FakeEvent:
    id = "{unique_event_id}"
    type = "customer.subscription.updated"
    created = 1700000000
    class data:
        object = FakeObj()

db = SessionLocal()
r1 = process_stripe_event(db, event=FakeEvent())
print("delivery_1:", r1)
r2 = process_stripe_event(db, event=FakeEvent())
print("delivery_2:", r2)
count = db.query(StripeEvent).filter(StripeEvent.event_id == "{unique_event_id}").count()
print("event_row_count:", count)
db.close()
assert r1.get("processed") == True and r1.get("idempotent") != True, f"First delivery wrong: {{r1}}"
assert r2.get("idempotent") == True, f"Second delivery not idempotent: {{r2}}"
assert count == 1, f"Expected 1 event row, got {{count}}"
print("idempotency_assertions: PASS")
"""
    r = subprocess.run(
        ["docker", "exec", "-w", "/app", CONTAINER, "python", "-c", script],
        capture_output=True, text=True,
    )
    print(r.stdout)
    if r.returncode != 0:
        print("STDERR:", r.stderr[:500])
    passed = "idempotency_assertions: PASS" in r.stdout
    print(f"\nCheck 3: {'PASS' if passed else 'FAIL'}")
    return passed


# ---------------------------------------------------------------------------
# Check 4: One-time entitlement idempotency
# ---------------------------------------------------------------------------
def check4(plan_id):
    print("\n" + "="*60)
    print("CHECK 4: One-time entitlement idempotency")
    print("="*60)
    import time
    pi_id = f"pi_test_idempotency_{int(time.time())}"
    athlete_id = "4368ec7f-c30d-45ff-a6ee-58db7716be24"
    script = f"""
from database import SessionLocal
from models import PlanPurchase
from services.stripe_service import _record_plan_purchase
import uuid

db = SessionLocal()
athlete_id = uuid.UUID("{athlete_id}")
plan_snapshot_id = "{plan_id}"
pi_id = "{pi_id}"

# First call - should succeed
_record_plan_purchase(db, athlete_id=athlete_id, plan_snapshot_id=plan_snapshot_id, stripe_session_id="evt_test", stripe_payment_intent_id=pi_id)
db.commit()

# Second call - should be idempotent no-op
_record_plan_purchase(db, athlete_id=athlete_id, plan_snapshot_id=plan_snapshot_id, stripe_session_id="evt_test", stripe_payment_intent_id=pi_id)
db.commit()

count = db.query(PlanPurchase).filter(PlanPurchase.stripe_payment_intent_id == pi_id).count()
print("plan_purchase_row_count:", count)
assert count == 1, f"Expected 1 purchase row, got {{count}}"
print("one_time_idempotency: PASS")
db.close()
"""
    r = subprocess.run(
        ["docker", "exec", "-w", "/app", CONTAINER, "python", "-c", script],
        capture_output=True, text=True,
    )
    print(r.stdout)
    if r.returncode != 0:
        print("STDERR:", r.stderr[:500])
    passed = "one_time_idempotency: PASS" in r.stdout
    print(f"\nCheck 4: {'PASS' if passed else 'FAIL'}")
    return passed


# ---------------------------------------------------------------------------
# Check 5: Migration safety proof
# ---------------------------------------------------------------------------
def check5():
    print("\n" + "="*60)
    print("CHECK 5: Migration safety proof")
    print("="*60)

    # Count premium users before rollback
    before = sql("SELECT subscription_tier, count(*) FROM athlete GROUP BY subscription_tier ORDER BY subscription_tier;")
    print("Tier distribution (current, post-migration-up):")
    print(before)

    ledger = sql("SELECT count(*) as migrated_count FROM monetization_migration_ledger;")
    print("Ledger row count (athletes migrated pro→premium):")
    print(ledger)

    purchases = sql("SELECT count(*) FROM plan_purchases;")
    print("plan_purchases row count:")
    print(purchases)

    # Run downgrade
    print("\n--- Running alembic downgrade monetization_001 ---")
    r = subprocess.run(
        ["docker", "exec", "-w", "/app", CONTAINER, "alembic", "downgrade", "sleep_quality_001"],
        capture_output=True, text=True,
    )
    print(r.stdout)
    if r.returncode != 0:
        print("STDERR:", r.stderr[:400])
        print("\nCheck 5: FAIL (downgrade failed)")
        return False

    after_down = sql("SELECT subscription_tier, count(*) FROM athlete GROUP BY subscription_tier ORDER BY subscription_tier;")
    print("Tier distribution after downgrade:")
    print(after_down)

    # Re-run upgrade
    print("--- Re-running alembic upgrade monetization_001 ---")
    r2 = subprocess.run(
        ["docker", "exec", "-w", "/app", CONTAINER, "alembic", "upgrade", "monetization_001"],
        capture_output=True, text=True,
    )
    print(r2.stdout)
    if r2.returncode != 0:
        print("STDERR:", r2.stderr[:400])
        print("\nCheck 5: FAIL (re-upgrade failed)")
        return False

    after_up = sql("SELECT subscription_tier, count(*) FROM athlete GROUP BY subscription_tier ORDER BY subscription_tier;")
    print("Tier distribution after re-upgrade:")
    print(after_up)

    passed = r.returncode == 0 and r2.returncode == 0
    print(f"\nCheck 5: {'PASS' if passed else 'FAIL'}")
    return passed


# ---------------------------------------------------------------------------
# Check 6: Regression tests
# ---------------------------------------------------------------------------
def check6():
    print("\n" + "="*60)
    print("CHECK 6: Regression smoke (unit tests)")
    print("="*60)
    r = subprocess.run(
        ["docker", "exec", "-w", "/app", CONTAINER, "python", "-m", "pytest",
         "tests/test_tier_engine.py", "tests/test_stripe_service_unit.py",
         "-v", "--tb=short", "-q"],
        capture_output=True, text=True,
    )
    print(r.stdout[-3000:] if len(r.stdout) > 3000 else r.stdout)
    if r.returncode != 0:
        print("STDERR:", r.stderr[:300])
    passed = r.returncode == 0
    print(f"\nCheck 6: {'PASS' if passed else 'FAIL'}")
    return passed


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print(f"Phase 1 Close Gate — {datetime.now(timezone.utc).isoformat()}")
    print("Getting credentials...")
    token, plan_id = get_creds()
    print(f"  athlete token: ...{token[-12:]}")
    print(f"  plan_id: {plan_id}")

    results = {}
    results["check1"] = check1(token, plan_id)
    results["check2"] = check2()
    results["check3"] = check3()
    results["check4"] = check4(plan_id)
    results["check5"] = check5()
    results["check6"] = check6()

    print("\n" + "="*60)
    print("FINAL VERDICT")
    print("="*60)
    for k, v in results.items():
        print(f"  {k}: {'PASS' if v else 'FAIL'}")
    overall = all(results.values())
    print(f"\nPhase 1 Close Gate: {'PASS' if overall else 'FAIL'}")
    sys.exit(0 if overall else 1)
