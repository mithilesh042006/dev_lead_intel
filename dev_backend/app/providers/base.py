"""Maps provider abstraction (spec §5.2).

    MapsProvider
        |-- ApifyProvider
        `-- GooglePlacesProvider   (not implemented; see notes in README)
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from app.models import Business, Review


class MapsProvider(ABC):
    name: str = "base"

    @abstractmethod
    def search_businesses(
        self, query: str, location: str, max_places: int, max_reviews: int
    ) -> list[Business]:
        """Return businesses for a category+location, with reviews already attached
        when the provider supports it in a single call."""

    @abstractmethod
    def get_business_details(self, place_id: str) -> Business | None: ...

    @abstractmethod
    def get_reviews(self, place_id: str, limit: int) -> list[Review]: ...
