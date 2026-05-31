"""
Harnessed Orchestrator — runs the full packet workflow through AgentHarness contracts.

Every agent call is wrapped in: typed schemas, model routing, budgets, validators,
and local/W&B logging. The orchestrator owns state, task order, and approval gates.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agents import profile, company, problem, people, technical_note, outreach, qa, action
import db

from .config import load_settings
from .connectors import ApprovalGate
from .harness import AgentHarness, HarnessBudget, HarnessContext, HarnessResult
from .model_router import ModelRouter, TaskType
from .schemas import (
    AgentRunRecord,
    ApprovalStatus,
    Company as CompanySchema,
    ExternalAction,
    OpportunityPacket,
    OutreachChannel,
    OutreachDraft,
    Person,
    Problem as ProblemSchema,
    Source,
    SourceType,
    TechnicalNote,
    utc_now_iso,
)
from .tracking import RunLogger


# ---------------------------------------------------------------------------
# Helpers — bridge loose-dict agent returns into our typed schemas
# ---------------------------------------------------------------------------

def _sources_from_urls(urls: list[str], default_type: SourceType = SourceType.OTHER) -> list[Source]:
    return [Source(url=u, title=u.split("/")[-1][:80], source_type=default_type) for u in urls if u]


def _build_packet_from_context(ctx: "PacketRunContext") -> OpportunityPacket:
    """Convert the run context back into a canonical OpportunityPacket."""
    people = [
        Person(
            name=p.get("name", ""),
            company_name=ctx.company_name,
            role=p.get("role", ""),
            relevance_reason=p.get("relevance_reason", ""),
            best_channel=OutreachChannel.LINKEDIN_CONNECTION,
            profile_urls=[u for u in [p.get("linkedin_url", "")] if u],
            sources=[Source(url=u, title="", source_type=SourceType.LINKEDIN) for u in [p.get("linkedin_url", "")] if u],
        )
        for p in ctx.people
    ]

    outreach_drafts = []
    for variant, body in ctx.outreach_drafts.items():
        channel = OutreachChannel.EMAIL if "email" in variant else OutreachChannel.LINKEDIN_CONNECTION
        outreach_drafts.append(
            OutreachDraft(
                person_name=people[0].name if people else "",
                company_name=ctx.company_name,
                channel=channel,
                body=body,
            )
        )

    return OpportunityPacket(
        lane=ctx.lane,
        company=CompanySchema(
            name=ctx.company_name,
            lane=ctx.lane,
            website=ctx.company_record.get("website", ""),
        ),
        problem=ProblemSchema(
            company_name=ctx.company_name,
            title=ctx.problems[0].get("title", "") if ctx.problems else "",
            summary=ctx.problems[0].get("description", "") if ctx.problems else "",
            buildable_angle=ctx.problems[0].get("contribution_surface", "") if ctx.problems else "",
        ) if ctx.problems else None,
        people=people,
        technical_note=TechnicalNote(
            title=f"Technical Note — {ctx.company_name}",
            company_name=ctx.company_name,
            problem_title=ctx.problems[0].get("title", "") if ctx.problems else "",
            body_markdown=ctx.technical_note_text,
        ),
        outreach_drafts=outreach_drafts,
    )


# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------

def _validate_person_list(output: dict) -> list[str]:
    errors = []
    people_list = output.get("people", []) if isinstance(output, dict) else []
    for p in people_list:
        if not p.get("name"):
            errors.append("Person missing name")
        if not p.get("role"):
            errors.append(f"Person {p.get('name', '?')} missing role")
        if not p.get("relevance_reason"):
            errors.append(f"Person {p.get('name', '?')} missing relevance_reason")
    return errors


def _validate_company_output(output: dict) -> list[str]:
    errors = []
    result = output.get("result", output)
    if not result.get("name"):
        errors.append("Company missing name")
    if not result.get("what_they_do"):
        errors.append("Company missing description")
    return errors


def _validate_problems(output: dict) -> list[str]:
    errors = []
    result = output.get("result", output)
    problems_list = result.get("problems", [])
    if not problems_list:
        errors.append("No problems found")
    for p in problems_list:
        if not p.get("title"):
            errors.append("Problem missing title")
        if not p.get("description"):
            errors.append(f"Problem {p.get('title', '?')} missing description")
    return errors


def _validate_technical_note(output: dict) -> list[str]:
    errors = []
    result = output.get("result", output)
    if not result.get("technical_note"):
        errors.append("Technical note is empty")
    return errors


def _validate_outreach(output: dict) -> list[str]:
    errors = []
    result = output.get("result", output)
    for variant in ("email", "linkedin_note", "connection_followup"):
        body = result.get(variant, "")
        if body and len(body.split()) > 200:
            errors.append(f"{variant} is {len(body.split())} words, over 200 limit")
    return errors


def _validate_qa(output: dict) -> list[str]:
    errors = []
    result = output.get("result", output)
    if result.get("score", 0) < 6:
        errors.append(f"QA score {result.get('score', 0)} is below threshold 6")
    for flag in result.get("flags", []):
        errors.append(f"QA flag: {flag}")
    return errors


# ---------------------------------------------------------------------------
# Runners — wrap the agent run() calls so they match the Harness signature
# ---------------------------------------------------------------------------

def _profile_runner(input_data: str, _route, _context) -> dict:
    return profile.run(input_data)


def _company_runner(input_data: tuple, _route, _context) -> dict:
    company_name, lane, user_profile = input_data
    return company.run(company_name, lane, user_profile)


def _problem_runner(input_data: tuple, _route, _context) -> dict:
    company_name, company_record, user_profile = input_data
    return problem.run(company_name, company_record, user_profile)


def _people_runner(input_data: tuple, _route, _context) -> dict:
    company_name, problem_item, user_profile = input_data
    return people.run(company_name, problem_item, user_profile)


def _note_runner(input_data: tuple, _route, _context) -> dict:
    company_name, company_record, problem_item, user_profile = input_data
    return technical_note.run(company_name, company_record, problem_item, user_profile)


def _outreach_runner(input_data: tuple, _route, _context) -> dict:
    company_name, problem_item, person_item, note_text, proof, user_profile = input_data
    return outreach.run(company_name, problem_item, person_item, note_text, proof, user_profile)


def _qa_runner(input_data: tuple, _route, _context) -> dict:
    packet_data, user_profile = input_data
    return qa.run(packet_data, user_profile)


# ---------------------------------------------------------------------------
# Shared harness factory
# ---------------------------------------------------------------------------

def _make_harness(
    name: str,
    task_type: TaskType,
    router: ModelRouter,
    runner_fn,
    validators: list | None = None,
) -> AgentHarness:
    route = router.route(task_type)
    # Cheap model for broad work
    budget = HarnessBudget(max_input_tokens=120000, max_output_tokens=2048, max_cost_usd=0.25)
    return AgentHarness(
        name=name,
        task_type=task_type,
        route=route,
        budget=budget,
        runner=runner_fn,
        validators=validators or [],
    )


# ---------------------------------------------------------------------------
# Run context — shared mutable state for one company run
# ---------------------------------------------------------------------------

@dataclass
class PacketRunContext:
    company_name: str
    lane: str

    user_profile: dict = field(default_factory=dict)
    profile_raw: str = ""
    company_record: dict = field(default_factory=dict)
    problems: list = field(default_factory=list)
    people: list = field(default_factory=list)
    technical_note_text: str = ""
    adjacent_proof: str = ""
    outreach_drafts: dict = field(default_factory=dict)
    qa_result: dict = field(default_factory=dict)

    db_company_id: int = 0
    db_packet_id: int = 0


# ---------------------------------------------------------------------------
# Main orchestration entry point
# ---------------------------------------------------------------------------

def run_harnessed_packet(
    company_name: str,
    lane: str = "ai_infra",
    profile_text: str = "",
) -> PacketRunContext:
    """Run the full packet workflow with every agent inside an AgentHarness."""
    settings = load_settings()
    router = ModelRouter(settings)
    logger = RunLogger(settings)
    approval_gate = ApprovalGate()

    ctx = PacketRunContext(company_name=company_name, lane=lane)
    db.init_db()

    # ---------- Step 0: Profile ----------
    profile_harness = _make_harness(
        "profile", TaskType.PROFILE_INGEST, router, _profile_runner,
    )
    profile_result = profile_harness.run(
        input_data=profile_text,
        context=HarnessContext(lane=lane),
        logger=logger,
    )
    ctx.user_profile = profile_result.output
    ctx.profile_raw = profile_text

    db_company_id = db.upsert_company(
        company_name,
        website="",
        lane=lane,
        fit_score=0,
    )
    ctx.db_company_id = db_company_id
    db.clear_company_generated_state(db_company_id)

    # ---------- Step 1: Company ----------
    company_harness = _make_harness(
        "company_sourcing", TaskType.COMPANY_SOURCING, router, _company_runner,
        validators=[_validate_company_output],
    )
    company_result = company_harness.run(
        input_data=(company_name, lane, ctx.user_profile),
        context=HarnessContext(lane=lane, run_id=logger.new_run_id()),
        logger=logger,
    )
    ctx.company_record = company_result.output.get("result", company_result.output)

    db.upsert_company(
        company_name,
        website=ctx.company_record.get("website", ""),
        lane=lane,
        fit_score=ctx.company_record.get("fit_score", 5),
        hiring_status=ctx.company_record.get("hiring_status", "unknown"),
        source_urls=json.dumps(company_result.output.get("source_urls", [])),
        status="researched",
    )

    # ---------- Step 2: Problems ----------
    problem_harness = _make_harness(
        "problem_discovery", TaskType.PROBLEM_DISCOVERY, router, _problem_runner,
        validators=[_validate_problems],
    )
    problem_result = problem_harness.run(
        input_data=(company_name, ctx.company_record, ctx.user_profile),
        context=HarnessContext(lane=lane),
        logger=logger,
    )
    ctx.problems = problem_result.output.get("result", problem_result.output).get("problems", [])

    for p in ctx.problems:
        db.insert_problem(
            ctx.db_company_id,
            title=p.get("title", ""),
            description=p.get("description", ""),
            source_urls=p.get("source_urls", []),
            relevance_score=p.get("relevance_score", 0),
        )

    # ---------- Step 3: People ----------
    top_problem = ctx.problems[0] if ctx.problems else {}
    people_harness = _make_harness(
        "people_sourcing", TaskType.PEOPLE_SOURCING, router, _people_runner,
        validators=[_validate_person_list],
    )
    people_result = people_harness.run(
        input_data=(company_name, top_problem, ctx.user_profile),
        context=HarnessContext(lane=lane),
        logger=logger,
    )
    ctx.people = people_result.output.get("result", people_result.output).get("people", [])

    for p in ctx.people:
        db.insert_person(
            ctx.db_company_id,
            name=p.get("name", ""),
            role=p.get("role", ""),
            linkedin_url=p.get("linkedin_url", ""),
            relevance_score=p.get("relevance_score", 0),
            relevance_reason=p.get("relevance_reason", ""),
            proximity=p.get("proximity", "engineer"),
        )

    # ---------- Step 4: Technical Note ----------
    note_harness = _make_harness(
        "technical_note", TaskType.TECHNICAL_NOTE, router, _note_runner,
        validators=[_validate_technical_note],
    )
    note_result = note_harness.run(
        input_data=(company_name, ctx.company_record, top_problem, ctx.user_profile),
        context=HarnessContext(lane=lane),
        logger=logger,
    )
    note_output = note_result.output.get("result", note_result.output)
    ctx.technical_note_text = note_output.get("technical_note", "")
    ctx.adjacent_proof = note_output.get("adjacent_proof", "")

    # ---------- Step 5: Outreach ----------
    top_person = ctx.people[0] if ctx.people else {}
    outreach_harness = _make_harness(
        "outreach_draft", TaskType.OUTREACH_DRAFT, router, _outreach_runner,
        validators=[_validate_outreach],
    )
    outreach_result = outreach_harness.run(
        input_data=(
            company_name, top_problem, top_person,
            ctx.technical_note_text, ctx.adjacent_proof, ctx.user_profile,
        ),
        context=HarnessContext(lane=lane),
        logger=logger,
    )
    ctx.outreach_drafts = outreach_result.output.get("result", outreach_result.output)

    # ---------- Step 6: QA ----------
    packet_for_qa = {
        "company": ctx.company_record,
        "problems": ctx.problems,
        "people": ctx.people,
        "technical_note": ctx.technical_note_text,
        "adjacent_proof": ctx.adjacent_proof,
        "outreach_drafts": ctx.outreach_drafts,
    }
    qa_harness = _make_harness(
        "qa_verification", TaskType.VERIFICATION, router, _qa_runner,
        validators=[_validate_qa],
    )
    qa_result = qa_harness.run(
        input_data=(packet_for_qa, ctx.user_profile),
        context=HarnessContext(lane=lane),
        logger=logger,
    )
    ctx.qa_result = qa_result.output.get("result", qa_result.output)

    # ---------- Store packet in DB ----------
    qa_score = ctx.qa_result.get("score", 0)
    packet_id = db.upsert_packet(
        ctx.db_company_id,
        company_fit=ctx.company_record.get("why", ""),
        open_problem=json.dumps(top_problem),
        people_map=json.dumps(ctx.people),
        technical_note=ctx.technical_note_text,
        adjacent_proof=ctx.adjacent_proof,
        outreach_drafts=json.dumps(ctx.outreach_drafts),
        verification=json.dumps(ctx.qa_result),
        qa_score=qa_score,
        qa_flags=json.dumps(ctx.qa_result.get("flags", [])),
        crm_status="prepared" if qa_score >= 6 else "needs_review",
    )
    ctx.db_packet_id = packet_id
    db.set_company_status(ctx.db_company_id, "packet_ready")

    # Save messages
    for variant, draft_text in ctx.outreach_drafts.items():
        person_id = None
        db_people = db.get_people(ctx.db_company_id)
        if db_people:
            person_id = db_people[0]["id"]
        db.insert_message(packet_id, person_id, variant, draft_text)

    return ctx


def report(ctx: PacketRunContext) -> str:
    """Print a human-readable summary of a finished packet run."""
    lines = [
        f"Packet complete: {ctx.company_name} ({ctx.lane})",
        f"  Profile: {ctx.user_profile.get('name', '?')}",
        f"  Company fit: {ctx.company_record.get('fit_score', '?')}/10",
        f"  Problems found: {len(ctx.problems)}",
        f"  People mapped: {len(ctx.people)}",
        f"  Technical note: {len(ctx.technical_note_text.split())} words",
        f"  Outreach drafts: {list(ctx.outreach_drafts.keys())}",
        f"  QA score: {ctx.qa_result.get('score', 0)}/10  passed={ctx.qa_result.get('passed', False)}",
        f"  DB company: {ctx.db_company_id}  packet: {ctx.db_packet_id}",
    ]
    return "\n".join(lines)
