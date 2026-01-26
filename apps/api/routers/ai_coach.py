"""
AI Coach API Router

Provides chat interface to the AI running coach.
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List, AsyncIterator
import asyncio
import json

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
    timed_out: bool = False
    history_thin: bool = False
    used_baseline: bool = False
    baseline_needed: bool = False
    rebuild_plan_prompt: bool = False


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
        error=result.get("error", False),
        timed_out=bool(result.get("timed_out", False)),
        history_thin=bool(result.get("history_thin", False)),
        used_baseline=bool(result.get("used_baseline", False)),
        baseline_needed=bool(result.get("baseline_needed", False)),
        rebuild_plan_prompt=bool(result.get("rebuild_plan_prompt", False)),
    )


@router.post("/chat/stream")
async def chat_with_coach_stream(
    request: ChatRequest,
    athlete: Athlete = Depends(get_current_athlete),
    db: Session = Depends(get_db),
):
    """
    Stream coach responses (SSE over fetch).

    Why:
    - Avoid client-side 30s aborts.
    - Provide progress heartbeats while the model/tools run.
    - Deliver the final answer in chunks so UI can render progressively.
    """

    coach = AICoach(db)

    async def _gen() -> AsyncIterator[bytes]:
        # Start the work in the background so we can emit heartbeats meanwhile.
        task = asyncio.create_task(
            coach.chat(athlete_id=athlete.id, message=request.message, include_context=request.include_context)
        )

        # Initial event.
        yield b"event: meta\ndata: " + json.dumps({"type": "meta"}).encode("utf-8") + b"\n\n"

        # Heartbeat loop until completion or timeout.
        while True:
            done, _pending = await asyncio.wait({task}, timeout=2.0)
            if done:
                break
            yield b"event: heartbeat\ndata: " + json.dumps({"type": "heartbeat"}).encode("utf-8") + b"\n\n"

        result = await task
        text = (result.get("response") or "").strip()
        timed_out = bool(result.get("timed_out", False))

        # Stream the final text in chunks (best-effort "token-like" UX).
        chunk_size = 220
        for i in range(0, len(text), chunk_size):
            delta = text[i : i + chunk_size]
            yield b"event: delta\ndata: " + json.dumps({"type": "delta", "delta": delta}).encode("utf-8") + b"\n\n"
            await asyncio.sleep(0)  # let the event loop flush

        yield b"event: done\ndata: " + json.dumps(
            {
                "type": "done",
                "timed_out": timed_out,
                "thread_id": result.get("thread_id"),
                "history_thin": bool(result.get("history_thin", False)),
                "used_baseline": bool(result.get("used_baseline", False)),
                "baseline_needed": bool(result.get("baseline_needed", False)),
                "rebuild_plan_prompt": bool(result.get("rebuild_plan_prompt", False)),
            }
        ).encode("utf-8") + b"\n\n"

    return StreamingResponse(
        _gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            # Nginx / some proxies buffer by default; disable buffering when present.
            "X-Accel-Buffering": "no",
        },
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
