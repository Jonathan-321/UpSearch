"""
Problem Agent — extracts current open technical problems from public sources.
Output: ranked list of specific, source-backed problem briefs.
"""
from upsearch import llm
from upsearch.json_utils import parse_model_json_object
from upsearch.sourcing import hackernews, reddit
from upsearch.sourcing.web_search import search_company_problems, search_company_blog

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
    domain = company_record.get("official_domain", "") or company_record.get("website", "")
    lane_phrase = str(company_record.get("lane", "")).replace("_", " ")
    web_results = search_company_problems(company_name, lane_phrase)
    blog_results = search_company_blog(company_name, domain)
    all_posts = hn_posts + reddit_posts

    # Every retrieval channel feeds one catalog: discussion posts, web search,
    # and site-specific blog search. The model may cite only catalog URLs, and
    # the same URLs are reported upstream as retrieved source candidates —
    # web/blog results are retrieval output, not model-asserted links.
    catalog_entries = [
        {"source": p.source, "title": p.title, "body": p.body[:300], "url": p.url}
        for p in all_posts[:6]
        if p.url
    ]
    catalog_entries += [
        {"source": "web_search", "title": str(item.get("title", ""))[:160], "body": "", "url": item.get("url", "")}
        for item in web_results[:4]
        if item.get("url")
    ]
    catalog_entries += [
        {"source": "company_blog", "title": str(item.get("title", ""))[:160], "body": "", "url": item.get("url", "")}
        for item in blog_results[:4]
        if item.get("url")
    ]
    source_catalog = []
    seen_urls: set[str] = set()
    for entry in catalog_entries:
        if entry["url"] in seen_urls:
            continue
        seen_urls.add(entry["url"])
        source_catalog.append({"id": f"S{len(source_catalog) + 1}", **entry})
    allowed_urls = {item["url"] for item in source_catalog}

    source_text = "\n".join(
        f"{item['id']} [{item['source']}] {item['title']}\n{item['body']}\nURL: {item['url']}".replace("\n\n", "\n")
        for item in source_catalog
    ) if source_catalog else "No recent public discussions found."

    text = llm.complete(
        system=SYSTEM,
        user=(
            f"Company: {company_name}\n"
            f"What they do: {what_they_do}\n"
            f"Tech stack: {tech_stack}\n\n"
            f"Public signal catalog. Use only these exact URLs as source_urls:\n{source_text}\n\n"
            f"Student skills: {', '.join(user_profile.get('skills', []))}"
        ),
        max_tokens=1024,
    )
    result = parse_model_json_object(text, {"problems": []})
    result["problems"] = _sanitize_problems(result.get("problems", []), allowed_urls)
    if not result.get("problems"):
        fallback = _fallback_problem(company_name, company_record, all_posts)
        result = {"problems": [fallback] if fallback.get("source_urls") else []}

    return {
        "result": result,
        "source_urls": [item["url"] for item in source_catalog],
        "confidence": 0.65 if source_catalog else 0.4,
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
    if website and company_record.get("identity_status") == "verified":
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


def _sanitize_problems(problems: list, allowed_urls: set[str]) -> list[dict]:
    """Keep only model problems backed by URLs that were actually retrieved."""
    if not isinstance(problems, list):
        return []
    sanitized: list[dict] = []
    for item in problems:
        if not isinstance(item, dict):
            continue
        urls = item.get("source_urls", [])
        if not isinstance(urls, list):
            urls = []
        valid_urls = [url for url in urls if isinstance(url, str) and url in allowed_urls]
        if not valid_urls:
            continue
        next_item = dict(item)
        next_item["source_urls"] = list(dict.fromkeys(valid_urls))
        sanitized.append(next_item)
    return sanitized
