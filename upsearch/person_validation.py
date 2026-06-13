"""Deterministic person-name validation.

The people pipeline extracts candidate names from model output, company team
and blog pages, and GitHub orgs. Marketing-site markup makes nav sections,
feature cards, and blog titles look like team cards, which is how strings
like "Pricing", "Use Cases", or an article headline end up scored and shown
as people. Nothing downstream can verify its way out of that: evidence
checks only prove a string appears on a company page, which nav labels do by
definition.

This module is the gate: a candidate that does not look like a human name
never becomes a person record. It is deliberately strict — a junk card shown
to the reviewer costs trust, while a missed candidate is recoverable from
other sources.
"""

from __future__ import annotations

import re

# Tokens that appear in website navigation, marketing sections, and group
# labels. A candidate containing any of these (case-insensitive) is not a
# person. Token-level matching keeps this robust to combinations ("Use
# Cases", "Model Library", "Fireworks GitHub Contributors").
NAV_VOCAB = {
    "about", "api", "blog", "careers", "case", "cases", "changelog", "cloud",
    "community", "company", "contact", "contributors", "customers", "demo",
    "developer", "developers", "docs", "documentation", "engineering",
    "engineers", "enterprise", "events", "faq", "features", "github",
    "guides", "hiring", "infrastructure", "integrations", "jobs",
    "leadership", "learn", "legal", "library", "login", "members", "model",
    "models", "news", "overview", "papers", "partners", "platform",
    "pricing", "privacy", "product", "products", "register", "research",
    "resources", "sdk", "security", "serverless", "signin", "signup",
    "solutions", "staff", "started", "status", "studies", "support", "team",
    "teams", "terms", "tutorials", "use",
}

# Lowercase particles that legitimately appear inside human names.
_NAME_PARTICLES = {"af", "al", "bin", "da", "de", "del", "der", "di", "el", "la", "le", "ten", "van", "von"}

def _valid_name_token(token: str) -> bool:
    """Unicode-aware: uppercase letter start, then letters/apostrophes/dots/hyphens."""
    if not token or not (token[0].isalpha() and token[0].isupper()):
        return False
    return all(ch.isalpha() or ch in "'’.-" for ch in token[1:])


def person_name_rejection(name: str) -> str | None:
    """Return why ``name`` is not a human name, or None when it looks like one."""
    cleaned = " ".join(str(name or "").split())
    if not cleaned:
        return "empty"
    if len(cleaned) > 40:
        return "too_long"
    if re.search(r"\d", cleaned):
        return "contains_digits"

    tokens = cleaned.split()
    if len(tokens) < 2:
        return "single_token"
    if len(tokens) > 4:
        return "too_many_tokens"

    for token in tokens:
        bare = token.strip("'’.-").lower()
        if bare in NAV_VOCAB:
            return f"nav_vocabulary:{bare}"

    for index, token in enumerate(tokens):
        if index > 0 and token.lower() in _NAME_PARTICLES:
            continue
        bare = token.strip("'’.-")
        if len(bare) > 1 and bare.isupper():
            return f"acronym_token:{token}"
        if not _valid_name_token(token):
            return f"malformed_token:{token}"

    return None


def is_person_name(name: str) -> bool:
    return person_name_rejection(name) is None


def filter_people(people: list[dict]) -> tuple[list[dict], list[dict]]:
    """Split candidate dicts into (people, rejected-non-people)."""
    kept: list[dict] = []
    rejected: list[dict] = []
    for person in people:
        if isinstance(person, dict) and is_person_name(str(person.get("name", ""))):
            kept.append(person)
        else:
            rejected.append(person if isinstance(person, dict) else {"name": str(person)})
    return kept, rejected
