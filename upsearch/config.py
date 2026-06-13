"""Runtime configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    """Configuration values for local and hosted UpSearch runs."""

    tracking_dir: Path
    wandb_project: str | None
    wandb_entity: str | None
    wandb_mode: str
    deepseek_model: str
    strong_model_provider: str
    strong_model: str
    coreweave_namespace: str | None
    coreweave_cluster: str | None
    cheap_model_provider: str = "deepseek"
    cheap_model: str = "deepseek-chat"

    @property
    def has_deepseek_key(self) -> bool:
        return bool(os.environ.get("DEEPSEEK_API_KEY"))

    @property
    def has_openrouter_key(self) -> bool:
        return bool(os.environ.get("OPENROUTER_API_KEY"))

    @property
    def has_wandb_key(self) -> bool:
        return bool(os.environ.get("WANDB_API_KEY"))

    @property
    def has_anthropic_key(self) -> bool:
        return bool(os.environ.get("ANTHROPIC_API_KEY"))

    @property
    def has_openai_key(self) -> bool:
        return bool(os.environ.get("OPENAI_API_KEY"))


def load_settings() -> Settings:
    """Load settings without exposing secret values."""

    deepseek_model = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
    cheap_model_provider = os.environ.get("UPSEARCH_CHEAP_MODEL_PROVIDER", "deepseek").lower()
    default_cheap_model = (
        "deepseek/deepseek-chat" if cheap_model_provider == "openrouter" else deepseek_model
    )
    return Settings(
        tracking_dir=Path(os.environ.get("UPSEARCH_TRACKING_DIR", ".upsearch/runs")),
        wandb_project=os.environ.get("WANDB_PROJECT"),
        wandb_entity=os.environ.get("WANDB_ENTITY"),
        wandb_mode=os.environ.get("WANDB_MODE", "disabled"),
        deepseek_model=deepseek_model,
        strong_model_provider=os.environ.get("UPSEARCH_STRONG_MODEL_PROVIDER", "manual-review"),
        strong_model=os.environ.get("UPSEARCH_STRONG_MODEL", "not-configured"),
        coreweave_namespace=os.environ.get("COREWEAVE_NAMESPACE"),
        coreweave_cluster=os.environ.get("COREWEAVE_CLUSTER"),
        cheap_model_provider=cheap_model_provider,
        cheap_model=os.environ.get("UPSEARCH_CHEAP_MODEL", default_cheap_model),
    )
