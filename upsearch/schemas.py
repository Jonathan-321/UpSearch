"""Core state models for opportunity packets and agent runs."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ExternalAction(StrEnum):
    NONE = "none"
    DRAFT_CREATED = "draft_created"
    SENT = "sent"
    SCHEDULED = "scheduled"


class OutreachChannel(StrEnum):
    LINKEDIN_CONNECTION = "linkedin_connection"
    LINKEDIN_MESSAGE = "linkedin_message"
    EMAIL = "email"
    X_DM = "x_dm"


class SourceType(StrEnum):
    COMPANY_BLOG = "company_blog"
    CAREERS = "careers"
    DOCS = "docs"
    LINKEDIN = "linkedin"
    PAPER = "paper"
    GITHUB = "github"
    LOCAL_ARTIFACT = "local_artifact"
    OTHER = "other"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class Source:
    url: str
    title: str
    source_type: SourceType = SourceType.OTHER
    notes: str = ""


@dataclass(frozen=True)
class Company:
    name: str
    lane: str
    website: str
    careers_url: str | None = None
    fit_score: float | None = None
    sponsorship_signal: str = "unknown"
    sources: list[Source] = field(default_factory=list)


@dataclass(frozen=True)
class Problem:
    company_name: str
    title: str
    summary: str
    buildable_angle: str
    success_criteria: list[str] = field(default_factory=list)
    sources: list[Source] = field(default_factory=list)


@dataclass(frozen=True)
class Person:
    name: str
    company_name: str
    role: str
    relevance_reason: str
    best_channel: OutreachChannel
    profile_urls: list[str] = field(default_factory=list)
    sources: list[Source] = field(default_factory=list)


@dataclass(frozen=True)
class TechnicalNote:
    title: str
    company_name: str
    problem_title: str
    body_markdown: str
    artifact_paths: list[str] = field(default_factory=list)
    sources: list[Source] = field(default_factory=list)


@dataclass(frozen=True)
class OutreachDraft:
    person_name: str
    company_name: str
    channel: OutreachChannel
    body: str
    subject: str | None = None
    approval_status: ApprovalStatus = ApprovalStatus.PENDING
    external_action: ExternalAction = ExternalAction.NONE
    follow_up_days: int | None = None

    @property
    def word_count(self) -> int:
        return len([word for word in self.body.split() if word.strip()])


@dataclass(frozen=True)
class OpportunityPacket:
    lane: str
    company: Company
    problem: Problem
    people: list[Person]
    technical_note: TechnicalNote
    outreach_drafts: list[OutreachDraft]
    approval_required: bool = True
    created_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    def write_json(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json() + "\n", encoding="utf-8")


@dataclass(frozen=True)
class AgentRunRecord:
    run_id: str
    agent: str
    run_type: str
    company: str | None = None
    lane: str | None = None
    model_provider: str | None = None
    model_name: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    estimated_cost_usd: float | None = None
    source_urls: list[str] = field(default_factory=list)
    artifact_paths: list[str] = field(default_factory=list)
    approval_status: ApprovalStatus = ApprovalStatus.PENDING
    external_action: ExternalAction = ExternalAction.NONE
    created_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
