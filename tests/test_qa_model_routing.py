from dataclasses import replace
from unittest.mock import MagicMock

from agents import qa
from upsearch.config import Settings
from upsearch.qa_execution import qa_verify


def settings(**overrides) -> Settings:
    base = Settings(
        tracking_dir=None,
        wandb_project=None,
        wandb_entity=None,
        wandb_mode="disabled",
        deepseek_model="deepseek-chat",
        strong_model_provider="anthropic",
        strong_model="claude-test",
        coreweave_namespace=None,
        coreweave_cluster=None,
    )
    return replace(base, **overrides)


def minimal_packet(overrides: dict | None = None) -> dict:
    p = {
        "company": {"identity_status": "verified"},
        "problems": [{"source_urls": ["https://example.com/problem"]}],
        "people": [{"name": "A Person", "source_url": "https://example.com/person"}],
        "technical_note": "A source-backed technical note.",
        "adjacent_proof": "A documented project.",
        "outreach_drafts": {"email": "Hello\n\nA short specific message."},
    }
    if overrides:
        p.update(overrides)
    return p


def _fake_success_result() -> dict:
    return {
        "passed": True,
        "score": 8,
        "flags": [],
        "recommendations": [],
        "claim_check": "honest",
        "source_coverage": "good",
    }


def test_qa_reports_strong_model_route(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(qa, "load_settings", lambda: settings())
    monkeypatch.setattr(qa, "qa_verify", lambda route, **kwargs: (_fake_success_result(), False))

    result = qa.run(minimal_packet(), {"proof_points": ["documented"]})

    assert result["model_route"]["provider"] == "anthropic"
    assert result["model_route"]["model"] == "claude-test"
    assert result["model_route"]["degraded_mode"] is False


def test_qa_marks_degraded_mode_when_route_is_unconfigured(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(qa, "load_settings", lambda: settings())

    result = qa.run(minimal_packet(), {"proof_points": ["documented"]})

    assert result["passed"] is False
    assert result["model_route"]["configured"] is False
    assert result["model_route"]["degraded_mode"] is True
    assert any("not configured" in flag for flag in result["flags"])


def test_qa_result_dict_structure(monkeypatch):
    """qa.run() returns expected keys and merges deterministic+model results."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(qa, "load_settings", lambda: settings())
    monkeypatch.setattr(qa, "qa_verify", lambda route, **kwargs: ({
        "passed": True,
        "score": 7,
        "flags": ["a minor flag"],
        "recommendations": ["consider tightening"],
        "claim_check": "fair",
        "source_coverage": "decent",
    }, False))

    packet = minimal_packet({"people": [
        {"name": "A Person", "verification_status": "verified",
         "source_url": "https://example.com/person", "relevance_score": 8},
    ]})
    result = qa.run(packet, {"proof_points": ["documented"]})

    assert result["passed"] is True
    # Score 7 - 0 flags = 7 (no deterministic flags triggered)
    assert result["score"] == 7
    assert result["claim_check"] == "fair"
    assert "model_route" in result
    assert "rule_checks" in result


def test_qa_execution_failure_produces_degraded_result(monkeypatch):
    """When qa_verify raises, exception is caught, degraded result is returned."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(qa, "load_settings", lambda: settings())
    monkeypatch.setattr(qa, "qa_verify", lambda route, **kwargs: (
        {
            "passed": False,
            "score": 4,
            "flags": ["QA model degraded: execution failed"],
            "recommendations": ["Configure a verification model or review this packet manually."],
            "claim_check": "Not evaluated by a configured verification model.",
            "source_coverage": "Deterministic source checks only.",
        },
        True,
    ))

    result = qa.run(minimal_packet(), {"proof_points": ["documented"]})

    assert result["model_route"]["degraded_mode"] is True
    assert any("degraded" in f.lower() for f in result["flags"])


def test_qa_fallback_route_marks_degraded(monkeypatch):
    """When strong_model is 'not-configured', the fallback route is degraded."""
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(qa, "load_settings", lambda: settings(strong_model="not-configured"))

    result = qa.run(minimal_packet(), {"proof_points": ["documented"]})

    assert result["model_route"]["degraded_mode"] is True
    assert result["model_route"]["is_fallback"] is True
    assert any("fallback" in f.lower() or "degraded" in f.lower()
               for f in result["flags"])


def test_qa_gives_reasoning_models_token_headroom(monkeypatch):
    """Reasoning models spend output tokens thinking; 512 starved deepseek-r1
    into empty output and a parse-error default instead of a real verdict."""
    captured: dict = {}

    def capture_verify(route, **kwargs):
        captured.update(kwargs)
        return _fake_success_result(), False

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(qa, "load_settings", lambda: settings())
    monkeypatch.setattr(qa, "qa_verify", capture_verify)

    qa.run(minimal_packet(), {"proof_points": []})

    assert captured["max_tokens"] >= 2048


def test_qa_offline_benchmark_fails_closed_on_unsupported_claim(monkeypatch):
    """An unsupported claim results in score below threshold."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(qa, "load_settings", lambda: settings())

    def _unsupported_verify(_route, **_kwargs):
        return ({
            "passed": False,
            "score": 3,
            "flags": ["Claim 'I built their infra' has no supporting evidence"],
            "recommendations": ["Remove unsupported claim or add source"],
            "claim_check": "Claim appears fabricated",
            "source_coverage": "No source backs the strong claim",
        }, False)

    monkeypatch.setattr(qa, "qa_verify", _unsupported_verify)

    packet = minimal_packet({
        "people": [{"name": "A Person", "verification_status": "verified",
                    "source_url": "https://example.com/person", "relevance_score": 8}],
        "outreach_drafts": {"email": "Hi\n\nI built their entire ML pipeline from scratch."},
    })

    result = qa.run(packet, {"proof_points": []})

    assert result["score"] < 6
    assert not result["passed"]
