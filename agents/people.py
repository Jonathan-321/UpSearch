"""
People Agent — finds and ranks relevant people at the target company.
Proximity types: engineer, researcher, founder, FDE, PM, recruiter, hiring_manager.
"""
import json
from upsearch import llm
from upsearch.sourcing import hackernews

SYSTEM = """You are a People Agent for an Opportunity Intelligence OS. Given a company and problem,
identify 3-6 people who are most worth reaching out to.

Rank by: proximity to the problem, public signal, and likelihood of a useful conversation.
Only list people you have actual public signal for (HN username, GitHub profile, LinkedIn, Twitter).
Mark guessed profiles with (source: inferred from role) — never fabricate URLs.

Respond with valid JSON only:
{
  "people": [
    {
      "name": "Full Name or HN username",
      "role": "e.g. ML Infrastructure Engineer",
      "proximity": "engineer | researcher | founder | FDE | PM | hiring_manager | recruiter",
      "linkedin_url": "https://linkedin.com/in/... or null",
      "github_url": "https://github.com/... or null",
      "twitter_url": "https://x.com/... or null",
      "relevance_score": <1-10>,
      "relevance_reason": "1 sentence on why this person and why now",
      "source": "where you found this person",
      "outreach_note": "one thing to reference in the opening line"
    }
  ]
}"""


def run(company_name: str, problem: dict, user_profile: dict) -> dict:
    problem_title = problem.get("title", "")
    hn_posts = hackernews.search(f"{company_name} engineer researcher", limit=5)
    source_text = "\n".join(
        f"Author: {p.author} | {p.title}\nURL: {p.url}" for p in hn_posts
    ) if hn_posts else "No HN signal found."

    text = llm.complete(
        system=SYSTEM,
        user=(
            f"Company: {company_name}\n"
            f"Problem focus: {problem_title}\n\n"
            f"Public signal (HN discussions with authors):\n{source_text}\n\n"
            f"Student profile: {', '.join(user_profile.get('skills', []))}\n"
            f"Note: include founders/engineers from {company_name} GitHub org if known"
        ),
        max_tokens=1024,
    )
    start, end = text.find("{"), text.rfind("}") + 1
    try:
        result = json.loads(text[start:end]) if start != -1 else {"people": []}
    except json.JSONDecodeError:
        result = {"people": []}

    return {
        "result": result,
        "source_urls": [p.url for p in hn_posts],
        "confidence": 0.55,
        "assumptions": [
            "LinkedIn/GitHub URLs need manual verification before use",
            "Relevance scores based on public signal only",
        ],
        "next_action": "run_technical_note_agent",
    }
