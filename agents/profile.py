"""
Profile Agent — builds the user's technical map from profile.txt and GitHub.
Output: structured profile dict used by every downstream agent.
"""
import hashlib
import json
import os
import re
from pathlib import Path

from upsearch import llm
from upsearch.json_utils import parse_model_json_object

# Task 031: the LLM extraction depends only on the raw profile text, which
# rarely changes, so the parsed model output is cached on disk keyed by the
# sha256 of that text. Source-evidence merging (_merge_source_evidence) is
# deterministic and re-reads the source-fetch cache on every call, so it runs
# on cache hits too — a hit skips only the llm.complete call, and fresh
# source evidence still lands without invalidating the cache.
CACHE_PATH = Path(".upsearch/profile/structured-cache.json")

SYSTEM = """You are a Profile Agent. Given a student's raw profile text, extract a structured technical map.

Respond with valid JSON only:
{
  "name": "...",
  "school": "...",
  "email": "...",
  "skills": ["Python", "ML", "systems"],
  "coursework": ["Operating Systems", "AI", "Convex Optimization"],
  "projects": [{"name": "...", "description": "...", "tech": [...]}],
  "interests": ["LLM inference", "ML systems"],
  "preferred_roles": ["ML engineer intern", "research intern"],
  "github_url": "...",
  "background_summary": "2-sentence honest summary of what this student has done and is capable of",
  "proof_points": ["specific credible proof point 1", "specific credible proof point 2"]
}

Be honest. Do not inflate experience. If something is coursework, label it as coursework."""

SKILL_KEYWORDS = {
    "C++": r"\bc\+\+\b",
    "Python": r"\bpython\b",
    "SQL": r"\bsql\b",
    "JavaScript/TypeScript": r"\b(?:javascript|typescript)\b",
    "PyTorch": r"\bpytorch\b",
    "TensorFlow": r"\btensorflow\b",
    "ROS2": r"\bros2?\b",
    "Docker": r"\bdocker\b",
    "AWS": r"\baws\b",
    "MinIO": r"\bminio\b",
    "LakeFS": r"\blakefs\b",
    "OpenCV": r"\bopencv\b",
    "ML evaluation": r"\b(?:evaluation|benchmarking|rubrics?)\b",
    "Data pipelines": r"\b(?:data|etl)\s+pipelines?\b",
}

INTEREST_KEYWORDS = {
    "AI infrastructure": r"\b(?:ai|ml)\s+infrastructure\b",
    "Inference systems": r"\b(?:inference|model serving|latency)\b",
    "Agentic AI": r"\b(?:agentic|multi-agent|ai agents?)\b",
    "Robotics": r"\b(?:robotics|ros2?|teleoperation)\b",
    "Data infrastructure": r"\b(?:data pipelines?|minio|lakefs|distributed systems)\b",
    "ML evaluation": r"\b(?:ml evaluation|model evaluation|benchmarking)\b",
}


def _line_value(raw_profile: str, label: str) -> str:
    prefix = f"{label.lower()}:"
    for line in raw_profile.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith(prefix):
            return stripped.split(":", 1)[1].strip()
    return ""


def _bullets_after(raw_profile: str, heading: str) -> list[str]:
    lines = raw_profile.splitlines()
    bullets: list[str] = []
    in_section = False
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.lower().rstrip(":") == heading.lower().rstrip(":"):
            in_section = True
            continue
        if in_section and not stripped.startswith(("-", "*")) and stripped.endswith(":"):
            break
        if in_section and stripped.startswith(("-", "*")):
            value = stripped.lstrip("-* ").strip()
            if value:
                bullets.append(value)
    return bullets


def _has_substance(item: str) -> bool:
    if "check everything" in item.lower():
        return False
    if ":" in item and not item.split(":", 1)[1].strip():
        return False
    return bool(item.strip())


def _source_profile() -> tuple[dict, list[str], list[dict]]:
    try:
        from upsearch.profile_source_fetch import load_cached_report  # noqa: PLC0415

        report = load_cached_report() or {}
    except Exception:
        return {}, [], []

    facts = {
        str(key): str(value).strip()
        for key, value in report.get("profile_facts", {}).items()
        if str(value).strip()
    }
    proof = [
        str(item).strip()
        for item in report.get("proof_candidates", [])
        if str(item).strip()
    ]
    projects: list[dict] = []
    for source in report.get("sources", []):
        if source.get("kind") != "github" or source.get("status") != "fetched":
            continue
        for item in source.get("proof_candidates", []):
            match = re.match(
                r"^([^:]{2,80}):\s+(.+?)\s+\(([^)]+)\)\s+(https://github\.com/\S+)$",
                str(item).strip(),
            )
            if not match:
                continue
            projects.append({
                "name": match.group(1).strip(),
                "description": match.group(2).strip(),
                "tech": [part.strip() for part in match.group(3).split(";") if part.strip()],
                "url": match.group(4),
            })
    return facts, proof, projects[:8]


def _keyword_matches(text: str, patterns: dict[str, str]) -> list[str]:
    return [label for label, pattern in patterns.items() if re.search(pattern, text, re.I)]


def fallback_profile(raw_profile: str) -> dict:
    background = _bullets_after(raw_profile, "Background")
    source_facts, source_proof, source_projects = _source_profile()
    evidence_text = "\n".join([
        raw_profile,
        source_facts.get("background_summary", ""),
        *source_proof,
    ])
    interests = []
    for item in background:
        if "interested in:" in item.lower():
            value = item.split(":", 1)[1].strip()
            if value:
                interests.extend(part.strip() for part in value.split(",") if part.strip())

    return {
        # User-typed identity lines outrank fetched source facts; fetched facts
        # only fill blanks the user did not provide.
        "name": _line_value(raw_profile, "Name") or source_facts.get("name") or "Student",
        "school": _line_value(raw_profile, "School") or source_facts.get("school") or "Unknown",
        "email": _line_value(raw_profile, "Email") or source_facts.get("email"),
        "skills": _keyword_matches(evidence_text, SKILL_KEYWORDS),
        "coursework": [
            item for item in background
            if "coursework" in item.lower() and item.split(":", 1)[-1].strip()
        ],
        "projects": source_projects,
        "interests": list(dict.fromkeys([*interests, *_keyword_matches(evidence_text, INTEREST_KEYWORDS)])),
        "preferred_roles": _bullets_after(raw_profile, "Looking for"),
        "github_url": source_facts.get("github_url", ""),
        "background_summary": source_facts.get("background_summary") or raw_profile.strip()[:300],
        "proof_points": list(dict.fromkeys([
            *(item for item in background if _has_substance(item)),
            *source_proof,
        ]))[:10],
    }


def _merge_source_evidence(result: dict, raw_profile: str) -> dict:
    fallback = fallback_profile(raw_profile)
    for key in ("name", "school", "email", "github_url", "background_summary"):
        value = fallback.get(key)
        if value and value not in {"Student", "Unknown"}:
            result[key] = value
    for key in ("skills", "coursework", "interests", "preferred_roles", "proof_points"):
        result[key] = list(dict.fromkeys([
            *(str(item).strip() for item in result.get(key, []) if str(item).strip()),
            *(str(item).strip() for item in fallback.get(key, []) if str(item).strip()),
        ]))
    existing_projects = [
        item for item in result.get("projects", [])
        if isinstance(item, dict) and item.get("name")
    ]
    seen_projects = {str(item["name"]).strip().lower() for item in existing_projects}
    for project in fallback.get("projects", []):
        key = str(project.get("name", "")).strip().lower()
        if key and key not in seen_projects:
            existing_projects.append(project)
            seen_projects.add(key)
    result["projects"] = existing_projects
    return result


def _cache_enabled() -> bool:
    """Read at call time so UPSEARCH_PROFILE_CACHE=0 disables without restart.

    UPSEARCH_PROFILE_CACHE: "0" disables, "1" force-enables. Unset means
    enabled — except under pytest, where the cache stays off so test runs
    that stub llm.complete can never read or overwrite the operator's real
    .upsearch/profile cache. Cache-specific tests opt back in with "1" after
    monkeypatching CACHE_PATH to a tmp path.
    """
    value = os.environ.get("UPSEARCH_PROFILE_CACHE")
    if value == "0":
        return False
    if value == "1":
        return True
    return "PYTEST_CURRENT_TEST" not in os.environ


def _profile_hash(raw_profile: str) -> str:
    return hashlib.sha256(raw_profile.encode("utf-8")).hexdigest()


def _load_cached_extraction(profile_hash: str) -> dict | None:
    """Return the cached LLM extraction for this exact profile text, or None.

    A missing, corrupt, or mismatched cache is a miss, never an error — the
    caller falls through to the normal LLM path and overwrites the file.
    """
    try:
        payload = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(payload, dict) or payload.get("hash") != profile_hash:
        return None
    profile = payload.get("profile")
    if not isinstance(profile, dict) or not profile:
        return None
    return profile


def _store_cached_extraction(profile_hash: str, profile: dict) -> None:
    """Persist the parsed LLM output. Cache failures never break a run."""
    try:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CACHE_PATH.write_text(
            json.dumps({"hash": profile_hash, "profile": profile}, indent=2) + "\n",
            encoding="utf-8",
        )
    except (OSError, TypeError, ValueError):
        pass


def run(raw_profile: str) -> dict:
    if not raw_profile.strip():
        return {
            "name": "Student",
            "school": "Unknown",
            "skills": [],
            "interests": [],
            "background_summary": "CS student seeking technical opportunities.",
            "proof_points": [],
        }
    cache_enabled = _cache_enabled()
    profile_hash = _profile_hash(raw_profile)
    if cache_enabled:
        cached = _load_cached_extraction(profile_hash)
        if cached is not None:
            return _merge_source_evidence(cached, raw_profile)
    try:
        text = llm.complete(system=SYSTEM, user=f"Profile:\n{raw_profile}", max_tokens=4096)
    except Exception:
        # Degraded fallback is never cached: it must not mask later recovery.
        return fallback_profile(raw_profile)
    result = parse_model_json_object(text)
    if not result:
        return fallback_profile(raw_profile)
    if cache_enabled:
        # Cache the pre-merge extraction so hits still merge live source
        # evidence; store before merging because the merge mutates result.
        _store_cached_extraction(profile_hash, result)
    return _merge_source_evidence(result, raw_profile)
