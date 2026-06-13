"""Tests for retry/backoff and client caching in ``upsearch.model_execution``.

All provider SDK clients are mocked; no real network calls are made. Retry
delays are forced to 0 via the documented env vars so the suite stays fast.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from upsearch import model_execution
from upsearch.model_router import ModelRoute


@pytest.fixture(autouse=True)
def _fast_retries(monkeypatch):
    # No sleeping in tests; keep the default attempt count (3).
    monkeypatch.setenv("MODEL_RETRY_BASE_DELAY", "0")
    monkeypatch.setenv("MODEL_RETRY_MAX_DELAY", "0")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    model_execution._reset_clients()
    yield
    model_execution._reset_clients()


class _HTTPError(Exception):
    """Transient-looking error carrying an HTTP status code."""

    def __init__(self, status_code: int):
        super().__init__(f"http {status_code}")
        self.status_code = status_code


def _openai_response(text: str) -> SimpleNamespace:
    message = SimpleNamespace(content=text)
    choice = SimpleNamespace(message=message)
    return SimpleNamespace(choices=[choice])


def _route(provider: str = "openai", model: str = "gpt-4o-mini") -> ModelRoute:
    return ModelRoute(provider=provider, model=model, reason="test", configured=True)


# --- classification ---------------------------------------------------------


@pytest.mark.parametrize("code", [429, 408, 500, 502, 503])
def test_status_codes_retryable(code):
    assert model_execution._is_retryable(_HTTPError(code)) is True


@pytest.mark.parametrize("code", [400, 401, 403, 404, 422])
def test_status_codes_not_retryable(code):
    assert model_execution._is_retryable(_HTTPError(code)) is False


def test_connection_error_retryable():
    assert model_execution._is_retryable(ConnectionError("boom")) is True
    assert model_execution._is_retryable(TimeoutError("slow")) is True


# --- retry behavior ---------------------------------------------------------


def test_transient_error_is_retried_then_succeeds():
    create = MagicMock(side_effect=[_HTTPError(429), _openai_response("  hi  ")])
    client = MagicMock()
    client.chat.completions.create = create

    with patch("openai.OpenAI", return_value=client) as factory:
        result = model_execution.complete_for_route(
            _route(), system="s", user="u"
        )

    assert result == "hi"
    assert create.call_count == 2
    # Client built once (and cached).
    assert factory.call_count == 1


def test_retries_exhausted_raises_final_error():
    create = MagicMock(side_effect=_HTTPError(503))
    client = MagicMock()
    client.chat.completions.create = create

    with patch("openai.OpenAI", return_value=client):
        with pytest.raises(_HTTPError) as excinfo:
            model_execution.complete_for_route(_route(), system="s", user="u")

    assert excinfo.value.status_code == 503
    assert create.call_count == model_execution._max_attempts() == 3


def test_auth_error_not_retried():
    create = MagicMock(side_effect=_HTTPError(401))
    client = MagicMock()
    client.chat.completions.create = create

    with patch("openai.OpenAI", return_value=client):
        with pytest.raises(_HTTPError) as excinfo:
            model_execution.complete_for_route(_route(), system="s", user="u")

    assert excinfo.value.status_code == 401
    assert create.call_count == 1  # surfaced immediately


def test_happy_path_returns_stripped_content():
    create = MagicMock(return_value=_openai_response("\n  result text \n"))
    client = MagicMock()
    client.chat.completions.create = create

    with patch("openai.OpenAI", return_value=client):
        result = model_execution.complete_for_route(_route(), system="s", user="u")

    assert result == "result text"
    assert create.call_count == 1


# --- caching & timeout ------------------------------------------------------


def test_client_is_cached_across_calls():
    create = MagicMock(side_effect=[_openai_response("a"), _openai_response("b")])
    client = MagicMock()
    client.chat.completions.create = create

    with patch("openai.OpenAI", return_value=client) as factory:
        model_execution.complete_for_route(_route(), system="s", user="u")
        model_execution.complete_for_route(_route(), system="s", user="u")

    assert factory.call_count == 1
    assert create.call_count == 2


def test_request_timeout_passed_to_client(monkeypatch):
    monkeypatch.setenv("MODEL_REQUEST_TIMEOUT", "12.5")
    create = MagicMock(return_value=_openai_response("ok"))
    client = MagicMock()
    client.chat.completions.create = create

    with patch("openai.OpenAI", return_value=client) as factory:
        model_execution.complete_for_route(_route(), system="s", user="u")

    _, kwargs = factory.call_args
    assert kwargs["timeout"] == 12.5
    assert kwargs["max_retries"] == 0


# --- provider coverage ------------------------------------------------------


def test_deepseek_model_validation_falls_back(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_MODEL", "totally-made-up")
    create = MagicMock(return_value=_openai_response("ds"))
    client = MagicMock()
    client.chat.completions.create = create

    with patch("openai.OpenAI", return_value=client):
        result = model_execution.complete_for_route(
            _route(provider="deepseek", model="deepseek-chat"),
            system="s",
            user="u",
        )

    assert result == "ds"
    _, kwargs = create.call_args
    assert kwargs["model"] == "deepseek-chat"


def test_anthropic_provider_retries_and_returns_text():
    block = SimpleNamespace(text="  claude says hi  ")
    response = SimpleNamespace(content=[block])
    create = MagicMock(side_effect=[_HTTPError(500), response])
    client = MagicMock()
    client.messages.create = create

    fake_anthropic = MagicMock()
    fake_anthropic.Anthropic.return_value = client

    with patch.dict("sys.modules", {"anthropic": fake_anthropic}):
        result = model_execution.complete_for_route(
            _route(provider="anthropic", model="claude-3-5-sonnet"),
            system="s",
            user="u",
        )

    assert result == "claude says hi"
    assert create.call_count == 2


def test_unconfigured_route_raises():
    route = ModelRoute(provider="openai", model="gpt", reason="x", configured=False)
    with pytest.raises(RuntimeError, match="not configured"):
        model_execution.complete_for_route(route, system="s", user="u")


def test_unsupported_provider_raises():
    route = _route(provider="weirdprovider")
    with pytest.raises(RuntimeError, match="Unsupported model provider"):
        model_execution.complete_for_route(route, system="s", user="u")
