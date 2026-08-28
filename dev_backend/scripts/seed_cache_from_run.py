"""Seed the disk cache from an Apify run that already completed.

Use when a run succeeded on Apify's side but the pipeline failed afterwards —
the data is already paid for, so pull it into the cache instead of re-running.

    python scripts/seed_cache_from_run.py <run_id> \
        --category "Clothing Stores" --location "Chennai"

The run_input reconstructed here must match ApifyProvider.search_businesses
exactly, or the cache key will not line up.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from apify_client import ApifyClient  # noqa: E402

from app.config import settings  # noqa: E402
from app.providers import cache  # noqa: E402
from app.providers.apify_provider import _dataset_id, _scrub_personal_data  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_id")
    parser.add_argument("--category", required=True)
    parser.add_argument("--location", required=True)
    parser.add_argument("--max-places", type=int, default=settings.max_places_per_search)
    parser.add_argument("--max-reviews", type=int, default=settings.max_reviews_per_place)
    args = parser.parse_args()

    client = ApifyClient(settings.apify_api_token)
    run = client.run(args.run_id).get()
    if run is None:
        print(f"run {args.run_id} not found")
        return 1

    dataset_id = _dataset_id(run)
    items = _scrub_personal_data(list(client.dataset(dataset_id).iterate_items()))

    run_input = {
        "searchStringsArray": [args.category],
        "locationQuery": args.location,
        "maxCrawledPlacesPerSearch": args.max_places,
        "language": "en",
        "maxReviews": args.max_reviews,
        "reviewsSort": settings.reviews_sort,
        "scrapeReviewsPersonalData": False,
        "skipClosedPlaces": True,
        "maxImages": 0,
        "scrapePlaceDetailPage": True,
    }

    cache.put("apify_search", run_input, items)
    print(f"status:  {getattr(run, 'status', '?')}")
    print(f"cost:    ${getattr(run, 'usage_total_usd', '?')}")
    print(f"items:   {len(items)}")
    print(f"cached:  {cache.describe('apify_search', run_input)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
