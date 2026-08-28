"""Business filtering + deduplication (spec §6, §34.5).

Runs before any expensive work so we never pay LLM or crawl cost for a business
that was never a candidate.

The spec's filters (§6) assume the scraper returns a broad spread of ratings. In
practice Google Maps surfaces prominent, well-rated businesses first, so a
narrow band like 3.0-4.0 routinely matches nothing — especially at small place
counts. Filtering therefore runs in passes: the strict filter first, then
progressively relaxed ones until enough candidates survive.

Nothing is silently ignored. Every relaxation is reported so the caller can say
which rule was dropped, and the rating preference is not lost — it still shapes
`business_potential_score` in scoring_service, which peaks at 3.5 stars. A
relaxed 4.9-star business is kept, but it ranks below a 3.5-star one.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.models import Business, SearchRequest
from app.utils.text import normalize_business_name, slugify

log = logging.getLogger(__name__)


@dataclass
class FilterRules:
    """Which of the §6 filters are active in a given pass."""

    rating_range: bool = True
    minimum_reviews: bool = True
    category: bool = True
    contactable: bool = True


# Relaxed in this order: most arbitrary heuristic first, most useful last.
# A lead with no phone and no website is close to worthless to a sales rep, so
# contactability is the last thing to go.
RELAXATION_STEPS: list[tuple[str, str]] = [
    ("rating_range", "rating range"),
    ("minimum_reviews", "minimum review count"),
    ("category", "category match"),
    ("contactable", "contactability (phone or website)"),
]


@dataclass
class FilterReport:
    """Kept so the CLI and API can show where candidates were lost (§35)."""

    started: int = 0
    dropped: dict[str, int] = field(default_factory=dict)
    kept: int = 0
    relaxed: list[str] = field(default_factory=list)

    def drop(self, reason: str) -> None:
        self.dropped[reason] = self.dropped.get(reason, 0) + 1

    def summary(self) -> str:
        if self.dropped:
            detail = ", ".join(f"{k}: {v}" for k, v in sorted(self.dropped.items()))
            base = f"{self.started} -> {self.kept}  [dropped: {detail}]"
        else:
            base = f"{self.started} -> {self.kept} (nothing filtered out)"
        if self.relaxed:
            base += f"  [relaxed: {', '.join(self.relaxed)}]"
        return base

    @property
    def relaxation_warning(self) -> str | None:
        if not self.relaxed:
            return None
        return (
            "Too few businesses matched your filters, so these were relaxed to "
            f"return results: {', '.join(self.relaxed)}. Scoring still prefers "
            "businesses near 3.5 stars, so the ranking is unchanged."
        )


def _category_matches(business: Business, wanted: str) -> bool:
    """Loose match: the scraper's category vocabulary rarely equals the user's words."""
    wanted_tokens = {t for t in slugify(wanted).split() if len(t) > 3}
    if not wanted_tokens:
        return True
    haystack = slugify(" ".join([business.category, *business.categories, business.name]))
    return any(token in haystack for token in wanted_tokens)


def _single_pass(
    businesses: list[Business], request: SearchRequest, rules: FilterRules
) -> tuple[list[Business], FilterReport]:
    report = FilterReport(started=len(businesses))
    seen: dict[str, Business] = {}

    for b in businesses:
        # Always enforced: a closed business is never a lead.
        if b.permanently_closed:
            report.drop("closed")
            continue

        if rules.rating_range:
            if b.rating is None:
                report.drop("no_rating")
                continue
            if not (request.min_rating <= b.rating <= request.max_rating):
                report.drop("rating_out_of_range")
                continue

        if rules.minimum_reviews and b.review_count < request.minimum_reviews:
            report.drop("too_few_reviews")
            continue

        if rules.category and not _category_matches(b, request.category):
            report.drop("category_mismatch")
            continue

        if rules.contactable and not (b.phone or b.website):
            report.drop("not_contactable")
            continue

        # §34.5 dedup — always on, and never the reason a search returns nothing.
        key = normalize_business_name(b.name, b.city)
        existing = seen.get(key)
        if existing is None:
            seen[key] = b
        else:
            report.drop("duplicate")
            if b.review_count > existing.review_count:
                seen[key] = b  # keep the richer duplicate

    kept = sorted(seen.values(), key=lambda x: x.review_count, reverse=True)
    report.kept = len(kept)
    return kept, report


def filter_businesses(
    businesses: list[Business], request: SearchRequest
) -> tuple[list[Business], FilterReport]:
    """Filter to candidates, relaxing rules rather than returning nothing.

    Set `request.strict_filters = True` to disable relaxation and get the
    literal §6 behaviour.
    """
    rules = FilterRules()
    kept, report = _single_pass(businesses, request, rules)

    target = max(request.limit, 1)
    if getattr(request, "strict_filters", False):
        log.info("business filter (strict): %s", report.summary())
        return kept, report

    relaxed_labels: list[str] = []
    for attr, label in RELAXATION_STEPS:
        if len(kept) >= target:
            break
        setattr(rules, attr, False)
        relaxed_labels.append(label)
        kept, report = _single_pass(businesses, request, rules)
        report.relaxed = list(relaxed_labels)

    log.info("business filter: %s", report.summary())
    return kept, report
