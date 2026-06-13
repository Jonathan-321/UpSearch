"""Run logging for local development and optional W&B tracking.

Only structured metadata (route, model, latency, source count, verification
state, QA score, retries, final packet status) is accepted. Sensitive fields
such as prompt bodies, credentials, private profile text, outreach content,
email addresses, and recipient contact data are always stripped before logging.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field, is_dataclass
from pathlib import Path
from typing import Any

from .config import Settings
from .schemas import AgentRunRecord, utc_now_iso

# ── structured metadata keys ──────────────────────────────────────────────
ALLOWED_METADATA_KEYS: frozenset[str] = frozenset({
    "route",
    "model",
    "latency",
    "source_count",
    "verification_state",
    "qa_score",
    "retries",
    "final_packet_status",
})

SENSITIVE_KEY_PATTERNS: frozenset[str] = frozenset({
    "prompt",
    "body",
    "draft",
    "content",
    "profile",
    "credential",
    "api_key",
    "password",
    "secret",
    "token",
    "email",
    "contact",
    "recipient",
    "address",
    "phone",
})


def _is_sensitive_key(key: str) -> bool:
    """Return True if *key* looks like it carries sensitive data."""
    lower = key.lower().replace("_", "").replace("-", "")
    return any(pattern in lower for pattern in SENSITIVE_KEY_PATTERNS)


def _json_default(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, Path):
        return str(value)
    return str(value)


def sanitize_for_logging(payload: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of *payload* with sensitive keys removed.

    Only keys listed in ``ALLOWED_METADATA_KEYS`` are kept. All other keys
    are silently dropped to guarantee no prompt bodies, credentials, private
    profile text, outreach content, email addresses, or recipient contact
    data leaks into the log.
    """
    return {k: v for k, v in payload.items() if k in ALLOWED_METADATA_KEYS}


@dataclass(frozen=True)
class StructuredRunMetrics:
    """Safe structured metadata for a single pipeline run.

    Every field is optional so callers log only what they have.
    """

    route: str | None = None
    model: str | None = None
    latency: float | None = None
    source_count: int | None = None
    verification_state: str | None = None
    qa_score: float | None = None
    retries: int | None = None
    final_packet_status: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


class RunLogger:
    """Append-only execution ledger with optional W&B mirroring.

    *Local JSONL logging always works.*
    *W&B mirroring is optional and fails open.*
    """

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
        payload = sanitize_for_logging(record.to_dict())
        self.log_event("agent_run", payload)

    def log_metrics(self, metrics: StructuredRunMetrics) -> None:
        """Log structured run metrics locally and optionally to W&B.

        Only the safe fields in *metrics* are persisted. Any extra keys
        passed in a raw dict must go through :meth:`log_event` instead.
        """
        self.log_event("run_metrics", metrics.to_dict())

    def log_event(self, event_type: str, payload: dict[str, Any]) -> None:
        sanitized = sanitize_for_logging(payload)
        event = {
            "event_type": event_type,
            "timestamp": utc_now_iso(),
            "payload": sanitized,
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
            run.log({"event_type": event_type, **sanitized})
            run.finish()
