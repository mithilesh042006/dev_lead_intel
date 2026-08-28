"""LLM analysis with structured output (spec §7, §11, §18, §19).

Every call is schema-constrained so the pipeline receives predictable data
instead of prose it has to parse. Reviews for one business are analysed in a
single batched call (§34.3), and results are cached per business (§34.4).
"""
from __future__ import annotations

import json
import logging

from google import genai
from google.genai import types
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config import BASE_DIR, settings
from app.models import (
    PAIN_CATEGORIES,
    Business,
    Opportunity,
    Review,
    ReviewAnalysis,
    TechSignals,
)
from app.providers import cache

log = logging.getLogger(__name__)

PROMPT_DIR = BASE_DIR / "prompts"


def _load_prompt(name: str) -> str:
    return (PROMPT_DIR / name).read_text(encoding="utf-8")


# --- §11 JSON Schemas ------------------------------------------------------ #

REVIEW_ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "analyses": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "review_index": {"type": "integer"},
                    "software_related": {"type": "boolean"},
                    "pain_point": {"type": "string"},
                    "pain_category": {"type": "string", "enum": PAIN_CATEGORIES},
                    "severity": {"type": "string", "enum": ["high", "medium", "low"]},
                    "customer_impact": {"type": "string"},
                    "business_impact": {"type": "string"},
                    "recommended_solution": {"type": "string"},
                    "solution_type": {"type": "string"},
                    "confidence": {"type": "number"},
                },
                "required": [
                    "review_index", "software_related", "pain_point", "pain_category",
                    "severity", "customer_impact", "business_impact",
                    "recommended_solution", "solution_type", "confidence",
                ],
            },
        }
    },
    "required": ["analyses"],
}

OPPORTUNITY_SCHEMA = {
    "type": "object",
    "properties": {
        "primary_opportunity": {"type": "string"},
        "secondary_opportunities": {"type": "array", "items": {"type": "string"}},
        "sales_priority": {"type": "string", "enum": ["high", "medium", "low"]},
        "rationale": {"type": "string"},
    },
    "required": [
        "primary_opportunity", "secondary_opportunities", "sales_priority", "rationale",
    ],
}


class LLMError(RuntimeError):
    """Transient failure — worth retrying (timeout, 429, 5xx)."""


class LLMFatalError(RuntimeError):
    """Permanent failure — bad key, unknown model, malformed request. Do not retry."""


class LLMQuotaError(LLMFatalError):
    """Daily free-tier quota exhausted. Retrying inside this run cannot help.

    Gemini's free tier allows 20 generate_content requests per day per model,
    so a full search of ~10 businesses can exhaust it. The quota is per model,
    so switching LLM_MODEL is the quickest workaround.
    """


# 404 = model retired, 400 = bad request, 401/403 = bad key. Retrying these
# just burns wall-clock; 429 and 5xx are the only ones worth a second attempt.
_FATAL_MARKERS = ("400", "401", "403", "404", "INVALID_ARGUMENT", "PERMISSION_DENIED")


class LLMService:
    def __init__(self, api_key: str | None = None, model: str | None = None):
        key = api_key or settings.gemini_api_key
        if not key:
            raise RuntimeError("GEMINI_API_KEY is not set (see .env.example)")
        self.model = model or settings.llm_model
        self.client = genai.Client(api_key=key)
        self.calls_made = 0

    # ------------------------------------------------------------------ #

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=20),
        retry=retry_if_exception_type(LLMError),
        reraise=True,
    )
    def _generate(self, system: str, user: str, schema: dict | None) -> str:
        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=settings.llm_temperature,
        )
        if schema is not None:
            config.response_mime_type = "application/json"
            config.response_schema = schema

        try:
            resp = self.client.models.generate_content(
                model=self.model, contents=user, config=config
            )
        except Exception as exc:
            message = str(exc)
            if "RESOURCE_EXHAUSTED" in message or "429" in message:
                raise LLMQuotaError(message) from exc
            if any(marker in message for marker in _FATAL_MARKERS):
                raise LLMFatalError(message) from exc
            raise LLMError(message) from exc

        self.calls_made += 1
        text = (resp.text or "").strip()
        if not text:
            raise LLMError("empty response from model")
        return text

    # --- §7 / §11 ------------------------------------------------------ #

    def analyze_reviews(self, business: Business, reviews: list[Review]) -> list[ReviewAnalysis]:
        if not reviews:
            return []

        cache_key = {
            "model": self.model,
            "place_id": business.place_id,
            "reviews": [r.text for r in reviews],
        }
        cached = cache.get("llm_reviews", cache_key)
        if cached is None:
            numbered = "\n\n".join(
                "[{}] (rating: {}) {}".format(
                    i, r.rating if r.rating is not None else "unknown", r.text
                )
                for i, r in enumerate(reviews)
            )
            user = (
                "Business: {}\nCategory: {}\nCity: {}\n\nReviews:\n\n{}".format(
                    business.name,
                    business.category or "unknown",
                    business.city or "unknown",
                    numbered,
                )
            )
            raw = self._generate(
                _load_prompt("review_analysis.txt"), user, REVIEW_ANALYSIS_SCHEMA
            )
            cached = json.loads(raw)
            cache.put("llm_reviews", cache_key, cached)

        return self._bind_evidence(cached.get("analyses", []), reviews)

    @staticmethod
    def _bind_evidence(raw_analyses: list[dict], reviews: list[Review]) -> list[ReviewAnalysis]:
        """§12 — an interpretation is never stored apart from the review it came from."""
        out: list[ReviewAnalysis] = []
        for raw in raw_analyses:
            idx = raw.get("review_index")
            if not isinstance(idx, int) or not (0 <= idx < len(reviews)):
                continue  # a hallucinated index has no evidence, so it is dropped
            review = reviews[idx]
            try:
                analysis = ReviewAnalysis(
                    **raw,
                    evidence_text=review.text,
                    evidence_rating=review.rating,
                    evidence_date=review.review_date,
                    evidence_url=review.review_url,
                )
            except Exception:
                continue
            analysis.confidence = max(0.0, min(1.0, analysis.confidence))
            out.append(analysis)
        return out

    # --- §18 ----------------------------------------------------------- #

    @staticmethod
    def _describe_gaps(tech: TechSignals) -> str:
        """State what is demonstrably missing, for the no-complaints path.

        Only observable facts go in here. An unreachable website yields "unknown",
        never "they have nothing" — §12's rule against inventing a problem applies
        just as much to gaps as it does to complaints.
        """
        if not tech.has_website:
            return (
                "- No website could be found or reached for this business\n"
                "- Online capabilities are therefore unknown"
            )

        lines = ["(No customer complaints were found. These are observed gaps.)"]
        for present, label in (
            (tech.ecommerce, "online catalogue or e-commerce"),
            (tech.online_payment, "online payment"),
            (tech.online_ordering, "online ordering"),
            (tech.booking, "booking or appointment system"),
            (tech.whatsapp, "WhatsApp customer messaging"),
        ):
            if not present:
                lines.append(f"- No {label} detected on their website")
        if tech.platforms:
            lines.append(f"- Existing platform: {', '.join(tech.platforms)}")
        if len(lines) == 1:
            lines.append("- No obvious capability gaps detected")
        return "\n".join(lines)

    def detect_opportunity(
        self, business: Business, analyses: list[ReviewAnalysis], tech: TechSignals
    ) -> Opportunity:
        software = [a for a in analyses if a.software_related]

        if software:
            problems = "\n".join(
                "- {} ({}, severity: {})".format(a.pain_point, a.pain_category, a.severity)
                for a in software
            )
        else:
            # No complaints is not a dead end — a missing capability is still a
            # sellable gap. It is a weaker signal than an actual complaint, and
            # the prompt is told to say so rather than imply anyone complained.
            problems = self._describe_gaps(tech)
        cache_key = {
            "model": self.model,
            "place_id": business.place_id,
            "problems": problems,
            "tech": tech.as_csv_field(),
        }
        cached = cache.get("llm_opportunity", cache_key)
        if cached is None:
            user = (
                "Business: {}\nCategory: {}\nExisting technology: {}\n"
                "Has website: {}\n\nObserved problems:\n{}".format(
                    business.name,
                    business.category or "unknown",
                    tech.as_csv_field() or "none detected",
                    "yes" if tech.has_website else "no",
                    problems,
                )
            )
            raw = self._generate(
                _load_prompt("opportunity_detection.txt"), user, OPPORTUNITY_SCHEMA
            )
            cached = json.loads(raw)
            cache.put("llm_opportunity", cache_key, cached)

        try:
            return Opportunity(**cached)
        except Exception:
            return Opportunity(
                sales_priority="low", rationale="Malformed opportunity response."
            )

    # --- §19 ----------------------------------------------------------- #

    def generate_pitch(
        self,
        business: Business,
        analysis: ReviewAnalysis | None,
        opportunity: Opportunity,
        tech: TechSignals | None = None,
    ) -> str:
        if not opportunity.primary_opportunity:
            return ""

        tech_summary = tech.as_csv_field() if tech else ""
        cache_key = {
            "model": self.model,
            "place_id": business.place_id,
            "pain": analysis.pain_point if analysis else "",
            "solution": opportunity.primary_opportunity,
        }
        cached = cache.get("llm_pitch", cache_key)
        if cached is None:
            if analysis is not None:
                situation = (
                    'Problem area: {} ({})\nEvidence from customer feedback: "{}"'.format(
                        analysis.pain_point,
                        analysis.pain_category,
                        analysis.evidence_text[:300],
                    )
                )
            else:
                # No complaint to quote. The pitch must lean on the capability
                # gap and must not imply a customer said anything.
                situation = (
                    "No customer complaints were found for this business.\n"
                    "Base the opening on the missing capability below."
                )

            user = (
                "Business: {}\nCategory: {}\n{}\n"
                "Recommended solution: {}\nExisting technology: {}".format(
                    business.name,
                    business.category or "retail business",
                    situation,
                    opportunity.primary_opportunity,
                    tech_summary or "none detected",
                )
            )
            text = self._generate(_load_prompt("sales_pitch.txt"), user, None)
            cached = {"pitch": text}
            cache.put("llm_pitch", cache_key, cached)

        return (cached.get("pitch") or "").strip()
