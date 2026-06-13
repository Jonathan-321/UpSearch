"""Company-Owned People Source Connector.

Fetches candidate people from verified company team, author, and
engineering-blog pages.  Every candidate passes through the existing
evidence-first verification path — no direct trust.

Rules
-----
- Only HTTP(S) pages on the verified company domain are fetched.
- Candidate names are extracted from author bylines, team member cards,
  and similar HTML patterns on the fetched page.
- Extraction is intentionally simple and lossy: the verification pipeline
  rejects false positives later.
- No LinkedIn, GitHub, X, or email address is ever synthesised.
- On any fetch/parse/evidence failure the connector returns an empty list.
"""

from __future__ import annotations

import logging
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx

from upsearch.person_validation import is_person_name

logger = logging.getLogger(__name__)

_FETCH_TIMEOUT = httpx.Timeout(10.0, connect=5.0)
_FETCH_HEADERS = {
    "User-Agent": "UpSearchCompanyPeopleConnector/0.1",
    "Accept": "text/html,text/plain;q=0.8,*/*;q=0.5",
}
_MAX_FETCH_CHARS = 100_000
_MAX_AUTHOR_PAGES = 4
_MAX_FETCH_WORKERS = 6


# ── helpers ────────────────────────────────────────────────────────────────


def _domain_from_url(url: str) -> str:
    try:
        host = urlparse(url).hostname or ""
        return host.lower()
    except Exception:
        return ""


def _canonical_domain(value: str) -> str:
    domain = value.lower().strip().rstrip(".")
    return domain[4:] if domain.startswith("www.") else domain


def _normalise_name(raw: str) -> str:
    """Collapse whitespace and strip punctuation for dedup."""
    cleaned = re.sub(r"[^\w\s'-]", " ", raw)
    return " ".join(cleaned.strip().lower().split())


def _on_verified_domain(url: str, company_domain: str) -> bool:
    """Return True if *url* is an HTTP(S) page on *company_domain*."""
    if not url.startswith(("http://", "https://")):
        return False
    host = _canonical_domain(_domain_from_url(url))
    domain = _canonical_domain(company_domain)
    return bool(domain and host == domain)


def _fetch_page(url: str) -> str:
    """Fetch a public URL and return its text content.

    Returns an empty string on any failure — network error, non-200, etc.
    """
    try:
        with httpx.Client(
            timeout=_FETCH_TIMEOUT, follow_redirects=True, headers=_FETCH_HEADERS
        ) as client:
            resp = client.get(url)
            resp.raise_for_status()
            return resp.text[:_MAX_FETCH_CHARS]
    except Exception as exc:
        logger.debug("company_people fetch failed for %s: %s", url, exc)
        return ""


def _fetch_pages(urls: list[str]) -> dict[str, str]:
    """Fetch several pages concurrently, mapping each URL to its text.

    Each fetch is independent and :func:`_fetch_page` already swallows its own
    failures (returning ``""``), so a single failed fetch degrades exactly as it
    did sequentially. Results are returned as a dict; callers iterate their own
    ordered URL list to preserve the original processing order.
    """
    if not urls:
        return {}
    with ThreadPoolExecutor(max_workers=min(_MAX_FETCH_WORKERS, len(urls))) as pool:
        return dict(zip(urls, pool.map(_fetch_page, urls)))


def _clean_text(html: str) -> str:
    """Strip markup and normalise whitespace for regex extraction."""
    text = re.sub(r"<script\b[^>]*>.*?</script>", " ", html, flags=re.I | re.S)
    text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()[:20_000]


# ── candidate extraction ───────────────────────────────────────────────────


def _extract_candidates(
    html: str, url: str, company_domain: str
) -> list[dict[str, Any]]:
    """Extract candidate person records from a fetched company page.

    Heuristics tried in order:
    1. ``<author>`` or ``class="author"`` inline bylines
    2. ``<article>`` or ``class="post"`` author bylines
    3. Team member cards (list items with visible name text)
    """
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()

    # Heuristic 1: author-byline patterns
    for raw_name in re.findall(
        r"(?i:by|author|written\s+by)\s*:?\s*"
        r"([A-Z][a-zA-Z'-]*(?:\s+[A-Z][a-zA-Z'-]*){0,3})(?=\s*<)",
        html,
    ):
        name = raw_name.strip()
        norm = _normalise_name(name)
        if norm and norm not in seen and len(norm) >= 3:
            seen.add(norm)
            candidates.append(_make_candidate(
                name,
                url,
                role="Technical author",
                relevance_reason="Authored content on a company-owned page.",
            ))

    # Heuristic 2: article / blog byline meta
    for raw_name in re.findall(
        r'class="author-name"[^>]*>([^<]{3,50})<',
        html,
        flags=re.I,
    ):
        name = raw_name.strip()
        norm = _normalise_name(name)
        if norm and norm not in seen and len(norm) > 3:
            seen.add(norm)
            candidates.append(_make_candidate(
                name,
                url,
                role="Technical author",
                relevance_reason="Listed as an author on a company-owned page.",
            ))

    for raw_name in re.findall(
        r'rel="author"[^>]*>([^<]{3,50})<',
        html,
        flags=re.I,
    ):
        name = raw_name.strip()
        norm = _normalise_name(name)
        if norm and norm not in seen and len(norm) > 3:
            seen.add(norm)
            candidates.append(_make_candidate(
                name,
                url,
                role="Technical author",
                relevance_reason="Linked as an author on a company-owned page.",
            ))

    # Heuristic 3: visible h3/h4/strong inside list items (team cards)
    # Prefer a short role label immediately following the heading.
    for _level, raw_name, raw_role in re.findall(
        r"<h([34])[^>]*>([A-Z][a-zA-Z\s'-]{2,40}?)</h\1>"
        r"\s*(?:<[^>]+>)*\s*([^<]{2,80})<",
        html,
    ):
        name = raw_name.strip()
        role = re.sub(r"\s+", " ", raw_role).strip()
        norm = _normalise_name(name)
        if norm and norm not in seen and len(norm) > 3:
            seen.add(norm)
            candidates.append(_make_candidate(
                name,
                url,
                role=role,
                relevance_reason=f"Listed as {role} on a company-owned page.",
            ))

    # Capture headings without an adjacent role as lower-confidence candidates.
    for raw_name in re.findall(
        r"<h[34][^>]*>([A-Z][a-zA-Z\s'-]{2,40}?)</h[34]>",
        html,
    ):
        name = raw_name.strip()
        norm = _normalise_name(name)
        if norm and norm not in seen and len(norm) > 3:
            seen.add(norm)
            candidates.append(_make_candidate(
                name,
                url,
                role="Team member",
                relevance_reason="Listed on a company-owned people page.",
            ))

    return candidates


def _extract_author_links(html: str, base_url: str, company_domain: str) -> list[str]:
    """Same-domain author-page links discovered on a fetched page.

    Blog indexes rarely carry parseable bylines, but they link to per-author
    pages (``/author/<slug>``, ``/blog/author/<slug>``) that name the person
    in the title — those pages are also exactly what evidence verification
    wants to fetch.
    """
    links: list[str] = []
    for href in re.findall(r'href="([^"#?]*/authors?/[^"#?]+)[^"]*"', html, flags=re.I):
        absolute = urljoin(base_url, href).rstrip("/")
        if _on_verified_domain(absolute, company_domain) and absolute not in links:
            links.append(absolute)
    return links


def _extract_author_page_candidates(html: str, url: str) -> list[dict[str, Any]]:
    """Candidate from an author page's title/h1 (e.g. "Posts by Jane Doe")."""
    texts: list[str] = []
    title_match = re.search(r"<title[^>]*>([^<]{3,120})</title>", html, flags=re.I)
    if title_match:
        texts.append(title_match.group(1))
    texts.extend(re.findall(r"<h1[^>]*>([^<]{3,80})</h1>", html, flags=re.I))

    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in texts:
        cleaned = _unescape_text(raw)
        for fragment in re.split(r"[|–—:·-]", cleaned):
            name = re.sub(r"^(?:posts?|articles?|written)\s+by\s+", "", fragment.strip(), flags=re.I)
            name = name.strip()
            norm = _normalise_name(name)
            if norm and norm not in seen and is_person_name(name):
                seen.add(norm)
                candidates.append(_make_candidate(
                    name,
                    url,
                    role="Technical author",
                    relevance_reason="Has a dedicated author page on the company site.",
                ))
    return candidates


def _unescape_text(value: str) -> str:
    from html import unescape  # noqa: PLC0415

    return re.sub(r"\s+", " ", unescape(value)).strip()


def _make_candidate(
    name: str,
    source_url: str,
    *,
    role: str,
    relevance_reason: str,
) -> dict[str, Any]:
    return {
        "name": name.strip(),
        "role": role,
        "proximity": "engineer",
        "source_url": source_url,
        "relevance_score": 5,
        "relevance_reason": relevance_reason,
        "source": f"company-people connector ({_domain_from_url(source_url)})",
        "outreach_note": "",
    }


def author_from_post_url(post_url: str, company_domain: str) -> dict[str, Any] | None:
    """Resolve the author of a cited company post.

    The problem stage cites company posts as evidence; whoever wrote the
    cited post is the most-proximate possible person — outreach can reference
    their own writing. Prefers the post's author page (its title names the
    person, and it doubles as a strong verification source), falling back to
    an on-page byline.
    """
    if not _on_verified_domain(post_url, company_domain):
        return None
    html = _fetch_page(post_url)
    if not html:
        return None

    candidate: dict[str, Any] | None = None
    author_pages = _extract_author_links(html, post_url, company_domain)
    if author_pages:
        page_html = _fetch_page(author_pages[0])
        if page_html:
            from_page = [
                c for c in _extract_author_page_candidates(page_html, author_pages[0])
                if is_person_name(c.get("name", ""))
            ]
            if from_page:
                candidate = from_page[0]

    if candidate is None:
        bylines = [
            c for c in _extract_candidates(html, post_url, company_domain)
            if c.get("role") == "Technical author" and is_person_name(c.get("name", ""))
        ]
        if bylines:
            candidate = bylines[0]

    if candidate is None:
        return None

    candidate.update({
        "role": candidate.get("role") or "Technical author",
        "proximity": "author",
        "relevance_score": 10,
        "relevance_reason": "Wrote the source this packet cites — closest person to the exact problem.",
        "outreach_note": f"Reference their post: {post_url}",
        "cited_source_url": post_url,
        # Evidence coordinates for independent re-verification: an author
        # page on the company's own domain whose title/h1 names the person
        # IS the person<->company link; generic phrase-matching would demand
        # synthetic role words the page never contains.
        "author_page_evidence": {
            "url": candidate.get("source_url", ""),
            "company_domain": company_domain,
        },
    })
    return candidate


# ── merging ────────────────────────────────────────────────────────────────


def _merge_dedup(
    existing: list[dict[str, Any]], new: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Merge *new* candidates into *existing*, deduplicating by normalised name.

    When a duplicate is found the existing record is kept (first-wins).
    """
    existing_norms = {_normalise_name(p.get("name", "")) for p in existing}
    for candidate in new:
        norm = _normalise_name(candidate.get("name", ""))
        if norm and norm not in existing_norms:
            existing_norms.add(norm)
            existing.append(candidate)
    return existing


# ── public API ─────────────────────────────────────────────────────────────


def fetch_company_people(
    company_domain: str,
    page_urls: list[str],
) -> list[dict[str, Any]]:
    """Fetch and extract candidate people from company-owned pages.

    Only pages whose domain matches *company_domain* are fetched.  Every
    candidate produced by this function still passes through the evidence-first
    :func:`upsearch.person_verification.verify_people` pipeline — this
    connector does **not** bypass verification.

    Parameters
    ----------
    company_domain:
        Verified company domain (e.g. ``"baseten.co"``).
    page_urls:
        Candidate page URLs to try fetching.

    Returns
    -------
    List of person dicts with ``name``, ``source_url``, ``source``, and
    placeholder role/relevance fields.  Empty on any failure.
    """
    if not company_domain or not page_urls:
        return []

    candidates: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    author_links: list[str] = []

    # Resolve the ordered set of on-domain seed URLs to fetch (preserving the
    # original dedup and off-domain skip exactly), then fetch them concurrently.
    seed_urls: list[str] = []
    for url in page_urls:
        if url in seen_urls:
            continue
        seen_urls.add(url)
        if not _on_verified_domain(url, company_domain):
            logger.debug("skipping off-domain URL: %s", url)
            continue
        seed_urls.append(url)

    seed_html = _fetch_pages(seed_urls)
    for url in seed_urls:
        html = seed_html.get(url, "")
        if not html:
            logger.debug("empty fetch for %s — skipping", url)
            continue

        extracted = _extract_candidates(html, url, company_domain)
        # Marketing markup makes nav sections and article cards look like team
        # cards; only candidates that look like human names leave the connector.
        extracted = [c for c in extracted if is_person_name(c.get("name", ""))]
        _merge_dedup(candidates, extracted)

        for link in _extract_author_links(html, url, company_domain):
            if link not in seen_urls and link not in author_links:
                author_links.append(link)

    # One discovery hop: fetch per-author pages found on the seed pages. Their
    # titles name the author, and they double as strong verification sources.
    hop_urls = author_links[:_MAX_AUTHOR_PAGES]
    for url in hop_urls:
        seen_urls.add(url)
    hop_html = _fetch_pages(hop_urls)
    for url in hop_urls:
        html = hop_html.get(url, "")
        if not html:
            continue
        extracted = [
            *_extract_author_page_candidates(html, url),
            *_extract_candidates(html, url, company_domain),
        ]
        extracted = [c for c in extracted if is_person_name(c.get("name", ""))]
        _merge_dedup(candidates, extracted)

    return candidates
