"""Profile harness helpers for onboarding and claim boundaries.

This is the product-facing version of profile ingest: it turns the active
profile text into a small reviewable object before downstream agents use it.
"""

from __future__ import annotations

import re
import json
from dataclasses import dataclass, asdict, field
from pathlib import Path
from urllib.parse import urlparse

from agents import profile as profile_agent
from .config import load_settings
from .model_router import ModelRouter, TaskType


PROFILE_SOURCE_CACHE_PATH = Path(".upsearch/profile/source-fetch.json")
URL_RE = re.compile(
    r"(?:https?://)?(?:www\.)?(?:"
    r"github\.com/[^\s,)]+|"
    r"linkedin\.com/[^\s,)]+|"
    r"[a-z0-9][a-z0-9.-]+\.[a-z]{2,}(?:/[^\s,)]*)?"
    r")",
    re.I,
)


def enrich_profile_text(raw_profile: str) -> str:
    """Enrich raw profile text with fetched source data (GitHub, website).

    Loads the cached source fetch report and appends structured proof candidates
    as clear annotations. The profile agent then extracts richer skills, coursework,
    proof_points, and projects from this context.

    Falls back to the original text if no cache exists.
    """
    if not raw_profile.strip():
        return raw_profile

    # Lazy import to avoid circular dependency:
    # profile_source_fetch -> profile_harness (extract_profile_urls)
    from .profile_source_fetch import load_cached_report  # noqa: PLC0415

    cache = load_cached_report()
    if not cache:
        return raw_profile

    proof_candidates = cache.get("proof_candidates", [])
    cache_warnings = cache.get("warnings", [])
    if not proof_candidates:
        return raw_profile

    lines = [
        "",
        "--- Source enrichment (automatically fetched from public sources) ---",
    ]
    for proof in proof_candidates:
        lines.append(f"- {proof[:150]}")

    if cache_warnings:
        lines.append("")
        lines.append("Source fetch warnings:")
        for w in cache_warnings:
            lines.append(f"- {w[:150]}")

    lines.append("--- End source enrichment ---")
    return raw_profile.rstrip() + "\n".join(lines)


@dataclass(frozen=True)
class ProfileSource:
    kind: str
    value: str
    status: str
    discovered_from: str = ""
    origin: str = "seed"


@dataclass(frozen=True)
class ProfileHarnessReport:
    route_provider: str
    route_model: str
    route_reason: str
    sources: list[ProfileSource]
    profile_name: str = ""
    school: str = ""
    email: str = ""
    background_summary: str = ""
    proof_bank: list[str] = field(default_factory=list)
    target_lanes: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    claim_boundaries: list[str] = field(default_factory=list)
    missing_inputs: list[str] = field(default_factory=list)
    fetched_at: str | None = None
    source_warnings: list[str] = field(default_factory=list)
    identity_warnings: list[str] = field(default_factory=list)
    proof_provenance: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["sources"] = [asdict(source) for source in self.sources]
        return data


def _source_kind(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.hostname or ""
    path = parsed.path.lower()
    if "github.com" in host:
        return "github"
    if "linkedin.com" in host:
        return "linkedin"
    if path.endswith(".pdf") or any(part in path for part in ("/resume", "/cv")):
        return "resume"
    return "web"


def _normalize_url(value: str) -> str:
    value = value.strip().rstrip(".,;")
    if not value:
        return value
    if not value.startswith(("http://", "https://")):
        value = "https://" + value
    return value.rstrip("/")


def _url_key(value: str) -> str:
    return value.strip().rstrip("/").lower()


def extract_profile_urls(raw_profile: str) -> list[str]:
    """Return normalized profile/source URLs from free-form profile text."""
    urls: list[str] = []
    for match in URL_RE.finditer(raw_profile):
        if match.start() > 0 and raw_profile[match.start() - 1] == "@":
            continue
        urls.append(_normalize_url(match.group(0)))
    return list(dict.fromkeys(urls))


def _load_cached_source_report() -> dict | None:
    if not PROFILE_SOURCE_CACHE_PATH.exists():
        return None
    try:
        return json.loads(PROFILE_SOURCE_CACHE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _line_values(raw_profile: str, labels: tuple[str, ...]) -> list[str]:
    values: list[str] = []
    label_pattern = "|".join(re.escape(label) for label in labels)
    pattern = re.compile(rf"^\s*(?:[-*]\s*)?(?:{label_pattern})\s*:\s*(.+)$", re.I)
    for line in raw_profile.splitlines():
        match = pattern.match(line)
        if match and match.group(1).strip():
            values.append(match.group(1).strip())
    return values


def _bullets_after(raw_profile: str, heading: str) -> list[str]:
    lines = raw_profile.splitlines()
    results: list[str] = []
    in_section = False
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if in_section:
                continue
            continue
        if stripped.lower().rstrip(":") == heading.lower().rstrip(":"):
            in_section = True
            continue
        if in_section and not stripped.startswith(("-", "*")) and stripped.endswith(":"):
            break
        if in_section and stripped.startswith(("-", "*")):
            results.append(stripped.lstrip("-* ").strip())
    return results


def _has_substance(item: str) -> bool:
    if "check everything" in item.lower():
        return False
    if ":" in item and not item.split(":", 1)[1].strip():
        return False
    return bool(item.strip())


def _first_line_value(raw_profile: str, labels: tuple[str, ...]) -> str:
    values = _line_values(raw_profile, labels)
    return values[0] if values else ""


def _resolve_identity_field(
    label: str,
    user_value: str,
    fetched_value: str,
    model_value: str,
    warnings: list[str],
) -> str:
    """User-typed identity wins over fetched facts; fetched facts win over model output.

    A conflict between the user-typed value and a fetched fact is surfaced as a
    warning instead of being resolved silently.
    """
    if user_value:
        if fetched_value and fetched_value.strip().casefold() != user_value.strip().casefold():
            warnings.append(
                f'Fetched sources report {label} "{fetched_value}" but the profile says '
                f'"{user_value}"; keeping the profile value.'
            )
        return user_value
    return fetched_value or model_value


def build_profile_harness_report(raw_profile: str, structured_profile: dict | None = None) -> dict:
    enriched = enrich_profile_text(raw_profile) if structured_profile is None else raw_profile
    structured_profile = structured_profile or profile_agent.run(enriched)
    settings = load_settings()
    route = ModelRouter(settings).route(TaskType.PROFILE_INGEST)

    seed_urls = extract_profile_urls(raw_profile)
    source_report = _load_cached_source_report()
    fetched_by_url = {}
    fetched_proof_primary: list[str] = []
    fetched_proof_extra: list[str] = []
    source_warnings: list[str] = []
    source_facts: dict[str, str] = {}
    proof_origins: dict[str, dict] = {}
    fetched_at = None
    if source_report:
        fetched_at = source_report.get("fetched_at")
        source_facts = {
            str(key): str(value).strip()
            for key, value in source_report.get("profile_facts", {}).items()
            if str(value).strip()
        }
        for source in source_report.get("sources", []):
            fetched_by_url[_url_key(source.get("url", ""))] = source
            source_proofs = [
                str(item).strip()
                for item in source.get("proof_candidates", [])
                if str(item).strip()
            ]
            for proof in source_proofs:
                proof_origins.setdefault(proof, {
                    "source_url": str(source.get("url", "")),
                    "source_kind": str(source.get("kind", "")),
                    "origin": "discovered" if source.get("discovered_from") else "seed",
                    "fetched_at": fetched_at,
                })
            fetched_proof_primary.extend(source_proofs[:3])
            fetched_proof_extra.extend(source_proofs[3:])
            source_warnings.extend(
                str(item).strip()
                for item in source.get("warnings", [])
                if str(item).strip()
            )

    urls: list[str] = []
    seen_url_keys: set[str] = set()
    for url in [
        *(source.get("url", "") for source in (source_report or {}).get("sources", [])),
        *seed_urls,
    ]:
        key = _url_key(url)
        if not key or key in seen_url_keys:
            continue
        seen_url_keys.add(key)
        urls.append(url)
    sources = [
        ProfileSource(
            kind=_source_kind(url),
            value=url,
            status=fetched_by_url.get(_url_key(url), {}).get("status", "needs_fetch"),
            discovered_from=fetched_by_url.get(_url_key(url), {}).get("discovered_from", ""),
            origin=(
                "discovered"
                if fetched_by_url.get(_url_key(url), {}).get("discovered_from")
                else "seed"
            ),
        )
        for url in urls
    ]

    if not any(source.kind == "github" for source in sources):
        sources.append(ProfileSource(kind="github", value="not provided", status="missing"))
    if not any(source.kind == "linkedin" for source in sources):
        sources.append(ProfileSource(kind="linkedin", value="not provided", status="missing"))
    if not any(source.kind == "resume" for source in sources):
        sources.append(ProfileSource(kind="resume", value="not provided", status="optional"))

    proof_bank = [
        str(item).strip()
        for item in structured_profile.get("proof_points", [])
        if str(item).strip()
    ]
    if not proof_bank:
        proof_bank = [item for item in _bullets_after(raw_profile, "Background") if _has_substance(item)][:5]
    proof_bank = list(dict.fromkeys([*proof_bank, *fetched_proof_primary, *fetched_proof_extra]))

    target_lanes = [
        str(item).strip()
        for item in structured_profile.get("interests", [])
        if str(item).strip()
    ] or _bullets_after(raw_profile, "Target lanes")
    if not target_lanes:
        for value in _line_values(raw_profile, ("Interested in", "Interests")):
            target_lanes.extend(part.strip() for part in value.split(",") if part.strip())

    constraints = _bullets_after(raw_profile, "Constraints")
    constraints.extend(_line_values(raw_profile, ("Visa / sponsorship", "Location", "Timeframe")))
    constraints = list(dict.fromkeys([item for item in constraints if item]))

    claim_boundaries = _bullets_after(raw_profile, "Do not claim")
    if not claim_boundaries:
        claim_boundaries = [
            "Do not imply production experience unless the profile gives evidence.",
            "Label coursework as coursework.",
            "Treat unverified GitHub, LinkedIn, website, and resume claims as review items.",
        ]
    if any(source.status == "needs_fetch" for source in sources):
        claim_boundaries.insert(
            0,
            "Do not claim details from provided source links until the source fetch step has summarized them.",
        )

    missing_inputs = [
        source.kind
        for source in sources
        if source.status == "missing"
    ]
    if not constraints:
        missing_inputs.append("constraints")

    identity_warnings: list[str] = []
    profile_name = _resolve_identity_field(
        "name",
        _first_line_value(raw_profile, ("Name",)),
        source_facts.get("name", ""),
        str(structured_profile.get("name", "")).strip(),
        identity_warnings,
    )
    school = _resolve_identity_field(
        "school",
        _first_line_value(raw_profile, ("School",)),
        source_facts.get("school", ""),
        str(structured_profile.get("school", "")).strip(),
        identity_warnings,
    )
    email = _resolve_identity_field(
        "email",
        _first_line_value(raw_profile, ("Email",)),
        source_facts.get("email", ""),
        str(structured_profile.get("email", "")).strip(),
        identity_warnings,
    )

    proof_bank = proof_bank[:6]
    proof_provenance = [
        {
            "claim": proof,
            **proof_origins.get(proof, {
                "source_url": "",
                "source_kind": "",
                "origin": "user",
                "fetched_at": None,
            }),
        }
        for proof in proof_bank
    ]

    return ProfileHarnessReport(
        route_provider=route.provider,
        route_model=route.model,
        route_reason=route.reason,
        sources=sources,
        profile_name=profile_name,
        school=school,
        email=email,
        background_summary=source_facts.get("background_summary")
        or str(structured_profile.get("background_summary", "")).strip(),
        proof_bank=proof_bank,
        target_lanes=target_lanes[:6],
        constraints=constraints[:6],
        claim_boundaries=claim_boundaries[:6],
        missing_inputs=list(dict.fromkeys(missing_inputs)),
        fetched_at=fetched_at,
        source_warnings=source_warnings[:6],
        identity_warnings=identity_warnings[:6],
        proof_provenance=proof_provenance,
    ).to_dict()
