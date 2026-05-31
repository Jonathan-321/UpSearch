"""Run logging for local development and optional W&B tracking."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from .config import Settings
from .schemas import AgentRunRecord, utc_now_iso


def _json_default(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, Path):
        return str(value)
    return str(value)


class RunLogger:
    """Append-only execution ledger with optional W&B mirroring."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.settings.tracking_dir.mkdir(parents=True, exist_ok=True)
        self.events_path = self.settings.tracking_dir / "events.jsonl"
        self._wandb = None

        if (
            settings.has_wandb_key
            and settings.wandb_project
            and settings.wandb_mode != "disabled"
        ):
            try:
                import wandb  # type: ignore

                self._wandb = wandb
            except ImportError:
                self._wandb = None

    def new_run_id(self) -> str:
        return uuid.uuid4().hex[:12]

    def log_record(self, record: AgentRunRecord) -> None:
        self.log_event("agent_run", record.to_dict())

    def log_event(self, event_type: str, payload: dict[str, Any]) -> None:
        event = {
            "event_type": event_type,
            "timestamp": utc_now_iso(),
            "payload": payload,
        }
        with self.events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, default=_json_default) + "\n")

        if self._wandb is not None:
            run = self._wandb.init(
                project=self.settings.wandb_project,
                entity=self.settings.wandb_entity,
                mode=self.settings.wandb_mode,
                reinit=True,
            )
            run.log({"event_type": event_type, **payload})
            run.finish()
