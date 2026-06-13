"""Task 031: profile extraction cache.

agents/profile.run() made an LLM call on every packet run even though the
profile text rarely changes. The parsed LLM extraction is now cached at
CACHE_PATH keyed by sha256 of the raw profile text. These tests pin the
contract: a hit skips llm.complete but still merges live source evidence; a
corrupt or stale cache falls through and is overwritten; UPSEARCH_PROFILE_CACHE=0
disables both read and write; the degraded fallback path is never cached.
"""
from __future__ import annotations

import hashlib
import json

import pytest

from agents import profile
from upsearch import profile_source_fetch

RAW_PROFILE = """Name: Cache Tester
School: Example University

Background:
- Interested in: ML systems
- Coursework: Operating Systems

Looking for:
- ML engineer intern
"""

LLM_PAYLOAD = {
    "name": "Cache Tester",
    "school": "Example University",
    "email": "cache@example.edu",
    "skills": ["Python"],
    "coursework": ["Operating Systems"],
    "projects": [],
    "interests": ["ML systems"],
    "preferred_roles": ["ML engineer intern"],
    "github_url": "",
    "background_summary": "Student focused on ML systems.",
    "proof_points": ["Built an inference benchmark"],
}


class LLMSpy:
    """Counts llm.complete calls; can be told to fail to simulate outages."""

    def __init__(self, payload: dict | str = LLM_PAYLOAD, fail: bool = False):
        self.calls = 0
        self.payload = payload
        self.fail = fail

    def __call__(self, **kwargs) -> str:
        self.calls += 1
        if self.fail:
            raise RuntimeError("provider down")
        if isinstance(self.payload, str):
            return self.payload
        return json.dumps(self.payload)


@pytest.fixture
def cache_path(monkeypatch: pytest.MonkeyPatch, tmp_path):
    """Isolate the on-disk cache and the source-fetch report from the repo.

    The cache defaults off under pytest (so unrelated tests can never touch
    the operator's real .upsearch/profile cache); force it on here against a
    tmp path.
    """
    path = tmp_path / "structured-cache.json"
    monkeypatch.setattr(profile, "CACHE_PATH", path)
    monkeypatch.setattr(profile_source_fetch, "load_cached_report", lambda: None)
    monkeypatch.setenv("UPSEARCH_PROFILE_CACHE", "1")
    return path


@pytest.fixture
def llm_spy(monkeypatch: pytest.MonkeyPatch):
    spy = LLMSpy()
    monkeypatch.setattr(profile.llm, "complete", spy)
    return spy


def test_cache_hit_skips_llm_call(cache_path, llm_spy):
    first = profile.run(RAW_PROFILE)
    assert llm_spy.calls == 1
    assert cache_path.exists()
    payload = json.loads(cache_path.read_text(encoding="utf-8"))
    assert payload["hash"] == hashlib.sha256(RAW_PROFILE.encode("utf-8")).hexdigest()
    assert payload["profile"]["name"] == "Cache Tester"

    second = profile.run(RAW_PROFILE)
    assert llm_spy.calls == 1  # served from cache, no second model call
    assert second == first


def test_changed_profile_misses_and_overwrites_cache(cache_path, llm_spy):
    profile.run(RAW_PROFILE)
    assert llm_spy.calls == 1

    changed = RAW_PROFILE + "\n- New project: distributed cache\n"
    profile.run(changed)
    assert llm_spy.calls == 2  # different text, real model call

    payload = json.loads(cache_path.read_text(encoding="utf-8"))
    assert payload["hash"] == hashlib.sha256(changed.encode("utf-8")).hexdigest()
    # The old profile no longer matches the single-slot cache.
    profile.run(RAW_PROFILE)
    assert llm_spy.calls == 3


@pytest.mark.parametrize(
    "corrupt",
    [
        "not json {",
        json.dumps(["wrong", "shape"]),
        json.dumps({"hash": "stale", "profile": {"name": "Old"}}),
        json.dumps({"profile": {"name": "No hash"}}),
    ],
)
def test_corrupt_or_stale_cache_falls_through_to_llm(cache_path, llm_spy, corrupt):
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(corrupt, encoding="utf-8")

    result = profile.run(RAW_PROFILE)
    assert llm_spy.calls == 1
    assert result["name"] == "Cache Tester"

    # The miss overwrote the bad payload; the next run is a clean hit.
    profile.run(RAW_PROFILE)
    assert llm_spy.calls == 1


def test_wrong_shape_cached_profile_is_a_miss(cache_path, llm_spy):
    profile_hash = hashlib.sha256(RAW_PROFILE.encode("utf-8")).hexdigest()
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps({"hash": profile_hash, "profile": "not a dict"}),
        encoding="utf-8",
    )

    profile.run(RAW_PROFILE)
    assert llm_spy.calls == 1


def test_env_escape_hatch_disables_read_and_write(cache_path, llm_spy, monkeypatch):
    monkeypatch.setenv("UPSEARCH_PROFILE_CACHE", "0")

    profile.run(RAW_PROFILE)
    profile.run(RAW_PROFILE)
    assert llm_spy.calls == 2  # every run hits the model
    assert not cache_path.exists()  # nothing written while disabled


def test_env_escape_hatch_ignores_existing_cache(cache_path, llm_spy, monkeypatch):
    profile.run(RAW_PROFILE)  # primes a valid cache while enabled
    assert llm_spy.calls == 1

    monkeypatch.setenv("UPSEARCH_PROFILE_CACHE", "0")
    profile.run(RAW_PROFILE)
    assert llm_spy.calls == 2  # valid cache present but not consulted


def test_cache_defaults_off_under_pytest_without_explicit_opt_in(
    cache_path, llm_spy, monkeypatch
):
    """Unset env under pytest means disabled: unrelated tests that stub
    llm.complete can never read or overwrite the operator's real cache."""
    monkeypatch.delenv("UPSEARCH_PROFILE_CACHE", raising=False)

    profile.run(RAW_PROFILE)
    profile.run(RAW_PROFILE)
    assert llm_spy.calls == 2
    assert not cache_path.exists()


def test_llm_failure_fallback_is_never_cached(cache_path, monkeypatch):
    spy = LLMSpy(fail=True)
    monkeypatch.setattr(profile.llm, "complete", spy)

    degraded = profile.run(RAW_PROFILE)
    assert spy.calls == 1
    assert degraded["name"] == "Cache Tester"  # deterministic fallback shape
    assert not cache_path.exists()  # degraded result must not mask recovery

    # Provider recovers: the next run makes a real call and caches it.
    spy.fail = False
    recovered = profile.run(RAW_PROFILE)
    assert spy.calls == 2
    assert cache_path.exists()
    assert "Built an inference benchmark" in recovered["proof_points"]

    profile.run(RAW_PROFILE)
    assert spy.calls == 2  # now served from cache


def test_unparseable_llm_output_is_never_cached(cache_path, monkeypatch):
    spy = LLMSpy(payload="this is not json")
    monkeypatch.setattr(profile.llm, "complete", spy)

    result = profile.run(RAW_PROFILE)
    assert spy.calls == 1
    assert result["name"] == "Cache Tester"  # fallback profile
    assert not cache_path.exists()


def test_cache_hit_still_merges_fresh_source_evidence(cache_path, llm_spy, monkeypatch):
    profile.run(RAW_PROFILE)
    assert llm_spy.calls == 1

    # New source-fetch evidence lands after the cache was written.
    monkeypatch.setattr(
        profile_source_fetch,
        "load_cached_report",
        lambda: {
            "profile_facts": {"github_url": "https://github.com/cache-tester"},
            "proof_candidates": ["Shipped a model server. Source: https://example.dev/post"],
            "sources": [],
        },
    )
    merged = profile.run(RAW_PROFILE)
    assert llm_spy.calls == 1  # still a cache hit — no model call
    assert merged["github_url"] == "https://github.com/cache-tester"
    assert any("Shipped a model server" in item for item in merged["proof_points"])
    # The cache file keeps the pre-merge extraction, not the merged view.
    payload = json.loads(cache_path.read_text(encoding="utf-8"))
    assert payload["profile"]["github_url"] == ""


def test_empty_profile_never_touches_cache_or_llm(cache_path, llm_spy):
    result = profile.run("   \n  ")
    assert llm_spy.calls == 0
    assert not cache_path.exists()
    assert result["name"] == "Student"
