"""
Technical Note Agent — writes a one-page technical note for a company opportunity.
Sections: problem framing, current landscape, contribution idea, evaluation approach, adjacent proof.
"""
import json
from upsearch import llm

SYSTEM = """You are a Technical Note Agent. Write a concise one-page technical note (400-600 words)
for a student to use as a reference artifact when reaching out to a technical team.

The note must be technically honest and grounded. It should show that the student
understands the problem at a level that earns a reply — not that they have solved it.

Structure:
## Problem
What the team is dealing with and why it matters.

## Current Landscape
What existing approaches exist and where they fall short.

## Contribution Idea
One specific thing a student with this background could prototype, benchmark, or analyze.

## Evaluation
How you would know if the contribution is useful.

Then separately provide:
adjacent_proof: a sober 2-3 sentence mapping from the student's background to this problem.
Do not overstate. Use language like "studying", "coursework in", "prototyping", "read through".

Respond with JSON:
{
  "technical_note": "full markdown text of the one-pager",
  "adjacent_proof": "2-3 sentence honest proof mapping"
}"""


def run(company_name: str, company_record: dict, problem: dict, user_profile: dict) -> dict:
    skills = ", ".join(user_profile.get("skills", []))
    coursework = ", ".join(user_profile.get("coursework", []))
    proof_points = "\n".join(f"- {p}" for p in user_profile.get("proof_points", []))
    projects = json.dumps(user_profile.get("projects", []))

    text = llm.complete(
        system=SYSTEM,
        user=(
            f"Company: {company_name}\n"
            f"What they do: {company_record.get('what_they_do', '')}\n"
            f"Tech stack: {', '.join(company_record.get('tech_stack', []))}\n\n"
            f"Problem:\nTitle: {problem.get('title', '')}\n{problem.get('description', '')}\n"
            f"Contribution surface: {problem.get('contribution_surface', '')}\n\n"
            f"Student:\nSkills: {skills}\nCoursework: {coursework}\n"
            f"Proof points:\n{proof_points}\nProjects: {projects}"
        ),
        max_tokens=1200,
    )
    start, end = text.find("{"), text.rfind("}") + 1
    try:
        result = json.loads(text[start:end]) if start != -1 else {}
    except json.JSONDecodeError:
        result = {"technical_note": text, "adjacent_proof": ""}

    return {
        "result": result,
        "confidence": 0.8,
        "source_urls": company_record.get("open_source", []),
        "assumptions": ["Technical claims should be verified against current state of the art"],
        "next_action": "run_outreach_agent",
    }
