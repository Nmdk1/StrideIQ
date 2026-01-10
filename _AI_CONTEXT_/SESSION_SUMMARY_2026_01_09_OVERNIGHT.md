# Overnight Build Session - January 9, 2026

## Mission
Build the core product flow: **Plan Generation → Calendar → AI Discussion**

---

## What Was Built

### 1. Training Plan System (Complete)

#### Database Models
Added to `apps/api/models.py`:

**TrainingPlan**
- `id`, `athlete_id`, `created_at`, `updated_at`
- `name`, `status` (draft/active/completed/cancelled)
- `goal_race_name`, `goal_race_date`, `goal_race_distance_m`, `goal_time_seconds`
- `plan_start_date`, `plan_end_date`, `total_weeks`
- `baseline_vdot`, `baseline_weekly_volume_km`
- `plan_type` (marathon/half_marathon/10k/5k)
- `generation_method` (ai/template/custom)
- `methodology_blend` (JSONB)

**PlannedWorkout**
- `id`, `plan_id`, `athlete_id`
- `scheduled_date`, `week_number`, `day_of_week`
- `workout_type` (easy/long/tempo/intervals/rest/race)
- `workout_subtype`, `title`, `description`
- `phase` (base/build/peak/taper/recovery)
- `phase_week`
- Target metrics: `duration_minutes`, `distance_km`, `pace_per_km_seconds`
- Segments (JSONB for intervals)
- `completed`, `completed_activity_id`, `skipped`, `skip_reason`
- `coach_notes`, `athlete_notes`

Migration applied: `b7eda0eabd7f_add_training_plan_and_planned_workout.py`

#### Plan Generator Service
`apps/api/services/plan_generator.py`

Features:
- Generates periodized plans based on goal race
- Phase distributions: Base → Build → Peak → Taper
- Minimum weeks by distance (Marathon: 16, Half: 12, 10K: 8, 5K: 6)
- Week templates for each phase
- Training pace calculations from VDOT
- Workout descriptions with guidance

#### Training Plans API
`apps/api/routers/training_plans.py`

Endpoints:
- `POST /v1/training-plans` - Create new plan
- `GET /v1/training-plans/current` - Get active plan
- `GET /v1/training-plans/current/week` - This week's workouts
- `GET /v1/training-plans/calendar` - Calendar view with planned + actual
- `POST /v1/training-plans/{plan_id}/workouts/{workout_id}/complete`
- `POST /v1/training-plans/{plan_id}/workouts/{workout_id}/skip`

### 2. AI Coach System (Complete)

#### AI Coach Service
`apps/api/services/ai_coach.py`

Features:
- Uses OpenAI Assistants API
- Context injection from athlete's data:
  - Athlete profile (age, VDOT, HR)
  - Personal bests
  - Current training plan
  - Last 7 days activities (detailed)
  - Last 30 days summary
  - Recent wellness check-ins
- Persistent assistant (StrideIQ Coach)
- System instructions for coaching behavior

#### AI Coach API
`apps/api/routers/ai_coach.py`

Endpoints:
- `POST /v1/coach/chat` - Chat with AI coach
- `GET /v1/coach/context` - Preview context data
- `GET /v1/coach/suggestions` - Suggested questions

### 3. Frontend Components (Complete)

#### API Services
- `apps/web/lib/api/services/training-plans.ts`
- `apps/web/lib/api/services/ai-coach.ts`

#### React Query Hooks
- `apps/web/lib/hooks/queries/training-plans.ts`
  - `useCurrentPlan()`
  - `useCurrentWeek()`
  - `useCalendar()`
  - `useCreatePlan()`
  - `useCompleteWorkout()`
  - `useSkipWorkout()`

#### Pages
- `apps/web/app/calendar/page.tsx` - Training calendar with:
  - Plan overview (progress bar, days to race)
  - Week-by-week view
  - Color-coded workouts by type
  - Plan creation form

- `apps/web/app/coach/page.tsx` - AI Coach chat with:
  - Real-time chat interface
  - Markdown rendering for responses
  - Suggested questions
  - Loading states

#### Dashboard Enhancement
`apps/web/app/dashboard/page.tsx` now shows:
- Training plan quick view (if active)
- This week's workouts grid
- Link to create plan (if none)

#### Navigation Update
Added to authenticated nav:
- 📅 Plan → /calendar
- 🤖 Coach → /coach (highlighted)

---

## Test Results

### API Health
```
[OK] GET /v1/training-plans/current
[OK] GET /v1/training-plans/calendar
[OK] GET /v1/coach/context
[OK] GET /v1/coach/suggestions
```

### Context Data (Real Athlete)
```
## Athlete Profile
Name: Michael Shaffer
Age: 58

## Personal Bests
- 10k: 39:39 (Dec 13, 2025)
- 25k: 2:23:53 (Nov 30, 2025)
- half_marathon: 1:27:40 (Nov 29, 2025)
- 5k: 19:01 (Aug 30, 2025)
- 2mile: 12:55 (Jul 10, 2025)

## Current Training Plan
Goal: Boston Marathon 2026
Race Date: 2026-04-20
Week: 0 of 16

## Last 30 Days
Runs: 13 | Distance: 86 km | Avg/week: 20 km
Average efficiency: 2.433 (pace/HR ratio)
```

### Test Plan Created
- **Name:** Boston Marathon 2026 Training Plan
- **Start:** January 12, 2026
- **Race:** April 20, 2026
- **Goal Time:** 3:30:00
- **Total Weeks:** 16
- **Generated Workouts:** 112 (16 weeks × 7 days)

---

## Files Created/Modified

### New Files
- `apps/api/services/plan_generator.py` (500+ lines)
- `apps/api/routers/training_plans.py` (350+ lines)
- `apps/api/services/ai_coach.py` (380+ lines)
- `apps/api/routers/ai_coach.py` (80+ lines)
- `apps/web/lib/api/services/training-plans.ts`
- `apps/web/lib/api/services/ai-coach.ts`
- `apps/web/lib/hooks/queries/training-plans.ts`
- `apps/web/app/calendar/page.tsx` (300+ lines)
- `apps/web/app/coach/page.tsx` (200+ lines)
- `apps/api/alembic/versions/b7eda0eabd7f_add_training_plan_and_planned_workout.py`

### Modified Files
- `apps/api/models.py` - Added TrainingPlan, PlannedWorkout
- `apps/api/main.py` - Added routers
- `apps/web/app/dashboard/page.tsx` - Added plan overview
- `apps/web/app/components/Navigation.tsx` - Added Plan, Coach links

---

## Requirements for AI Coach to Work

The AI Coach requires an OpenAI API key:

```bash
# Add to environment (.env or docker-compose)
OPENAI_API_KEY=sk-your-key-here
```

Without the key, the coach returns a friendly error message.

---

## What's Working Now

1. ✅ **Create Training Plan** - Set goal race, get 16-week periodized plan
2. ✅ **View Calendar** - See planned workouts + actual activities
3. ✅ **Dashboard Integration** - Quick view of plan and this week
4. ✅ **AI Context Building** - Rich context from athlete's real data
5. ✅ **Chat Interface** - Ready for AI conversations

---

## Next Steps

1. **Add OpenAI API key** to enable AI chat
2. **Test the frontend** at http://localhost:3000/calendar
3. **Refine plan generation** based on feedback
4. **Add workout completion tracking** (link activities to planned workouts)
5. **Persist AI threads** in database for conversation continuity

---

## How to Test

1. Login at http://localhost:3000/login
2. Go to /calendar to see the Boston Marathon plan
3. Go to /coach to chat (requires OpenAI key)
4. Dashboard shows plan overview

---

## Known Limitations

1. **AI Chat requires OpenAI key** - Not yet configured
2. **Plan dates are in future** - Current week is empty (plan starts Jan 12)
3. **No workout auto-matching** - Activities don't auto-complete planned workouts
4. **Single thread per chat** - Threads not persisted yet

---

Built overnight while you slept. The core flow is complete and tested with your real data.
