"""Task 017: official-domain fallback for company identity resolution."""

from upsearch.company_identity import (
    FetchedPage,
    official_site_candidates,
    resolve_company_identity_with_fallback,
)


BASETEN_PAGE = FetchedPage(
    url="https://baseten.co",
    title="Baseten | Machine learning infrastructure",
    text=(
        "Baseten is the platform for serving and scaling ML model inference on "
        "GPU infrastructure. Product, pricing, customers, careers."
    ),
    status_code=200,
)

COMPETITOR_PAGE = FetchedPage(
    url="https://www.hyperpodai.com",
    title="HyperPod — serverless AI infrastructure",
    text="Serverless inference platform. 3x perf, 1/5 the cost. Product pricing customers.",
    status_code=200,
)


def fetcher_for(pages: dict[str, FetchedPage]):
    def fetch(url: str) -> FetchedPage:
        return pages.get(url, FetchedPage(url=url))

    return fetch


def test_official_site_candidates_orders_common_tlds() -> None:
    assert official_site_candidates("Baseten") == [
        "https://baseten.com",
        "https://baseten.ai",
        "https://baseten.co",
        "https://baseten.io",
    ]
    assert official_site_candidates("  ") == []


def test_polluted_discovery_evidence_recovers_via_domain_probe() -> None:
    search_calls: list[str] = []

    def search(query: str, limit: int) -> list[dict[str, str]]:
        search_calls.append(query)
        return []

    identity = resolve_company_identity_with_fallback(
        name="Baseten",
        lane="ai_infra",
        evidence_urls=["https://www.hyperpodai.com"],
        evidence_titles=["Show HN: 3x perf of baseten, 1/5 the cost"],
        fetcher=fetcher_for({"https://baseten.co": BASETEN_PAGE, "https://www.hyperpodai.com": COMPETITOR_PAGE}),
        search=search,
    )

    assert identity.verified
    assert identity.website == "https://baseten.co"
    assert identity.official_domain == "baseten.co"
    # The domain probe succeeded, so the web search was never needed.
    assert search_calls == []


def test_search_runs_only_after_probes_fail() -> None:
    search_calls: list[str] = []

    def search(query: str, limit: int) -> list[dict[str, str]]:
        search_calls.append(query)
        return [{"title": "Baseten official site", "url": "https://app.baseten.example"}]

    pages = {
        "https://app.baseten.example": FetchedPage(
            url="https://baseten.example",
            title="Baseten | ML inference platform",
            text="Serving model inference on GPU. Product pricing customers careers.",
            status_code=200,
        ),
    }

    identity = resolve_company_identity_with_fallback(
        name="Baseten",
        lane="ai_infra",
        evidence_urls=["https://news.ycombinator.com/item?id=1"],
        evidence_titles=[],
        fetcher=fetcher_for(pages),
        search=search,
    )

    assert search_calls == ["Baseten official website"]
    assert identity.verified
    assert identity.official_domain == "baseten.example"


def test_all_fallbacks_failing_keeps_most_informative_rejection() -> None:
    identity = resolve_company_identity_with_fallback(
        name="Baseten",
        lane="ai_infra",
        evidence_urls=["https://www.hyperpodai.com"],
        evidence_titles=[],
        fetcher=fetcher_for({"https://www.hyperpodai.com": COMPETITOR_PAGE}),
        search=lambda query, limit: [],
    )

    assert not identity.verified
    assert identity.status == "rejected"
    # The competitor page scored on lane/employer evidence, beating the
    # unfetchable probe candidates; its reason names the real gap.
    assert "official-domain agreement" in identity.reason


def test_www_prefixed_final_url_still_matches_host_name() -> None:
    """Sites that redirect to a www. host must not fail official-domain agreement.

    Regression: host matching used the first DNS label, so any company whose
    site resolves to www.<name>.<tld> was systematically unverifiable.
    """
    www_page = FetchedPage(
        url="https://www.baseten.co/",
        title="Inference Platform: Deploy AI models in production | Baseten",
        text="Baseten inference platform. Product pricing customers careers.",
        status_code=200,
    )

    identity = resolve_company_identity_with_fallback(
        name="Baseten",
        lane="ai_infra",
        evidence_urls=[],
        evidence_titles=[],
        fetcher=fetcher_for({"https://baseten.com": www_page}),
        search=lambda query, limit: [],
    )

    assert identity.verified
    assert identity.website == "https://www.baseten.co"
    assert identity.official_domain == "www.baseten.co"


def test_verified_discovery_evidence_short_circuits_fallback() -> None:
    def search(query: str, limit: int) -> list[dict[str, str]]:
        raise AssertionError("search must not run when discovery evidence verifies")

    identity = resolve_company_identity_with_fallback(
        name="Baseten",
        lane="ai_infra",
        evidence_urls=["https://baseten.co"],
        evidence_titles=["Baseten raises round for ML infrastructure"],
        fetcher=fetcher_for({"https://baseten.co": BASETEN_PAGE}),
        search=search,
    )

    assert identity.verified
    assert identity.official_domain == "baseten.co"


def test_fetch_page_retries_js_shell_with_browser_ua(monkeypatch) -> None:
    """Sites serving the verifier UA a contentless shell get one browser-UA retry."""
    from upsearch import company_identity

    calls: list[str] = []

    class FakeResponse:
        def __init__(self, text):
            self.text = text
            self.url = "https://www.databricks.com"
            self.status_code = 200

        def raise_for_status(self):
            return None

    def fake_get(url, timeout, user_agent):
        calls.append(user_agent)
        if "Mozilla" in user_agent:
            return FakeResponse(
                "<title>Databricks: Leading Data and AI Platform</title>"
                '<meta name="description" content="Unified platform for data, analytics and AI">'
                "<p>Build AI on your data.</p>"
            )
        return FakeResponse("<script>var x=1;</script>")

    monkeypatch.setattr(company_identity, "_get", fake_get)

    page = company_identity.fetch_page("https://www.databricks.com")

    assert len(calls) == 2
    assert "Databricks" in page.title
    assert "analytics" in page.text  # meta description counted as evidence


def test_rejection_names_closest_fetched_candidate() -> None:
    """A typo'd company blocks, and the reason names the nearest real site."""
    oblivus_page = FetchedPage(
        url="https://www.oblivus.com",
        title="Oblivus | The next generation GPU Cloud",
        text="GPU cloud for AI inference. Pricing, product, customers.",
        status_code=200,
    )

    identity = resolve_company_identity_with_fallback(
        name="Oblivious GPU Cloud",
        lane="ai_infra",
        evidence_urls=["https://www.oblivus.com"],
        evidence_titles=[],
        fetcher=fetcher_for({"https://www.oblivus.com": oblivus_page}),
        search=lambda query, limit: [],
    )

    assert not identity.verified
    assert "Closest fetched candidate: www.oblivus.com" in identity.reason
