"""Evidence-first company identity resolution.

Discovery results are leads, not company records. This module turns a lead into
an accepted company identity only when the public evidence agrees on the name,
domain, and technical lane.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from html import unescape
from typing import Callable
from urllib.parse import urlparse

import requests


AGGREGATOR_HOSTS = {
    "arxiv.org",
    "github.com",
    "linkedin.com",
    "news.ycombinator.com",
    "reddit.com",
    "www.arxiv.org",
    "www.github.com",
    "www.linkedin.com",
    "www.reddit.com",
    "x.com",
    "youtube.com",
    "www.youtube.com",
}

EMPLOYER_TERMS = {
    "careers",
    "company",
    "customers",
    "enterprise",
    "founded",
    "hiring",
    "platform",
    "pricing",
    "product",
    "startup",
    "team",
}

LANE_TERMS = {
    "ai_infra": {"ai", "gpu", "inference", "ml", "model", "serving"},
    "inference_systems": {"gpu", "inference", "latency", "llm", "model", "serving"},
    "agentic_ai": {"agent", "agentic", "automation", "llm", "orchestration", "workflow"},
    "developer_tools": {"api", "developer", "devtool", "ide", "sdk", "tooling"},
    "data_platforms": {"analytics", "data", "database", "etl", "pipeline", "warehouse"},
    "robotics_ai": {"autonomous", "embodied", "robot", "robotics", "simulation", "vision"},
}


def _tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", value.lower())
        if len(token) > 1
    }


def _normalized_name(value: str) -> str:
    return "".join(re.findall(r"[a-z0-9]+", value.lower()))


def _hostname(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower()
    except ValueError:
        return ""


def is_dedicated_company_url(url: str) -> bool:
    host = _hostname(url)
    if not host or host in AGGREGATOR_HOSTS:
        return False
    return not any(host.endswith(f".{blocked}") for blocked in AGGREGATOR_HOSTS)


def canonical_website(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return ""
    return f"{parsed.scheme}://{parsed.hostname.lower()}"


def _identity_rejection_reason(
    *,
    host_name_match: bool,
    page_name_match: bool,
    page_lane_match: bool,
    employer_match: bool,
    ambiguous_acronym: bool,
) -> str:
    missing: list[str] = []
    if not host_name_match:
        missing.append("official-domain agreement")
    if not page_name_match:
        missing.append("company-name agreement")
    if not page_lane_match:
        missing.append("technical-lane evidence on the fetched page")
    if not employer_match:
        missing.append("employer or product evidence")
    prefix = "Ambiguous acronym requires stronger evidence" if ambiguous_acronym else "Identity evidence is incomplete"
    return f"{prefix}: {', '.join(missing) or 'confidence threshold not met'}."


@dataclass(frozen=True)
class FetchedPage:
    url: str
    title: str = ""
    text: str = ""
    status_code: int = 0


@dataclass(frozen=True)
class CompanyIdentity:
    query_name: str
    canonical_name: str
    website: str
    official_domain: str
    lane: str
    status: str
    confidence: float
    reason: str
    evidence_urls: list[str] = field(default_factory=list)
    evidence_titles: list[str] = field(default_factory=list)

    @property
    def verified(self) -> bool:
        return self.status == "verified"

    def to_dict(self) -> dict:
        return asdict(self)


_BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


def _parse_page(url: str, raw: str, status_code: int) -> FetchedPage:
    title_match = re.search(r"<title[^>]*>(.*?)</title>", raw, flags=re.I | re.S)
    title = unescape(re.sub(r"\s+", " ", title_match.group(1)).strip()) if title_match else ""
    # Meta descriptions survive in SSR shells whose body is a JS bundle; they
    # are first-party page content and count as identity evidence.
    metas = re.findall(
        r'<meta[^>]+(?:name|property)=["\'](?:description|og:description|keywords)["\']'
        r'[^>]+content=["\']([^"\']+)["\']',
        raw,
        flags=re.I,
    )
    without_markup = re.sub(r"<script\b[^>]*>.*?</script>", " ", raw, flags=re.I | re.S)
    without_markup = re.sub(r"<style\b[^>]*>.*?</style>", " ", without_markup, flags=re.I | re.S)
    text = unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", without_markup))).strip()
    meta_text = unescape(" ".join(metas)).strip()
    combined = f"{meta_text} {text}".strip() if meta_text else text
    return FetchedPage(
        url=url,
        title=title[:500],
        text=combined[:20_000],
        status_code=status_code,
    )


def _get(url: str, timeout: float, user_agent: str):
    return requests.get(
        url,
        timeout=timeout,
        allow_redirects=True,
        headers={"User-Agent": user_agent},
    )


def fetch_page(url: str, timeout: float = 8.0) -> FetchedPage:
    """Fetch enough public page text to verify identity, without executing JS.

    Some sites serve the verifier User-Agent a contentless JS shell (no
    title, bundle text only) while serving browsers the real document; when
    the first fetch looks like a shell, one retry with a browser User-Agent
    recovers the actual page.
    """
    try:
        response = _get(url, timeout, "UpSearch/0.1 company-identity-verifier")
        response.raise_for_status()
    except requests.RequestException:
        return FetchedPage(url=url)

    page = _parse_page(response.url, response.text[:250_000], response.status_code)
    if not page.title:
        try:
            retry = _get(url, timeout, _BROWSER_UA)
            retry.raise_for_status()
            retry_page = _parse_page(retry.url, retry.text[:250_000], retry.status_code)
            if retry_page.title:
                return retry_page
        except requests.RequestException:
            pass
    return page


def resolve_company_identity(
    *,
    name: str,
    lane: str,
    evidence_urls: list[str],
    evidence_titles: list[str] | None = None,
    fetcher: Callable[[str], FetchedPage] = fetch_page,
) -> CompanyIdentity:
    """Resolve a candidate into a canonical company or reject it.

    A verified identity requires a dedicated domain plus agreement between the
    candidate name, discovery context, fetched page, and requested lane.
    """
    titles = [title.strip() for title in (evidence_titles or []) if title.strip()]
    urls = list(dict.fromkeys(url.strip() for url in evidence_urls if url.strip()))
    dedicated_urls = [url for url in urls if is_dedicated_company_url(url)]
    if not dedicated_urls:
        return CompanyIdentity(
            query_name=name,
            canonical_name=name.strip(),
            website="",
            official_domain="",
            lane=lane,
            status="rejected",
            confidence=0.0,
            reason="No dedicated company or product domain was present in discovery evidence.",
            evidence_urls=urls,
            evidence_titles=titles,
        )

    # Corporate suffixes carry no identity; descriptive tokens ("GPU",
    # "Cloud") DO — they are what separates "Oblivus GPU Cloud" from an
    # unrelated company that happens to share the first word.
    corp_suffixes = {"co", "corp", "inc", "labs", "llc", "ltd", "technologies", "technology"}
    name_tokens = _tokens(name) - corp_suffixes
    normalized_name = _normalized_name(name)
    lane_terms = LANE_TERMS.get(lane, _tokens(lane.replace("_", " ")))
    discovery_text = " ".join(titles)
    discovery_tokens = _tokens(discovery_text)
    exact_title_match = any(normalized_name in _normalized_name(title) for title in titles)

    best: tuple[float, CompanyIdentity] | None = None
    for source_url in dedicated_urls[:3]:
        page = fetcher(source_url)
        if page.status_code < 200 or page.status_code >= 400:
            continue

        final_url = page.url or source_url
        host = _hostname(final_url)
        host_label = host.removeprefix("www.").split(".")[0] if host else ""
        host_name = _normalized_name(host_label)
        page_text = f"{page.title} {page.text}"
        page_tokens = _tokens(page_text)
        host_name_match = bool(normalized_name) and (
            normalized_name in host_name
            or (len(host_name) >= 4 and host_name in normalized_name)
        )
        # The page itself must carry the full name (every significant token,
        # or the exact name in the title). A host matching only the FIRST
        # word must not satisfy this — that is how a typo'd "Oblivious GPU
        # Cloud" verified against oblivious.com, an unrelated company.
        page_name_match = bool(name_tokens) and (
            name_tokens.issubset(page_tokens)
            or normalized_name in _normalized_name(page.title)
        )
        discovery_lane_match = bool(lane_terms & discovery_tokens)
        page_lane_match = bool(lane_terms & page_tokens)
        employer_match = bool(EMPLOYER_TERMS & page_tokens)

        score = 0.0
        score += 0.25 if exact_title_match else 0.0
        score += 0.25 if page_name_match else 0.0
        score += 0.20 if host_name_match else 0.0
        score += 0.20 if page_lane_match else 0.0
        score += 0.05 if discovery_lane_match else 0.0
        score += 0.10 if employer_match else 0.0
        score = min(1.0, score)

        ambiguous_acronym = name.isupper() and len(normalized_name) <= 5
        threshold = 0.9 if ambiguous_acronym else 0.7
        verified = score >= threshold and host_name_match and page_name_match and page_lane_match
        identity = CompanyIdentity(
            query_name=name,
            canonical_name=name.strip(),
            website=canonical_website(final_url),
            official_domain=host,
            lane=lane,
            status="verified" if verified else "rejected",
            confidence=round(score, 2),
            reason=(
                "Dedicated domain, company name, and technical lane agree."
                if verified
                else _identity_rejection_reason(
                    host_name_match=host_name_match,
                    page_name_match=page_name_match,
                    page_lane_match=page_lane_match,
                    employer_match=employer_match,
                    ambiguous_acronym=ambiguous_acronym,
                )
            ),
            evidence_urls=urls,
            evidence_titles=titles,
        )
        if best is None or score > best[0]:
            best = (score, identity)

    if best is not None:
        return best[1]
    return CompanyIdentity(
        query_name=name,
        canonical_name=name.strip(),
        website="",
        official_domain="",
        lane=lane,
        status="rejected",
        confidence=0.0,
        reason="The dedicated domain could not be fetched for verification.",
        evidence_urls=urls,
        evidence_titles=titles,
    )


PROBE_TLDS = ("com", "ai", "co", "io")


def official_site_candidates(name: str) -> list[str]:
    """Name-derived official-domain guesses, most common TLDs first."""
    normalized = _normalized_name(name)
    if not normalized:
        return []
    return [f"https://{normalized}.{tld}" for tld in PROBE_TLDS]


def resolve_company_identity_with_fallback(
    *,
    name: str,
    lane: str,
    evidence_urls: list[str],
    evidence_titles: list[str] | None = None,
    fetcher: Callable[[str], FetchedPage] = fetch_page,
    search: Callable[[str, int], list[dict[str, str]]] | None = None,
) -> CompanyIdentity:
    """Resolve identity from discovery evidence, then deterministic fallbacks.

    Discovery evidence can be polluted (a competitor's launch post mentioning
    the company name) or simply thin. When the first resolution is rejected,
    probe name-derived domains and then an official-site web search. Every
    candidate faces the same strict scorer — this widens the candidate pool,
    never the verification bar. When nothing verifies, the highest-confidence
    rejection is returned so the reason stays informative.
    """
    identity = resolve_company_identity(
        name=name,
        lane=lane,
        evidence_urls=evidence_urls,
        evidence_titles=evidence_titles,
        fetcher=fetcher,
    )
    if identity.verified:
        return identity

    titles = [title for title in (evidence_titles or []) if title.strip()]

    def candidate_batches():
        probes = official_site_candidates(name)
        if probes:
            yield probes, titles
        nonlocal search
        if search is None:
            from .sourcing.web_search import search as web_search  # noqa: PLC0415

            search = web_search
        try:
            results = search(f"{name} official website", 5)
        except Exception:
            results = []
        search_urls = [str(item.get("url", "")) for item in results if item.get("url")]
        search_titles = [str(item.get("title", "")) for item in results if item.get("title")]
        if search_urls:
            yield search_urls, [*titles, *search_titles]

    best = identity
    for urls, batch_titles in candidate_batches():
        candidate = resolve_company_identity(
            name=name,
            lane=lane,
            evidence_urls=urls,
            evidence_titles=batch_titles,
            fetcher=fetcher,
        )
        if candidate.verified:
            return candidate
        if candidate.confidence > best.confidence:
            best = candidate

    # A misspelled company name blocks correctly but unhelpfully; naming the
    # nearest real site that WAS fetched lets the reviewer spot the typo
    # ("Oblivious GPU Cloud" -> closest fetched candidate oblivus.com).
    if best.official_domain and "Closest fetched candidate" not in best.reason:
        from dataclasses import replace as _replace  # noqa: PLC0415

        best = _replace(
            best,
            reason=f"{best.reason} Closest fetched candidate: {best.official_domain}.",
        )
    return best
