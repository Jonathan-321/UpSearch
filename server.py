#!/usr/bin/env python3
"""
UpSearch + Opportunity Intelligence OS — unified API server.

Run with:  uvicorn server:app --reload --port 8000

Routes:
  /api/*   — UpSearch quick-search pipeline (Scout → Analyst → Strategist → Writer)
  /os/*    — Opportunity Intelligence OS (full company packet workflow, SSE streaming)
"""
import asyncio
import hashlib
import dataclasses
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# UpSearch pipeline
from upsearch.agents import scout, analyst, strategist, writer
from upsearch import supervisor as sup, tracker, llm
from upsearch.sourcing.base import Post

# OS pipeline
from agents import profile as profile_agent
from agents import company as company_agent
from agents import problem as problem_agent
from agents import people as people_agent
from agents import technical_note as technical_note_agent
from agents import outreach as outreach_agent
from agents import qa as qa_agent
import db

app = FastAPI(title="UpSearch + Opportunity Intelligence OS", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5179",
        "http://localhost:5180",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PROFILE_PATH = Path("profile.txt")


# ── Shared helpers ────────────────────────────────────────────────────────────

def load_profile_text() -> str:
    return PROFILE_PATH.read_text().strip() if PROFILE_PATH.exists() else ""


def serialize_post(post: Post) -> dict:
    d = dataclasses.asdict(post)
    d["id"] = hashlib.md5(post.url.encode()).hexdigest()[:8]
    return d


def dict_to_post(d: dict) -> Post:
    return Post(
        title=d.get("title", ""),
        body=d.get("body", ""),
        url=d.get("url", ""),
        source=d.get("source", "hackernews"),
        author=d.get("author", ""),
        subreddit=d.get("subreddit", ""),
        score=d.get("score", 0),
        comments=d.get("comments", 0),
    )


def sup_score(s: sup.AgentScore) -> dict:
    return {"score": s.score, "passed": s.passed, "flags": s.flags,
            "reasoning": s.reasoning, "rule_checks": s.rule_checks}


def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


# ── UpSearch /api/* endpoints (unchanged) ────────────────────────────────────

class ScoutRequest(BaseModel):
    topic: str
    mode: str = "jobs"

class AnalyzeRequest(BaseModel):
    posts: list[dict]

class StrategizeRequest(BaseModel):
    post: dict
    analysis: dict

class WriteRequest(BaseModel):
    post: dict
    analysis: dict
    strategy: dict

class LogRequest(BaseModel):
    post: dict
    analysis: dict
    strategy: dict
    draft: str
    sent: bool = False
    supervisor_summary: dict | None = None


@app.get("/api/health")
def health():
    return {"status": "ok", "provider": llm.active_provider(), "model": llm.active_model()}

@app.get("/api/profile")
def get_profile_api():
    return {"content": load_profile_text()}

@app.post("/api/scout")
def run_scout(req: ScoutRequest):
    query = f"{req.topic} {'job opening hiring internship' if req.mode == 'jobs' else 'open problem'}"
    try:
        posts = scout.run(query)
    except Exception as e:
        raise HTTPException(500, f"Scout failed: {e}")
    if not posts:
        raise HTTPException(404, "No posts found.")
    return {"posts": [serialize_post(p) for p in posts], "count": len(posts),
            "supervisor": sup_score(sup.evaluate_scout(posts, req.topic))}

@app.post("/api/analyze")
def run_analyst(req: AnalyzeRequest):
    profile = load_profile_text()
    post_objs = [dict_to_post(p) for p in req.posts]
    opps = []
    for p in post_objs:
        a = analyst.run(p, profile)
        if a and a.get("fit_score", 0) >= 5 and a.get("contact_type") != "skip":
            opps.append({"post": serialize_post(p), "analysis": a})
    opps.sort(key=lambda x: x["analysis"].get("fit_score", 0), reverse=True)
    return {"opportunities": opps, "count": len(opps),
            "supervisor": sup_score(sup.evaluate_analyst(
                [(dict_to_post(o["post"]), o["analysis"]) for o in opps], len(post_objs)))}

@app.post("/api/strategize")
def run_strategist(req: StrategizeRequest):
    profile = load_profile_text()
    s = strategist.run(dict_to_post(req.post), req.analysis, profile)
    if not s:
        raise HTTPException(500, "Strategist failed.")
    return {"strategy": s, "supervisor": sup_score(sup.evaluate_strategist(s, req.analysis))}

@app.post("/api/write")
def run_writer(req: WriteRequest):
    profile = load_profile_text()
    draft = writer.run(dict_to_post(req.post), req.analysis, req.strategy, profile)
    return {"draft": draft, "word_count": len(draft.split()),
            "supervisor": sup_score(sup.evaluate_writer(draft, req.strategy))}

@app.post("/api/log")
def run_log(req: LogRequest):
    try:
        run_id = tracker.log(dict_to_post(req.post), req.analysis, req.strategy,
                             req.draft, sent=req.sent, supervisor_summary=req.supervisor_summary)
    except Exception as e:
        raise HTTPException(500, f"W&B logging failed: {e}")
    return {"run_id": run_id}


# ── OS /os/* endpoints ────────────────────────────────────────────────────────

@app.on_event("startup")
def startup():
    db.init_db()


@app.get("/os/health")
def os_health():
    return {"status": "ok", "provider": llm.active_provider(), "model": llm.active_model()}


@app.get("/os/companies")
def os_companies():
    return {"companies": db.list_companies()}


@app.get("/os/packet/{company_name}")
def os_get_packet(company_name: str):
    company = db.get_company(company_name)
    if not company:
        raise HTTPException(404, f"No packet for '{company_name}'")
    packet = db.get_packet(company["id"])
    problems = db.get_problems(company["id"])
    people = db.get_people(company["id"])
    return {
        "company": company,
        "packet": packet,
        "problems": problems,
        "people": people,
    }


@app.get("/os/messages/pending")
def os_pending_messages():
    return {"messages": db.get_pending_approvals()}


@app.post("/os/messages/{message_id}/approve")
def os_approve_message(message_id: int):
    db.approve_message(message_id)
    return {"ok": True, "message_id": message_id}


@app.get("/os/packet/stream/{company_name}")
async def os_stream_packet(company_name: str, lane: str = "ai_infra"):
    """
    SSE stream — runs the full OS packet workflow for one company.
    Emits 'stage' events as each agent completes, then 'complete' when done.
    """
    raw_profile = load_profile_text()

    async def generate():
        try:
            # ── Profile ───────────────────────────────────────────────────────
            yield sse("stage", {"stage": "profile", "status": "running", "message": "Loading profile..."})
            profile = await asyncio.to_thread(profile_agent.run, raw_profile)
            yield sse("stage", {"stage": "profile", "status": "complete",
                                "message": f"{profile.get('name','?')} @ {profile.get('school','?')}"})

            # ── Company ───────────────────────────────────────────────────────
            yield sse("stage", {"stage": "company", "status": "running", "message": f"Researching {company_name}..."})
            company_result = await asyncio.to_thread(company_agent.run, company_name, lane, profile)
            company_data = company_result["result"]
            company_id = db.upsert_company(
                company_name,
                website=company_data.get("website", ""),
                lane=lane,
                fit_score=company_data.get("fit_score", 0),
                hiring_status=company_data.get("hiring_status", "unknown"),
                status="researched",
            )
            yield sse("stage", {"stage": "company", "status": "complete",
                                "message": f"Fit: {company_data.get('fit_score','?')}/10",
                                "data": company_data})

            # ── Problems ──────────────────────────────────────────────────────
            yield sse("stage", {"stage": "problem", "status": "running", "message": "Extracting open problems..."})
            problem_result = await asyncio.to_thread(problem_agent.run, company_name, company_data, profile)
            problems = problem_result["result"].get("problems", [])
            for p in problems:
                db.insert_problem(company_id, p["title"], p.get("description",""),
                                  p.get("source_urls",[]), p.get("relevance_score",0))
            yield sse("stage", {"stage": "problem", "status": "complete",
                                "message": f"Found {len(problems)} problems", "data": problems})

            # ── People ────────────────────────────────────────────────────────
            top_problem = problems[0] if problems else {}
            yield sse("stage", {"stage": "people", "status": "running", "message": "Finding relevant people..."})
            people_result = await asyncio.to_thread(people_agent.run, company_name, top_problem, profile)
            people_list = people_result["result"].get("people", [])
            for person in people_list:
                db.insert_person(company_id, person["name"], person.get("role",""),
                                 linkedin_url=person.get("linkedin_url",""),
                                 github_url=person.get("github_url",""),
                                 relevance_score=person.get("relevance_score",0),
                                 relevance_reason=person.get("relevance_reason",""),
                                 proximity=person.get("proximity","engineer"))
            yield sse("stage", {"stage": "people", "status": "complete",
                                "message": f"Mapped {len(people_list)} people", "data": people_list})

            # ── Technical Note ────────────────────────────────────────────────
            yield sse("stage", {"stage": "technical_note", "status": "running", "message": "Writing one-page technical note..."})
            note_result = await asyncio.to_thread(technical_note_agent.run, company_name, company_data, top_problem, profile)
            note_text = note_result["result"].get("technical_note", "")
            adjacent_proof = note_result["result"].get("adjacent_proof", "")
            yield sse("stage", {"stage": "technical_note", "status": "complete",
                                "message": f"{len(note_text.split())} words",
                                "data": {"technical_note": note_text, "adjacent_proof": adjacent_proof}})

            # ── Outreach ──────────────────────────────────────────────────────
            top_person = people_list[0] if people_list else {}
            yield sse("stage", {"stage": "outreach", "status": "running", "message": "Drafting outreach variants..."})
            outreach_result = await asyncio.to_thread(
                outreach_agent.run, company_name, top_problem, top_person, note_text, adjacent_proof, profile)
            drafts = outreach_result["result"]
            yield sse("stage", {"stage": "outreach", "status": "complete",
                                "message": f"{len(drafts)} variants", "data": drafts})

            # ── QA ────────────────────────────────────────────────────────────
            yield sse("stage", {"stage": "qa", "status": "running", "message": "Running QA checks..."})
            packet_data = {"company": company_data, "problems": problems, "people": people_list,
                           "technical_note": note_text, "adjacent_proof": adjacent_proof, "outreach_drafts": drafts}
            qa_result = await asyncio.to_thread(qa_agent.run, packet_data, profile)

            packet_id = db.upsert_packet(
                company_id,
                company_fit=company_data.get("why",""),
                open_problem=json.dumps(top_problem),
                people_map=json.dumps(people_list),
                technical_note=note_text,
                adjacent_proof=adjacent_proof,
                outreach_drafts=json.dumps(drafts),
                verification=json.dumps(qa_result),
                qa_score=qa_result.get("score", 0),
                qa_flags=json.dumps(qa_result.get("flags",[])),
                crm_status="prepared" if qa_result.get("passed") else "needs_review",
            )
            for variant, draft_text in drafts.items():
                if draft_text.strip():
                    db.insert_message(packet_id, None, variant, draft_text)
            db.set_company_status(company_id, "packet_ready")

            yield sse("stage", {"stage": "qa", "status": "complete",
                                "message": f"QA: {qa_result.get('score',0)}/10",
                                "data": qa_result})

            # ── Done ──────────────────────────────────────────────────────────
            yield sse("complete", {
                "packet_id": packet_id,
                "company": company_name,
                "fit_score": company_data.get("fit_score", 0),
                "qa_score": qa_result.get("score", 0),
                "problems": len(problems),
                "people": len(people_list),
            })

        except Exception as e:
            yield sse("error", {"error": str(e), "stage": "unknown"})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
