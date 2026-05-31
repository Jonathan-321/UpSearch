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

    @property
    def has_deepseek_key(self) -> bool:
        return bool(os.environ.get("DEEPSEEK_API_KEY"))

    @property
    def has_wandb_key(self) -> bool:
        return bool(os.environ.get("WANDB_API_KEY"))


def load_settings() -> Settings:
    """Load settings without exposing secret values."""

    return Settings(
        tracking_dir=Path(os.environ.get("UPSEARCH_TRACKING_DIR", ".upsearch/runs")),
        wandb_project=os.environ.get("WANDB_PROJECT"),
        wandb_entity=os.environ.get("WANDB_ENTITY"),
        wandb_mode=os.environ.get("WANDB_MODE", "disabled"),
        deepseek_model=os.environ.get("DEEPSEEK_MODEL", "deepseek-chat"),
        strong_model_provider=os.environ.get("UPSEARCH_STRONG_MODEL_PROVIDER", "manual-review"),
        strong_model=os.environ.get("UPSEARCH_STRONG_MODEL", "not-configured"),
        coreweave_namespace=os.environ.get("COREWEAVE_NAMESPACE"),
        coreweave_cluster=os.environ.get("COREWEAVE_CLUSTER"),
    )
