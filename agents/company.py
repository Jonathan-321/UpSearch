"""
Company Agent — researches a company and scores it for technical fit, hiring relevance, and reachability.
Uses LLM knowledge + public sources (HN, GitHub activity).
"""
import json
from upsearch import llm
from upsearch.sourcing import hackernews

SYSTEM = """You are a Company Agent for an Opportunity Intelligence OS. Given a company name and target lane,
produce a structured company brief based on your knowledge and any provided source material.

Respond with valid JSON only:
{
  "name": "...",
  "website": "...",
  "lane": "...",
  "fit_score": <1-10>,
  "what_they_do": "1-2 sentence description of the product and tech stack",
  "why": "why this company is worth reaching out to for a student in this lane",
  "hiring_status": "actively_hiring | unknown | limited",
  "sponsorship_notes": "any notes on H1B sponsorship or internship programs",
  "open_source": ["repo1", "repo2"],
  "tech_stack": ["Python", "CUDA", "Kubernetes"],
  "recent_signal": "recent relevant activity — blog post, paper, HN discussion",
  "assumptions": ["assumption1"]
}

Be honest about uncertainty. Mark guesses with (assumed)."""


def run(company_name: str, lane: str, user_profile: dict) -> dict:
    # Enrich with HN discussions about this company
    hn_posts = hackernews.search(f"{company_name} {lane}", limit=3)
    hn_context = "\n".join(
        f"- [{p.source}] {p.title} ({p.score} pts)" for p in hn_posts
    ) if hn_posts else "No recent HN activity found."

    user_ctx = (
        f"Student interests: {', '.join(user_profile.get('interests', []))}\n"
        f"Skills: {', '.join(user_profile.get('skills', []))}"
    )

    text = llm.complete(
        system=SYSTEM,
        user=(
            f"Company: {company_name}\nLane: {lane}\n\n"
            f"Recent HN signal:\n{hn_context}\n\n"
            f"Student context:\n{user_ctx}"
        ),
        max_tokens=800,
    )
    start, end = text.find("{"), text.rfind("}") + 1
    try:
        result = json.loads(text[start:end]) if start != -1 else {}
    except json.JSONDecodeError:
        result = {"name": company_name, "fit_score": 5, "why": "Parse error"}

    return {
        "result": result,
        "source_urls": [p.url for p in hn_posts],
        "confidence": 0.7,
        "assumptions": result.get("assumptions", []),
        "next_action": "run_problem_agent",
    }
