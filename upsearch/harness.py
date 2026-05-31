"""Agent harness contracts.

The harness owns repeatability: typed inputs, typed outputs, validation, budget
metadata, and tracking. The model call is only one replaceable step.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Generic, TypeVar

from .model_router import ModelRoute, TaskType
from .schemas import AgentRunRecord
from .tracking import RunLogger


InputT = TypeVar("InputT")
OutputT = TypeVar("OutputT")


@dataclass(frozen=True)
class HarnessBudget:
    max_input_tokens: int | None = None
    max_output_tokens: int | None = None
    max_cost_usd: float | None = None
    max_source_count: int | None = None


@dataclass(frozen=True)
class HarnessContext:
    lane: str
    company: str | None = None
    run_id: str | None = None
    source_urls: list[str] = field(default_factory=list)
    artifact_paths: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class HarnessResult(Generic[OutputT]):
    output: OutputT
    route: ModelRoute
    validation_errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.validation_errors


Validator = Callable[[OutputT], list[str]]
Runner = Callable[[InputT, ModelRoute, HarnessContext], OutputT]


@dataclass(frozen=True)
class AgentHarness(Generic[InputT, OutputT]):
    name: str
    task_type: TaskType
    route: ModelRoute
    budget: HarnessBudget
    runner: Runner[InputT, OutputT]
    validators: list[Validator[OutputT]] = field(default_factory=list)

    def run(
        self,
        input_data: InputT,
        context: HarnessContext,
        logger: RunLogger | None = None,
    ) -> HarnessResult[OutputT]:
        output = self.runner(input_data, self.route, context)
        errors: list[str] = []
        for validator in self.validators:
            errors.extend(validator(output))

        result = HarnessResult(
            output=output,
            route=self.route,
            validation_errors=errors,
            metadata={
                "agent": self.name,
                "task_type": self.task_type.value,
                "budget": self.budget,
            },
        )

        if logger is not None:
            run_id = context.run_id or logger.new_run_id()
            logger.log_record(
                AgentRunRecord(
                    run_id=run_id,
                    agent=self.name,
                    run_type=self.task_type.value,
                    company=context.company,
                    lane=context.lane,
                    model_provider=self.route.provider,
                    model_name=self.route.model,
                    source_urls=context.source_urls,
                    artifact_paths=context.artifact_paths,
                )
            )
            logger.log_event(
                "harness_validation",
                {
                    "run_id": run_id,
                    "agent": self.name,
                    "ok": result.ok,
                    "errors": errors,
                },
            )

        return result


def require_non_empty_string(value_name: str) -> Validator[str]:
    def validate(value: str) -> list[str]:
        if not value.strip():
            return [f"{value_name} must not be empty."]
        return []

    return validate
