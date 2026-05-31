"""
Problem Agent — extracts current open technical problems from public sources.
Output: ranked list of specific, source-backed problem briefs.
"""
from upsearch import llm
from upsearch.json_utils import parse_model_json_object
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
    result = parse_model_json_object(text, {"problems": []})
    if not result.get("problems"):
        result = {"problems": [_fallback_problem(company_name, company_record, all_posts)]}

    return {
        "result": result,
        "source_urls": [p.url for p in all_posts],
        "confidence": 0.65 if all_posts else 0.4,
        "assumptions": ["Problem list based on public signal; direct company contact may reveal different priorities"],
        "next_action": "run_people_agent",
    }


def _fallback_problem(company_name: str, company_record: dict, public_posts: list) -> dict:
    """Conservative fallback when the model output cannot be parsed.

    This prevents a malformed JSON character from erasing the whole packet. The
    fallback is intentionally framed as a candidate problem and carries the
    source uncertainty forward for QA/human review.
    """
    what_they_do = company_record.get("what_they_do", "")
    tech_stack = ", ".join(company_record.get("tech_stack", [])[:5])
    urls = [p.url for p in public_posts if getattr(p, "url", "")]
    website = company_record.get("website")
    if website:
        urls.append(website)

    focus = "production inference reliability and evaluation"
    if "lora" in f"{what_they_do} {tech_stack}".lower():
        focus = "adapter-aware routing and validation for LoRA or continually updated models"
    elif "gpu" in f"{what_they_do} {tech_stack}".lower():
        focus = "GPU inference performance, cold starts, and capacity efficiency"

    return {
        "title": focus.title(),
        "description": (
            f"{company_name} appears to operate in a technical area where {focus} matters. "
            "The first useful contribution is a scoped measurement or validation harness that makes the "
            "problem observable before claiming an optimization."
        ),
        "source_urls": list(dict.fromkeys(urls)),
        "source_signal": (
            "Fallback generated from company brief and available public posts after model JSON parsing failed; "
            "requires source verification before outreach."
        ),
        "relevance_score": 6,
        "contribution_surface": "Build a small benchmark, router, validator, or report generator that makes the system tradeoff measurable.",
    }
