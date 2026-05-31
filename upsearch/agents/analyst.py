"""
Analyst Agent — reads a post and writes a structured technical note.
Output: problem summary, gap, student contribution angle, fit score, contact type.
"""
import json
import os
import anthropic
from upsearch.sourcing.base import Post

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

SYSTEM = """You are an Analyst Agent in a cold outreach research pipeline for a CS student.

Given a post describing a technical problem, extract a structured analysis. Be honest about fit — not every post is a good outreach opportunity.

Respond with valid JSON only, no markdown fences. Schema:
{
  "problem": "2-sentence max description of the core technical problem",
  "gap": "1 sentence on why current solutions fall short",
  "contribution": "1-2 sentences on what a motivated CS student with ML/systems background could realistically contribute",
  "fit_score": <integer 1-10, 10 = ideal cold reach opportunity>,
  "contact_type": "engineer" | "researcher" | "skip",
  "reasoning": "1 sentence on why this fit score"
}

Penalize: vague questions, job postings, news sharing, no clear open problem.
Reward: someone actively stuck, asking for approaches, describing a real system issue."""


def run(post: Post, user_profile: str) -> dict | None:
    response = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=512,
        system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
        messages=[{
            "role": "user",
            "content": f"{post.to_text()}\n\n---\nStudent profile:\n{user_profile}",
        }],
    )

    text = response.content[0].text.strip()
    start, end = text.find("{"), text.rfind("}") + 1
    if start == -1 or end == 0:
        return None
    try:
        return json.loads(text[start:end])
    except json.JSONDecodeError:
        return None
