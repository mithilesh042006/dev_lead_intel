"""End-to-end MVP pipeline (spec §25, §40).

    1-4  user input                     -> SearchRequest
    5    Apify search                   -> ApifyProvider
    6    business filtering             -> filtering.filter_businesses
    7    reviews collected              -> arrive with the Apify run
    8    problem reviews identified     -> review_filter.prefilter_reviews
    9    LLM analysis                   -> LLMService.analyze_reviews
    10   website checked                -> website_service.analyze_many
    11   email/contact extracted        -> validators
    12   software opportunity           -> LLMService.detect_opportunity
    13   lead score                     -> scoring_service.score_lead
    14   cold-call pitch                -> LLMService.generate_pitch
    15   CSV                            -> export_service.export_leads

Failure handling follows §35: one business failing never stops the job.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from app.config import settings
from app.models import Business, Lead, SearchRequest
from app.providers.apify_provider import ApifyProvider
from app.providers.base import MapsProvider
from app.services import filtering, review_filter, scoring_service, website_service
from app.services.export_service import export_leads
from app.services.llm_service import LLMFatalError, LLMQuotaError, LLMService
from app.utils.validators import pick_best_email

log = logging.getLogger(__name__)

ProgressFn = Callable[[str, str], None]


@dataclass
class PipelineResult:
    leads: list[Lead] = field(default_factory=list)
    csv_path: Optional[Path] = None
    evidence_path: Optional[Path] = None
    status: str = "completed"
    warnings: list[str] = field(default_factory=list)
    stats: dict = field(default_factory=dict)


def _noop(stage: str, message: str) -> None:
    log.info("[%s] %s", stage, message)


class LeadPipeline:
    def __init__(
        self,
        provider: MapsProvider | None = None,
        llm: LLMService | None = None,
        progress: ProgressFn | None = None,
    ):
        self.provider = provider or ApifyProvider()
        self.llm = llm or LLMService()
        self.progress = progress or _noop

    # ------------------------------------------------------------------ #

    def run(self, request: SearchRequest, validate_email_mx: bool = True) -> PipelineResult:
        result = PipelineResult()

        # --- Steps 5 & 7: search + reviews in one actor run --------------
        max_places = request.max_places or max(
            settings.max_places_per_search, request.limit * 2
        )
        self.progress("search", f"searching {request.category} in {request.location}")
        try:
            businesses = self.provider.search_businesses(
                query=request.category,
                location=request.location,
                max_places=max_places,
                max_reviews=settings.max_reviews_per_place,
            )
        except Exception as exc:  # §35 — Apify failed, nothing to salvage
            log.exception("provider search failed")
            result.status = "failed"
            result.warnings.append(f"provider search failed: {exc}")
            return result

        self.progress("search", f"{len(businesses)} businesses returned")
        if not businesses:
            result.status = "empty"
            result.warnings.append("provider returned no businesses for this query")
            return result

        # --- Step 6: filtering + dedup -----------------------------------
        candidates, report = filtering.filter_businesses(businesses, request)
        self.progress("filter", report.summary())
        result.stats["filter"] = report.summary()

        if report.relaxation_warning:
            result.warnings.append(report.relaxation_warning)

        if not candidates:
            result.status = "empty"
            result.warnings.append(
                "No business survived filtering, even with all optional filters "
                "relaxed. The search itself returned nothing usable — try a "
                "broader category or a larger 'places to scrape'."
            )
            return result

        # Rank candidates before spending LLM budget (§40 step 3): review volume
        # is the cheapest available proxy for "worth analysing".
        candidates = candidates[: max(request.limit * 3, request.limit)]

        # --- Step 10: websites, all at once (§34.1) ----------------------
        self.progress("website", f"analysing {len(candidates)} websites concurrently")
        try:
            site_map = asyncio.run(website_service.analyze_many(candidates))
        except Exception as exc:
            log.warning("website stage failed wholesale: %s", exc)
            result.warnings.append(f"website analysis unavailable: {exc}")
            site_map = {}

        # --- Steps 8, 9, 11, 12, 14 per business -------------------------
        leads: list[Lead] = []
        for index, business in enumerate(candidates, start=1):
            label = f"{index}/{len(candidates)} {business.name}"
            try:
                lead = self._build_lead(business, site_map.get(business.place_id),
                                        validate_email_mx)
                leads.append(lead)
                self.progress(
                    "analyse",
                    f"{label} -> score {lead.scores.lead_score} {lead.scores.priority}",
                )
            except LLMFatalError as exc:
                # A bad key or retired model will fail identically for every
                # business — stop rather than burn the whole candidate list.
                result.status = "partial"
                result.warnings.append(f"LLM unavailable, stopped early: {exc}")
                log.error("fatal LLM error, aborting analysis loop: %s", exc)
                break
            except Exception as exc:  # §35 — never stop the job for one business
                result.status = "partial"
                result.warnings.append(f"{business.name}: {exc}")
                log.warning("business failed, continuing: %s -> %s", business.name, exc)

        if not leads:
            result.status = "failed" if result.status != "empty" else result.status
            result.warnings.append("no lead could be assembled")
            return result

        # --- Step 13 + 8 (§40): rank and cut to the requested count ------
        leads.sort(key=lambda l: l.scores.lead_score, reverse=True)
        top = leads[: request.limit]

        # --- Steps 12 & 14: only for the leads we actually return --------
        for lead in top:
            # Every returned lead gets an opportunity and a pitch, including
            # those with no complaint in their reviews — those fall back to a
            # recommendation built from observed capability gaps.
            try:
                lead.opportunity = self.llm.detect_opportunity(
                    lead.business, lead.analyses, lead.website_info.tech
                )
                lead.sales_pitch = self.llm.generate_pitch(
                    lead.business, lead.top_analysis, lead.opportunity, lead.website_info.tech
                )
            except LLMQuotaError:
                result.status = "partial"
                result.warnings.append(
                    "Gemini daily free-tier quota exhausted (20 requests/day per "
                    "model). Leads and scores are complete; pitches are missing for "
                    "the remaining leads. Switch LLM_MODEL or wait for the reset."
                )
                log.error("LLM quota exhausted, skipping remaining pitches")
                break
            except Exception as exc:
                result.status = "partial"
                result.warnings.append(f"pitch failed for {lead.business.name}: {exc}")
                log.warning("pitch generation failed for %s: %s", lead.business.name, exc)

        # --- Step 15: CSV ------------------------------------------------
        csv_path, evidence_path = export_leads(top)
        result.leads = top
        result.csv_path = csv_path
        result.evidence_path = evidence_path
        result.stats["analysed"] = len(leads)
        result.stats["returned"] = len(top)
        result.stats["llm_calls"] = self.llm.calls_made
        return result

    # ------------------------------------------------------------------ #

    def _build_lead(self, business: Business, site_info, validate_email_mx: bool) -> Lead:
        from app.models import WebsiteInfo

        website_info = site_info or WebsiteInfo(url=business.website, reachable=False)

        # --- Step 11: email (§15). Never fabricated from the domain. -----
        if website_info.emails:
            business.email = pick_best_email(website_info.emails, check_mx=validate_email_mx)
        if not business.phone and website_info.phones:
            business.phone = website_info.phones[0]

        # --- Step 8: pre-filter before spending tokens (§10) -------------
        pre = review_filter.prefilter_reviews(
            business.reviews, limit=settings.max_llm_reviews_per_business
        )

        # --- Step 9: batched LLM analysis (§34.3) ------------------------
        analyses = self.llm.analyze_reviews(business, pre.reviews) if pre.reviews else []

        lead = Lead(business=business, website_info=website_info, analyses=analyses)

        # Step 12 (opportunity) is deliberately NOT run here. Scoring does not
        # depend on it, so deferring it to the ranked top-N saves one LLM call
        # for every candidate that gets cut — which matters on a free tier
        # capped at 20 requests per day.

        # --- Step 13: scoring (§16/§29) ----------------------------------
        lead.scores = scoring_service.score_lead(lead)
        return lead
