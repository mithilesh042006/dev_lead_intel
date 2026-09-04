"""Saving and reading individual leads (spec §28).

Saving is explicit and per-lead: the user ticks the leads worth keeping and
presses Save. A search that returned five businesses where only one is worth
calling should put one row in the database, not five.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from typing import Optional
from uuid import uuid4

from sqlalchemy import func, select

from app.db import session_scope
from app.db_models import LeadFollowUp, SavedEvidence, SavedLead
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


# --- Follow-ups ------------------------------------------------------------ #


def _lead_row(db, lead_id: str) -> Optional[SavedLead]:
    return db.execute(
        select(SavedLead).where(SavedLead.lead_id == lead_id)
    ).scalar_one_or_none()


def list_followups(lead_id: str) -> Optional[list[LeadFollowUp]]:
    """None means the lead itself is not saved — distinct from 'no follow-ups'."""
    with session_scope() as db:
        row = _lead_row(db, lead_id)
        return None if row is None else list(row.followups)


def add_followup(lead_id: str, data: dict) -> Optional[LeadFollowUp]:
    with session_scope() as db:
        row = _lead_row(db, lead_id)
        if row is None:
            return None
        entry = LeadFollowUp(
            lead_db_id=row.id,
            happened_on=data["happened_on"],
            method=data.get("method") or "Call",
            outcome=(data.get("outcome") or "").strip(),
            notes=(data.get("notes") or "").strip(),
            next_followup_on=data.get("next_followup_on"),
        )
        db.add(entry)
        db.flush()
        db.refresh(entry)
        return entry


def delete_followup(lead_id: str, followup_id: int) -> bool:
    with session_scope() as db:
        row = _lead_row(db, lead_id)
        if row is None:
            return False
        entry = db.get(LeadFollowUp, followup_id)
        # Scope the delete to this lead so an id from another lead cannot be
        # removed by guessing.
        if entry is None or entry.lead_db_id != row.id:
            return False
        db.delete(entry)
        return True


# --- Dashboard ------------------------------------------------------------- #


def dashboard_stats(today: date, due_window_days: int = 7) -> dict:
    """Aggregate the saved-lead pipeline into what a rep needs to act on.

    Computed in Python over the loaded rows rather than in SQL. At a few hundred
    saved leads that is simpler and fast enough; past a few thousand this wants
    real aggregate queries.

    "Next due" is the date on a lead's MOST RECENT follow-up, not the earliest
    across all of them — it is what the rep last committed to, which is the only
    one still meaningful.
    """
    with session_scope() as db:
        leads = db.execute(select(SavedLead)).unique().scalars().all()

        priority_counts = {p: 0 for p in ("HOT", "WARM", "COLD", "LOW")}
        pain_counts: dict[str, int] = {}
        scores: list[int] = []
        total_followups = 0
        contacted = 0

        overdue: list[dict] = []
        due_soon: list[dict] = []
        uncontacted: list[dict] = []

        for lead in leads:
            priority_counts[lead.priority] = priority_counts.get(lead.priority, 0) + 1
            scores.append(lead.lead_score)
            if lead.pain_category:
                pain_counts[lead.pain_category] = pain_counts.get(lead.pain_category, 0) + 1

            followups = list(lead.followups)  # already ordered newest first
            total_followups += len(followups)

            ref = {
                "lead_id": lead.lead_id,
                "company_name": lead.company_name,
                "lead_score": lead.lead_score,
                "priority": lead.priority,
                "city": lead.city,
                "pain_category": lead.pain_category,
                "saved_at": lead.saved_at,
                "last_followup_on": None,
                "next_followup_on": None,
            }

            if not followups:
                uncontacted.append(ref)
                continue

            contacted += 1
            latest = followups[0]
            ref["last_followup_on"] = latest.happened_on
            ref["next_followup_on"] = latest.next_followup_on

            if latest.next_followup_on:
                delta = (latest.next_followup_on - today).days
                if delta < 0:
                    overdue.append(ref)
                elif delta <= due_window_days:
                    due_soon.append(ref)

        overdue.sort(key=lambda r: r["next_followup_on"])
        due_soon.sort(key=lambda r: r["next_followup_on"])
        # Worth-calling-first: highest score among those nobody has contacted.
        uncontacted.sort(key=lambda r: r["lead_score"], reverse=True)

        recent = sorted(
            (
                {
                    "lead_id": l.lead_id,
                    "company_name": l.company_name,
                    "lead_score": l.lead_score,
                    "priority": l.priority,
                    "city": l.city,
                    "pain_category": l.pain_category,
                    "saved_at": l.saved_at,
                    "last_followup_on": None,
                    "next_followup_on": None,
                }
                for l in leads
            ),
            key=lambda r: r["saved_at"],
            reverse=True,
        )[:5]

        return {
            "total_leads": len(leads),
            "average_score": round(sum(scores) / len(scores), 1) if scores else 0.0,
            "top_score": max(scores) if scores else 0,
            "by_priority": [
                {"priority": p, "count": priority_counts.get(p, 0)}
                for p in ("HOT", "WARM", "COLD", "LOW")
            ],
            "by_pain_category": [
                {"category": c, "count": n}
                for c, n in sorted(pain_counts.items(), key=lambda kv: -kv[1])[:8]
            ],
            "total_followups": total_followups,
            "leads_contacted": contacted,
            "leads_never_contacted": len(uncontacted),
            "overdue": overdue[:10],
            "due_soon": due_soon[:10],
            "needs_attention": uncontacted[:10],
            "recent": recent,
        }


# --- Manual entry ---------------------------------------------------------- #

# A manual lead has no review evidence, so there is nothing to compute a score
# from. The user states a priority instead and this is the score recorded for
# it — the midpoint of each §17 band, so manual leads sort sensibly alongside
# computed ones without pretending to a precision they do not have.
PRIORITY_NOMINAL_SCORE = {"HOT": 90, "WARM": 70, "COLD": 50, "LOW": 25}


def create_manual_lead(data: dict) -> SavedLead:
    """Insert a hand-entered lead. Always creates — never merges into another."""
    priority = data.get("priority") or "WARM"

    row = SavedLead(
        # No place id exists, so the id is random rather than derived. Two
        # manual entries for the same business are the user's call to make.
        lead_id=uuid4().hex[:12],
        is_manual=True,
        source_job_id=None,
        source_location=(data.get("city") or "").strip(),
        source_category=(data.get("category") or "").strip(),
        llm_model=None,
        company_name=data["company_name"].strip(),
        category=(data.get("category") or "").strip(),
        rating=data.get("rating"),
        total_reviews=data.get("total_reviews") or 0,
        phone=(data.get("phone") or "").strip() or None,
        email=(data.get("email") or "").strip() or None,
        website=(data.get("website") or "").strip() or None,
        address=(data.get("address") or "").strip(),
        city=(data.get("city") or "").strip(),
        google_maps_url=(data.get("google_maps_url") or "").strip() or None,
        pain_point=(data.get("pain_point") or "").strip(),
        pain_category=(data.get("pain_category") or "").strip(),
        pain_severity=(data.get("pain_severity") or "").strip(),
        customer_impact="",
        business_impact=(data.get("business_impact") or "").strip(),
        confidence=0.0,
        primary_opportunity=(data.get("primary_opportunity") or "").strip(),
        secondary_opportunities=[],
        technology_signals=[
            t.strip() for t in (data.get("technology_signals") or "").split(",") if t.strip()
        ],
        website_reachable=bool(data.get("website")),
        sales_pitch=(data.get("sales_pitch") or "").strip(),
        lead_score=PRIORITY_NOMINAL_SCORE.get(priority, 50),
        priority=priority,
        # Subscores stay at zero: nothing was measured. The note says so rather
        # than leaving a reader to assume the bars were computed.
        score_notes=["Entered manually — priority set by hand, not scored from review evidence."],
    )

    with session_scope() as db:
        db.add(row)
        db.flush()
        db.refresh(row)
        return row
