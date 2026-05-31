#!/usr/bin/env python3
"""
UpSearch — Research-to-Reach Pipeline
Orchestrates: Scout → Analyst → Strategist → Writer → W&B
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, IntPrompt, Confirm
from rich.rule import Rule
from rich import print as rprint

from upsearch.agents import scout, analyst, strategist, writer
from upsearch import tracker

console = Console()


def load_profile() -> str:
    p = Path("profile.txt")
    if p.exists():
        return p.read_text().strip()
    return "CS student interested in ML and systems."


def check_env():
    missing = []
    if not os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_API_KEY") == "your_anthropic_key_here":
        missing.append("ANTHROPIC_API_KEY")
    if not os.environ.get("WANDB_API_KEY"):
        missing.append("WANDB_API_KEY")
    if missing:
        console.print(f"[red]Missing in .env: {', '.join(missing)}[/red]")
        sys.exit(1)


def main():
    console.print(Panel(
        "[bold cyan]UpSearch[/bold cyan]  |  Scout → Analyst → Strategist → Writer\n"
        "[dim]AI-powered research-to-reach pipeline[/dim]",
        expand=False,
    ))

    check_env()
    profile = load_profile()

    topic = Prompt.ask("\n[bold]What problem space do you want to explore?[/bold]")

    # ── Stage 1: Scout Agent ──────────────────────────────────────────────────
    console.print(Rule("[cyan]Stage 1: Scout Agent[/cyan]"))
    console.print("[dim]Claude is deciding what to search and fetching posts...[/dim]")

    with console.status("Scout Agent running..."):
        posts = scout.run(topic)

    if not posts:
        console.print("[red]Scout found nothing. Try a different topic.[/red]")
        sys.exit(1)

    console.print(f"Scout found [bold]{len(posts)}[/bold] posts.\n")

    # ── Stage 2: Analyst Agent ────────────────────────────────────────────────
    console.print(Rule("[cyan]Stage 2: Analyst Agent[/cyan]"))
    console.print("[dim]Scoring each post for fit and extracting the technical angle...[/dim]")

    results = []
    with console.status("Analyst Agent running..."):
        for post in posts:
            analysis = analyst.run(post, profile)
            if analysis and analysis.get("fit_score", 0) >= 5 and analysis.get("contact_type") != "skip":
                results.append((post, analysis))

    results.sort(key=lambda x: x[1].get("fit_score", 0), reverse=True)

    if not results:
        console.print("[yellow]No high-fit results (score >= 5). Try a more specific topic.[/yellow]")
        sys.exit(0)

    # Show ranked results
    table = Table(show_header=True, header_style="bold magenta", expand=False)
    table.add_column("#", width=3)
    table.add_column("Fit", width=4)
    table.add_column("Source", width=10)
    table.add_column("Title", width=55)
    table.add_column("Contact", width=12)

    for i, (post, analysis) in enumerate(results[:8]):
        fit = analysis.get("fit_score", 0)
        color = "green" if fit >= 8 else "yellow" if fit >= 6 else "white"
        table.add_row(
            str(i + 1),
            f"[{color}]{fit}[/{color}]",
            post.source,
            post.title[:53],
            analysis.get("contact_type", "?"),
        )

    console.print(table)

    choice = IntPrompt.ask("\nPick a result to build outreach for", default=1)
    if choice < 1 or choice > len(results[:8]):
        console.print("[red]Invalid choice.[/red]")
        sys.exit(1)

    post, analysis = results[choice - 1]

    console.print(f"\n[bold]Problem:[/bold] {analysis.get('problem', '')}")
    console.print(f"[bold]Gap:[/bold] {analysis.get('gap', '')}")
    console.print(f"[bold]Your angle:[/bold] {analysis.get('contribution', '')}")
    console.print(f"[dim]Reasoning: {analysis.get('reasoning', '')}[/dim]\n")

    # ── Stage 3: Strategist Agent ─────────────────────────────────────────────
    console.print(Rule("[cyan]Stage 3: Strategist Agent[/cyan]"))

    with console.status("Strategist Agent deciding who to contact and how..."):
        strategy = strategist.run(post, analysis, profile)

    if not strategy:
        console.print("[red]Strategist failed. Try again.[/red]")
        sys.exit(1)

    console.print(f"[bold]Target:[/bold] {strategy.get('target_role', '')}")
    console.print(f"[bold]Hook:[/bold] {strategy.get('hook', '')}")
    console.print(f"[bold]Channel:[/bold] {strategy.get('channel', '')}")
    console.print(f"[bold]Icebreaker:[/bold] {strategy.get('icebreaker', '')}\n")

    # ── Stage 4: Writer Agent ─────────────────────────────────────────────────
    console.print(Rule("[cyan]Stage 4: Writer Agent[/cyan]"))

    with console.status("Writer Agent drafting the email..."):
        draft = writer.run(post, analysis, strategy, profile)

    word_count = len(draft.split())
    console.print(Panel(
        draft,
        title=f"[bold green]Draft Email[/bold green] [dim]({word_count} words)[/dim]",
        expand=False,
    ))

    if word_count > 200:
        console.print(f"[yellow]Warning: {word_count} words — over the 200-word limit. Edit before sending.[/yellow]")

    # ── Stage 5: W&B Logging ──────────────────────────────────────────────────
    console.print(Rule("[cyan]Stage 5: W&B Tracker[/cyan]"))

    if Confirm.ask("Log this run to W&B?", default=True):
        sent = Confirm.ask("Mark as already sent?", default=False)
        with console.status("Logging to W&B..."):
            run_id = tracker.log(post, analysis, strategy, draft, sent=sent)
        console.print(f"[green]Logged.[/green] W&B run ID: [bold]{run_id}[/bold]")
        console.print("[dim]Track reply rates at https://wandb.ai/home[/dim]")

    # ── Next steps ────────────────────────────────────────────────────────────
    console.print(Rule())
    console.print("[bold cyan]Next steps:[/bold cyan]")
    console.print(f"  1. Find the right person at the company (engineer/researcher, not recruiter)")
    console.print(f"  2. Edit the draft if needed — keep it under 200 words")
    console.print(f"  3. Send from your school email or {strategy.get('channel', 'email')}")
    console.print(f"  4. If no reply in 7 days, one LinkedIn follow-up")
    console.print(f"  5. Update the W&B run when you get a reply\n")


if __name__ == "__main__":
    main()
