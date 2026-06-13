"""Cost-aware model routing for agent tasks."""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum

from .config import Settings


class TaskType(StrEnum):
    PROFILE_INGEST = "profile_ingest"
    COMPANY_SOURCING = "company_sourcing"
    PROBLEM_DISCOVERY = "problem_discovery"
    PEOPLE_SOURCING = "people_sourcing"
    TECHNICAL_NOTE = "technical_note"
    OUTREACH_DRAFT = "outreach_draft"
    VERIFICATION = "verification"
    TRACKING = "tracking"


@dataclass(frozen=True)
class ModelRoute:
    provider: str
    model: str
    reason: str
    requires_api_key: bool = False
    configured: bool = True
    """True when the selected route's API key is present. Still True on fallback to
    a cheap provider — see ``is_fallback`` to distinguish deliberate vs degraded routing."""

    is_fallback: bool = False
    """True when a task was routed to a cheaper provider because the preferred
    strong model was unavailable. Consumers MUST check this when reporting
    degraded-mode to avoid silently claiming strong-model verification."""



_PROVIDER_KEY_ENV = {
    "deepseek": "DEEPSEEK_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "claude": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
}
_KEYLESS_PROVIDERS = {"local", "manual-review", "deterministic"}


def provider_key_env(provider: str) -> str | None:
    """Name of the env var holding the API key for ``provider``, if it needs one."""
    return _PROVIDER_KEY_ENV.get(provider.lower())


def provider_configured(provider: str) -> bool:
    """True when ``provider`` needs no key or its key env var is set."""
    provider = provider.lower()
    if provider in _KEYLESS_PROVIDERS:
        return True
    key_env = provider_key_env(provider)
    return bool(key_env and os.environ.get(key_env))


class ModelRouter:
    """Pick a provider/model by task shape and configured keys."""

    def __init__(self, settings: Settings):
        self.settings = settings

    def _provider_configured(self, provider: str) -> bool:
        return provider_configured(provider)

    def route(self, task_type: TaskType) -> ModelRoute:
        if task_type in {
            TaskType.COMPANY_SOURCING,
            TaskType.PROBLEM_DISCOVERY,
            TaskType.PEOPLE_SOURCING,
            TaskType.OUTREACH_DRAFT,
            TaskType.PROFILE_INGEST,
        }:
            return ModelRoute(
                provider=self.settings.cheap_model_provider,
                model=self.settings.cheap_model,
                reason="Cheap/high-context route for broad research, extraction, and first-pass drafting.",
                requires_api_key=True,
                configured=self._provider_configured(self.settings.cheap_model_provider),
            )

        if task_type in {TaskType.TECHNICAL_NOTE, TaskType.VERIFICATION}:
            if self.settings.strong_model != "not-configured":
                configured = self._provider_configured(self.settings.strong_model_provider)
                return ModelRoute(
                    provider=self.settings.strong_model_provider,
                    model=self.settings.strong_model,
                    reason="Judgment-heavy route for final synthesis and claim QA.",
                    requires_api_key=self.settings.strong_model_provider not in {"manual-review", "local"},
                    configured=configured,
                    is_fallback=False,
                )
            # Fallback to cheap model when no strong model is configured
            return ModelRoute(
                provider=self.settings.cheap_model_provider,
                model=self.settings.cheap_model,
                reason="Fallback to cheap model for technical note and QA — strong model not configured.",
                requires_api_key=True,
                configured=self._provider_configured(self.settings.cheap_model_provider),
                is_fallback=True,
            )

        return ModelRoute(
            provider="deterministic",
            model="none",
            reason="No model call needed for tracking or state updates.",
        )

    def routes_for_phase_one(self) -> dict[str, ModelRoute]:
        return {task.value: self.route(task) for task in TaskType}
