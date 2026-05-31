"""
Orchestrator — owns the task graph, state, agent dispatch, and approval gates.
Runs the full packet workflow for a single company.

Workflow:
  Profile -> Company -> Problem -> People -> TechnicalNote -> Outreach -> QA -> [Action]

Each agent receives a context dict and returns a structured result.
The orchestrator stores intermediate results in SQLite and surfaces them to the user.
"""
import json
from dataclasses import dataclass, field
from pathlib import Path
from rich.console import Console
from rich.rule import Rule
from rich.panel import Panel

import db
from agents import profile, company, problem, people, technical_note, outreach, qa, action

console = Console()

LANES = [
    "ai_infra",
    "inference_systems",
    "agentic_ai",
    "developer_tools",
    "data_platforms",
    "robotics_ai",
]


@dataclass
class PacketContext:
    """Shared context threaded through all agent calls for one company."""
    company_name: str
    lane: str = ""
    user_profile: dict = field(default_factory=dict)
    company_record: dict = field(default_factory=dict)
    problems: list = field(default_factory=list)
    people: list = field(default_factory=list)
    technical_note_text: str = ""
    adjacent_proof: str = ""
    outreach_drafts: dict = field(default_factory=dict)
    qa_result: dict = field(default_factory=dict)
    db_company_id: int = 0
    db_packet_id: int = 0


def _section(title: str):
    console.print(Rule(f"[cyan]{title}[/cyan]"))


def run_packet(company_name: str, lane: str = "ai_infra", auto_approve: bool = False) -> PacketContext:
    """
    Run the full packet workflow for one company.
    Returns the populated PacketContext with all agent outputs.
    """
    db.init_db()
    ctx = PacketContext(company_name=company_name, lane=lane)

    console.print(Panel(
        f"[bold cyan]Opportunity Intelligence OS[/bold cyan]\n"
        f"[dim]Building packet: {company_name}  |  Lane: {lane}[/dim]",
        expand=False,
    ))

    # ── Step 0: Load user profile ─────────────────────────────────────────────
    _section("Profile Agent")
    raw_profile = Path("profile.txt").read_text() if Path("profile.txt").exists() else ""
    with console.status("Loading and enriching user profile..."):
        ctx.user_profile = profile.run(raw_profile)
    console.print(f"  Profile loaded — {ctx.user_profile.get('name', 'unknown')} @ {ctx.user_profile.get('school', '?')}")

    # ── Step 1: Company research ──────────────────────────────────────────────
    _section("Company Agent")
    with console.status(f"Researching {company_name}..."):
        company_result = company.run(company_name, lane, ctx.user_profile)
    ctx.company_record = company_result["result"]

    company_id = db.upsert_company(
        company_name,
        website=ctx.company_record.get("website", ""),
        lane=lane,
        fit_score=ctx.company_record.get("fit_score", 0),
        hiring_status=ctx.company_record.get("hiring_status", "unknown"),
        source_urls=json.dumps(company_result.get("source_urls", [])),
        status="researched",
    )
    ctx.db_company_id = company_id
    console.print(f"  Fit score: [bold]{ctx.company_record.get('fit_score', '?')}/10[/bold]")
    console.print(f"  [dim]{ctx.company_record.get('why', '')}[/dim]")

    # ── Step 2: Problem extraction ────────────────────────────────────────────
    _section("Problem Agent")
    with console.status("Extracting open problems..."):
        problem_result = problem.run(company_name, ctx.company_record, ctx.user_profile)
    ctx.problems = problem_result["result"]["problems"]

    for p in ctx.problems:
        db.insert_problem(
            company_id,
            title=p["title"],
            description=p["description"],
            source_urls=p.get("source_urls", []),
            relevance_score=p.get("relevance_score", 0),
        )

    console.print(f"  Found [bold]{len(ctx.problems)}[/bold] open problems")
    for p in ctx.problems[:3]:
        console.print(f"  [dim]• {p['title']} ({p.get('relevance_score', 0)}/10)[/dim]")

    # ── Step 3: People mapping ────────────────────────────────────────────────
    _section("People Agent")
    top_problem = ctx.problems[0] if ctx.problems else {}
    with console.status("Finding and ranking relevant people..."):
        people_result = people.run(company_name, top_problem, ctx.user_profile)
    ctx.people = people_result["result"]["people"]

    for person in ctx.people:
        db.insert_person(
            company_id,
            name=person["name"],
            role=person["role"],
            linkedin_url=person.get("linkedin_url", ""),
            relevance_score=person.get("relevance_score", 0),
            relevance_reason=person.get("relevance_reason", ""),
            proximity=person.get("proximity", "engineer"),
        )

    console.print(f"  Mapped [bold]{len(ctx.people)}[/bold] people")
    for person in ctx.people[:3]:
        console.print(f"  [dim]• {person['name']} — {person['role']} ({person.get('proximity', '?')})[/dim]")

    # ── Step 4: Technical note ────────────────────────────────────────────────
    _section("Technical Note Agent")
    with console.status("Writing one-page technical note..."):
        note_result = technical_note.run(
            company_name, ctx.company_record, top_problem, ctx.user_profile
        )
    ctx.technical_note_text = note_result["result"]["technical_note"]
    ctx.adjacent_proof = note_result["result"]["adjacent_proof"]

    words = len(ctx.technical_note_text.split())
    console.print(f"  Technical note: [bold]{words} words[/bold]")
    console.print(f"  Adjacent proof: [dim]{ctx.adjacent_proof[:120]}...[/dim]")

    # ── Step 5: Outreach drafts ───────────────────────────────────────────────
    _section("Outreach Agent")
    top_person = ctx.people[0] if ctx.people else {}
    with console.status("Drafting outreach variants..."):
        outreach_result = outreach.run(
            company_name, top_problem, top_person,
            ctx.technical_note_text, ctx.adjacent_proof, ctx.user_profile
        )
    ctx.outreach_drafts = outreach_result["result"]

    for variant, draft in ctx.outreach_drafts.items():
        console.print(f"  [dim]{variant}: {len(draft.split())} words[/dim]")

    # ── Step 6: QA ────────────────────────────────────────────────────────────
    _section("QA Agent")
    packet_data = {
        "company": ctx.company_record,
        "problems": ctx.problems,
        "people": ctx.people,
        "technical_note": ctx.technical_note_text,
        "adjacent_proof": ctx.adjacent_proof,
        "outreach_drafts": ctx.outreach_drafts,
    }
    with console.status("Running QA checks..."):
        ctx.qa_result = qa.run(packet_data, ctx.user_profile)

    qa_score = ctx.qa_result.get("score", 0)
    qa_color = "green" if qa_score >= 7 else "yellow" if qa_score >= 5 else "red"
    console.print(f"  QA score: [{qa_color}][bold]{qa_score}/10[/bold][/{qa_color}]")
    for flag in ctx.qa_result.get("flags", [])[:5]:
        console.print(f"  [yellow]! {flag}[/yellow]")

    # ── Store packet ──────────────────────────────────────────────────────────
    packet_id = db.upsert_packet(
        company_id,
        company_fit=ctx.company_record.get("why", ""),
        open_problem=json.dumps(top_problem),
        people_map=json.dumps(ctx.people),
        technical_note=ctx.technical_note_text,
        adjacent_proof=ctx.adjacent_proof,
        outreach_drafts=json.dumps(ctx.outreach_drafts),
        verification=json.dumps(ctx.qa_result),
        qa_score=qa_score,
        qa_flags=json.dumps(ctx.qa_result.get("flags", [])),
        crm_status="prepared" if ctx.qa_result.get("passed") else "needs_review",
    )
    ctx.db_packet_id = packet_id
    db.set_company_status(company_id, "packet_ready")

    # Save messages to DB
    for variant, draft_text in ctx.outreach_drafts.items():
        person_id = None
        if top_person:
            db_people = db.get_people(company_id)
            if db_people:
                person_id = db_people[0]["id"]
        db.insert_message(packet_id, person_id, variant, draft_text)

    # ── Step 7: Action gate ───────────────────────────────────────────────────
    _section("Action Agent")
    if auto_approve:
        console.print("  [yellow]auto_approve=True — skipping approval gate[/yellow]")
    else:
        action_status = action.show_approval_gate(ctx.outreach_drafts, company_name)
        console.print(f"  [dim]{action_status}[/dim]")

    # ── Summary ───────────────────────────────────────────────────────────────
    console.print(Rule())
    console.print(f"[bold green]Packet complete:[/bold green] {company_name}")
    console.print(f"  Fit:      {ctx.company_record.get('fit_score', '?')}/10")
    console.print(f"  Problems: {len(ctx.problems)}")
    console.print(f"  People:   {len(ctx.people)}")
    console.print(f"  QA:       {qa_score}/10  ({'passed' if ctx.qa_result.get('passed') else 'needs review'})")
    console.print(f"  Packet ID: {packet_id}  |  DB: {db.DB_PATH}\n")

    return ctx
