"""
Calendar API Router

The calendar is the central UI hub for StrideIQ subscribers.
Everything flows through it: plans, activities, insights, notes, coach chat.

Endpoints:
- GET /calendar - Get merged plan + actual view for date range
- GET /calendar/{date} - Get full day detail
- POST /calendar/{date}/notes - Add note to a day
- GET /calendar/week/{week_number} - Get week view with summary
- POST /calendar/coach - Send message to GPT coach
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from datetime import date, datetime, timedelta
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel

from core.database import get_db
from core.auth import get_current_user
from models import (
    Athlete, Activity, TrainingPlan, PlannedWorkout,
    CalendarNote, CoachChat, CalendarInsight, ActivityFeedback
)

router = APIRouter(prefix="/calendar", tags=["Calendar"])


# =============================================================================
# SCHEMAS
# =============================================================================

class CalendarNoteCreate(BaseModel):
    note_type: str  # 'pre_workout', 'post_workout', 'free_text', 'voice_memo'
    structured_data: Optional[dict] = None
    text_content: Optional[str] = None
    activity_id: Optional[UUID] = None


class CalendarNoteResponse(BaseModel):
    id: UUID
    note_date: date
    note_type: str
    structured_data: Optional[dict] = None
    text_content: Optional[str] = None
    activity_id: Optional[UUID] = None
    created_at: datetime

    class Config:
        from_attributes = True


class PlannedWorkoutResponse(BaseModel):
    id: UUID
    scheduled_date: date
    workout_type: str
    workout_subtype: Optional[str] = None
    title: str
    description: Optional[str] = None
    phase: str
    target_distance_km: Optional[float] = None
    target_duration_minutes: Optional[int] = None
    segments: Optional[list] = None  # List of workout segments
    completed: bool
    skipped: bool
    coach_notes: Optional[str] = None  # Pace description or guidance
    
    # Option A/B support
    has_option_b: bool = False
    option_b_title: Optional[str] = None
    option_b_description: Optional[str] = None
    option_b_segments: Optional[list] = None  # List of workout segments for option B
    selected_option: str = "A"  # Which option athlete has selected

    class Config:
        from_attributes = True


class ActivitySummary(BaseModel):
    id: UUID
    name: Optional[str] = None
    start_time: datetime
    distance_m: Optional[int] = None
    duration_s: Optional[int] = None
    avg_hr: Optional[int] = None
    workout_type: Optional[str] = None
    intensity_score: Optional[float] = None

    class Config:
        from_attributes = True


class InsightResponse(BaseModel):
    id: UUID
    insight_type: str
    priority: int
    title: str
    content: str
    activity_id: Optional[UUID] = None

    class Config:
        from_attributes = True


class InlineInsight(BaseModel):
    """Single inline insight for calendar display - one per day max."""
    metric: str  # 'efficiency', 'hr', 'pace', 'drift', 'consistency'
    value: str  # Human-readable value
    delta: Optional[float] = None  # % change vs baseline (if applicable)
    sentiment: str = 'neutral'  # 'positive', 'negative', 'neutral'


class CalendarDayResponse(BaseModel):
    date: date
    day_of_week: int  # 0=Monday, 6=Sunday
    day_name: str
    
    # Plan data
    planned_workout: Optional[PlannedWorkoutResponse] = None
    
    # Actual data
    activities: List[ActivitySummary] = []
    
    # Status: 'future', 'completed', 'modified', 'missed', 'rest'
    status: str
    
    # Notes and insights
    notes: List[CalendarNoteResponse] = []
    insights: List[InsightResponse] = []
    
    # Inline insight - single key metric for this day (for calendar cell display)
    inline_insight: Optional[InlineInsight] = None
    
    # Summary metrics for the day
    total_distance_m: int = 0
    total_duration_s: int = 0


class WeekSummaryResponse(BaseModel):
    week_number: int
    phase: Optional[str] = None
    phase_week: Optional[int] = None
    
    # Volume
    planned_miles: float
    completed_miles: float
    
    # Sessions
    quality_sessions_planned: int
    quality_sessions_completed: int
    long_run_planned_miles: Optional[float] = None
    long_run_completed_miles: Optional[float] = None
    
    # Focus text
    focus: Optional[str] = None
    
    # Days
    days: List[CalendarDayResponse]


class CalendarRangeResponse(BaseModel):
    start_date: date
    end_date: date
    
    # Active plan info
    active_plan: Optional[dict] = None
    current_week: Optional[int] = None
    current_phase: Optional[str] = None
    
    # Days in range
    days: List[CalendarDayResponse]
    
    # Week summaries
    week_summaries: List[WeekSummaryResponse] = []


class CoachMessageRequest(BaseModel):
    message: str
    context_type: str = "open"  # 'day', 'week', 'build', 'open'
    context_date: Optional[date] = None
    context_week: Optional[int] = None
    chat_id: Optional[UUID] = None  # Continue existing chat


class CoachMessageResponse(BaseModel):
    chat_id: UUID
    response: str
    context_type: str


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_day_status(planned: Optional[PlannedWorkout], activities: List[Activity], day_date: date) -> str:
    """Determine the status of a calendar day."""
    today = date.today()
    
    if day_date > today:
        return "future"
    
    if not planned:
        if activities:
            return "completed"  # Unplanned activity
        return "rest"
    
    if planned.workout_type == "rest" or planned.workout_type == "gym":
        return "rest"
    
    if planned.completed or planned.completed_activity_id:
        return "completed"
    
    if planned.skipped:
        return "missed"
    
    if activities:
        # Check if activity matches plan (rough match)
        total_distance = sum(a.distance_m or 0 for a in activities)
        planned_distance = (planned.target_distance_km or 0) * 1000
        
        if planned_distance > 0:
            ratio = total_distance / planned_distance
            if 0.8 <= ratio <= 1.2:
                return "completed"
            else:
                return "modified"
        return "completed"
    
    if day_date < today:
        return "missed"
    
    return "future"


def get_day_name(day_date: date) -> str:
    """Get day name from date."""
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    return days[day_date.weekday()]


def meters_to_miles(meters: int) -> float:
    """Convert meters to miles."""
    return round(meters / 1609.344, 1)


def generate_inline_insight(activities: List[Activity], planned: Optional[PlannedWorkout]) -> Optional[InlineInsight]:
    """
    Generate a single inline insight for a calendar day.
    
    Priority:
    1. Efficiency delta (if available)
    2. HR zone indicator
    3. Pace consistency
    
    Tone: Data speaks. No praise.
    """
    if not activities:
        return None
    
    # Use first/primary activity
    activity = activities[0]
    
    # Check for efficiency score (stored in activity or calculated)
    if hasattr(activity, 'efficiency_factor') and activity.efficiency_factor:
        # Would need baseline comparison - placeholder
        pass
    
    # HR-based insight
    if activity.avg_hr:
        if activity.avg_hr < 135:
            return InlineInsight(
                metric='hr',
                value=f'HR {activity.avg_hr}',
                sentiment='positive'
            )
        elif activity.avg_hr > 165:
            return InlineInsight(
                metric='hr',
                value=f'HR {activity.avg_hr}',
                sentiment='negative'
            )
    
    # Pace-based insight
    if activity.distance_m and activity.duration_s and activity.distance_m > 0:
        pace_per_mile = activity.duration_s / (activity.distance_m / 1609.344)
        mins = int(pace_per_mile // 60)
        secs = int(pace_per_mile % 60)
        pace_str = f'{mins}:{secs:02d}'
        
        # Compare to planned pace if available
        if planned and planned.workout_type:
            wt = planned.workout_type
            if 'easy' in wt or 'recovery' in wt:
                # Easy pace check - should be slower than 8:00 for most
                if pace_per_mile > 480:  # > 8:00/mi
                    return InlineInsight(
                        metric='pace',
                        value=f'{pace_str}/mi',
                        sentiment='positive'
                    )
            elif 'threshold' in wt or 'tempo' in wt:
                return InlineInsight(
                    metric='pace',
                    value=f'{pace_str}/mi',
                    sentiment='neutral'
                )
    
    # Default: just show distance completed
    if activity.distance_m:
        miles = round(activity.distance_m / 1609.344, 1)
        return InlineInsight(
            metric='distance',
            value=f'{miles}mi',
            sentiment='neutral'
        )
    
    return None


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.get("", response_model=CalendarRangeResponse)
def get_calendar(
    start_date: date = Query(default=None, description="Start date (defaults to start of current month)"),
    end_date: date = Query(default=None, description="End date (defaults to end of current month)"),
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get calendar data for a date range.
    
    Returns merged view of:
    - Planned workouts (from active training plan)
    - Actual activities (synced from Strava/Garmin)
    - Notes
    - Insights
    """
    # Default to current month
    if not start_date:
        today = date.today()
        start_date = today.replace(day=1)
    if not end_date:
        # End of month
        next_month = start_date.replace(day=28) + timedelta(days=4)
        end_date = next_month.replace(day=1) - timedelta(days=1)
    
    # Get active training plan
    active_plan = db.query(TrainingPlan).filter(
        TrainingPlan.athlete_id == current_user.id,
        TrainingPlan.status == "active"
    ).first()
    
    # Get planned workouts in range
    planned_workouts = {}
    current_week = None
    current_phase = None
    
    if active_plan:
        workouts = db.query(PlannedWorkout).filter(
            PlannedWorkout.plan_id == active_plan.id,
            PlannedWorkout.scheduled_date >= start_date,
            PlannedWorkout.scheduled_date <= end_date
        ).all()
        
        for w in workouts:
            planned_workouts[w.scheduled_date] = w
            
            # Determine current week/phase based on today
            if w.scheduled_date == date.today():
                current_week = w.week_number
                current_phase = w.phase
        
        # If current_week not set (no workout today), calculate from plan dates
        if current_week is None and active_plan.plan_start_date:
            today = date.today()
            if today < active_plan.plan_start_date:
                # Plan hasn't started yet - show week 1
                current_week = 1
                # Get phase from first workout
                first_workout = db.query(PlannedWorkout).filter(
                    PlannedWorkout.plan_id == active_plan.id
                ).order_by(PlannedWorkout.scheduled_date).first()
                if first_workout:
                    current_phase = first_workout.phase
            elif today <= (active_plan.plan_end_date or today):
                # Plan is in progress - calculate week from start date
                days_from_start = (today - active_plan.plan_start_date).days
                current_week = (days_from_start // 7) + 1
                # Get phase from nearest workout in this week
                nearest = db.query(PlannedWorkout).filter(
                    PlannedWorkout.plan_id == active_plan.id,
                    PlannedWorkout.week_number == current_week
                ).first()
                if nearest:
                    current_phase = nearest.phase
    
    # Get activities in range
    activities_by_date = {}
    activities = db.query(Activity).filter(
        Activity.athlete_id == current_user.id,
        func.date(Activity.start_time) >= start_date,
        func.date(Activity.start_time) <= end_date
    ).order_by(Activity.start_time).all()
    
    for a in activities:
        activity_date = a.start_time.date()
        if activity_date not in activities_by_date:
            activities_by_date[activity_date] = []
        activities_by_date[activity_date].append(a)
    
    # Get notes in range
    notes_by_date = {}
    notes = db.query(CalendarNote).filter(
        CalendarNote.athlete_id == current_user.id,
        CalendarNote.note_date >= start_date,
        CalendarNote.note_date <= end_date
    ).all()
    
    for n in notes:
        if n.note_date not in notes_by_date:
            notes_by_date[n.note_date] = []
        notes_by_date[n.note_date].append(n)
    
    # Get insights in range
    insights_by_date = {}
    insights = db.query(CalendarInsight).filter(
        CalendarInsight.athlete_id == current_user.id,
        CalendarInsight.insight_date >= start_date,
        CalendarInsight.insight_date <= end_date,
        CalendarInsight.is_dismissed == False
    ).order_by(CalendarInsight.priority.desc()).all()
    
    for i in insights:
        if i.insight_date not in insights_by_date:
            insights_by_date[i.insight_date] = []
        insights_by_date[i.insight_date].append(i)
    
    # Build calendar days
    days = []
    current = start_date
    while current <= end_date:
        planned = planned_workouts.get(current)
        day_activities = activities_by_date.get(current, [])
        day_notes = notes_by_date.get(current, [])
        day_insights = insights_by_date.get(current, [])
        
        status = get_day_status(planned, day_activities, current)
        
        total_distance = sum(a.distance_m or 0 for a in day_activities)
        total_duration = sum(a.duration_s or 0 for a in day_activities)
        
        # Generate inline insight for completed days
        inline_insight = None
        if day_activities and status in ('completed', 'modified'):
            inline_insight = generate_inline_insight(day_activities, planned)
        
        day_response = CalendarDayResponse(
            date=current,
            day_of_week=current.weekday(),
            day_name=get_day_name(current),
            planned_workout=PlannedWorkoutResponse.model_validate(planned) if planned else None,
            activities=[ActivitySummary.model_validate(a) for a in day_activities],
            status=status,
            notes=[CalendarNoteResponse.model_validate(n) for n in day_notes],
            insights=[InsightResponse.model_validate(i) for i in day_insights],
            inline_insight=inline_insight,
            total_distance_m=total_distance,
            total_duration_s=total_duration
        )
        days.append(day_response)
        current += timedelta(days=1)
    
    # Build week summaries
    week_summaries = []
    if active_plan:
        # Group days by week number
        weeks = {}
        for day in days:
            if day.planned_workout:
                week_num = day.planned_workout.week_number if hasattr(day.planned_workout, 'week_number') else None
                if week_num:
                    if week_num not in weeks:
                        weeks[week_num] = {"days": [], "phase": day.planned_workout.phase}
                    weeks[week_num]["days"].append(day)
        
        for week_num, week_data in sorted(weeks.items()):
            week_days = week_data["days"]
            
            planned_miles = sum(
                (d.planned_workout.target_distance_km or 0) * 0.621371
                for d in week_days if d.planned_workout
            )
            completed_miles = sum(
                meters_to_miles(d.total_distance_m)
                for d in week_days
            )
            
            quality_planned = sum(
                1 for d in week_days
                if d.planned_workout and d.planned_workout.workout_type in ['threshold', 'intervals', 'tempo', 'long_mp']
            )
            quality_completed = sum(
                1 for d in week_days
                if d.status == "completed" and d.planned_workout and d.planned_workout.workout_type in ['threshold', 'intervals', 'tempo', 'long_mp']
            )
            
            week_summaries.append(WeekSummaryResponse(
                week_number=week_num,
                phase=week_data["phase"],
                planned_miles=round(planned_miles, 1),
                completed_miles=round(completed_miles, 1),
                quality_sessions_planned=quality_planned,
                quality_sessions_completed=quality_completed,
                days=week_days
            ))
    
    return CalendarRangeResponse(
        start_date=start_date,
        end_date=end_date,
        active_plan={
            "id": str(active_plan.id),
            "name": active_plan.name,
            "goal_race_name": active_plan.goal_race_name,
            "goal_race_date": active_plan.goal_race_date.isoformat() if active_plan.goal_race_date else None,
            "total_weeks": active_plan.total_weeks
        } if active_plan else None,
        current_week=current_week,
        current_phase=current_phase,
        days=days,
        week_summaries=week_summaries
    )


@router.get("/{calendar_date}", response_model=CalendarDayResponse)
def get_calendar_day(
    calendar_date: date,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get full detail for a specific calendar day.
    
    Returns:
    - Planned workout with structure
    - Actual activities with analysis
    - All notes
    - All insights
    """
    # Get active plan and planned workout
    active_plan = db.query(TrainingPlan).filter(
        TrainingPlan.athlete_id == current_user.id,
        TrainingPlan.status == "active"
    ).first()
    
    planned = None
    if active_plan:
        planned = db.query(PlannedWorkout).filter(
            PlannedWorkout.plan_id == active_plan.id,
            PlannedWorkout.scheduled_date == calendar_date
        ).first()
    
    # Get activities for this day
    activities = db.query(Activity).filter(
        Activity.athlete_id == current_user.id,
        func.date(Activity.start_time) == calendar_date
    ).order_by(Activity.start_time).all()
    
    # Get notes
    notes = db.query(CalendarNote).filter(
        CalendarNote.athlete_id == current_user.id,
        CalendarNote.note_date == calendar_date
    ).order_by(CalendarNote.created_at).all()
    
    # Get insights
    insights = db.query(CalendarInsight).filter(
        CalendarInsight.athlete_id == current_user.id,
        CalendarInsight.insight_date == calendar_date,
        CalendarInsight.is_dismissed == False
    ).order_by(CalendarInsight.priority.desc()).all()
    
    status = get_day_status(planned, activities, calendar_date)
    total_distance = sum(a.distance_m or 0 for a in activities)
    total_duration = sum(a.duration_s or 0 for a in activities)
    
    return CalendarDayResponse(
        date=calendar_date,
        day_of_week=calendar_date.weekday(),
        day_name=get_day_name(calendar_date),
        planned_workout=PlannedWorkoutResponse.model_validate(planned) if planned else None,
        activities=[ActivitySummary.model_validate(a) for a in activities],
        status=status,
        notes=[CalendarNoteResponse.model_validate(n) for n in notes],
        insights=[InsightResponse.model_validate(i) for i in insights],
        total_distance_m=total_distance,
        total_duration_s=total_duration
    )


@router.post("/{calendar_date}/notes", response_model=CalendarNoteResponse)
def add_calendar_note(
    calendar_date: date,
    note: CalendarNoteCreate,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Add a note to a calendar day.
    
    Note types:
    - pre_workout: Before the run (structured: sleep, energy, stress, weather)
    - post_workout: After the run (structured: feel, pain, fueling, mental)
    - free_text: General notes
    - voice_memo: Transcribed voice notes
    """
    db_note = CalendarNote(
        athlete_id=current_user.id,
        note_date=calendar_date,
        note_type=note.note_type,
        structured_data=note.structured_data,
        text_content=note.text_content,
        activity_id=note.activity_id
    )
    
    db.add(db_note)
    db.commit()
    db.refresh(db_note)
    
    return CalendarNoteResponse.model_validate(db_note)


@router.delete("/{calendar_date}/notes/{note_id}")
def delete_calendar_note(
    calendar_date: date,
    note_id: UUID,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a calendar note."""
    note = db.query(CalendarNote).filter(
        CalendarNote.id == note_id,
        CalendarNote.athlete_id == current_user.id
    ).first()
    
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    
    db.delete(note)
    db.commit()
    
    return {"status": "deleted"}


@router.post("/coach", response_model=CoachMessageResponse)
def send_coach_message(
    request: CoachMessageRequest,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Send a message to the GPT coach.
    
    Context types:
    - day: Asking about a specific day's workout
    - week: Asking about the current/upcoming week
    - build: Asking about the overall training build
    - open: General question
    
    The coach receives full context injection based on context type.
    """
    # Get or create chat session
    if request.chat_id:
        chat = db.query(CoachChat).filter(
            CoachChat.id == request.chat_id,
            CoachChat.athlete_id == current_user.id
        ).first()
        if not chat:
            raise HTTPException(status_code=404, detail="Chat session not found")
    else:
        chat = CoachChat(
            athlete_id=current_user.id,
            context_type=request.context_type,
            context_date=request.context_date,
            context_week=request.context_week,
            messages=[]
        )
        db.add(chat)
        db.commit()
        db.refresh(chat)
    
    # Add user message
    messages = chat.messages or []
    messages.append({
        "role": "user",
        "content": request.message,
        "timestamp": datetime.utcnow().isoformat()
    })
    
    # Build context for GPT
    context = _build_coach_context(
        db=db,
        athlete=current_user,
        context_type=request.context_type,
        context_date=request.context_date,
        context_week=request.context_week
    )
    
    # Generate coach response (placeholder - integrate with actual GPT)
    coach_response = _generate_coach_response(
        message=request.message,
        context=context,
        history=messages[:-1]  # Previous messages
    )
    
    # Add coach response
    messages.append({
        "role": "coach",
        "content": coach_response,
        "timestamp": datetime.utcnow().isoformat()
    })
    
    # Update chat
    chat.messages = messages
    chat.updated_at = datetime.utcnow()
    db.commit()
    
    return CoachMessageResponse(
        chat_id=chat.id,
        response=coach_response,
        context_type=request.context_type
    )


def _build_coach_context(
    db: Session,
    athlete: Athlete,
    context_type: str,
    context_date: Optional[date] = None,
    context_week: Optional[int] = None
) -> dict:
    """Build context for GPT coach based on context type."""
    context = {
        "athlete": {
            "display_name": athlete.display_name,
            "subscription_tier": athlete.subscription_tier,
            "vdot": athlete.vdot,
            "max_hr": athlete.max_hr,
            "threshold_pace_per_km": athlete.threshold_pace_per_km
        }
    }
    
    # Get active plan
    active_plan = db.query(TrainingPlan).filter(
        TrainingPlan.athlete_id == athlete.id,
        TrainingPlan.status == "active"
    ).first()
    
    if active_plan:
        context["active_plan"] = {
            "name": active_plan.name,
            "goal_race_name": active_plan.goal_race_name,
            "goal_race_date": active_plan.goal_race_date.isoformat() if active_plan.goal_race_date else None,
            "goal_time_seconds": active_plan.goal_time_seconds,
            "total_weeks": active_plan.total_weeks
        }
    
    if context_type == "day" and context_date:
        # Get specific day context
        planned = None
        if active_plan:
            planned = db.query(PlannedWorkout).filter(
                PlannedWorkout.plan_id == active_plan.id,
                PlannedWorkout.scheduled_date == context_date
            ).first()
        
        activities = db.query(Activity).filter(
            Activity.athlete_id == athlete.id,
            func.date(Activity.start_time) == context_date
        ).all()
        
        context["day"] = {
            "date": context_date.isoformat(),
            "planned_workout": {
                "type": planned.workout_type,
                "title": planned.title,
                "description": planned.description,
                "target_distance_km": planned.target_distance_km,
                "segments": planned.segments
            } if planned else None,
            "activities": [
                {
                    "distance_m": a.distance_m,
                    "duration_s": a.duration_s,
                    "avg_hr": a.avg_hr,
                    "workout_type": a.workout_type
                } for a in activities
            ]
        }
    
    # Get recent workouts for context
    recent = db.query(Activity).filter(
        Activity.athlete_id == athlete.id
    ).order_by(Activity.start_time.desc()).limit(7).all()
    
    context["recent_workouts"] = [
        {
            "date": a.start_time.date().isoformat(),
            "distance_m": a.distance_m,
            "workout_type": a.workout_type,
            "avg_hr": a.avg_hr
        } for a in recent
    ]
    
    return context


def _generate_coach_response(message: str, context: dict, history: list) -> str:
    """
    Generate coach response.
    
    TODO: Integrate with actual GPT API with proper prompt engineering.
    For now, returns a placeholder response.
    """
    # Placeholder - will be replaced with actual GPT integration
    athlete_name = context.get("athlete", {}).get("display_name", "there")
    
    if "ready" in message.lower():
        return f"Based on your recent training, you're tracking well. Your consistency is building the foundation for a strong performance. Trust the work you've put in."
    
    if "pace" in message.lower():
        return f"For your current fitness level, focus on effort over pace. Easy runs should feel conversational - if you can't talk, you're too fast. Save the speed for the quality sessions."
    
    if "tired" in message.lower() or "fatigue" in message.lower():
        return f"Fatigue is expected during a build phase. The key question: is it productive fatigue (from training) or accumulated fatigue (needs attention)? How's your sleep been? Any unusual soreness?"
    
    return f"I see your question about your training. Based on your recent workouts and current phase, let me help you think through this. What specific aspect would you like to explore further?"


@router.get("/week/{week_number}", response_model=WeekSummaryResponse)
def get_calendar_week(
    week_number: int,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get detailed view of a specific training week."""
    # Get active plan
    active_plan = db.query(TrainingPlan).filter(
        TrainingPlan.athlete_id == current_user.id,
        TrainingPlan.status == "active"
    ).first()
    
    if not active_plan:
        raise HTTPException(status_code=404, detail="No active training plan")
    
    # Get planned workouts for this week
    planned_workouts = db.query(PlannedWorkout).filter(
        PlannedWorkout.plan_id == active_plan.id,
        PlannedWorkout.week_number == week_number
    ).order_by(PlannedWorkout.scheduled_date).all()
    
    if not planned_workouts:
        raise HTTPException(status_code=404, detail=f"Week {week_number} not found in plan")
    
    # Get date range for the week
    start_date = min(w.scheduled_date for w in planned_workouts)
    end_date = max(w.scheduled_date for w in planned_workouts)
    
    # Get activities for the week
    activities = db.query(Activity).filter(
        Activity.athlete_id == current_user.id,
        func.date(Activity.start_time) >= start_date,
        func.date(Activity.start_time) <= end_date
    ).all()
    
    activities_by_date = {}
    for a in activities:
        d = a.start_time.date()
        if d not in activities_by_date:
            activities_by_date[d] = []
        activities_by_date[d].append(a)
    
    # Build day responses
    days = []
    for planned in planned_workouts:
        day_activities = activities_by_date.get(planned.scheduled_date, [])
        status = get_day_status(planned, day_activities, planned.scheduled_date)
        
        total_distance = sum(a.distance_m or 0 for a in day_activities)
        total_duration = sum(a.duration_s or 0 for a in day_activities)
        
        days.append(CalendarDayResponse(
            date=planned.scheduled_date,
            day_of_week=planned.scheduled_date.weekday(),
            day_name=get_day_name(planned.scheduled_date),
            planned_workout=PlannedWorkoutResponse.model_validate(planned),
            activities=[ActivitySummary.model_validate(a) for a in day_activities],
            status=status,
            notes=[],
            insights=[],
            total_distance_m=total_distance,
            total_duration_s=total_duration
        ))
    
    # Calculate week summary
    planned_miles = sum(
        (w.target_distance_km or 0) * 0.621371
        for w in planned_workouts
    )
    completed_miles = sum(
        meters_to_miles(d.total_distance_m)
        for d in days
    )
    
    quality_types = ['threshold', 'intervals', 'tempo', 'long_mp']
    quality_planned = sum(1 for w in planned_workouts if w.workout_type in quality_types)
    quality_completed = sum(
        1 for d in days
        if d.status == "completed" and d.planned_workout and d.planned_workout.workout_type in quality_types
    )
    
    phase = planned_workouts[0].phase if planned_workouts else None
    
    return WeekSummaryResponse(
        week_number=week_number,
        phase=phase,
        planned_miles=round(planned_miles, 1),
        completed_miles=round(completed_miles, 1),
        quality_sessions_planned=quality_planned,
        quality_sessions_completed=quality_completed,
        days=days
    )
