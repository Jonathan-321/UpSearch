"""
Profile Agent — builds the user's technical map from profile.txt and GitHub.
Output: structured profile dict used by every downstream agent.
"""
import json
from upsearch import llm

SYSTEM = """You are a Profile Agent. Given a student's raw profile text, extract a structured technical map.

Respond with valid JSON only:
{
  "name": "...",
  "school": "...",
  "email": "...",
  "skills": ["Python", "ML", "systems"],
  "coursework": ["Operating Systems", "AI", "Convex Optimization"],
  "projects": [{"name": "...", "description": "...", "tech": [...]}],
  "interests": ["LLM inference", "ML systems"],
  "preferred_roles": ["ML engineer intern", "research intern"],
  "github_url": "...",
  "background_summary": "2-sentence honest summary of what this student has done and is capable of",
  "proof_points": ["specific credible proof point 1", "specific credible proof point 2"]
}

Be honest. Do not inflate experience. If something is coursework, label it as coursework."""


def run(raw_profile: str) -> dict:
    if not raw_profile.strip():
        return {
            "name": "Student",
            "school": "Unknown",
            "skills": [],
            "interests": [],
            "background_summary": "CS student seeking technical opportunities.",
            "proof_points": [],
        }
    text = llm.complete(system=SYSTEM, user=f"Profile:\n{raw_profile}", max_tokens=800)
    start, end = text.find("{"), text.rfind("}") + 1
    try:
        return json.loads(text[start:end]) if start != -1 else {}
    except json.JSONDecodeError:
        return {"background_summary": raw_profile[:300], "skills": [], "interests": []}
