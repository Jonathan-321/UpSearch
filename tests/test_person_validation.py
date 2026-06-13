"""Task 022: deterministic person-name gate across the people pipeline."""

from agents import people as people_agent
from upsearch.person_validation import filter_people, is_person_name, person_name_rejection
from upsearch.person_verification import verify_person
from upsearch.sourcing import company_people


REAL_NAMES = [
    "Liang Xiong",
    "Jonathan Frankle",
    "Bola Malek",
    "Joey Zwicker",
    "Dmytro Dzhulgakov",
    "J. Robert Oppenheimer",
    "Maria de Souza",
    # Diacritics are letters; found flagged as malformed in the live DB.
    "Jérôme Labesse",
    "Marek Šuppa",
    "Michal Servátka",
    "Ján Sendecký",
]

# Every one of these appeared as a scored "person" in a real packet.
SCREENSHOT_JUNK = [
    "Platform",
    "Use Cases",
    "Developers",
    "Pricing",
    "Partners",
    "Resources",
    "Company",
    "Fireworks GitHub Contributors",
    "ML Systems Engineers",
    "Frontier RL Is Cheaper Than You Think",
    "3/10/2026",
    "Model Library",
    "Get Started",
]


def test_real_names_pass() -> None:
    for name in REAL_NAMES:
        assert is_person_name(name), f"{name!r} rejected: {person_name_rejection(name)}"


def test_screenshot_junk_is_rejected() -> None:
    for junk in SCREENSHOT_JUNK:
        assert not is_person_name(junk), f"{junk!r} passed the person-name gate"


def test_filter_people_splits_kept_and_rejected() -> None:
    kept, rejected = filter_people([
        {"name": "Liang Xiong"},
        {"name": "Pricing"},
        {"name": "Frontier RL Is Cheaper Than You Think"},
    ])

    assert [p["name"] for p in kept] == ["Liang Xiong"]
    assert len(rejected) == 2


def test_verify_person_rejects_non_names_without_fetching(monkeypatch) -> None:
    def _no_fetch(url):
        raise AssertionError("non-names must never trigger a fetch")

    monkeypatch.setattr("upsearch.person_verification.fetch_source_text", _no_fetch)

    result = verify_person(
        {"name": "Pricing", "role": "Serverless", "source_url": "https://fireworks.ai/pricing"},
        "Fireworks",
    )

    assert result["verification_status"] == "unverified"
    assert result["verification_reason"].startswith("not_a_person_name:")


def test_company_people_connector_drops_nav_headings(monkeypatch) -> None:
    html = """
    <li><h3>Platform</h3><span>AI Native</span></li>
    <li><h3>Pricing</h3><span>Serverless</span></li>
    <li><h3>Liang Xiong</h3><span>Co-founder &amp; CTO</span></li>
    <h4>Frontier RL Is Cheaper Than You Think</h4>
    """
    monkeypatch.setattr(company_people, "_fetch_page", lambda url: html)

    candidates = company_people.fetch_company_people(
        "fireworks.ai", ["https://fireworks.ai/company"]
    )

    assert [c["name"] for c in candidates] == ["Liang Xiong"]


def test_people_agent_filters_pool_and_keeps_seeds_additive(monkeypatch) -> None:
    monkeypatch.setattr(people_agent.hackernews, "search", lambda *a, **k: [])
    monkeypatch.setattr(people_agent, "fetch_company_people", lambda *a, **k: [])
    monkeypatch.setattr(people_agent, "find_company_org", lambda *a, **k: None)
    monkeypatch.setattr(people_agent, "verify_people", lambda people, company: [
        {**p, "verification_status": "verified"} for p in people
    ])
    monkeypatch.setattr(
        people_agent.llm,
        "complete",
        lambda **kwargs: (
            '{"people": ['
            '{"name": "Amir Haghighat", "role": "Co-founder", "source_url": "https://www.baseten.co/about"},'
            '{"name": "ML Systems Engineers", "role": "Infrastructure Team", "source_url": "https://www.baseten.co"}'
            "]}"
        ),
    )

    out = people_agent.run("Baseten", {"title": "inference"}, {"skills": []})
    names = [p["name"] for p in out["result"]["people"]]

    # The model's real person survives, the group placeholder is dropped, and
    # the curated Baseten seeds merge in additively instead of replacing.
    assert "Amir Haghighat" in names
    assert "ML Systems Engineers" not in names
    assert "Bola Malek" in names
