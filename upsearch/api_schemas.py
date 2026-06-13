"""Pydantic models for typed API responses — run state, trace, QA, approval, handoff readiness.

These models formalize the contract between server and UI so the frontend
can render explicit backend states instead of inferring them from event counts.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


# ── Run state ───────────────────────────────────────────────────────────────────


class RunRecordOut(BaseModel):
    """Typed representation of a run record for API responses."""

    run_id: str
    company_name: str
    lane: str
    status: str  # running | complete | failed | cancelled
    started_at: str | None = None
    completed_at: str | None = None
    current_step: str | None = None
    steps_completed: list[str] = Field(default_factory=list)
    qa_score: float | None = None
    final_status: str | None = None  # prepared | needs_review
    error_message: str | None = None
    created_at: str | None = None

    @classmethod
    def from_db(cls, record: dict[str, Any] | None) -> RunRecordOut | None:
        if record is None:
            return None
        steps = record.get("steps_completed", [])
        if isinstance(steps, str):
            import json
            try:
                steps = json.loads(steps)
            except (json.JSONDecodeError, TypeError):
                steps = []
        return cls(
            run_id=record.get("run_id", ""),
            company_name=record.get("company_name", ""),
            lane=record.get("lane", ""),
            status=record.get("status", "running"),
            started_at=record.get("started_at"),
            completed_at=record.get("completed_at"),
            current_step=record.get("current_step"),
            steps_completed=steps,
            qa_score=_safe_float(record.get("qa_score")),
            final_status=record.get("final_status"),
            error_message=record.get("error_message"),
            created_at=record.get("created_at"),
        )


# ── Trace ──────────────────────────────────────────────────────────────────────


class TraceEventOut(BaseModel):
    """Typed trace event for API responses and SSE progress events."""

    event_type: str
    status: str = "ok"
    timestamp: str = ""
    agent: str | None = None
    agent_role: str | None = None
    role: str | None = None
    reads: list[str] = Field(default_factory=list)
    writes: list[str] = Field(default_factory=list)
    output_summary: str | None = None
    latency_ms: int | None = None
    from_agent: str | None = None
    to_agent: str | None = None
    payload_keys: list[str] = Field(default_factory=list)
    reason: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class TraceSummaryOut(BaseModel):
    """Summary of a run's trace for list views."""

    run_id: str
    event_count: int = 0
    agent_step_count: int = 0
    handoff_count: int = 0
    missing_agents: list[str] = Field(default_factory=list)
    has_errors: bool = False


class TraceHealthOut(BaseModel):
    events: list[TraceEventOut] = Field(default_factory=list)
    agent_steps: int = 0
    handoffs: int = 0
    missing_agents: list[str] = Field(default_factory=list)
    has_errors: bool = False


# ── Checkup ────────────────────────────────────────────────────────────────────


class CheckupMetricOut(BaseModel):
    name: str
    score: float
    detail: str = ""


class CheckupFactsOut(BaseModel):
    problem_source_urls: list[str] = Field(default_factory=list)
    problem_source_candidates: int | None = None
    unverified_model_sources: bool = False
    verified_people: int = 0
    qa_flags: list[str] = Field(default_factory=list)
    over_200_drafts: list[str] = Field(default_factory=list)
    note_words: int = 0


class CheckupOut(BaseModel):
    """Typed checkup response matching evaluate_packet output."""

    company: str
    status: str  # passed | needs_review | failed
    overall_score: float
    failure_category: str
    trace_status: str = "unavailable"  # unavailable | incomplete | complete
    suggested_fix: str = ""
    metrics: list[CheckupMetricOut] = Field(default_factory=list)
    facts: CheckupFactsOut = Field(default_factory=CheckupFactsOut)
    trace: TraceHealthOut = Field(default_factory=TraceHealthOut)
    source_methods: dict[str, Any] = Field(default_factory=dict)
    artifact_paths: dict[str, str] = Field(default_factory=dict)
    created_at: str = ""


# ── QA ─────────────────────────────────────────────────────────────────────────


class QAModelRouteOut(BaseModel):
    """Model routing record attached to a QA result.

    Mirrors the ``model_route`` block emitted by ``agents.qa`` so the UI can
    surface degraded verification instead of presenting every score as
    strong-model checked.
    """

    provider: str | None = None
    model: str | None = None
    configured: bool = False
    is_fallback: bool = False
    degraded_mode: bool = False
    reason: str | None = None


class QAResultOut(BaseModel):
    """Typed QA result for API responses."""

    score: float
    passed: bool
    flags: list[str] = Field(default_factory=list)
    reasoning: str | None = None
    model_route: QAModelRouteOut | None = None


# ── Approval state ──────────────────────────────────────────────────────────────


class ApprovalOut(BaseModel):
    """Typed approval record."""

    id: int | None = None
    message_id: int | None = None
    approved_at: str | None = None
    channel: str | None = None
    target: str | None = None
    notes: str | None = None


class DeliveryUpdateIn(BaseModel):
    status: Literal["prepared", "opened", "sent", "delivered", "failed", "unknown"]
    channel: str | None = None
    error_message: str | None = None


class DeliveryEventOut(BaseModel):
    id: int
    message_id: int
    approval_id: int
    status: str
    channel: str | None = None
    body_digest: str | None = None
    sent_at: str | None = None
    error_message: str | None = None
    stale: bool = False


class FollowUpCreateIn(BaseModel):
    due_date: date
    notes: str = ""


class FollowUpUpdateIn(BaseModel):
    status: Literal["pending", "completed", "skipped"]
    notes: str = ""


class FollowUpOut(BaseModel):
    id: int
    message_id: int
    approval_id: int | None = None
    body_digest: str | None = None
    due_date: str
    status: str
    notes: str = ""
    created_at: str | None = None
    stale: bool = False


class MessageReviewOut(BaseModel):
    id: int
    packet_id: int | None = None
    person_id: int | None = None
    company_name: str | None = None
    variant: str = ""
    content: str = ""
    word_count: int = 0
    status: str = "draft"
    person_name: str | None = None
    person_role: str | None = None
    linkedin_url: str | None = None
    github_url: str | None = None
    twitter_url: str | None = None
    source_url: str | None = None
    problem_title: str | None = None
    problem_source_urls: list[str] = Field(default_factory=list)
    qa_score: float | None = None
    qa_flags: list[str] = Field(default_factory=list)
    crm_status: str | None = None
    channel: str | None = None
    platform: str | None = None
    platform_label: str | None = None
    platform_url: str | None = None
    handoff_mode: str | None = None
    approval_contract: str | None = None
    actionable: bool = False
    review_actionable: bool = False
    safety_reasons: list[str] = Field(default_factory=list)
    approval_id: int | None = None
    approved_at: str | None = None
    approval_current: bool = False
    state_stale: bool = False
    body_digest: str = ""
    delivery_status: str | None = None
    delivery_error: str | None = None
    delivery_updated_at: str | None = None
    safe_retry: bool = False
    follow_up_id: int | None = None
    follow_up_status: str | None = None
    follow_up_due_date: str | None = None
    follow_up_notes: str | None = None


# ── Handoff readiness ───────────────────────────────────────────────────────────


class HandoffReadinessOut(BaseModel):
    """Whether a message is ready for external platform handoff."""

    message_id: int
    actionable: bool = False
    safety_reasons: list[str] = Field(default_factory=list)
    platform: str | None = None
    platform_label: str | None = None
    platform_url: str | None = None
    handoff_mode: str | None = None
    approval_contract: str | None = None


# ── Full packet response ───────────────────────────────────────────────────────


class PacketDetailOut(BaseModel):
    """Full typed packet response combining company, packet, problems, people, checkup."""

    company: dict[str, Any] = Field(default_factory=dict)
    packet: dict[str, Any] | None = None
    problems: list[dict[str, Any]] = Field(default_factory=list)
    people: list[dict[str, Any]] = Field(default_factory=list)
    checkup: CheckupOut | None = None
    run: RunRecordOut | None = None
    trace_status: Literal["unavailable", "incomplete", "complete"] = "unavailable"
    trace: list[TraceEventOut] = Field(default_factory=list)
    qa: QAResultOut | None = None
    approval_state: Literal["unavailable", "required", "partially_approved", "approved"] = "unavailable"
    handoff_readiness: list[HandoffReadinessOut] = Field(default_factory=list)


class RunStateOut(BaseModel):
    run: RunRecordOut
    trace_status: Literal["unavailable", "incomplete", "complete"]
    trace: list[TraceEventOut] = Field(default_factory=list)
    qa: QAResultOut | None = None
    approval_state: Literal["unavailable", "required", "partially_approved", "approved"] = "unavailable"
    handoff_readiness: list[HandoffReadinessOut] = Field(default_factory=list)


# ── Helpers ─────────────────────────────────────────────────────────────────────


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
