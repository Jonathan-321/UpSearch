"""
QA Agent — checks sources, claims, word count, tone, and unsupported experience claims.
Runs before any packet is marked ready for outreach.
"""
import re
from upsearch import llm
from upsearch.json_utils import parse_model_json_object

SYSTEM = """You are a QA Agent for an outreach packet. Check for:
1. Fabricated experience — phrases like "I built", "I deployed", "I worked on" without proof
2. Missing sources — claims about the company with no URL backing
3. Inflated language — "passionate", "excited to connect", "synergy", etc.
4. Word count violations — email body over 200 words
5. Unsourced people — people listed without public profile links
6. Generic icebreakers — openers that could apply to any company/person

Score the overall packet 1-10. Pass threshold is 6.

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
    all_drafts = "\n\n".join(packet.get("outreach_drafts", {}).values())

    # Word count check (email body)
    email_draft = packet.get("outreach_drafts", {}).get("email", "")
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
    proof_points = user_profile.get("proof_points", [])
    if strong_claims and not proof_points:
        flags.append(f"Strong experience claims without proof: {', '.join(set(strong_claims))}")

    # People source check
    people = packet.get("people", [])
    people_without_source = [p["name"] for p in people if not p.get("linkedin_url") and not p.get("github_url")]
    if people_without_source:
        flags.append(f"People without verified profiles: {', '.join(people_without_source[:3])}")

    # LLM quality check
    packet_summary = (
        f"Technical note excerpt:\n{packet.get('technical_note', '')[:600]}\n\n"
        f"Email draft:\n{email_draft[:600]}\n\n"
        f"Adjacent proof: {packet.get('adjacent_proof', '')}\n\n"
        f"Rule-based flags already found: {flags}"
    )
    llm_result_text = llm.complete(system=SYSTEM, user=packet_summary, max_tokens=512)

    llm_result = parse_model_json_object(
        llm_result_text,
        {"passed": False, "score": 4, "flags": ["QA parse error"]},
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
        "rule_checks": {
            "word_count": word_count,
            "has_buzzwords": bool(buzzwords),
            "has_dashes": "—" in all_drafts or "–" in all_drafts,
            "strong_claims": list(set(strong_claims)),
            "unsourced_people": people_without_source,
        },
    }
