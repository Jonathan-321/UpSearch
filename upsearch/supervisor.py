"""
Supervisor Agent — evaluates the output quality of each pipeline agent.
Runs after every stage, scores 1-10, flags issues, logs metrics to W&B.
Works with both Claude and DeepSeek via llm.complete().
"""
import json
import re
from dataclasses import dataclass, field
from upsearch.sourcing.base import Post
from upsearch import llm

SYSTEM = """You are a Supervisor Agent that quality-checks outputs in a cold outreach research pipeline.

Score strictly and honestly — your evaluations are logged to W&B and used to improve agent prompts over time.

Respond with valid JSON only, no markdown fences:
{
  "score": <integer 1-10>,
  "passed": <true if score >= 6>,
  "flags": ["specific issue if any"],
  "reasoning": "1 sentence explaining the score"
}"""


@dataclass
class AgentScore:
    agent: str
    score: int
    passed: bool
    flags: list[str]
    reasoning: str
    rule_checks: dict = field(default_factory=dict)


def _llm_eval(prompt: str) -> dict:
    text = llm.complete(system=SYSTEM, user=prompt, max_tokens=256)
    start, end = text.find("{"), text.rfind("}") + 1
    if start == -1 or end == 0:
        return {"score": 5, "passed": True, "flags": ["Supervisor parse error"], "reasoning": "Could not parse evaluation."}
    try:
        return json.loads(text[start:end])
    except json.JSONDecodeError:
        return {"score": 5, "passed": True, "flags": ["Supervisor JSON error"], "reasoning": "Malformed evaluation JSON."}


# ── Per-agent evaluators ──────────────────────────────────────────────────────

def evaluate_scout(posts: list[Post], topic: str) -> AgentScore:
    """Did the Scout find relevant, diverse posts for the given topic?"""
    if not posts:
        return AgentScore(
            agent="scout", score=0, passed=False,
            flags=["No posts returned"],
            reasoning="Scout returned zero results."
        )

    sample = "\n".join(
        f"- [{p.source}] {p.title} (score={p.score}, comments={p.comments})"
        for p in posts[:8]
    )
    sources = {p.source for p in posts}
    rule_checks = {
        "post_count": len(posts),
        "source_diversity": len(sources),
        "has_reddit": "reddit" in sources,
        "has_hackernews": "hackernews" in sources,
    }

    prompt = (
        f"Topic: {topic}\n\n"
        f"Scout returned {len(posts)} posts from {len(sources)} source(s).\n\n"
        f"Sample results:\n{sample}\n\n"
        "Evaluate: Are these posts on-topic? Do they represent real problems or opportunities "
        "worth reaching out about? Is the source diversity adequate?"
    )
    result = _llm_eval(prompt)
    return AgentScore(agent="scout", rule_checks=rule_checks, **result)


def evaluate_analyst(
    results: list[tuple],
    total_posts: int,
) -> AgentScore:
    """Did the Analyst score calibration look realistic and useful?"""
    if not results:
        return AgentScore(
            agent="analyst", score=2, passed=False,
            flags=["No results passed the fit threshold"],
            reasoning="Analyst filtered everything out — threshold may be too strict or posts were off-topic."
        )

    scores = [r[1].get("fit_score", 0) for r in results]
    avg_score = sum(scores) / len(scores)
    score_range = max(scores) - min(scores)

    sample = "\n".join(
        f"- Fit {r[1].get('fit_score')}/10 | {r[1].get('contact_type')} | {r[0].title[:60]}\n"
        f"  Problem: {r[1].get('problem', '')[:120]}"
        for r in results[:4]
    )
    rule_checks = {
        "results_kept": len(results),
        "posts_dropped": total_posts - len(results),
        "avg_fit_score": round(avg_score, 1),
        "score_range": score_range,
        "score_spread_ok": score_range >= 2,
    }

    prompt = (
        f"Analyst kept {len(results)} of {total_posts} posts. Average fit score: {avg_score:.1f}.\n\n"
        f"Top results:\n{sample}\n\n"
        "Evaluate: Are the fit scores well-calibrated (not all the same, not inflated)? "
        "Are the problem summaries specific and actionable? "
        "Does the contact type make sense for each post?"
    )
    result = _llm_eval(prompt)
    return AgentScore(agent="analyst", rule_checks=rule_checks, **result)


def evaluate_strategist(strategy: dict, analysis: dict) -> AgentScore:
    """Is the outreach strategy specific and actionable?"""
    icebreaker = strategy.get("icebreaker", "")
    hook = strategy.get("hook", "")

    # Rule-based checks
    generic_phrases = ["great work", "love your project", "interesting post", "amazing", "impressive"]
    is_generic = any(p in icebreaker.lower() for p in generic_phrases)
    rule_checks = {
        "has_target_role": bool(strategy.get("target_role")),
        "has_hook": bool(hook),
        "has_icebreaker": bool(icebreaker),
        "has_channel": bool(strategy.get("channel")),
        "icebreaker_not_generic": not is_generic,
        "channel_valid": strategy.get("channel") in ("email", "linkedin", "x"),
    }

    prompt = (
        f"Opportunity fit score: {analysis.get('fit_score')}/10\n"
        f"Problem: {analysis.get('problem', '')}\n\n"
        f"Strategy produced:\n"
        f"  Target: {strategy.get('target_role', '')}\n"
        f"  Hook: {hook}\n"
        f"  Icebreaker: {icebreaker}\n"
        f"  Channel: {strategy.get('channel', '')}\n\n"
        "Evaluate: Is the icebreaker specific to the post's actual content (not generic flattery)? "
        "Is the hook compelling and honest? Is the channel choice appropriate?"
    )
    result = _llm_eval(prompt)
    if is_generic and "generic" not in str(result.get("flags", [])).lower():
        result.setdefault("flags", []).append("Icebreaker sounds generic")
    return AgentScore(agent="strategist", rule_checks=rule_checks, **result)


def evaluate_writer(draft: str, strategy: dict) -> AgentScore:
    """Did the Writer follow all rules? Word count, tone, structure, ask."""
    lines = draft.strip().splitlines()
    subject_line = lines[0] if lines else ""
    body = "\n".join(lines[2:]) if len(lines) > 2 else draft
    word_count = len(body.split())

    # Rule-based checks (fast, deterministic)
    has_em_dash = "—" in draft or " -- " in draft
    has_en_dash = "–" in draft
    has_buzzwords = bool(re.search(
        r"\b(leverage|synergy|utilize|excited to connect|reach out|touch base|passionate)\b",
        draft, re.IGNORECASE
    ))
    has_subject = subject_line.lower().startswith("subject:")
    has_ask = bool(re.search(
        r"\b(15.?min|call|chat|question|reply|connect)\b", draft, re.IGNORECASE
    ))
    rule_checks = {
        "word_count": word_count,
        "under_200_words": word_count <= 200,
        "has_subject_line": has_subject,
        "no_em_dash": not has_em_dash,
        "no_en_dash": not has_en_dash,
        "no_buzzwords": not has_buzzwords,
        "has_clear_ask": has_ask,
    }

    flags_from_rules = []
    if word_count > 200:
        flags_from_rules.append(f"Body is {word_count} words — over the 200-word limit")
    if has_em_dash or has_en_dash:
        flags_from_rules.append("Contains em-dash or en-dash")
    if has_buzzwords:
        flags_from_rules.append("Contains buzzword(s)")
    if not has_subject:
        flags_from_rules.append("Missing subject line")

    prompt = (
        f"Icebreaker the draft should open with: {strategy.get('icebreaker', '')}\n"
        f"Suggested ask: {strategy.get('suggested_ask', '')}\n\n"
        f"Draft:\n{draft}\n\n"
        "Evaluate: Does the email open with something specific to the recipient's actual work? "
        "Is the tone student-like and human (not corporate)? Is there one clear low-friction ask at the end? "
        "Would this email likely get a reply?"
    )
    result = _llm_eval(prompt)
    result.setdefault("flags", []).extend(flags_from_rules)
    result["passed"] = result.get("score", 5) >= 6 and word_count <= 200
    return AgentScore(agent="writer", rule_checks=rule_checks, **result)


# ── Final summary ─────────────────────────────────────────────────────────────

def pipeline_summary(scores: list[AgentScore]) -> dict:
    """Aggregate all agent scores into an overall pipeline performance report."""
    total = sum(s.score for s in scores)
    avg = total / len(scores) if scores else 0
    all_passed = all(s.passed for s in scores)
    all_flags = [f"{s.agent}: {f}" for s in scores for f in s.flags]

    return {
        "overall_score": round(avg, 1),
        "passed": all_passed,
        "agent_scores": {s.agent: s.score for s in scores},
        "flags": all_flags,
        "total_flags": len(all_flags),
    }
