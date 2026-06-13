from dataclasses import dataclass

import run_scheduler as scheduler
from upsearch.orchestrator_service import RunResult


def _blocked_result(company: str, reason: str) -> RunResult:
    return RunResult(
        run_id="test-blocked",
        company_name=company,
        lane="robotics_ai",
        status="blocked",
        qa_result={"passed": False, "score": 0, "flags": [f"identity_blocked: {reason}"]},
    )


def test_pipeline_stops_before_problem_generation_for_unverified_company(monkeypatch):
    """Scheduler returns blocked when orchestrator blocks on unverified identity."""
    async def fake_pipeline(**kwargs):
        return _blocked_result("MARS", "Ambiguous company identity.")

    monkeypatch.setattr(scheduler.orchestrator_service, "run_pipeline", fake_pipeline)

    result = scheduler.execute_run_pipeline(
        {
            "company_name": "MARS",
            "lane": "robotics_ai",
            "source_urls": ["https://mars.com"],
        }
    )

    assert result.status == "blocked"
    assert "identity_blocked" in (result.error or "")


@dataclass
class Candidate:
    name: str = "AcmeFlow"
    website: str = "https://acmeflow.ai"
    official_domain: str = "acmeflow.ai"
    identity_status: str = "verified"
    identity_confidence: float = 0.9
    identity_reason: str = "Evidence agrees."
    source_urls: tuple[str, ...] = ("https://acmeflow.ai",)
    evidence: tuple[str, ...] = ("Show HN: AcmeFlow",)
    fit_guess: float = 0.8


def test_discovery_persists_verified_identity_before_enqueuing(monkeypatch):
    writes: list[tuple[str, dict]] = []
    monkeypatch.setattr(scheduler, "discover", lambda *_args, **_kwargs: [Candidate()])
    monkeypatch.setattr(scheduler.db, "get_company", lambda _name: None)
    monkeypatch.setattr(scheduler, "check_company_has_pending_job", lambda _name: False)

    def upsert(name, **kwargs):
        writes.append((name, kwargs))
        return 11

    enqueued: list[tuple[str, dict]] = []
    monkeypatch.setattr(scheduler.db, "upsert_company", upsert)
    monkeypatch.setattr(scheduler.db, "insert_source", lambda *_args, **_kwargs: 21)
    monkeypatch.setattr(
        scheduler.db,
        "enqueue_job",
        lambda job_type, **kwargs: enqueued.append((job_type, kwargs)) or 31,
    )

    result = scheduler.execute_discover_companies({"lane": "ai_infra", "max_candidates": 1})

    assert result.status == "processed"
    assert writes[0][1]["identity_status"] == "verified"
    assert writes[0][1]["official_domain"] == "acmeflow.ai"
    assert enqueued[0][0] == "run_pipeline"
