"""Apify implementation of MapsProvider (spec §5.2).

Uses the `compass/crawler-google-places` actor, which returns place details and
reviews from a single run — one billable operation instead of two.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

from apify_client import ApifyClient

from app.config import settings
from app.models import Business, Review
from app.providers import cache
from app.providers.base import MapsProvider

log = logging.getLogger(__name__)


def _parse_date(raw: Any) -> Optional[datetime]:
    if not raw:
        return None
    if isinstance(raw, datetime):
        return raw
    text = str(raw).replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


# §36 — the actor's scrapeReviewsPersonalData=False flag does not actually
# suppress these, so reviewer identity is stripped at the boundary before
# anything is cached to disk. The pipeline never needs it: §12 evidence is
# review text, rating and date.
_REVIEWER_PII_FIELDS = (
    "name", "reviewerId", "reviewerUrl", "reviewerPhotoUrl",
    "reviewerNumberOfReviews", "isLocalGuide", "reviewImageUrls",
)


def _scrub_personal_data(items: list[dict]) -> list[dict]:
    for item in items:
        for review in item.get("reviews") or []:
            for field in _REVIEWER_PII_FIELDS:
                review.pop(field, None)
    return items


def _dataset_id(run: Any) -> str | None:
    """apify-client >=3 returns a pydantic Run; older versions return a dict."""
    if isinstance(run, dict):
        return run.get("defaultDatasetId")
    return getattr(run, "default_dataset_id", None)


def _first_str(*values: Any) -> str:
    for v in values:
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


class ApifyProvider(MapsProvider):
    name = "apify"

    def __init__(self, token: str | None = None, actor_id: str | None = None):
        self.token = token or settings.apify_api_token
        if not self.token:
            raise RuntimeError("APIFY_API_TOKEN is not set (see .env.example)")
        self.actor_id = actor_id or settings.apify_actor_id
        self.client = ApifyClient(self.token)

    # ------------------------------------------------------------------ #

    def search_businesses(
        self, query: str, location: str, max_places: int, max_reviews: int
    ) -> list[Business]:
        run_input = {
            "searchStringsArray": [query],
            "locationQuery": location,
            "maxCrawledPlacesPerSearch": max_places,
            "language": "en",
            "maxReviews": max_reviews,
            "reviewsSort": settings.reviews_sort,
            # §36 — do not collect reviewer personal data we have no use for.
            "scrapeReviewsPersonalData": False,
            "skipClosedPlaces": True,
            "maxImages": 0,
            "scrapePlaceDetailPage": True,
        }

        cached = cache.get("apify_search", run_input)
        if cached is not None:
            log.info("cache hit: %s (0 credits spent)", cache.describe("apify_search", run_input))
            items = cached
        else:
            log.info("calling Apify actor %s (this spends credits)", self.actor_id)
            run = self.client.actor(self.actor_id).call(run_input=run_input)
            dataset_id = _dataset_id(run)
            if not dataset_id:
                raise RuntimeError(f"Apify run returned no dataset: {run!r}")
            items = _scrub_personal_data(list(self.client.dataset(dataset_id).iterate_items()))
            cache.put("apify_search", run_input, items)
            log.info(
                "Apify returned %d items (cost $%s) -> cached",
                len(items),
                getattr(run, "usage_total_usd", "?"),
            )

        return [self._to_business(i) for i in items if i.get("placeId") or i.get("title")]

    def get_business_details(self, place_id: str) -> Business | None:
        raise NotImplementedError(
            "search_businesses already returns full details; a per-place lookup "
            "would double the credit spend."
        )

    def get_reviews(self, place_id: str, limit: int) -> list[Review]:
        raise NotImplementedError(
            "Reviews arrive with search_businesses in the same actor run."
        )

    # ------------------------------------------------------------------ #

    def _to_business(self, item: dict) -> Business:
        loc = item.get("location") or {}
        categories = item.get("categories") or []

        return Business(
            place_id=_first_str(item.get("placeId"), item.get("fid"), item.get("title")),
            name=_first_str(item.get("title")),
            category=_first_str(item.get("categoryName"), categories[0] if categories else ""),
            categories=[c for c in categories if isinstance(c, str)],
            rating=item.get("totalScore"),
            review_count=int(item.get("reviewsCount") or 0),
            phone=_first_str(item.get("phoneUnformatted"), item.get("phone")) or None,
            website=_first_str(item.get("website")) or None,
            address=_first_str(item.get("address")),
            city=_first_str(item.get("city")),
            latitude=loc.get("lat"),
            longitude=loc.get("lng"),
            google_maps_url=_first_str(item.get("url")) or None,
            permanently_closed=bool(item.get("permanentlyClosed")),
            reviews=self._to_reviews(item.get("reviews") or []),
        )

    @staticmethod
    def _to_reviews(raw_reviews: list[dict]) -> list[Review]:
        out: list[Review] = []
        for r in raw_reviews:
            text = _first_str(r.get("text"), r.get("textTranslated"))
            if not text:
                continue  # a star-only review carries no evidence (§12)
            # This actor populates "stars" and leaves "rating" null; other
            # actors do the reverse. A null rating disables the negative-review
            # ranking in §9/§10, so both spellings are accepted.
            rating = r.get("stars")
            if rating is None:
                rating = r.get("rating")
            out.append(
                Review(
                    external_id=_first_str(r.get("reviewId")) or None,
                    rating=rating,
                    text=text,
                    review_date=_parse_date(r.get("publishedAtDate")),
                    review_url=_first_str(r.get("reviewUrl")) or None,
                    source="google_maps",
                )
            )
        return out
