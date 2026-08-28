"""Email extraction, ranking and validation (spec §15).

Hard rule from §15: never fabricate an email address from a domain. Everything
returned here was literally present in a page we fetched.
"""
from __future__ import annotations

import re
from functools import lru_cache
from urllib.parse import urlparse

import dns.resolver

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")

# §15 preferred local parts, best first.
PREFERRED_PREFIXES = (
    "info", "contact", "sales", "support", "hello", "business", "enquiry",
    "enquiries", "inquiry", "care", "admin", "office",
)

# Addresses that belong to the platform, not the business.
JUNK_PATTERNS = (
    "example.com", "sentry.io", "wixpress.com", "godaddy", "@2x", "@3x",
    "yourdomain", "domain.com", "email.com", "test@", "noreply", "no-reply",
    "donotreply", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".css", ".js",
)

DISPOSABLE_DOMAINS = {"mailinator.com", "tempmail.com", "10minutemail.com", "guerrillamail.com"}


def extract_emails(html: str) -> list[str]:
    """Pull every literal email out of a page, including mailto: hrefs."""
    found = EMAIL_RE.findall(html or "")
    cleaned: list[str] = []
    for raw in found:
        email = raw.strip().strip(".").lower()
        lowered = email.lower()
        if any(junk in lowered for junk in JUNK_PATTERNS):
            continue
        if lowered.split("@")[-1] in DISPOSABLE_DOMAINS:
            continue
        if len(email) > 100:
            continue
        cleaned.append(email)
    return list(dict.fromkeys(cleaned))


def rank_emails(emails: list[str], site_url: str | None = None) -> list[str]:
    """Prefer business addresses on the business's own domain (§15)."""
    site_domain = ""
    if site_url:
        netloc = urlparse(site_url).netloc.lower()
        site_domain = netloc[4:] if netloc.startswith("www.") else netloc

    def sort_key(email: str) -> tuple[int, int]:
        local, _, domain = email.partition("@")
        domain_rank = 0 if site_domain and site_domain in domain else 1
        try:
            prefix_rank = PREFERRED_PREFIXES.index(local)
        except ValueError:
            prefix_rank = len(PREFERRED_PREFIXES)
        return domain_rank, prefix_rank

    return sorted(dict.fromkeys(emails), key=sort_key)


@lru_cache(maxsize=512)
def has_mx_record(domain: str) -> bool:
    """Cheap deliverability check — no third-party validation API needed."""
    try:
        answers = dns.resolver.resolve(domain, "MX", lifetime=5)
        return len(answers) > 0
    except Exception:
        return False


def validate_email(email: str, check_mx: bool = True) -> bool:
    if not email or not EMAIL_RE.fullmatch(email):
        return False
    domain = email.rpartition("@")[2]
    if not domain or domain in DISPOSABLE_DOMAINS:
        return False
    return has_mx_record(domain) if check_mx else True


def pick_best_email(emails: list[str], check_mx: bool = True) -> str | None:
    for email in emails:
        if validate_email(email, check_mx=check_mx):
            return email
    return None
