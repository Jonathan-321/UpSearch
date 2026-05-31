"""Cost-aware model routing for agent tasks."""

from __future__ import annotations

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


class ModelRouter:
    """Pick a provider/model by task shape and configured keys."""

    def __init__(self, settings: Settings):
        self.settings = settings

    def route(self, task_type: TaskType) -> ModelRoute:
        if task_type in {
            TaskType.COMPANY_SOURCING,
            TaskType.PROBLEM_DISCOVERY,
            TaskType.PEOPLE_SOURCING,
            TaskType.OUTREACH_DRAFT,
            TaskType.PROFILE_INGEST,
        }:
            return ModelRoute(
                provider="deepseek",
                model=self.settings.deepseek_model,
                reason="Cheap/high-context route for broad research, extraction, and first-pass drafting.",
                requires_api_key=True,
                configured=self.settings.has_deepseek_key,
            )

        if task_type in {TaskType.TECHNICAL_NOTE, TaskType.VERIFICATION}:
            if self.settings.strong_model != "not-configured":
                return ModelRoute(
                    provider=self.settings.strong_model_provider,
                    model=self.settings.strong_model,
                    reason="Judgment-heavy route for final synthesis and claim QA.",
                    requires_api_key=self.settings.strong_model_provider not in {"manual-review", "local"},
                    configured=True,
                )
            # Fallback to cheap model when no strong model is configured
            return ModelRoute(
                provider="deepseek",
                model=self.settings.deepseek_model,
                reason="Fallback to cheap model for technical note and QA — strong model not configured.",
                requires_api_key=True,
                configured=self.settings.has_deepseek_key,
            )

        return ModelRoute(
            provider="deterministic",
            model="none",
            reason="No model call needed for tracking or state updates.",
        )

    def routes_for_phase_one(self) -> dict[str, ModelRoute]:
        return {task.value: self.route(task) for task in TaskType}
