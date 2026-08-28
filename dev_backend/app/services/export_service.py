"""CSV export (spec §20).

The spec's schema mixes business-level columns with singular review columns, and
its example shows one row per business. That is the grain used here: one row per
lead, carrying the strongest pain point and the review that evidences it.

Because collapsing to one row would discard the other pain points, a second
evidence CSV is written alongside it with every analysed review. §12 requires
that the evidence survive; it must not be thrown away for the sake of a tidy
spreadsheet.
"""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

import pandas as pd

from app.config import settings
from app.models import Lead

log = logging.getLogger(__name__)

# §20 recommended CSV schema, in order.
LEAD_COLUMNS = [
    "company_name", "category", "rating", "total_reviews",
    "phone", "email", "website",
    "address", "city", "google_maps_url",
    "latitude", "longitude",
    "review_rating", "review_text", "review_date", "review_url",
    "pain_point", "pain_category", "pain_severity",
    "software_related", "software_problem", "customer_impact", "business_impact",
    "recommended_solution", "solution_type",
    "technology_signals",
    "lead_score", "lead_priority", "confidence",
    "sales_pitch",
]

EVIDENCE_COLUMNS = [
    "company_name", "google_maps_url", "review_rating", "review_date", "review_text",
    "software_related", "pain_point", "pain_category", "severity",
    "customer_impact", "business_impact", "recommended_solution", "confidence",
]


def _fmt_date(value: datetime | None) -> str:
    return value.date().isoformat() if value else ""


# Review text and pitches are user-generated content landing in a file that a
# sales rep will open in Excel. A review beginning with "=" or "@" would run as
# a formula, so leading formula triggers are neutralised with a zero-width-safe
# apostrophe. Phone numbers keep their leading "+" (CRMs need E.164) and are
# handled by the tab prefix instead, which Excel treats as text.
_FORMULA_TRIGGERS = ("=", "+", "-", "@", "\t", "\r")


def _sanitize(value):
    if not isinstance(value, str) or not value:
        return value
    if value.startswith(_FORMULA_TRIGGERS):
        return "'" + value
    return value


def _sanitize_frame(df: pd.DataFrame) -> pd.DataFrame:
    return df.map(_sanitize)


def lead_to_row(lead: Lead) -> dict:
    b = lead.business
    top = lead.top_analysis
    scores = lead.scores

    return {
        "company_name": b.name,
        "category": b.category,
        "rating": b.rating,
        "total_reviews": b.review_count,
        "phone": b.phone or "",
        "email": b.email or "",
        "website": b.website or "",
        "address": b.address,
        "city": b.city,
        "google_maps_url": b.google_maps_url or "",
        "latitude": b.latitude,
        "longitude": b.longitude,
        "review_rating": top.evidence_rating if top else "",
        "review_text": top.evidence_text if top else "",
        "review_date": _fmt_date(top.evidence_date) if top else "",
        "review_url": (top.evidence_url or "") if top else "",
        "pain_point": top.pain_point if top else "",
        "pain_category": top.pain_category if top else "",
        "pain_severity": top.severity if top else "",
        "software_related": bool(top),
        "software_problem": top.pain_point if top else "",
        "customer_impact": top.customer_impact if top else "",
        "business_impact": top.business_impact if top else "",
        "recommended_solution": lead.opportunity.primary_opportunity or (
            top.recommended_solution if top else ""
        ),
        "solution_type": top.solution_type if top else "",
        "technology_signals": lead.website_info.tech.as_csv_field(),
        "lead_score": scores.lead_score,
        "lead_priority": scores.priority,
        "confidence": round(top.confidence, 2) if top else 0.0,
        "sales_pitch": lead.sales_pitch,
    }


def evidence_rows(leads: list[Lead]) -> list[dict]:
    rows = []
    for lead in leads:
        for a in lead.analyses:
            rows.append({
                "company_name": lead.business.name,
                "google_maps_url": lead.business.google_maps_url or "",
                "review_rating": a.evidence_rating,
                "review_date": _fmt_date(a.evidence_date),
                "review_text": a.evidence_text,
                "software_related": a.software_related,
                "pain_point": a.pain_point,
                "pain_category": a.pain_category,
                "severity": a.severity,
                "customer_impact": a.customer_impact,
                "business_impact": a.business_impact,
                "recommended_solution": a.recommended_solution,
                "confidence": round(a.confidence, 2),
            })
    return rows


def export_leads(leads: list[Lead], slug: str = "leads") -> tuple[Path, Path]:
    settings.output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    leads_path = settings.output_dir / f"{slug}_{stamp}.csv"
    _sanitize_frame(
        pd.DataFrame([lead_to_row(l) for l in leads], columns=LEAD_COLUMNS)
    ).to_csv(leads_path, index=False, encoding="utf-8-sig")

    evidence_path = settings.output_dir / f"{slug}_{stamp}_evidence.csv"
    _sanitize_frame(
        pd.DataFrame(evidence_rows(leads), columns=EVIDENCE_COLUMNS)
    ).to_csv(evidence_path, index=False, encoding="utf-8-sig")

    log.info("exported %d leads -> %s", len(leads), leads_path.name)
    return leads_path, evidence_path
