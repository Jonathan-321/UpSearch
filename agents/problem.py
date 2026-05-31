"""
Problem Agent — extracts current open technical problems from public sources.
Output: ranked list of specific, source-backed problem briefs.
"""
import json
from upsearch import llm
from upsearch.sourcing import hackernews, reddit

SYSTEM = """You are a Problem Agent. Given a company brief and public source material,
identify specific open technical problems this team appears to care about.

For each problem, provide evidence (source URL or signal). Do not invent problems.
Only list problems with real public signal.

Respond with valid JSON only:
{
  "problems": [
    {
      "title": "Concise problem name",
      "description": "2-3 sentence technical description of the problem",
      "source_urls": ["url1", "url2"],
      "source_signal": "what public signal indicates this is a real problem",
      "relevance_score": <1-10>,
      "contribution_surface": "where a student could realistically contribute"
    }
  ]
}"""


def run(company_name: str, company_record: dict, user_profile: dict) -> dict:
    tech_stack = ", ".join(company_record.get("tech_stack", []))
    what_they_do = company_record.get("what_they_do", "")

    hn_posts = hackernews.search(f"{company_name} problems engineering", limit=5)
    reddit_posts = reddit.search(f"{company_name} technical issues", limit=3)
    all_posts = hn_posts + reddit_posts

    source_text = "\n".join(
        f"[{p.source}] {p.title}\n{p.body[:300]}\nURL: {p.url}"
        for p in all_posts[:6]
    ) if all_posts else "No recent public discussions found."

    text = llm.complete(
        system=SYSTEM,
        user=(
            f"Company: {company_name}\n"
            f"What they do: {what_they_do}\n"
            f"Tech stack: {tech_stack}\n\n"
            f"Public signal:\n{source_text}\n\n"
            f"Student skills: {', '.join(user_profile.get('skills', []))}"
        ),
        max_tokens=1024,
    )
    start, end = text.find("{"), text.rfind("}") + 1
    try:
        result = json.loads(text[start:end]) if start != -1 else {"problems": []}
    except json.JSONDecodeError:
        result = {"problems": []}

    return {
        "result": result,
        "source_urls": [p.url for p in all_posts],
        "confidence": 0.65 if all_posts else 0.4,
        "assumptions": ["Problem list based on public signal; direct company contact may reveal different priorities"],
        "next_action": "run_people_agent",
    }
