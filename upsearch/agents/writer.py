"""
Writer Agent — drafts the cold email.
Works for both research outreach and job search outreach.
Rules: ≤200 words, student voice, no dashes, no buzzwords, one icebreaker.
"""
from upsearch.sourcing.base import Post
from upsearch import llm

SYSTEM = """You are a Writer Agent that drafts cold outreach emails for a CS student.

This email may be for research collaboration OR for a job/internship — adapt the tone accordingly.
For jobs: show genuine interest in the team's work, not just the role. Skip "I saw your job posting."
For research: be curious, specific, and direct about what you want to learn or contribute.

Hard rules for both:
- Subject line on the first line, then one blank line, then the body
- 200 words maximum for the body (not counting subject line)
- Write like a real student: direct, human, no corporate tone
- No em-dashes, no en-dashes, no buzzwords
- Open with the icebreaker — something specific to their actual work
- One clear low-friction ask at the end (15-min call or one specific question)
- Sign off with first name only

The goal is a reply. Specificity beats polish every time."""


def run(post: Post, analysis: dict, strategy: dict, user_profile: str) -> str:
    payload = (
        f"Post: {post.title}\nURL: {post.url}\n\n"
        f"Analysis:\n- Opportunity: {analysis.get('problem', '')}\n"
        f"- Gap: {analysis.get('gap', '')}\n"
        f"- My angle: {analysis.get('contribution', '')}\n"
        f"- Contact type: {analysis.get('contact_type', '')}\n\n"
        f"Strategy:\n- Target: {strategy.get('target_role', '')}\n"
        f"- Hook: {strategy.get('hook', '')}\n"
        f"- Icebreaker: {strategy.get('icebreaker', '')}\n\n"
        f"Student profile:\n{user_profile}"
    )
    return llm.complete(system=SYSTEM, user=payload, max_tokens=600)
