"""GitHub org member search for people discovery.

Falls back to searching GitHub for contributors when the People Agent's
LLM output contains no verifiable source_urls. Returns real people with
real GitHub profile URLs.

The GitHub API is unauthenticated by default (rate-limited to 60 req/hr).
When GITHUB_TOKEN is set in the environment, the rate limit rises to 5000/hr.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

_GITHUB_API = "https://api.github.com"
_TIMEOUT = httpx.Timeout(10.0, connect=5.0)
_HEADERS = {
    "Accept": "application/vnd.github.v3+json",
    "User-Agent": "UpSearchOrgSearch/0.1",
}
_MAX_MEMBERS = 8
_MAX_LANGUAGES = 5
_MAX_READMES = 3


def _auth_headers() -> dict[str, str]:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        return {**_HEADERS, "Authorization": f"Bearer {token}"}
    return _HEADERS


def resolve_org_url(org_name: str) -> str | None:
    """Check if a GitHub org exists and return its URL."""
    try:
        with httpx.Client(timeout=_TIMEOUT, follow_redirects=True) as client:
            resp = client.get(f"{_GITHUB_API}/orgs/{org_name}", headers=_auth_headers())
            if resp.status_code == 200:
                return resp.json().get("html_url", f"https://github.com/{org_name}")
            return None
    except Exception as exc:
        logger.debug("resolve_org_url failed for %s: %s", org_name, exc)
        return None


def _fetch_readme_text(client: httpx.Client, org: str, repo: str) -> str:
    """Fetch repo README and return first meaningful line."""
    try:
        resp = client.get(f"{_GITHUB_API}/repos/{org}/{repo}/readme", headers=_auth_headers())
        if resp.status_code != 200:
            return ""
        import base64  # noqa: PLC0415
        content = resp.json().get("content", "")
        if not content:
            return ""
        decoded = base64.b64decode(content).decode("utf-8", errors="ignore")
        for line in decoded.splitlines():
            cleaned = line.strip("# *").strip()
            if cleaned and cleaned.lower() != repo.lower():
                return cleaned
        return ""
    except Exception:
        return ""


def _org_repos_evidence(client: httpx.Client, org: str) -> list[str]:
    """Collect brief evidence that this org matches the company."""
    evidence: list[str] = []
    try:
        resp = client.get(
            f"{_GITHUB_API}/orgs/{org}/repos",
            params={"sort": "updated", "per_page": str(_MAX_READMES), "type": "public"},
            headers=_auth_headers(),
        )
        if resp.status_code != 200:
            return evidence
        repos = resp.json()
        languages: set[str] = set()
        for repo in repos[:5]:
            name = repo.get("name", "")
            desc = repo.get("description") or ""
            lang = repo.get("language") or ""
            if lang:
                languages.add(lang)
            if desc:
                evidence.append(f"Repo {name}: {desc[:120]}")
            elif name:
                readme_line = _fetch_readme_text(client, org, name)
                if readme_line:
                    evidence.append(f"Repo {name}: {readme_line[:120]}")
        if languages:
            evidence.append(f"Languages: {', '.join(sorted(languages)[:_MAX_LANGUAGES])}")
    except Exception as exc:
        logger.debug("_org_repos_evidence failed: %s", exc)
    return evidence


_BOT_MARKERS = ("[bot]", "-bot", "dependabot", "renovate")


def _is_bot_login(login: str) -> bool:
    lowered = login.lower()
    return any(marker in lowered for marker in _BOT_MARKERS)


def _clean_display_name(name: str) -> str:
    """GitHub display names carry decorations ("Yufei (Benny) Chen"); keep the
    formal name so the person-name gate and outreach drafts get a clean value."""
    cleaned = re.sub(r"\([^)]*\)", " ", name)
    return " ".join(cleaned.split())


def _canonical_host(value: str) -> str:
    host = (urlparse(value).hostname or value or "").lower().strip().strip("/")
    return host[4:] if host.startswith("www.") else host


def _org_profile(client: httpx.Client, org_name: str) -> dict | None:
    try:
        resp = client.get(f"{_GITHUB_API}/orgs/{org_name}", headers=_auth_headers())
        return resp.json() if resp.status_code == 200 else None
    except Exception:
        return None


def _org_matches_company(profile: dict, company_name: str, company_domain: str) -> bool:
    """An org belongs to the company when its website matches the verified
    company domain, or its display name IS the company name (optionally with
    a corporate suffix). Containment is not enough — "Fireworks Photo App"
    contains "fireworks" without being Fireworks AI."""
    blog = str(profile.get("blog") or "")
    if company_domain and _canonical_host(blog) == _canonical_host(company_domain):
        return True
    # An org that declares a different website is a different company, no
    # matter how well the name matches ("Fireworks!" at fireworks-ai.com is
    # not Fireworks AI at fireworks.ai).
    if blog and company_domain and _canonical_host(blog) != _canonical_host(company_domain):
        return False
    org_title = re.sub(r"[^a-z0-9]", "", str(profile.get("name") or "").lower())
    company_token = re.sub(r"[^a-z0-9]", "", company_name.lower())
    if not company_token or not org_title:
        return False
    return org_title == company_token or org_title in {
        f"{company_token}{suffix}" for suffix in ("ai", "hq", "labs", "inc")
    }


_SITE_ORG_EXCLUDED = {
    "about", "apps", "blog", "contact", "features", "login", "marketplace",
    "orgs", "pricing", "readme", "search", "settings", "sponsors", "topics",
}


def orgs_from_company_site(company_domain: str, fetcher=None) -> list[str]:
    """GitHub org handles the company's own website links to.

    A company that links github.com/<org> from its homepage or docs is
    declaring ownership — the strongest possible org<->company signal, and it
    needs no name matching at all (Together AI's org is "togethercomputer").
    """
    domain = company_domain.lower().removeprefix("www.").strip("/")
    if not domain:
        return []
    if fetcher is None:
        def fetcher(url: str) -> str:
            try:
                with httpx.Client(timeout=_TIMEOUT, follow_redirects=True) as client:
                    resp = client.get(url, headers={"User-Agent": _HEADERS["User-Agent"]})
                    return resp.text[:200_000] if resp.status_code == 200 else ""
            except Exception:
                return ""

    handles: list[str] = []
    for url in (f"https://www.{domain}", f"https://docs.{domain}"):
        html = fetcher(url)
        for handle in re.findall(r"github\.com/([A-Za-z0-9][A-Za-z0-9_-]*)", html or ""):
            lowered = handle.lower()
            if lowered not in _SITE_ORG_EXCLUDED and handle not in handles:
                handles.append(handle)
    return handles[:5]


def find_company_org(
    company_name: str,
    company_domain: str = "",
    candidates: list[str] | None = None,
) -> str | None:
    """Resolve the company's GitHub org.

    Resolution order:
    1. Orgs the company's own site links to — declaration is ownership, so
       these need only exist and not be domain-vetoed.
    2. Name-derived guesses, accepted only on metadata match (website ==
       verified domain, or display-name match) — bare existence is not
       ownership ("fireworks" the org is not Fireworks AI).
    3. The GitHub org search API, confirmed the same way as guesses.
    """
    try:
        with httpx.Client(timeout=_TIMEOUT, follow_redirects=True) as client:
            for declared in orgs_from_company_site(company_domain):
                profile = _org_profile(client, declared)
                if not profile:
                    continue
                blog_host = _canonical_host(str(profile.get("blog") or ""))
                if blog_host and company_domain and blog_host != _canonical_host(company_domain):
                    continue
                return declared

            for candidate in candidates or []:
                profile = _org_profile(client, candidate)
                if profile and _org_matches_company(profile, company_name, company_domain):
                    return candidate

            resp = client.get(
                f"{_GITHUB_API}/search/users",
                params={"q": f"{company_name} type:org", "per_page": "5"},
                headers=_auth_headers(),
            )
            if resp.status_code != 200:
                return None
            for item in resp.json().get("items", []):
                login = item.get("login", "")
                if not login:
                    continue
                profile = _org_profile(client, login)
                if profile and _org_matches_company(profile, company_name, company_domain):
                    return login
    except Exception as exc:
        logger.debug("find_company_org failed for %s: %s", company_name, exc)
    return None


def _org_member_logins(client: httpx.Client, org_name: str) -> list[str]:
    """Public org members, if any are visible."""
    resp = client.get(
        f"{_GITHUB_API}/orgs/{org_name}/members",
        params={"per_page": str(_MAX_MEMBERS)},
        headers=_auth_headers(),
    )
    if resp.status_code != 200:
        logger.debug("GitHub org members fetch failed: %s", resp.status_code)
        return []
    return [member.get("login", "") for member in resp.json() if member.get("login")]


def _repo_problem_score(repo: dict, problem_keywords: list[str]) -> int:
    """Token overlap between a repo's name/description/topics and the problem."""
    text = " ".join([
        str(repo.get("name") or ""),
        str(repo.get("description") or ""),
        " ".join(repo.get("topics") or []),
    ]).lower()
    tokens = set(re.findall(r"[a-z0-9]+", text))
    return sum(1 for keyword in problem_keywords if keyword in tokens)


def _org_contributor_logins(
    client: httpx.Client,
    org_name: str,
    problem_keywords: list[str] | None = None,
) -> tuple[list[tuple[str, str]], set[str]]:
    """((login, repo) pairs, problem-matched repo names) for top contributors.

    Most org members hide their membership, so the public members list is
    often empty. Repo contributors are always public and are usually the
    people closest to the code. Repos are ranked by problem-keyword overlap
    before recency, so contributors come from the repo that implements the
    problem area — not merely the most recently pushed one. The repo is kept
    as the evidence coordinate that verification re-fetches independently.
    """
    resp = client.get(
        f"{_GITHUB_API}/orgs/{org_name}/repos",
        params={"sort": "pushed", "per_page": "10", "type": "public"},
        headers=_auth_headers(),
    )
    if resp.status_code != 200:
        return [], set()
    repos = [repo for repo in resp.json() if repo.get("name")]
    keywords = problem_keywords or []
    scored = sorted(
        enumerate(repos),
        key=lambda pair: (-_repo_problem_score(pair[1], keywords), pair[0]),
    )
    matched_repos = {
        repo.get("name", "")
        for _, repo in scored
        if keywords and _repo_problem_score(repo, keywords) > 0
    }
    pairs: list[tuple[str, str]] = []
    for _, repo in scored[:3]:
        repo_name = repo.get("name", "")
        contrib_resp = client.get(
            f"{_GITHUB_API}/repos/{org_name}/{repo_name}/contributors",
            params={"per_page": "5"},
            headers=_auth_headers(),
        )
        if contrib_resp.status_code != 200:
            continue
        pairs.extend(
            (item.get("login", ""), repo_name)
            for item in contrib_resp.json()
            if item.get("login")
        )
    return pairs, matched_repos


def search_org_members(
    company_name: str,
    org_name: str,
    problem_keywords: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Search for people at a GitHub org.

    Candidates come from public org members, falling back to top repo
    contributors (always public) when membership is hidden; contributor repos
    are ranked by problem-keyword relevance. Each candidate's ``source_url``
    is their GitHub profile page; verification status is NOT pre-claimed
    here — every candidate still passes the evidence-first verification
    pipeline.

    Returns an empty list when the org doesn't exist or the API fails.
    """
    org_url = resolve_org_url(org_name)
    if not org_url:
        logger.debug("GitHub org '%s' not found for company '%s'", org_name, company_name)
        return []

    people: list[dict[str, Any]] = []
    matched_repos: set[str] = set()
    try:
        with httpx.Client(timeout=_TIMEOUT, follow_redirects=True) as client:
            login_repos: dict[str, str] = {
                login: "" for login in _org_member_logins(client, org_name)
            }
            source_kind = "github_org_member"
            if len(login_repos) < 2:
                contributor_pairs, matched_repos = _org_contributor_logins(
                    client, org_name, problem_keywords
                )
                if contributor_pairs:
                    source_kind = "github_repo_contributor"
                    for login, repo in contributor_pairs:
                        login_repos.setdefault(login, repo)
            logins = [
                login for login in login_repos if not _is_bot_login(login)
            ][:_MAX_MEMBERS]

            for login in logins:
                profile_url = f"https://github.com/{login}"

                # Fetch user details for display name/bio
                name = login
                bio = ""
                try:
                    user_resp = client.get(
                        f"{_GITHUB_API}/users/{login}",
                        headers=_auth_headers(),
                    )
                    if user_resp.status_code == 200:
                        user_data = user_resp.json()
                        name = _clean_display_name(user_data.get("name") or "") or login
                        bio = (user_data.get("bio") or "")[:200]
                except Exception:
                    pass

                repo = login_repos.get(login, "")
                problem_relevant = bool(repo) and repo in matched_repos
                reason_parts = [
                    f"Contributor to {org_name}/{repo}, the repo matching this packet's problem area"
                    if problem_relevant
                    else f"GitHub contributor to {org_name}"
                ]
                if bio:
                    reason_parts.append(f"Bio: {bio[:160]}")

                people.append({
                    "name": name,
                    "role": f"GitHub contributor at {company_name}",
                    "proximity": "engineer",
                    "source_url": profile_url,
                    "github_url": profile_url,
                    "relevance_score": 8 if problem_relevant else 7,
                    "relevance_reason": "; ".join(reason_parts),
                    "source": source_kind,
                    "outreach_note": (
                        f"Their contributions to {org_name}/{repo}"
                        if problem_relevant
                        else f"GitHub activity in {org_name} org"
                    ),
                    # Evidence coordinates for independent re-verification:
                    # the public contributors/membership listing links the
                    # login to the org; the org profile links org to company.
                    "github_evidence": {
                        "org": org_name,
                        "repo": login_repos.get(login, ""),
                        "login": login,
                    },
                })
    except Exception as exc:
        logger.debug("search_org_members failed for %s: %s", org_name, exc)
        return []

    return people
