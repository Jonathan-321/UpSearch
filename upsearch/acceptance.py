"""Golden packet acceptance — repeatable offline verification of the full packet contract.

Usage
-----
    from upsearch.acceptance import run_golden_acceptance

    results = run_golden_acceptance()
    # results -> {"baseten": {...}, "modal": {...}}
    all_ok = all(r["status"] == "passed" for r in results.values())

Each entry is compared against the 8 criteria described in Task 006.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .packet_checkup import evaluate_packet


GOLDEN_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "golden"


@dataclass
class AcceptanceCriterion:
    name: str
    passed: bool
    detail: str | None = None
    score: float | None = None


@dataclass
class GoldenAcceptanceResult:
    company_name: str
    all_passed: bool
    criteria: list[AcceptanceCriterion] = field(default_factory=list)
    checkup: dict[str, Any] | None = None


# ── Criteria checkers ────────────────────────────────────────────────────────


def _check_verified_identity(fixture: dict) -> AcceptanceCriterion:
    identity = fixture.get("company", {}).get("identity_status", "")
    passed = identity == "verified"
    return AcceptanceCriterion(
        name="verified_company_identity",
        passed=passed,
        detail=f"identity_status={identity}, expected verified",
        score=10.0 if passed else 0.0,
    )


def _check_source_backed_fit(fixture: dict) -> AcceptanceCriterion:
    """Problem sources are stored — at least one problem with at least one URL."""
    problems = fixture.get("problems", [])
    sourced = [p for p in problems if p.get("source_urls")]
    passed = len(sourced) >= 1
    return AcceptanceCriterion(
        name="source_backed_problem_fit",
        passed=passed,
        detail=f"{len(sourced)}/{len(problems)} problems have source URLs",
        score=10.0 if passed else 0.0,
    )


def _check_technical_problem_with_evidence(fixture: dict) -> AcceptanceCriterion:
    """At least one specific technical problem with stored evidence."""
    problems = fixture.get("problems", [])
    specific = [
        p for p in problems
        if p.get("title") and p.get("description") and p.get("source_urls")
    ]
    passed = len(specific) >= 1
    return AcceptanceCriterion(
        name="specific_technical_problem_with_evidence",
        passed=passed,
        detail=f"{len(specific)} specific problems with title, description, and source URLs",
        score=10.0 if passed else 0.0,
    )


def _check_verified_person(fixture: dict) -> AcceptanceCriterion:
    """At least one evidence-verified relevant person."""
    people = fixture.get("people", [])
    verified = [
        p for p in people
        if p.get("verification_status") == "verified" and p.get("source_url")
    ]
    passed = len(verified) >= 1
    names = [p["name"] for p in verified]
    return AcceptanceCriterion(
        name="verified_relevant_person",
        passed=passed,
        detail=f"{len(verified)} verified person(s): {', '.join(names)}",
        score=10.0 if passed else 0.0,
    )


def _check_technical_note_quality(fixture: dict) -> AcceptanceCriterion:
    """Technical note has concrete contribution and evaluation criteria."""
    note = fixture.get("packet", {}).get("technical_note", "")
    has_contribution = "Build Plan" in note or "build plan" in note.lower()
    has_criteria = "Success Criteria" in note or "success criteria" in note.lower()
    words = len(note.split())
    passed = bool(note) and has_contribution and has_criteria and words >= 80
    return AcceptanceCriterion(
        name="technical_note_quality",
        passed=passed,
        detail=f"{words} words, contribution={'yes' if has_contribution else 'no'}, criteria={'yes' if has_criteria else 'no'}",
        score=10.0 if passed else 0.0,
    )


def _check_adjacent_proof(fixture: dict) -> AcceptanceCriterion:
    """Honest adjacent-proof mapping — a real-looking URL."""
    proof = fixture.get("packet", {}).get("adjacent_proof", "")
    passed = bool(proof) and proof.startswith("http")
    return AcceptanceCriterion(
        name="adjacent_proof_mapping",
        passed=passed,
        detail=f"adjacent_proof={'url present' if passed else 'missing or invalid'}",
        score=10.0 if passed else 0.0,
    )


def _check_outreach_limits(fixture: dict) -> AcceptanceCriterion:
    """Outreach within channel limits — no draft over 200 words for email body."""
    drafts = fixture.get("packet", {}).get("outreach_drafts", {})
    email_body = drafts.get("email", "")
    # Body is after the greeting line
    lines = email_body.split("\n\n", 1)
    body = lines[1] if len(lines) > 1 else email_body
    word_count = len(body.split())
    passed = word_count <= 200
    return AcceptanceCriterion(
        name="outreach_within_limits",
        passed=passed,
        detail=f"email body={word_count} words, limit=200",
        score=10.0 if passed else 0.0,
    )


def _check_qa_and_trace(fixture: dict) -> AcceptanceCriterion:
    """QA score ≥6, flags empty, exact approval requirement."""
    packet = fixture.get("packet", {})
    qa_score = packet.get("qa_score", 0) or 0
    qa_flags = packet.get("qa_flags", [])
    passed = qa_score >= 6 and len(qa_flags) == 0
    return AcceptanceCriterion(
        name="qa_and_approval_gate",
        passed=passed,
        detail=f"qa_score={qa_score}/10, flags={len(qa_flags)}",
        score=min(10.0, qa_score) if passed else 0.0,
    )


ALL_CRITERIA = [
    _check_verified_identity,
    _check_source_backed_fit,
    _check_technical_problem_with_evidence,
    _check_verified_person,
    _check_technical_note_quality,
    _check_adjacent_proof,
    _check_outreach_limits,
    _check_qa_and_trace,
]


def _load_fixture(company_name: str) -> dict[str, Any]:
    path = GOLDEN_DIR / f"{company_name}.json"
    if not path.exists():
        raise FileNotFoundError(f"Golden fixture not found: {path}")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def run_golden_acceptance(
    fixture_paths: list[Path] | None = None,
) -> dict[str, GoldenAcceptanceResult]:
    """Run all golden fixtures through the acceptance criteria.

    Returns a dict keyed by company name.
    """
    if fixture_paths:
        paths = fixture_paths
    else:
        paths = sorted(GOLDEN_DIR.glob("*.json"))

    results: dict[str, GoldenAcceptanceResult] = {}
    for path in paths:
        fixture = json.loads(path.read_text(encoding="utf-8"))
        company = fixture.get("company_name", path.stem)

        criteria = [check(fixture) for check in ALL_CRITERIA]
        all_passed = all(c.passed for c in criteria)

        checkup = evaluate_packet(
            company_name=company,
            packet=fixture.get("packet"),
            problems=fixture.get("problems", []),
            people=fixture.get("people", []),
        )

        results[company] = GoldenAcceptanceResult(
            company_name=company,
            all_passed=all_passed,
            criteria=criteria,
            checkup=checkup,
        )

    return results


def report(results: dict[str, GoldenAcceptanceResult]) -> str:
    """Render a human-readable acceptance report."""
    lines = ["# Golden Packet Acceptance Report", ""]
    for company, result in results.items():
        status = "✅ PASS" if result.all_passed else "❌ FAIL"
        checkup_status = result.checkup.get("status", "?") if result.checkup else "?"
        score = result.checkup.get("overall_score", "?") if result.checkup else "?"
        lines.append(f"## {company} — {status} (checkup: {checkup_status}, score: {score})")
        lines.append("")
        for c in result.criteria:
            passed = "✅" if c.passed else "❌"
            detail = f" — {c.detail}" if c.detail else ""
            lines.append(f"- {passed} {c.name}{detail}")
        lines.append("")
    return "\n".join(lines)
