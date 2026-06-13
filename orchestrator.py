"""
Orchestrator — owns the task graph, state, agent dispatch, and approval gates.
Runs the full packet workflow for a single company.

This module is a thin CLI adapter over :func:`upsearch.orchestrator_service.run_pipeline`.
The unified pipeline contract lives in ``orchestrator_service.py``.
"""
import asyncio
import json
from dataclasses import dataclass, field
from pathlib import Path
from rich.console import Console
from rich.rule import Rule
from rich.panel import Panel

from upsearch.orchestrator_service import run_pipeline as _run_pipeline

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


def run_packet(
    company_name: str, lane: str = "ai_infra", auto_approve: bool = False
) -> PacketContext:
    """
    Run the full packet workflow for one company (thin CLI adapter).

    Delegates to :func:`upsearch.orchestrator_service.run_pipeline` and
    wraps the result with rich console output and the backward-compatible
    :class:`PacketContext` return type.
    """
    import db as _db

    _db.init_db()
    raw_profile = (
        Path("profile.txt").read_text() if Path("profile.txt").exists() else ""
    )

    console.print(
        Panel(
            f"[bold cyan]Opportunity Intelligence OS[/bold cyan]\n"
            f"[dim]Building packet: {company_name}  |  Lane: {lane}[/dim]",
            expand=False,
        )
    )

    _section("Profile Agent")
    with console.status("Loading and enriching user profile..."):
        result = asyncio.run(_run_pipeline(company_name, lane, raw_profile))

    ctx = PacketContext(
        company_name=company_name,
        lane=lane,
        user_profile=result.profile,
        company_record=result.company_record,
        problems=result.problems,
        people=result.people,
        technical_note_text=result.technical_note_text,
        adjacent_proof=result.adjacent_proof,
        outreach_drafts=result.outreach_drafts,
        qa_result=result.qa_result,
        db_company_id=result.db_company_id,
        db_packet_id=result.packet_id,
    )
    console.print(
        f"  Profile loaded \u2014 {ctx.user_profile.get('name', 'unknown')} @ {ctx.user_profile.get('school', '?')}"
    )

    _section("Company Agent")
    console.print(
        f"  Fit score: [bold]{ctx.company_record.get('fit_score', '?')}/10[/bold]"
    )
    console.print(f"  [dim]{ctx.company_record.get('why', '')}[/dim]")

    _section("Problem Agent")
    console.print(f"  Found [bold]{len(ctx.problems)}[/bold] open problems")
    for p in ctx.problems[:3]:
        console.print(
            f"  [dim]\u2022 {p['title']} ({p.get('relevance_score', 0)}/10)[/dim]"
        )

    _section("People Agent")
    console.print(f"  Mapped [bold]{len(ctx.people)}[/bold] people")
    for person in ctx.people[:3]:
        console.print(
            f"  [dim]\u2022 {person['name']} \u2014 {person.get('role', '?')} ({person.get('proximity', '?')})[/dim]"
        )

    _section("Technical Note Agent")
    words = len(ctx.technical_note_text.split())
    console.print(f"  Technical note: [bold]{words} words[/bold]")
    console.print(f"  Adjacent proof: [dim]{ctx.adjacent_proof[:120]}...[/dim]")

    _section("Outreach Agent")
    for variant, draft in ctx.outreach_drafts.items():
        console.print(f"  [dim]{variant}: {len(draft.split())} words[/dim]")

    _section("QA Agent")
    qa_score = ctx.qa_result.get("score", 0)
    qa_color = (
        "green" if qa_score >= 7 else "yellow" if qa_score >= 5 else "red"
    )
    console.print(
        f"  QA score: [{qa_color}][bold]{qa_score}/10[/bold][/{qa_color}]"
    )
    for flag in ctx.qa_result.get("flags", [])[:5]:
        console.print(f"  [yellow]! {flag}[/yellow]")

    _section("Action Agent")
    if auto_approve:
        console.print(
            "  [yellow]auto_approve=True \u2014 skipping approval gate[/yellow]"
        )
    else:
        from agents import action as _action

        action_status = _action.show_approval_gate(
            ctx.outreach_drafts, company_name
        )
        console.print(f"  [dim]{action_status}[/dim]")

    _section("Summary")
    console.print(f"[bold green]Packet complete:[/bold green] {company_name}")
    console.print(
        f"  Fit:      {ctx.company_record.get('fit_score', '?')}/10"
    )
    console.print(f"  Problems: {len(ctx.problems)}")
    console.print(f"  People:   {len(ctx.people)}")
    console.print(
        f"  QA:       {qa_score}/10  ({'passed' if ctx.qa_result.get('passed') else 'needs review'})"
    )
    console.print(f"  Packet ID: {result.packet_id}  |  Run ID: {result.run_id}\n")

    return ctx
