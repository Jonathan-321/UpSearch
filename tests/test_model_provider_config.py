"""Task 016: OpenRouter route and visible config validation."""

from dataclasses import replace
from unittest.mock import MagicMock

import pytest

from upsearch import llm
from upsearch.config import Settings, load_settings
from upsearch.model_router import ModelRouter, TaskType, provider_configured
from upsearch.startup_validation import enforce_model_config, model_config_problems


ALL_KEY_ENVS = (
    "DEEPSEEK_API_KEY",
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "OPENROUTER_API_KEY",
    "GITHUB_TOKEN",
)


def clear_keys(monkeypatch) -> None:
    for name in ALL_KEY_ENVS:
        monkeypatch.delenv(name, raising=False)


def settings(**overrides) -> Settings:
    base = Settings(
        tracking_dir=None,
        wandb_project=None,
        wandb_entity=None,
        wandb_mode="disabled",
        deepseek_model="deepseek-chat",
        strong_model_provider="manual-review",
        strong_model="not-configured",
        coreweave_namespace=None,
        coreweave_cluster=None,
    )
    return replace(base, **overrides)


def test_default_cheap_route_unchanged(monkeypatch) -> None:
    clear_keys(monkeypatch)
    route = ModelRouter(settings()).route(TaskType.PROFILE_INGEST)

    assert route.provider == "deepseek"
    assert route.model == "deepseek-chat"
    assert route.configured is False

    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    route = ModelRouter(settings()).route(TaskType.PROFILE_INGEST)
    assert route.configured is True


def test_openrouter_cheap_route_configured(monkeypatch) -> None:
    clear_keys(monkeypatch)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    router = ModelRouter(settings(
        cheap_model_provider="openrouter",
        cheap_model="deepseek/deepseek-chat",
    ))

    route = router.route(TaskType.COMPANY_SOURCING)

    assert route.provider == "openrouter"
    assert route.model == "deepseek/deepseek-chat"
    assert route.configured is True
    assert route.is_fallback is False


def test_strong_route_via_openrouter_is_not_degraded(monkeypatch) -> None:
    clear_keys(monkeypatch)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    router = ModelRouter(settings(
        strong_model_provider="openrouter",
        strong_model="deepseek/deepseek-r1",
    ))

    route = router.route(TaskType.VERIFICATION)

    assert route.provider == "openrouter"
    assert route.model == "deepseek/deepseek-r1"
    assert route.configured is True
    assert route.is_fallback is False


def test_load_settings_openrouter_cheap_defaults(monkeypatch) -> None:
    monkeypatch.setenv("UPSEARCH_CHEAP_MODEL_PROVIDER", "openrouter")
    monkeypatch.delenv("UPSEARCH_CHEAP_MODEL", raising=False)

    loaded = load_settings()

    assert loaded.cheap_model_provider == "openrouter"
    assert loaded.cheap_model == "deepseek/deepseek-chat"


def test_load_settings_defaults_preserve_deepseek(monkeypatch) -> None:
    monkeypatch.delenv("UPSEARCH_CHEAP_MODEL_PROVIDER", raising=False)
    monkeypatch.delenv("UPSEARCH_CHEAP_MODEL", raising=False)
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-chat")

    loaded = load_settings()

    assert loaded.cheap_model_provider == "deepseek"
    assert loaded.cheap_model == "deepseek-chat"


def test_llm_complete_routes_through_openrouter(monkeypatch) -> None:
    client = MagicMock()
    client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content="  openrouter reply  "))]
    )
    monkeypatch.setattr(llm, "PROVIDER", "openrouter")
    monkeypatch.setattr(llm, "OPENROUTER_MODEL", "deepseek/deepseek-chat")
    monkeypatch.setattr(llm, "_openrouter_client", lambda: client)

    result = llm.complete(system="sys", user="hello")

    assert result == "openrouter reply"
    assert client.chat.completions.create.call_args.kwargs["model"] == "deepseek/deepseek-chat"


def test_provider_configured_openrouter(monkeypatch) -> None:
    clear_keys(monkeypatch)
    assert provider_configured("openrouter") is False
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    assert provider_configured("openrouter") is True
    assert provider_configured("manual-review") is True
    assert provider_configured("unknown-provider") is False


def test_model_config_problems_reports_all_gaps(monkeypatch) -> None:
    clear_keys(monkeypatch)
    monkeypatch.setenv("MODEL_PROVIDER", "openrouter")

    problems = model_config_problems(settings())

    assert any("OPENROUTER_API_KEY" in problem for problem in problems)
    assert any("no packet can be approved" in problem for problem in problems)
    assert any("GITHUB_TOKEN" in problem for problem in problems)


def test_model_config_problems_empty_when_healthy(monkeypatch) -> None:
    clear_keys(monkeypatch)
    monkeypatch.setenv("MODEL_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")

    problems = model_config_problems(settings(
        strong_model_provider="openrouter",
        strong_model="deepseek/deepseek-r1",
    ))

    assert problems == []


def test_model_config_problems_flags_strong_key_missing(monkeypatch) -> None:
    clear_keys(monkeypatch)
    monkeypatch.setenv("MODEL_PROVIDER", "deepseek")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")

    problems = model_config_problems(settings(
        strong_model_provider="anthropic",
        strong_model="claude-opus-4-8",
    ))

    assert len(problems) == 1
    assert "ANTHROPIC_API_KEY" in problems[0]


def test_enforce_model_config_only_raises_when_required(monkeypatch) -> None:
    problems = ["Strong QA model is not configured"]

    monkeypatch.delenv("UPSEARCH_REQUIRE_MODELS", raising=False)
    enforce_model_config(problems)

    monkeypatch.setenv("UPSEARCH_REQUIRE_MODELS", "1")
    with pytest.raises(RuntimeError, match="Strong QA model"):
        enforce_model_config(problems)
    enforce_model_config([])
