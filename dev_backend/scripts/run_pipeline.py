"""CLI entry point for the MVP pipeline (spec §42).

    python scripts/run_pipeline.py --location Chennai --category "Clothing Stores" \
        --min-rating 3.0 --max-rating 4.0 --min-reviews 20 --limit 5

Add --dry-run to exercise the whole pipeline on built-in sample data without
spending a single Apify credit.
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings  # noqa: E402
from app.models import Lead, SearchRequest  # noqa: E402
from app.pipeline import LeadPipeline  # noqa: E402

BAR = "=" * 62
RULE = "-" * 62


def _force_utf8_stdout() -> None:
    """Windows consoles default to cp1252, which mangles review text and
    smart quotes in generated pitches. The CSV is written as UTF-8 either way;
    this only fixes what is printed."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="  %(message)s",
        stream=sys.stdout,
    )
    for noisy in ("httpx", "httpcore", "google_genai", "apify_client", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def render_lead(lead: Lead, rank: int) -> str:
    b = lead.business
    top = lead.top_analysis
    s = lead.scores
    out: list[str] = [BAR, f"#{rank}  {b.name.upper()}", BAR]

    out.append(f"Category:      {b.category or '-'}")
    out.append(f"Rating:        {b.rating} / 5   ({b.review_count} reviews)")
    out.append(f"Location:      {b.city or b.address or '-'}")
    out.append(f"Phone:         {b.phone or '-'}")
    out.append(f"Email:         {b.email or '-'}")
    out.append(f"Website:       {b.website or '-'}")
    out.append(f"Google Maps:   {b.google_maps_url or '-'}")

    out += ["", RULE, "CUSTOMER PAIN POINT (fact)", RULE]
    if top:
        out.append(f"Problem:       {top.pain_point}")
        out.append(f"Category:      {top.pain_category}")
        out.append(f"Severity:      {top.severity}")
        out.append("Evidence:")
        out.append(f'  "{top.evidence_text.strip()[:300]}"')
        stars = f"{top.evidence_rating}*" if top.evidence_rating is not None else "?"
        date = top.evidence_date.date().isoformat() if top.evidence_date else "date unknown"
        out.append(f"  - {stars}, {date}")
    else:
        out.append("No software-related pain point found in the analysed reviews.")

    out += ["", RULE, "AI INTERPRETATION & RECOMMENDATION", RULE]
    if top:
        out.append(f"Customer impact:  {top.customer_impact}")
        out.append(f"Business impact:  {top.business_impact}")
        out.append(f"Opportunity:      {lead.opportunity.primary_opportunity or '-'}")
        if lead.opportunity.secondary_opportunities:
            out.append(f"Also consider:    {', '.join(lead.opportunity.secondary_opportunities)}")
        out.append(f"Confidence:       {top.confidence:.0%}")
        out.append("(Interpretation, not a confirmed fact about this business.)")

    out += ["", RULE, "TECHNOLOGY", RULE]
    tech = lead.website_info.tech
    out.append(f"Website reachable: {'yes' if lead.website_info.reachable else 'no'}")
    out.append(f"Signals:           {tech.as_csv_field() or 'none detected'}")

    out += ["", RULE, f"LEAD SCORE   {s.lead_score} / 100   [{s.priority}]", RULE]
    out.append(
        f"  pain {s.software_pain_score:.0f} x40%  |  potential "
        f"{s.business_potential_score:.0f} x25%  |  evidence "
        f"{s.review_evidence_score:.0f} x20%"
    )
    out.append(
        f"  digital {s.digital_presence_score:.0f} x10%  |  contact "
        f"{s.contactability_score:.0f} x5%"
    )
    for note in s.notes:
        out.append(f"  - {note}")

    if lead.sales_pitch:
        out += ["", RULE, "COLD CALL OPENING", RULE, lead.sales_pitch]
    out.append(BAR)
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(description="AI Lead Intelligence - MVP pipeline")
    parser.add_argument("--location", default="Chennai")
    parser.add_argument("--category", default="Clothing Stores")
    parser.add_argument("--min-rating", type=float, default=3.0)
    parser.add_argument("--max-rating", type=float, default=4.0)
    parser.add_argument("--min-reviews", type=int, default=20)
    parser.add_argument("--limit", type=int, default=5, help="qualified leads to return")
    parser.add_argument(
        "--max-places", type=int, default=None,
        help="places to scrape (drives Apify cost; default: max(config, limit*2))",
    )
    parser.add_argument("--no-cache", action="store_true", help="ignore the disk cache")
    parser.add_argument("--no-mx", action="store_true", help="skip email MX lookups")
    parser.add_argument("--dry-run", action="store_true",
                        help="use built-in sample data, spend no Apify credits")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    _force_utf8_stdout()
    setup_logging(args.verbose)
    if args.no_cache:
        settings.cache_enabled = False

    request = SearchRequest(
        location=args.location,
        category=args.category,
        min_rating=args.min_rating,
        max_rating=args.max_rating,
        minimum_reviews=args.min_reviews,
        limit=args.limit,
        max_places=args.max_places,
    )

    print(BAR)
    print("AI LEAD INTELLIGENCE - MVP")
    print(BAR)
    print(f"Location:        {request.location}")
    print(f"Category:        {request.category}")
    print(f"Rating range:    {request.min_rating} - {request.max_rating}")
    print(f"Minimum reviews: {request.minimum_reviews}")
    print(f"Leads wanted:    {request.limit}")
    print(f"Model:           {settings.llm_model}")
    print(f"Cache:           {'on' if settings.cache_enabled else 'OFF'}")
    print(BAR)
    print()

    if args.dry_run:
        from scripts.sample_data import SampleProvider
        pipeline = LeadPipeline(provider=SampleProvider())
    else:
        pipeline = LeadPipeline()

    result = pipeline.run(request, validate_email_mx=not args.no_mx)

    print()
    if not result.leads:
        print(f"No leads produced (status: {result.status}).")
        for w in result.warnings:
            print(f"  ! {w}")
        return 1

    for i, lead in enumerate(result.leads, start=1):
        print(render_lead(lead, i))
        print()

    print(BAR)
    print(f"Status:      {result.status}")
    print(f"Analysed:    {result.stats.get('analysed')} businesses")
    print(f"Returned:    {result.stats.get('returned')} leads")
    print(f"LLM calls:   {result.stats.get('llm_calls')}")
    print(f"Leads CSV:   {result.csv_path}")
    print(f"Evidence CSV:{result.evidence_path}")
    for w in result.warnings:
        print(f"  ! {w}")
    print(BAR)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
