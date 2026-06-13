"""Task 020: outreach drafts must be non-empty strings."""

import json

from agents import outreach


def _run(monkeypatch, model_text: str) -> dict:
    monkeypatch.setattr(outreach.llm, "complete", lambda **kwargs: model_text)
    return outreach.run(
        "Baseten",
        {"title": "Inference latency", "description": "Cold starts."},
        {"name": "Bola Malek", "role": "FDE", "outreach_note": "note"},
        "## Problem\n...\n## Contribution\nBuild a benchmark.",
        "A documented project.",
        {"background_summary": "CS student."},
    )


def test_null_and_non_string_variants_are_dropped(monkeypatch) -> None:
    result = _run(monkeypatch, json.dumps({
        "email": "Subject: Hi\n\nShort note.",
        "linkedin_note": None,
        "connection_followup": 42,
        "twitter_dm": "   ",
    }))["result"]

    assert result == {"email": "Subject: Hi\n\nShort note."}


def test_unparseable_output_falls_back_to_email_draft(monkeypatch) -> None:
    result = _run(monkeypatch, "just plain text, no JSON")["result"]

    assert result["email"] == "just plain text, no JSON"


def test_em_and_en_dashes_are_normalized(monkeypatch) -> None:
    result = _run(monkeypatch, json.dumps({
        "email": "Subject: Hi\n\nYour work on routing—really sharp–impressive.",
    }))["result"]

    assert "—" not in result["email"]
    assert "–" not in result["email"]
    assert "Your work on routing - really sharp - impressive." in result["email"]
