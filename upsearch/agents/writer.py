"""
Writer Agent — drafts the cold email using the analyst and strategist outputs.
Rules: ≤200 words, student voice, no dashes, no buzzwords, one icebreaker.
"""
import os
import anthropic
from upsearch.sourcing.base import Post

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

SYSTEM = """You are a Writer Agent that drafts cold outreach emails for a CS student.

Hard rules:
- Subject line on the first line, then one blank line, then the email body
- 200 words maximum for the body (not counting subject line)
- Write like a human student: direct, specific, a little informal
- No em-dashes, no en-dashes, no buzzwords ("leverage", "synergy", "excited to connect")
- Open with the icebreaker — something specific they wrote or built, not a generic compliment
- One clear, low-friction ask at the end (a 15-minute call, one specific question)
- Sign off with first name only

The goal is a reply, not to impress. Specificity beats polish."""


def run(post: Post, analysis: dict, strategy: dict, user_profile: str) -> str:
    import json

    payload = (
        f"Post: {post.title}\nURL: {post.url}\n\n"
        f"Technical analysis:\n- Problem: {analysis.get('problem', '')}\n"
        f"- Gap: {analysis.get('gap', '')}\n"
        f"- My angle: {analysis.get('contribution', '')}\n\n"
        f"Strategy:\n- Target: {strategy.get('target_role', '')}\n"
        f"- Hook: {strategy.get('hook', '')}\n"
        f"- Icebreaker: {strategy.get('icebreaker', '')}\n\n"
        f"Student profile:\n{user_profile}"
    )

    response = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=600,
        system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": payload}],
    )

    return response.content[0].text.strip()
