"""Text normalisation helpers used by dedup and filtering (§34.5)."""
from __future__ import annotations

import re
import unicodedata

# Suffixes that make "ABC Fashion", "ABC Fashion Store" and "ABC Fashions
# Chennai" look like three businesses when they are one (§34.5).
_NOISE_WORDS = {
    "store", "stores", "shop", "shops", "showroom", "showrooms", "outlet",
    "outlets", "pvt", "private", "ltd", "limited", "llp", "inc", "co",
    "company", "the", "and",
}


def slugify(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = value.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _singularize(token: str) -> str:
    """Fold trivial plurals so "Fashion" and "Fashions" collapse together (§34.5).

    Deliberately naive — this only needs to match storefront names, not English.
    """
    if len(token) > 3 and token.endswith("s") and not token.endswith(("ss", "us", "is")):
        return token[:-1]
    return token


def normalize_business_name(name: str, city: str = "") -> str:
    """Collapse a display name to a comparable key."""
    slug = slugify(name)
    city_tokens = {_singularize(t) for t in slugify(city).split()}
    tokens = [
        s for t in slug.split()
        if not t.isdigit()
        for s in [_singularize(t)]
        if s not in _NOISE_WORDS and s not in city_tokens
    ]
    return " ".join(tokens) or slug


def normalize_review_text(text: str) -> str:
    return re.sub(r"\s+", " ", slugify(text))[:400]
