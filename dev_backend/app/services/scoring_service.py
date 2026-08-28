"""Lead scoring (spec §16, §17, §29).

The spec supplies the weights but not how each 0-100 subscore is produced, so
the rubric below fills that gap. Every subscore is derived from observable
facts and records a human-readable note explaining itself, because a sales rep
who cannot see why a lead scored 84 will not trust the number.
"""
from __future__ import annotations

import logging
import math
from datetime import datetime, timezone

from app.models import Business, Lead, Priority, ReviewAnalysis, ScoreBreakdown, WebsiteInfo

log = logging.getLogger(__name__)

# §29 weights
WEIGHTS = {
    "software_pain_score": 0.40,
    "business_potential_score": 0.25,
    "review_evidence_score": 0.20,
    "digital_presence_score": 0.10,
    "contactability_score": 0.05,
}

SEVERITY_VALUE = {"high": 100.0, "medium": 65.0, "low": 35.0}

# §16 assumes a business with some scale is worth calling. Reviews are the only
# size proxy Maps gives us, so it is used on a log scale.
REVIEW_VOLUME_SATURATION = 500

# The 3.0-4.0 band in the spec's own example is the sweet spot: enough
# dissatisfaction to have a problem, enough traction to afford a fix.
IDEAL_RATING = 3.5


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _months_since(when: datetime | None) -> float | None:
    if when is None:
        return None
    now = datetime.now(timezone.utc)
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return max(0.0, (now - when).days / 30.44)


# --- §16 subscores --------------------------------------------------------- #


def software_pain_score(analyses: list[ReviewAnalysis]) -> tuple[float, str]:
    """40% — how badly does this business need software?

    Weighted toward the single worst confirmed problem (that is what gets sold),
    with a smaller term for breadth, because three distinct problems is a bigger
    engagement than one.
    """
    software = [a for a in analyses if a.software_related]
    if not software:
        return 0.0, "no software-related pain detected"

    top = max(software, key=lambda a: SEVERITY_VALUE.get(a.severity, 0) * a.confidence)
    top_value = SEVERITY_VALUE.get(top.severity, 35.0) * max(top.confidence, 0.1)

    distinct_categories = {a.pain_category for a in software}
    breadth = min(len(distinct_categories) / 3.0, 1.0) * 100.0

    score = _clamp(0.70 * top_value + 0.30 * breadth)
    note = (
        f"pain: {len(software)} software review(s) across "
        f"{len(distinct_categories)} categor(ies); worst = {top.severity} "
        f"@ {top.confidence:.0%} confidence"
    )
    return score, note


def business_potential_score(business: Business) -> tuple[float, str]:
    """25% — can they afford it, and are they the right kind of unhappy?"""
    volume = _clamp(40.0 * math.log10(max(business.review_count, 1) + 1))

    rating = business.rating if business.rating is not None else IDEAL_RATING
    rating_fit = _clamp(100.0 - abs(rating - IDEAL_RATING) * 40.0)

    score = _clamp(0.60 * volume + 0.40 * rating_fit)
    note = (
        f"potential: {business.review_count} reviews (volume {volume:.0f}), "
        f"rating {rating:.1f} (fit {rating_fit:.0f})"
    )
    return score, note


def review_evidence_score(
    analyses: list[ReviewAnalysis], focus_category: str | None = None
) -> tuple[float, str]:
    """20% — §12. How well-evidenced is the claim we are about to make?

    One vague review is a guess. Three recent, specific, mutually consistent
    reviews is a finding.

    `focus_category` is the pain point the lead actually leads with, so the
    score measures corroboration of *that* claim rather than of whichever theme
    happens to be most frequent. Without it the note could cite one category
    while the pitch sells another.
    """
    software = [a for a in analyses if a.software_related]
    if not software:
        return 0.0, "evidence: none"

    top_category = focus_category or max(
        {a.pain_category for a in software},
        key=lambda c: sum(1 for a in software if a.pain_category == c),
    )
    supporting = [a for a in software if a.pain_category == top_category] or software

    support = min(len(supporting) / 3.0, 1.0) * 100.0
    confidence = (sum(a.confidence for a in supporting) / len(supporting)) * 100.0

    ages = [m for m in (_months_since(a.evidence_date) for a in supporting) if m is not None]
    if not ages:
        recency = 50.0  # unknown date is neither fresh nor stale
        recency_note = "dates unknown"
    else:
        newest = min(ages)
        recency = 100.0 if newest <= 12 else 60.0 if newest <= 24 else 30.0
        recency_note = f"newest {newest:.0f}mo old"

    score = _clamp(0.40 * support + 0.40 * confidence + 0.20 * recency)
    note = (
        f"evidence: {len(supporting)} review(s) on '{top_category}', "
        f"avg confidence {confidence:.0f}%, {recency_note}"
    )
    return score, note


def digital_presence_score(website: WebsiteInfo) -> tuple[float, str]:
    """10% — a business already investing in digital buys software more readily."""
    if not website.reachable:
        note = "digital: no reachable website"
        return (10.0 if website.url else 0.0), note

    tech = website.tech
    points = 40.0
    parts = ["website"]
    for flag, value, label in (
        (tech.ecommerce, 20.0, "e-commerce"),
        (tech.online_payment, 15.0, "payments"),
        (tech.online_ordering, 10.0, "online ordering"),
        (tech.booking, 10.0, "booking"),
        (tech.whatsapp, 5.0, "whatsapp"),
        (bool(tech.social_links), 5.0, "social"),
        (bool(tech.analytics), 5.0, "analytics"),
    ):
        if flag:
            points += value
            parts.append(label)

    note = "digital: " + ", ".join(parts)
    if tech.platforms:
        note += f" (on {', '.join(tech.platforms)})"
    return _clamp(points), note


def contactability_score(business: Business, website: WebsiteInfo) -> tuple[float, str]:
    """5% — can a rep actually reach them today?"""
    points = 0.0
    parts = []
    if business.phone:
        points += 50.0
        parts.append("phone")
    if business.email:
        points += 35.0
        parts.append("email")
    if business.website:
        points += 15.0
        parts.append("website")
    note = "contact: " + (", ".join(parts) if parts else "none")
    return _clamp(points), note


# --- §17 / §29 ------------------------------------------------------------- #


def classify_priority(score: float) -> Priority:
    if score >= 80:
        return "HOT"
    if score >= 60:
        return "WARM"
    if score >= 40:
        return "COLD"
    return "LOW"


def score_lead(lead: Lead) -> ScoreBreakdown:
    top = lead.top_analysis
    pain, pain_note = software_pain_score(lead.analyses)
    potential, potential_note = business_potential_score(lead.business)
    evidence, evidence_note = review_evidence_score(
        lead.analyses, focus_category=top.pain_category if top else None
    )
    digital, digital_note = digital_presence_score(lead.website_info)
    contact, contact_note = contactability_score(lead.business, lead.website_info)

    total = (
        pain * WEIGHTS["software_pain_score"]
        + potential * WEIGHTS["business_potential_score"]
        + evidence * WEIGHTS["review_evidence_score"]
        + digital * WEIGHTS["digital_presence_score"]
        + contact * WEIGHTS["contactability_score"]
    )
    final = int(round(total))

    return ScoreBreakdown(
        software_pain_score=round(pain, 1),
        business_potential_score=round(potential, 1),
        review_evidence_score=round(evidence, 1),
        digital_presence_score=round(digital, 1),
        contactability_score=round(contact, 1),
        lead_score=final,
        priority=classify_priority(final),
        notes=[pain_note, potential_note, evidence_note, digital_note, contact_note],
    )
