"""Provider-agnostic connector and approval contracts.

Connectors are replaceable execution surfaces. The orchestrator should decide
what action is allowed; a connector should only expose what it can do.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import StrEnum

from .schemas import ApprovalStatus, ExternalAction, OutreachChannel


def body_digest(content: str) -> str:
    """Return a SHA-256 hex digest of message content for approval binding."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


class ConnectorKind(StrEnum):
    CODEX_BROWSER = "codex_browser"
    TANDEM_BROWSER = "tandem_browser"
    CHROME = "chrome"
    GMAIL_API = "gmail_api"
    GOOGLE_DRIVE_API = "google_drive_api"
    LINKEDIN_BROWSER = "linkedin_browser"
    MANUAL = "manual"


class ConnectorCapability(StrEnum):
    READ_PAGE = "read_page"
    NAVIGATE = "navigate"
    CREATE_DRAFT = "create_draft"
    SEND_MESSAGE = "send_message"
    SCHEDULE_SEND = "schedule_send"
    UPLOAD_FILE = "upload_file"
    CREATE_DOCUMENT = "create_document"
    READ_DOCUMENT = "read_document"
    WRITE_DOCUMENT = "write_document"


class ActionRisk(StrEnum):
    READ_ONLY = "read_only"
    LOCAL_WRITE = "local_write"
    CLOUD_WRITE = "cloud_write"
    EXTERNAL_SEND = "external_send"
    SCHEDULED_EXTERNAL_SEND = "scheduled_external_send"


@dataclass(frozen=True)
class ConnectorProfile:
    name: str
    kind: ConnectorKind
    capabilities: set[ConnectorCapability]
    authenticated: bool = False
    notes: str = ""

    def supports(self, capability: ConnectorCapability) -> bool:
        return capability in self.capabilities


@dataclass(frozen=True)
class ActionIntent:
    action_type: ExternalAction
    risk: ActionRisk
    channel: OutreachChannel | None = None
    target: str | None = None
    subject: str | None = None
    body: str | None = None
    artifact_paths: list[str] = field(default_factory=list)
    scheduled_for: str | None = None


@dataclass(frozen=True)
class ApprovalDecision:
    status: ApprovalStatus
    approver: str | None = None
    approved_action: ActionIntent | None = None
    notes: str = ""


class ApprovalGate:
    """Block risky actions unless the exact action has approval."""

    def validate(self, intent: ActionIntent, decision: ApprovalDecision | None,
                 decision_digest: str | None = None) -> None:
        if intent.risk in {ActionRisk.READ_ONLY, ActionRisk.LOCAL_WRITE}:
            return

        if decision is None:
            raise PermissionError(f"{intent.risk.value} requires explicit approval.")

        if decision.status != ApprovalStatus.APPROVED:
            raise PermissionError(f"{intent.risk.value} is not approved.")

        if decision.approved_action is None:
            raise PermissionError("Approval must include the exact approved action.")

        approved = decision.approved_action
        if approved.action_type != intent.action_type:
            raise PermissionError("Approved action type does not match requested action.")
        if approved.target != intent.target:
            raise PermissionError("Approved target does not match requested action.")
        if approved.body != intent.body:
            raise PermissionError("Approved body does not match requested action.")
        if approved.scheduled_for != intent.scheduled_for:
            raise PermissionError("Approved schedule does not match requested action.")

        # If a body digest was stored at approval time, verify the body hasn't changed
        if decision_digest and intent.body is not None:
            current_digest = body_digest(intent.body)
            if current_digest != decision_digest:
                raise PermissionError(
                    "Message body has changed since approval. "
                    f"Digest mismatch: stored={decision_digest[:12]}, current={current_digest[:12]}"
                )


def default_connector_profiles() -> list[ConnectorProfile]:
    """Known connector surfaces, ordered by preferred use for Phase 1."""

    return [
        ConnectorProfile(
            name="Manual handoff",
            kind=ConnectorKind.MANUAL,
            authenticated=True,
            capabilities={
                ConnectorCapability.READ_PAGE,
                ConnectorCapability.CREATE_DRAFT,
            },
            notes="Always available fallback for review and user-executed actions.",
        ),
        ConnectorProfile(
            name="Codex in-app browser",
            kind=ConnectorKind.CODEX_BROWSER,
            capabilities={
                ConnectorCapability.READ_PAGE,
                ConnectorCapability.NAVIGATE,
                ConnectorCapability.CREATE_DRAFT,
                ConnectorCapability.SEND_MESSAGE,
            },
            notes="Good for authenticated browser tasks when the session is available.",
        ),
        ConnectorProfile(
            name="Tandem browser",
            kind=ConnectorKind.TANDEM_BROWSER,
            capabilities={
                ConnectorCapability.READ_PAGE,
                ConnectorCapability.NAVIGATE,
                ConnectorCapability.CREATE_DRAFT,
                ConnectorCapability.SEND_MESSAGE,
                ConnectorCapability.CREATE_DOCUMENT,
            },
            notes="Useful when stable, but not a hard dependency.",
        ),
        ConnectorProfile(
            name="Chrome",
            kind=ConnectorKind.CHROME,
            capabilities={
                ConnectorCapability.READ_PAGE,
                ConnectorCapability.NAVIGATE,
                ConnectorCapability.CREATE_DRAFT,
                ConnectorCapability.SEND_MESSAGE,
            },
            notes="Best when the user's normal Chrome profile has the required session.",
        ),
        ConnectorProfile(
            name="Gmail API",
            kind=ConnectorKind.GMAIL_API,
            capabilities={
                ConnectorCapability.CREATE_DRAFT,
                ConnectorCapability.SEND_MESSAGE,
                ConnectorCapability.SCHEDULE_SEND,
            },
            notes="Preferred over browser automation when scopes are available.",
        ),
        ConnectorProfile(
            name="Google Drive API",
            kind=ConnectorKind.GOOGLE_DRIVE_API,
            capabilities={
                ConnectorCapability.CREATE_DOCUMENT,
                ConnectorCapability.READ_DOCUMENT,
                ConnectorCapability.WRITE_DOCUMENT,
                ConnectorCapability.UPLOAD_FILE,
            },
            notes="Preferred for documents when create/edit/upload scopes are available.",
        ),
    ]
