"""
AI Coach Service

Uses OpenAI Assistants API for persistent, context-aware coaching.

Features:
- Persistent threads per athlete (conversation memory)
- Context injection from athlete's actual data
- Knowledge of training methodology
- Tiered context (7-day, 30-day, 120-day)
"""

import os
import json
from datetime import date, datetime, timedelta
from typing import Optional, Dict, List, Any
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import func
import logging

logger = logging.getLogger(__name__)

# Check if OpenAI is available
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logger.warning("OpenAI not installed - AI Coach will be disabled")

from models import (
    Athlete, Activity, TrainingPlan, PlannedWorkout, 
    DailyCheckin, PersonalBest
)


class AICoach:
    """
    AI Coach powered by OpenAI Assistants API.
    
    Provides:
    - Persistent conversation threads
    - Context-aware responses based on athlete data
    - Training methodology knowledge
    """
    
    # System instructions for the AI coach
    SYSTEM_INSTRUCTIONS = """You are StrideIQ, an AI running coach. You provide personalized, data-driven guidance to runners.

## Your Core Principles

1. **Data-Driven**: Always ground advice in the athlete's actual training data. Never make assumptions.

2. **Efficiency-Focused**: The key metric is running efficiency (pace at a given heart rate). Faster pace at same HR = improvement.

3. **Individualized**: Every athlete responds differently. Patterns from THIS athlete's data matter more than generic advice.

4. **Honest**: If the data is insufficient or inconclusive, say so. Don't guess.

5. **Action-Oriented**: Every response should include something actionable.

## Your Knowledge

You understand running physiology, periodization, and training principles:
- Base building (aerobic development, volume accumulation)
- Threshold training (lactate clearance, tempo runs)
- VO2max development (intervals, speed work)
- Recovery (easy days, sleep, nutrition)
- Tapering (pre-race reduction)
- Injury prevention (load management, progression)

## Your Communication Style

- Be concise and clear
- Use the athlete's actual data when making points
- Avoid jargon unless the athlete uses it first
- Be encouraging but never sugarcoat problems
- Format responses with clear structure (use markdown)

## Important Rules

1. Never recommend medical advice - refer to healthcare professionals
2. Never recommend extreme diets or protocols
3. Always acknowledge when you're uncertain
4. Base recommendations on the athlete's current fitness level, not aspirational goals
5. Consider the athlete's injury history if mentioned"""

    def __init__(self, db: Session):
        self.db = db
        self.client = None
        self.assistant_id = None
        
        if OPENAI_AVAILABLE:
            api_key = os.getenv("OPENAI_API_KEY")
            if api_key:
                self.client = OpenAI(api_key=api_key)
                # Get or create assistant
                self.assistant_id = os.getenv("OPENAI_ASSISTANT_ID") or self._get_or_create_assistant()
    
    def _get_or_create_assistant(self) -> Optional[str]:
        """Get existing assistant or create a new one."""
        if not self.client:
            return None
        
        try:
            # Try to find existing assistant by name
            assistants = self.client.beta.assistants.list(limit=20)
            for assistant in assistants.data:
                if assistant.name == "StrideIQ Coach":
                    logger.info(f"Using existing assistant: {assistant.id}")
                    return assistant.id
            
            # Create new assistant
            assistant = self.client.beta.assistants.create(
                name="StrideIQ Coach",
                instructions=self.SYSTEM_INSTRUCTIONS,
                model="gpt-4o",  # or "gpt-4-turbo-preview" for cost savings
                tools=[],  # Can add code interpreter, retrieval later
            )
            logger.info(f"Created new assistant: {assistant.id}")
            return assistant.id
            
        except Exception as e:
            logger.error(f"Failed to get/create assistant: {e}")
            return None
    
    def get_or_create_thread(self, athlete_id: UUID) -> Optional[str]:
        """
        Get or create a conversation thread for an athlete.
        
        In production, thread IDs would be stored in the database.
        For now, we create a new thread each time (stateless).
        """
        if not self.client:
            return None
        
        try:
            thread = self.client.beta.threads.create()
            return thread.id
        except Exception as e:
            logger.error(f"Failed to create thread: {e}")
            return None
    
    def build_context(self, athlete_id: UUID, window_days: int = 30) -> str:
        """
        Build context from athlete's data for injection into conversation.
        
        Context tiers:
        - 7 days: Detailed daily data
        - 30 days: Weekly summaries
        - 120+ days: Phase/block summaries
        """
        athlete = self.db.query(Athlete).filter(Athlete.id == athlete_id).first()
        if not athlete:
            return "No athlete data available."
        
        context_parts = []
        today = date.today()
        
        # --- Athlete Profile ---
        context_parts.append("## Athlete Profile")
        if athlete.display_name:
            context_parts.append(f"Name: {athlete.display_name}")
        if athlete.birthdate:
            age = (today - athlete.birthdate).days // 365
            context_parts.append(f"Age: {age}")
        if athlete.vdot:
            context_parts.append(f"Current VDOT: {athlete.vdot:.1f}")
        if athlete.resting_hr:
            context_parts.append(f"Resting HR: {athlete.resting_hr} bpm")
        if athlete.max_hr:
            context_parts.append(f"Max HR: {athlete.max_hr} bpm")
        
        # --- Personal Bests ---
        pbs = self.db.query(PersonalBest).filter(
            PersonalBest.athlete_id == athlete_id
        ).order_by(PersonalBest.achieved_at.desc()).limit(5).all()
        
        if pbs:
            context_parts.append("\n## Personal Bests")
            for pb in pbs:
                time_str = self._format_time(pb.time_seconds)
                achieved = pb.achieved_at.strftime("%b %d, %Y")
                context_parts.append(f"- {pb.distance_category}: {time_str} ({achieved})")
        
        # --- Current Training Plan ---
        plan = self.db.query(TrainingPlan).filter(
            TrainingPlan.athlete_id == athlete_id,
            TrainingPlan.status == "active"
        ).first()
        
        if plan:
            context_parts.append("\n## Current Training Plan")
            context_parts.append(f"Goal: {plan.goal_race_name}")
            context_parts.append(f"Race Date: {plan.goal_race_date}")
            context_parts.append(f"Week: {self._get_plan_week(plan)} of {plan.total_weeks}")
            
            # This week's workouts
            week_start = today - timedelta(days=today.weekday())
            week_end = week_start + timedelta(days=6)
            
            workouts = self.db.query(PlannedWorkout).filter(
                PlannedWorkout.plan_id == plan.id,
                PlannedWorkout.scheduled_date >= week_start,
                PlannedWorkout.scheduled_date <= week_end
            ).order_by(PlannedWorkout.scheduled_date).all()
            
            if workouts:
                context_parts.append("\nThis week's plan:")
                for w in workouts:
                    status = "✓" if w.completed else "○"
                    context_parts.append(f"  {status} {w.scheduled_date.strftime('%a')}: {w.title}")
        
        # --- Recent Activity Summary (7 days) ---
        seven_days_ago = today - timedelta(days=7)
        recent_activities = self.db.query(Activity).filter(
            Activity.athlete_id == athlete_id,
            Activity.start_time >= datetime.combine(seven_days_ago, datetime.min.time()),
            Activity.sport == 'run'
        ).order_by(Activity.start_time.desc()).all()
        
        if recent_activities:
            context_parts.append("\n## Last 7 Days")
            total_distance = sum(a.distance_m or 0 for a in recent_activities) / 1000
            total_time = sum(a.duration_s or 0 for a in recent_activities) / 60
            context_parts.append(f"Runs: {len(recent_activities)} | Distance: {total_distance:.1f} km | Time: {total_time:.0f} min")
            
            for a in recent_activities[:5]:  # Show last 5
                distance_km = (a.distance_m or 0) / 1000
                pace = self._format_pace(a.duration_s, a.distance_m) if a.distance_m else "N/A"
                hr = f"{a.avg_hr} bpm" if a.avg_hr else ""
                context_parts.append(f"  - {a.start_time.strftime('%a %m/%d')}: {distance_km:.1f} km @ {pace} {hr}")
        
        # --- 30-Day Summary ---
        thirty_days_ago = today - timedelta(days=30)
        month_activities = self.db.query(Activity).filter(
            Activity.athlete_id == athlete_id,
            Activity.start_time >= datetime.combine(thirty_days_ago, datetime.min.time()),
            Activity.sport == 'run'
        ).all()
        
        if month_activities:
            context_parts.append("\n## Last 30 Days")
            total_distance = sum(a.distance_m or 0 for a in month_activities) / 1000
            avg_weekly = total_distance / 4.3  # ~4.3 weeks
            run_count = len(month_activities)
            
            # Calculate average efficiency
            efficiencies = []
            for a in month_activities:
                if a.avg_hr and a.distance_m and a.duration_s:
                    pace_km = a.duration_s / (a.distance_m / 1000)
                    efficiency = pace_km / a.avg_hr  # Lower is better
                    efficiencies.append(efficiency)
            
            context_parts.append(f"Runs: {run_count} | Distance: {total_distance:.0f} km | Avg/week: {avg_weekly:.0f} km")
            
            if efficiencies:
                avg_eff = sum(efficiencies) / len(efficiencies)
                context_parts.append(f"Average efficiency: {avg_eff:.3f} (pace/HR ratio - lower is better)")
        
        # --- Recent Check-ins ---
        recent_checkins = self.db.query(DailyCheckin).filter(
            DailyCheckin.athlete_id == athlete_id,
            DailyCheckin.date >= seven_days_ago
        ).order_by(DailyCheckin.date.desc()).limit(3).all()
        
        if recent_checkins:
            context_parts.append("\n## Recent Wellness")
            for c in recent_checkins:
                parts = []
                if c.sleep_h:
                    parts.append(f"Sleep: {c.sleep_h}h")
                if c.stress_1_5:
                    parts.append(f"Stress: {c.stress_1_5}/5")
                if c.soreness_1_5:
                    parts.append(f"Soreness: {c.soreness_1_5}/5")
                if parts:
                    context_parts.append(f"  {c.date.strftime('%m/%d')}: {' | '.join(parts)}")
        
        return "\n".join(context_parts)
    
    def _format_time(self, seconds: int) -> str:
        """Format seconds as H:MM:SS or M:SS."""
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        
        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        return f"{minutes}:{secs:02d}"
    
    def _format_pace(self, duration_s: Optional[int], distance_m: Optional[int]) -> str:
        """Format pace as M:SS/km."""
        if not duration_s or not distance_m or distance_m == 0:
            return "N/A"
        
        pace_per_km = duration_s / (distance_m / 1000)
        minutes = int(pace_per_km // 60)
        seconds = int(pace_per_km % 60)
        return f"{minutes}:{seconds:02d}/km"
    
    def _get_plan_week(self, plan: TrainingPlan) -> int:
        """Calculate current week of the plan."""
        today = date.today()
        if today < plan.plan_start_date:
            return 0
        if today > plan.plan_end_date:
            return plan.total_weeks + 1
        
        days_in = (today - plan.plan_start_date).days
        return (days_in // 7) + 1
    
    async def chat(
        self, 
        athlete_id: UUID, 
        message: str,
        include_context: bool = True
    ) -> Dict[str, Any]:
        """
        Send a message to the AI coach and get a response.
        
        Args:
            athlete_id: The athlete's ID
            message: The user's message
            include_context: Whether to inject context from athlete data
        
        Returns:
            Dict with response text and metadata
        """
        # If OpenAI not available, return a helpful message
        if not self.client or not self.assistant_id:
            return {
                "response": "AI Coach is not configured. Please set OPENAI_API_KEY in your environment.",
                "error": True
            }
        
        try:
            # Create a new thread for this conversation
            thread = self.client.beta.threads.create()
            
            # Build context
            if include_context:
                context = self.build_context(athlete_id)
                system_context = f"## Athlete Context\n\n{context}\n\n---\n\nRespond to the athlete's question below:"
                
                # Add context as first message
                self.client.beta.threads.messages.create(
                    thread_id=thread.id,
                    role="user",
                    content=system_context
                )
            
            # Add the user's message
            self.client.beta.threads.messages.create(
                thread_id=thread.id,
                role="user",
                content=message
            )
            
            # Run the assistant
            run = self.client.beta.threads.runs.create(
                thread_id=thread.id,
                assistant_id=self.assistant_id
            )
            
            # Wait for completion (with timeout)
            import time
            max_wait = 60  # seconds
            start = time.time()
            
            while True:
                run_status = self.client.beta.threads.runs.retrieve(
                    thread_id=thread.id,
                    run_id=run.id
                )
                
                if run_status.status == "completed":
                    break
                elif run_status.status in ["failed", "cancelled", "expired"]:
                    return {
                        "response": f"The AI coach encountered an error: {run_status.status}",
                        "error": True
                    }
                
                if time.time() - start > max_wait:
                    return {
                        "response": "The AI coach took too long to respond. Please try again.",
                        "error": True
                    }
                
                time.sleep(1)
            
            # Get the response
            messages = self.client.beta.threads.messages.list(
                thread_id=thread.id,
                order="desc",
                limit=1
            )
            
            if messages.data:
                response_content = messages.data[0].content[0]
                if hasattr(response_content, 'text'):
                    response_text = response_content.text.value
                else:
                    response_text = str(response_content)
                
                return {
                    "response": response_text,
                    "thread_id": thread.id,
                    "error": False
                }
            
            return {
                "response": "No response received from AI coach.",
                "error": True
            }
            
        except Exception as e:
            logger.error(f"AI Coach error: {e}")
            return {
                "response": f"An error occurred: {str(e)}",
                "error": True
            }


def get_ai_coach(db: Session) -> AICoach:
    """Factory function for dependency injection."""
    return AICoach(db)
