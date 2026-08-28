"""Two-stage review pre-filter (spec §10).

Stage 1 is free and local. Only what survives it reaches the LLM, which is where
the money is. §9 matters here: "food was bad" is dissatisfaction, not a software
opportunity, and must not consume a token.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from app.models import Review
from app.utils.text import normalize_review_text

log = logging.getLogger(__name__)

# §10 keyword list, grouped so a hit can explain itself. Word-boundary matched,
# so "app" does not fire on "appreciate" and "call" does not fire on "called out".
KEYWORD_GROUPS: dict[str, list[str]] = {
    "POS / Billing": [
        "billing", "bill", "invoice", "counter", "queue", "checkout", "cashier",
        "long wait", "waiting", "slow", "cash only", "card machine",
    ],
    "Inventory Management": [
        "stock", "out of stock", "inventory", "availability", "available",
        "sold out", "not in stock", "size not",
    ],
    "E-commerce": [
        "online", "ecommerce", "e-commerce", "cart", "checkout page", "order online",
    ],
    "Website": [
        "website", "site", "web page", "webpage", "link", "login", "log in",
        "account", "portal", "loading", "error",
    ],
    "Mobile App": ["app", "application", "mobile app", "android", "ios"],
    "Customer Communication": [
        "no response", "did not respond", "never respond", "call", "calls",
        "phone", "customer care", "customer service", "support", "reply",
        "unreachable", "not picking",
    ],
    "WhatsApp Automation": ["whatsapp", "whats app", "message", "messages", "sms"],
    "Booking / Appointment": [
        "booking", "book", "appointment", "slot", "reservation", "reserve", "queue token",
    ],
    "Delivery Management": [
        "delivery", "deliver", "shipping", "shipment", "courier", "tracking",
        "track order", "late delivery",
    ],
    "Payment Integration": [
        "payment", "paytm", "upi", "gpay", "google pay", "card", "refund",
        "transaction", "failed payment", "not processed",
    ],
    "Order Management": ["order", "orders", "wrong item", "missing item", "return", "exchange"],
    "Loyalty / Rewards": ["loyalty", "points", "reward", "membership", "coupon", "offer code"],
    "Analytics / Reporting": ["receipt", "record", "report", "statement"],
    "System / Generic": ["system", "software", "digital", "server", "down", "technical", "glitch"],
}

_COMPILED: list[tuple[str, str, re.Pattern]] = [
    (category, kw, re.compile(rf"\b{re.escape(kw)}\b"))
    for category, kws in KEYWORD_GROUPS.items()
    for kw in kws
]

# §9 — complaints that are real but not ours to solve. Used only to break ties,
# never to hard-drop, because "bad food AND wrong order" is still a lead.
NON_SOFTWARE_HINTS = [
    "taste", "tasty", "food quality", "rude", "behaviour", "behavior", "dirty",
    "parking", "expensive", "price", "quality of cloth", "fabric", "smell",
]

MIN_TEXT_LENGTH = 25


@dataclass
class PreFilterResult:
    reviews: list[Review]
    total_seen: int
    deduped: int
    kept: int
    matched_categories: list[str]

    def summary(self) -> str:
        return (
            f"{self.total_seen} reviews -> {self.deduped} unique -> "
            f"{self.kept} potentially relevant"
        )


def _keyword_hits(text: str) -> tuple[list[str], list[str]]:
    lowered = f" {text.lower()} "
    categories, words = [], []
    for category, kw, pattern in _COMPILED:
        if pattern.search(lowered):
            categories.append(category)
            words.append(kw)
    return list(dict.fromkeys(categories)), list(dict.fromkeys(words))


def _score(review: Review, hit_count: int, text: str) -> float:
    """Rank survivors so the LLM budget goes to the most promising reviews first."""
    score = hit_count * 10.0
    if review.rating is not None:
        # A 1-star review with software keywords is the strongest signal (§9).
        score += max(0.0, (4.0 - review.rating)) * 12.0
    score += min(len(text), 600) / 60.0
    lowered = text.lower()
    score -= sum(3.0 for hint in NON_SOFTWARE_HINTS if hint in lowered)
    return score


def prefilter_reviews(reviews: list[Review], limit: int) -> PreFilterResult:
    total = len(reviews)

    # --- Deduplicate (§10) ---
    seen: set[str] = set()
    unique: list[Review] = []
    for r in reviews:
        key = normalize_review_text(r.text)
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(r)

    # --- Keyword / heuristic filtering (§10) ---
    scored: list[tuple[float, Review]] = []
    all_categories: list[str] = []
    for r in unique:
        text = (r.text or "").strip()
        if len(text) < MIN_TEXT_LENGTH:
            continue
        categories, words = _keyword_hits(text)
        if not words:
            continue
        all_categories.extend(categories)
        scored.append((_score(r, len(words), text), r))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    kept = [r for _, r in scored[:limit]]

    result = PreFilterResult(
        reviews=kept,
        total_seen=total,
        deduped=len(unique),
        kept=len(kept),
        matched_categories=list(dict.fromkeys(all_categories)),
    )
    log.info("review prefilter: %s", result.summary())
    return result
