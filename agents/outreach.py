"""
Outreach Agent — writes concise, human outreach variants.
Variants: email, linkedin_note, connection_followup, recruiter (optional).
All variants: <=200 words, student voice, no buzzwords, specific icebreaker, one clear ask.
"""
import json
from upsearch import llm

SYSTEM = """You are an Outreach Agent writing cold messages for a technical student.

Rules for every variant:
- Under 200 words (body only, not subject line)
- Student voice: direct, specific, a little informal
- No em-dashes, no en-dashes, no buzzwords (leverage, synergy, excited to connect)
- Open with the icebreaker — something specific to their actual work
- One clear low-friction ask at the end (15-min call, one question, a link to their work)
- Sign off with first name only
- Do NOT fabricate experience; use "studying", "working through", "prototyping"

For the email: include subject line on first line, blank line, then body.
For linkedin_note: 200-char connection note PLUS 200-word follow-up message after acceptance.
For connection_followup: message to send after LinkedIn connection is accepted.

Respond with valid JSON only:
{
  "email": "Subject: ...\\n\\nBody...",
  "linkedin_note": "short connection note under 200 chars",
  "connection_followup": "message to send after connection accepted",
  "recruiter": "optional recruiter/FDE variant if relevant"
}"""


def run(
    company_name: str,
    problem: dict,
    person: dict,
    technical_note_text: str,
    adjacent_proof: str,
    user_profile: dict,
) -> dict:
    outreach_note = person.get("outreach_note", "")
    person_role = person.get("role", "engineer")
    person_name = person.get("name", "[Name]")

    text = llm.complete(
        system=SYSTEM,
        user=(
            f"Target: {person_name} — {person_role} at {company_name}\n"
            f"Problem: {problem.get('title', '')}\n"
            f"{problem.get('description', '')[:400]}\n\n"
            f"Opening icebreaker to use: {outreach_note}\n\n"
            f"Student adjacent proof: {adjacent_proof}\n\n"
            f"Student background summary: {user_profile.get('background_summary', '')}\n\n"
            f"Contribution idea (from technical note): "
            f"{technical_note_text[technical_note_text.find('## Contribution'):technical_note_text.find('## Contribution')+400] if '## Contribution' in technical_note_text else ''}"
        ),
        max_tokens=1200,
    )
    start, end = text.find("{"), text.rfind("}") + 1
    try:
        result = json.loads(text[start:end]) if start != -1 else {}
    except json.JSONDecodeError:
        result = {"email": text, "linkedin_note": "", "connection_followup": ""}

    return {
        "result": result,
        "confidence": 0.85,
        "source_urls": [],
        "assumptions": ["Person details need manual verification before sending"],
        "next_action": "run_qa_agent",
    }
