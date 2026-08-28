"""Domain models. Mirrors the database schema in spec §28 without requiring a DB yet."""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

Severity = Literal["high", "medium", "low"]
Priority = Literal["HOT", "WARM", "COLD", "LOW"]

# Spec §8 — the fixed taxonomy the LLM must classify into.
PAIN_CATEGORIES = [
    "POS / Billing",
    "Inventory Management",
    "E-commerce",
    "Website",
    "Mobile App",
    "CRM",
    "Customer Communication",
    "WhatsApp Automation",
    "Booking / Appointment",
    "Delivery Management",
    "Payment Integration",
    "Order Management",
    "Loyalty / Rewards",
    "Marketing Automation",
    "Analytics / Reporting",
    "Employee Management",
    "Accounting Integration",
    "Other",
]


class Review(BaseModel):
    """§28 reviews"""

    external_id: Optional[str] = None
    rating: Optional[float] = None
    text: str = ""
    review_date: Optional[datetime] = None
    review_url: Optional[str] = None
    source: str = "google_maps"


class ReviewAnalysis(BaseModel):
    """§11 / §28 review_analysis — one LLM verdict, bound to its evidence review."""

    review_index: int
    software_related: bool = False
    pain_point: str = ""
    pain_category: str = "Other"
    severity: Severity = "low"
    customer_impact: str = ""
    business_impact: str = ""
    recommended_solution: str = ""
    solution_type: str = ""
    confidence: float = 0.0

    # §12 evidence — never separated from the interpretation above.
    evidence_text: str = ""
    evidence_rating: Optional[float] = None
    evidence_date: Optional[datetime] = None
    evidence_url: Optional[str] = None


class TechSignals(BaseModel):
    """§14"""

    has_website: bool = False
    ecommerce: bool = False
    online_ordering: bool = False
    booking: bool = False
    online_payment: bool = False
    whatsapp: bool = False
    platforms: list[str] = Field(default_factory=list)
    analytics: list[str] = Field(default_factory=list)
    social_links: list[str] = Field(default_factory=list)

    def as_csv_field(self) -> str:
        parts = list(self.platforms)
        for flag, label in (
            (self.ecommerce, "E-commerce"),
            (self.online_ordering, "Online Ordering"),
            (self.booking, "Booking"),
            (self.online_payment, "Online Payment"),
            (self.whatsapp, "WhatsApp"),
        ):
            if flag:
                parts.append(label)
        parts.extend(self.analytics)
        return "; ".join(dict.fromkeys(parts))


class WebsiteInfo(BaseModel):
    """§13"""

    url: Optional[str] = None
    reachable: bool = False
    title: str = ""
    description: str = ""
    emails: list[str] = Field(default_factory=list)
    phones: list[str] = Field(default_factory=list)
    tech: TechSignals = Field(default_factory=TechSignals)
    error: Optional[str] = None


class Business(BaseModel):
    """§28 businesses"""

    place_id: str
    name: str
    category: str = ""
    categories: list[str] = Field(default_factory=list)
    rating: Optional[float] = None
    review_count: int = 0
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    address: str = ""
    city: str = ""
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    google_maps_url: Optional[str] = None
    permanently_closed: bool = False

    reviews: list[Review] = Field(default_factory=list)


class Opportunity(BaseModel):
    """§18 / prompt 2"""

    primary_opportunity: str = ""
    secondary_opportunities: list[str] = Field(default_factory=list)
    sales_priority: str = "medium"
    rationale: str = ""


class ScoreBreakdown(BaseModel):
    """§16 / §29 — every subscore is explainable, not a black box."""

    software_pain_score: float = 0.0
    business_potential_score: float = 0.0
    review_evidence_score: float = 0.0
    digital_presence_score: float = 0.0
    contactability_score: float = 0.0
    lead_score: int = 0
    priority: Priority = "LOW"
    notes: list[str] = Field(default_factory=list)


class Lead(BaseModel):
    """§28 leads — the assembled output row."""

    business: Business
    website_info: WebsiteInfo = Field(default_factory=WebsiteInfo)
    analyses: list[ReviewAnalysis] = Field(default_factory=list)
    opportunity: Opportunity = Field(default_factory=Opportunity)
    scores: ScoreBreakdown = Field(default_factory=ScoreBreakdown)
    sales_pitch: str = ""

    @property
    def software_analyses(self) -> list[ReviewAnalysis]:
        return [a for a in self.analyses if a.software_related]

    @property
    def top_analysis(self) -> Optional[ReviewAnalysis]:
        """Highest-severity, highest-confidence software pain point."""
        rank = {"high": 3, "medium": 2, "low": 1}
        sw = self.software_analyses
        if not sw:
            return None
        return max(sw, key=lambda a: (rank.get(a.severity, 0), a.confidence))


class SearchRequest(BaseModel):
    """§26 POST /api/search body"""

    location: str
    category: str
    min_rating: float = 3.0
    max_rating: float = 4.0
    minimum_reviews: int = 20
    limit: int = 5
    max_places: Optional[int] = None
    # When False (default), filters relax rather than returning zero leads.
    strict_filters: bool = False
