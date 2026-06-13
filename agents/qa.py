"""
QA Agent — checks sources, claims, word count, tone, and unsupported experience claims.
Runs before any packet is marked ready for outreach.

Journey-heavy verification uses qa_execution.qa_verify(), which respects the
configured strong model route and signals degraded mode when the strong model
is unavailable. Deterministic rule checks always run first.
"""
import re
from upsearch.config import load_settings
from upsearch.model_router import ModelRouter, TaskType
from upsearch.qa_execution import qa_verify

SYSTEM = """You are a QA Agent for an outreach packet. Check for:
1. Fabricated experience — phrases like "I built", "I deployed", "I worked on" without proof
2. Missing sources — claims about the company with no URL backing
3. Inflated language — "passionate", "excited to connect", "synergy", etc.
4. Word count violations — email body over 200 words
5. Unverified people — people without a fetched source that passed the
   name + company + role/relevance evidence contract
6. Generic icebreakers — openers that could apply to any company/person

Score the overall packet 1-10. Pass threshold is 6.
Use the provided people source lines and verification status. A URL alone is not
evidence. Only ``verification_status=verified`` counts as a verified person.

Respond with valid JSON only:
{
  "passed": <true|false>,
  "score": <1-10>,
  "flags": ["specific issue 1", "specific issue 2"],
  "recommendations": ["how to fix issue 1"],
  "claim_check": "brief note on whether claims seem honest",
  "source_coverage": "brief note on source quality"
}"""


def run(packet: dict, user_profile: dict) -> dict:
    # Rule-based checks first (fast, deterministic)
    flags = []
    drafts = {
        str(key): value if isinstance(value, str) else ""
        for key, value in (packet.get("outreach_drafts") or {}).items()
    }
    all_drafts = "\n\n".join(value for value in drafts.values() if value)

    # Word count check (email body)
    email_draft = drafts.get("email", "")
    email_body = "\n".join(email_draft.splitlines()[2:]) if "\n\n" in email_draft else email_draft
    word_count = len(email_body.split())
    if word_count > 200:
        flags.append(f"Email body is {word_count} words — over 200-word limit")

    # Em-dash / en-dash
    if "—" in all_drafts or "–" in all_drafts:
        flags.append("Drafts contain em-dash or en-dash")

    # Buzzwords
    buzzwords = re.findall(
        r"\b(passionate|excited to connect|leverage|synergy|utilize|touch base|reach out to learn)\b",
        all_drafts, re.IGNORECASE
    )
    if buzzwords:
        flags.append(f"Buzzwords found: {', '.join(set(buzzwords))}")

    # Fabricated experience check
    strong_claims = re.findall(
        r"\bI (built|deployed|shipped|led|managed|owned|ran|architected)\b",
        all_drafts, re.IGNORECASE
    )
    proof_points = [
        str(item).strip()
        for item in user_profile.get("proof_points", [])
        if str(item).strip()
    ]
    if strong_claims and not proof_points:
        flags.append(f"Strong experience claims without proof: {', '.join(set(strong_claims))}")

    # People source check
    people = packet.get("people", [])
    people_without_verified_evidence = [
        p.get("name", "?") for p in people
        if p.get("verification_status") != "verified" or not p.get("source_url")
    ]
    if people_without_verified_evidence:
        flags.append(
            "People without verified evidence: "
            f"{', '.join(people_without_verified_evidence[:3])}"
        )

    people_source_lines = "\n".join(
        (
            f"- {p.get('name', '?')}: status={p.get('verification_status', 'unverified')}; "
            f"evidence={p.get('source_url') or 'missing'}; "
            f"contact={p.get('linkedin_url') or p.get('github_url') or p.get('twitter_url') or 'none'}"
        )
        for p in people
    )

    # Build known proof bank from enriched profile
    proof_bank_text = ""
    if proof_points:
        proof_bank_text = "User proof points:\n" + "\n".join(f"- {p}" for p in proof_points[:6])

    # LLM quality check
    packet_summary = (
        f"Technical note excerpt:\n{packet.get('technical_note', '')[:600]}\n\n"
        f"Email draft:\n{email_draft[:600]}\n\n"
        f"People source lines:\n{people_source_lines}\n\n"
        f"Adjacent proof: {packet.get('adjacent_proof', '')}\n\n"
        f"{proof_bank_text}\n\n"
        f"Rule-based flags already found: {flags}"
    )
    route = ModelRouter(load_settings()).route(TaskType.VERIFICATION)
    # Reasoning models (e.g. deepseek-r1) spend output tokens on thinking
    # before the JSON verdict; 512 starves them into empty/truncated output
    # and a parse-error default instead of a real evaluation.
    llm_result, degraded_mode = qa_verify(
        route,
        system=SYSTEM,
        user_prompt=packet_summary,
        rule_flags=flags,
        max_tokens=2048,
    )

    # Merge rule-based flags with LLM flags
    all_flags = flags + [f for f in llm_result.get("flags", []) if f not in flags]
    score = llm_result.get("score", 5)
    if flags:
        score = max(1, score - len(flags))

    return {
        "passed": score >= 6 and len([f for f in all_flags if "over 200" in f or "Fabricated" in f]) == 0,
        "score": score,
        "flags": all_flags,
        "recommendations": llm_result.get("recommendations", []),
        "claim_check": llm_result.get("claim_check", ""),
        "source_coverage": llm_result.get("source_coverage", ""),
        "model_route": {
            "provider": route.provider,
            "model": route.model,
            "configured": route.configured,
            "is_fallback": route.is_fallback,
            "degraded_mode": degraded_mode,
            "reason": route.reason,
        },
        "rule_checks": {
            "word_count": word_count,
            "has_buzzwords": bool(buzzwords),
            "has_dashes": "—" in all_drafts or "–" in all_drafts,
            "strong_claims": list(set(strong_claims)),
            "unsourced_people": people_without_verified_evidence,
        },
    }
