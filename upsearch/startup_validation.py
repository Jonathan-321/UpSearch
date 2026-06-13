"""Operator-visible validation of model configuration.

The pipeline degrades deliberately when models are unconfigured: agents fall
back to keyword heuristics and QA fails closed, blocking approval. That safety
behavior is correct, but it must never be silent. This module turns the
degraded states into explicit startup problems an operator can act on.
"""

from __future__ import annotations

import os

from .config import Settings
from .model_router import provider_configured, provider_key_env


def active_agent_provider() -> str:
    """Provider the agent layer (upsearch.llm) will use for completions."""
    return os.environ.get("MODEL_PROVIDER", "claude").lower()


def model_config_problems(settings: Settings) -> list[str]:
    """Return operator-readable configuration problems, empty when healthy."""
    problems: list[str] = []

    agent_provider = active_agent_provider()
    if not provider_configured(agent_provider):
        key_env = provider_key_env(agent_provider) or "an API key"
        problems.append(
            f"Agent model provider '{agent_provider}' (MODEL_PROVIDER) is missing {key_env}; "
            "profile, company, problem, people, and outreach agents will silently fall back "
            "to keyword heuristics."
        )

    if (
        settings.strong_model == "not-configured"
        or settings.strong_model_provider == "manual-review"
    ):
        problems.append(
            "Strong QA model is not configured (UPSEARCH_STRONG_MODEL_PROVIDER / "
            "UPSEARCH_STRONG_MODEL); QA fails closed and no packet can be approved."
        )
    elif not provider_configured(settings.strong_model_provider):
        key_env = provider_key_env(settings.strong_model_provider) or "an API key"
        problems.append(
            f"Strong QA provider '{settings.strong_model_provider}' is missing {key_env}; "
            "QA runs degraded and packets cannot be approved."
        )

    if not os.environ.get("GITHUB_TOKEN"):
        problems.append(
            "GITHUB_TOKEN is not set; people sourcing is limited to 60 GitHub requests/hour "
            "and will rate-limit mid-run."
        )

    return problems


def enforce_model_config(problems: list[str]) -> None:
    """Fail startup when problems exist and UPSEARCH_REQUIRE_MODELS is set."""
    if problems and os.environ.get("UPSEARCH_REQUIRE_MODELS"):
        raise RuntimeError(
            "Model configuration problems (UPSEARCH_REQUIRE_MODELS is set):\n- "
            + "\n- ".join(problems)
        )
