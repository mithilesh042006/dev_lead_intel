"""HTTP request/response schemas (spec §26).

Kept separate from the domain models in app/models.py so the wire format can
change without disturbing the pipeline, and so raw review dumps are never
serialised into a list response by accident.
"""
from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.models import Lead


def lead_id_for(place_id: str) -> str:
    """Stable id for a lead within a job — derived, so it survives re-runs."""
    return hashlib.sha256(place_id.encode("utf-8")).hexdigest()[:12]


# --- Requests -------------------------------------------------------------- #


class SearchBody(BaseModel):
    """§26 POST /api/search"""

    location: str = Field(min_length=2, max_length=120)
    category: str = Field(min_length=2, max_length=120)
    min_rating: float = Field(default=3.0, ge=0, le=5)
    max_rating: float = Field(default=4.0, ge=0, le=5)
    minimum_reviews: int = Field(default=20, ge=0, le=100_000)
    limit: int = Field(default=5, ge=1, le=25)
    # Bounded deliberately: this is the knob that spends Apify credits.
    max_places: Optional[int] = Field(default=None, ge=1, le=50)
    # Off by default: a search that returns nothing is worse than one that
    # returns lower-confidence leads and says which rule it dropped.
    strict_filters: bool = False

    @field_validator("max_rating")
    @classmethod
    def _range_is_ordered(cls, v: float, info):
        low = info.data.get("min_rating")
        if low is not None and v < low:
            raise ValueError("max_rating must be greater than or equal to min_rating")
        return v


# --- Responses ------------------------------------------------------------- #


class EvidenceOut(BaseModel):
    """§12 — an interpretation is never returned without its source review."""

    review_text: str
    review_rating: Optional[float] = None
    review_date: Optional[datetime] = None
    review_url: Optional[str] = None
    pain_point: str
    pain_category: str
    severity: str
    customer_impact: str
    business_impact: str
    recommended_solution: str
    confidence: float


class ScoresOut(BaseModel):
    software_pain_score: float
    business_potential_score: float
    review_evidence_score: float
    digital_presence_score: float
    contactability_score: float
    lead_score: int
    priority: str
    notes: list[str]


class LeadOut(BaseModel):
    lead_id: str
    company_name: str
    category: str
    rating: Optional[float]
    total_reviews: int
    phone: Optional[str]
    email: Optional[str]
    website: Optional[str]
    address: str
    city: str
    google_maps_url: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]

    pain_point: str
    pain_category: str
    pain_severity: str
    customer_impact: str
    business_impact: str
    confidence: float

    primary_opportunity: str
    secondary_opportunities: list[str]

    technology_signals: list[str]
    website_reachable: bool

    scores: ScoresOut
    sales_pitch: str
    evidence: list[EvidenceOut]

    @classmethod
    def from_lead(cls, lead: Lead) -> "LeadOut":
        b = lead.business
        top = lead.top_analysis
        tech = lead.website_info.tech
        signals = [s for s in tech.as_csv_field().split("; ") if s]

        return cls(
            lead_id=lead_id_for(b.place_id),
            company_name=b.name,
            category=b.category,
            rating=b.rating,
            total_reviews=b.review_count,
            phone=b.phone,
            email=b.email,
            website=b.website,
            address=b.address,
            city=b.city,
            google_maps_url=b.google_maps_url,
            latitude=b.latitude,
            longitude=b.longitude,
            pain_point=top.pain_point if top else "",
            pain_category=top.pain_category if top else "",
            pain_severity=top.severity if top else "",
            customer_impact=top.customer_impact if top else "",
            business_impact=top.business_impact if top else "",
            confidence=round(top.confidence, 2) if top else 0.0,
            primary_opportunity=lead.opportunity.primary_opportunity,
            secondary_opportunities=lead.opportunity.secondary_opportunities,
            technology_signals=signals,
            website_reachable=lead.website_info.reachable,
            scores=ScoresOut(**lead.scores.model_dump()),
            sales_pitch=lead.sales_pitch,
            evidence=[
                EvidenceOut(
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
            ],
        )


class JobOut(BaseModel):
    """§26 GET /api/jobs/{job_id}"""

    job_id: str
    status: str
    stage: str
    message: str
    progress: int
    location: str
    category: str
    min_rating: float
    max_rating: float
    minimum_reviews: int
    requested_leads: int
    created_at: datetime
    completed_at: Optional[datetime]
    lead_count: int
    warnings: list[str]
    stats: dict
    has_csv: bool


class SearchAccepted(BaseModel):
    job_id: str
    status: str


class LeadsResponse(BaseModel):
    job_id: str
    status: str
    count: int
    leads: list[LeadOut]


# --- Saved leads (§28) ----------------------------------------------------- #


class SaveLeadsBody(BaseModel):
    """The Save-selected action: a job plus the leads ticked in the UI."""

    job_id: str
    lead_ids: list[str] = Field(min_length=1, max_length=100)


class SaveLeadsResult(BaseModel):
    created: int
    updated: int
    lead_ids: list[str]


class SavedLeadOut(LeadOut):
    """A saved lead is a LeadOut plus where and when it was kept.

    Inheriting means the sessions list and a live search render through the same
    contract, so the frontend needs no second code path.
    """

    source_location: str = ""
    source_category: str = ""
    llm_model: Optional[str] = None
    saved_at: datetime


class SavedLeadsResponse(BaseModel):
    total: int
    count: int
    leads: list[SavedLeadOut]


def saved_lead_to_out(row) -> SavedLeadOut:
    """Rebuild the API shape from a persisted row."""
    return SavedLeadOut(
        lead_id=row.lead_id,
        company_name=row.company_name,
        category=row.category,
        rating=row.rating,
        total_reviews=row.total_reviews,
        phone=row.phone,
        email=row.email,
        website=row.website,
        address=row.address,
        city=row.city,
        google_maps_url=row.google_maps_url,
        latitude=row.latitude,
        longitude=row.longitude,
        pain_point=row.pain_point,
        pain_category=row.pain_category,
        pain_severity=row.pain_severity,
        customer_impact=row.customer_impact,
        business_impact=row.business_impact,
        confidence=row.confidence,
        primary_opportunity=row.primary_opportunity,
        secondary_opportunities=list(row.secondary_opportunities or []),
        technology_signals=list(row.technology_signals or []),
        website_reachable=row.website_reachable,
        scores=ScoresOut(
            software_pain_score=row.software_pain_score,
            business_potential_score=row.business_potential_score,
            review_evidence_score=row.review_evidence_score,
            digital_presence_score=row.digital_presence_score,
            contactability_score=row.contactability_score,
            lead_score=row.lead_score,
            priority=row.priority,
            notes=list(row.score_notes or []),
        ),
        sales_pitch=row.sales_pitch,
        evidence=[
            EvidenceOut(
                review_text=e.review_text,
                review_rating=e.review_rating,
                review_date=e.review_date,
                review_url=e.review_url,
                pain_point=e.pain_point,
                pain_category=e.pain_category,
                severity=e.severity,
                customer_impact=e.customer_impact,
                business_impact=e.business_impact,
                recommended_solution=e.recommended_solution,
                confidence=e.confidence,
            )
            for e in row.evidence
        ],
        source_location=row.source_location,
        source_category=row.source_category,
        llm_model=row.llm_model,
        saved_at=row.saved_at,
    )
