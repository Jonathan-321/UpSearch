from agents import qa


def test_qa_ignores_null_optional_drafts(monkeypatch) -> None:
    monkeypatch.setattr(
        qa,
        "qa_verify",
        lambda *args, **kwargs: (
            {
                "score": 7,
                "flags": [],
                "recommendations": [],
                "claim_check": "Claims are bounded.",
                "source_coverage": "Sources are present.",
            },
            False,
        ),
    )

    result = qa.run(
        {
            "outreach_drafts": {
                "email": "Hi there",
                "linkedin_note": "Short note",
                "connection_followup": None,
                "recruiter": None,
            },
            "people": [],
            "technical_note": "Technical note",
            "adjacent_proof": "Source-backed proof",
        },
        {"proof_points": ["Built a source-backed benchmark."]},
    )

    assert result["score"] == 7
    assert result["passed"] is True
