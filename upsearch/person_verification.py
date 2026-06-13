"""Person Verification — evidence-first candidate validation.

Every candidate person produced by the People Agent must have a fetched public
source that explicitly links the person's name, role/relevance, and target
company. Candidates whose source_url cannot be fetched or whose fetched content
does not mention name + company + role/relevance are marked unverified and have
all contact URLs stripped.

This module never synthesizes LinkedIn slugs or any other contact URL.
"""
from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import urlparse

import httpx

from .person_validation import person_name_rejection

logger = logging.getLogger(__name__)

# Fields that are never trusted from model output without fetching that exact URL.
_CONTACT_URL_FIELDS = {"linkedin_url", "github_url", "twitter_url"}

_FETCH_TIMEOUT = httpx.Timeout(10.0, connect=5.0)
_FETCH_HEADERS = {
    "User-Agent": "UpSearchPersonVerification/0.1",
    "Accept": "text/html,text/plain;q=0.8,*/*;q=0.5",
}
_MAX_FETCH_CHARS = 50_000
_ROLE_STOPWORDS = {
    "and",
    "at",
    "for",
    "head",
    "lead",
    "of",
    "senior",
    "staff",
    "the",
}


def _host(url: str) -> str:
    try:
        return urlparse(url).hostname or ""
    except Exception:
        return ""


def _client() -> httpx.Client:
    return httpx.Client(
        timeout=_FETCH_TIMEOUT,
        follow_redirects=True,
        headers=_FETCH_HEADERS,
    )


def _is_http_url(url: str | None) -> bool:
    return bool(url and isinstance(url, str) and url.startswith(("http://", "https://")))


def fetch_source_text(url: str) -> str:
    """Fetch a public URL and return cleaned text content.

    Returns an empty string on any fetch failure (timeout, non-200, DNS error).
    This is intentionally conservative — a failed fetch means no evidence.
    """
    if not _is_http_url(url):
        return ""
    try:
        with _client() as client:
            resp = client.get(url)
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "")
            text = resp.text[:_MAX_FETCH_CHARS]
            return text
    except Exception as exc:
        logger.debug("fetch_source_text failed for %s: %s", url, exc)
        return ""


def _clean_html_text(html: str) -> str:
    """Strip HTML tags and normalize whitespace for evidence checking."""
    text = re.sub(r"<script\b[^>]*>.*?</script>", " ", html, flags=re.I | re.S)
    text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()[:10_000]


def _contains_phrase(text: str, phrase: str) -> bool:
    normalized = " ".join(phrase.lower().split())
    if not normalized:
        return False
    return re.search(rf"(?<![a-z0-9]){re.escape(normalized)}(?![a-z0-9])", text.lower()) is not None


def _role_or_relevance_terms(role: str, relevance_reason: str) -> set[str]:
    terms = {
        token
        for token in re.findall(r"[a-z0-9]+", f"{role} {relevance_reason}".lower())
        if len(token) >= 4 and token not in _ROLE_STOPWORDS
    }
    return terms


def evidence_checks(
    source_text: str,
    person_name: str,
    company_name: str,
    role: str = "",
    relevance_reason: str = "",
) -> dict[str, bool]:
    """Return deterministic checks for the person/company/relevance contract."""
    cleaned = _clean_html_text(source_text)
    relevance_terms = _role_or_relevance_terms(role, relevance_reason)
    return {
        "name": _contains_phrase(cleaned, person_name),
        "company": _contains_phrase(cleaned, company_name),
        "role_or_relevance": bool(relevance_terms) and any(
            _contains_phrase(cleaned, term) for term in relevance_terms
        ),
    }


def check_evidence(
    source_text: str,
    person_name: str,
    company_name: str,
    role: str = "",
    relevance_reason: str = "",
) -> bool:
    """Check whether source text links name, company, and role/relevance.

    The result is intentionally conservative and deterministic. A person is not
    verified merely because a page mentions their name and the company in
    unrelated sections; the page must also contain a role or relevance term.
    """
    if not source_text or not person_name or not company_name or not (role or relevance_reason):
        return False
    return all(evidence_checks(
        source_text,
        person_name,
        company_name,
        role,
        relevance_reason,
    ).values())


def check_contact_evidence(source_text: str, person_name: str, company_name: str) -> bool:
    """Check whether a contact page itself links the person to the company.

    Contact URLs are different from source evidence. A verified blog/team page
    can prove the person mapping, but it does not prove a model-supplied
    LinkedIn/GitHub/Twitter URL. That contact URL only survives when the exact
    URL is fetched and its content contains the person name and company.
    """
    if not source_text or not person_name or not company_name:
        return False
    cleaned = _clean_html_text(source_text)
    return _contains_phrase(cleaned, person_name) and _contains_phrase(cleaned, company_name)


def strip_model_contact_urls(person: dict) -> dict:
    """Return a copy with every model-supplied contact URL removed.

    The ``source_url`` field is always preserved — it is the evidence URL, not
    a contact channel. A later connector may resolve contact channels from a
    verified source, but generated URLs never pass through this verifier.
    """
    cleaned = dict(person)
    for field in _CONTACT_URL_FIELDS:
        cleaned[field] = None
    return cleaned


def strip_unverified_urls(person: dict, verified: bool) -> dict:
    """Compatibility wrapper: generated contact URLs are always stripped."""
    return strip_model_contact_urls(person)


def _verified_contact_urls(
    person: dict,
    *,
    person_name: str,
    company_name: str,
    source_url: str,
    source_text: str,
) -> tuple[dict[str, str | None], dict[str, dict[str, bool | str]]]:
    """Return contact URLs that independently pass exact-URL verification."""
    retained: dict[str, str | None] = {field: None for field in _CONTACT_URL_FIELDS}
    checks: dict[str, dict[str, bool | str]] = {}

    for field in _CONTACT_URL_FIELDS:
        contact_url = person.get(field)
        if not _is_http_url(contact_url):
            checks[field] = {"present": bool(contact_url), "fetched": False, "matched": False}
            continue

        if contact_url == source_url:
            contact_text = source_text
        else:
            contact_text = fetch_source_text(contact_url)

        matched = check_contact_evidence(contact_text, person_name, company_name)
        checks[field] = {
            "present": True,
            "fetched": bool(contact_text),
            "matched": matched,
            "url": contact_url,
        }
        if matched:
            retained[field] = contact_url

    return retained, checks


_GITHUB_API = "https://api.github.com"


def _github_auth_headers() -> dict[str, str]:
    import os  # noqa: PLC0415

    headers = {"Accept": "application/vnd.github.v3+json", "User-Agent": _FETCH_HEADERS["User-Agent"]}
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _canonical_host_token(value: str) -> str:
    host = (urlparse(value).hostname or value or "").lower().strip().strip("/")
    return host[4:] if host.startswith("www.") else host


def check_github_org_evidence(
    evidence: dict,
    company_name: str,
    memo: dict | None = None,
) -> tuple[bool, str]:
    """Independently re-verify a GitHub-sourced candidate against public API documents.

    A contributor's profile page often cannot prove the company link (private
    org membership, empty company field). The links that exist publicly are:
    the org's contributors/membership listing (login <-> org) and the org
    profile's declared website (org <-> verified company domain). Both are
    re-fetched here at verification time — nothing is trusted from sourcing.

    ``memo`` caches the org profile and contributor listings across one
    verification batch: a packet's candidates share an org, and re-fetching
    the same two documents per person added ~15s per run.
    """
    org = str(evidence.get("org") or "")
    login = str(evidence.get("login") or "")
    repo = str(evidence.get("repo") or "")
    company_domain = str(evidence.get("company_domain") or "")
    if not org or not login:
        return False, "github_evidence_incomplete"
    memo = memo if memo is not None else {}

    try:
        with _client() as client:
            org_key = ("org", org)
            if org_key not in memo:
                org_resp = client.get(f"{_GITHUB_API}/orgs/{org}", headers=_github_auth_headers())
                memo[org_key] = org_resp.json() if org_resp.status_code == 200 else None
            org_profile = memo[org_key]
            if org_profile is None:
                return False, "github_org_fetch_failed"
            blog_host = _canonical_host_token(str(org_profile.get("blog") or ""))
            org_title = re.sub(r"[^a-z0-9]", "", str(org_profile.get("name") or "").lower())
            company_token = re.sub(r"[^a-z0-9]", "", company_name.lower())
            domain_ok = bool(company_domain) and blog_host == _canonical_host_token(company_domain)
            # An org that declares a different website is a different company,
            # no matter how well the display name matches.
            if not domain_ok and blog_host and company_domain:
                return False, "github_org_company_mismatch"
            name_ok = bool(company_token) and (
                org_title == company_token
                or org_title in {f"{company_token}{s}" for s in ("ai", "hq", "labs", "inc")}
            )
            if not (domain_ok or name_ok):
                # Last resort, declaration check: the company's own site
                # linking github.com/<org> is ownership (Together AI's org
                # "Together"/togethercomputer has no blog and no name match).
                site_key = ("site", _canonical_host_token(company_domain))
                if company_domain and memo.get(site_key) is None:
                    from .github_org_search import orgs_from_company_site  # noqa: PLC0415

                    memo[site_key] = {
                        handle.lower()
                        for handle in orgs_from_company_site(company_domain)
                    }
                if org.lower() not in (memo.get(site_key) or set()):
                    return False, "github_org_company_mismatch"

            if repo:
                listing_key = ("listing", org, repo)
                if listing_key not in memo:
                    listing = client.get(
                        f"{_GITHUB_API}/repos/{org}/{repo}/contributors",
                        params={"per_page": "100"},
                        headers=_github_auth_headers(),
                    )
                    memo[listing_key] = (
                        {str(item.get("login", "")).lower() for item in listing.json()}
                        if listing.status_code == 200
                        else None
                    )
                listing_logins = memo[listing_key]
                if listing_logins and login.lower() in listing_logins:
                    return True, "github_contributor_listing_confirmed"
                return False, "github_contributor_not_in_listing"

            membership = client.get(
                f"{_GITHUB_API}/orgs/{org}/public_members/{login}",
                headers=_github_auth_headers(),
            )
            if membership.status_code == 204:
                return True, "github_public_membership_confirmed"
            return False, "github_membership_not_public"
    except Exception as exc:
        logger.debug("github evidence check failed for %s/%s: %s", org, login, exc)
        return False, "github_evidence_fetch_failed"


def check_author_page_evidence(evidence: dict, person_name: str) -> tuple[bool, str]:
    """Re-verify an author-page candidate against the page itself.

    An author page on the company's own domain whose title or first heading
    names the person is the person<->company link — the company published a
    byline page for them. Re-fetched here independently; the domain
    containment is re-checked against the URL, and the name against the page.
    """
    url = str(evidence.get("url") or "")
    company_domain = str(evidence.get("company_domain") or "").lower().removeprefix("www.")
    host = (_host(url) or "").lower().removeprefix("www.")
    if not url or not company_domain or host != company_domain:
        return False, "author_page_off_domain"

    html = fetch_source_text(url)
    if not html:
        return False, "author_page_fetch_failed"

    heads: list[str] = []
    title_match = re.search(r"<title[^>]*>([^<]{3,200})</title>", html, flags=re.I)
    if title_match:
        heads.append(title_match.group(1))
    heads.extend(re.findall(r"<h1[^>]*>([^<]{3,120})</h1>", html, flags=re.I))
    named = any(_contains_phrase(_clean_html_text(head), person_name) for head in heads)
    if named:
        return True, "author_page_title_confirmed"
    return False, "author_page_does_not_name_person"


def verify_person(person: dict, company_name: str, _github_memo: dict | None = None) -> dict:
    """Verify a single person against their source_url.

    Steps:
    1. Extract the source_url from the person dict.
    2. Fetch the URL and check for evidence linking name + company.
    3. Strip model-supplied contact URLs.
    4. Retain a contact URL only if that exact URL is fetched and its content
       links the person name to the target company.
    5. Tag the person with ``verification_status`` (``"verified"`` or
       ``"unverified"``).
    """
    name = person.get("name", "")
    source_url = person.get("source_url", "")
    role = person.get("role", "")
    relevance_reason = person.get("relevance_reason", "")
    result = strip_model_contact_urls(person)

    # Evidence checks prove a string appears on a company page — which nav
    # labels and article titles do by definition. A candidate that is not a
    # human name can never verify, regardless of what its source page says.
    name_rejection = person_name_rejection(name)
    if name_rejection:
        result["verification_status"] = "unverified"
        result["verification_reason"] = f"not_a_person_name:{name_rejection}"
        result["evidence_checks"] = {"name": False, "company": False, "role_or_relevance": False}
        result["contact_url_checks"] = {
            field: {"present": bool(person.get(field)), "fetched": False, "matched": False}
            for field in _CONTACT_URL_FIELDS
        }
        return result

    # GitHub-sourced candidates verify against public API documents (the
    # contributors/membership listing plus the org's declared website); their
    # profile HTML often legitimately cannot name the company.
    author_evidence = person.get("author_page_evidence")
    if isinstance(author_evidence, dict):
        confirmed, reason = check_author_page_evidence(author_evidence, name)
        result["verification_status"] = "verified" if confirmed else "unverified"
        result["verification_reason"] = reason
        result["evidence_checks"] = {
            "name": confirmed,
            "company": confirmed,
            "role_or_relevance": confirmed,
        }
        result["contact_url_checks"] = {
            field: {"present": bool(person.get(field)), "fetched": False, "matched": False}
            for field in _CONTACT_URL_FIELDS
        }
        return result

    github_evidence = person.get("github_evidence")
    if isinstance(github_evidence, dict):
        confirmed, reason = check_github_org_evidence(
            github_evidence, company_name, memo=_github_memo
        )
        result["verification_status"] = "verified" if confirmed else "unverified"
        result["verification_reason"] = reason
        result["evidence_checks"] = {
            "name": confirmed,
            "company": confirmed,
            "role_or_relevance": confirmed,
        }
        if confirmed and _is_http_url(person.get("github_url")):
            result["github_url"] = person.get("github_url")
        result["contact_url_checks"] = {
            field: {
                "present": bool(person.get(field)),
                "fetched": False,
                "matched": bool(confirmed and field == "github_url" and person.get(field)),
            }
            for field in _CONTACT_URL_FIELDS
        }
        return result

    if not source_url:
        result["verification_status"] = "unverified"
        result["verification_reason"] = "missing_source_url"
        result["evidence_checks"] = {"name": False, "company": False, "role_or_relevance": False}
        result["contact_url_checks"] = {
            field: {"present": bool(person.get(field)), "fetched": False, "matched": False}
            for field in _CONTACT_URL_FIELDS
        }
        return result

    raw_text = fetch_source_text(source_url)
    if not raw_text:
        result["verification_status"] = "unverified"
        result["verification_reason"] = "source_fetch_failed"
        result["evidence_checks"] = {"name": False, "company": False, "role_or_relevance": False}
        result["contact_url_checks"] = {
            field: {"present": bool(person.get(field)), "fetched": False, "matched": False}
            for field in _CONTACT_URL_FIELDS
        }
        return result

    checks = evidence_checks(raw_text, name, company_name, role, relevance_reason)
    verified = all(checks.values())
    result["verification_status"] = "verified" if verified else "unverified"
    result["verification_reason"] = "evidence_contract_passed" if verified else "evidence_contract_failed"
    result["evidence_checks"] = checks
    if verified:
        retained_contacts, contact_checks = _verified_contact_urls(
            person,
            person_name=name,
            company_name=company_name,
            source_url=source_url,
            source_text=raw_text,
        )
        result.update(retained_contacts)
        result["contact_url_checks"] = contact_checks
    else:
        result["contact_url_checks"] = {
            field: {"present": bool(person.get(field)), "fetched": False, "matched": False}
            for field in _CONTACT_URL_FIELDS
        }
    return result


def verify_people(people: list[dict], company_name: str) -> list[dict]:
    """Verify a list of candidate people against evidence-first rules.

    For each candidate:
    - Fetches the ``source_url`` and checks for name + company evidence.
    - Unverified candidates have all contact URLs set to ``None``.
    - Each returned dict gains a ``verification_status`` field.

    Args:
        people: List of person dicts (from People Agent output).
        company_name: Target company name, used for evidence matching.

    Returns:
        List of verified/unverified person dicts with contact URLs stripped
        where no evidence was found.
    """
    github_memo: dict = {}
    return [verify_person(p, company_name, _github_memo=github_memo) for p in people]
