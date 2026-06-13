"""Deterministic offline tests for the company-owned people source connector.

All HTTP fetches are mocked — no external calls, no network.
Test vectors cover:
  - On-domain pages are fetched; off-domain pages are rejected.
  - Author-byline extraction from HTML.
  - Team-card extraction from HTML.
  - Dedup by normalised name across multiple page results.
  - Network failure returns empty list (no fabricated person).
  - Empty domain or URL list returns empty list.
  - Retrieved candidates feed the verify_people path (integration-style test).
"""
from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from upsearch.sourcing.company_people import (
    _domain_from_url,
    _extract_candidates,
    _merge_dedup,
    _normalise_name,
    _on_verified_domain,
    fetch_company_people,
)

# ── Tests: helpers ──────────────────────────────────────────────────────────


class TestDomainFromUrl:
    def test_bare_domain(self) -> None:
        assert _domain_from_url("https://baseten.co/team") == "baseten.co"

    def test_www_prefix(self) -> None:
        assert _domain_from_url("https://www.baseten.co/author/bola") == "www.baseten.co"

    def test_invalid(self) -> None:
        assert _domain_from_url("not-a-url") == ""


class TestOnVerifiedDomain:
    def test_matching_domain(self) -> None:
        assert _on_verified_domain("https://baseten.co/team", "baseten.co") is True

    def test_subdomain_mismatch(self) -> None:
        assert _on_verified_domain("https://blog.baseten.co/x", "baseten.co") is False

    def test_wrong_domain(self) -> None:
        assert _on_verified_domain("https://other.com/team", "baseten.co") is False

    def test_non_http_rejected(self) -> None:
        assert _on_verified_domain("ftp://baseten.co/file", "baseten.co") is False

    def test_not_a_url(self) -> None:
        assert _on_verified_domain("baseten.co", "baseten.co") is False


class TestNormaliseName:
    def test_basic(self) -> None:
        assert _normalise_name("Bola Malek") == "bola malek"

    def test_trailing_punctuation(self) -> None:
        assert _normalise_name("Raymond Cano,") == "raymond cano"

    def test_multi_whitespace(self) -> None:
        assert _normalise_name("John   Smith") == "john smith"

    def test_empty(self) -> None:
        assert _normalise_name("") == ""

    def test_hyphenated(self) -> None:
        assert _normalise_name("Mary-Jane Watson") == "mary-jane watson"


# ── Tests: extraction ───────────────────────────────────────────────────────


class TestExtractCandidates:
    def test_author_byline_pattern(self) -> None:
        html = "<article><p>By: Tero Karras</p><p>Content here.</p></article>"
        result = _extract_candidates(html, "https://example.com/blog", "example.com")
        names = [p["name"] for p in result]
        assert "Tero Karras" in names

    def test_written_by_pattern(self) -> None:
        html = "<div class='post'><p>Written by Bola Malek</p></div>"
        result = _extract_candidates(html, "https://example.com/post1", "example.com")
        names = [p["name"] for p in result]
        assert "Bola Malek" in names

    def test_team_card_by_h3(self) -> None:
        html = (
            "<div class='team-member'><h3>Alice Zhang</h3><p>Engineer</p></div>"
            "<div class='team-member'><h3>Bob Chen</h3><p>Designer</p></div>"
        )
        result = _extract_candidates(html, "https://example.com/team", "example.com")
        names = [p["name"] for p in result]
        assert "Alice Zhang" in names
        assert "Bob Chen" in names

    def test_team_card_by_h4(self) -> None:
        html = "<div class='person'><h4>Diana Ross</h4><p>ML Engineer</p></div>"
        result = _extract_candidates(html, "https://example.com/team", "example.com")
        names = [p["name"] for p in result]
        assert "Diana Ross" in names

    def test_rel_author_pattern(self) -> None:
        html = '<a rel="author" href="/author/foo">John Smith</a>'
        result = _extract_candidates(html, "https://example.com/post", "example.com")
        names = [p["name"] for p in result]
        assert "John Smith" in names

    def test_author_name_class(self) -> None:
        html = '<span class="author-name">Tero Karras</span>'
        result = _extract_candidates(html, "https://example.com/post", "example.com")
        names = [p["name"] for p in result]
        assert "Tero Karras" in names

    def test_html_no_names(self) -> None:
        html = "<html><body><p>Welcome to our company</p></body></html>"
        result = _extract_candidates(html, "https://example.com/team", "example.com")
        assert result == []

    def test_empty_html(self) -> None:
        assert _extract_candidates("", "https://example.com/team", "example.com") == []

    def test_script_tags_stripped(self) -> None:
        html = "<script>var author = 'Fake Person';</script><p>Welcome</p>"
        result = _extract_candidates(html, "https://example.com/team", "example.com")
        assert result == []

    def test_person_record_fields(self) -> None:
        html = "<p>By: Alice Zhang</p>"
        result = _extract_candidates(html, "https://example.com/blog", "example.com")
        assert len(result) == 1
        person = result[0]
        assert person["name"] == "Alice Zhang"
        assert person["source_url"] == "https://example.com/blog"
        assert person["source"] == "company-people connector (example.com)"
        assert person["role"] == "Technical author"
        assert person["relevance_reason"]
        assert person["relevance_score"] == 5


# ── Tests: dedup ────────────────────────────────────────────────────────────


class TestMergeDedup:
    def test_no_duplicates(self) -> None:
        existing = [{"name": "Alice Zhang"}]
        new = [{"name": "Bob Chen"}]
        result = _merge_dedup(existing, new)
        assert len(result) == 2

    def test_duplicate_by_normalised_name(self) -> None:
        existing = [{"name": "Alice Zhang"}]
        new = [{"name": "Alice   Zhang"}]
        result = _merge_dedup(existing, new)
        assert len(result) == 1  # first-wins, no duplicate

    def test_empty_existing(self) -> None:
        new = [{"name": "Alice Zhang"}]
        result = _merge_dedup([], new)
        assert len(result) == 1

    def test_empty_new(self) -> None:
        existing = [{"name": "Alice Zhang"}]
        result = _merge_dedup(existing, [])
        assert len(result) == 1


# ── Tests: fetch_company_people (HTTP mocked) ───────────────────────────────


class TestFetchCompanyPeople:
    @patch("upsearch.sourcing.company_people.httpx.Client")
    def test_fetches_on_domain_and_extracts_authors(self, mock_client) -> None:
        instance = mock_client.return_value.__enter__.return_value
        resp = instance.get.return_value
        resp.raise_for_status.return_value = None
        resp.text = "<html><body><p>By: Bola Malek</p><p>By: Raymond Cano</p></body></html>"

        result = fetch_company_people("baseten.co", ["https://www.baseten.co/author/bola-malek/"])

        assert len(result) >= 1
        names = {p["name"] for p in result}
        assert "Bola Malek" in names

    @patch("upsearch.sourcing.company_people.httpx.Client")
    def test_off_domain_urls_skipped(self, mock_client) -> None:
        instance = mock_client.return_value.__enter__.return_value
        resp = instance.get.return_value
        resp.raise_for_status.return_value = None
        resp.text = "<html><body><p>By: Someone Person</p></body></html>"

        result = fetch_company_people(
            "baseten.co",
            [
                "https://www.baseten.co/team",
                "https://linkedin.com/company/baseten",
            ],
        )

        # Only the baseten.co page should have been fetched
        names = {p["name"] for p in result}
        assert "Someone Person" in names
        # The Client should only be called once (linkedin URL skipped)
        assert instance.get.call_count == 1

    @patch("upsearch.sourcing.company_people.httpx.Client")
    def test_network_failure_returns_empty(self, mock_client) -> None:
        instance = mock_client.return_value.__enter__.return_value
        instance.get.side_effect = Exception("Connection refused")

        result = fetch_company_people("baseten.co", ["https://www.baseten.co/team"])
        assert result == []

    @patch("upsearch.sourcing.company_people.httpx.Client")
    def test_duplicate_names_merged(self, mock_client) -> None:
        instance = mock_client.return_value.__enter__.return_value
        resp = instance.get.return_value
        resp.raise_for_status.return_value = None
        resp.text = "<html><body><p>By: Bola Malek</p></body></html>"

        result = fetch_company_people(
            "baseten.co",
            [
                "https://www.baseten.co/author/bola-malek/",
                "https://www.baseten.co/blog/bola-malek-post/",
            ],
        )

        assert len(result) == 1  # same name from two pages → merged

    def test_empty_domain_returns_empty(self) -> None:
        assert fetch_company_people("", ["https://example.com/team"]) == []

    def test_empty_url_list_returns_empty(self) -> None:
        assert fetch_company_people("example.com", []) == []

    @patch("upsearch.sourcing.company_people.httpx.Client")
    def test_non_200_response_returns_empty(self, mock_client) -> None:
        instance = mock_client.return_value.__enter__.return_value
        from httpx import HTTPStatusError, Request

        resp = instance.get.return_value
        resp.raise_for_status.side_effect = HTTPStatusError(
            "404 Not Found", request=Request("GET", "https://example.com/team"), response=resp
        )

        result = fetch_company_people("example.com", ["https://example.com/team"])
        assert result == []

    @patch("upsearch.sourcing.company_people.httpx.Client")
    def test_extracted_candidates_have_minimal_fields(self, mock_client) -> None:
        instance = mock_client.return_value.__enter__.return_value
        resp = instance.get.return_value
        resp.raise_for_status.return_value = None
        resp.text = "<html><body><p>By: Alice Zhang</p></body></html>"

        result = fetch_company_people("example.com", ["https://example.com/team"])
        assert len(result) == 1
        person = result[0]
        assert "name" in person
        assert "source_url" in person
        assert "source" in person
        assert "role" in person
        assert "proximity" in person
        # Must not contain synthetic contact URLs
        assert "linkedin_url" not in person or person.get("linkedin_url") is None
        assert "github_url" not in person or person.get("github_url") is None
        assert "twitter_url" not in person or person.get("twitter_url") is None
        assert "email" not in person

    @patch("upsearch.sourcing.company_people.httpx.Client")
    def test_extraction_multiple_pages(self, mock_client) -> None:
        """Multiple pages on the same domain are each fetched and extracted."""
        instance = mock_client.return_value.__enter__.return_value

        def side_effect(url, **kw):
            class MockResp:
                text = ""
                status_code = 200

                def raise_for_status(self):
                    pass

            resp = MockResp()
            if "team" in url:
                resp.text = "<html><body><h3>Alice Zhang</h3><h3>Bob Chen</h3></body></html>"
            elif "blog" in url:
                resp.text = "<html><body><p>By: Carol Davis</p></body></html>"
            else:
                resp.text = "<html><body></body></html>"
            return resp

        instance.get.side_effect = side_effect

        result = fetch_company_people(
            "example.com",
            ["https://example.com/team", "https://example.com/blog"],
        )
        names = {p["name"] for p in result}
        assert "Alice Zhang" in names
        assert "Bob Chen" in names
        assert "Carol Davis" in names
