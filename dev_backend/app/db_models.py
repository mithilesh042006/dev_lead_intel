"""ORM models for saved sessions (spec §28).

The spec's §28 splits data across businesses / reviews / review_analysis /
leads / jobs. A saved session is a *snapshot* of one completed search, so the
shape here is session -> leads -> evidence:

    search_sessions   the search parameters and run outcome  (§28 jobs + leads)
    saved_leads       one row per returned lead              (§28 businesses + leads)
    saved_evidence    one row per software-related review    (§28 reviews + review_analysis)

Snapshot, not a live join: re-running the same search later must not silently
rewrite what a rep already saved and acted on. Ratings change, reviews get
deleted, and a saved session is a record of what was true when it was saved.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class SearchSession(Base):
    """One saved search. §28 `jobs`, plus the outcome."""

    __tablename__ = "search_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)

    # The job id is not unique: the same search may be saved twice on purpose.
    job_id: Mapped[str | None] = mapped_column(String(64), index=True)

    # --- search parameters (§26 request) ---
    location: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(200), nullable=False)
    min_rating: Mapped[float] = mapped_column(Float, default=0.0)
    max_rating: Mapped[float] = mapped_column(Float, default=5.0)
    minimum_reviews: Mapped[int] = mapped_column(Integer, default=0)
    requested_leads: Mapped[int] = mapped_column(Integer, default=0)
    max_places: Mapped[int | None] = mapped_column(Integer)
    strict_filters: Mapped[bool] = mapped_column(Boolean, default=False)

    # --- outcome ---
    status: Mapped[str] = mapped_column(String(32), default="completed")
    lead_count: Mapped[int] = mapped_column(Integer, default=0)
    hot_count: Mapped[int] = mapped_column(Integer, default=0)
    top_score: Mapped[int] = mapped_column(Integer, default=0)
    llm_model: Mapped[str | None] = mapped_column(String(80))
    warnings: Mapped[list] = mapped_column(JSONB, default=list)
    stats: Mapped[dict] = mapped_column(JSONB, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True
    )

    leads: Mapped[list["SavedLead"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="SavedLead.rank",
        lazy="selectin",
    )


class SavedLead(Base):
    """§28 `businesses` + `leads`, denormalised into the snapshot."""

    __tablename__ = "saved_leads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("search_sessions.id", ondelete="CASCADE"), index=True
    )
    rank: Mapped[int] = mapped_column(Integer, default=0)

    lead_id: Mapped[str] = mapped_column(String(32))
    company_name: Mapped[str] = mapped_column(String(300), nullable=False)
    category: Mapped[str] = mapped_column(String(200), default="")
    rating: Mapped[float | None] = mapped_column(Float)
    total_reviews: Mapped[int] = mapped_column(Integer, default=0)

    phone: Mapped[str | None] = mapped_column(String(60))
    email: Mapped[str | None] = mapped_column(String(200))
    website: Mapped[str | None] = mapped_column(Text)
    address: Mapped[str] = mapped_column(Text, default="")
    city: Mapped[str] = mapped_column(String(120), default="")
    google_maps_url: Mapped[str | None] = mapped_column(Text)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)

    # --- §33 fact ---
    pain_point: Mapped[str] = mapped_column(Text, default="")
    pain_category: Mapped[str] = mapped_column(String(80), default="")
    pain_severity: Mapped[str] = mapped_column(String(20), default="")
    customer_impact: Mapped[str] = mapped_column(Text, default="")
    business_impact: Mapped[str] = mapped_column(Text, default="")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)

    # --- §33 recommendation ---
    primary_opportunity: Mapped[str] = mapped_column(Text, default="")
    secondary_opportunities: Mapped[list] = mapped_column(JSONB, default=list)
    technology_signals: Mapped[list] = mapped_column(JSONB, default=list)
    website_reachable: Mapped[bool] = mapped_column(Boolean, default=False)
    sales_pitch: Mapped[str] = mapped_column(Text, default="")

    # --- §16 scores ---
    lead_score: Mapped[int] = mapped_column(Integer, default=0, index=True)
    priority: Mapped[str] = mapped_column(String(10), default="LOW")
    software_pain_score: Mapped[float] = mapped_column(Float, default=0.0)
    business_potential_score: Mapped[float] = mapped_column(Float, default=0.0)
    review_evidence_score: Mapped[float] = mapped_column(Float, default=0.0)
    digital_presence_score: Mapped[float] = mapped_column(Float, default=0.0)
    contactability_score: Mapped[float] = mapped_column(Float, default=0.0)
    score_notes: Mapped[list] = mapped_column(JSONB, default=list)

    session: Mapped[SearchSession] = relationship(back_populates="leads")
    evidence: Mapped[list["SavedEvidence"]] = relationship(
        back_populates="lead", cascade="all, delete-orphan", lazy="selectin"
    )


class SavedEvidence(Base):
    """§28 `reviews` + `review_analysis`.

    §12 requires that a conclusion never be stored apart from the review that
    produced it, so evidence rows carry both the original text and the reading
    of it.
    """

    __tablename__ = "saved_evidence"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lead_db_id: Mapped[int] = mapped_column(
        ForeignKey("saved_leads.id", ondelete="CASCADE"), index=True
    )

    # --- fact ---
    review_text: Mapped[str] = mapped_column(Text, default="")
    review_rating: Mapped[float | None] = mapped_column(Float)
    review_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_url: Mapped[str | None] = mapped_column(Text)

    # --- interpretation ---
    pain_point: Mapped[str] = mapped_column(Text, default="")
    pain_category: Mapped[str] = mapped_column(String(80), default="")
    severity: Mapped[str] = mapped_column(String(20), default="")
    customer_impact: Mapped[str] = mapped_column(Text, default="")
    business_impact: Mapped[str] = mapped_column(Text, default="")
    recommended_solution: Mapped[str] = mapped_column(Text, default="")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)

    lead: Mapped[SavedLead] = relationship(back_populates="evidence")


Index("ix_sessions_created_desc", SearchSession.created_at.desc())
