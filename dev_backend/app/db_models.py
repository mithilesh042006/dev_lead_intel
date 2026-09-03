"""ORM models for saved leads (spec §28).

A saved lead is the unit the sales team actually works with, so leads are
stored flat rather than hanging off a saved search. Each row keeps the search
context it came from (location, category, job) for reference, but nothing about
the row depends on that search still existing.

    saved_leads      one row per business the user chose to keep
    saved_evidence   one row per software-related review backing that lead

`lead_id` is unique: it derives from the Google place id, so saving the same
business twice updates the row instead of creating a duplicate. Re-saving after
a fresh search is how a rep refreshes a lead.

The stored row is a snapshot of the analysis when it was saved. Ratings move and
reviews get deleted, so a lead a rep already read and acted on must not silently
rewrite itself.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
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


class SavedLead(Base):
    """§28 `businesses` + `leads`, denormalised into one saved row."""

    __tablename__ = "saved_leads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Derived from the place id, so the same business is never stored twice.
    lead_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)

    # --- where this lead came from ---
    source_job_id: Mapped[str | None] = mapped_column(String(64))
    source_location: Mapped[str] = mapped_column(String(200), default="")
    source_category: Mapped[str] = mapped_column(String(200), default="")
    llm_model: Mapped[str | None] = mapped_column(String(80))

    # --- business (§28 businesses) ---
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
    priority: Mapped[str] = mapped_column(String(10), default="LOW", index=True)
    software_pain_score: Mapped[float] = mapped_column(Float, default=0.0)
    business_potential_score: Mapped[float] = mapped_column(Float, default=0.0)
    review_evidence_score: Mapped[float] = mapped_column(Float, default=0.0)
    digital_presence_score: Mapped[float] = mapped_column(Float, default=0.0)
    contactability_score: Mapped[float] = mapped_column(Float, default=0.0)
    score_notes: Mapped[list] = mapped_column(JSONB, default=list)

    saved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    evidence: Mapped[list["SavedEvidence"]] = relationship(
        back_populates="lead", cascade="all, delete-orphan", lazy="selectin"
    )
    followups: Mapped[list["LeadFollowUp"]] = relationship(
        back_populates="lead",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="LeadFollowUp.happened_on.desc(), LeadFollowUp.id.desc()",
    )


class SavedEvidence(Base):
    """§28 `reviews` + `review_analysis`.

    §12 requires a conclusion never be stored apart from the review that
    produced it, so each row carries both the original text and the reading.
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


# Methods a rep can log. Kept as a plain list rather than a database enum so
# adding one is a code change, not a migration.
FOLLOWUP_METHODS = ["Call", "Email", "WhatsApp", "SMS", "Meeting", "LinkedIn", "Other"]


class LeadFollowUp(Base):
    """A logged contact attempt against a saved lead.

    This is the human half of the product: the pipeline says who to call and
    why, and this records what happened when someone did.
    """

    __tablename__ = "lead_followups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lead_db_id: Mapped[int] = mapped_column(
        ForeignKey("saved_leads.id", ondelete="CASCADE"), index=True
    )

    happened_on: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    method: Mapped[str] = mapped_column(String(40), default="Call")
    outcome: Mapped[str] = mapped_column(String(300), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    next_followup_on: Mapped[date | None] = mapped_column(Date, index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    lead: Mapped[SavedLead] = relationship(back_populates="followups")
