"""Packet Checkup reliability layer.

This is the UpSearch equivalent of Swarm Checkup: it records agent steps and
handoffs, scores the produced opportunity packet, assigns a concrete failure
category, and writes a small report that can be shown in the app.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import load_settings
from .tracking import RunLogger


EXPECTED_AGENTS = [
    "profile",
    "company_sourcing",
    "problem_discovery",
    "people_sourcing",
    "technical_note",
    "outreach_draft",
    "qa_verification",
]

FAILURE_FIXES = {
    "none": "No immediate fix needed. Keep the approval gate before external actions.",
    "identity_blocked": (
        "Company identity could not be verified, so every later stage was "
        "skipped. Check the company name and domain (the identity reason may "
        "name the closest fetched candidate), then re-run company research."
    ),
    "missing_packet": "Run the packet workflow before evaluating reliability.",
    "empty_problem_set": "Strengthen public-source retrieval and keep a conservative fallback problem with explicit uncertainty.",
    "missing_source_url": "Require each problem to carry at least one source URL before it is treated as outreach-ready.",
    "unverified_source_urls": "Do not trust model-supplied URLs unless they came from a retrieval connector or a verified source fetch.",
    "weak_person_mapping": "Add stronger person sourcing from LinkedIn, GitHub, author pages, and company/team pages.",
    "technical_note_too_vague": "Force the note to include problem framing, build plan, success criteria, and adjacent proof.",
    "outreach_over_200_words": "Shorten outreach and keep only one technical observation plus one clear ask.",
    "unsupported_claim": "Remove claims that are not backed by stored source URLs or the user's proof bank.",
    "approval_gate_missing": "Keep messages in draft state until the exact action is approved by the user.",
    "agent_coordination_failure": "Record every agent step and handoff with reads, writes, and payload keys.",
    "qa_failed": "Inspect QA flags before showing any send control.",
}

SOURCE_METHODS = {
    "problem_discovery": {
        "title": "How open problems are found",
        "steps": [
            "Start from the company brief: what they do, lane, tech stack, and fit notes.",
            "Search public discussion surfaces such as Hacker News and Reddit for company engineering signals.",
            "Give the model only the company brief plus retrieved source snippets and require JSON with source URLs.",
            "Rank problems by specificity, public evidence, and whether a student can build a concrete contribution.",
            "If model JSON breaks or no problem is returned, use a conservative fallback labeled with uncertainty.",
            "QA later checks that the problem is source-backed before outreach is treated as ready.",
        ],
        "current_tools": ["Hacker News search", "Reddit search", "company brief", "JSON repair", "QA flags"],
        "planned_tools": ["company blogs", "docs", "careers pages", "GitHub repos", "papers", "LinkedIn posts"],
    },
    "people_sourcing": {
        "title": "How company people are found",
        "steps": [
            "Use the selected problem as the search lens, not just the company name.",
            "Search public people signals such as HN authors and known founder/engineer/researcher surfaces.",
            "Ask the model to rank people by proximity to the problem, public signal, and conversation usefulness.",
            "Require URLs when available and mark unverifiable profiles instead of fabricating them.",
            "QA flags people without public profile links so a human can verify before contact.",
        ],
        "current_tools": ["Hacker News search", "problem context", "role/proximity ranking", "QA flags"],
        "planned_tools": ["LinkedIn", "GitHub orgs", "author pages", "conference talks", "papers", "company team pages"],
    },
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "packet"


def _json_default(value: Any) -> Any:
    if hasattr(value, "to_dict"):
        return value.to_dict()
    return str(value)


def _parse_json(value: Any, fallback: Any) -> Any:
    if value is None:
        return fallback
    if isinstance(value, (list, dict)):
        return value
    if not isinstance(value, str):
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def _urls_from(value: Any) -> list[str]:
    parsed = _parse_json(value, value)
    if isinstance(parsed, list):
        return [item for item in parsed if isinstance(item, str) and item.strip()]
    if isinstance(parsed, str) and parsed.startswith("http"):
        return [parsed]
    return []


def _word_count(text: str | None) -> int:
    return len([word for word in (text or "").split() if word.strip()])


def _clamp_score(value: float) -> float:
    return round(max(0.0, min(10.0, value)), 1)


@dataclass(frozen=True)
class TraceEvent:
    event_type: str
    status: str = "ok"
    timestamp: str = field(default_factory=utc_now_iso)
    agent: str | None = None
    role: str | None = None
    reads: list[str] = field(default_factory=list)
    writes: list[str] = field(default_factory=list)
    output_summary: str = ""
    latency_ms: int = 0
    from_agent: str | None = None
    to_agent: str | None = None
    payload_keys: list[str] = field(default_factory=list)
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def agent_step(
    agent: str,
    role: str,
    *,
    reads: list[str],
    writes: list[str],
    output_summary: str,
    latency_ms: int = 0,
    status: str = "ok",
) -> dict[str, Any]:
    return TraceEvent(
        event_type="agent_step",
        agent=agent,
        role=role,
        reads=reads,
        writes=writes,
        output_summary=output_summary,
        latency_ms=latency_ms,
        status=status,
    ).to_dict()


def handoff_event(
    from_agent: str,
    to_agent: str,
    *,
    payload_keys: list[str],
    reason: str,
    status: str = "ok",
) -> dict[str, Any]:
    return TraceEvent(
        event_type="handoff",
        from_agent=from_agent,
        to_agent=to_agent,
        payload_keys=payload_keys,
        reason=reason,
        status=status,
    ).to_dict()


def _score_coordination(
    trace_events: list[dict[str, Any]],
    trace_provided: bool = True,
) -> tuple[float, list[str], int, int]:
    if not trace_provided:
        return 8.0, [], 0, 0
    if not trace_events:
        return 5.0, EXPECTED_AGENTS[:], 0, 0

    agent_steps = [event for event in trace_events if event.get("event_type") == "agent_step"]
    handoffs = [event for event in trace_events if event.get("event_type") == "handoff"]
    seen_agents = {event.get("agent") for event in agent_steps if event.get("agent")}
    missing = [agent for agent in EXPECTED_AGENTS if agent not in seen_agents]
    errored = [event for event in trace_events if event.get("status") == "error"]

    score = 10.0
    score -= len(missing) * 1.1
    if len(handoffs) < max(0, len(EXPECTED_AGENTS) - 1):
        score -= 1.5
    if errored:
        score -= 3.0

    return _clamp_score(score), missing, len(agent_steps), len(handoffs)


def _problem_source_candidate_count(trace_events: list[dict[str, Any]]) -> int | None:
    for event in trace_events:
        if event.get("event_type") != "agent_step" or event.get("agent") != "problem_discovery":
            continue
        summary = str(event.get("output_summary", ""))
        match = re.search(r"source_candidates=(\d+)", summary)
        if match:
            return int(match.group(1))
    return None


def evaluate_packet(
    company_name: str,
    packet: dict[str, Any] | None,
    problems: list[dict[str, Any]],
    people: list[dict[str, Any]],
    trace_events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    trace_provided = trace_events is not None
    resolved_trace = trace_events if trace_provided else []
    if not packet:
        trace_status = "incomplete" if trace_provided else "unavailable"
        return {
            "company": company_name,
            "status": "failed",
            "overall_score": 0,
            "failure_category": "missing_packet",
            "suggested_fix": FAILURE_FIXES["missing_packet"],
            "metrics": [],
            "trace_status": trace_status,
            "trace": {
                "events": resolved_trace,
                "agent_steps": 0,
                "handoffs": 0,
                "missing_agents": EXPECTED_AGENTS if trace_provided else [],
            },
            "source_methods": SOURCE_METHODS,
        }

    problem_urls = sorted({url for problem in problems for url in _urls_from(problem.get("source_urls"))})
    sourced_problem_count = sum(1 for problem in problems if _urls_from(problem.get("source_urls")))
    verified_people = [
        person for person in people
        if person.get("verification_status") == "verified" and person.get("source_url")
    ]
    drafts = _parse_json(packet.get("outreach_drafts"), {})
    if not isinstance(drafts, dict):
        drafts = {}
    over_200 = [name for name, text in drafts.items() if _word_count(str(text)) > 200]
    qa_flags = _parse_json(packet.get("qa_flags"), [])
    if not isinstance(qa_flags, list):
        qa_flags = []

    qa_score = float(packet.get("qa_score") or 0)
    note_words = _word_count(packet.get("technical_note", ""))
    avg_problem_relevance = (
        sum(float(problem.get("relevance_score") or 0) for problem in problems) / len(problems)
        if problems else 0
    )
    avg_people_relevance = (
        sum(float(person.get("relevance_score") or 0) for person in people) / len(people)
        if people else 0
    )

    source_score = _clamp_score(min(10, len(problem_urls) * 2.5) if problems else 0)
    problem_score = _clamp_score(0.65 * avg_problem_relevance + 0.35 * (10 if sourced_problem_count else 0))
    people_source_ratio = len(verified_people) / max(1, len(people))
    people_score = _clamp_score(0.6 * avg_people_relevance + 0.4 * people_source_ratio * 10)
    note_score = _clamp_score(10 if note_words >= 260 else 7 if note_words >= 180 else 4 if note_words else 0)
    outreach_score = _clamp_score(10 if drafts and not over_200 else 6 if drafts else 0)
    coordination_score, missing_agents, agent_step_count, handoff_count = _score_coordination(resolved_trace, trace_provided)
    trace_has_errors = any(event.get("status") == "error" for event in resolved_trace)
    coordination_incomplete = trace_provided and (
        bool(missing_agents)
        or handoff_count < max(0, len(EXPECTED_AGENTS) - 1)
        or trace_has_errors
    )
    source_candidate_count = _problem_source_candidate_count(resolved_trace)
    unverified_model_sources = (
        bool(resolved_trace)
        and source_candidate_count == 0
        and bool(problem_urls)
    )
    if unverified_model_sources:
        source_score = min(source_score, 4.0)

    unsupported_claim_flag = any("unsupported" in str(flag).lower() for flag in qa_flags)
    identity_blocked = str(packet.get("crm_status") or "") == "identity_blocked"
    failure_category = "none"
    if identity_blocked:
        # Empty problems/people/note/drafts are SYMPTOMS of the identity
        # block, not separate failures — one category owns the diagnosis.
        failure_category = "identity_blocked"
    elif not problems:
        failure_category = "empty_problem_set"
    elif not problem_urls:
        failure_category = "missing_source_url"
    elif unverified_model_sources:
        failure_category = "unverified_source_urls"
    elif not people or not verified_people or people_score < 5.5:
        failure_category = "weak_person_mapping"
    elif note_words < 180:
        failure_category = "technical_note_too_vague"
    elif over_200:
        failure_category = "outreach_over_200_words"
    elif unsupported_claim_flag:
        failure_category = "unsupported_claim"
    elif coordination_incomplete:
        failure_category = "agent_coordination_failure"
    elif qa_score < 6:
        failure_category = "qa_failed"

    # ── Determine trace_status ──────────────────────────────────────────────
    if not trace_provided:
        trace_status = "unavailable"
    elif coordination_incomplete:
        trace_status = "incomplete"
    else:
        trace_status = "complete"

    overall = _clamp_score(
        0.18 * source_score
        + 0.18 * problem_score
        + 0.16 * people_score
        + 0.18 * note_score
        + 0.12 * outreach_score
        + 0.10 * qa_score
        + 0.08 * coordination_score
    )
    caps: list[float] = []
    if not problems:
        caps.append(4.0)
    if not problem_urls:
        caps.append(5.0)
    if unverified_model_sources:
        caps.append(5.5)
    if not people:
        caps.append(5.5)
    elif not verified_people:
        caps.append(5.5)
    if qa_score < 6:
        caps.append(6.0)
    if caps:
        overall = _clamp_score(min(overall, *caps))
    status = "passed" if overall >= 7 and failure_category == "none" else "needs_review"

    metrics = [
        {"name": "Source grounding", "score": source_score, "detail": f"{len(problem_urls)} unique problem source URLs"},
        {"name": "Problem specificity", "score": problem_score, "detail": f"{len(problems)} problems, {sourced_problem_count} source-backed"},
        {
            "name": "People mapping",
            "score": people_score,
            "detail": f"{len(verified_people)}/{len(people)} people passed evidence verification",
        },
        {"name": "Technical note", "score": note_score, "detail": f"{note_words} words"},
        {"name": "Outreach safety", "score": outreach_score, "detail": f"{len(drafts)} drafts, {len(over_200)} over 200 words"},
        {
            "name": "Agent coordination",
            "score": coordination_score,
            "detail": (
                "trace unavailable"
                if not trace_provided
                else f"{agent_step_count} steps, {handoff_count} handoffs, "
                f"{'errors present' if trace_has_errors else 'no errors'}"
            ),
        },
        {"name": "QA", "score": _clamp_score(qa_score), "detail": f"{len(qa_flags)} flags"},
    ]

    return {
        "company": company_name,
        "status": status,
        "overall_score": overall,
        "failure_category": failure_category,
        "trace_status": trace_status,
        "suggested_fix": FAILURE_FIXES.get(failure_category, "Review packet quality before outreach."),
        "metrics": metrics,
        "trace": {
            "events": resolved_trace,
            "agent_steps": agent_step_count,
            "handoffs": handoff_count,
            "missing_agents": missing_agents,
            "has_errors": trace_has_errors,
        },
        "source_methods": SOURCE_METHODS,
        "facts": {
            "problem_source_urls": problem_urls,
            "problem_source_candidates": source_candidate_count,
            "unverified_model_sources": unverified_model_sources,
            "verified_people": len(verified_people),
            "qa_flags": qa_flags,
            "over_200_drafts": over_200,
            "note_words": note_words,
        },
        "created_at": utc_now_iso(),
    }


PASS_THRESHOLD = 7.0
MAX_RETRIES_PER_CATEGORY = 2


def decide_action(
    checkup: dict[str, Any],
    retry_counts: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Map a checkup result to a pipeline decision.

    Returns one of:
      {"action": "pass", "reason": "..."}
      {"action": "retry", "stage": str, "reason": "..."}  -- re-run the named agent
      {"action": "block", "reason": "..."}                 -- stop, needs user input
      {"action": "ask", "question": "..."}                  -- surface to user mid-pipeline
    """
    retry_counts = retry_counts or {}
    category = checkup.get("failure_category", "none")
    score = checkup.get("overall_score", 0.0)

    if category == "none" and score >= PASS_THRESHOLD:
        return {"action": "pass", "reason": f"Packet score {score}/10, no failure category."}

    # ── Retry-eligible categories ──────────────────────────────────────────
    retry_map = {
        "empty_problem_set": {
            "stage": "problem_discovery",
            "reason": "No problems found. Retry with broader search.",
        },
        "missing_source_url": {
            "stage": "problem_discovery",
            "reason": "Problems lack source URLs. Retry requiring URL-backed output.",
        },
        "weak_person_mapping": {
            "stage": "people_sourcing",
            "reason": "People mapping below threshold. Retry with wider query.",
        },
        "outreach_over_200_words": {
            "stage": "outreach_draft",
            "reason": "Outreach exceeds 200 words. Retry with stricter length enforcement.",
        },
    }
    retry_info = retry_map.get(category)
    if retry_info:
        used = retry_counts.get(category, 0)
        if used < MAX_RETRIES_PER_CATEGORY:
            retry_counts[category] = used + 1
            return {
                "action": "retry",
                "stage": retry_info["stage"],
                "reason": retry_info["reason"],
                "retry_count": used + 1,
                "max_retries": MAX_RETRIES_PER_CATEGORY,
            }
        return {
            "action": "block",
            "reason": f"Retried {category} {MAX_RETRIES_PER_CATEGORY}x without improvement.",
        }

    # ── Block-eligible categories ──────────────────────────────────────────
    block_map = {
        "identity_blocked": {
            "reason": "Company identity unverified — check the name/domain and re-run company research.",
        },
        "missing_packet": {
            "reason": "No packet data. Run the pipeline from the start.",
        },
        "unsupported_claim": {
            "reason": "Claims found without proof source. Blocking until user reviews.",
        },
        "unverified_source_urls": {
            "reason": "Source URLs may be fabricated. Requires source verification connector.",
        },
        "approval_gate_missing": {
            "reason": "No approval gate configured. Blocking external action.",
        },
        "agent_coordination_failure": {
            "reason": "Agent pipeline incomplete. Some steps were skipped.",
        },
        "qa_failed": {
            "reason": "QA verification failed. Review flags before proceeding.",
        },
    }
    block_info = block_map.get(category)
    if block_info:
        return {"action": "block", "reason": block_info["reason"]}

    # ── Technical note too vague — can't retry meaningfully, ask user ──────
    if category == "technical_note_too_vague":
        return {
            "action": "ask",
            "question": f"The technical note is only {checkup.get('facts', {}).get('note_words', '?')} words. Review and approve, or we deepen the research?",
        }

    # ── Fallback: block with the suggested fix ─────────────────────────────
    return {
        "action": "block",
        "reason": checkup.get("suggested_fix", "Packet needs review before continuing."),
    }


def write_checkup_artifacts(
    company_name: str,
    checkup: dict[str, Any],
    root: Path | None = None,
) -> dict[str, str]:
    settings = load_settings()
    report_root = root or settings.tracking_dir / "packet-checkups"
    report_root.mkdir(parents=True, exist_ok=True)
    slug = slugify(company_name)
    json_path = report_root / f"{slug}.json"
    report_path = report_root / f"{slug}.md"

    checkup_with_paths = {**checkup, "artifact_paths": {"json": str(json_path), "report": str(report_path)}}
    json_path.write_text(json.dumps(checkup_with_paths, indent=2, default=_json_default) + "\n", encoding="utf-8")
    report_path.write_text(render_markdown_report(checkup_with_paths), encoding="utf-8")
    return {"json": str(json_path), "report": str(report_path)}


def load_checkup(company_name: str, root: Path | None = None) -> dict[str, Any] | None:
    settings = load_settings()
    report_root = root or settings.tracking_dir / "packet-checkups"
    path = report_root / f"{slugify(company_name)}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def run_packet_checkup(
    company_name: str,
    packet: dict[str, Any] | None,
    problems: list[dict[str, Any]],
    people: list[dict[str, Any]],
    trace_events: list[dict[str, Any]] | None = None,
    logger: RunLogger | None = None,
) -> dict[str, Any]:
    checkup = evaluate_packet(company_name, packet, problems, people, trace_events)
    artifact_paths = write_checkup_artifacts(company_name, checkup)
    checkup = {**checkup, "artifact_paths": artifact_paths}
    if logger is not None:
        logger.log_event(
            "packet_checkup",
            {
                "company": company_name,
                "status": checkup["status"],
                "overall_score": checkup["overall_score"],
                "failure_category": checkup["failure_category"],
                "artifact_paths": artifact_paths,
            },
        )
    return checkup


def render_markdown_report(checkup: dict[str, Any]) -> str:
    metrics = checkup.get("metrics", [])
    trace = checkup.get("trace", {})
    lines = [
        f"# Packet Checkup: {checkup.get('company', 'Unknown')}",
        "",
        f"- Status: `{checkup.get('status')}`",
        f"- Overall score: `{checkup.get('overall_score')}/10`",
        f"- Top failure category: `{checkup.get('failure_category')}`",
        f"- Trace status: `{checkup.get('trace_status', 'unavailable')}`",
        f"- Suggested fix: {checkup.get('suggested_fix')}",
        f"- Agent steps: `{trace.get('agent_steps', 0)}`",
        f"- Handoffs: `{trace.get('handoffs', 0)}`",
        "",
        "## Metrics",
        "",
        "| Metric | Score | Detail |",
        "|---|---:|---|",
    ]
    for metric in metrics:
        lines.append(f"| {metric['name']} | {metric['score']} | {metric['detail']} |")

    missing = trace.get("missing_agents", [])
    lines.extend([
        "",
        "## Coordination",
        "",
        f"- Missing agents: `{', '.join(missing) if missing else 'none'}`",
        "",
        "## How Problem Discovery Works",
        "",
    ])
    for step in SOURCE_METHODS["problem_discovery"]["steps"]:
        lines.append(f"- {step}")

    lines.extend(["", "## How People Sourcing Works", ""])
    for step in SOURCE_METHODS["people_sourcing"]["steps"]:
        lines.append(f"- {step}")

    lines.extend(["", "## Trace Events", ""])
    for event in trace.get("events", [])[:40]:
        if event.get("event_type") == "handoff":
            lines.append(
                f"- handoff: `{event.get('from_agent')}` -> `{event.get('to_agent')}` "
                f"payload={event.get('payload_keys')} reason={event.get('reason')}"
            )
        else:
            lines.append(
                f"- step: `{event.get('agent')}` status={event.get('status')} "
                f"writes={event.get('writes')} summary={event.get('output_summary')}"
            )
    lines.append("")
    return "\n".join(lines)
