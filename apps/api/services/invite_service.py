"""
Invite allowlist service (Phase 3).

Invites are first-class, auditable domain objects:
- Enforced at all account creation boundaries.
- Admin-managed via API (no DB access needed).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Tuple
from uuid import UUID

from sqlalchemy.orm import Session

from models import InviteAllowlist, InviteAuditEvent


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def get_invite(db: Session, email: str) -> Optional[InviteAllowlist]:
    norm = normalize_email(email)
    if not norm:
        return None
    return db.query(InviteAllowlist).filter(InviteAllowlist.email == norm).first()


def is_invited(db: Session, email: str) -> Tuple[bool, Optional[InviteAllowlist]]:
    inv = get_invite(db, email)
    if not inv:
        return False, None
    if not inv.is_active:
        return False, inv
    if inv.used_at is not None:
        return False, inv
    return True, inv


def audit_invite(
    db: Session,
    *,
    invite_id: UUID,
    actor_athlete_id: Optional[UUID],
    action: str,
    target_email: str,
    metadata: Optional[dict] = None,
) -> None:
    db.add(
        InviteAuditEvent(
            invite_id=invite_id,
            actor_athlete_id=actor_athlete_id,
            action=action,
            target_email=normalize_email(target_email),
            event_metadata=metadata,
        )
    )


def create_invite(
    db: Session,
    *,
    email: str,
    invited_by_athlete_id: Optional[UUID],
    note: Optional[str] = None,
    grant_tier: Optional[str] = None,
) -> InviteAllowlist:
    """
    Create or reactivate an invite.
    
    Args:
        grant_tier: Optional subscription tier to grant on signup (e.g., "pro" for beta testers)
    """
    norm = normalize_email(email)
    inv = get_invite(db, norm)
    if inv:
        # idempotent: if already exists, re-activate unless used
        if inv.used_at is None:
            inv.is_active = True
            inv.note = note or inv.note
            inv.grant_tier = grant_tier if grant_tier is not None else inv.grant_tier
            inv.invited_by_athlete_id = invited_by_athlete_id
            inv.invited_at = datetime.now(timezone.utc)
            inv.revoked_at = None
            inv.revoked_by_athlete_id = None
            audit_invite(
                db,
                invite_id=inv.id,
                actor_athlete_id=invited_by_athlete_id,
                action="invite.reactivated",
                target_email=norm,
                metadata={"grant_tier": grant_tier} if grant_tier else None,
            )
        return inv

    inv = InviteAllowlist(
        email=norm,
        is_active=True,
        note=note,
        grant_tier=grant_tier,
        invited_by_athlete_id=invited_by_athlete_id,
        invited_at=datetime.now(timezone.utc),
    )
    db.add(inv)
    db.flush()  # ensures inv.id
    audit_invite(
        db,
        invite_id=inv.id,
        actor_athlete_id=invited_by_athlete_id,
        action="invite.created",
        target_email=norm,
        metadata={"grant_tier": grant_tier} if grant_tier else None,
    )
    return inv


def revoke_invite(
    db: Session,
    *,
    email: str,
    revoked_by_athlete_id: Optional[UUID],
    reason: Optional[str] = None,
) -> Optional[InviteAllowlist]:
    inv = get_invite(db, email)
    if not inv:
        return None
    inv.is_active = False
    inv.revoked_at = datetime.now(timezone.utc)
    inv.revoked_by_athlete_id = revoked_by_athlete_id
    audit_invite(
        db,
        invite_id=inv.id,
        actor_athlete_id=revoked_by_athlete_id,
        action="invite.revoked",
        target_email=inv.email,
        metadata={"reason": reason} if reason else None,
    )
    return inv


def mark_invite_used(
    db: Session,
    *,
    invite: InviteAllowlist,
    used_by_athlete_id: UUID,
) -> InviteAllowlist:
    invite.used_at = datetime.now(timezone.utc)
    invite.used_by_athlete_id = used_by_athlete_id
    invite.is_active = False
    audit_invite(
        db,
        invite_id=invite.id,
        actor_athlete_id=used_by_athlete_id,
        action="invite.used",
        target_email=invite.email,
        metadata={"athlete_id": str(used_by_athlete_id)},
    )
    return invite

