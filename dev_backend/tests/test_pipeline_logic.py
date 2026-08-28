"""Tests for the deterministic stages. No network, no API keys required."""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from app.models import (
    Business,
    Lead,
    Review,
    ReviewAnalysis,
    SearchRequest,
    TechSignals,
    WebsiteInfo,
)
from app.services.filtering import filter_businesses  # noqa: E402
from app.services.review_filter import prefilter_reviews
from app.services.scoring_service import (
    classify_priority,
    contactability_score,
    review_evidence_score,
    score_lead,
    software_pain_score,
)
from app.utils.text import normalize_business_name
from app.utils.validators import extract_emails, rank_emails
from app.services.website_service import _analyze_html


def _biz(**kwargs) -> Business:
    base = dict(
        place_id="p", name="Test Store", category="Clothing store", rating=3.5,
        review_count=50, phone="+919999999999", city="Chennai",
    )
    base.update(kwargs)
    return Business(**base)


def _ago(days: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days)


# --- §10 review pre-filter ------------------------------------------------- #

class TestReviewPrefilter:
    def test_drops_non_software_complaints(self):
        """§9 — dissatisfaction is not a software opportunity."""
        reviews = [Review(text="Food was bad and the staff were rude to us.", rating=1)]
        assert prefilter_reviews(reviews, 10).kept == 0

    def test_keeps_software_complaints(self):
        reviews = [Review(
            text="Good collection but billing took almost 30 minutes. Only one counter open.",
            rating=2,
        )]
        assert prefilter_reviews(reviews, 10).kept == 1

    def test_deduplicates(self):
        text = "Billing took almost 30 minutes, only one counter was open at the store."
        result = prefilter_reviews([Review(text=text, rating=2)] * 3, 10)
        assert result.deduped == 1

    def test_drops_very_short_reviews(self):
        assert prefilter_reviews([Review(text="slow", rating=1)], 10).kept == 0

    def test_word_boundary_prevents_false_positive(self):
        """'app' must not fire on 'appreciate'."""
        reviews = [Review(text="I really appreciate how they treated my family here.", rating=5)]
        assert prefilter_reviews(reviews, 10).kept == 0

    def test_respects_limit(self):
        reviews = [
            Review(text=f"The billing counter queue was very slow on day {i} of my visit.", rating=2)
            for i in range(20)
        ]
        assert prefilter_reviews(reviews, 5).kept == 5

    def test_ranks_worse_ratings_first(self):
        reviews = [
            Review(text="The billing counter was a little slow when I visited today.", rating=4),
            Review(text="The billing counter was extremely slow and I waited ages.", rating=1),
        ]
        assert prefilter_reviews(reviews, 1).reviews[0].rating == 1


# --- §6 business filtering ------------------------------------------------- #

class TestBusinessFiltering:
    def _request(self, **kw) -> SearchRequest:
        # strict by default here so each rule can be asserted in isolation;
        # relaxation is covered by TestFilterRelaxation below.
        base = dict(location="Chennai", category="Clothing Stores", min_rating=3.0,
                    max_rating=4.0, minimum_reviews=20, limit=5, strict_filters=True)
        base.update(kw)
        return SearchRequest(**base)

    def test_rating_range_enforced(self):
        businesses = [_biz(place_id="a", rating=4.8), _biz(place_id="b", rating=3.5)]
        kept, report = filter_businesses(businesses, self._request())
        assert [b.place_id for b in kept] == ["b"]
        assert report.dropped["rating_out_of_range"] == 1

    def test_minimum_reviews_enforced(self):
        kept, report = filter_businesses([_biz(review_count=4)], self._request())
        assert kept == [] and report.dropped["too_few_reviews"] == 1

    def test_uncontactable_dropped(self):
        kept, report = filter_businesses(
            [_biz(phone=None, website=None)], self._request()
        )
        assert kept == [] and report.dropped["not_contactable"] == 1

    def test_closed_dropped_even_when_relaxing(self):
        """A closed business is never a lead, at any relaxation level."""
        kept, _ = filter_businesses(
            [_biz(permanently_closed=True)], self._request(strict_filters=False)
        )
        assert kept == []

    def test_duplicates_collapsed_keeping_richer(self):
        """§34.5 — three name variants are one business."""
        businesses = [
            _biz(place_id="a", name="ABC Fashion", review_count=50),
            _biz(place_id="b", name="ABC Fashion Store", review_count=210),
            _biz(place_id="c", name="ABC Fashions Chennai", review_count=90),
        ]
        kept, _ = filter_businesses(businesses, self._request())
        assert len(kept) == 1
        assert kept[0].review_count == 210

    def test_missing_rating_dropped(self):
        kept, _ = filter_businesses([_biz(rating=None)], self._request())
        assert kept == []


class TestFilterRelaxation:
    """A search must not return zero leads just because a heuristic band missed.

    Reproduces the real failure: every business Google returned for Chennai
    clothing stores rated 4.4-5.0, against a requested band of 3.0-4.2.
    """

    def _request(self, **kw) -> SearchRequest:
        base = dict(location="Chennai", category="Clothing Stores", min_rating=3.0,
                    max_rating=4.2, minimum_reviews=5, limit=5)
        base.update(kw)
        return SearchRequest(**base)

    def _high_rated(self) -> list[Business]:
        return [
            _biz(place_id=f"p{i}", name=f"Store {i}", rating=r, review_count=n)
            for i, (r, n) in enumerate([(4.8, 2838), (4.8, 1993), (4.9, 91), (4.4, 22), (5.0, 2)])
        ]

    def test_strict_returns_nothing(self):
        kept, _ = filter_businesses(self._high_rated(), self._request(strict_filters=True))
        assert kept == []

    def test_relaxed_returns_all_five(self):
        kept, report = filter_businesses(self._high_rated(), self._request())
        assert len(kept) == 5
        assert "rating range" in report.relaxed
        assert report.relaxation_warning is not None

    def test_no_relaxation_when_strict_filter_already_satisfies(self):
        """Relaxation must not kick in when the strict pass found enough."""
        businesses = [
            _biz(place_id=f"p{i}", name=f"Store {i}", rating=3.5, review_count=50)
            for i in range(5)
        ]
        kept, report = filter_businesses(businesses, self._request())
        assert len(kept) == 5
        assert report.relaxed == []
        assert report.relaxation_warning is None

    def test_relaxes_only_as_far_as_needed(self):
        """Dropping the rating band is enough here, so contactability stays on."""
        businesses = self._high_rated() + [
            _biz(place_id="nc", name="No Contact", rating=4.7, review_count=80,
                 phone=None, website=None)
        ]
        kept, report = filter_businesses(businesses, self._request())
        assert "rating range" in report.relaxed
        assert "contactability (phone or website)" not in report.relaxed
        assert all(b.phone or b.website for b in kept)

    def test_empty_input_stays_empty(self):
        kept, report = filter_businesses([], self._request())
        assert kept == [] and report.kept == 0


def test_name_normalisation_collapses_variants():
    keys = {
        normalize_business_name("ABC Fashion", "Chennai"),
        normalize_business_name("ABC Fashion Store", "Chennai"),
        normalize_business_name("ABC Fashions Chennai", "Chennai"),
    }
    assert len(keys) == 1


# --- §16/§29 scoring ------------------------------------------------------- #

class TestScoring:
    def test_no_software_pain_scores_zero(self):
        analyses = [ReviewAnalysis(review_index=0, software_related=False, confidence=0.9)]
        assert software_pain_score(analyses)[0] == 0.0

    def test_high_severity_beats_low(self):
        high = [ReviewAnalysis(review_index=0, software_related=True, severity="high",
                               confidence=0.9, pain_category="POS / Billing")]
        low = [ReviewAnalysis(review_index=0, software_related=True, severity="low",
                              confidence=0.9, pain_category="POS / Billing")]
        assert software_pain_score(high)[0] > software_pain_score(low)[0]

    def test_priority_bands_match_spec(self):
        """§17"""
        assert classify_priority(87) == "HOT"
        assert classify_priority(80) == "HOT"
        assert classify_priority(79) == "WARM"
        assert classify_priority(60) == "WARM"
        assert classify_priority(59) == "COLD"
        assert classify_priority(40) == "COLD"
        assert classify_priority(39) == "LOW"

    def test_contactability_weights(self):
        with_all = _biz(phone="+91", email="a@b.com", website="https://x.com")
        assert contactability_score(with_all, WebsiteInfo())[0] == 100.0
        phone_only = _biz(phone="+91", email=None, website=None)
        assert contactability_score(phone_only, WebsiteInfo())[0] == 50.0

    def test_evidence_score_follows_the_headline_pain_point(self):
        """The note must corroborate the claim the pitch actually makes."""
        analyses = [
            ReviewAnalysis(review_index=0, software_related=True, severity="high",
                           confidence=0.95, pain_category="Inventory Management",
                           evidence_date=_ago(30)),
            ReviewAnalysis(review_index=1, software_related=True, severity="low",
                           confidence=0.6, pain_category="POS / Billing",
                           evidence_date=_ago(30)),
            ReviewAnalysis(review_index=2, software_related=True, severity="low",
                           confidence=0.6, pain_category="POS / Billing",
                           evidence_date=_ago(30)),
        ]
        _, note = review_evidence_score(analyses, focus_category="Inventory Management")
        assert "Inventory Management" in note

    def test_spec_worked_example_scores_hot(self):
        """§16/§29 ABC Fashion example should land in the low 80s, HOT."""
        lead = Lead(
            business=_biz(name="ABC Fashion", rating=3.6, review_count=218,
                          email="info@abc.com", website="https://abc.com"),
            analyses=[
                ReviewAnalysis(review_index=0, software_related=True, severity="high",
                               confidence=0.91, pain_category="POS / Billing",
                               pain_point="Long billing queue", evidence_date=_ago(120)),
                ReviewAnalysis(review_index=1, software_related=True, severity="medium",
                               confidence=0.8, pain_category="Inventory Management",
                               evidence_date=_ago(60)),
            ],
            website_info=WebsiteInfo(
                url="https://abc.com", reachable=True,
                tech=TechSignals(has_website=True, ecommerce=True, online_payment=True,
                                 whatsapp=True, platforms=["Shopify"], social_links=["x"]),
            ),
        )
        scores = score_lead(lead)
        assert scores.priority == "HOT"
        assert 78 <= scores.lead_score <= 90
        assert len(scores.notes) == 5  # every subscore explains itself

    def test_scores_never_exceed_bounds(self):
        lead = Lead(
            business=_biz(review_count=100000, rating=3.5, email="a@b.com",
                          website="https://x.com"),
            analyses=[
                ReviewAnalysis(review_index=i, software_related=True, severity="high",
                               confidence=1.0, pain_category=c, evidence_date=_ago(1))
                for i, c in enumerate(["POS / Billing", "E-commerce", "CRM", "Website"])
            ],
            website_info=WebsiteInfo(
                url="https://x.com", reachable=True,
                tech=TechSignals(has_website=True, ecommerce=True, online_payment=True,
                                 online_ordering=True, booking=True, whatsapp=True,
                                 social_links=["a"], analytics=["Google Analytics"]),
            ),
        )
        s = score_lead(lead)
        assert 0 <= s.lead_score <= 100
        for value in (s.software_pain_score, s.business_potential_score,
                      s.review_evidence_score, s.digital_presence_score,
                      s.contactability_score):
            assert 0.0 <= value <= 100.0


# --- §15 email extraction -------------------------------------------------- #

class TestEmailExtraction:
    def test_extracts_and_ranks_business_addresses(self):
        html = '<a href="mailto:sales@abc.com">Sales</a> or info@abc.com or random@gmail.com'
        ranked = rank_emails(extract_emails(html), "https://abc.com")
        assert ranked[0] == "info@abc.com"  # §15 preferred prefix order
        assert "sales@abc.com" in ranked

    def test_rejects_image_and_placeholder_noise(self):
        html = "logo@2x.png banner@3x.jpg test@example.com noreply@abc.com"
        assert extract_emails(html) == []

    def test_never_invents_an_address(self):
        """§15 — a page with no email must yield no email."""
        assert extract_emails("<html><body>Call us on 044-1234</body></html>") == []

    def test_prefers_own_domain_over_free_mail(self):
        ranked = rank_emails(["owner123@gmail.com", "contact@abc.com"], "https://abc.com")
        assert ranked[0] == "contact@abc.com"


# --- §14 technology detection ---------------------------------------------- #

class TestTechDetection:
    def test_detects_shopify_and_payments(self):
        html = """<html><head><title>ABC Fashion</title>
        <meta name="description" content="Best clothes"></head><body>
        <script src="https://cdn.shopify.com/s/files/x.js"></script>
        <script src="https://checkout.razorpay.com/v1/checkout.js"></script>
        <a href="https://wa.me/919999999999">WhatsApp</a>
        <a href="/cart">Add to cart</a>
        <a href="https://instagram.com/abc">Insta</a>
        </body></html>"""
        tech, title, desc, emails, phones = _analyze_html(html, {}, "https://abc.com")
        assert "Shopify" in tech.platforms
        assert tech.online_payment and tech.whatsapp and tech.ecommerce
        assert title == "ABC Fashion" and desc == "Best clothes"
        assert tech.social_links

    def test_clean_site_reports_no_false_signals(self):
        tech, _, _, _, _ = _analyze_html(
            "<html><body><h1>Welcome to our shop</h1></body></html>", {}, "https://x.com"
        )
        assert tech.platforms == [] and not tech.online_payment and not tech.booking


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v", "--tb=short"]))
