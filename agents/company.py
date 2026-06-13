"""
Company Agent — researches a company and scores it for technical fit, hiring relevance, and reachability.
Uses LLM knowledge + public sources (HN, GitHub activity).
"""
from urllib.parse import urlparse

from upsearch import llm
from upsearch.company_identity import (
    resolve_company_identity,
    resolve_company_identity_with_fallback,
)
from upsearch.company_signal import fetch_company_signal
from upsearch.json_utils import parse_model_json_object
from upsearch.sourcing import hackernews

SYSTEM = """You are a Company Agent for an Opportunity Intelligence OS. Given a company name and target lane,
produce a structured company brief based on your knowledge and any provided source material.

Respond with valid JSON only:
{
  "name": "...",
  "website": "...",
  "lane": "...",
  "fit_score": <1-10>,
  "what_they_do": "1-2 sentence description of the product and tech stack",
  "why": "why this company is worth reaching out to for a student in this lane",
  "hiring_status": "actively_hiring | unknown | limited",
  "sponsorship_notes": "any notes on H1B sponsorship or internship programs",
  "open_source": ["repo1", "repo2"],
  "tech_stack": ["Python", "CUDA", "Kubernetes"],
  "recent_signal": "recent relevant activity — blog post, paper, HN discussion",
  "assumptions": ["assumption1"]
}

Be honest about uncertainty. Mark guesses with (assumed)."""


def _website_candidate(value: object) -> str:
    if not isinstance(value, str):
        return ""
    candidate = value.strip()
    if not candidate:
        return ""
    original = urlparse(candidate)
    if original.scheme and original.scheme not in {"http", "https"}:
        return ""
    if "://" not in candidate:
        candidate = f"https://{candidate}"
    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return ""
    return candidate


def run(company_name: str, lane: str, user_profile: dict, discovery_source_urls: list[str] | None = None) -> dict:
    # Enrich with HN discussions about this company
    hn_posts = hackernews.search(f"{company_name} {lane}", limit=3)
    discovery_source_urls = discovery_source_urls or []
    # Discovery evidence can be polluted (e.g. a competitor's launch post that
    # mentions the company); the fallback resolver also probes name-derived
    # official domains and an official-site search, all behind the same
    # strict verification scoring.
    identity = resolve_company_identity_with_fallback(
        name=company_name,
        lane=lane,
        evidence_urls=discovery_source_urls + [p.url for p in hn_posts if p.url],
        evidence_titles=[p.title for p in hn_posts],
    )
    hn_context = "\n".join(
        f"- [{p.source}] {p.title} ({p.score} pts)" for p in hn_posts
    ) if hn_posts else "No recent HN activity found."
    identity_context = (
        f"Identity status: {identity.status}\n"
        f"Canonical name: {identity.canonical_name}\n"
        f"Verified website: {identity.website or 'unknown'}\n"
        f"Official domain: {identity.official_domain or 'unknown'}\n"
        f"Identity reason: {identity.reason}\n"
        f"Evidence URLs: {identity.evidence_urls}"
    )

    user_ctx = (
        f"Student interests: {', '.join(user_profile.get('interests', []))}\n"
        f"Skills: {', '.join(user_profile.get('skills', []))}"
    )

    # Company website signal — careers pages and blog posts
    domain = identity.official_domain or identity.website or ""
    company_signal = fetch_company_signal(domain) if domain else {"error": "no domain"}
    signal_context = ""
    if company_signal.get("careers", {}).get("found"):
        c = company_signal["careers"]
        signal_context += f"\nHiring signal ({c['url']}): roles seeking: {', '.join(c['roles'][:6])}\n"
    else:
        signal_context += "\nNo careers page detected.\n"
    if company_signal.get("blog", {}).get("found"):
        b = company_signal["blog"]
        headlines = b.get("headlines", [])
        if headlines:
            signal_context += f"Blog ({b['url']}): recent posts: {' | '.join(headlines[:4])}\n"

    text = llm.complete(
        system=SYSTEM,
        user=(
            f"Company: {company_name}\nLane: {lane}\n\n"
            f"Company identity check:\n{identity_context}\n\n"
            f"Recent HN signal:\n{hn_context}\n\n"
            f"Company website signal:\n{signal_context}\n\n"
            f"Student context:\n{user_ctx}"
        ),
        max_tokens=800,
    )
    result = parse_model_json_object(text, {"name": company_name, "fit_score": 5, "why": "Parse error"})
    if not result:
        result = {"name": company_name, "fit_score": 5, "why": "Parse error"}

    # Public search results often contain only third-party coverage. Let the
    # model propose a website, but accept it only after the deterministic
    # identity verifier fetches the page and confirms name + lane agreement.
    website_candidate = _website_candidate(result.get("website"))
    if not identity.verified and website_candidate:
        identity = resolve_company_identity(
            name=company_name,
            lane=lane,
            evidence_urls=[website_candidate, *identity.evidence_urls],
            evidence_titles=[p.title for p in hn_posts],
        )

    if identity.verified:
        result["name"] = identity.canonical_name
        result["website"] = identity.website
        result["official_domain"] = identity.official_domain
        result["identity_status"] = identity.status
        result["identity_confidence"] = identity.confidence
        result["identity_reason"] = identity.reason
    else:
        result["identity_status"] = identity.status
        result["identity_confidence"] = identity.confidence
        result["identity_reason"] = identity.reason

    return {
        "result": result,
        "source_urls": list(dict.fromkeys(
            discovery_source_urls + [p.url for p in hn_posts] + identity.evidence_urls
        )),
        "identity": identity.to_dict(),
        "confidence": 0.7,
        "assumptions": result.get("assumptions", []),
        "next_action": "run_problem_agent",
    }
