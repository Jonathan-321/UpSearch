"""Tests for safe run tracking with local JSONL + optional W&B mirroring.

These tests require no network and no credentials. W&B is always faked or
disabled so every test is hermetic.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from upsearch.config import Settings, load_settings
from upsearch.schemas import AgentRunRecord
from upsearch.tracking import (
    ALLOWED_METADATA_KEYS,
    RunLogger,
    StructuredRunMetrics,
    sanitize_for_logging,
)


# ── fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def tmp_tracking_dir(tmp_path: Path) -> Path:
    """Return a clean temporary directory for tracking artifacts."""
    p = tmp_path / "upsearch_runs"
    p.mkdir(parents=True, exist_ok=True)
    return p


@pytest.fixture
def offline_settings(tmp_tracking_dir: Path) -> Settings:
    """Settings with W&B disabled and no API key set."""
    return Settings(
        tracking_dir=tmp_tracking_dir,
        wandb_project=None,
        wandb_entity=None,
        wandb_mode="disabled",
        deepseek_model="deepseek-chat",
        strong_model_provider="manual-review",
        strong_model="not-configured",
        coreweave_namespace=None,
        coreweave_cluster=None,
    )


@pytest.fixture
def logger(offline_settings: Settings) -> RunLogger:
    """A RunLogger that logs locally only (W&B disabled)."""
    return RunLogger(offline_settings)


@pytest.fixture
def full_metrics() -> StructuredRunMetrics:
    """Return a metrics object with every field set."""
    return StructuredRunMetrics(
        route="company",
        model="gpt-4",
        latency=2.34,
        source_count=12,
        verification_state="verified",
        qa_score=0.92,
        retries=1,
        final_packet_status="approved",
    )


# ── sanitize_for_logging ─────────────────────────────────────────────────────


class TestSanitizeForLogging:
    def test_allows_all_metadata_keys(self) -> None:
        payload = {k: f"val_{k}" for k in ALLOWED_METADATA_KEYS}
        result = sanitize_for_logging(payload)
        assert result == payload

    def test_drops_non_allowed_keys(self) -> None:
        payload = {"route": "company", "prompt": "secret", "email": "a@b.com"}
        result = sanitize_for_logging(payload)
        assert result == {"route": "company"}
        assert "prompt" not in result
        assert "email" not in result

    def test_drops_sensitive_key_patterns(self) -> None:
        payload = {
            "route": "people",
            "profile_text": "private info",
            "outreach_body": "hello",
            "api_key": "sk-xxx",
        }
        result = sanitize_for_logging(payload)
        assert result == {"route": "people"}

    def test_handles_empty_payload(self) -> None:
        assert sanitize_for_logging({}) == {}

    def test_handles_none_values(self) -> None:
        payload = {"route": None, "latency": None}
        result = sanitize_for_logging(payload)
        assert result == {"route": None, "latency": None}


# ── local JSONL logging ──────────────────────────────────────────────────────


class TestLocalJsonlLogging:
    def test_log_metrics_writes_jsonl(self, logger: RunLogger, full_metrics: StructuredRunMetrics) -> None:
        logger.log_metrics(full_metrics)
        lines = logger.events_path.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 1
        event = json.loads(lines[0])
        assert event["event_type"] == "run_metrics"
        assert "timestamp" in event
        for key in ALLOWED_METADATA_KEYS:
            assert event["payload"][key] == getattr(full_metrics, key)

    def test_log_metrics_appends_multiple_events(self, logger: RunLogger) -> None:
        logger.log_metrics(StructuredRunMetrics(route="company"))
        logger.log_metrics(StructuredRunMetrics(route="people"))
        lines = logger.events_path.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 2
        assert json.loads(lines[0])["payload"]["route"] == "company"
        assert json.loads(lines[1])["payload"]["route"] == "people"

    def test_log_record_strips_non_allowed_fields(self, logger: RunLogger) -> None:
        record = AgentRunRecord(
            run_id="abc123",
            agent="company_agent",
            run_type="full",
            source_urls=["https://example.com"],
        )
        logger.log_record(record)
        lines = logger.events_path.read_text(encoding="utf-8").strip().split("\n")
        event = json.loads(lines[0])
        # Allowed keys are not in AgentRunRecord fields, so payload should be empty
        assert event["event_type"] == "agent_run"
        # The allowed keys don't overlap with AgentRunRecord fields, so payload is empty
        for key in ALLOWED_METADATA_KEYS:
            assert key not in event["payload"]

    def test_jsonl_writes_have_correct_structure(self, logger: RunLogger) -> None:
        logger.log_metrics(StructuredRunMetrics(route="test"))
        event = json.loads(logger.events_path.read_text(encoding="utf-8"))
        assert set(event.keys()) == {"event_type", "timestamp", "payload"}
        assert isinstance(event["timestamp"], str)
        assert isinstance(event["payload"], dict)

    def test_jsonl_always_writes_even_without_wandb(self, tmp_tracking_dir: Path) -> None:
        """Local logging works even when wandb is not installed."""
        settings = Settings(
            tracking_dir=tmp_tracking_dir,
            wandb_project="myproject",
            wandb_entity=None,
            wandb_mode="online",
            deepseek_model="deepseek-chat",
            strong_model_provider="manual-review",
            strong_model="not-configured",
            coreweave_namespace=None,
            coreweave_cluster=None,
        )
        # Unset the W&B key so has_wandb_key is False
        old_key = os.environ.pop("WANDB_API_KEY", None)
        try:
            log = RunLogger(settings)
            log.log_metrics(StructuredRunMetrics(route="no-wandb"))
            assert log.events_path.exists()
        finally:
            if old_key is not None:
                os.environ["WANDB_API_KEY"] = old_key


# ── optional W&B ─────────────────────────────────────────────────────────────


class TestOptionalWandB:
    def test_no_wandb_key_fails_open(self, tmp_tracking_dir: Path) -> None:
        """No crash when WANDB_API_KEY is unset and wandb_project is set."""
        settings = Settings(
            tracking_dir=tmp_tracking_dir,
            wandb_project="test-project",
            wandb_entity=None,
            wandb_mode="online",
            deepseek_model="deepseek-chat",
            strong_model_provider="manual-review",
            strong_model="not-configured",
            coreweave_namespace=None,
            coreweave_cluster=None,
        )
        old_key = os.environ.pop("WANDB_API_KEY", None)
        try:
            log = RunLogger(settings)  # should not crash
            log.log_metrics(StructuredRunMetrics(route="safe"))
            line = json.loads(log.events_path.read_text(encoding="utf-8"))
            assert line["payload"]["route"] == "safe"
        finally:
            if old_key is not None:
                os.environ["WANDB_API_KEY"] = old_key

    def test_disabled_mode_fails_open(self, tmp_tracking_dir: Path) -> None:
        """W&B mode 'disabled' skips W&B even with key set."""
        settings = Settings(
            tracking_dir=tmp_tracking_dir,
            wandb_project="test-project",
            wandb_entity=None,
            wandb_mode="disabled",
            deepseek_model="deepseek-chat",
            strong_model_provider="manual-review",
            strong_model="not-configured",
            coreweave_namespace=None,
            coreweave_cluster=None,
        )
        log = RunLogger(settings)
        assert log._wandb is None  # noqa: SLF001

    def test_wandb_import_error_fails_open(self, tmp_tracking_dir: Path) -> None:
        """RunLogger doesn't crash when wandb import fails."""
        settings = Settings(
            tracking_dir=tmp_tracking_dir,
            wandb_project="test-project",
            wandb_entity="test-entity",
            wandb_mode="online",
            deepseek_model="deepseek-chat",
            strong_model_provider="manual-review",
            strong_model="not-configured",
            coreweave_namespace=None,
            coreweave_cluster=None,
        )
        old_key = os.environ.pop("WANDB_API_KEY", None)
        if old_key is None:
            os.environ["WANDB_API_KEY"] = "mock-key"
        try:
            log = RunLogger(settings)
            assert log._wandb is None  # noqa: SLF001 — wandb not installed, fails open
        finally:
            if old_key is None:
                del os.environ["WANDB_API_KEY"]
            else:
                os.environ["WANDB_API_KEY"] = old_key


# ── StructuredRunMetrics ─────────────────────────────────────────────────────


class TestStructuredRunMetrics:
    def test_to_dict_omits_none(self) -> None:
        metrics = StructuredRunMetrics(route="test", latency=None)
        assert metrics.to_dict() == {"route": "test"}

    def test_to_dict_includes_all_set_fields(self, full_metrics: StructuredRunMetrics) -> None:
        d = full_metrics.to_dict()
        assert set(d.keys()) == ALLOWED_METADATA_KEYS

    def test_empty_metrics_produces_empty_dict(self) -> None:
        assert StructuredRunMetrics().to_dict() == {}


# ── edge cases ────────────────────────────────────────────────────────────────


class TestEdgeCases:
    def test_log_with_invalid_type_does_not_crash(self, logger: RunLogger) -> None:
        logger.log_metrics(StructuredRunMetrics(latency=float("inf")))
        event = json.loads(logger.events_path.read_text(encoding="utf-8"))
        assert event["event_type"] == "run_metrics"

    def test_concurrent_logging_does_not_corrupt(self, logger: RunLogger) -> None:
        import threading

        errors: list[Exception] = []

        def log_route(route: str) -> None:
            try:
                logger.log_metrics(StructuredRunMetrics(route=route))
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=log_route, args=(f"route-{i}",)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        lines = logger.events_path.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 10
