"""Offline sample provider for --dry-run.

Lets the full pipeline (filter -> prefilter -> LLM -> score -> CSV) be exercised
without spending Apify credits. Useful for tuning prompts and scoring weights.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.models import Business, Review
from app.providers.base import MapsProvider


def _days_ago(n: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=n)


_RAW = [
    {
        "place_id": "sample-abc-fashion",
        "name": "ABC Fashion",
        "category": "Clothing store",
        "rating": 3.6,
        "review_count": 218,
        "phone": "+914412345678",
        "website": "https://example.com",
        "address": "12 T Nagar Main Road, Chennai",
        "city": "Chennai",
        "reviews": [
            ("Good collection but billing took almost 30 minutes. Only one counter was open.", 2, 40),
            ("Nice clothes, decent prices.", 5, 60),
            ("The website showed the shirt as available but the store said it was out of stock.", 2, 90),
            ("Staff were helpful but the queue at the counter was very long on Sunday.", 3, 120),
            ("Called the store four times to ask about an exchange, nobody picked up.", 1, 20),
            ("Parking is difficult.", 3, 200),
        ],
    },
    {
        "place_id": "sample-xyz-clothing",
        "name": "XYZ Clothing Store",
        "category": "Clothing store",
        "rating": 3.8,
        "review_count": 97,
        "phone": "+914498765432",
        "website": "",
        "address": "45 Anna Salai, Chennai",
        "city": "Chennai",
        "reviews": [
            ("Ordered online and paid but the order never got confirmed. Had to call to sort it out.", 1, 30),
            ("Fabric quality is poor for the price.", 2, 75),
            ("They keep no record of past purchases so exchanges are a nightmare.", 2, 55),
            ("Lovely store.", 5, 15),
        ],
    },
    {
        "place_id": "sample-style-world",
        "name": "Style World",
        "category": "Clothing store",
        "rating": 3.5,
        "review_count": 142,
        "phone": "",
        "website": "https://example.org",
        "address": "8 Velachery Road, Chennai",
        "city": "Chennai",
        "reviews": [
            ("Their website has been down for weeks, cannot check anything online.", 2, 25),
            ("Delivery was three weeks late and there was no way to track it.", 1, 45),
            ("Rude staff.", 1, 100),
        ],
    },
    {
        "place_id": "sample-too-few",
        "name": "Tiny Boutique",
        "category": "Clothing store",
        "rating": 3.7,
        "review_count": 4,  # filtered out by minimum_reviews
        "phone": "+914400000000",
        "website": "",
        "address": "1 Side Street, Chennai",
        "city": "Chennai",
        "reviews": [("Small shop, billing is slow.", 3, 10)],
    },
    {
        "place_id": "sample-too-good",
        "name": "Premium Threads",
        "category": "Clothing store",
        "rating": 4.8,  # filtered out by rating range
        "review_count": 310,
        "phone": "+914411111111",
        "website": "https://example.net",
        "address": "9 ECR, Chennai",
        "city": "Chennai",
        "reviews": [("Excellent service.", 5, 10)],
    },
]


def _build(raw: dict) -> Business:
    return Business(
        place_id=raw["place_id"],
        name=raw["name"],
        category=raw["category"],
        categories=[raw["category"]],
        rating=raw["rating"],
        review_count=raw["review_count"],
        phone=raw["phone"] or None,
        website=raw["website"] or None,
        address=raw["address"],
        city=raw["city"],
        latitude=13.0827,
        longitude=80.2707,
        google_maps_url=f"https://maps.google.com/?q={raw['place_id']}",
        reviews=[
            Review(text=text, rating=stars, review_date=_days_ago(age), source="sample")
            for text, stars, age in raw["reviews"]
        ],
    )


class SampleProvider(MapsProvider):
    name = "sample"

    def search_businesses(self, query, location, max_places, max_reviews):
        return [_build(r) for r in _RAW][:max_places]

    def get_business_details(self, place_id):
        for r in _RAW:
            if r["place_id"] == place_id:
                return _build(r)
        return None

    def get_reviews(self, place_id, limit):
        b = self.get_business_details(place_id)
        return b.reviews[:limit] if b else []
