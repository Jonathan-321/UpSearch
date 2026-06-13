#!/usr/bin/env python3
"""
UpSearch + Opportunity Intelligence OS — unified API server.

Run with:  uvicorn server:app --reload --port 8000

Routes:
  /api/*   — Profile, health, and model-config endpoints
  /os/*    — Opportunity Intelligence OS (full company packet workflow, SSE streaming)
"""
import asyncio
import json
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus
from dotenv import load_dotenv

load_dotenv(override=True)

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from upsearch import llm

# OS pipeline
from upsearch.orchestrator_service import run_pipeline
import db
from upsearch.api_schemas import (
    DeliveryEventOut,
    DeliveryUpdateIn,
    FollowUpCreateIn,
    FollowUpOut,
    FollowUpUpdateIn,
    HandoffReadinessOut,
    MessageReviewOut,
    PacketDetailOut,
    QAModelRouteOut,
    QAResultOut,
    RunRecordOut,
    RunStateOut,
    TraceEventOut,
)
from upsearch.config import load_settings
from upsearch.packet_checkup import agent_step, handoff_event, load_checkup, run_packet_checkup
from upsearch.profile_harness import build_profile_harness_report
from upsearch.profile_source_fetch import fetch_profile_sources
from upsearch.tracking import RunLogger

app = FastAPI(title="UpSearch + Opportunity Intelligence OS", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5179",
        "http://localhost:5180",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5179",
        "http://127.0.0.1:5180",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PROFILE_PATH = Path("profile.txt")
SSE_KEEPALIVE_SECONDS = 15.0


# ── Shared helpers ────────────────────────────────────────────────────────────

def load_profile_text() -> str:
    """Return the current profile text. Prefers the file when both exist."""
    file_profile = PROFILE_PATH.read_text().strip() if PROFILE_PATH.exists() else ""
    if file_profile:
        return file_profile
    stored = db.get_profile()
    if stored and stored.get("raw_profile"):
        return stored["raw_profile"].strip()
    return ""


def infer_profile_metadata(raw_profile: str) -> dict:
    metadata = {"name": "", "email": "", "school": "", "background_summary": ""}
    for line in raw_profile.splitlines():
        if ":" not in line:
            continue
        key, value = [part.strip() for part in line.split(":", 1)]
        key_lower = key.lower()
        if key_lower == "name":
            metadata["name"] = value
        elif key_lower == "email":
            metadata["email"] = value
        elif key_lower == "school":
            metadata["school"] = value
    metadata["background_summary"] = raw_profile.strip()[:500]
    return metadata


def profile_payload() -> dict:
    stored = db.get_profile()
    content = load_profile_text()
    return {
        "content": content,
        "profile": stored,
        "harness": build_profile_harness_report(content),
    }


def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def safe_json(value, fallback):
    if value in (None, ""):
        return fallback
    if isinstance(value, (list, dict)):
        return value
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return fallback


def message_platform(message: dict) -> dict:
    """Return the external surface for a reviewer handoff.

    This intentionally opens only the destination surface. Sending and form
    filling remain user-approved, manual actions.
    """
    variant = (message.get("variant") or "").lower()
    linkedin_url = message.get("linkedin_url") or ""
    source_url = message.get("source_url") or ""
    person = message.get("person_name") or ""
    company = message.get("company_name") or ""

    if "linkedin" in variant or "connection" in variant:
        linkedin_search = "https://www.linkedin.com/search/results/people/?keywords=" + quote_plus(
            " ".join(part for part in [person, company] if part)
        )
        return {
            "channel": "linkedin",
            "platform": "LinkedIn",
            "platform_label": "Open LinkedIn profile" if linkedin_url else "Search LinkedIn",
            "platform_url": linkedin_url or linkedin_search or "https://www.linkedin.com/feed/",
            "handoff_mode": "copy_then_open",
        }

    if "email" in variant or "recruiter" in variant:
        subject, body = split_email_draft(message.get("content") or "", company)
        compose_url = (
            "https://mail.google.com/mail/u/0/?view=cm&fs=1&tf=1"
            f"&su={quote_plus(subject)}&body={quote_plus(body)}"
        )
        return {
            "channel": "email",
            "platform": "Gmail",
            "platform_label": "Open Gmail compose",
            "platform_url": compose_url,
            "handoff_mode": "prefill_compose",
        }

    return {
        "channel": "manual",
        "platform": "Source",
        "platform_label": "Open source",
        "platform_url": source_url or linkedin_url or "https://www.linkedin.com/feed/",
        "handoff_mode": "open_only",
    }


def split_email_draft(content: str, company: str) -> tuple[str, str]:
    lines = content.strip().splitlines()
    if lines and lines[0].lower().startswith("subject:"):
        subject = lines[0].split(":", 1)[1].strip()
        body = "\n".join(lines[1:]).strip()
    else:
        subject = f"Question about {company}" if company else "Quick question"
        body = content.strip()
    return subject or "Quick question", body


def enrich_pending_message(message: dict) -> dict:
    problem = safe_json(message.get("open_problem"), {})
    qa_flags = safe_json(message.get("qa_flags"), [])
    if not isinstance(qa_flags, list):
        qa_flags = [str(qa_flags)]

    enriched = dict(message)
    enriched["problem_title"] = problem.get("title") if isinstance(problem, dict) else ""
    enriched["problem_source_urls"] = problem.get("source_urls", []) if isinstance(problem, dict) else []
    enriched["qa_flags"] = qa_flags
    enriched.update(message_platform(enriched))

    company = enriched.get("company_name") or "this company"
    person = enriched.get("person_name") or "the selected recipient"
    platform = enriched.get("platform") or "the target platform"
    mode = enriched.get("handoff_mode")
    if mode == "prefill_compose":
        action_note = "The platform button opens a prepared Gmail compose window, but does not send it."
    elif mode == "copy_then_open":
        action_note = "The platform button copies the draft and opens LinkedIn, but does not send it."
    else:
        action_note = "The platform button opens the destination surface only."
    enriched["approval_contract"] = (
        f"Approve only this exact {platform} draft for {person} at {company}. "
        f"{action_note} The final send remains a human action."
    )
    return enriched


def enrich_review_message(message: dict) -> dict:
    enriched = enrich_pending_message(message)
    company_name = enriched.get("company_name", "")
    checkup = load_checkup(company_name) if company_name else None
    if checkup:
        enriched["checkup"] = checkup
        enriched["failure_category"] = checkup.get("failure_category", "none")
        enriched["checkup_score"] = checkup.get("overall_score", 0)
    actionable, safety_reasons = message_safety(
        enriched,
        checkup,
        current_profile_markers(),
    )
    enriched["review_actionable"] = actionable
    if enriched.get("state_stale"):
        actionable = False
        safety_reasons.append("The message changed after approval. Review and approve the current text again.")
    if enriched.get("status") == "approved" and not enriched.get("approval_current"):
        actionable = False
        safety_reasons.append("No current approval matches this exact message body.")
    enriched["safe_retry"] = bool(
        enriched.get("approval_current")
        and enriched.get("delivery_status") in {"failed", "unknown"}
    )
    enriched["actionable"] = actionable
    enriched["safety_reasons"] = list(dict.fromkeys(safety_reasons))
    return enriched


def get_review_message(message_id: int) -> dict:
    for message in db.get_review_messages():
        if message["id"] == message_id:
            return enrich_review_message(message)
    raise HTTPException(404, f"Message {message_id} not found")


def current_profile_markers() -> dict:
    raw_profile = load_profile_text()
    stored = db.get_profile() or {}
    metadata = infer_profile_metadata(raw_profile)
    return {
        "name": (stored.get("name") or metadata.get("name") or "").strip(),
        "school": (stored.get("school") or metadata.get("school") or "").strip(),
    }


def message_safety(enriched: dict, checkup: dict | None, profile_markers: dict) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    content = enriched.get("content") or ""
    word_count = enriched.get("word_count") or len(content.split())
    qa_score = enriched.get("qa_score")
    person = enriched.get("person_name") or ""
    platform = (enriched.get("platform") or "").lower()
    variant = (enriched.get("variant") or "").lower()

    if not checkup:
        reasons.append("No packet checkup is attached.")
    elif checkup.get("failure_category") != "none":
        reasons.append(f"Checkup failed: {checkup.get('failure_category')}.")

    if isinstance(qa_score, (int, float)) and qa_score < 6:
        reasons.append(f"QA score is {qa_score}/10.")

    if word_count > 200:
        reasons.append(f"Draft is {word_count} words.")

    if not person and "recruiter" not in variant:
        reasons.append("No verified recipient is attached.")

    current_name = profile_markers.get("name", "").lower()
    current_school = profile_markers.get("school", "").lower()
    stale_markers = [
        ("Luis", "profile name"),
        ("UConn", "school"),
        ("Luis Mendez", "profile name"),
    ]
    for marker, label in stale_markers:
        marker_lower = marker.lower()
        if marker_lower not in content.lower():
            continue
        if label == "school" and marker_lower in current_school:
            continue
        if label == "profile name" and marker_lower in current_name:
            continue
        reasons.append(f"Draft contains stale {label} marker: {marker}.")

    if platform == "gmail" and not enriched.get("platform_url"):
        reasons.append("No Gmail handoff URL is configured.")
    if platform == "linkedin" and not (enriched.get("linkedin_url") or enriched.get("platform_url")):
        reasons.append("No LinkedIn destination is configured.")

    return len(reasons) == 0, reasons


def packet_qa(packet: dict | None) -> QAResultOut | None:
    if not packet:
        return None
    verification = safe_json(packet.get("verification"), {})
    flags = safe_json(packet.get("qa_flags"), [])
    if not isinstance(flags, list):
        flags = [str(flags)]
    model_route = verification.get("model_route") if isinstance(verification, dict) else None
    return QAResultOut(
        score=float(packet.get("qa_score") or 0),
        passed=bool(verification.get("passed")) if isinstance(verification, dict) else False,
        flags=flags,
        reasoning=verification.get("reasoning") if isinstance(verification, dict) else None,
        model_route=QAModelRouteOut.model_validate(model_route) if isinstance(model_route, dict) else None,
    )


def company_review_state(
    company: dict,
    packet: dict | None,
    checkup: dict | None,
) -> tuple[str, list[HandoffReadinessOut]]:
    messages = db.get_company_messages(company["id"])
    if not messages:
        return "unavailable", []

    approved = sum(
        1
        for message in messages
        if message.get("status") == "approved" and message.get("approval_current")
    )
    if approved == len(messages):
        approval_state = "approved"
    elif approved:
        approval_state = "partially_approved"
    else:
        approval_state = "required"

    profile_markers = current_profile_markers()
    handoffs: list[HandoffReadinessOut] = []
    for message in messages:
        enriched = enrich_pending_message({
            **message,
            "company_name": company["name"],
            "qa_score": packet.get("qa_score") if packet else None,
            "qa_flags": packet.get("qa_flags") if packet else None,
        })
        actionable, reasons = message_safety(enriched, checkup, profile_markers)
        if message.get("status") != "draft":
            actionable = False
            reasons = [f"Message status is {message.get('status', 'unknown')}."]
        handoffs.append(HandoffReadinessOut(
            message_id=message["id"],
            actionable=actionable,
            safety_reasons=reasons,
            platform=enriched.get("platform"),
            platform_label=enriched.get("platform_label"),
            platform_url=enriched.get("platform_url"),
            handoff_mode=enriched.get("handoff_mode"),
            approval_contract=enriched.get("approval_contract"),
        ))
    return approval_state, handoffs


def packet_detail(company_name: str) -> PacketDetailOut:
    company = db.get_company(company_name)
    if not company:
        raise HTTPException(404, f"No packet for '{company_name}'")
    packet = db.get_packet(company["id"])
    problems = db.get_problems(company["id"])
    people = db.get_people(company["id"])
    run_record = db.get_latest_run_record(company_name)
    persisted_trace = db.get_trace_events(run_record["run_id"]) if run_record else []
    trace_input = persisted_trace if run_record else None
    stored_checkup = load_checkup(company_name)
    checkup = (
        run_packet_checkup(company_name, packet, problems, people, trace_input)
        if packet
        else stored_checkup
    )
    trace_status = (
        checkup.get("trace_status", "unavailable")
        if checkup
        else "unavailable"
    )
    approval_state, handoffs = company_review_state(company, packet, checkup)
    return PacketDetailOut(
        company=company,
        packet=packet,
        problems=problems,
        people=people,
        checkup=checkup,
        run=RunRecordOut.from_db(run_record),
        trace_status=trace_status,
        trace=[TraceEventOut(**event) for event in persisted_trace],
        qa=packet_qa(packet),
        approval_state=approval_state,
        handoff_readiness=handoffs,
    )


# ── /api/* endpoints (profile, health, model config) ─────────────────────────

class ProfileRequest(BaseModel):
    content: str


@app.get("/api/health")
def health():
    return {"status": "ok", "provider": llm.active_provider(), "model": llm.active_model()}

@app.get("/api/profile")
def get_profile_api():
    return profile_payload()

@app.post("/api/profile")
def save_profile_api(req: ProfileRequest):
    content = req.content.strip()
    metadata = infer_profile_metadata(content)
    db.save_profile(
        name=metadata["name"],
        email=metadata["email"],
        school=metadata["school"],
        background_summary=metadata["background_summary"],
        raw_profile=content,
    )
    PROFILE_PATH.write_text(content + "\n", encoding="utf-8")
    # Automatically fetch profile sources in the background on save
    from upsearch.profile_source_fetch import fetch_profile_sources  # noqa: PLC0415
    try:
        fetch_profile_sources(content)
    except Exception:
        pass  # Non-blocking — enrichment falls back gracefully
    return {
        "ok": True,
        **profile_payload(),
    }


@app.post("/api/profile/fetch-sources")
def fetch_profile_sources_api():
    content = load_profile_text()
    report = fetch_profile_sources(content)
    return {"ok": True, "source_fetch": report, **profile_payload()}

# ── OS /os/* endpoints ────────────────────────────────────────────────────────

@app.on_event("startup")
def startup():
    db.init_db()
    db.recover_abandoned_runs()
    # Refresh profile source cache if stale (> 24 hours old)
    _refresh_profile_sources_if_stale()
    _report_model_config()


def _report_model_config():
    from upsearch.config import load_settings  # noqa: PLC0415
    from upsearch.startup_validation import (  # noqa: PLC0415
        enforce_model_config,
        model_config_problems,
    )
    problems = model_config_problems(load_settings())
    for problem in problems:
        print(f"[upsearch] model config: {problem}")
    enforce_model_config(problems)


@app.get("/api/config/model-status")
def model_config_status():
    from upsearch.config import load_settings  # noqa: PLC0415
    from upsearch.startup_validation import model_config_problems  # noqa: PLC0415
    settings = load_settings()
    problems = model_config_problems(settings)
    return {
        "ok": not problems,
        "agent_provider": llm.active_provider(),
        "agent_model": llm.active_model(),
        "strong_model_provider": settings.strong_model_provider,
        "strong_model": settings.strong_model,
        "problems": problems,
    }


def _refresh_profile_sources_if_stale():
    from upsearch.profile_source_fetch import load_cached_report, fetch_profile_sources  # noqa: PLC0415
    from datetime import datetime, timezone, timedelta  # noqa: PLC0415
    cached = load_cached_report()
    should_fetch = True
    if cached and cached.get("fetched_at"):
        try:
            fetched = datetime.fromisoformat(cached["fetched_at"])
            if datetime.now(timezone.utc) - fetched < timedelta(hours=24):
                should_fetch = False
        except (ValueError, TypeError):
            pass
    if should_fetch:
        try:
            content = load_profile_text()
            if content.strip():
                fetch_profile_sources(content)
        except Exception:
            pass  # Non-blocking


@app.get("/os/health")
def os_health():
    return {"status": "ok", "provider": llm.active_provider(), "model": llm.active_model()}


@app.get("/os/profile")
def os_get_profile():
    return profile_payload()


@app.post("/os/profile")
def os_save_profile(req: ProfileRequest):
    return save_profile_api(req)


@app.post("/os/profile/fetch-sources")
def os_fetch_profile_sources():
    return fetch_profile_sources_api()


@app.get("/os/companies")
def os_companies():
    return {"companies": db.list_companies()}


@app.get("/os/packet/{company_name}", response_model=PacketDetailOut)
def os_get_packet(company_name: str):
    return packet_detail(company_name)


@app.get("/os/runs/{run_id}", response_model=RunStateOut)
def os_get_run(run_id: str):
    run_record = db.get_run_record(run_id)
    if not run_record:
        raise HTTPException(404, f"No run '{run_id}'")
    detail = packet_detail(run_record["company_name"])
    trace = db.get_trace_events(run_id)
    if trace:
        checkup_trace_status = (
            "complete"
            if run_record.get("status") == "complete"
            and not any(event.get("status") == "error" for event in trace)
            else "incomplete"
        )
    else:
        checkup_trace_status = "incomplete"
    return RunStateOut(
        run=RunRecordOut.from_db(run_record),
        trace_status=checkup_trace_status,
        trace=[TraceEventOut(**event) for event in trace],
        qa=detail.qa,
        approval_state=detail.approval_state,
        handoff_readiness=detail.handoff_readiness,
    )


@app.get("/os/checkup/{company_name}")
def os_get_checkup(company_name: str):
    checkup = packet_detail(company_name).checkup
    if checkup is None:
        raise HTTPException(404, f"No checkup for '{company_name}'")
    return {"checkup": checkup.model_dump()}


@app.get("/os/messages/pending")
def os_pending_messages(include_needs_review: bool = False):
    """Return pending messages, optionally filtered by checkup status.

    By default, only actionable messages are shown. Messages without a
    passing checkup, a recipient, a safe profile match, or acceptable QA stay
    quarantined unless include_needs_review=true.
    Set include_needs_review=true to see all pending messages.
    """
    messages = []
    from upsearch.packet_checkup import load_checkup  # noqa: PLC0415
    profile_markers = current_profile_markers()
    for m in db.get_pending_approvals():
        enriched = enrich_pending_message(m)
        company_name = m.get("company_name", "")
        checkup = None
        if company_name:
            checkup = load_checkup(company_name)
            enriched["checkup"] = checkup
            if checkup:
                category = checkup.get("failure_category", "none")
                enriched["failure_category"] = category
                enriched["checkup_score"] = checkup.get("overall_score", 0)
        actionable, safety_reasons = message_safety(enriched, checkup, profile_markers)
        enriched["actionable"] = actionable
        enriched["safety_reasons"] = safety_reasons
        if not include_needs_review and not actionable:
            continue
        messages.append(enriched)
    return {"messages": messages}


@app.get("/os/messages/review", response_model=list[MessageReviewOut])
def os_review_messages():
    return [
        MessageReviewOut(**enrich_review_message(message))
        for message in db.get_review_messages()
    ]


@app.post("/os/messages/{message_id}/approve")
def os_approve_message(message_id: int):
    message = get_review_message(message_id)
    if message.get("status") != "draft" and not message.get("state_stale"):
        raise HTTPException(409, "Only draft or edited-stale messages can be approved")
    if not message.get("review_actionable"):
        reasons = " ".join(message.get("safety_reasons") or [])
        raise HTTPException(409, reasons or "Message is not safe to approve")
    channel = message.get("channel") or "manual"
    target = message.get("platform_url")
    approval_id = db.approve_message(
        message_id,
        notes="Approved in review",
        body_digest=db.message_digest(message.get("content") or ""),
        channel=channel,
        target=target,
    )
    event_id = db.record_delivery_event(
        message_id,
        approval_id,
        channel,
        status="prepared",
    )
    return {
        "ok": True,
        "message_id": message_id,
        "approval_id": approval_id,
        "delivery_event_id": event_id,
        "body_digest": db.message_digest(message.get("content") or ""),
    }


@app.post("/os/messages/{message_id}/reject")
def os_reject_message(message_id: int, notes: str = ""):
    from datetime import datetime, timezone  # noqa: PLC0415
    with db.conn() as c:
        c.execute("UPDATE messages SET status='rejected' WHERE id=?", (message_id,))
        c.execute(
            "INSERT INTO approvals (message_id, approved_at, notes) VALUES (?, ?, ?)",
            (message_id, datetime.now(timezone.utc).isoformat(), notes or "Rejected by user"),
        )
    return {"ok": True, "message_id": message_id}


@app.post("/os/messages/{message_id}/delivery", response_model=DeliveryEventOut)
def os_record_delivery(message_id: int, update: DeliveryUpdateIn):
    message = get_review_message(message_id)
    approval_id = message.get("approval_id")
    if not approval_id or not message.get("approval_current"):
        raise HTTPException(409, "Delivery state requires a current exact-message approval")
    channel = update.channel or message.get("approval_channel") or message.get("channel") or "manual"
    try:
        event_id = db.record_delivery_event(
            message_id,
            approval_id,
            channel,
            status=update.status,
            error_message=update.error_message,
        )
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    event = next(
        event for event in db.get_delivery_events(message_id)
        if event["id"] == event_id
    )
    return DeliveryEventOut(**event)


@app.get("/os/messages/{message_id}/delivery", response_model=list[DeliveryEventOut])
def os_get_delivery(message_id: int):
    if not db.get_message(message_id):
        raise HTTPException(404, f"Message {message_id} not found")
    return [DeliveryEventOut(**event) for event in db.get_delivery_events(message_id)]


@app.post("/os/messages/{message_id}/follow-ups", response_model=FollowUpOut)
def os_create_follow_up(message_id: int, request: FollowUpCreateIn):
    message = get_review_message(message_id)
    if not message.get("approval_current"):
        raise HTTPException(409, "Follow-up requires a current exact-message approval")
    if message.get("delivery_status") not in {"sent", "delivered"}:
        raise HTTPException(409, "Mark the approved message as sent before scheduling a follow-up")
    try:
        follow_up_id = db.insert_follow_up(
            message_id,
            request.due_date,
            request.notes,
            approval_id=message.get("approval_id"),
        )
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    follow_up = next(
        item for item in db.get_follow_ups_for_message(message_id)
        if item["id"] == follow_up_id
    )
    return FollowUpOut(**follow_up)


@app.patch("/os/follow-ups/{follow_up_id}", response_model=FollowUpOut)
def os_update_follow_up(follow_up_id: int, request: FollowUpUpdateIn):
    with db.conn() as connection:
        row = connection.execute(
            "SELECT message_id FROM follow_ups WHERE id=?",
            (follow_up_id,),
        ).fetchone()
    if not row:
        raise HTTPException(404, f"Follow-up {follow_up_id} not found")
    try:
        db.update_follow_up(follow_up_id, request.status, request.notes)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    follow_up = next(
        item for item in db.get_follow_ups_for_message(row["message_id"])
        if item["id"] == follow_up_id
    )
    return FollowUpOut(**follow_up)


# ── Maintenance (024, 031) ────────────────────────────────────────────────────

@app.get("/os/maintenance/people-hygiene")
def os_people_hygiene_report():
    """Read-only preview: junk people rows and the pending messages addressed
    to them or to unverified recipients. Never mutates."""
    return db.people_hygiene_report()


@app.post("/os/maintenance/people-hygiene")
def os_run_people_hygiene():
    """Run the hygiene purge after reviewing the GET report. Deletes junk
    people, rejects their pending messages, and rewrites packet people maps."""
    return db.run_people_hygiene()


@app.get("/os/maintenance/legacy-archive")
def os_legacy_archive_report():
    """Read-only preview: identity_blocked packets and packet-less
    rejected/discovered companies left by pre-fix discovery. Never mutates."""
    return db.legacy_archive_report()


@app.post("/os/maintenance/legacy-archive")
def os_run_legacy_archive():
    """Archive the legacy junk after reviewing the GET report. Sets packets
    crm_status='archived' and companies status='archived'; deletes nothing.
    The operator runs this after review — agents never run it against the
    live database."""
    return db.run_legacy_archive()


@app.get("/os/packet/stream/{company_name}")
async def os_stream_packet(company_name: str, lane: str = "ai_infra"):
    """
    SSE stream — runs the full OS packet workflow for one company.
    Emits 'stage' events as each agent completes, then 'complete' when done.
    Delegates to ``orchestrator_service.run_pipeline``.
    """
    raw_profile = load_profile_text()

    async def generate():
        from datetime import datetime, timezone
        import time

        events: list[tuple[str, dict]] = []
        active_run_id: str | None = None

        def on_progress(event_type: str, data: dict):
            nonlocal active_run_id
            active_run_id = data.get("run_id") or active_run_id
            events.append((event_type, data))

        task = asyncio.create_task(
            run_pipeline(
                company_name, lane, raw_profile,
                progress_callback=on_progress,
            )
        )

        try:
            last_idx = 0
            last_emit = time.monotonic()
            while not task.done() or last_idx < len(events):
                while last_idx < len(events):
                    event_type, data = events[last_idx]
                    yield sse(event_type, data)
                    last_idx += 1
                    last_emit = time.monotonic()
                if not task.done():
                    if time.monotonic() - last_emit >= SSE_KEEPALIVE_SECONDS:
                        yield sse("keepalive", {
                            "run_id": active_run_id,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        })
                        last_emit = time.monotonic()
                    await asyncio.sleep(min(0.05, SSE_KEEPALIVE_SECONDS))

            # Yield any final events after task completes
            while last_idx < len(events):
                event_type, data = events[last_idx]
                yield sse(event_type, data)
                last_idx += 1

            exc = task.exception()
            if exc:
                yield sse("error", {"error": str(exc)})
        finally:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Batch pipeline ────────────────────────────────────────────────────────────

import uuid  # noqa: E402
_batch_runs: dict[str, dict] = {}
_BATCH_CONCURRENCY = 2
_SEM = asyncio.Semaphore(_BATCH_CONCURRENCY)


class BatchRequest(BaseModel):
    companies: list[dict]  # [{"name": "...", "lane": "..."}]


@app.post("/os/batch")
async def os_batch_start(req: BatchRequest):
    """Start a batch pipeline run. Returns a batch ID for status polling."""
    batch_id = uuid.uuid4().hex[:12]
    _batch_runs[batch_id] = {
        "id": batch_id,
        "status": "running",
        "companies": [],
        "results": {},
    }
    for entry in req.companies:
        name = entry.get("name", "")
        lane = entry.get("lane", "ai_infra")
        _batch_runs[batch_id]["companies"].append({"name": name, "lane": lane, "status": "queued"})

    async def _run_batch():
        """Process each company sequentially with a concurrency cap."""
        idx = 0
        for entry in _batch_runs[batch_id]["companies"]:
            name = entry["name"]
            lane = entry["lane"]
            _batch_runs[batch_id]["companies"][idx]["status"] = "running"
            async with _SEM:
                try:
                    raw_profile = load_profile_text()
                    result = await run_pipeline(name, lane, raw_profile)
                    _batch_runs[batch_id]["companies"][idx]["status"] = "complete"
                    _batch_runs[batch_id]["results"][name] = {
                        "status": "complete",
                        "qa_score": result.qa_result.get("score", 0),
                        "qa_passed": result.qa_result.get("passed", False),
                        "problems": len(result.problems),
                        "people": len(result.people),
                        "drafts": list(result.outreach_drafts.keys()),
                        "error": None,
                    }
                except Exception as e:
                    _batch_runs[batch_id]["companies"][idx]["status"] = "error"
                    _batch_runs[batch_id]["results"][name] = {
                        "status": "error",
                        "error": str(e),
                    }
            idx += 1
        _batch_runs[batch_id]["status"] = "complete"

    asyncio.create_task(_run_batch())
    return {"batch_id": batch_id, "company_count": len(req.companies)}


@app.get("/os/batch/{batch_id}")
def os_batch_status(batch_id: str):
    run = _batch_runs.get(batch_id)
    if not run:
        from fastapi import HTTPException  # noqa: PLC0415
        raise HTTPException(404, f"Batch {batch_id} not found")
    return run


@app.get("/os/batch/{batch_id}/stream")
async def os_batch_stream(batch_id: str):
    """SSE stream for a batch run — emits 'batch_company' events as each finishes."""
    run = _batch_runs.get(batch_id)
    if not run:
        from fastapi import HTTPException  # noqa: PLC0415
        raise HTTPException(404, f"Batch {batch_id} not found")

    async def stream_batch():
        while True:
            run = _batch_runs.get(batch_id)
            if not run:
                yield sse("error", {"error": "Batch not found"})
                return
            yield sse("batch_status", {
                "batch_id": batch_id,
                "status": run["status"],
                "companies": run["companies"],
                "results": run["results"],
            })
            if run["status"] == "complete":
                yield sse("batch_complete", {"batch_id": batch_id, "results": run["results"]})
                return
            await asyncio.sleep(5)

    return StreamingResponse(stream_batch(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
