"""Profile Source Fetch Agent.

Fetches public profile sources such as GitHub and personal websites, then
returns conservative proof candidates. This agent does not fetch LinkedIn yet;
authenticated sources should be wired through an explicit browser connector.
"""

from __future__ import annotations

import base64
import json
import re
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
from io import BytesIO
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlparse

import httpx
from pypdf import PdfReader

from .profile_harness import extract_profile_urls


CACHE_PATH = Path(".upsearch/profile/source-fetch.json")
MAX_TEXT_CHARS = 4000
MAX_REPOS = 10
MAX_READMES = 4
MAX_SOURCES = 12
MAX_DISCOVERY_DEPTH = 2
MAX_PDF_BYTES = 8_000_000

PROFILE_PAGE_PATHS = {"about", "bio", "cv", "portfolio", "profile", "projects", "resume", "work"}


@dataclass(frozen=True)
class SourceFetchItem:
    kind: str
    url: str
    status: str
    title: str = ""
    summary: str = ""
    proof_candidates: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    discovered_from: str = ""
    discovered_urls: list[str] = field(default_factory=list)
    contact_candidates: list[str] = field(default_factory=list)
    facts: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class SourceFetchReport:
    fetched_at: str
    sources: list[SourceFetchItem]
    proof_candidates: list[str]
    warnings: list[str]
    seed_urls: list[str] = field(default_factory=list)
    discovered_urls: list[str] = field(default_factory=list)
    contact_candidates: list[str] = field(default_factory=list)
    profile_facts: dict[str, str] = field(default_factory=dict)
    fact_provenance: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["sources"] = [asdict(source) for source in self.sources]
        return data


def load_cached_report() -> dict | None:
    if not CACHE_PATH.exists():
        return None
    try:
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def write_cached_report(report: dict) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _host(url: str) -> str:
    return urlparse(url).hostname or ""


def _source_kind(url: str) -> str:
    host = _host(url)
    path = urlparse(url).path.lower()
    if "github.com" in host:
        return "github"
    if "linkedin.com" in host:
        return "linkedin"
    if path.endswith(".pdf") or any(part in path for part in ("/resume", "/cv")):
        return "resume"
    return "web"


def _clean_text(text: str) -> str:
    text = re.sub(r"<script[\s\S]*?</script>", " ", text, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _meta_content(html: str, name: str) -> str:
    pattern = re.compile(
        rf"<meta[^>]+(?:name|property)=[\"']{re.escape(name)}[\"'][^>]+content=[\"']([^\"']+)[\"']",
        re.I,
    )
    match = pattern.search(html)
    return unescape(match.group(1)).strip() if match else ""


def _title(html: str) -> str:
    match = re.search(r"<title[^>]*>([\s\S]*?)</title>", html, re.I)
    return _clean_text(match.group(1)) if match else ""


def _headings(html: str) -> list[str]:
    matches = re.findall(r"<h[1-3][^>]*>([\s\S]*?)</h[1-3]>", html, re.I)
    cleaned = [_clean_text(match) for match in matches]
    return [item for item in cleaned if item][:8]


class _LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        href = dict(attrs).get("href")
        if href:
            self.links.append(href.strip())


def _canonical_source_url(url: str) -> str:
    value = urldefrag(url.strip())[0].rstrip("/")
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return ""
    host = parsed.hostname.lower()
    parts = [part for part in parsed.path.split("/") if part]
    if host in {"github.com", "www.github.com"} and parts:
        return f"https://github.com/{parts[0]}"
    if host in {"linkedin.com", "www.linkedin.com"} and len(parts) >= 2 and parts[0] == "in":
        return f"https://www.linkedin.com/in/{parts[1]}"
    return value


def _is_relevant_profile_link(base_url: str, candidate: str) -> bool:
    parsed = urlparse(candidate)
    host = (parsed.hostname or "").lower()
    path = parsed.path.lower()
    if host in {"github.com", "www.github.com"} and path.strip("/"):
        return True
    if host in {"linkedin.com", "www.linkedin.com"} and path.startswith("/in/"):
        return True
    if path.endswith(".pdf") and any(token in path for token in ("resume", "cv")):
        return True
    base_host = _host(base_url).lower()
    first_path = next((part for part in path.split("/") if part), "")
    return host == base_host and first_path in PROFILE_PAGE_PATHS


def _extract_web_edges(html: str, base_url: str) -> tuple[list[str], list[str]]:
    parser = _LinkParser()
    parser.feed(html)
    discovered: list[str] = []
    contacts: list[str] = []
    for href in parser.links:
        if href.startswith("mailto:"):
            email = href.removeprefix("mailto:").split("?", 1)[0].strip()
            if email:
                contacts.append(email)
            continue
        if href.startswith("tel:"):
            phone = href.removeprefix("tel:").strip()
            if phone:
                contacts.append(phone)
            continue
        candidate = _canonical_source_url(urljoin(base_url, href))
        if candidate and _is_relevant_profile_link(base_url, candidate):
            discovered.append(candidate)
    return list(dict.fromkeys(discovered)), list(dict.fromkeys(contacts))


def _client() -> httpx.Client:
    return httpx.Client(
        timeout=httpx.Timeout(10.0, connect=5.0),
        follow_redirects=True,
        headers={
            "User-Agent": "UpSearchProfileSourceFetch/0.1",
            "Accept": "application/json,text/html,text/plain;q=0.8,*/*;q=0.5",
        },
    )


def _github_owner(url: str) -> str:
    path = urlparse(url).path.strip("/")
    return path.split("/")[0] if path else ""


def _fetch_github(client: httpx.Client, url: str, discovered_from: str = "") -> SourceFetchItem:
    owner = _github_owner(url)
    if not owner:
        return SourceFetchItem(
            kind="github",
            url=url,
            status="failed",
            warnings=["GitHub URL did not include a username."],
            discovered_from=discovered_from,
        )

    api_base = "https://api.github.com"
    warnings: list[str] = []
    proof: list[str] = []

    try:
        user_res = client.get(f"{api_base}/users/{owner}")
        user_res.raise_for_status()
        user = user_res.json()

        repos_res = client.get(
            f"{api_base}/users/{owner}/repos",
            params={"sort": "updated", "per_page": str(MAX_REPOS)},
        )
        repos_res.raise_for_status()
        repos = [
            repo for repo in repos_res.json()
            if not repo.get("fork") and not repo.get("archived")
        ][:MAX_REPOS]
    except Exception as exc:
        return SourceFetchItem(
            kind="github",
            url=url,
            status="failed",
            warnings=[f"GitHub fetch failed: {exc}"],
            discovered_from=discovered_from,
        )

    languages = sorted({repo.get("language") for repo in repos if repo.get("language")})
    if repos:
        repo_names = ", ".join(repo.get("name", "") for repo in repos[:5] if repo.get("name"))
        proof.append(
            f"GitHub shows {len(repos)} recent public repositories; visible projects include "
            f"{repo_names}. Source: {url}"
        )
    if languages:
        proof.append(f"GitHub language signal includes {', '.join(languages[:6])}. Source: {url}")

    readme_count = 0
    for repo in repos[:MAX_READMES]:
        repo_name = repo.get("name")
        description = (repo.get("description") or "").strip()
        language = repo.get("language") or "unknown language"
        html_url = repo.get("html_url") or ""
        if description:
            topics = ", ".join(repo.get("topics", [])[:5])
            topic_suffix = f"; topics: {topics}" if topics else ""
            proof.append(f"{repo_name}: {description} ({language}{topic_suffix}) {html_url}".strip())

        if readme_count >= MAX_READMES:
            continue
        try:
            readme_res = client.get(f"{api_base}/repos/{owner}/{repo_name}/readme")
            if readme_res.status_code == 404:
                continue
            readme_res.raise_for_status()
            readme = readme_res.json()
            content = base64.b64decode(readme.get("content", "")).decode("utf-8", errors="ignore")
            first_line = next((line.strip("# ").strip() for line in content.splitlines() if line.strip()), "")
            if first_line and first_line.lower() != repo_name.lower():
                proof.append(f"{repo_name} README signal: {first_line[:180]}. {html_url}")
            readme_count += 1
        except Exception as exc:
            warnings.append(f"README fetch skipped for {repo_name}: {exc}")

    summary_parts = []
    if user.get("name"):
        summary_parts.append(str(user["name"]))
    if user.get("bio"):
        summary_parts.append(str(user["bio"]))
    if languages:
        summary_parts.append(f"Languages: {', '.join(languages[:6])}")

    discovered_urls = []
    blog = _canonical_source_url(str(user.get("blog") or ""))
    if blog:
        discovered_urls.append(blog)

    return SourceFetchItem(
        kind="github",
        url=url,
        status="fetched",
        title=f"GitHub: {owner}",
        summary=" | ".join(summary_parts) or f"Fetched public GitHub profile for {owner}.",
        proof_candidates=proof[:10],
        warnings=warnings[:5],
        discovered_from=discovered_from,
        discovered_urls=discovered_urls,
        facts={
            key: value
            for key, value in {
                "name": str(user.get("name") or "").strip(),
                "github_url": str(user.get("html_url") or url).strip(),
                "website": blog,
            }.items()
            if value
        },
    )


def _fetch_web(client: httpx.Client, url: str, discovered_from: str = "") -> SourceFetchItem:
    try:
        response = client.get(url)
        response.raise_for_status()
        html = response.text[:100_000]
    except Exception as exc:
        return SourceFetchItem(
            kind="web",
            url=url,
            status="failed",
            warnings=[f"Website fetch failed: {exc}"],
            discovered_from=discovered_from,
        )

    title = _title(html) or _host(url)
    description = _meta_content(html, "description") or _meta_content(html, "og:description")
    headings = _headings(html)
    text = _clean_text(html)[:MAX_TEXT_CHARS]
    discovered_urls, contact_candidates = _extract_web_edges(html, str(response.url))

    proof: list[str] = []
    if description:
        proof.append(f"Website description: {description[:240]}. Source: {response.url}")
    for heading in headings[:5]:
        proof.append(f"Website section signal: {heading[:180]}. Source: {response.url}")
    if not proof and text:
        proof.append(f"Website text signal: {text[:240]}. Source: {response.url}")

    return SourceFetchItem(
        kind="web",
        url=url,
        status="fetched",
        title=title,
        summary=description or text[:320],
        proof_candidates=proof[:8],
        discovered_from=discovered_from,
        discovered_urls=discovered_urls,
        contact_candidates=contact_candidates,
        facts={
            "name": title
            if urlparse(str(response.url)).path in {"", "/"}
            and title
            and len(title) <= 100
            else "",
            "website": _canonical_source_url(str(response.url)),
        },
    )


def _resume_proof_candidates(text: str, url: str) -> list[str]:
    lines = [
        re.sub(r"\s+", " ", line).strip(" •\t")
        for line in text.splitlines()
        if re.sub(r"\s+", " ", line).strip(" •\t")
    ]
    proof: list[str] = []
    for line in lines:
        lower = line.lower()
        if len(line) < 35 or len(line) > 280:
            continue
        if lower.startswith(("technical skills", "professional experience", "selected projects")):
            continue
        if any(token in lower for token in (
            "built ", "developed ", "implemented ", "designed ", "created ",
            "contributed ", "improved ", "reviewed ", "received ", "ran experiments",
        )):
            proof.append(f"Resume evidence: {line} Source: {url}")
    return list(dict.fromkeys(proof))[:10]


def _resume_facts(text: str, url: str) -> dict[str, str]:
    lines = [
        re.sub(r"\s+", " ", line).strip()
        for line in text.splitlines()
        if re.sub(r"\s+", " ", line).strip()
    ]
    name = lines[0] if lines and len(lines[0]) <= 100 else ""
    email_match = re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", text)
    phone_match = re.search(r"(?:\+\d{1,3}\s*)?\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}", text)
    school_match = re.search(
        r"\b([A-Z][A-Za-z&.' -]{2,80}?(?:University|College))\b",
        text,
    )
    summary = ""
    for line in lines[1:8]:
        if len(line) >= 80 and "@" not in line:
            summary = line[:500]
            break
    return {
        key: value
        for key, value in {
            "name": name,
            "email": email_match.group(0) if email_match else "",
            "phone": phone_match.group(0) if phone_match else "",
            "school": school_match.group(1).strip() if school_match else "",
            "background_summary": summary,
            "resume_url": url,
        }.items()
        if value
    }


def _fetch_resume(client: httpx.Client, url: str, discovered_from: str = "") -> SourceFetchItem:
    try:
        response = client.get(url)
        response.raise_for_status()
        content = response.content
        if len(content) > MAX_PDF_BYTES:
            raise ValueError(f"resume exceeds {MAX_PDF_BYTES // 1_000_000} MB limit")
        reader = PdfReader(BytesIO(content))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception as exc:
        return SourceFetchItem(
            kind="resume",
            url=url,
            status="failed",
            warnings=[f"Resume fetch failed: {exc}"],
            discovered_from=discovered_from,
        )

    emails = re.findall(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", text)
    phones = re.findall(r"(?:\+\d{1,3}\s*)?\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}", text)
    discovered_urls = extract_profile_urls(text)
    first_line = next((line.strip() for line in text.splitlines() if line.strip()), "Resume")
    return SourceFetchItem(
        kind="resume",
        url=url,
        status="fetched",
        title=f"Resume: {first_line[:120]}",
        summary=_clean_text(text)[:500],
        proof_candidates=_resume_proof_candidates(text, url),
        discovered_from=discovered_from,
        discovered_urls=discovered_urls,
        contact_candidates=list(dict.fromkeys([*emails, *phones])),
        facts=_resume_facts(text, url),
    )


def fetch_profile_sources(raw_profile: str) -> dict:
    seed_urls = extract_profile_urls(raw_profile)
    items: list[SourceFetchItem] = []
    warnings: list[str] = []
    discovered_urls: list[str] = []
    queue = deque((url, "", 0) for url in seed_urls)
    seen: set[str] = set()

    with _client() as client:
        while queue and len(items) < MAX_SOURCES:
            queued_url, discovered_from, depth = queue.popleft()
            url = _canonical_source_url(queued_url)
            if not url or url in seen:
                continue
            seen.add(url)
            kind = _source_kind(url)
            if kind == "github":
                item = _fetch_github(client, url, discovered_from)
            elif kind == "linkedin":
                item = SourceFetchItem(
                    kind="linkedin",
                    url=url,
                    status="auth_required",
                    warnings=["LinkedIn source fetching requires an authenticated browser connector and explicit user approval."],
                    discovered_from=discovered_from,
                )
            elif kind == "resume":
                item = _fetch_resume(client, url, discovered_from)
            else:
                item = _fetch_web(client, url, discovered_from)
            items.append(item)
            warnings.extend(item.warnings)
            for discovered_url in item.discovered_urls:
                normalized = _canonical_source_url(discovered_url)
                if not normalized or normalized in seen:
                    continue
                discovered_urls.append(normalized)
                if depth < MAX_DISCOVERY_DEPTH:
                    queue.append((normalized, url, depth + 1))

    proof_candidates: list[str] = []
    contact_candidates: list[str] = []
    profile_facts: dict[str, str] = {}
    fact_provenance: dict[str, str] = {}
    proof_priority = {"resume": 0, "github": 1, "web": 2, "linkedin": 3}
    # Seed sources outrank discovered sources; within an origin, resume facts
    # outrank github, which outranks web. First write wins so the highest-trust
    # source keeps each fact.
    for item in sorted(
        items,
        key=lambda value: (bool(value.discovered_from), proof_priority.get(value.kind, 9)),
    ):
        if item.status == "fetched":
            proof_candidates.extend(item.proof_candidates)
            contact_candidates.extend(item.contact_candidates)
            for key, value in item.facts.items():
                if value and key not in profile_facts:
                    profile_facts[key] = value
                    fact_provenance[key] = item.url

    report = SourceFetchReport(
        fetched_at=_now(),
        sources=items,
        proof_candidates=list(dict.fromkeys(proof_candidates))[:24],
        warnings=list(dict.fromkeys(warnings))[:12],
        seed_urls=seed_urls,
        discovered_urls=list(dict.fromkeys(discovered_urls)),
        contact_candidates=list(dict.fromkeys(contact_candidates))[:8],
        profile_facts=profile_facts,
        fact_provenance=fact_provenance,
    ).to_dict()
    write_cached_report(report)
    return report
