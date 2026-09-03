"""Saving and reading individual leads (spec §28).

Saving is explicit and per-lead: the user ticks the leads worth keeping and
presses Save. A search that returned five businesses where only one is worth
calling should put one row in the database, not five.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import func, select

from app.db import session_scope
from app.db_models import SavedEvidence, SavedLead
from app.models import Lead
from app.schemas.api import lead_id_for

log = logging.getLogger(__name__)


@dataclass
class SaveOutcome:
    created: int = 0
    updated: int = 0
    lead_ids: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.lead_ids is None:
            self.lead_ids = []

    @property
    def total(self) -> int:
        return self.created + self.updated


def _apply(row: SavedLead, lead: Lead, context: dict) -> None:
    """Copy a pipeline Lead onto a database row (create or refresh)."""
    b = lead.business
    top = lead.top_analysis
    s = lead.scores
    tech = lead.website_info.tech

    row.source_job_id = context.get("job_id")
    row.source_location = context.get("location", "")
    row.source_category = context.get("category", "")
    row.llm_model = context.get("llm_model")

    row.company_name = b.name
    row.category = b.category or ""
    row.rating = b.rating
    row.total_reviews = b.review_count
    row.phone = b.phone
    row.email = b.email
    row.website = b.website
    row.address = b.address or ""
    row.city = b.city or ""
    row.google_maps_url = b.google_maps_url
    row.latitude = b.latitude
    row.longitude = b.longitude

    row.pain_point = top.pain_point if top else ""
    row.pain_category = top.pain_category if top else ""
    row.pain_severity = top.severity if top else ""
    row.customer_impact = top.customer_impact if top else ""
    row.business_impact = top.business_impact if top else ""
    row.confidence = round(top.confidence, 2) if top else 0.0

    row.primary_opportunity = lead.opportunity.primary_opportunity or ""
    row.secondary_opportunities = list(lead.opportunity.secondary_opportunities or [])
    row.technology_signals = [t for t in tech.as_csv_field().split("; ") if t]
    row.website_reachable = lead.website_info.reachable
    row.sales_pitch = lead.sales_pitch or ""

    row.lead_score = s.lead_score
    row.priority = s.priority
    row.software_pain_score = s.software_pain_score
    row.business_potential_score = s.business_potential_score
    row.review_evidence_score = s.review_evidence_score
    row.digital_presence_score = s.digital_presence_score
    row.contactability_score = s.contactability_score
    row.score_notes = list(s.notes or [])

    # §12 — replace evidence wholesale so a refreshed lead never mixes
    # conclusions from two different analyses.
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


def save_leads(leads: list[Lead], context: dict) -> SaveOutcome:
    """Insert or refresh the given leads. Returns what actually changed."""
    outcome = SaveOutcome()

    with session_scope() as db:
        for lead in leads:
            key = lead_id_for(lead.business.place_id)
            row = db.execute(
                select(SavedLead).where(SavedLead.lead_id == key)
            ).scalar_one_or_none()

            if row is None:
                row = SavedLead(lead_id=key)
                db.add(row)
                outcome.created += 1
            else:
                outcome.updated += 1

            _apply(row, lead, context)
            outcome.lead_ids.append(key)

    log.info("saved leads: %d new, %d refreshed", outcome.created, outcome.updated)
    return outcome


def list_saved(limit: int = 200, offset: int = 0) -> tuple[list[SavedLead], int]:
    """Highest score first — the order a rep would work them in."""
    with session_scope() as db:
        total = db.execute(select(func.count(SavedLead.id))).scalar_one()
        rows = (
            db.execute(
                select(SavedLead)
                .order_by(SavedLead.lead_score.desc(), SavedLead.saved_at.desc())
                .limit(limit)
                .offset(offset)
            )
            .unique()
            .scalars()
            .all()
        )
        return list(rows), total


def get_saved(lead_id: str) -> Optional[SavedLead]:
    with session_scope() as db:
        return db.execute(
            select(SavedLead).where(SavedLead.lead_id == lead_id)
        ).scalar_one_or_none()


def saved_ids() -> set[str]:
    """Which leads are already saved — lets the UI show them as ticked."""
    with session_scope() as db:
        return set(db.execute(select(SavedLead.lead_id)).scalars().all())


def delete_saved(lead_id: str) -> bool:
    with session_scope() as db:
        row = db.execute(
            select(SavedLead).where(SavedLead.lead_id == lead_id)
        ).scalar_one_or_none()
        if row is None:
            return False
        db.delete(row)  # evidence cascades
        return True
