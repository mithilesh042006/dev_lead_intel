"""Website analysis, technology detection and email extraction (spec §13, §14, §15).

No third-party API is used here. Platform and capability signals are read
straight out of the HTML, headers and script sources, which is both free and
more transparent than a paid detection service.

Requests run concurrently (§34.1). A site that is down never fails the job (§35).
"""
from __future__ import annotations

import asyncio
import logging
import re
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from app.config import settings
from app.models import Business, TechSignals, WebsiteInfo
from app.utils.validators import extract_emails, rank_emails

log = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

# §14 — platform fingerprints, matched against HTML + headers + script srcs.
PLATFORM_SIGNALS: dict[str, tuple[str, ...]] = {
    "Shopify": ("cdn.shopify.com", "shopify-features", "myshopify.com", "shopify.theme"),
    "WooCommerce": ("woocommerce", "wp-content/plugins/woocommerce"),
    "WordPress": ("wp-content", "wp-includes", "wp-json"),
    "Magento": ("magento", "mage/cookies", "static/version"),
    "Wix": ("wix.com", "wixstatic", "parastorage"),
    "Squarespace": ("squarespace", "sqsp.net"),
    "BigCommerce": ("bigcommerce", "bigcommerce.com"),
    "Webflow": ("webflow", "assets.website-files.com"),
    "Dukaan": ("mydukaan.io",),
    "Zoho Commerce": ("zohocommerce", "zohostatic"),
}

ANALYTICS_SIGNALS: dict[str, tuple[str, ...]] = {
    "Google Analytics": ("google-analytics.com", "gtag/js", "googletagmanager.com"),
    "Meta Pixel": ("connect.facebook.net", "fbevents.js"),
    "Hotjar": ("hotjar.com",),
    "Clarity": ("clarity.ms",),
}

PAYMENT_SIGNALS = (
    "razorpay", "stripe", "payu", "paytm", "ccavenue", "instamojo", "cashfree",
    "phonepe", "billdesk", "paypal", "checkout.js",
)
ECOMMERCE_SIGNALS = (
    "add to cart", "add-to-cart", "addtocart", "shopping cart", "/cart", "checkout",
    "buy now", "shop now", "my account", "wishlist",
)
ORDERING_SIGNALS = ("order online", "order now", "place order", "online order", "swiggy", "zomato")
BOOKING_SIGNALS = (
    "book now", "book a", "booking", "appointment", "schedule a", "reserve a table",
    "calendly", "make a reservation",
)

CONTACT_PATH_HINTS = (
    "contact", "contact-us", "contactus", "about", "about-us", "reach-us",
    "get-in-touch", "support",
)

PHONE_RE = re.compile(r"(?:\+?91[\-\s]?)?[6-9]\d{9}\b")


def _normalize_url(raw: str | None) -> str | None:
    if not raw:
        return None
    raw = raw.strip()
    if not raw:
        return None
    if not raw.startswith(("http://", "https://")):
        raw = "https://" + raw
    parsed = urlparse(raw)
    return raw if parsed.netloc else None


def _detect(haystack: str, signals: tuple[str, ...]) -> bool:
    return any(s in haystack for s in signals)


def _detect_named(haystack: str, table: dict[str, tuple[str, ...]]) -> list[str]:
    return [name for name, sigs in table.items() if _detect(haystack, sigs)]


def _contact_links(soup: BeautifulSoup, base_url: str, limit: int) -> list[str]:
    """Pick the pages most likely to carry an email (§15)."""
    found: list[str] = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = (a.get_text() or "").lower()
        blob = f"{href.lower()} {text}"
        if any(hint in blob for hint in CONTACT_PATH_HINTS):
            absolute = urljoin(base_url, href)
            if absolute.startswith(("http://", "https://")) and absolute not in found:
                found.append(absolute)
        if len(found) >= limit:
            break
    return found


def _analyze_html(html: str, headers: dict, url: str) -> tuple[TechSignals, str, str, list[str], list[str]]:
    soup = BeautifulSoup(html, "html.parser")

    scripts = " ".join(s.get("src", "") for s in soup.find_all("script"))
    links = " ".join(l.get("href", "") for l in soup.find_all("link"))
    header_blob = " ".join(f"{k}:{v}" for k, v in headers.items())
    text = soup.get_text(" ", strip=True)

    # Markup blob for platform/analytics fingerprints; text blob for capability words.
    markup = f"{html[:250000]} {scripts} {links} {header_blob}".lower()
    lowered_text = text.lower()

    social = [
        a["href"] for a in soup.find_all("a", href=True)
        if any(d in a["href"].lower() for d in
               ("facebook.com", "instagram.com", "twitter.com", "x.com",
                "linkedin.com", "youtube.com"))
    ]
    whatsapp = "wa.me" in markup or "whatsapp" in markup or "api.whatsapp.com" in markup

    tech = TechSignals(
        has_website=True,
        platforms=_detect_named(markup, PLATFORM_SIGNALS),
        analytics=_detect_named(markup, ANALYTICS_SIGNALS),
        ecommerce=_detect(lowered_text, ECOMMERCE_SIGNALS) or _detect(markup, ECOMMERCE_SIGNALS),
        online_ordering=_detect(lowered_text, ORDERING_SIGNALS),
        booking=_detect(lowered_text, BOOKING_SIGNALS),
        online_payment=_detect(markup, PAYMENT_SIGNALS),
        whatsapp=whatsapp,
        social_links=list(dict.fromkeys(social))[:6],
    )

    title = (soup.title.get_text(strip=True) if soup.title else "")[:200]
    desc_tag = soup.find("meta", attrs={"name": "description"}) or soup.find(
        "meta", attrs={"property": "og:description"}
    )
    description = (desc_tag.get("content", "") if desc_tag else "")[:400]

    emails = extract_emails(html)
    phones = list(dict.fromkeys(PHONE_RE.findall(text)))[:3]
    return tech, title, description, emails, phones


async def _fetch_one(client: httpx.AsyncClient, url: str) -> tuple[str, dict] | None:
    try:
        resp = await client.get(url)
        if resp.status_code >= 400:
            return None
        ctype = resp.headers.get("content-type", "")
        if "html" not in ctype.lower():
            return None
        return resp.text, dict(resp.headers)
    except Exception:
        return None


async def analyze_website(url_raw: str | None) -> WebsiteInfo:
    url = _normalize_url(url_raw)
    if not url:
        return WebsiteInfo(url=None, reachable=False, error="no website")

    limits = httpx.Limits(max_connections=settings.website_concurrency)
    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=settings.website_timeout,
        headers={"User-Agent": USER_AGENT},
        limits=limits,
        verify=False,
    ) as client:
        home = await _fetch_one(client, url)
        if home is None:
            # §35 — an unreachable site continues the job with Maps data only.
            return WebsiteInfo(url=url, reachable=False, error="unreachable")

        html, headers = home
        tech, title, description, emails, phones = _analyze_html(html, headers, url)

        # §15 — the homepage rarely carries the email; contact/about pages do.
        if not emails:
            soup = BeautifulSoup(html, "html.parser")
            extra_pages = _contact_links(soup, url, settings.website_max_pages)
            if extra_pages:
                results = await asyncio.gather(
                    *(_fetch_one(client, p) for p in extra_pages), return_exceptions=True
                )
                for r in results:
                    if isinstance(r, tuple):
                        page_html, _ = r
                        emails.extend(extract_emails(page_html))
                        if not phones:
                            phones = list(dict.fromkeys(
                                PHONE_RE.findall(BeautifulSoup(page_html, "html.parser")
                                                 .get_text(" ", strip=True))
                            ))[:3]

    return WebsiteInfo(
        url=url,
        reachable=True,
        title=title,
        description=description,
        emails=rank_emails(emails, url),
        phones=phones,
        tech=tech,
    )


async def analyze_many(businesses: list[Business]) -> dict[str, WebsiteInfo]:
    """Analyse every candidate's website concurrently (§34.1)."""
    semaphore = asyncio.Semaphore(settings.website_concurrency)

    async def worker(b: Business) -> tuple[str, WebsiteInfo]:
        async with semaphore:
            try:
                return b.place_id, await analyze_website(b.website)
            except Exception as exc:  # §35 — one bad site never fails the batch
                log.warning("website analysis failed for %s: %s", b.name, exc)
                return b.place_id, WebsiteInfo(url=b.website, reachable=False, error=str(exc))

    pairs = await asyncio.gather(*(worker(b) for b in businesses))
    return dict(pairs)
