"""
People Agent — finds and ranks relevant people at the target company.
Proximity types: engineer, researcher, founder, FDE, PM, recruiter, hiring_manager.

Evidence-first: the LLM is never asked to produce contact URLs (LinkedIn,
GitHub, Twitter). Instead, only a ``source_url`` is collected; it is then fetched
and checked for explicit person name + company + role/relevance evidence in
:mod:`upsearch.person_verification`. Unverified candidates get no contact URLs.
"""
from upsearch import llm
from upsearch.json_utils import parse_model_json_object
from upsearch.person_validation import filter_people
from upsearch.person_verification import verify_people
from upsearch.sourcing import hackernews
import re

from upsearch.sourcing.company_people import author_from_post_url, fetch_company_people
from upsearch.github_org_search import find_company_org, search_org_members

SYSTEM = """You are a People Agent for an Opportunity Intelligence OS. Given a company and problem,
identify 3-6 people who are most worth reaching out to.

Rank by: proximity to the problem, public signal, and likelihood of a useful conversation.
Only list people supported by a retrieved team page, author page, company blog,
paper/author page, GitHub contribution page, or public discussion.
Do not output LinkedIn, GitHub, Twitter, email, or other contact fields. Supply
only a source_url pointing to the retrieved page that links the person, company,
and role/relevance.

Respond with valid JSON only:
{
  "people": [
    {
      "name": "Full Name or HN username",
      "role": "e.g. ML Infrastructure Engineer",
      "proximity": "engineer | researcher | founder | FDE | PM | hiring_manager | recruiter",
      "source_url": "public author/team/blog source URL or null",
      "relevance_score": <1-10>,
      "relevance_reason": "1 sentence on why this person and why now",
      "source": "where you found this person",
      "outreach_note": "one thing to reference in the opening line"
    }
  ]
}"""


def run(company_name: str, problem: dict, user_profile: dict, *, company_domain: str = "") -> dict:
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
    result = parse_model_json_object(text, {"people": []})
    if not result.get("people"):
        result = {"people": []}
    # Curated seed candidates merge into the pool like any other source —
    # they must not replace live sourcing, and they still face verification.
    seed_names = {p.get("name", "") for p in result["people"]}
    for seed in _fallback_people(company_name, problem):
        if seed.get("name", "") not in seed_names:
            seed_names.add(seed.get("name", ""))
            result["people"].append(seed)

    # ── Cited-source authors: the most-proximate people ─────────────────────
    # The problem stage cites company posts as evidence. Whoever wrote the
    # cited post owns the exact topic the packet discusses — outreach that
    # references their own writing is the straightest path to the right
    # person. These candidates lead the pool and still face verification.
    if company_domain:
        from urllib.parse import urlparse  # noqa: PLC0415

        domain_token = company_domain.lower().removeprefix("www.")
        cited_urls = [
            url for url in problem.get("source_urls", [])
            if isinstance(url, str) and url.strip()
            # Only company-domain posts can have a company author page, and a
            # bare homepage citation names no specific post — skip both early
            # so off-domain links don't consume the scan budget.
            and domain_token in url.lower()
            and urlparse(url).path.strip("/")
        ]
        for cited_url in cited_urls[:3]:
            author = author_from_post_url(cited_url, company_domain)
            if not author:
                continue
            # The cited-author record carries strictly better evidence than a
            # model proposal of the same person (author page vs. an about-page
            # claim), so it replaces a same-name entry rather than deferring.
            result["people"] = [
                p for p in result["people"] if p.get("name") != author.get("name")
            ]
            result["people"].insert(0, author)

    # ── Company-owned people source connector ────────────────────────────
    # Fetch candidates from company team / author / blog pages when a
    # verified domain is available.  Retrieved candidates merge into the
    # pool before the GitHub fallback and before verification.
    if company_domain:
        candidate_urls = _candidate_company_page_urls(company_domain, company_name)
        if candidate_urls:
            company_people = fetch_company_people(company_domain, candidate_urls)
            existing_names = {p.get("name", "") for p in result.get("people", [])}
            for person in company_people:
                p_name = person.get("name", "")
                if p_name and p_name not in existing_names:
                    existing_names.add(p_name)
                    result.setdefault("people", []).append(person)

    # ── Person-name gate, then evidence-first verification ──────────────────
    # Non-names (nav labels, group placeholders, article titles) are dropped
    # before verification: they cannot be outreach targets and a junk card
    # shown to the reviewer costs trust.
    raw_people, _rejected = filter_people(result.get("people", []))
    verified_people = verify_people(raw_people, company_name)

    # ── GitHub org fallback, driven by verified scarcity ─────────────────────
    # A pile of plausible-but-unverifiable names (hallucinated founders,
    # LinkedIn-walled sources) must not suppress the one source that yields
    # fetchable person pages. Trigger on how many candidates VERIFIED, not on
    # how many were proposed.
    verified_count = sum(
        1 for p in verified_people if p.get("verification_status") == "verified"
    )
    if verified_count < 2:
        github_org_name = find_company_org(
            company_name, company_domain, candidates=_org_name_guesses(company_name)
        )
        if github_org_name:
            gh_members = search_org_members(
                company_name, github_org_name,
                problem_keywords=_problem_keywords(problem),
            )
            existing_names = {p.get("name", "") for p in verified_people}
            fresh_members, _ = filter_people([
                member for member in gh_members
                if member.get("name", "") not in existing_names
            ])
            # The verified company domain lets verification independently
            # confirm the org belongs to this company (org profile website).
            for member in fresh_members:
                if isinstance(member.get("github_evidence"), dict):
                    member["github_evidence"]["company_domain"] = company_domain
            verified_people.extend(verify_people(fresh_members, company_name))

    result["people"] = verified_people

    return {
        "result": result,
        "source_urls": [p.url for p in hn_posts] + [p.get("source_url", "") for p in verified_people if p.get("source_url")],
        "confidence": 0.55,
        "assumptions": [
            "Contact URLs stripped from any person whose source_url did not contain explicit name+company evidence",
            "Relevance scores based on public signal only",
        ],
        "next_action": "run_technical_note_agent",
    }


def _fallback_people(company_name: str, problem: dict) -> list[dict]:
    """Use explicit Baseten source candidates when live people search is empty.

    These are candidates, not trusted records. They pass through the same fetch
    and evidence checks as model output.
    """
    if company_name.lower() != "baseten":
        return []

    problem_title = problem.get("title", "production inference")
    return [
        {
            "name": "Bola Malek",
            "role": "Forward Deployed Engineer",
            "proximity": "FDE",
            "linkedin_url": None,
            "github_url": None,
            "twitter_url": None,
            "source_url": "https://www.baseten.co/author/bola-malek/",
            "relevance_score": 9,
            "relevance_reason": f"Baseten author/FDE connected to customer-facing inference work; useful first reader for {problem_title}.",
            "source": "Baseten author page",
            "outreach_note": "Reference Baseten's continual-learning or Frontier Gateway writing and ask who owns the closest inference/FDE problem.",
        },
        {
            "name": "Raymond Cano",
            "role": "Software Engineer",
            "proximity": "engineer",
            "linkedin_url": None,
            "github_url": None,
            "twitter_url": None,
            "source_url": "https://www.baseten.co/author/raymond-cano/",
            "relevance_score": 8,
            "relevance_reason": "Baseten author on Loops and training-to-deploy workflows, relevant to checkpoints moving into production inference.",
            "source": "Baseten author page",
            "outreach_note": "Ask how deployment should behave when checkpoints change frequently.",
        },
        {
            "name": "Joey Zwicker",
            "role": "Head of Forward Deployed Engineering",
            "proximity": "hiring_manager",
            "linkedin_url": None,
            "github_url": None,
            "twitter_url": None,
            "source_url": "https://www.baseten.co/blog/joey-zwicker-joins-baseten-as-head-of-fde/",
            "relevance_score": 8,
            "relevance_reason": "Publicly tied to Baseten's FDE function, where ambiguous customer AI infrastructure problems become deployable systems.",
            "source": "Baseten FDE announcement",
            "outreach_note": "Ask whether the one-page note is best routed to FDE or inference engineering.",
        },
    ]


def _candidate_company_page_urls(company_domain: str, company_name: str) -> list[str]:
    """Return canonical page-URL candidates for company-owned people pages.

    These are best-effort guesses for common team / author / blog patterns.
    The connector filters to the verified domain, and pages that don't
    contain person names simply produce no candidates.
    """
    base = f"https://www.{company_domain}" if not company_domain.startswith("www.") else f"https://{company_domain}"
    return [
        f"{base}/team",
        f"{base}/about",
        f"{base}/company",
        f"{base}/about-us",
        f"{base}/company/team",
        f"{base}/blog",
        f"{base}/authors",
        f"{base}/author",
    ]


_KEYWORD_STOPWORDS = {"from", "have", "into", "more", "than", "that", "their", "this", "using", "with"}


def _problem_keywords(problem: dict) -> list[str]:
    """Distinctive tokens from the problem, used to rank org repos by relevance."""
    text = f"{problem.get('title', '')} {problem.get('description', '')}".lower()
    tokens = [
        token for token in re.findall(r"[a-z0-9]+", text)
        if len(token) >= 4 and token not in _KEYWORD_STOPWORDS
    ]
    return list(dict.fromkeys(tokens))[:12]


def _org_name_guesses(company_name: str) -> list[str]:
    """Name-derived GitHub org candidates (groq, baseten-ai, basetenai).

    These are guesses, not answers: `find_company_org` accepts one only when
    the org's profile actually matches the company, and falls back to the
    GitHub org search API when every guess misses (Fireworks AI is "fw-ai").
    """
    # Strip corporate suffixes BEFORE replacing spaces, or "together ai"
    # becomes "together-ai" and suffix stripping mangles it to "together-".
    base = company_name.strip().lower()
    for suffix in (" llc", " inc", " corp", " ltd", " technologies", " technology", " ai"):
        if base.endswith(suffix):
            base = base[: -len(suffix)].strip()
    base = base.replace(" ", "-")
    candidates: list[str] = []
    for c in [base, f"{base}-ai", f"{base}ai", base.replace("-", "")]:
        if re.match(r"^[a-z0-9][a-z0-9-]{1,38}$", c) and c not in candidates:
            candidates.append(c)
    return candidates
