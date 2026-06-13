"""Company auto-discovery from public signals.

Given a technical lane (e.g. "ai_infra", "inference_systems"), searches
public sources for candidate companies. Returns ranked results with
source URLs so the user can verify.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .company_identity import resolve_company_identity
from .sourcing import hackernews, reddit, web_search
from .sourcing.base import Post
from .sourcing.github_org_search import search_github_orgs
from .sourcing.rss_feeds import search as rss_search, _extract_company_name as rss_extract_company


# Lane keywords used to construct search queries
# Each lane has both technical keywords AND hiring/funding keywords
# to catch both project discussions and "Who's Hiring" threads.
LANE_KEYWORDS = {
    "ai_infra": [
        "hiring AI infrastructure", "hiring ML platform", "hiring GPU cloud",
        "AI infrastructure", "ML platform", "GPU cloud",
    ],
    "inference_systems": [
        "hiring inference", "hiring LLM inference", "hiring model serving",
        "LLM inference", "model serving", "inference engine", "GPU inference",
    ],
    "agentic_ai": [
        "hiring AI agents", "hiring agent infrastructure",
        "AI agents", "agent framework", "agentic", "autonomous AI",
    ],
    "developer_tools": [
        "hiring developer tools", "hiring devtools",
        "developer tools", "devtools", "IDE", "developer platform", "API platform",
    ],
    "data_platforms": [
        "hiring data platform", "hiring data infrastructure",
        "data platform", "data infrastructure", "analytics", "data pipeline",
    ],
    "robotics_ai": [
        "hiring robotics", "hiring robot AI",
        "robotics", "robot AI", "autonomous robots", "robot learning", "embodied AI",
    ],
}

# Canonical lane names (e.g. ``lane:`` in agent/system.yaml) that are broader
# than a single LANE_KEYWORDS entry. discover() expands an alias to its mapped
# lanes and merges the results instead of degrading to a literal-string search.
# Keys are normalized: lowercase with spaces/hyphens collapsed to underscores.
LANE_ALIASES: dict[str, list[str]] = {
    "ai_infrastructure_and_inference": ["ai_infra", "inference_systems"],
}


def _normalize_lane_key(lane: str) -> str:
    return re.sub(r"[\s\-]+", "_", lane.strip().lower())


def resolve_lanes(lane: str) -> list[str]:
    """Resolve a lane name to one or more concrete LANE_KEYWORDS lanes.

    Aliases (including hyphen/space variants) expand to their mapped lanes;
    hyphen/space variants of canonical lanes normalize to the canonical key;
    unknown lanes pass through unchanged, preserving the existing
    literal-keyword degrade behavior.
    """
    normalized = _normalize_lane_key(lane)
    if normalized in LANE_ALIASES:
        return list(LANE_ALIASES[normalized])
    if normalized in LANE_KEYWORDS:
        return [normalized]
    return [lane]


# Keywords that suggest a result is a company, not a person or generic post
COMPANY_SIGNAL = re.compile(
    r"(series\s+[abc]|funding|seed|startup|company|hiring|launch|announcing|inc\b|corp\b|\.com\b)",
    re.I,
)


@dataclass(frozen=True)
class CompanyCandidate:
    name: str
    lane: str
    website: str = ""
    official_domain: str = ""
    identity_status: str = "unverified"
    identity_confidence: float = 0.0
    identity_reason: str = ""
    source_urls: list[str] = field(default_factory=list)
    fit_guess: float = 0.5
    source_labels: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "lane": self.lane,
            "website": self.website,
            "official_domain": self.official_domain,
            "identity_status": self.identity_status,
            "identity_confidence": self.identity_confidence,
            "identity_reason": self.identity_reason,
            "source_urls": self.source_urls,
            "fit_guess": self.fit_guess,
            "source_labels": self.source_labels,
            "evidence": self.evidence,
        }


def _rank_candidates(candidates: dict[str, CompanyCandidate]) -> list[CompanyCandidate]:
    """Rank by fit_guess descending. Name-deduplicate by lowercase."""
    seen: set[str] = set()
    ranked: list[CompanyCandidate] = []
    for c in sorted(candidates.values(), key=lambda x: x.fit_guess, reverse=True):
        key = c.name.lower().strip()
        if key and key not in seen:
            seen.add(key)
            ranked.append(c)
    return ranked


def _extract_company_names(text: str) -> list[str]:
    """Extract company names from post titles and bodies.

    Patterns matched:
    - "CompanyName (YC S24)"           — YC batch identifier
    - "Show HN: CompanyName"            — Show HN launch
    - "Launch HN: CompanyName"          — Launch HN
    - "Hiring CompanyName"              — "Who's Hiring" threads
    - "CompanyName — description"       — title separator pattern
    """
    names: list[str] = []
    # YC batch pattern: "CompanyName (YC S24)" or "CompanyName (YC W25)"
    for match in re.finditer(r"([A-Z][a-zA-Z0-9]+(?:\s+[A-Z][a-zA-Z0-9]+)*)\s*\(YC\s+\w+\d+\)", text):
        names.append(match.group(1).strip())
    # Show HN / Launch HN with optional colon
    for match in re.finditer(
        r"(?:Show|Launch)\s+HN:?\s+([A-Z][a-zA-Z0-9]*(?:\s+[A-Z][a-zA-Z0-9]*){0,3})(?=\s*(?:[-–—:|]|\(|$))",
        text,
    ):
        names.append(match.group(1).strip())
    # "Hiring CompanyName" — common in "Who's Hiring" threads
    for match in re.finditer(r"(?:Hiring|We're hiring|hiring:)\s+([A-Z][a-zA-Z0-9]+(?:\s+[A-Z][a-zA-Z0-9]+)*)", text):
        names.append(match.group(1).strip())
    # "CompanyName — description" pattern (capitalized word(s) before em-dash)
    for match in re.finditer(
        r"^([A-Z][a-z0-9]+(?:\s+[A-Z][a-z0-9]+)*)\s*[—–\-|]\s+.+",
        text,
    ):
        name = match.group(1).strip()
        if name and len(name) >= 2 and not name.startswith("I "):
            names.append(name)
    return list(dict.fromkeys(names))


# Words likely to be generic nouns, not company names
_GENERIC_WORDS = frozenset({
    "engineers", "agent", "agents", "humans", "human", "auto",
    "founder", "founders", "founding", "account", "executive", "manager", "managers",
    "engineer", "developer", "developers", "researcher", "researchers",
    "intern", "interns", "internship", "internships", "student", "students",
    "startup", "startups", "company", "companies", "team", "teams",
    "software", "hardware", "platform", "infrastructure", "product",
    "hiring", "recruiter", "recruiters", "remote", "onsite",
    "science", "scientist", "scientists", "data",
    "open", "jobs", "career", "careers", "role", "roles",
    "full-time", "part-time", "contractor", "consultant",
})


def _is_likely_not_a_company(name: str) -> bool:
    """Heuristic rejection of clearly non-company names."""
    nl = name.strip().lower()
    if nl in _GENERIC_WORDS:
        return True
    if len(nl.split()) >= 2 and nl.split()[-1] in {
        "engineer", "engineers", "developer", "developers",
        "researcher", "researchers", "manager", "managers",
        "scientist", "scientists", "intern", "interns",
        "executive", "recruiter", "recruiters", "officer",
    }:
        return True
    return False


def _candidate_from_post(name: str, lane: str, post: Any) -> CompanyCandidate | None:
    # Reject clearly non-company names
    if _is_likely_not_a_company(name):
        return None

    # Try identity resolution but don't require it — accept unverified candidates too
    # so discovery is generous. Verification happens in the pipeline's Company agent.
    identity = resolve_company_identity(
        name=name,
        lane=lane,
        evidence_urls=[post.url] if post.url else [],
        evidence_titles=[f"{post.title} {post.body[:400]}"],
    )
    if identity.verified:
        return CompanyCandidate(
            name=identity.canonical_name,
            lane=lane,
            website=identity.website,
            official_domain=identity.official_domain,
            identity_status=identity.status,
            identity_confidence=identity.confidence,
            identity_reason=identity.reason,
            source_urls=identity.evidence_urls,
            fit_guess=max(0.5, identity.confidence),
            source_labels=[post.source],
            evidence=[
                f"{post.source}: {post.title[:160]}",
                identity.reason,
            ],
        )
    # Fallback: unverified candidate with lower fit guess
    # The Company agent in the pipeline will do proper identity resolution
    return CompanyCandidate(
        name=name.strip(),
        lane=lane,
        identity_status="discovered",
        identity_confidence=0.3,
        identity_reason="Extracted from public signal; pending identity verification.",
        source_urls=[post.url] if post.url else [],
        fit_guess=0.4,
        source_labels=[post.source, "unverified"],
        evidence=[
            f"{post.source}: {post.title[:160]}",
            "Awaiting company identity verification.",
        ],
    )


# Lane-specific engineering-blog search queries for web search
_ENGINEERING_BLOG_QUERIES: dict[str, list[str]] = {
    "ai_infra": [
        "AI infrastructure engineering blog 2026",
        "ML platform engineering blog 2025",
    ],
    "inference_systems": [
        "LLM inference engineering blog 2026",
        "model serving engineering blog 2025",
    ],
    "agentic_ai": [
        "AI agent engineering blog 2026",
        "agent framework engineering blog 2025",
    ],
    "developer_tools": [
        "developer tools engineering blog 2026",
    ],
    "data_platforms": [
        "data platform engineering blog 2026",
    ],
    "robotics_ai": [
        "robotics engineering blog 2026",
    ],
}

_DISCOVERY_LANE_SIGNALS: dict[str, tuple[str, ...]] = {
    "ai_infra": (
        "ai infrastructure",
        "ml infrastructure",
        "ml platform",
        "gpu cloud",
        "gpu compute",
        "infrastructure for ai",
        "search infrastructure for ai",
        "model serving",
        "inference platform",
        "training platform",
    ),
    "inference_systems": (
        "inference",
        "model serving",
        "llm serving",
        "gpu serving",
        "serving engine",
        "latency",
        "vllm",
        "tensorrt",
    ),
    "agentic_ai": (
        "ai agent",
        "agentic",
        "agent framework",
        "agent infrastructure",
        "agent orchestration",
        "tool use",
    ),
    "developer_tools": (
        "developer tool",
        "devtool",
        "developer platform",
        "software development",
        "code editor",
        "ide",
        "sdk",
    ),
    "data_platforms": (
        "data platform",
        "data infrastructure",
        "database",
        "data pipeline",
        "etl",
        "warehouse",
        "analytics platform",
    ),
    "robotics_ai": (
        "robotics",
        "robot learning",
        "embodied ai",
        "autonomous robot",
        "robot foundation model",
        "robot simulation",
    ),
}


def _matches_lane_signal(lane: str, *values: str) -> bool:
    text = " ".join(values).lower()
    signals = _DISCOVERY_LANE_SIGNALS.get(
        lane,
        (lane.replace("_", " "),),
    )
    return any(signal in text for signal in signals)


# Post-title markers for launch/hiring announcements that deserve a weaker
# lane bar (they name companies directly but rarely repeat full lane phrases).
_HIRING_LAUNCH_MARKERS = ("launch hn", "show hn", "is hiring")

# Words from lane signal phrases too generic to count as lane terms alone.
_LANE_TERM_STOPWORDS = frozenset({"a", "an", "and", "for", "of", "the", "to", "use"})


def _lane_terms(lane: str) -> frozenset[str]:
    """Individual significant words drawn from the lane's signal phrases."""
    signals = _DISCOVERY_LANE_SIGNALS.get(lane, (lane.replace("_", " "),))
    terms: set[str] = set()
    for signal in signals:
        for word in re.findall(r"[a-z0-9]+", signal.lower()):
            if word not in _LANE_TERM_STOPWORDS:
                terms.add(word)
    return frozenset(terms)


def _passes_post_lane_gate(lane: str, post: Post) -> bool:
    """Lane-signal gate for HN/Reddit posts, mirroring the github/RSS gates.

    Full bar: title+body matches a lane signal phrase. Escape hatch:
    launch/hiring posts ("Launch HN", "Show HN", "is hiring") pass the weaker
    bar of ANY single lane term in the title, so company announcements keep
    recall without admitting clearly off-lane posts.
    """
    if _matches_lane_signal(lane, post.title, post.body):
        return True
    title = post.title.lower()
    if any(marker in title for marker in _HIRING_LAUNCH_MARKERS):
        title_words = set(re.findall(r"[a-z0-9]+", title))
        return bool(title_words & _lane_terms(lane))
    return False


def _company_name_from_blog_title(title: str) -> str:
    prefix = title.split(" —")[0].split(" |")[0].split(" -")[0].strip()
    engineering_at = re.fullmatch(r"engineering\s+at\s+(.+)", prefix, flags=re.I)
    if engineering_at:
        return engineering_at.group(1).strip()
    engineering_suffix = re.fullmatch(r"(.+?)\s+engineering", prefix, flags=re.I)
    if engineering_suffix:
        return engineering_suffix.group(1).strip()
    blog_suffix = re.fullmatch(
        r"(.+?)\s+(?:engineering|technical|technology|developer)\s+blog",
        prefix,
        flags=re.I,
    )
    if blog_suffix:
        return blog_suffix.group(1).strip()
    generic_terms = {
        "article",
        "articles",
        "blog",
        "guide",
        "latest",
        "mlops",
        "model",
        "serving",
        "trends",
    }
    prefix_terms = set(re.findall(r"[a-z0-9]+", prefix.lower()))
    if (
        ":" in prefix
        or len(prefix.split()) > 4
        or re.search(r"\b20\d{2}\b", prefix)
        or re.search(r"\b(trends?|guide|future|how|why|what)\b", prefix, flags=re.I)
        or len(prefix_terms & generic_terms) >= 2
    ):
        return ""
    return prefix


def _candidate_key(candidate: CompanyCandidate) -> str:
    if candidate.official_domain:
        return f"domain:{candidate.official_domain.lower().removeprefix('www.')}"
    return f"name:{candidate.name.lower().strip()}"


def _matching_candidate_key(
    candidates: dict[str, CompanyCandidate],
    candidate: CompanyCandidate,
) -> str | None:
    new_domain = candidate.official_domain.lower().removeprefix("www.")
    new_name = candidate.name.lower().strip()
    for key, existing in candidates.items():
        existing_domain = existing.official_domain.lower().removeprefix("www.")
        if new_domain and existing_domain and new_domain == existing_domain:
            return key
        if new_name and existing.name.lower().strip() == new_name:
            return key
    return None


def _merge_or_create(
    candidates: dict[str, CompanyCandidate],
    candidate: CompanyCandidate,
    lane: str,  # noqa: ARG001
) -> None:
    """Merge a candidate by verified domain first, then normalized name.

    Repeated aggregator mentions may improve ranking, but never identity
    confidence or status. Only a candidate already verified by the identity
    resolver can supply verified identity fields.
    """
    existing_key = _matching_candidate_key(candidates, candidate)
    existing = candidates.get(existing_key) if existing_key else None
    if existing is None:
        candidates[_candidate_key(candidate)] = candidate
        return

    identity_source = max(
        (existing, candidate),
        key=lambda item: (
            item.identity_status == "verified",
            item.identity_confidence,
        ),
    )
    merged = CompanyCandidate(
        name=identity_source.name,
        lane=lane,
        website=identity_source.website,
        official_domain=identity_source.official_domain,
        identity_status=identity_source.identity_status,
        identity_confidence=max(existing.identity_confidence, candidate.identity_confidence),
        identity_reason=identity_source.identity_reason,
        source_urls=list(dict.fromkeys(existing.source_urls + candidate.source_urls)),
        fit_guess=min(1.0, existing.fit_guess + 0.1),
        source_labels=list(dict.fromkeys(existing.source_labels + candidate.source_labels)),
        evidence=existing.evidence + candidate.evidence,
    )
    if existing_key:
        del candidates[existing_key]
    candidates[_candidate_key(merged)] = merged


def _discover_from_github_orgs(
    lane: str,
    candidates: dict[str, CompanyCandidate],
) -> None:
    """Search GitHub organisations for companies active in *lane*."""
    orgs = search_github_orgs(lane, limit=5)
    for org in orgs:
        name = org.get("display_name") or org.get("name", "")
        website = org.get("website", "")
        if not name:
            continue
        if not _matches_lane_signal(
            lane,
            org.get("description", ""),
            org.get("repo_description", ""),
        ):
            continue
        repo_url = org.get("repo_url", "")
        evidence_titles = [
            " ".join(
                part
                for part in (
                    name,
                    org.get("description", ""),
                    org.get("repo_description", ""),
                )
                if part
            )
        ]
        identity = resolve_company_identity(
            name=name,
            lane=lane,
            evidence_urls=[website] if website else [],
            evidence_titles=evidence_titles,
        )
        verified = identity.verified
        _merge_or_create(
            candidates,
            CompanyCandidate(
                name=identity.canonical_name if verified else name.strip(),
                lane=lane,
                website=identity.website if verified else website,
                official_domain=identity.official_domain if verified else "",
                identity_status=identity.status if verified else "discovered",
                identity_confidence=identity.confidence if verified else 0.3,
                identity_reason=(
                    identity.reason
                    if verified
                    else "GitHub organization found; official company identity remains unverified."
                ),
                source_urls=list(dict.fromkeys(
                    ([website] if website else [])
                    + ([repo_url] if repo_url else [])
                )),
                fit_guess=max(0.45, identity.confidence) if verified else 0.45,
                source_labels=["github_org"] + ([] if verified else ["unverified"]),
                evidence=[
                    f"GitHub organisation: {name}",
                    *evidence_titles,
                ],
            ),
            lane,
        )


def _discover_from_engineering_blogs(
    lane: str,
    candidates: dict[str, CompanyCandidate],
) -> None:
    """Search the web for company engineering blogs matching *lane*.

    Each result whose URL contains a dedicated company domain feeds into
    identity resolution automatically via ``_candidate_from_post`` if a
    company name can be extracted; otherwise it is added as a bare-domain
    lead.
    """
    queries = _ENGINEERING_BLOG_QUERIES.get(lane, [f"{lane.replace('_', ' ')} engineering blog"])
    for query in queries:
        results = web_search.search(query, limit=3)
        for r in results:
            url = r.get("url", "")
            title = r.get("title", "")
            if not url or not title:
                continue
            # Try extracting a company name from the page title
            name = _company_name_from_blog_title(title)
            if _is_likely_not_a_company(name):
                continue
            if not name or len(name) < 2:
                continue

            candidate = _candidate_from_post(name, lane, Post(
                title=title,
                body="",
                url=url,
                source="web_blog",
            ))
            if candidate is None:
                continue
            _merge_or_create(candidates, candidate, lane)


def _discover_from_rss(
    lane: str,
    candidates: dict[str, CompanyCandidate],
) -> None:
    """Fetch curated RSS feeds and merge extracted companies into *candidates*.

    The same RSS sources are reused across all lanes since startup/funding
    news is lane-agnostic at discovery time.
    """
    rss_items = rss_search(feed_names=["techcrunch_startups", "techcrunch_funding", "yc_blog", "venturebeat", "thenewstack"], limit=12)
    for item in rss_items:
        company_name = item.get("company_name") or rss_extract_company(item.get("title", ""))
        if not company_name or _is_likely_not_a_company(company_name):
            continue
        if not _matches_lane_signal(
            lane,
            item.get("title", ""),
            item.get("summary", ""),
        ):
            continue
        item_url = item.get("link", "")
        item_source = item.get("source", "rss")
        _merge_or_create(
            candidates,
            CompanyCandidate(
                name=company_name.strip(),
                lane=lane,
                identity_status="discovered",
                identity_confidence=0.3,
                identity_reason=f"Extracted from {item_source} RSS; pending identity verification.",
                source_urls=[item_url] if item_url else [],
                fit_guess=0.45,
                source_labels=[item_source, "unverified"],
                evidence=[f"{item_source}: {item.get('title', '')[:120]}"],
            ),
            lane,
        )


def discover(lane: str, limit: int = 8) -> list[CompanyCandidate]:
    """Discover candidate companies in the given technical lane.

    Searches Hacker News, Reddit, GitHub organisations, engineering blogs,
    and curated RSS sources for discussions in the lane. An alias lane
    (see LANE_ALIASES) expands to its mapped lanes and merges their results.
    Returns ranked candidates with source URLs.
    Returns an empty list if nothing is found (no hallucination).
    """
    candidates: dict[str, CompanyCandidate] = {}
    for resolved_lane in resolve_lanes(lane):
        _collect_lane_candidates(resolved_lane, candidates)
    ranked = _rank_candidates(candidates)
    return ranked[:limit]


def _collect_lane_candidates(
    lane: str,
    candidates: dict[str, CompanyCandidate],
) -> None:
    """Run every discovery source for one concrete lane into *candidates*."""
    keywords = LANE_KEYWORDS.get(lane, [lane])

    for keyword in keywords[:3]:
        # HN search
        hn_posts = hackernews.search(keyword, limit=5)
        if hn_posts:
            for post in hn_posts:
                if not _passes_post_lane_gate(lane, post):
                    continue
                for name in _extract_company_names(post.title):
                    candidate = _candidate_from_post(name, lane, post)
                    if candidate is None:
                        continue
                    _merge_or_create(candidates, candidate, lane)

        # Reddit search (more general)
        reddit_posts = reddit.search(keyword, limit=3)
        if reddit_posts:
            for post in reddit_posts:
                if not _passes_post_lane_gate(lane, post):
                    continue
                for name in _extract_company_names(post.title):
                    if _is_likely_not_a_company(name):
                        continue
                    key = name.lower().strip()
                    if key not in candidates:
                        candidates[key] = CompanyCandidate(
                            name=name.strip(),
                            lane=lane,
                            identity_status="discovered",
                            identity_confidence=0.3,
                            identity_reason="Extracted from Reddit; pending identity verification.",
                            source_urls=[post.url] if post.url else [],
                            fit_guess=0.4,
                            source_labels=["reddit", "unverified"],
                            evidence=[f"Reddit ({post.subreddit}): {post.title[:120]}"],
                        )
                    else:
                        existing = candidates[key]
                        candidates[key] = CompanyCandidate(
                            name=existing.name,
                            lane=lane,
                            identity_status=existing.identity_status,
                            identity_confidence=existing.identity_confidence,
                            identity_reason=existing.identity_reason,
                            source_urls=list(dict.fromkeys(existing.source_urls + ([post.url] if post.url else []))),
                            fit_guess=min(1.0, existing.fit_guess + 0.1),
                            source_labels=list(dict.fromkeys(existing.source_labels + ["reddit"])),
                            evidence=existing.evidence + [f"Reddit ({post.subreddit}): {post.title[:120]}"],
                        )

    # New source types — called once per lane, not once per keyword

    # GitHub org search
    _discover_from_github_orgs(lane, candidates)

    # Engineering blog search (web)
    _discover_from_engineering_blogs(lane, candidates)

    # Curated RSS feeds
    _discover_from_rss(lane, candidates)


def discover_all_lanes(lanes: list[str] | None = None, limit_per_lane: int = 3) -> dict[str, list[CompanyCandidate]]:
    """Discover companies across multiple lanes. Returns {lane: [candidates]}."""
    if lanes is None:
        lanes = list(LANE_KEYWORDS.keys())
    results: dict[str, list[CompanyCandidate]] = {}
    for lane in lanes:
        results[lane] = discover(lane, limit=limit_per_lane)
    return results
