#!/usr/bin/env python3
"""
Opportunity Intelligence OS — CLI entry point.

Commands:
  python os_main.py packet  --company baseten --lane ai_infra
  python os_main.py list    [--status packet_ready]
  python os_main.py show    --company baseten
  python os_main.py approve [--company baseten]
  python os_main.py crm     [--due-today]
"""
import argparse
import json
import sys
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

load_dotenv()

import db
from orchestrator import run_packet

console = Console()

LANES = {
    "ai_infra":         "AI Infrastructure",
    "inference":        "Inference Systems",
    "agentic":          "Agentic AI",
    "dev_tools":        "Developer Tools",
    "data":             "Data Platforms",
    "robotics":         "Robotics AI",
}


def cmd_packet(args):
    """Run the full packet workflow for one company."""
    lane = args.lane or "ai_infra"
    ctx = run_packet(args.company, lane=lane, auto_approve=args.yes)
    console.print(f"\n[bold green]Done.[/bold green] Packet saved to DB (ID {ctx.db_packet_id}).")
    console.print(f"Run [bold]python os_main.py show --company {args.company}[/bold] to review.")


def cmd_list(args):
    """List all companies tracked in the CRM."""
    db.init_db()
    companies = db.list_companies(status=args.status)
    if not companies:
        console.print("[dim]No companies found. Run: python os_main.py packet --company <name>[/dim]")
        return

    table = Table(show_header=True, header_style="bold magenta", expand=False)
    table.add_column("Company", width=20)
    table.add_column("Lane", width=16)
    table.add_column("Fit", width=5)
    table.add_column("Status", width=16)
    table.add_column("Hiring", width=14)

    for c in companies:
        fit = c.get("fit_score", 0)
        color = "green" if fit >= 8 else "yellow" if fit >= 6 else "white"
        table.add_row(
            c["name"],
            c.get("lane", "?"),
            f"[{color}]{fit}[/{color}]",
            c.get("status", "?"),
            c.get("hiring_status", "?"),
        )
    console.print(table)
    console.print(f"\n[dim]{len(companies)} companies total.[/dim]")


def cmd_show(args):
    """Show the full packet for a company."""
    db.init_db()
    company = db.get_company(args.company)
    if not company:
        console.print(f"[red]No company '{args.company}' in DB. Run packet first.[/red]")
        sys.exit(1)

    packet = db.get_packet(company["id"])
    problems = db.get_problems(company["id"])
    people = db.get_people(company["id"])

    console.print(Panel(
        f"[bold cyan]{company['name']}[/bold cyan]  |  {company.get('lane', '?')}  |  "
        f"Fit: [bold]{company.get('fit_score', '?')}/10[/bold]  |  "
        f"Status: {packet.get('crm_status', '?') if packet else 'no packet'}",
        expand=False,
    ))

    if packet:
        console.print(f"\n[bold]Company fit:[/bold] {packet.get('company_fit', '—')}")
        console.print(f"[bold]Adjacent proof:[/bold] {packet.get('adjacent_proof', '—')}\n")

    if problems:
        console.print("[bold]Open Problems:[/bold]")
        for p in problems[:3]:
            console.print(f"  [{p.get('relevance_score', 0)}/10] {p['title']}")

    if people:
        console.print("\n[bold]People:[/bold]")
        for person in people[:5]:
            linkedin = person.get("linkedin_url", "")
            link_str = f" — {linkedin}" if linkedin else ""
            console.print(f"  [{person.get('relevance_score', 0)}/10] {person['name']} | {person.get('role', '?')}{link_str}")

    if packet and packet.get("technical_note"):
        console.print("\n[bold]Technical Note:[/bold]")
        console.print(packet["technical_note"][:800] + "...\n")

    if packet:
        drafts = json.loads(packet.get("outreach_drafts", "{}"))
        for variant, draft_text in drafts.items():
            if draft_text.strip():
                word_count = len(draft_text.split())
                console.print(Panel(
                    draft_text[:600] + ("..." if len(draft_text) > 600 else ""),
                    title=f"[bold]{variant}[/bold] ({word_count} words)",
                    expand=False,
                ))


def cmd_approve(args):
    """Review and approve pending message drafts."""
    db.init_db()
    pending = db.get_pending_approvals()
    if not pending:
        console.print("[dim]No pending drafts.[/dim]")
        return

    from rich.prompt import Confirm
    for msg in pending:
        console.print(Panel(
            msg["content"],
            title=f"[bold]Message #{msg['id']}[/bold] | {msg.get('variant', '?')} | "
                  f"{msg.get('person_name', 'unknown person')} ({len(msg['content'].split())} words)",
            expand=False,
        ))
        if Confirm.ask("Approve this draft?", default=False):
            db.approve_message(msg["id"])
            console.print(f"[green]Approved #{msg['id']}.[/green] Send manually when ready.")
        else:
            console.print("[dim]Skipped.[/dim]")


def cmd_crm(args):
    """Show CRM status: due follow-ups, pending approvals, pipeline health."""
    db.init_db()
    follow_ups = db.get_due_follow_ups()
    pending = db.get_pending_approvals()
    companies = db.list_companies()

    # Status distribution
    status_counts: dict[str, int] = {}
    for c in companies:
        s = c.get("status", "unknown")
        status_counts[s] = status_counts.get(s, 0) + 1

    console.print("[bold]CRM Overview[/bold]")
    for status, count in status_counts.items():
        console.print(f"  {status}: {count}")

    if pending:
        console.print(f"\n[yellow]{len(pending)} draft(s) pending approval[/yellow] — run: python os_main.py approve")

    if follow_ups:
        console.print(f"\n[bold red]{len(follow_ups)} follow-up(s) due today:[/bold red]")
        for f in follow_ups:
            console.print(f"  Message #{f['message_id']} ({f['variant']}) — due {f['due_date']}")
    else:
        console.print("\n[green]No follow-ups due today.[/green]")


def main():
    parser = argparse.ArgumentParser(
        description="Opportunity Intelligence OS",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    # packet
    p_packet = sub.add_parser("packet", help="Run full packet workflow for a company")
    p_packet.add_argument("--company", required=True, help="Company name")
    p_packet.add_argument("--lane", default="ai_infra", choices=list(LANES.keys()))
    p_packet.add_argument("--yes", action="store_true", help="Skip approval prompts")

    # list
    p_list = sub.add_parser("list", help="List tracked companies")
    p_list.add_argument("--status", default=None, help="Filter by status")

    # show
    p_show = sub.add_parser("show", help="Show packet for a company")
    p_show.add_argument("--company", required=True)

    # approve
    sub.add_parser("approve", help="Review and approve pending drafts")

    # crm
    sub.add_parser("crm", help="CRM status overview and follow-ups")

    args = parser.parse_args()

    dispatch = {
        "packet":  cmd_packet,
        "list":    cmd_list,
        "show":    cmd_show,
        "approve": cmd_approve,
        "crm":     cmd_crm,
    }
    dispatch[args.cmd](args)


if __name__ == "__main__":
    main()
