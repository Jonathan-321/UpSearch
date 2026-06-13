import json

from agents import problem
from agents.problem import _fallback_problem, _sanitize_problems


def test_problem_sources_are_restricted_to_retrieved_catalog():
    problems = [
        {
            "title": "Serving latency",
            "source_urls": [
                "https://company.example/blog/latency",
                "https://invented.example/fake",
            ],
        },
        {
            "title": "Unsupported claim",
            "source_urls": ["https://invented.example/only"],
        },
    ]

    sanitized = _sanitize_problems(
        problems,
        {"https://company.example/blog/latency"},
    )

    assert sanitized == [
        {
            "title": "Serving latency",
            "source_urls": ["https://company.example/blog/latency"],
        }
    ]


def test_web_and_blog_retrieval_count_as_source_candidates(monkeypatch):
    """DDG web/blog results are retrieval output: citable and reported upstream.

    Regression: only HN/Reddit URLs were allowed, so when those were empty the
    model's legitimately-cited blog URLs were stripped, the synthesized
    fallback fired, and the checkup gate blocked the packet as unverified.
    """
    blog_url = "https://www.baseten.co/blog/cold-starts"
    search_calls: list[tuple[str, str]] = []

    monkeypatch.setattr(problem.hackernews, "search", lambda *a, **k: [])
    monkeypatch.setattr(problem.reddit, "search", lambda *a, **k: [])

    def fake_problems_search(name, lane):
        search_calls.append((name, lane))
        return [{"title": "Baseten on GPU cold starts", "url": blog_url}]

    monkeypatch.setattr(problem, "search_company_problems", fake_problems_search)
    monkeypatch.setattr(
        problem,
        "search_company_blog",
        lambda name, domain: [{"title": "Engineering at Baseten", "url": "https://www.baseten.co/blog/engineering"}],
    )
    monkeypatch.setattr(
        problem.llm,
        "complete",
        lambda **kwargs: json.dumps({
            "problems": [{
                "title": "GPU cold starts",
                "description": "Cold start latency on model serving.",
                "source_urls": [blog_url],
                "source_signal": "Company blog post",
                "relevance_score": 8,
                "contribution_surface": "benchmark",
            }],
        }),
    )

    out = problem.run(
        "Baseten",
        {"lane": "ai_infra", "official_domain": "www.baseten.co", "tech_stack": [], "what_they_do": "inference"},
        {"skills": []},
    )

    assert [p["source_urls"] for p in out["result"]["problems"]] == [[blog_url]]
    assert blog_url in out["source_urls"]
    assert "https://www.baseten.co/blog/engineering" in out["source_urls"]
    # Lane keys are naturalized before being used as search terms.
    assert search_calls == [("Baseten", "ai infra")]


def test_fallback_does_not_promote_unverified_model_website():
    fallback = _fallback_problem(
        "UnknownCo",
        {
            "website": "https://invented.example",
            "identity_status": "unverified",
            "what_they_do": "AI platform",
        },
        [],
    )

    assert fallback["source_urls"] == []
