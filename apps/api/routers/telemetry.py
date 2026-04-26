"""
Usage Telemetry API

Lightweight page-view tracking. Fire-and-forget from the frontend —
telemetry failures never affect the athlete experience.
"""
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from core.auth import get_current_user, require_admin, get_current_athlete_optional
from core.database import get_db
from models import Athlete, PageView, ToolTelemetryEvent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/telemetry", tags=["telemetry"])


# ── Request / Response models ─────────────────────────────────────────

class PageViewEvent(BaseModel):
    screen: str
    referrer_screen: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class PageViewResponse(BaseModel):
    id: str


class PageExitEvent(BaseModel):
    pass  # body intentionally empty; ID is in the path


TOOL_FUNNEL_EVENT_TYPES = frozenset(
    {"tool_page_view", "tool_result_view", "signup_cta_click"}
)


class ToolFunnelEvent(BaseModel):
    event_type: str
    path: str
    metadata: Optional[Dict[str, Any]] = Field(default=None)

    @field_validator("event_type")
    @classmethod
    def validate_event_type(cls, v: str) -> str:
        if v not in TOOL_FUNNEL_EVENT_TYPES:
            raise ValueError("invalid event_type")
        return v

    @field_validator("path")
    @classmethod
    def validate_path(cls, v: str) -> str:
        if not v or len(v) > 2048:
            raise ValueError("invalid path")
        return v


# ── Athlete endpoints ─────────────────────────────────────────────────

@router.post("/page-view", response_model=PageViewResponse, status_code=201)
def record_page_view(
    event: PageViewEvent,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PageViewResponse:
    pv = PageView(
        athlete_id=current_user.id,
        screen=event.screen,
        referrer_screen=event.referrer_screen,
        event_metadata=event.metadata,
    )
    db.add(pv)
    db.commit()
    db.refresh(pv)
    return PageViewResponse(id=str(pv.id))


@router.post("/tool-event", status_code=204)
def record_tool_funnel_event(
    event: ToolFunnelEvent,
    db: Session = Depends(get_db),
    current_athlete: Optional[Athlete] = Depends(get_current_athlete_optional),
) -> None:
    """
    Public funnel telemetry for /tools and signup CTAs. Fire-and-forget; failures are ignored client-side.
    Authenticated users are correlated via optional Bearer token.
    """
    if event.event_type in ("tool_page_view", "tool_result_view"):
        if not event.path.startswith("/tools"):
            raise HTTPException(status_code=400, detail="path must start with /tools")
    row = ToolTelemetryEvent(
        event_type=event.event_type,
        path=event.path,
        athlete_id=current_athlete.id if current_athlete else None,
        event_metadata=event.metadata,
    )
    db.add(row)
    db.commit()


@router.patch("/page-view/{page_view_id}/exit", status_code=204)
def record_page_exit(
    page_view_id: UUID,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    pv = (
        db.query(PageView)
        .filter(PageView.id == page_view_id, PageView.athlete_id == current_user.id)
        .first()
    )
    if not pv:
        return
    if pv.exited_at is not None:
        return

    now = datetime.now(timezone.utc)
    pv.exited_at = now
    if pv.entered_at:
        delta = (now - pv.entered_at).total_seconds()
        pv.duration_seconds = round(delta, 1) if delta > 0 else 0
    db.commit()


# ── Beacon endpoint (same as exit but accepts POST for sendBeacon) ────

@router.post("/page-view/{page_view_id}/exit", status_code=204)
def record_page_exit_beacon(
    page_view_id: UUID,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    record_page_exit(page_view_id, current_user, db)


# ── Admin usage report ────────────────────────────────────────────────

SESSION_GAP_MINUTES = 30


class ScreenUsage(BaseModel):
    screen: str
    visits: int
    avg_duration_s: Optional[float] = None


class EntryPoint(BaseModel):
    screen: str
    count: int


class AthleteUsage(BaseModel):
    athlete_id: str
    name: str
    total_sessions: int
    total_page_views: int
    most_visited: List[ScreenUsage]
    entry_points: List[EntryPoint]
    hourly_distribution: Dict[str, int]
    last_active: Optional[str] = None


class UsageReportResponse(BaseModel):
    days: int
    athletes: List[AthleteUsage]


@router.get(
    "/admin/usage-report",
    response_model=UsageReportResponse,
    dependencies=[Depends(require_admin)],
)
def get_usage_report(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
) -> UsageReportResponse:
    since = datetime.now(timezone.utc) - timedelta(days=days)

    rows = (
        db.query(PageView)
        .filter(PageView.entered_at >= since)
        .order_by(PageView.athlete_id, PageView.entered_at)
        .all()
    )

    athletes_map: Dict[UUID, List[PageView]] = defaultdict(list)
    for r in rows:
        athletes_map[r.athlete_id].append(r)

    athlete_ids = list(athletes_map.keys())
    athlete_names: Dict[UUID, str] = {}
    if athlete_ids:
        athletes = db.query(Athlete.id, Athlete.first_name, Athlete.last_name).filter(
            Athlete.id.in_(athlete_ids)
        ).all()
        for a in athletes:
            name = f"{a.first_name or ''} {a.last_name or ''}".strip() or "Unknown"
            athlete_names[a.id] = name

    result: List[AthleteUsage] = []

    for athlete_id, views in athletes_map.items():
        screen_counts: Dict[str, int] = defaultdict(int)
        screen_durations: Dict[str, List[float]] = defaultdict(list)
        hourly: Dict[int, int] = defaultdict(int)
        sessions: List[List[PageView]] = []
        current_session: List[PageView] = []

        for v in views:
            screen_counts[v.screen] += 1
            if v.duration_seconds is not None and v.duration_seconds > 0:
                screen_durations[v.screen].append(v.duration_seconds)
            if v.entered_at:
                hourly[v.entered_at.hour] += 1

            if not current_session:
                current_session.append(v)
            else:
                last = current_session[-1]
                gap_ref = last.exited_at or last.entered_at
                if gap_ref and v.entered_at and (v.entered_at - gap_ref).total_seconds() > SESSION_GAP_MINUTES * 60:
                    sessions.append(current_session)
                    current_session = [v]
                else:
                    current_session.append(v)

        if current_session:
            sessions.append(current_session)

        most_visited = sorted(
            [
                ScreenUsage(
                    screen=s,
                    visits=c,
                    avg_duration_s=round(sum(screen_durations[s]) / len(screen_durations[s]), 1) if screen_durations[s] else None,
                )
                for s, c in screen_counts.items()
            ],
            key=lambda x: x.visits,
            reverse=True,
        )[:10]

        entry_counts: Dict[str, int] = defaultdict(int)
        for sess in sessions:
            if sess:
                entry_counts[sess[0].screen] += 1

        entry_points = sorted(
            [EntryPoint(screen=s, count=c) for s, c in entry_counts.items()],
            key=lambda x: x.count,
            reverse=True,
        )

        last_view = views[-1] if views else None
        last_active = last_view.entered_at.isoformat() if last_view and last_view.entered_at else None

        result.append(
            AthleteUsage(
                athlete_id=str(athlete_id),
                name=athlete_names.get(athlete_id, "Unknown"),
                total_sessions=len(sessions),
                total_page_views=len(views),
                most_visited=most_visited,
                entry_points=entry_points,
                hourly_distribution={str(h): c for h, c in sorted(hourly.items())},
                last_active=last_active,
            )
        )

    result.sort(key=lambda x: x.total_page_views, reverse=True)

    return UsageReportResponse(days=days, athletes=result)
