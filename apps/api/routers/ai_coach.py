"""
AI Coach API Router

Provides chat interface to the AI running coach.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List

from core.database import get_db
from core.auth import get_current_athlete
from models import Athlete
from services.ai_coach import AICoach

router = APIRouter(prefix="/v1/coach", tags=["AI Coach"])


class ChatRequest(BaseModel):
    """Request to chat with AI coach."""
    message: str
    include_context: bool = True


class ChatResponse(BaseModel):
    """Response from AI coach."""
    response: str
    thread_id: Optional[str] = None
    error: bool = False


class ContextResponse(BaseModel):
    """Athlete context that would be sent to AI."""
    context: str


class NewConversationResponse(BaseModel):
    ok: bool


class ThreadMessage(BaseModel):
    role: str
    content: str
    created_at: Optional[str] = None


class ThreadHistoryResponse(BaseModel):
    thread_id: Optional[str] = None
    messages: List[ThreadMessage]


@router.post("/chat", response_model=ChatResponse)
async def chat_with_coach(
    request: ChatRequest,
    athlete: Athlete = Depends(get_current_athlete),
    db: Session = Depends(get_db),
):
    """
    Send a message to the AI coach and get a response.
    
    The coach has access to your training data and provides
    personalized advice based on your actual performance.
    """
    coach = AICoach(db)
    result = await coach.chat(
        athlete_id=athlete.id,
        message=request.message,
        include_context=request.include_context
    )
    
    return ChatResponse(
        response=result.get("response", ""),
        thread_id=result.get("thread_id"),
        error=result.get("error", False)
    )


@router.post("/new-conversation", response_model=NewConversationResponse)
async def new_conversation(
    athlete: Athlete = Depends(get_current_athlete),
    db: Session = Depends(get_db),
):
    """
    Clear the stored coach thread for the athlete.

    Next chat message will create a new conversation thread.
    """
    athlete.coach_thread_id = None
    db.add(athlete)
    db.commit()
    return NewConversationResponse(ok=True)


@router.get("/context", response_model=ContextResponse)
async def get_coach_context(
    days: int = 30,
    athlete: Athlete = Depends(get_current_athlete),
    db: Session = Depends(get_db),
):
    """
    Preview the context that would be sent to the AI coach.
    
    Useful for understanding what data the coach has access to.
    """
    coach = AICoach(db)
    context = coach.build_context(athlete.id, window_days=days)
    
    return ContextResponse(context=context)


@router.get("/suggestions")
async def get_suggested_questions(
    athlete: Athlete = Depends(get_current_athlete),
    db: Session = Depends(get_db),
):
    """
    Get suggested questions based on current athlete state.
    """
    coach = AICoach(db)
    suggestions = coach.get_dynamic_suggestions(athlete.id)
    return {"suggestions": suggestions}


@router.get("/history", response_model=ThreadHistoryResponse)
async def get_coach_history(
    limit: int = 50,
    athlete: Athlete = Depends(get_current_athlete),
    db: Session = Depends(get_db),
):
    """
    Get persisted coach thread history (if configured).
    """
    coach = AICoach(db)
    hist = coach.get_thread_history(athlete.id, limit=limit)
    msgs = [
        ThreadMessage(role=m.get("role", "assistant"), content=m.get("content", ""), created_at=m.get("created_at"))
        for m in (hist.get("messages") or [])
        if (m.get("content") or "").strip()
    ]
    return ThreadHistoryResponse(thread_id=hist.get("thread_id"), messages=msgs)
