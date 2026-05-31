"""
Analyst Agent — reads a post and writes a structured analysis.
Handles both research problems and job/hiring opportunities.
"""
import json
from upsearch.sourcing.base import Post
from upsearch import llm

SYSTEM = """You are an Analyst Agent in a research-to-reach pipeline for a CS student looking for internships, research roles, and collaboration opportunities.

Given a post, extract a structured analysis. The post may describe:
- An open technical problem (research/engineering challenge)
- A company or team that is hiring or has openings
- A project looking for contributors

Be honest about fit — not every post is worth cold-reaching.

Respond with valid JSON only, no markdown fences:
{
  "problem": "2-sentence description of the core problem, need, or opportunity",
  "gap": "1 sentence on what is missing — a skill, a contributor, an approach, or an open role",
  "contribution": "1-2 sentences on what this specific student could realistically offer",
  "fit_score": <integer 1-10>,
  "contact_type": "engineer" | "researcher" | "hiring_manager" | "skip",
  "reasoning": "1 sentence explaining the fit score"
}

Fit score guide:
- 9-10: direct opening or active problem perfectly matched to student background
- 7-8: strong signal, student has relevant angle
- 5-6: possible, but indirect or competitive
- 1-4: weak signal, skip or score as skip

Penalize: old posts, vague roles, no clear person to contact.
Reward: specific technical need, team building something relevant, recent activity."""


def run(post: Post, user_profile: str) -> dict | None:
    text = llm.complete(
        system=SYSTEM,
        user=f"{post.to_text()}\n\n---\nStudent profile:\n{user_profile}",
        max_tokens=512,
    )
    start, end = text.find("{"), text.rfind("}") + 1
    if start == -1 or end == 0:
        return None
    try:
        return json.loads(text[start:end])
    except json.JSONDecodeError:
        return None
