from upsearch.packet_checkup import evaluate_packet


def test_people_url_without_verified_status_does_not_count_as_evidence() -> None:
    packet = {
        "technical_note": " ".join(["technical"] * 300),
        "outreach_drafts": {"email": "A concise draft."},
        "qa_score": 8,
        "qa_flags": [],
    }
    problems = [
        {
            "title": "Serving latency",
            "source_urls": ["https://example.com/problem"],
            "relevance_score": 8,
        }
    ]
    people = [
        {
            "name": "Taylor Kim",
            "source_url": "https://example.com/taylor",
            "verification_status": "unverified",
            "relevance_score": 10,
        }
    ]

    result = evaluate_packet("AcmeFlow", packet, problems, people)

    assert result["failure_category"] == "weak_person_mapping"
    assert result["facts"]["verified_people"] == 0
    people_metric = next(metric for metric in result["metrics"] if metric["name"] == "People mapping")
    assert people_metric["detail"] == "0/1 people passed evidence verification"
