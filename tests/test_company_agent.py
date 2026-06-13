from agents import company
from upsearch.company_identity import CompanyIdentity


def identity(
    *,
    status: str,
    website: str = "",
    official_domain: str = "",
    reason: str = "not verified",
) -> CompanyIdentity:
    return CompanyIdentity(
        query_name="Modal",
        canonical_name="Modal",
        website=website,
        official_domain=official_domain,
        lane="ai_infra",
        status=status,
        confidence=1.0 if status == "verified" else 0.4,
        reason=reason,
        evidence_urls=[website] if website else [],
        evidence_titles=[],
    )


def test_company_agent_verifies_model_website_candidate(monkeypatch) -> None:
    calls: list[list[str]] = []

    def resolve(**kwargs):
        calls.append(kwargs["evidence_urls"])
        if "https://modal.com" in kwargs["evidence_urls"]:
            return identity(
                status="verified",
                website="https://modal.com",
                official_domain="modal.com",
                reason="Dedicated domain, company name, and technical lane agree.",
            )
        return identity(status="rejected")

    monkeypatch.setattr(company.hackernews, "search", lambda *args, **kwargs: [])
    monkeypatch.setattr(company, "resolve_company_identity_with_fallback", resolve)
    monkeypatch.setattr(company, "resolve_company_identity", resolve)
    monkeypatch.setattr(company, "fetch_company_signal", lambda domain: {"error": "unused"})
    monkeypatch.setattr(
        company.llm,
        "complete",
        lambda **kwargs: (
            '{"name":"Modal","website":"modal.com","fit_score":9,'
            '"why":"Strong infrastructure fit","assumptions":[]}'
        ),
    )

    result = company.run("Modal", "ai_infra", {"interests": [], "skills": []})

    assert len(calls) == 2
    assert result["result"]["identity_status"] == "verified"
    assert result["result"]["website"] == "https://modal.com"
    assert result["result"]["official_domain"] == "modal.com"
    assert "https://modal.com" in result["source_urls"]


def test_website_candidate_rejects_non_http_values() -> None:
    assert company._website_candidate("javascript:alert(1)") == ""
    assert company._website_candidate("") == ""
    assert company._website_candidate(None) == ""
    assert company._website_candidate("modal.com") == "https://modal.com"
