"""Golden packet acceptance tests.

Every test loads a fixture from ``tests/fixtures/golden/`` and runs the full
set of acceptance criteria. No network or credentials are required.

The 8 criteria verified per fixture:
1. Verified company identity (identity_status = "verified")
2. Source-backed fit (at least one problem with source URLs)
3. Specific technical problem with stored evidence
4. At least one evidence-verified relevant person
5. Technical note with concrete contribution and evaluation criteria
6. Honest adjacent-proof mapping (valid URL)
7. Outreach within channel limits (email body ≤ 200 words)
8. QA score ≥ 6 and no QA flags
"""

from __future__ import annotations

from pathlib import Path

import pytest

from upsearch.acceptance import (
    ALL_CRITERIA,
    GoldenAcceptanceResult,
    _check_adjacent_proof,
    _check_outreach_limits,
    _check_qa_and_trace,
    _check_source_backed_fit,
    _check_technical_note_quality,
    _check_technical_problem_with_evidence,
    _check_verified_identity,
    _check_verified_person,
    run_golden_acceptance,
)

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures" / "golden"


def _discover_fixtures() -> list[Path]:
    return sorted(FIXTURES.glob("*.json"))


@pytest.mark.parametrize("path", _discover_fixtures(), ids=lambda p: p.stem)
def test_golden_packet_all_criteria(path: Path) -> None:
    """All 8 criteria pass for every golden fixture."""
    import json

    fixture = json.loads(path.read_text(encoding="utf-8"))
    errors = []
    for check_fn in ALL_CRITERIA:
        criterion = check_fn(fixture)
        if not criterion.passed:
            errors.append(f"  ❌ {criterion.name}: {criterion.detail}")
    assert not errors, (
        f"Golden packet '{path.stem}' failed criteria:\n" + "\n".join(errors)
    )


@pytest.mark.parametrize("path", _discover_fixtures(), ids=lambda p: p.stem)
def test_golden_packet_acceptance_harness(path: Path) -> None:
    """run_golden_acceptance returns all_passed=True for every fixture."""
    import json
    results = run_golden_acceptance(fixture_paths=[path])
    fixture = json.loads(path.read_text(encoding="utf-8"))
    company = fixture.get("company_name", path.stem)
    result = results.get(company)
    assert result is not None, f"No result for {path.stem}"
    assert result.all_passed, (
        f"Acceptance harness failed for '{path.stem}': "
        + ", ".join(f"{c.name}:{c.detail}" for c in result.criteria if not c.passed)
    )


# ── Individual criterion unit tests ──────────────────────────────────────────


class TestVerifiedIdentity:
    def test_passes_verified(self) -> None:
        c = _check_verified_identity({"company": {"identity_status": "verified"}})
        assert c.passed

    def test_fails_unverified(self) -> None:
        c = _check_verified_identity({"company": {"identity_status": "unverified"}})
        assert not c.passed

    def test_fails_missing(self) -> None:
        c = _check_verified_identity({"company": {}})
        assert not c.passed


class TestSourceBackedFit:
    def test_passes_with_sourced_problems(self) -> None:
        c = _check_source_backed_fit({
            "problems": [
                {"source_urls": ["https://example.com/p1"]},
                {"source_urls": []},
            ],
        })
        assert c.passed

    def test_fails_with_no_sources(self) -> None:
        c = _check_source_backed_fit({
            "problems": [{"source_urls": []}],
        })
        assert not c.passed

    def test_fails_empty_problems(self) -> None:
        c = _check_source_backed_fit({"problems": []})
        assert not c.passed


class TestTechnicalNoteQuality:
    def test_passes_with_build_plan_and_criteria(self) -> None:
        fixture = {
            "packet": {
                "technical_note": (
                    "## Build Plan\n"
                    "First, we implement a warm-pool strategy that keeps frequently-used "
                    "model shards in GPU memory across invocations. This reduces cold-start "
                    "latency by avoiding repeated weight loading from cloud storage. "
                    "Then we add priority-based weight ordering to load critical layers first "
                    "while deferring non-essential parameters. Finally, we evaluate model "
                    "quantization (FP16/INT8) to reduce the memory footprint for cold-start paths.\n\n"
                    "## Success Criteria\n"
                    "Cold-start latency under 5 seconds for models up to 7B parameters. "
                    "No regression in steady-state inference throughput. Memory overhead from "
                    "warm pools stays under 20% of available GPU memory."
                ),
            },
        }
        c = _check_technical_note_quality(fixture)
        assert c.passed

    def test_fails_no_build_plan(self) -> None:
        fixture = {
            "packet": {
                "technical_note": "## Some Note\n\nNothing here.",
            },
        }
        c = _check_technical_note_quality(fixture)
        assert not c.passed

    def test_fails_no_success_criteria(self) -> None:
        fixture = {
            "packet": {
                "technical_note": "## Build Plan\n\nDo the thing.",
            },
        }
        c = _check_technical_note_quality(fixture)
        assert not c.passed

    def test_fails_empty_note(self) -> None:
        c = _check_technical_note_quality({"packet": {"technical_note": ""}})
        assert not c.passed


class TestOutreachLimits:
    def test_passes_short_body(self) -> None:
        fixture = {"packet": {"outreach_drafts": {"email": "Hi\n\nShort body."}}}
        c = _check_outreach_limits(fixture)
        assert c.passed

    def test_fails_over_200(self) -> None:
        body = "Hi\n\n" + "word " * 210
        fixture = {"packet": {"outreach_drafts": {"email": body}}}
        c = _check_outreach_limits(fixture)
        assert not c.passed

    def test_passes_exactly_200(self) -> None:
        body = "Hi\n\n" + "word " * 199 + "end"
        fixture = {"packet": {"outreach_drafts": {"email": body}}}
        c = _check_outreach_limits(fixture)
        assert c.passed


class TestQaAndApprovalGate:
    def test_passes_good_score(self) -> None:
        c = _check_qa_and_trace({"packet": {"qa_score": 8, "qa_flags": []}})
        assert c.passed

    def test_fails_low_score(self) -> None:
        c = _check_qa_and_trace({"packet": {"qa_score": 5, "qa_flags": []}})
        assert not c.passed

    def test_fails_with_flags(self) -> None:
        c = _check_qa_and_trace({"packet": {"qa_score": 8, "qa_flags": ["over 200"]}})
        assert not c.passed


class TestAdjacentProof:
    def test_passes_with_url(self) -> None:
        c = _check_adjacent_proof({"packet": {"adjacent_proof": "https://github.com/example/project"}})
        assert c.passed

    def test_fails_empty(self) -> None:
        c = _check_adjacent_proof({"packet": {"adjacent_proof": ""}})
        assert not c.passed

    def test_fails_non_url(self) -> None:
        c = _check_adjacent_proof({"packet": {"adjacent_proof": "a sentence"}})
        assert not c.passed
