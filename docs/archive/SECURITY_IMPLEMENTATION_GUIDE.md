# Security Implementation Guide

**Purpose:** Step-by-step implementation instructions for each security fix.  
**Risk Level:** Each phase is designed to minimize site breakage.

---

## Phase 0: Critical Auth Fixes (LOW RISK)

These changes add authentication to previously unauthenticated endpoints. The frontend already sends Bearer tokens, so these should NOT break the site.

### 0.1 Add Auth to body_composition.py

**File:** `apps/api/routers/body_composition.py`

**Changes Required:**

1. Add import at top:
```python
from core.auth import get_current_user
```

2. Add `current_user` dependency to ALL endpoints:
```python
# Before:
def create_body_composition(body_comp: BodyCompositionCreate, db: Session = Depends(get_db)):

# After:
def create_body_composition(
    body_comp: BodyCompositionCreate,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db)
):
```

3. Replace athlete_id from request with current_user.id:
```python
# Before:
athlete = db.query(Athlete).filter(Athlete.id == body_comp.athlete_id).first()

# After:
# Use current_user.id instead of body_comp.athlete_id
db_entry = BodyComposition(
    athlete_id=current_user.id,  # From token, not request
    ...
)
```

4. Add ownership check for GET/PUT/DELETE by ID:
```python
entry = db.query(BodyComposition).filter(BodyComposition.id == id).first()
if not entry:
    raise HTTPException(status_code=404, detail="Entry not found")
if entry.athlete_id != current_user.id:
    raise HTTPException(status_code=403, detail="Access denied")
```

5. Filter list queries by current user:
```python
# Before:
query = db.query(BodyComposition).filter(BodyComposition.athlete_id == athlete_id)

# After:
query = db.query(BodyComposition).filter(BodyComposition.athlete_id == current_user.id)
```

**Test:** Run `pytest tests/test_security_auth_required.py::TestBodyCompositionAuthRequired -v`

---

### 0.2 Add Auth to work_pattern.py

**File:** `apps/api/routers/work_pattern.py`

Same pattern as 0.1:
1. Add `from core.auth import get_current_user`
2. Add `current_user: Athlete = Depends(get_current_user)` to all endpoints
3. Use `current_user.id` instead of request athlete_id
4. Add ownership checks for ID-based operations
5. Filter list queries by current_user.id

**Test:** Run `pytest tests/test_security_auth_required.py::TestWorkPatternAuthRequired -v`

---

### 0.3 Add Auth to nutrition.py

**File:** `apps/api/routers/nutrition.py`

Same pattern, BUT:
- Keep `/nutrition/parse/available` without auth (it's a capability check)
- `/nutrition/parse` already has auth (keep it)

Apply to:
- `POST /nutrition` 
- `GET /nutrition`
- `GET /nutrition/{id}`
- `PUT /nutrition/{id}`
- `DELETE /nutrition/{id}`

**Test:** Run `pytest tests/test_security_auth_required.py::TestNutritionAuthRequired -v`

---

### 0.4 Add Auth to feedback.py

**File:** `apps/api/routers/feedback.py`

1. Add auth import
2. Add `current_user` dependency to all endpoints
3. **IMPORTANT:** Remove `athlete_id` from URL path - use `current_user.id` instead

```python
# Before:
@router.get("/athletes/{athlete_id}/observe")
def observe_endpoint(athlete_id: UUID, ...):

# After:
@router.get("/athletes/me/observe")
def observe_endpoint(current_user: Athlete = Depends(get_current_user), ...):
    athlete_id = current_user.id
```

OR keep URL but verify ownership:
```python
@router.get("/athletes/{athlete_id}/observe")
def observe_endpoint(
    athlete_id: UUID,
    current_user: Athlete = Depends(get_current_user),
    ...
):
    if athlete_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
```

**Test:** Run `pytest tests/test_security_auth_required.py::TestFeedbackAuthRequired -v`

---

### 0.5 Fix Strava Token Encryption

**File:** `apps/api/services/strava_service.py`

**Line 439 - Current (VULNERABLE):**
```python
token = refresh_access_token(athlete.strava_refresh_token)
athlete.strava_access_token = token["access_token"]
```

**Fix:**
```python
from services.token_encryption import encrypt_token

token = refresh_access_token(athlete.strava_refresh_token)
athlete.strava_access_token = encrypt_token(token["access_token"])
```

**Test:** Verify Strava sync still works after token refresh.

---

### 0.6 Token Encryption Key Fail-Hard

**File:** `apps/api/services/token_encryption.py`

**Lines 27-35 - Current:**
```python
if not encryption_key:
    logger.warning("TOKEN_ENCRYPTION_KEY not set...")
    encryption_key = Fernet.generate_key().decode()
```

**Fix:**
```python
if not encryption_key:
    environment = os.getenv("ENVIRONMENT", "development")
    if environment == "production":
        raise RuntimeError(
            "TOKEN_ENCRYPTION_KEY must be set in production. "
            "Generate with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    logger.warning("TOKEN_ENCRYPTION_KEY not set. Generating temporary key (NOT FOR PRODUCTION)")
    encryption_key = Fernet.generate_key().decode()
```

**Pre-Deploy Check:** Verify `TOKEN_ENCRYPTION_KEY` is set in production environment.

---

## Phase 1: Critical Security Fixes (LOW-MEDIUM RISK)

### 1.1 Add Auth to v1.py mark-race/backfill

**File:** `apps/api/routers/v1.py`

**Lines 577-605:**
```python
@router.post("/activities/{activity_id}/mark-race")
def mark_activity_as_race(
    activity_id: UUID,
    current_user: Athlete = Depends(get_current_user),  # ADD
    is_race: bool = True,
    db: Session = Depends(get_db)
):
    activity = db.query(Activity).filter(Activity.id == activity_id).first()
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    if activity.athlete_id != current_user.id:  # ADD ownership check
        raise HTTPException(status_code=403, detail="Access denied")
    ...
```

Same pattern for `backfill_activity_splits`.

---

### 1.2 Make Strava Webhook Signature Mandatory

**File:** `apps/api/routers/strava_webhook.py`

**Lines 64-73 - Current:**
```python
if x_strava_signature:
    signature = x_strava_signature.replace("sha256=", "")
    if not verify_webhook_signature(body_str, signature):
        raise HTTPException(status_code=401, ...)
```

**Fix:**
```python
if not x_strava_signature:
    logger.warning("Strava webhook missing signature header")
    raise HTTPException(status_code=401, detail="Missing signature")

signature = x_strava_signature.replace("sha256=", "")
if not verify_webhook_signature(body_str, signature):
    logger.warning("Invalid Strava webhook signature")
    raise HTTPException(status_code=401, detail="Invalid signature")
```

**Risk:** If Strava's webhook format changes, this could reject valid webhooks. Monitor logs after deploy.

---

### 1.3 Add Auth to knowledge.py RPI Endpoints

**File:** `apps/api/routers/knowledge.py`

For RPI endpoints that accept `athlete_id`:
- If `athlete_id` is provided, require auth and verify ownership
- If `athlete_id` is not provided, return public RPI info (no auth needed)

```python
@router.get("/rpi/formula")
def get_rpi_formula(
    athlete_id: Optional[UUID] = None,
    current_user: Optional[Athlete] = Depends(get_optional_user),  # Optional auth
    db: Session = Depends(get_db)
):
    if athlete_id:
        if not current_user:
            raise HTTPException(status_code=401, detail="Authentication required")
        if athlete_id != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied")
        # Return athlete-specific RPI
    else:
        # Return generic RPI formula
```

---

### 1.4 Complete GDPR Deletion

**File:** `apps/api/routers/gdpr.py`

Add deletion for all 24 missing tables. Order matters due to foreign keys:

```python
# Add these deletions BEFORE deleting Athlete:

# Training Plans (cascade to workouts)
db.query(PlannedWorkout).filter(PlannedWorkout.athlete_id == athlete_id).delete()
db.query(PlanModificationLog).filter(PlanModificationLog.athlete_id == athlete_id).delete()
db.query(TrainingPlan).filter(TrainingPlan.athlete_id == athlete_id).delete()

# Performance data
db.query(PersonalBest).filter(PersonalBest.athlete_id == athlete_id).delete()
db.query(BestEffort).filter(BestEffort.athlete_id == athlete_id).delete()
db.query(AthleteRaceResultAnchor).filter(AthleteRaceResultAnchor.athlete_id == athlete_id).delete()

# Onboarding/Intake
db.query(IntakeQuestionnaire).filter(IntakeQuestionnaire.athlete_id == athlete_id).delete()
db.query(AthleteGoal).filter(AthleteGoal.athlete_id == athlete_id).delete()

# Calendar
db.query(CalendarNote).filter(CalendarNote.athlete_id == athlete_id).delete()
db.query(CalendarInsight).filter(CalendarInsight.athlete_id == athlete_id).delete()

# Coach interactions
db.query(CoachChat).filter(CoachChat.athlete_id == athlete_id).delete()
db.query(CoachActionProposal).filter(CoachActionProposal.athlete_id == athlete_id).delete()
db.query(CoachingRecommendation).filter(CoachingRecommendation.athlete_id == athlete_id).delete()
db.query(CoachIntentSnapshot).filter(CoachIntentSnapshot.athlete_id == athlete_id).delete()
db.query(CoachUsage).filter(CoachUsage.athlete_id == athlete_id).delete()

# Models/Learning
db.query(AthleteCalibratedModel).filter(AthleteCalibratedModel.athlete_id == athlete_id).delete()
db.query(AthleteWorkoutResponse).filter(AthleteWorkoutResponse.athlete_id == athlete_id).delete()
db.query(AthleteLearning).filter(AthleteLearning.athlete_id == athlete_id).delete()
db.query(AthleteTrainingPaceProfile).filter(AthleteTrainingPaceProfile.athlete_id == athlete_id).delete()

# Import/Sync
db.query(AthleteIngestionState).filter(AthleteIngestionState.athlete_id == athlete_id).delete()
db.query(AthleteDataImportJob).filter(AthleteDataImportJob.athlete_id == athlete_id).delete()

# Billing
db.query(Subscription).filter(Subscription.athlete_id == athlete_id).delete()
db.query(Purchase).filter(Purchase.athlete_id == athlete_id).delete()

# Audit
db.query(WorkoutSelectionAuditEvent).filter(WorkoutSelectionAuditEvent.athlete_id == athlete_id).delete()
```

---

## Phase 2: High Priority Fixes (MEDIUM RISK)

### 2.1 Escape SQL LIKE Metacharacters

Create a utility function:

**File:** `apps/api/core/utils.py` (new or existing)

```python
import re

def escape_like(pattern: str) -> str:
    """Escape SQL LIKE metacharacters (%, _, \\)."""
    return re.sub(r'([%_\\])', r'\\\1', pattern)
```

Apply to all ILIKE calls:
```python
from core.utils import escape_like

# Before:
query.filter(Athlete.email.ilike(f"%{search}%"))

# After:
query.filter(Athlete.email.ilike(f"%{escape_like(search)}%"))
```

---

### 2.2-2.8: See COMPREHENSIVE_SECURITY_PLAN.md for details

---

## Phase 3: Breaking Changes (HIGH RISK)

**WARNING:** These changes will affect all users. Deploy during low-traffic window.

### 3.1 Reduce JWT Expiration

**File:** `apps/api/core/security.py`

```python
# Before:
ACCESS_TOKEN_EXPIRE_MINUTES = 30 * 24 * 60  # 30 days

# After:
ACCESS_TOKEN_EXPIRE_MINUTES = 7 * 24 * 60  # 7 days (Phase 3)
# Future: 60 minutes with refresh tokens
```

**Impact:** All existing tokens older than 7 days will expire. Users will need to log in again.

**Mitigation:**
1. Deploy during low-traffic window
2. Consider sending email notice to active users
3. Monitor login rate after deploy

---

### 3.2 Infrastructure Changes

See `COMPREHENSIVE_SECURITY_PLAN.md` for Docker, SSL, and Redis auth changes.

---

## Testing Checklist

Before each deployment:

- [ ] All security tests pass (`pytest tests/test_security_*.py -v`)
- [ ] Existing tests pass (`pytest tests/ -v --ignore=tests/test_security_*.py`)
- [ ] Manual test: Login still works
- [ ] Manual test: Strava sync still works  
- [ ] Manual test: Can create/view activities
- [ ] Manual test: Check-in still works
- [ ] Manual test: Coach chat still works

After deployment:

- [ ] Monitor Sentry for new errors
- [ ] Check logs for 401/403 spikes
- [ ] Verify Strava webhooks still processing
- [ ] Test one full user flow (login → view dashboard → create check-in)

---

## Rollback Plan

If issues occur after deployment:

1. **Immediate:** Revert the commit and redeploy
   ```bash
   git revert HEAD
   git push origin main
   ```

2. **If auth breaks login:** Temporarily comment out new auth checks
   
3. **If Strava breaks:** Check webhook signature logic, may need to make optional again temporarily

4. **If tokens break:** Verify TOKEN_ENCRYPTION_KEY matches production value
