"""
Knowledge Base Query API

Tier-based access to queryable knowledge base:
- Tier 3+ (Guided Coaching & Premium): Full access to search endpoints
- Internal/Admin: Full access + admin endpoints

Endpoints:
- GET /v1/knowledge/search - Search entries by tags, methodology, concept
- GET /v1/knowledge/concepts/{concept} - Get all entries about a concept
- GET /v1/knowledge/compare - Compare methodologies on a concept
- GET /v1/knowledge/vdot/formula - Get exact VDOT formula
- GET /v1/knowledge/vdot/pace-tables - Get training pace tables
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from typing import List, Optional
from uuid import UUID
import json

from core.database import get_db
from core.auth import get_current_user
from models import CoachingKnowledgeEntry, Athlete
from core.config import settings

router = APIRouter(prefix="/v1/knowledge", tags=["Knowledge Base"])


def check_tier_access(athlete: Athlete) -> str:
    """
    Check if user has access to knowledge base (Tier 3+).
    
    Returns tier level or raises HTTPException if access denied.
    """
    tier = athlete.subscription_tier or "free"
    if tier in ["guided", "premium", "admin"]:
        return tier
    # Allow free tier access to knowledge base (read-only educational content)
    return tier


@router.get("/search")
def search_knowledge(
    tags: Optional[List[str]] = Query(None, description="Filter by tags (e.g., threshold, long_run)"),
    methodology: Optional[str] = Query(None, description="Filter by methodology (e.g., Daniels, Pfitzinger)"),
    principle_type: Optional[str] = Query(None, description="Filter by principle type (e.g., vdot_formula, periodization)"),
    concept: Optional[str] = Query(None, description="Search for a specific concept"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of results"),
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Search knowledge base entries.
    
    Supports filtering by:
    - Tags (multiple tags = AND logic)
    - Methodology
    - Principle type
    - Concept (searches text content)
    
    Tier: 3+ (Guided Coaching & Premium)
    """
    # Check tier access
    tier = check_tier_access(current_user)
    
    query = db.query(CoachingKnowledgeEntry)
    
    # Filter by tags (JSONB containment)
    if tags:
        for tag in tags:
            # PostgreSQL JSONB: tags @> '["tag"]' or tags ? 'tag'
            query = query.filter(CoachingKnowledgeEntry.tags.contains([tag]))
    
    # Filter by methodology
    if methodology:
        query = query.filter(CoachingKnowledgeEntry.methodology.ilike(f"%{methodology}%"))
    
    # Filter by principle type
    if principle_type:
        query = query.filter(CoachingKnowledgeEntry.principle_type == principle_type)
    
    # Search by concept (text search)
    if concept:
        query = query.filter(
            or_(
                CoachingKnowledgeEntry.text_chunk.ilike(f"%{concept}%"),
                CoachingKnowledgeEntry.source.ilike(f"%{concept}%")
            )
        )
    
    entries = query.limit(limit).all()
    
    results = []
    for entry in entries:
        tags_list = entry.tags if isinstance(entry.tags, list) else json.loads(entry.tags) if entry.tags else []
        
        results.append({
            "id": str(entry.id),
            "source": entry.source,
            "methodology": entry.methodology,
            "principle_type": entry.principle_type,
            "tags": tags_list,
            "text_preview": entry.text_chunk[:500] if entry.text_chunk else None,
            "has_extracted_principles": bool(entry.extracted_principles),
        })
    
    return {
        "count": len(results),
        "results": results,
        "filters": {
            "tags": tags,
            "methodology": methodology,
            "principle_type": principle_type,
            "concept": concept
        }
    }


@router.get("/concepts/{concept}")
def get_concept_entries(
    concept: str,
    methodology: Optional[str] = Query(None, description="Filter by methodology"),
    limit: int = Query(50, ge=1, le=100),
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all entries about a specific concept across methodologies.
    
    Searches for entries tagged with the concept or containing the concept in text.
    
    Tier: 3+ (Guided Coaching & Premium)
    """
    tier = check_tier_access(current_user)
    
    query = db.query(CoachingKnowledgeEntry).filter(
        or_(
            CoachingKnowledgeEntry.tags.contains([concept]),
            CoachingKnowledgeEntry.text_chunk.ilike(f"%{concept}%")
        )
    )
    
    if methodology:
        query = query.filter(CoachingKnowledgeEntry.methodology.ilike(f"%{methodology}%"))
    
    entries = query.limit(limit).all()
    
    # Group by methodology
    by_methodology = {}
    for entry in entries:
        meth = entry.methodology
        if meth not in by_methodology:
            by_methodology[meth] = []
        
        tags_list = entry.tags if isinstance(entry.tags, list) else json.loads(entry.tags) if entry.tags else []
        
        by_methodology[meth].append({
            "id": str(entry.id),
            "source": entry.source,
            "principle_type": entry.principle_type,
            "tags": tags_list,
            "text_preview": entry.text_chunk[:300] if entry.text_chunk else None,
        })
    
    return {
        "concept": concept,
        "total_entries": len(entries),
        "methodologies": list(by_methodology.keys()),
        "by_methodology": by_methodology
    }


@router.get("/compare")
def compare_methodologies(
    concept: str = Query(..., description="Concept to compare (e.g., threshold, long_run)"),
    methodologies: Optional[List[str]] = Query(None, description="Specific methodologies to compare"),
    limit_per_methodology: int = Query(5, ge=1, le=20),
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Compare how different methodologies approach a concept.
    
    Returns side-by-side excerpts from each methodology.
    
    Tier: 3+ (Guided Coaching & Premium)
    """
    tier = check_tier_access(current_user)
    
    # Find entries tagged with concept
    query = db.query(CoachingKnowledgeEntry).filter(
        CoachingKnowledgeEntry.tags.contains([concept])
    )
    
    if methodologies:
        # Filter to specific methodologies
        conditions = [CoachingKnowledgeEntry.methodology.ilike(f"%{meth}%") for meth in methodologies]
        query = query.filter(or_(*conditions))
    
    entries = query.all()
    
    # Group by methodology
    by_methodology = {}
    for entry in entries:
        meth = entry.methodology
        if meth not in by_methodology:
            by_methodology[meth] = []
        
        if len(by_methodology[meth]) < limit_per_methodology:
            tags_list = entry.tags if isinstance(entry.tags, list) else json.loads(entry.tags) if entry.tags else []
            
            by_methodology[meth].append({
                "id": str(entry.id),
                "source": entry.source,
                "principle_type": entry.principle_type,
                "tags": tags_list,
                "excerpt": entry.text_chunk[:500] if entry.text_chunk else None,
            })
    
    return {
        "concept": concept,
        "methodologies_compared": list(by_methodology.keys()),
        "comparison": by_methodology
    }


@router.get("/vdot/formula")
def get_vdot_formula(
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get exact VDOT calculation formula from Daniels' Running Formula.
    
    Tier: 3+ (Guided Coaching & Premium)
    """
    tier = check_tier_access(current_user)
    
    entry = db.query(CoachingKnowledgeEntry).filter(
        CoachingKnowledgeEntry.principle_type == "vdot_exact",
        CoachingKnowledgeEntry.methodology == "Daniels"
    ).first()
    
    if not entry or not entry.extracted_principles:
        raise HTTPException(status_code=404, detail="VDOT formula not found")
    
    data = json.loads(entry.extracted_principles)
    
    return {
        "source": entry.source,
        "methodology": entry.methodology,
        "formulas": data.get("formulas", {}),
        "zone_formulas": data.get("zone_formulas", {})
    }


@router.get("/vdot/pace-tables")
def get_vdot_pace_tables(
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get training pace tables (E, M, T, I, R paces) from Daniels' Running Formula.
    
    Tier: 3+ (Guided Coaching & Premium)
    """
    tier = check_tier_access(current_user)
    
    entry = db.query(CoachingKnowledgeEntry).filter(
        CoachingKnowledgeEntry.principle_type == "vdot_exact",
        CoachingKnowledgeEntry.methodology == "Daniels"
    ).first()
    
    if not entry or not entry.extracted_principles:
        raise HTTPException(status_code=404, detail="VDOT pace tables not found")
    
    data = json.loads(entry.extracted_principles)
    
    return {
        "source": entry.source,
        "methodology": entry.methodology,
        "pace_tables": data.get("pace_tables", {}),
        "equivalent_tables": data.get("equivalent_tables", {})
    }


@router.get("/tags")
def list_all_tags(
    methodology: Optional[str] = Query(None, description="Filter by methodology"),
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List all available tags in the knowledge base.
    
    Tier: 3+ (Guided Coaching & Premium)
    """
    tier = check_tier_access(current_user)
    
    query = db.query(CoachingKnowledgeEntry)
    
    if methodology:
        query = query.filter(CoachingKnowledgeEntry.methodology.ilike(f"%{methodology}%"))
    
    entries = query.all()
    
    tag_counts = {}
    for entry in entries:
        if entry.tags:
            tags = entry.tags if isinstance(entry.tags, list) else json.loads(entry.tags) if isinstance(entry.tags, str) else []
            for tag in tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
    
    return {
        "total_tags": len(tag_counts),
        "tags": sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)
    }

