"""Saving and reading search sessions (spec §28).

Saving is explicit — a session lands in the database only when the user presses
Save. Runs are cheap to repeat thanks to the disk cache, so auto-saving every
search would fill the table with noise nobody asked to keep.
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import func, select

from app.db import session_scope
from app.db_models import SavedEvidence, SavedLead, SearchSession
from app.models import Lead
from app.schemas.api import lead_id_for

log = logging.getLogger(__name__)

MAX_NAME_LENGTH = 200


def default_name(category: str, location: str) -> str:
    return f"{category} in {location}"[:MAX_NAME_LENGTH]


def _to_saved_lead(lead: Lead, rank: int) -> SavedLead:
    b = lead.business
    top = lead.top_analysis
    s = lead.scores
    tech = lead.website_info.tech

    row = SavedLead(
        rank=rank,
        lead_id=lead_id_for(b.place_id),
        company_name=b.name,
        category=b.category or "",
        rating=b.rating,
        total_reviews=b.review_count,
        phone=b.phone,
        email=b.email,
        website=b.website,
        address=b.address or "",
        city=b.city or "",
        google_maps_url=b.google_maps_url,
        latitude=b.latitude,
        longitude=b.longitude,
        pain_point=top.pain_point if top else "",
        pain_category=top.pain_category if top else "",
        pain_severity=top.severity if top else "",
        customer_impact=top.customer_impact if top else "",
        business_impact=top.business_impact if top else "",
        confidence=round(top.confidence, 2) if top else 0.0,
        primary_opportunity=lead.opportunity.primary_opportunity or "",
        secondary_opportunities=list(lead.opportunity.secondary_opportunities or []),
        technology_signals=[t for t in tech.as_csv_field().split("; ") if t],
        website_reachable=lead.website_info.reachable,
        sales_pitch=lead.sales_pitch or "",
        lead_score=s.lead_score,
        priority=s.priority,
        software_pain_score=s.software_pain_score,
        business_potential_score=s.business_potential_score,
        review_evidence_score=s.review_evidence_score,
        digital_presence_score=s.digital_presence_score,
        contactability_score=s.contactability_score,
        score_notes=list(s.notes or []),
    )

    # §12 — every conclusion keeps the review it came from.
    row.evidence = [
        SavedEvidence(
            review_text=a.evidence_text,
            review_rating=a.evidence_rating,
            review_date=a.evidence_date,
            review_url=a.evidence_url,
            pain_point=a.pain_point,
            pain_category=a.pain_category,
            severity=a.severity,
            customer_impact=a.customer_impact,
            business_impact=a.business_impact,
            recommended_solution=a.recommended_solution,
            confidence=round(a.confidence, 2),
        )
        for a in lead.software_analyses
    ]
    return row


def save_session(job, name: Optional[str] = None, llm_model: str = "") -> int:
    """Persist a finished job as a session. Returns the new session id."""
    r = job.request
    leads = job.leads or []

    session_row = SearchSession(
        name=(name or "").strip()[:MAX_NAME_LENGTH] or default_name(r.category, r.location),
        job_id=job.id,
        location=r.location,
        category=r.category,
        min_rating=r.min_rating,
        max_rating=r.max_rating,
        minimum_reviews=r.minimum_reviews,
        requested_leads=r.limit,
        max_places=r.max_places,
        strict_filters=getattr(r, "strict_filters", False),
        status=job.status,
        lead_count=len(leads),
        hot_count=sum(1 for l in leads if l.scores.priority == "HOT"),
        top_score=max((l.scores.lead_score for l in leads), default=0),
        llm_model=llm_model,
        warnings=list(job.warnings or []),
        stats=dict(job.stats or {}),
    )
    session_row.leads = [_to_saved_lead(l, i) for i, l in enumerate(leads, start=1)]

    with session_scope() as db:
        db.add(session_row)
        db.flush()
        new_id = session_row.id

    log.info("saved session %s (%d leads)", new_id, len(leads))
    return new_id


def list_sessions(limit: int = 50, offset: int = 0) -> tuple[list[SearchSession], int]:
    """Newest first. Leads are not loaded — the list view does not need them."""
    with session_scope() as db:
        total = db.execute(select(func.count(SearchSession.id))).scalar_one()
        rows = (
            db.execute(
                select(SearchSession)
                .order_by(SearchSession.created_at.desc(), SearchSession.id.desc())
                .limit(limit)
                .offset(offset)
            )
            .unique()
            .scalars()
            .all()
        )
        # Detached instances are safe to read: relationships that the caller
        # needs are eager-loaded, and expire_on_commit is off.
        return list(rows), total


def get_session(session_id: int) -> Optional[SearchSession]:
    with session_scope() as db:
        return db.get(SearchSession, session_id)


def delete_session(session_id: int) -> bool:
    with session_scope() as db:
        row = db.get(SearchSession, session_id)
        if row is None:
            return False
        db.delete(row)  # leads and evidence cascade
        return True


def rename_session(session_id: int, name: str) -> Optional[SearchSession]:
    with session_scope() as db:
        row = db.get(SearchSession, session_id)
        if row is None:
            return None
        cleaned = name.strip()[:MAX_NAME_LENGTH]
        if cleaned:
            row.name = cleaned
        return row
