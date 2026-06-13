"""Offline benchmark — runs fixed packets through qa.run() with fake model responses.

Every entry in ``qa_benchmark.json`` exercises the deterministic rule layer AND a
simulated model-verification call. The expected outcomes are checked without
network or credentials.

Test structure
--------------
Each benchmark entry declares an ``expected`` block. The test runner:

1. Monkeypatches ``qa_execution.qa_verify`` to return a canned result that
   matches the entry's *expected* outcome.
2. Runs ``qa.run(packet, profile)``.
3. Asserts ``score_min ≤ score ≤ score_max`` and ``passed`` matches.
4. Asserts that ``flags`` contain at least one ``allowed_flags`` pattern.
5. Asserts that no ``forbidden_flags_patterns`` appear in ``flags``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agents import qa
from upsearch.config import Settings

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"

# ── Helpers ──────────────────────────────────────────────────────────────────


def _canned_result(entry: dict) -> dict:
    """Build a fake qa_verify result that matches the entry's expected outcome."""
    exp = entry["expected"]
    passed = exp["passed"]
    # Middle of the expected score range, preferring the pass/fail boundary side
    lo, hi = exp["score_min"], exp["score_max"]
    score = hi if passed else lo + 1
    return {
        "passed": passed,
        "score": score,
        "flags": [],
        "recommendations": ["Automated benchmark — review flags."],
        "claim_check": "Benchmark fixture.",
        "source_coverage": "Fixture coverage.",
    }


# ── Tests ────────────────────────────────────────────────────────────────────


def _load_entries() -> list[dict]:
    path = FIXTURES / "qa_benchmark.json"
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data["entries"]


@pytest.mark.parametrize(
    "entry",
    _load_entries(),
    ids=lambda e: e["id"],
)
def test_benchmark_entry(entry: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    # Wire up a fake route
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(qa, "load_settings", lambda: Settings(
        tracking_dir=None,
        wandb_project=None,
        wandb_entity=None,
        wandb_mode="disabled",
        deepseek_model="deepseek-chat",
        strong_model_provider="anthropic",
        strong_model="claude-test",
        coreweave_namespace=None,
        coreweave_cluster=None,
    ))
    monkeypatch.setattr(
        qa, "qa_verify",
        lambda route, **kwargs: (_canned_result(entry), False),
    )

    result = qa.run(entry["packet"], entry["profile"])
    exp = entry["expected"]

    # ── Score range ──────────────────────────────────────────────────────
    assert exp["score_min"] <= result["score"] <= exp["score_max"], (
        f"Score {result['score']} outside [{exp['score_min']}, {exp['score_max']}] "
        f"for '{entry['id']}'"
    )

    # ── Pass/fail ────────────────────────────────────────────────────────
    assert result["passed"] is exp["passed"], (
        f"Expected passed={exp['passed']} for '{entry['id']}'"
    )

    # ── Required flag patterns present ───────────────────────────────────
    if exp.get("allowed_flags"):
        all_flag_text = " ".join(result["flags"]).lower()
        assert any(
            pattern.lower() in all_flag_text for pattern in exp["allowed_flags"]
        ), (
            f"None of allowed_flags={exp['allowed_flags']} found in flags for "
            f"'{entry['id']}': {result['flags']}"
        )

    # ── Forbidden flag patterns absent ───────────────────────────────────
    if exp.get("forbidden_flags_patterns"):
        all_flag_text = " ".join(result["flags"]).lower()
        for pattern in exp["forbidden_flags_patterns"]:
            assert pattern.lower() not in all_flag_text, (
                f"Flag matches forbidden pattern '{pattern}' in '{entry['id']}': "
                f"{result['flags']}"
            )
