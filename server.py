#!/usr/bin/env python3
"""
UpSearch API server — bridges the React frontend to the Python agent pipeline.

Run with:
  uvicorn server:app --reload --port 8000

Each endpoint runs one pipeline stage and returns its output plus a
Supervisor evaluation score so the frontend can display quality metrics live.
"""
import hashlib
import dataclasses
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from upsearch.agents import scout, analyst, strategist, writer
from upsearch import supervisor as sup, tracker, llm
from upsearch.sourcing.base import Post

app = FastAPI(title="UpSearch API", version="0.1.0")

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


# ── Helpers ───────────────────────────────────────────────────────────────────

def load_profile() -> str:
    if PROFILE_PATH.exists():
        return PROFILE_PATH.read_text().strip()
    return "CS student interested in ML and systems, looking for internships and research roles."


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


def supervisor_score(agent_score: sup.AgentScore) -> dict:
    return {
        "score": agent_score.score,
        "passed": agent_score.passed,
        "flags": agent_score.flags,
        "reasoning": agent_score.reasoning,
        "rule_checks": agent_score.rule_checks,
    }


# ── Request models ────────────────────────────────────────────────────────────

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


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "provider": llm.active_provider(),
        "model": llm.active_model(),
    }


@app.get("/api/profile")
def get_profile():
    return {"content": load_profile()}


@app.post("/api/scout")
def run_scout(req: ScoutRequest):
    """Stage 1 — Scout Agent searches Reddit and HN, Supervisor evaluates results."""
    search_query = (
        f"{req.topic} {'job opening hiring internship' if req.mode == 'jobs' else 'open problem'}"
    )
    try:
        posts = scout.run(search_query)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scout failed: {e}")

    if not posts:
        raise HTTPException(status_code=404, detail="No posts found. Try a different topic.")

    scout_eval = sup.evaluate_scout(posts, req.topic)

    return {
        "posts": [serialize_post(p) for p in posts],
        "count": len(posts),
        "supervisor": supervisor_score(scout_eval),
    }


@app.post("/api/analyze")
def run_analyst(req: AnalyzeRequest):
    """Stage 2 — Analyst Agent scores each post, Supervisor checks calibration."""
    profile = load_profile()
    post_objs = [dict_to_post(p) for p in req.posts]

    opportunities = []
    for post_obj in post_objs:
        analysis = analyst.run(post_obj, profile)
        if (
            analysis
            and analysis.get("fit_score", 0) >= 5
            and analysis.get("contact_type") != "skip"
        ):
            opportunities.append({
                "post": serialize_post(post_obj),
                "analysis": analysis,
            })

    opportunities.sort(key=lambda x: x["analysis"].get("fit_score", 0), reverse=True)

    analyst_eval = sup.evaluate_analyst(
        [(dict_to_post(o["post"]), o["analysis"]) for o in opportunities],
        total_posts=len(post_objs),
    )

    return {
        "opportunities": opportunities,
        "count": len(opportunities),
        "supervisor": supervisor_score(analyst_eval),
    }


@app.post("/api/strategize")
def run_strategist(req: StrategizeRequest):
    """Stage 3 — Strategist Agent picks who to contact and how."""
    profile = load_profile()
    post_obj = dict_to_post(req.post)

    strategy = strategist.run(post_obj, req.analysis, profile)
    if not strategy:
        raise HTTPException(status_code=500, detail="Strategist failed to produce a strategy.")

    strat_eval = sup.evaluate_strategist(strategy, req.analysis)

    return {
        "strategy": strategy,
        "supervisor": supervisor_score(strat_eval),
    }


@app.post("/api/write")
def run_writer(req: WriteRequest):
    """Stage 4 — Writer Agent drafts the email, Supervisor checks quality."""
    profile = load_profile()
    post_obj = dict_to_post(req.post)

    draft = writer.run(post_obj, req.analysis, req.strategy, profile)
    writer_eval = sup.evaluate_writer(draft, req.strategy)

    return {
        "draft": draft,
        "word_count": len(draft.split()),
        "supervisor": supervisor_score(writer_eval),
    }


@app.post("/api/log")
def run_log(req: LogRequest):
    """Log the outreach attempt and all supervisor scores to W&B."""
    post_obj = dict_to_post(req.post)
    try:
        run_id = tracker.log(
            post_obj,
            req.analysis,
            req.strategy,
            req.draft,
            sent=req.sent,
            supervisor_summary=req.supervisor_summary,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"W&B logging failed: {e}")
    return {"run_id": run_id}
