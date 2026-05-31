"""
Action Agent — creates drafts, surfaces them for approval, and records outcomes.
External sends REQUIRE explicit human approval. This agent never sends autonomously.
"""
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
import db

console = Console()


def show_approval_gate(outreach_drafts: dict, company_name: str) -> str:
    """
    Show the user each outreach draft and ask for approval.
    Only marks messages as approved in the DB — never sends.
    Sending requires a separate, explicit action.
    """
    if not outreach_drafts:
        return "No drafts to review."

    approved_count = 0
    for variant, draft_text in outreach_drafts.items():
        if not draft_text.strip():
            continue
        word_count = len(draft_text.split())
        console.print(Panel(
            draft_text,
            title=f"[bold]{variant.upper()}[/bold] — {company_name} ({word_count} words)",
            expand=False,
        ))
        if Confirm.ask(f"  Approve this {variant} draft?", default=False):
            approved_count += 1
            console.print(f"  [green]Approved.[/green] Marked in DB — send manually or via --send flag.")
        else:
            console.print(f"  [dim]Skipped.[/dim]")

    return f"{approved_count}/{len(outreach_drafts)} drafts approved."


def mark_sent(message_id: int, channel: str) -> dict:
    """
    Record that a message was sent. Call only after user has manually sent it.
    """
    with db.conn() as c:
        c.execute("UPDATE messages SET status='sent' WHERE id=?", (message_id,))
        c.execute(
            "INSERT INTO send_events (message_id, sent_at, channel, status) VALUES (?,datetime('now'),?,?)",
            (message_id, channel, "sent")
        )
    return {"status": "recorded", "message_id": message_id, "channel": channel}


def record_reply(message_id: int, notes: str = ""):
    """Record that a reply was received. Updates follow-up status."""
    with db.conn() as c:
        c.execute("UPDATE messages SET status='replied' WHERE id=?", (message_id,))
        c.execute(
            "UPDATE follow_ups SET status='received_reply', notes=? WHERE message_id=?",
            (notes, message_id)
        )


def list_pending(company_name: str | None = None) -> list[dict]:
    """List all messages pending approval or follow-up."""
    return db.get_pending_approvals()
