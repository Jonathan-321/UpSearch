"""Deterministic offline tests for person verification.

All HTTP fetches are mocked — no external calls, no network, no LLM.
Test vectors cover:
  - Verified person with real source content mentioning name + company
  - Unverified person with fabricated URL pointing to unrelated content
  - Phase 1 seeds still require fetched evidence
  - Empty source URL (no evidence to fetch)
  - Failed fetch (timeout / non-200)
  - Content mismatch (company mentioned but wrong person, or vice versa)
  - Mixed verified / unverified list
"""
from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from upsearch.person_verification import (
    _clean_html_text,
    check_contact_evidence,
    check_evidence,
    evidence_checks,
    fetch_source_text,
    strip_unverified_urls,
    verify_people,
    verify_person,
)


# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def baseten_bola() -> dict[str, Any]:
    """Historical seed person for Baseten; source labels are not trusted."""
    return {
        "name": "Bola Malek",
        "role": "Forward Deployed Engineer",
        "proximity": "FDE",
        "linkedin_url": None,
        "github_url": None,
        "twitter_url": None,
        "source_url": "https://www.baseten.co/author/bola-malek/",
        "relevance_score": 9,
        "relevance_reason": "Baseten author/FDE connected to customer-facing inference work.",
        "source": "Baseten author page from Phase 1 sourced dossier",
        "outreach_note": "Reference Baseten's continual-learning or Frontier Gateway writing.",
    }


@pytest.fixture
def verified_person() -> dict[str, Any]:
    """A candidate whose source_url contains both their name and the company."""
    return {
        "name": "Tero Karras",
        "role": "Research Scientist",
        "proximity": "researcher",
        "source_url": "https://example.com/tero-karras-nvidia",
        "relevance_score": 8,
        "relevance_reason": "Published work relevant to the problem.",
        "source": "Blog search",
        "outreach_note": "Reference the paper.",
    }


@pytest.fixture
def unverified_person() -> dict[str, Any]:
    """A candidate whose source_url does NOT contain their name or company."""
    return {
        "name": "Made Up Person",
        "role": "VP of Engineering",
        "proximity": "hiring_manager",
        "linkedin_url": "https://linkedin.com/in/made-up-person",
        "github_url": None,
        "twitter_url": "https://x.com/madeupperson",
        "source_url": "https://example.com/unrelated-page",
        "relevance_score": 5,
        "relevance_reason": "Seems plausible from role.",
        "source": "Inferred from role",
        "outreach_note": "Ask about their work.",
    }


@pytest.fixture
def no_source_person() -> dict[str, Any]:
    """A candidate with no source_url at all."""
    return {
        "name": "Ghost Candidate",
        "role": "Engineer",
        "proximity": "engineer",
        "linkedin_url": "https://linkedin.com/in/ghost",
        "source_url": None,
        "relevance_score": 3,
        "source": "Unknown",
        "outreach_note": "",
    }


# ── Unit tests: _clean_html_text ───────────────────────────────────────────

class TestCleanHtmlText:
    def test_strips_script_tags(self) -> None:
        html = "<script>var x = 1;</script><p>Hello</p>"
        assert _clean_html_text(html) == "Hello"

    def test_strips_style_tags(self) -> None:
        html = "<style>.cls{color:red;}</style><div>Content</div>"
        assert _clean_html_text(html) == "Content"

    def test_normalises_whitespace(self) -> None:
        html = "<p>Line1</p>  \n  <p>Line2</p>"
        assert _clean_html_text(html) == "Line1 Line2"

    def test_empty_input(self) -> None:
        assert _clean_html_text("") == ""

    def test_plain_text_passthrough(self) -> None:
        assert _clean_html_text("Tero Karras at NVIDIA") == "Tero Karras at NVIDIA"


# ── Unit tests: check_evidence ─────────────────────────────────────────────

class TestCheckEvidence:
    def test_name_and_company_found(self) -> None:
        text = "We are excited to have Tero Karras join NVIDIA's research team as a scientist."
        assert check_evidence(text, "Tero Karras", "NVIDIA", "Research Scientist") is True

    def test_name_found_company_missing(self) -> None:
        text = "Tero Karras published a new research paper."
        assert check_evidence(text, "Tero Karras", "NVIDIA", "Research Scientist") is False

    def test_company_found_name_missing(self) -> None:
        text = "NVIDIA's latest research architecture is Blackwell."
        assert check_evidence(text, "Tero Karras", "NVIDIA", "Research Scientist") is False

    def test_neither_found(self) -> None:
        text = "Something completely unrelated."
        assert check_evidence(text, "Tero Karras", "NVIDIA", "Research Scientist") is False

    def test_case_insensitive(self) -> None:
        text = "tero karras works at nvidia as a research scientist"
        assert check_evidence(text, "Tero Karras", "NVIDIA", "Research Scientist") is True

    def test_empty_text(self) -> None:
        assert check_evidence("", "Tero Karras", "NVIDIA", "Research Scientist") is False

    def test_empty_name(self) -> None:
        assert check_evidence("Tero works at NVIDIA", "", "NVIDIA", "Research Scientist") is False

    def test_role_or_relevance_required(self) -> None:
        text = "Tero Karras works at NVIDIA."
        assert check_evidence(text, "Tero Karras", "NVIDIA", "Research Scientist") is False
        checks = evidence_checks(text, "Tero Karras", "NVIDIA", "Research Scientist")
        assert checks == {"name": True, "company": True, "role_or_relevance": False}


class TestCheckContactEvidence:
    def test_contact_requires_name_and_company(self) -> None:
        assert check_contact_evidence("Tero Karras at NVIDIA", "Tero Karras", "NVIDIA") is True
        assert check_contact_evidence("Tero Karras personal profile", "Tero Karras", "NVIDIA") is False
        assert check_contact_evidence("NVIDIA research team", "Tero Karras", "NVIDIA") is False


# ── Unit tests: strip_unverified_urls ───────────────────────────────────────

class TestStripUnverifiedUrls:
    def test_verified_still_strips_model_contact_urls(self) -> None:
        person = {"name": "Tero", "linkedin_url": "https://linkedin.com/in/tero", "github_url": "https://github.com/tk"}
        result = strip_unverified_urls(person, verified=True)
        assert result["linkedin_url"] is None
        assert result["github_url"] is None

    def test_unverified_strips_contact(self) -> None:
        person = {"name": "Tero", "linkedin_url": "https://linkedin.com/in/tero", "github_url": "https://github.com/tk"}
        result = strip_unverified_urls(person, verified=False)
        assert result["linkedin_url"] is None
        assert result["github_url"] is None

    def test_unverified_preserves_source_url(self) -> None:
        person = {"name": "Tero", "source_url": "https://example.com/tero", "linkedin_url": "https://linkedin.com/in/tero"}
        result = strip_unverified_urls(person, verified=False)
        assert result["source_url"] == "https://example.com/tero"

    def test_original_not_mutated(self) -> None:
        person = {"name": "Tero", "linkedin_url": "https://linkedin.com/in/tero"}
        strip_unverified_urls(person, verified=False)
        assert person["linkedin_url"] == "https://linkedin.com/in/tero"


# ── Integration tests: verify_person (HTTP mocked) ─────────────────────────

class TestVerifyPerson:
    @patch(
        "upsearch.person_verification.fetch_source_text",
        return_value="<html><body>Bola Malek is a Forward Deployed Engineer at Baseten.</body></html>",
    )
    def test_phase_1_seed_still_requires_fetched_evidence(self, mock_fetch, baseten_bola: dict) -> None:
        result = verify_person(baseten_bola, "Baseten")
        assert result["verification_status"] == "verified"
        assert result["linkedin_url"] is None
        assert result["github_url"] is None
        mock_fetch.assert_called_once_with("https://www.baseten.co/author/bola-malek/")

    @patch("upsearch.person_verification.fetch_source_text", return_value="<html><body>Tero Karras works at NVIDIA as a Research Scientist.</body></html>")
    def test_verified_with_matching_source(self, mock_fetch, verified_person: dict) -> None:
        result = verify_person(verified_person, "NVIDIA")
        assert result["verification_status"] == "verified"
        assert result["source_url"] == "https://example.com/tero-karras-nvidia"
        # linkedin_url was not in the original — ensure it's absent from schema
        assert "linkedin_url" not in result or result.get("linkedin_url") is None

    @patch("upsearch.person_verification.fetch_source_text", return_value="<html><body>This page is about the weather in San Francisco.</body></html>")
    def test_unverified_when_source_does_not_match(self, mock_fetch, unverified_person: dict) -> None:
        result = verify_person(unverified_person, "NVIDIA")
        assert result["verification_status"] == "unverified"
        assert result["linkedin_url"] is None
        assert result["twitter_url"] is None

    @patch("upsearch.person_verification.fetch_source_text", return_value="")
    def test_unverified_on_failed_fetch(self, mock_fetch, unverified_person: dict) -> None:
        result = verify_person(unverified_person, "NVIDIA")
        assert result["verification_status"] == "unverified"
        assert result["linkedin_url"] is None

    def test_no_source_url(self, no_source_person: dict) -> None:
        result = verify_person(no_source_person, "SomeCorp")
        assert result["verification_status"] == "unverified"
        assert result["linkedin_url"] is None
        assert result["source_url"] is None

    @patch("upsearch.person_verification.fetch_source_text", return_value="<html><body>Made Up Person works at NVIDIA as an Engineering Manager.</body></html>")
    def test_verified_source_does_not_preserve_synthesized_contact_url(self, mock_fetch, unverified_person: dict) -> None:
        def fake_fetch(url: str) -> str:
            if url == "https://example.com/unrelated-page":
                return "<html><body>Made Up Person works at NVIDIA as an Engineering Manager.</body></html>"
            return "<html><body>This unrelated contact page mentions Made Up Person only.</body></html>"

        mock_fetch.side_effect = fake_fetch
        result = verify_person(unverified_person, "NVIDIA")
        assert result["verification_status"] == "verified"
        assert result["linkedin_url"] is None
        assert result["twitter_url"] is None
        assert result["contact_url_checks"]["linkedin_url"]["fetched"] is True
        assert result["contact_url_checks"]["linkedin_url"]["matched"] is False

    @patch("upsearch.person_verification.fetch_source_text")
    def test_same_exact_contact_url_can_survive_when_fetched_and_matched(self, mock_fetch) -> None:
        person = {
            "name": "Tero Karras",
            "role": "Research Scientist",
            "source_url": "https://github.com/tkarras",
            "github_url": "https://github.com/tkarras",
            "linkedin_url": "https://linkedin.com/in/guessed-tero",
            "relevance_reason": "NVIDIA research profile.",
        }

        def fake_fetch(url: str) -> str:
            if url == "https://github.com/tkarras":
                return "Tero Karras is a Research Scientist at NVIDIA."
            return "Tero Karras profile with no company evidence."

        mock_fetch.side_effect = fake_fetch
        result = verify_person(person, "NVIDIA")

        assert result["verification_status"] == "verified"
        assert result["github_url"] == "https://github.com/tkarras"
        assert result["linkedin_url"] is None
        assert result["contact_url_checks"]["github_url"]["matched"] is True
        assert result["contact_url_checks"]["linkedin_url"]["matched"] is False


# ── Integration tests: verify_people ────────────────────────────────────────

class TestVerifyPeople:
    @patch("upsearch.person_verification.fetch_source_text")
    def test_mixed_verified_and_unverified(self, mock_fetch) -> None:
        people = [
            {
                "name": "Tero Karras",
                "role": "Researcher",
                "source_url": "https://example.com/tero",
                "linkedin_url": "https://linkedin.com/in/tk",
            },
            {"name": "No One", "source_url": "https://example.com/weather", "linkedin_url": "https://linkedin.com/in/fake"},
        ]

        def fake_fetch(url: str) -> str:
            if url == "https://example.com/tero":
                return "<html><body>Tero Karras works at NVIDIA as a researcher.</body></html>"
            if url == "https://linkedin.com/in/tk":
                return "<html><body>Tero Karras personal page without company evidence.</body></html>"
            return "<html><body>Weather in San Francisco.</body></html>"

        mock_fetch.side_effect = fake_fetch
        results = verify_people(people, "NVIDIA")
        assert results[0]["verification_status"] == "verified"
        assert results[0]["linkedin_url"] is None
        assert results[1]["verification_status"] == "unverified"
        assert results[1]["linkedin_url"] is None

    def test_empty_list(self) -> None:
        assert verify_people([], "NVIDIA") == []

    def test_phase_1_seed_in_mixed_list_is_verified_by_fetch(self, baseten_bola: dict) -> None:
        llm_candidate = {"name": "Someone", "source_url": "https://example.com/person", "relevance_score": 5}

        def fake_fetch(url: str) -> str:
            if "baseten.co" in url:
                return "Bola Malek is a Forward Deployed Engineer at Baseten."
            return ""

        with patch("upsearch.person_verification.fetch_source_text", side_effect=fake_fetch):
            results = verify_people([baseten_bola, llm_candidate], "Baseten")

        assert results[0]["verification_status"] == "verified"
        assert results[0]["source_url"] == "https://www.baseten.co/author/bola-malek/"
        # Phase labels do not create a trust bypass; the fetch above did.
        assert results[0]["verification_reason"] == "evidence_contract_passed"
        # LLM candidate without a fetchable source is unverified
        assert results[1]["verification_status"] == "unverified"


# ── Integration tests: fetch_source_text ────────────────────────────────────

class TestFetchSourceText:
    @patch("upsearch.person_verification.httpx.Client")
    def test_invalid_url_returns_empty(self, mock_client) -> None:
        assert fetch_source_text("") == ""
        assert fetch_source_text("not-a-url") == ""
        # Client should never be constructed for invalid URLs
        mock_client.assert_not_called()

    @patch("upsearch.person_verification.httpx.Client")
    def test_exception_returns_empty(self, mock_client) -> None:
        instance = mock_client.return_value.__enter__.return_value
        instance.get.side_effect = Exception("Connection refused")
        result = fetch_source_text("https://example.com/person")
        assert result == ""
        instance.get.assert_called_once()

    @patch("upsearch.person_verification.httpx.Client")
    def test_successful_fetch(self, mock_client) -> None:
        instance = mock_client.return_value.__enter__.return_value
        mock_response = instance.get.return_value
        mock_response.raise_for_status.return_value = None
        mock_response.text = "<html><body>Tero Karras at NVIDIA</body></html>"
        mock_response.headers = {"content-type": "text/html"}

        result = fetch_source_text("https://example.com/tero-karras-nvidia")
        assert "Tero Karras" in result
        assert "NVIDIA" in result
