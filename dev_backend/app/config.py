"""Central configuration (spec §31). All secrets come from .env, never from code."""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- Credentials ---
    apify_api_token: str = ""
    gemini_api_key: str = ""
    outscraper_api_key: str = ""
    google_maps_api_key: str = ""

    # --- LLM ---
    llm_model: str = "gemini-3.6-flash"
    llm_temperature: float = 0.2

    # --- Cost controls. These govern free-tier burn rate. ---
    max_places_per_search: int = 10
    max_reviews_per_place: int = 20
    # "lowestRanking" targets the negative reviews §9 actually cares about,
    # which cuts review credits spent on 5-star noise.
    reviews_sort: str = "lowestRanking"
    max_llm_reviews_per_business: int = 12

    # --- Website analysis (§13/§14) ---
    website_timeout: int = 12
    website_max_pages: int = 3
    website_concurrency: int = 8

    # --- Local paths ---
    cache_dir: Path = BASE_DIR / "data" / "cache"
    output_dir: Path = BASE_DIR / "data" / "out"
    cache_enabled: bool = True

    # --- Apify actor (§5.2) ---
    apify_actor_id: str = "compass/crawler-google-places"

    def ensure_dirs(self) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_dirs()
