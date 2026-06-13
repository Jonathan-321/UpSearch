from upsearch.company_identity import (
    CompanyIdentity,
    FetchedPage,
    canonical_website,
    is_dedicated_company_url,
    resolve_company_identity,
)


def page(url: str, title: str, text: str, status_code: int = 200) -> FetchedPage:
    return FetchedPage(url=url, title=title, text=text, status_code=status_code)


def test_rejects_aggregator_only_evidence() -> None:
    identity = resolve_company_identity(
        name="OpenAPI DevTools",
        lane="developer_tools",
        evidence_urls=["https://github.com/AndrewWalsh/openapi-devtools"],
        evidence_titles=["Show HN: OpenAPI DevTools"],
        fetcher=lambda _: page("", "", ""),
    )

    assert identity.status == "rejected"
    assert identity.official_domain == ""
    assert "No dedicated company or product domain" in identity.reason


def test_verifies_name_lane_and_employer_on_dedicated_domain() -> None:
    identity = resolve_company_identity(
        name="Jido",
        lane="agentic_ai",
        evidence_urls=["https://jido.run/docs"],
        evidence_titles=["Show HN: Jido - agent workflow infrastructure"],
        fetcher=lambda url: page(
            url,
            "Jido | Agentic workflow infrastructure",
            "Jido is an agent orchestration platform. Our company is hiring engineers.",
        ),
    )

    assert identity.verified
    assert identity.website == "https://jido.run"
    assert identity.official_domain == "jido.run"
    assert 0.0 <= identity.confidence <= 1.0


def test_rejects_ambiguous_acronym_when_lane_only_appears_in_discovery() -> None:
    identity = resolve_company_identity(
        name="MARS",
        lane="robotics_ai",
        evidence_urls=["https://mars.com"],
        evidence_titles=["MARS robotics AI platform"],
        fetcher=lambda url: page(
            url,
            "Mars Incorporated",
            "Mars is a global company with petcare and food products. Explore careers.",
        ),
    )

    assert identity.status == "rejected"
    assert identity.confidence < 0.9
    assert "technical-lane evidence on the fetched page" in identity.reason


def test_rejects_company_page_without_requested_lane_evidence() -> None:
    identity = resolve_company_identity(
        name="Acme",
        lane="inference_systems",
        evidence_urls=["https://acme.example/about"],
        evidence_titles=["Show HN: Acme - LLM inference engine"],
        fetcher=lambda url: page(
            url,
            "Acme",
            "Acme is a company building accounting software. View product and careers.",
        ),
    )

    assert not identity.verified
    assert "technical-lane evidence on the fetched page" in identity.reason


def test_rejects_competitor_page_that_mentions_candidate_name() -> None:
    identity = resolve_company_identity(
        name="Baseten",
        lane="inference_systems",
        evidence_urls=["https://hyperpodai.com"],
        evidence_titles=["Serverless Infrastructure for AI apps - 3x perf of baseten"],
        fetcher=lambda url: page(
            url,
            "Hyperpod AI - faster than Baseten",
            "Hyperpod is a company building GPU inference infrastructure and comparing itself to Baseten.",
        ),
    )

    assert not identity.verified
    assert "official-domain agreement" in identity.reason


def test_rejects_unfetchable_dedicated_domain() -> None:
    identity = resolve_company_identity(
        name="Jido",
        lane="agentic_ai",
        evidence_urls=["https://jido.run"],
        evidence_titles=["Show HN: Jido"],
        fetcher=lambda url: page(url, "", "", status_code=503),
    )

    assert identity.status == "rejected"
    assert "could not be fetched" in identity.reason


def test_url_helpers_normalize_and_filter_domains() -> None:
    assert canonical_website("https://Jido.run/docs/start") == "https://jido.run"
    assert is_dedicated_company_url("https://jido.run/docs")
    assert not is_dedicated_company_url("https://news.ycombinator.com/item?id=1")
    assert not is_dedicated_company_url("https://github.com/org/repo")


def test_identity_serializes_for_pipeline_handoffs() -> None:
    identity = CompanyIdentity(
        query_name="Jido",
        canonical_name="Jido",
        website="https://jido.run",
        official_domain="jido.run",
        lane="agentic_ai",
        status="verified",
        confidence=0.95,
        reason="Evidence agrees.",
        evidence_urls=["https://jido.run"],
        evidence_titles=["Jido"],
    )

    assert identity.to_dict()["official_domain"] == "jido.run"
