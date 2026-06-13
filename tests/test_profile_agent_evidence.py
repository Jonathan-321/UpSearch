import json

from agents import profile
from upsearch import profile_source_fetch


def source_report() -> dict:
    return {
        "profile_facts": {
            "name": "Jonathan Muhire",
            "school": "Oklahoma Christian University",
            "email": "student@example.edu",
            "github_url": "https://github.com/student",
            "background_summary": "Software engineer focused on ML systems.",
        },
        "proof_candidates": [
            "Built a data pipeline using Python, MinIO, and LakeFS. Source: https://example.dev/resume.pdf",
            "Created model evaluation benchmarks for inference systems. Source: https://example.dev/resume.pdf",
        ],
        "sources": [
            {
                "kind": "github",
                "status": "fetched",
                "proof_candidates": [
                    "agentic: Multi-agent orchestration framework (Python; topics: ai-agents) https://github.com/student/agentic"
                ],
            }
        ],
    }


def test_fallback_profile_uses_source_backed_evidence(monkeypatch) -> None:
    monkeypatch.setattr(profile_source_fetch, "load_cached_report", source_report)

    result = profile.fallback_profile("Website: https://example.dev")

    assert result["name"] == "Jonathan Muhire"
    assert result["school"] == "Oklahoma Christian University"
    assert "Python" in result["skills"]
    assert "Data infrastructure" in result["interests"]
    assert result["projects"][0]["name"] == "agentic"
    assert result["proof_points"]


def test_model_cannot_override_verified_identity(monkeypatch) -> None:
    monkeypatch.setattr(profile_source_fetch, "load_cached_report", source_report)
    monkeypatch.setattr(
        profile.llm,
        "complete",
        lambda **kwargs: json.dumps({
            "name": "Wrong Name",
            "school": "Yale University",
            "skills": ["Python"],
            "coursework": [],
            "projects": [],
            "interests": [],
            "preferred_roles": [],
            "proof_points": [],
        }),
    )

    result = profile.run("Website: https://example.dev")

    assert result["name"] == "Jonathan Muhire"
    assert result["school"] == "Oklahoma Christian University"
    assert result["projects"][0]["name"] == "agentic"
