"""Unified pipeline service — one ``run_pipeline`` contract for all callers.

Every caller (SSE stream, batch route, CLI, scheduler) uses the same agent
order, retry policy, database writes, trace events, and run-ID tracking.
"""
from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable

import db
from upsearch.config import load_settings
from upsearch.packet_checkup import (
    agent_step,
    decide_action,
    evaluate_packet,
    handoff_event,
    run_packet_checkup,
)
from upsearch.tracking import RunLogger


# ── Public data contract ─────────────────────────────────────────────────────


@dataclass
class RunResult:
    """Everything produced by a single pipeline execution."""

    run_id: str
    company_name: str
    lane: str
    profile: dict = field(default_factory=dict)
    company_record: dict = field(default_factory=dict)
    problems: list = field(default_factory=list)
    people: list = field(default_factory=list)
    technical_note_text: str = ""
    adjacent_proof: str = ""
    outreach_drafts: dict = field(default_factory=dict)
    qa_result: dict = field(default_factory=dict)
    trace_events: list = field(default_factory=list)
    packet_id: int = 0
    db_company_id: int = 0
    status: str = "complete"  # complete | failed | blocked


# ── Outreach gating ──────────────────────────────────────────────────────────

OUTREACH_SKIP_NO_VERIFIED_PERSON = "No verified person; outreach skipped pending review"


def _relevance_score(person: dict) -> float:
    try:
        return float(person.get("relevance_score") or 0)
    except (TypeError, ValueError):
        return 0.0


def select_top_person(people: list[dict]) -> dict | None:
    """Return the highest-relevance person whose ``verification_status`` is ``"verified"``.

    Outreach is only ever drafted for verified people. Unverified people stay in
    the packet's ``people_map`` for research context but are never outreach
    targets; when no verified person exists this returns ``None`` and the caller
    must skip outreach drafting entirely.
    """
    verified = [
        person
        for person in people
        if isinstance(person, dict) and person.get("verification_status") == "verified"
    ]
    if not verified:
        return None
    return max(verified, key=_relevance_score)


# ── Pipeline ─────────────────────────────────────────────────────────────────


async def run_pipeline(
    company_name: str,
    lane: str,
    profile_text: str,
    *,
    run_id: str | None = None,
    progress_callback: Callable[[str, dict], None] | None = None,
    retry_counts: dict[str, int] | None = None,
    discovery_source_urls: list[str] | None = None,
) -> RunResult:
    """Run the full 7-agent packet pipeline under one run ID.

    Parameters
    ----------
    company_name : str
        Target company.
    lane : str
        Opportunity lane tag.
    profile_text : str
        Raw user profile text (enriched internally).
    run_id : str | None
        Optional stable lineage ID. Scheduler retries reuse the same value.
    progress_callback : Callable[[str, dict], None] | None
        Called with ``(event_type, data)`` after each step so callers can
        stream progress (SSE, scheduler status, etc.).  Event types match the
        existing SSE contract: ``stage``, ``log``, ``gate``, ``block``,
        ``checkup``, ``complete``, ``error``.
    retry_counts : dict[str, int] | None
        Per-stage retry count (mutated in place by checkup gates).
    discovery_source_urls : list[str] | None
        Source URLs discovered during lane discovery, passed to the company
        agent for identity verification reuse.

    Returns
    -------
    RunResult
        All pipeline outputs including the run ID.

    Notes
    -----
    - Sync agents are run via ``asyncio.to_thread`` so they never block the
      event loop.
    - Database writes (company, problems, people, packet, messages) happen
      inline in the correct order.
    - A ``run_records`` row is created at start and updated through every step.
    - If company identity is unverified after the company step, the pipeline
      blocks early and returns ``status="blocked"`` with a minimal packet.
    """
    _cb = progress_callback or (lambda _t, _d: None)
    _retries = retry_counts or {}
    _discovery_urls = discovery_source_urls or []
    trace_events: list[dict] = []
    logger = RunLogger(load_settings())

    # ── 0. Run record ────────────────────────────────────────────────────────
    run_id = db.create_run_record(company_name, lane, run_id=run_id)

    def _emit(event: str, data: dict) -> None:
        data.setdefault("run_id", run_id)
        if event in {"gate", "block", "error"}:
            status = (
                "error"
                if event == "error"
                else "needs_review"
                if event == "block"
                else str(data.get("action", "ok"))
            )
            db.insert_trace_event(
                run_id,
                event,
                status=status,
                reason=data.get("reason") or data.get("error"),
                payload=data,
            )
        _cb(event, data)

    def _log(agent: str, level: str, message: str, t0: float | None = None) -> None:
        entry: dict = {"agent": agent, "level": level, "message": message}
        if t0 is not None:
            entry["elapsed"] = f"{time.monotonic() - t0:.1f}s"
        _emit("log", entry)

    def _append_step(
        agent: str,
        role: str,
        t0: float,
        *,
        reads: list[str],
        writes: list[str],
        output_summary: str,
        status: str = "ok",
    ) -> None:
        event = agent_step(
            agent,
            role,
            reads=reads,
            writes=writes,
            output_summary=output_summary,
            latency_ms=int((time.monotonic() - t0) * 1000),
            status=status,
        )
        trace_events.append(event)
        db.insert_trace_event(
            run_id,
            event["event_type"],
            status=event.get("status", "ok"),
            timestamp=event.get("timestamp", ""),
            agent=event.get("agent"),
            agent_role=event.get("role"),
            reads=event.get("reads"),
            writes=event.get("writes"),
            output_summary=event.get("output_summary"),
            latency_ms=event.get("latency_ms"),
            payload=event,
        )
        _emit("progress", event.copy())

    def _append_handoff(
        from_agent: str,
        to_agent: str,
        payload_keys: list[str],
        reason: str,
    ) -> None:
        event = handoff_event(from_agent, to_agent, payload_keys=payload_keys, reason=reason)
        trace_events.append(event)
        db.insert_trace_event(
            run_id,
            event["event_type"],
            status=event.get("status", "ok"),
            timestamp=event.get("timestamp", ""),
            from_agent=event.get("from_agent"),
            to_agent=event.get("to_agent"),
            payload_keys=event.get("payload_keys"),
            reason=event.get("reason"),
            payload=event,
        )
        _emit("progress", event.copy())

    async def _check_and_decide(
        snapshot: dict | None,
        problems: list,
        people: list,
    ) -> dict[str, Any] | None:
        if not snapshot:
            return None
        checkup = await asyncio.to_thread(
            evaluate_packet, company_name, snapshot, problems, people, trace_events,
        )
        return decide_action(checkup, _retries)

    steps_completed: list[str] = []
    result = RunResult(
        run_id=run_id,
        company_name=company_name,
        lane=lane,
        trace_events=trace_events,
    )

    try:
        # ── 1. Profile ───────────────────────────────────────────────────────
        from agents import profile as _profile_agent
        from upsearch.profile_harness import enrich_profile_text

        steps_completed.append("profile")
        db.update_run_record(run_id, current_step="profile", steps_completed=steps_completed)
        _emit("stage", {"stage": "profile", "status": "running", "message": "Loading profile..."})
        _log("Profile", "STARTED", "Parsing background and experience")
        enriched = enrich_profile_text(profile_text)
        t0 = time.monotonic()
        profile = await asyncio.to_thread(_profile_agent.run, enriched)
        _append_step(
            "profile",
            "Parse user background into structured proof points.",
            t0,
            reads=["profile_text"],
            writes=["user_profile"],
            output_summary=f"{profile.get('name', '?')} at {profile.get('school', '?')}",
        )
        _append_handoff(
            "profile", "company_sourcing",
            ["user_profile", "lane", "company_name"],
            "Research company fit with user context.",
        )
        _log("Profile", "COMPLETE", f"Loaded: {profile.get('name', '?')} at {profile.get('school', '?')}", t0)
        _emit("stage", {"stage": "profile", "status": "complete",
                        "message": f"{profile.get('name', '?')} @ {profile.get('school', '?')}"})
        result.profile = profile

        # ── 2. Company ───────────────────────────────────────────────────────
        from agents import company as _company_agent

        steps_completed.append("company")
        db.update_run_record(run_id, current_step="company", steps_completed=steps_completed)
        _emit("stage", {"stage": "company", "status": "running", "message": f"Researching {company_name}..."})
        _log("Company", "STARTED", f"Looking up {company_name}")
        t0 = time.monotonic()
        company_args = (company_name, lane, profile)
        if _discovery_urls:
            company_result = await asyncio.to_thread(
                _company_agent.run,
                *company_args,
                discovery_source_urls=_discovery_urls,
            )
        else:
            company_result = await asyncio.to_thread(
                _company_agent.run,
                *company_args,
            )
        company_data = company_result["result"]
        company_sources = company_result.get("source_urls", [])

        company_id = db.upsert_company(
            company_name,
            canonical_name=company_data.get("name", company_name),
            website=company_data.get("website", ""),
            official_domain=company_data.get("official_domain", ""),
            identity_status=company_data.get("identity_status", "unverified"),
            identity_confidence=company_data.get("identity_confidence", 0),
            identity_reason=company_data.get("identity_reason", ""),
            lane=lane,
            fit_score=company_data.get("fit_score", 0),
            hiring_status=company_data.get("hiring_status", "unknown"),
            source_urls=company_sources,
            status="researched",
        )
        db.clear_company_generated_state(company_id)

        _append_step(
            "company_sourcing",
            "Research fit, product area, hiring signal, and public sources.",
            t0,
            reads=["company_name", "lane", "user_profile", "public_sources"],
            writes=["company_record", "company_sources"],
            output_summary=f"fit={company_data.get('fit_score', '?')}/10; sources={len(company_sources)}",
        )
        _append_handoff(
            "company_sourcing", "problem_discovery",
            ["company_record", "company_sources", "user_profile"],
            "Extract real technical problems from public signal.",
        )
        _log("Company", "COMPLETE",
             f"Fit {company_data.get('fit_score', '?')}/10 · {company_data.get('hiring_status', 'unknown')}", t0)
        _emit("stage", {"stage": "company", "status": "complete",
                        "message": f"Fit: {company_data.get('fit_score', '?')}/10",
                        "data": company_data})
        result.company_record = company_data
        result.db_company_id = company_id

        # ── 2b. Identity gate ──────────────────────────────────────────────────
        identity_status = company_data.get("identity_status", "unverified")
        if identity_status != "verified":
            reason = company_data.get(
                "identity_reason",
                "Company identity could not be verified from retrieved evidence.",
            )
            packet_id = db.upsert_packet(
                company_id,
                company_fit=company_data.get("why", ""),
                open_problem=json.dumps({}),
                people_map=json.dumps([]),
                technical_note="",
                adjacent_proof="",
                outreach_drafts=json.dumps({}),
                verification=json.dumps({"passed": False, "score": 0, "flags": [reason]}),
                qa_score=0,
                qa_flags=json.dumps([reason]),
                crm_status="identity_blocked",
            )
            db.set_company_status(company_id, "identity_blocked")
            _log("Company", "IDENTITY_BLOCKED", reason)
            _emit("block", {"stage": "company", "reason": reason,
                            "packet_id": packet_id, "company": company_name})
            _emit("complete", {
                "blocked": True,
                "stage": "company",
                "reason": reason,
                "company": company_name,
                "packet_id": packet_id,
            })
            result.status = "blocked"
            result.packet_id = packet_id
            db.update_run_record(
                run_id, status="failed", error_message=reason,
                steps_completed=steps_completed,
            )
            return result

        # ── 3. Problems ──────────────────────────────────────────────────────
        from agents import problem as _problem_agent

        steps_completed.append("problem")
        db.update_run_record(run_id, current_step="problem", steps_completed=steps_completed)
        _emit("stage", {"stage": "problem", "status": "running", "message": "Extracting open problems..."})
        _log("Problem", "STARTED", "Identifying open technical problems")
        t0 = time.monotonic()
        problem_result = await asyncio.to_thread(_problem_agent.run, company_name, company_data, profile)
        problems = problem_result["result"].get("problems", [])
        problem_sources = problem_result.get("source_urls", [])
        for p in problems:
            db.insert_problem(
                company_id,
                p["title"],
                p.get("description", ""),
                p.get("source_urls", []),
                p.get("relevance_score", 0),
            )
        _append_step(
            "problem_discovery",
            "Extract source-backed technical problems from company and discussion signals.",
            t0,
            reads=["company_record", "hacker_news_posts", "reddit_posts", "user_profile"],
            writes=["problems", "problem_sources"],
            output_summary=f"{len(problems)} problems; source_candidates={len(problem_sources)}",
        )
        _append_handoff(
            "problem_discovery", "people_sourcing",
            ["top_problem", "source_urls", "user_profile"],
            "Find people close to the selected technical problem.",
        )
        _log("Problem", "COMPLETE", f"Found {len(problems)} source-backed problems", t0)
        _emit("stage", {"stage": "problem", "status": "complete",
                        "message": f"Found {len(problems)} problems", "data": problems})
        result.problems = problems

        # ── 3b. Checkup gate after problem discovery ──────────────────────────
        problem_snapshot = {
            "qa_score": 7.0,
            "qa_flags": json.dumps([]),
            "crm_status": "prepared",
            "outreach_drafts": json.dumps({}),
            "technical_note": "",
        }
        problem_decision = await _check_and_decide(problem_snapshot, problems, [])
        if problem_decision and problem_decision["action"] == "retry" and problem_decision.get("stage") == "problem_discovery":
            _log("Checkup", "RETRY", problem_decision["reason"])
            _emit("gate", {"action": "retry", "stage": problem_decision["stage"],
                           "retry_count": problem_decision.get("retry_count", 1),
                           "reason": problem_decision["reason"]})
            _log("Problem", "RETRY", "Re-extracting problems with broader search")
            t0 = time.monotonic()
            problem_result = await asyncio.to_thread(_problem_agent.run, company_name, company_data, profile)
            problems = problem_result["result"].get("problems", [])
            _log("Problem", "RETRY_COMPLETE", f"Retry found {len(problems)} problems", t0)
            _emit("stage", {"stage": "problem", "status": "retry_complete",
                            "message": f"Retry: {len(problems)} problems", "data": problems})
            result.problems = problems
        elif problem_decision and problem_decision["action"] == "block":
            reason = problem_decision.get("reason") or "Packet needs review before continuing."
            _log("Checkup", "BLOCK", reason)
            _emit("block", {"stage": "problem", "reason": reason})
            _emit("complete", {
                "blocked": True,
                "stage": "problem",
                "reason": reason,
                "company": company_name,
            })
            result.status = "blocked"
            db.update_run_record(run_id, status="failed", error_message=reason, steps_completed=steps_completed)
            return result

        # ── 4. People ────────────────────────────────────────────────────────
        from agents import people as _people_agent

        top_problem = dict(problems[0]) if problems else {}
        if top_problem:
            # The cited-author resolver scans the packet's cited sources; the
            # author of ANY cited post is proximate, not only problem[0]'s.
            combined_urls = [
                url
                for problem_item in problems
                for url in problem_item.get("source_urls", [])
                if isinstance(url, str)
            ]
            top_problem["source_urls"] = list(dict.fromkeys([
                *top_problem.get("source_urls", []),
                *combined_urls,
            ]))[:6]
        steps_completed.append("people")
        db.update_run_record(run_id, current_step="people", steps_completed=steps_completed)
        _emit("stage", {"stage": "people", "status": "running", "message": "Finding relevant people..."})
        _log("People", "STARTED", "Mapping engineers and researchers")
        t0 = time.monotonic()
        people_result = await asyncio.to_thread(
            _people_agent.run,
            company_name,
            top_problem,
            profile,
            company_domain=company_data.get("official_domain", ""),
        )
        people_list = people_result["result"].get("people", [])
        people_sources = people_result.get("source_urls", [])
        inserted_people: list[dict] = []
        for person in people_list:
            person_id = db.insert_person(
                company_id,
                person["name"],
                person.get("role", ""),
                linkedin_url=person.get("linkedin_url", ""),
                twitter_url=person.get("twitter_url", ""),
                github_url=person.get("github_url", ""),
                source_url=person.get("source_url", "") or person.get("source", ""),
                verification_status=person.get("verification_status", "unverified"),
                verification_reason=person.get("verification_reason", ""),
                contact_url_checks=person.get("contact_url_checks", {}),
                relevance_score=person.get("relevance_score", 0),
                relevance_reason=person.get("relevance_reason", ""),
                proximity=person.get("proximity", "engineer"),
            )
            inserted_people.append({"id": person_id, **person})
        _append_step(
            "people_sourcing",
            "Map relevant people by problem proximity and public signal.",
            t0,
            reads=["top_problem", "hacker_news_authors", "user_profile"],
            writes=["people", "people_sources"],
            output_summary=f"{len(people_list)} people; source_candidates={len(people_sources)}",
        )
        _append_handoff(
            "people_sourcing", "technical_note",
            ["company_record", "top_problem", "people", "user_profile"],
            "Write a credible technical artifact for the selected problem.",
        )
        _log("People", "COMPLETE", f"Mapped {len(people_list)} people worth reaching", t0)
        _emit("stage", {"stage": "people", "status": "complete",
                        "message": f"Mapped {len(people_list)} people", "data": people_list})
        result.people = people_list

        # ── 4b. Checkup gate after people discovery ───────────────────────────
        people_snapshot = {
            "qa_score": 7.0,
            "qa_flags": json.dumps([]),
            "crm_status": "prepared",
            "outreach_drafts": json.dumps({}),
            "technical_note": "",
        }
        people_decision = await _check_and_decide(people_snapshot, problems, people_list)
        if people_decision and people_decision["action"] == "retry" and people_decision.get("stage") == "people_sourcing":
            _log("Checkup", "RETRY", people_decision["reason"])
            _emit("gate", {"action": "retry", "stage": people_decision["stage"],
                           "retry_count": people_decision.get("retry_count", 1),
                           "reason": people_decision["reason"]})
            _log("People", "RETRY", "Re-mapping with wider query")
            t0 = time.monotonic()
            people_result = await asyncio.to_thread(
                _people_agent.run,
                company_name,
                top_problem,
                profile,
                company_domain=company_data.get("official_domain", ""),
            )
            people_list = people_result["result"].get("people", [])
            _log("People", "RETRY_COMPLETE", f"Retry mapped {len(people_list)} people", t0)
            _emit("stage", {"stage": "people", "status": "retry_complete",
                            "message": f"Retry: {len(people_list)} people", "data": people_list})
            result.people = people_list
        elif people_decision and people_decision["action"] == "block":
            reason = people_decision.get("reason") or "Packet needs review before continuing."
            _log("Checkup", "BLOCK", reason)
            _emit("block", {"stage": "people", "reason": reason})
            _emit("complete", {
                "blocked": True,
                "stage": "people",
                "reason": reason,
                "company": company_name,
            })
            result.status = "blocked"
            db.update_run_record(run_id, status="failed", error_message=reason, steps_completed=steps_completed)
            return result

        # ── 5. Technical Note ────────────────────────────────────────────────
        from agents import technical_note as _note_agent

        steps_completed.append("technical_note")
        db.update_run_record(run_id, current_step="technical_note", steps_completed=steps_completed)
        _emit("stage", {"stage": "technical_note", "status": "running", "message": "Writing one-page technical note..."})
        _log("Note", "STARTED", "Writing one-page technical brief")
        t0 = time.monotonic()
        note_result = await asyncio.to_thread(
            _note_agent.run, company_name, company_data, top_problem, profile,
        )
        note_text = note_result["result"].get("technical_note", "")
        adjacent_proof = note_result["result"].get("adjacent_proof", "")
        _append_step(
            "technical_note",
            "Write one-page technical problem brief and adjacent proof mapping.",
            t0,
            reads=["company_record", "top_problem", "user_profile"],
            writes=["technical_note", "adjacent_proof"],
            output_summary=f"{len(note_text.split())} words; proof={'yes' if adjacent_proof else 'no'}",
        )
        _append_handoff(
            "technical_note", "outreach_draft",
            ["technical_note", "adjacent_proof", "top_person"],
            "Draft concise outreach without claiming fake experience.",
        )
        _log("Note", "COMPLETE", f"{len(note_text.split())} words written", t0)
        _emit("stage", {"stage": "technical_note", "status": "complete",
                        "message": f"{len(note_text.split())} words",
                        "data": {"technical_note": note_text, "adjacent_proof": adjacent_proof}})
        result.technical_note_text = note_text
        result.adjacent_proof = adjacent_proof

        # ── 6. Outreach ──────────────────────────────────────────────────────
        # Outreach targets are gated: only a verified person can receive a
        # draft. Prefer people with DB ids (inserted_people); fall back to the
        # latest sourced list (a checkup retry may have replaced it).
        top_person = select_top_person(inserted_people) or select_top_person(people_list)
        steps_completed.append("outreach")
        db.update_run_record(run_id, current_step="outreach", steps_completed=steps_completed)
        _emit("stage", {"stage": "outreach", "status": "running", "message": "Drafting outreach variants..."})
        t0 = time.monotonic()
        if top_person is None:
            # No verified person: skip the drafting model call entirely. The
            # unverified people remain in the packet for research context, and
            # the packet lands in review (checkup: weak_person_mapping).
            drafts: dict = {}
            _log("Outreach", "SKIPPED", OUTREACH_SKIP_NO_VERIFIED_PERSON)
            _append_step(
                "outreach_draft",
                "Draft channel-specific messages under the human approval gate.",
                t0,
                reads=["top_person", "top_problem", "technical_note", "adjacent_proof"],
                writes=["outreach_drafts"],
                output_summary="0 drafts; skipped: no verified person",
                status="needs_review",
            )
            _append_handoff(
                "outreach_draft", "qa_verification",
                ["packet_data", "drafts"],
                "No verified person; QA reviews the packet without drafts.",
            )
            _emit("stage", {"stage": "outreach", "status": "complete",
                            "message": "0 drafts (no verified person)", "data": drafts})
        else:
            from agents import outreach as _outreach_agent

            _log("Outreach", "STARTED", f"Drafting variants for {top_person.get('name', 'top contact')}")
            outreach_result = await asyncio.to_thread(
                _outreach_agent.run, company_name, top_problem, top_person,
                note_text, adjacent_proof, profile,
            )
            drafts = outreach_result["result"]
            _append_step(
                "outreach_draft",
                "Draft channel-specific messages under the human approval gate.",
                t0,
                reads=["top_person", "top_problem", "technical_note", "adjacent_proof"],
                writes=["outreach_drafts"],
                output_summary=f"{len(drafts)} drafts; max_words={max((len(str(v).split()) for v in drafts.values()), default=0)}",
            )
            _append_handoff(
                "outreach_draft", "qa_verification",
                ["packet_data", "drafts"],
                "Verify claims, sources, word count, and tone before user review.",
            )
            _log("Outreach", "COMPLETE", f"{len(drafts)} variants ready for review", t0)
            _emit("stage", {"stage": "outreach", "status": "complete",
                            "message": f"{len(drafts)} variants", "data": drafts})
        result.outreach_drafts = drafts

        # ── 7. QA ────────────────────────────────────────────────────────────
        from agents import qa as _qa_agent

        steps_completed.append("qa")
        db.update_run_record(run_id, current_step="qa", steps_completed=steps_completed)
        _emit("stage", {"stage": "qa", "status": "running", "message": "Running QA checks..."})
        _log("QA", "STARTED", "Checking claims, sources, word count, tone")
        t0 = time.monotonic()
        packet_data = {
            "company": company_data,
            "problems": problems,
            "people": people_list,
            "technical_note": note_text,
            "adjacent_proof": adjacent_proof,
            "outreach_drafts": drafts,
        }
        qa_result = await asyncio.to_thread(_qa_agent.run, packet_data, profile)
        _append_step(
            "qa_verification",
            "Check claims, sources, word count, tone, and approval readiness.",
            t0,
            reads=["packet_data"],
            writes=["qa_result"],
            output_summary=f"score={qa_result.get('score', 0)}/10; flags={len(qa_result.get('flags', []))}",
            status="ok" if qa_result.get("passed") else "needs_review",
        )

        # ── 7b. Persist packet ───────────────────────────────────────────────
        crm_status = (
            "prepared"
            if top_person is not None and qa_result.get("passed")
            else "needs_review"
        )
        packet_id = db.upsert_packet(
            company_id,
            company_fit=company_data.get("why", ""),
            open_problem=json.dumps(top_problem),
            people_map=json.dumps(people_list),
            technical_note=note_text,
            adjacent_proof=adjacent_proof,
            outreach_drafts=json.dumps(drafts),
            verification=json.dumps(qa_result),
            qa_score=qa_result.get("score", 0),
            qa_flags=json.dumps(qa_result.get("flags", [])),
            crm_status=crm_status,
        )
        # Hard invariant: messages are only ever inserted for a verified
        # recipient. With no verified person, drafts is empty and nothing
        # reaches the decision inbox.
        if top_person is not None and top_person.get("verification_status") == "verified":
            for variant, draft_text in drafts.items():
                if isinstance(draft_text, str) and draft_text.strip():
                    db.insert_message(packet_id, top_person.get("id"), variant, draft_text)
        db.set_company_status(company_id, "packet_ready")

        packet_snapshot = {
            "id": packet_id,
            "company_fit": company_data.get("why", ""),
            "open_problem": json.dumps(top_problem),
            "people_map": json.dumps(people_list),
            "technical_note": note_text,
            "adjacent_proof": adjacent_proof,
            "outreach_drafts": json.dumps(drafts),
            "verification": json.dumps(qa_result),
            "qa_score": qa_result.get("score", 0),
            "qa_flags": json.dumps(qa_result.get("flags", [])),
            "crm_status": crm_status,
        }

        # ── 7c. Final checkup + gate ─────────────────────────────────────────
        checkup = run_packet_checkup(
            company_name, packet_snapshot, problems, people_list, trace_events, logger=logger,
        )
        final_decision = await asyncio.to_thread(decide_action, checkup, _retries)
        _emit("gate", {
            "action": final_decision.get("action", "block"),
            "stage": "qa",
            "reason": final_decision.get("reason") or final_decision.get("question", ""),
        })

        flag_count = len(qa_result.get("flags", []))
        qa_status = "passed" if qa_result.get("passed") else f"{flag_count} flag{'s' if flag_count != 1 else ''}"
        _log("QA", "COMPLETE", f"Score {qa_result.get('score', 0)}/10 · {qa_status}", t0)
        _emit("stage", {"stage": "qa", "status": "complete",
                        "message": f"QA: {qa_result.get('score', 0)}/10",
                        "data": qa_result})
        _log("Checkup", "COMPLETE",
             f"{checkup.get('overall_score')}/10 · {checkup.get('failure_category', '?')}")
        _emit("checkup", checkup)

        result.qa_result = qa_result
        result.packet_id = packet_id

        if final_decision["action"] != "pass":
            reason = final_decision.get("reason") or "Packet needs review before continuing."
            _log("Checkup", "BLOCK", reason)
            _emit("block", {"stage": "qa", "reason": reason})
            _emit("complete", {"blocked": True, "reason": reason,
                               "company": company_name, "checkup": checkup, "packet_id": packet_id})
            result.status = "blocked"
            db.update_run_record(
                run_id, status="failed", qa_score=qa_result.get("score", 0),
                final_status="needs_review", error_message=reason,
                steps_completed=steps_completed,
            )
            return result

        # ── Complete ─────────────────────────────────────────────────────────
        final_status = crm_status
        db.update_run_record(
            run_id, status="complete", qa_score=qa_result.get("score", 0),
            final_status=final_status, steps_completed=steps_completed,
        )
        _emit("complete", {
            "packet_id": packet_id,
            "run_id": run_id,
            "company": company_name,
            "fit_score": company_data.get("fit_score", 0),
            "qa_score": qa_result.get("score", 0),
            "problems": len(problems),
            "people": len(people_list),
            "checkup": checkup,
        })

    except asyncio.CancelledError:
        reason = "Run cancelled because the client disconnected."
        _log("Pipeline", "CANCELLED", reason)
        db.update_run_record(
            run_id,
            status="cancelled",
            error_message=reason,
            steps_completed=steps_completed,
        )
        result.status = "cancelled"
        raise
    except Exception as exc:
        _log("Pipeline", "ERROR", str(exc))
        _emit("error", {"error": str(exc), "run_id": run_id})
        db.update_run_record(run_id, status="failed", error_message=str(exc)[:500],
                             steps_completed=steps_completed)
        result.status = "failed"
        raise

    return result
