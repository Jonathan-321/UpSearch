#!/usr/bin/env python3
"""
UpSearch — Research-to-Reach Pipeline
Orchestrates: Scout -> Analyst -> Strategist -> Writer -> W&B
Supports: Claude Opus 4.8 and DeepSeek (set MODEL_PROVIDER in .env)

Usage:
  python main.py                          # interactive
  python main.py --mode jobs --topic "ML inference engineer internship"
  python main.py --mode research --topic "speculative decoding"
"""
import os
import sys
import argparse
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import IntPrompt, Confirm
from rich.rule import Rule

from upsearch.agents import scout, analyst, strategist, writer
from upsearch import tracker, llm

console = Console()


def load_profile() -> str:
    p = Path("profile.txt")
    if p.exists():
        return p.read_text().strip()
    return "CS student interested in ML and systems, looking for internships and research roles."


def check_env():
    provider = llm.active_provider()
    if provider == "deepseek" and not os.environ.get("DEEPSEEK_API_KEY"):
        console.print("[red]Missing DEEPSEEK_API_KEY in .env[/red]")
        sys.exit(1)
    if provider == "claude" and not os.environ.get("ANTHROPIC_API_KEY"):
        console.print("[red]Missing ANTHROPIC_API_KEY in .env[/red]")
        sys.exit(1)
    if not os.environ.get("WANDB_API_KEY"):
        console.print("[red]Missing WANDB_API_KEY in .env[/red]")
        sys.exit(1)


def parse_args():
    parser = argparse.ArgumentParser(description="UpSearch — Research-to-Reach Pipeline")
    parser.add_argument("--mode", choices=["research", "jobs"], default=None,
                        help="Pipeline mode: 'jobs' for job search, 'research' for open problems")
    parser.add_argument("--topic", type=str, default=None,
                        help="Topic or role to search for")
    parser.add_argument("--pick", type=int, default=None,
                        help="Auto-select result number (skips interactive prompt)")
    parser.add_argument("--no-log", action="store_true",
                        help="Skip W&B logging prompt")
    return parser.parse_args()


def main():
    args = parse_args()
    provider = llm.active_provider()
    model = llm.active_model()

    console.print(Panel(
        f"[bold cyan]UpSearch[/bold cyan]  |  Scout -> Analyst -> Strategist -> Writer\n"
        f"[dim]Model: {model}  |  Provider: {provider}[/dim]",
        expand=False,
    ))

    check_env()
    profile = load_profile()

    mode = args.mode or input("\nMode [research/jobs] (default: jobs): ").strip() or "jobs"
    if mode not in ("research", "jobs"):
        mode = "jobs"

    topic = args.topic or input("Topic or role: ").strip()
    if not topic:
        console.print("[red]No topic provided.[/red]")
        sys.exit(1)

    # ── Stage 1: Scout Agent ──────────────────────────────────────────────────
    console.print(Rule(f"[cyan]Stage 1: Scout Agent[/cyan] [dim]({provider})[/dim]"))
    console.print("[dim]Deciding what to search and fetching posts...[/dim]")

    search_topic = f"{topic} {'job opening hiring internship' if mode == 'jobs' else 'open problem'}"

    with console.status(f"Scout Agent running via {provider}..."):
        posts = scout.run(search_topic)

    if not posts:
        console.print("[red]Scout found nothing. Try a different topic.[/red]")
        sys.exit(1)

    console.print(f"Scout found [bold]{len(posts)}[/bold] posts.\n")

    # ── Stage 2: Analyst Agent ────────────────────────────────────────────────
    console.print(Rule(f"[cyan]Stage 2: Analyst Agent[/cyan] [dim]({provider})[/dim]"))
    console.print("[dim]Scoring each result for fit and extracting the angle...[/dim]")

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

    if args.pick is not None:
        choice = args.pick
    else:
        choice = IntPrompt.ask("\nPick a result to build outreach for", default=1)
    if choice < 1 or choice > len(results[:8]):
        console.print("[red]Invalid choice.[/red]")
        sys.exit(1)

    post, analysis = results[choice - 1]

    console.print(f"\n[bold]Problem / Role:[/bold] {analysis.get('problem', '')}")
    console.print(f"[bold]Gap / Need:[/bold] {analysis.get('gap', '')}")
    console.print(f"[bold]Your angle:[/bold] {analysis.get('contribution', '')}")
    console.print(f"[dim]{analysis.get('reasoning', '')}[/dim]\n")

    # ── Stage 3: Strategist Agent ─────────────────────────────────────────────
    console.print(Rule(f"[cyan]Stage 3: Strategist Agent[/cyan] [dim]({provider})[/dim]"))

    with console.status("Strategist Agent deciding who to contact and how..."):
        strategy = strategist.run(post, analysis, profile)

    if not strategy:
        console.print("[red]Strategist failed. Try again.[/red]")
        sys.exit(1)

    console.print(f"[bold]Target:[/bold]     {strategy.get('target_role', '')}")
    console.print(f"[bold]Hook:[/bold]       {strategy.get('hook', '')}")
    console.print(f"[bold]Channel:[/bold]    {strategy.get('channel', '')}")
    console.print(f"[bold]Icebreaker:[/bold] {strategy.get('icebreaker', '')}\n")

    # ── Stage 4: Writer Agent ─────────────────────────────────────────────────
    console.print(Rule(f"[cyan]Stage 4: Writer Agent[/cyan] [dim]({provider})[/dim]"))

    with console.status("Writer Agent drafting the email..."):
        draft = writer.run(post, analysis, strategy, profile)

    word_count = len(draft.split())
    console.print(Panel(
        draft,
        title=f"[bold green]Draft Email[/bold green] [dim]({word_count} words)[/dim]",
        expand=False,
    ))

    if word_count > 200:
        console.print(f"[yellow]Warning: {word_count} words — edit before sending.[/yellow]")

    # ── Stage 5: W&B Logging ──────────────────────────────────────────────────
    console.print(Rule("[cyan]Stage 5: W&B Tracker[/cyan]"))

    if not args.no_log and Confirm.ask("Log this run to W&B?", default=True):
        sent = Confirm.ask("Mark as already sent?", default=False)
        with console.status("Logging to W&B..."):
            run_id = tracker.log(post, analysis, strategy, draft, sent=sent)
        console.print(f"[green]Logged.[/green] W&B run ID: [bold]{run_id}[/bold]")
        console.print("[dim]Track reply rates at https://wandb.ai/home[/dim]")

    # ── Next steps ────────────────────────────────────────────────────────────
    console.print(Rule())
    console.print("[bold cyan]Next steps:[/bold cyan]")
    if mode == "jobs":
        console.print("  1. Find the hiring manager or a team engineer on LinkedIn (not the recruiter)")
        console.print("  2. Edit the draft — keep it under 200 words")
        console.print(f"  3. Send from your school email")
        console.print("  4. If no reply in 7 days, one LinkedIn follow-up")
        console.print("  5. Update the W&B run when you get a reply\n")
    else:
        console.print("  1. Find the researcher/engineer who posted (LinkedIn or GitHub)")
        console.print("  2. Edit the draft — keep it under 200 words, stay specific")
        console.print(f"  3. Send via {strategy.get('channel', 'email')}")
        console.print("  4. One follow-up after 7 days if no reply\n")


if __name__ == "__main__":
    main()
