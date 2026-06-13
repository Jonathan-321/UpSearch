#!/usr/bin/env python3
"""
UpSearch Autonomous Scheduler — persistent duration contract with rediscovery.

Usage:
  python run_scheduler.py                          # run until queue empty (--once mode)
  python run_scheduler.py --duration 24            # run for up to 24 hours, rediscover when empty
  python run_scheduler.py --once                   # explicit: exit when queue empty
  python run_scheduler.py --test --max-jobs 2      # quick test: 2 jobs, 1 lane
  python run_scheduler.py --companies 10           # run 10 company pipelines
  python run_scheduler.py --duration 48 --rediscovery-interval 1800   # 48h, rediscover every 30 min

The scheduler:
  1. Enqueues initial tasks (profile refresh, discovery per lane, company pipelines)
  2. Loops: dequeue → execute → report
  3. When queue empty AND --duration > 0 AND not --once:
       sleeps for --rediscovery-interval, then rediscovers all lanes and enqueues new candidates
  4. Writes granular progress reports to .upsearch/loop-summary/
  5. Exits when queue empty (--once or no --duration), deadline elapses, or signal received

Reports distinguish:
  - processed:       jobs completed successfully
  - send_ready:      subset of processed where QA passed (packet crm_status = "prepared")
  - blocked:         jobs that failed pipeline/checkup steps (business-logic errors)
  - operational_exceptions: jobs that failed due to infrastructure errors (DB, unexpected crashes)

All state is persisted to SQLite via the scheduled_jobs table.
Server restarts are safe — the queue survives.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

# Ensure we can import from the project
sys.path.insert(0, str(Path(__file__).resolve().parent))

from dotenv import load_dotenv

load_dotenv(override=True)

from upsearch.profile_source_fetch import fetch_profile_sources, load_cached_report
from upsearch.auto_discovery import discover
from upsearch import orchestrator_service, runtime
import db


LOOP_SUMMARY_DIR = Path(".upsearch/loop-summary")
DEFAULT_LANES = ["ai_infra", "inference_systems", "agentic_ai"]
REPORT_INTERVAL = 3  # Write progress report every N completed jobs
STALE_HOURS = 24  # Re-fetch profile sources if older than this
DEFAULT_REDISCOVERY_INTERVAL = 3600  # seconds (1 hour)
MAX_IDLE_CYCLES = None  # None = unlimited idle cycles; set to int for hard cap


# ── Structured result types ────────────────────────────────────────────────────


@dataclass
class JobResult:
    """Structured outcome of executing a single job."""
    status: str  # "processed" | "blocked" | "operational_exception"
    error: str | None = None
    send_ready: bool = False


@dataclass
class SchedulerCounters:
    """Granular counters for progress and final reports."""
    processed: int = 0
    send_ready: int = 0
    blocked: int = 0
    operational_exceptions: int = 0
    errors: list[str] = field(default_factory=list)
    total_jobs_processed: int = 0

    @property
    def total(self) -> int:
        return self.processed + self.blocked + self.operational_exceptions


# ── Helpers ────────────────────────────────────────────────────────────────────


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def log(msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def count_companies_in_db() -> int:
    """How many companies have been researched so far this session."""
    with db.conn() as c:
        row = c.execute("SELECT COUNT(*) as cnt FROM companies").fetchone()
        return row["cnt"] if row else 0


def source_cache_is_fresh() -> bool:
    """Check if the profile source cache is < STALE_HOURS old."""
    cached = load_cached_report()
    if not cached or not cached.get("fetched_at"):
        return False
    try:
        fetched = datetime.fromisoformat(cached["fetched_at"])
        age = datetime.now(timezone.utc) - fetched
        return age.total_seconds() < STALE_HOURS * 3600
    except (ValueError, TypeError):
        return False


def check_company_has_pending_job(company_name: str) -> bool:
    """Return True if there's already a queued/running pipeline job for this company."""
    with db.conn() as c:
        rows = c.execute(
            """SELECT COUNT(*) as cnt FROM scheduled_jobs
               WHERE job_type='run_pipeline'
                 AND status IN ('queued', 'running')
                 AND json_extract(params, '$.company_name') = ?""",
            (company_name,),
        ).fetchall()
        return bool(rows and rows[0]["cnt"] > 0)


def _has_pending_discovery_for_lane(lane: str) -> bool:
    with db.conn() as c:
        row = c.execute(
            """SELECT COUNT(*) as cnt FROM scheduled_jobs
               WHERE job_type='discover_companies'
                 AND status IN ('queued', 'running')
                 AND json_extract(params, '$.lane') = ?""",
            (lane,),
        ).fetchone()
        return bool(row and row["cnt"] > 0)


def _has_pending_refresh() -> bool:
    with db.conn() as c:
        row = c.execute(
            """SELECT COUNT(*) as cnt FROM scheduled_jobs
               WHERE job_type='refresh_profile'
                 AND status IN ('queued', 'running')"""
        ).fetchone()
        return bool(row and row["cnt"] > 0)


def _loop_decision(
    *,
    once_mode: bool,
    deadline: float,
    max_jobs: int,
    total_processed: int,
    idle_cycle_count: int,
    max_idle_cycles: int | None,
    now: float | None = None,
) -> dict:
    """Pure decision helper for the scheduler loop.

    The main loop still owns DB dequeueing, sleeping, and side effects. This
    helper makes the duration contract testable without network or LLM calls.
    """
    now = time.monotonic() if now is None else now
    if now >= deadline:
        return {"action": "exit", "reason": "deadline reached"}
    if max_jobs > 0 and total_processed >= max_jobs:
        return {"action": "exit", "reason": "max jobs reached"}
    pending = db.get_pending_job_count()
    if pending > 0:
        return {"action": "wait", "reason": f"{pending} queued/running jobs remain"}
    if once_mode:
        return {"action": "exit", "reason": "queue drained in once mode"}
    if max_idle_cycles is not None and idle_cycle_count >= max_idle_cycles:
        return {"action": "exit", "reason": "max idle cycles reached"}
    return {
        "action": "idle_rediscover",
        "reason": "queue idle before rediscovery",
        "next_idle_cycle": idle_cycle_count + 1,
    }


# ── Task Executors ──────────────────────────────────────────────────────────────


def execute_refresh_profile(params: dict) -> JobResult:
    """Refresh the profile source cache. Returns a JobResult."""
    profile_path = Path("profile.txt")
    if not profile_path.exists():
        return JobResult("blocked", error="profile.txt not found")
    content = profile_path.read_text(encoding="utf-8").strip()
    if not content:
        return JobResult("blocked", error="profile.txt is empty")
    try:
        fetch_profile_sources(content)
        log("Profile source cache refreshed")
        return JobResult("processed")
    except Exception as e:
        return JobResult("operational_exception", error=f"Profile source refresh failed: {e}")


def execute_discover_companies(params: dict) -> JobResult:
    """Discover companies in the given lane and enqueue pipeline jobs."""
    lane = params.get("lane", "ai_infra")
    candidates = discover(lane, limit=params.get("max_candidates", 5))
    if not candidates:
        log(f"Discovery in '{lane}': no verified companies found")
        return JobResult("processed")

    enqueued = 0
    for c in candidates:
        canonical_name = getattr(c, "canonical_name", "") or c.name
        website = getattr(c, "website", "")
        official_domain = getattr(c, "official_domain", "")
        identity_status = getattr(c, "identity_status", "unverified")
        identity_confidence = getattr(c, "identity_confidence", 0)
        identity_reason = getattr(c, "identity_reason", "")

        # Check if company already exists in DB before writing the discovery
        # record. Otherwise a brand-new candidate would be inserted and then
        # immediately treated as pre-existing, which prevents enqueueing.
        existing = db.get_company(c.name)
        if existing:
            candidate_company_id = existing["id"]
        else:
            candidate_company_id = db.upsert_company(
                c.name,
                canonical_name=canonical_name,
                website=website,
                official_domain=official_domain,
                identity_status=identity_status,
                identity_confidence=identity_confidence,
                identity_reason=identity_reason,
                lane=lane,
                fit_score=getattr(c, "fit_guess", 0.5) * 10,
                source_urls=json.dumps(c.source_urls),
                status="sourced",
            )
        for idx, url in enumerate(c.source_urls):
            db.insert_source(
                url,
                title=c.evidence[idx] if idx < len(c.evidence) else "",
                source_type="company_identity",
                claim_type="company_identity",
                verified=identity_status == "verified",
                metadata={
                    "identity_confidence": identity_confidence,
                    "identity_reason": identity_reason,
                    "official_domain": official_domain,
                },
                company_id=candidate_company_id,
            )
        if existing:
            try:
                existing_urls = json.loads(existing.get("source_urls") or "[]")
            except json.JSONDecodeError:
                existing_urls = []
            merged_urls = list(dict.fromkeys(
                [url for url in existing_urls if isinstance(url, str) and url.strip()]
                + [url for url in c.source_urls if isinstance(url, str) and url.strip()]
            ))
            db.upsert_company(
                c.name,
                website=website or existing.get("website") or "",
                lane=existing.get("lane") or lane,
                fit_score=max(existing.get("fit_score") or 0, c.fit_guess * 10),
                canonical_name=canonical_name,
                official_domain=official_domain or existing.get("official_domain") or "",
                identity_status=identity_status,
                identity_confidence=identity_confidence,
                identity_reason=identity_reason,
                source_urls=json.dumps(merged_urls),
            )
            if merged_urls != existing_urls:
                log(f"  Refreshed sources for {c.name}: {len(merged_urls)} URLs")
            log(f"  Already have {c.name}, skipping")
            continue
        if check_company_has_pending_job(c.name):
            log(f"  Already queued {c.name}, skipping")
            continue
        # Enqueue a pipeline run
        db.enqueue_job(
            "run_pipeline",
            params={"company_name": c.name, "lane": lane, "source_urls": c.source_urls},
            lane=lane,
            priority=1,
            max_retries=2,
        )
        enqueued += 1

    log(f"Discovery in '{lane}': {len(candidates)} found, {enqueued} enqueued")
    return JobResult("processed")


def execute_run_pipeline(params: dict) -> JobResult:
    """Run the full packet pipeline via the shared orchestrator service."""
    company_name = params.get("company_name", "")
    lane = params.get("lane", "ai_infra")
    discovery_source_urls = params.get("source_urls", [])
    if not company_name:
        return JobResult("blocked", error="No company_name in job params")

    log(f"Pipeline: {company_name} ({lane})")

    try:
        raw_profile = (
            Path("profile.txt").read_text(encoding="utf-8")
            if Path("profile.txt").exists()
            else ""
        )

        result = asyncio.run(
            orchestrator_service.run_pipeline(
                company_name=company_name,
                lane=lane,
                profile_text=raw_profile,
                run_id=params.get("run_id"),
                discovery_source_urls=discovery_source_urls,
            )
        )

        if result.status == "complete":
            return JobResult("processed", send_ready=True)
        elif result.status == "blocked":
            error_reason = result.qa_result.get("flags", [result.status])[0] if isinstance(result.qa_result, dict) else result.status
            return JobResult("blocked", error=f"{company_name}: {error_reason}")
        else:
            return JobResult(
                "operational_exception",
                error=f"Pipeline failed for {company_name}: status={result.status}",
            )

    except Exception as e:
        return JobResult("operational_exception", error=f"Pipeline failed for {company_name}: {e}")


# ── Task Dispatch ───────────────────────────────────────────────────────────────


def execute_job(job: dict) -> JobResult:
    """Execute a single job by type."""
    job_type = job["job_type"]
    params = json.loads(job.get("params", "{}") or "{}")
    lane = job.get("lane", "")

    log(f"Job [{job['id']}]: {job_type} ({lane or 'no lane'})")

    if job_type == "refresh_profile":
        return execute_refresh_profile(params)
    elif job_type == "discover_companies":
        return execute_discover_companies(params)
    elif job_type == "run_pipeline":
        params["run_id"] = f"scheduler-job-{job['id']}"
        return execute_run_pipeline(params)
    else:
        return JobResult("operational_exception", error=f"Unknown job type: {job_type}")


# ── Progress Reporting ──────────────────────────────────────────────────────────


def write_progress_report(counters: SchedulerCounters) -> None:
    """Write a progress report to .upsearch/loop-summary/."""
    LOOP_SUMMARY_DIR.mkdir(parents=True, exist_ok=True)
    report_path = LOOP_SUMMARY_DIR / f"progress-{datetime.now().strftime('%H%M')}.json"
    companies_count = count_companies_in_db()

    job_summary = db.get_job_summary()
    report = {
        "timestamp": utc_now(),
        "processed": counters.processed,
        "send_ready": counters.send_ready,
        "blocked": counters.blocked,
        "operational_exceptions": counters.operational_exceptions,
        "jobs_total_processed": counters.total_jobs_processed,
        "companies_in_db": companies_count,
        "pending_jobs": db.get_pending_job_count(),
        "errors": counters.errors[-10:],
        "recent_jobs": job_summary[-15:],
    }
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def write_final_report(counters: SchedulerCounters, start_time: float, end_time: float) -> None:
    """Write the final summary report."""
    LOOP_SUMMARY_DIR.mkdir(parents=True, exist_ok=True)
    elapsed = end_time - start_time
    report_path = LOOP_SUMMARY_DIR / "final-report.json"
    job_summary = db.get_job_summary()
    companies_count = count_companies_in_db()

    report = {
        "timestamp": utc_now(),
        "elapsed_seconds": round(elapsed),
        "elapsed_hours": round(elapsed / 3600, 2),
        "processed": counters.processed,
        "send_ready": counters.send_ready,
        "blocked": counters.blocked,
        "operational_exceptions": counters.operational_exceptions,
        "jobs_total_processed": counters.total_jobs_processed,
        "companies_in_db": companies_count,
        "all_jobs": job_summary,
        "errors": counters.errors[-20:],
        "status": "complete" if counters.operational_exceptions == 0 else "completed_with_operational_exceptions",
    }
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    log(f"Final report: {report_path}")


# ── Main Loop ───────────────────────────────────────────────────────────────────


def enqueue_initial_tasks(lanes: list[str], max_companies: int | None = None) -> None:
    """Enqueue the startup task chain: refresh profile → discover each lane → run pipelines."""
    # 1. One profile source refresh (high priority, always first).
    # Freshness affects retry budget, not job count.
    refresh_retries = 1 if source_cache_is_fresh() else 2
    db.enqueue_job("refresh_profile", priority=10, max_retries=refresh_retries)

    # 2. Discovery per lane
    for lane in lanes:
        db.enqueue_job("discover_companies",
                       params={"lane": lane, "max_candidates": max_companies or 5},
                       lane=lane, priority=5, max_retries=1)

    log(f"Enqueued initial tasks: refresh + {len(lanes)} discovery jobs")


def _enqueue_rediscovery(lanes: list[str], max_companies: int = 5) -> int:
    """Enqueue discovery jobs for lanes, skipping lanes that already have a pending
    discovery job to prevent duplicate-job explosions."""
    enqueued = 0
    for lane in lanes:
        if _has_pending_discovery_for_lane(lane):
            log(f"  Rediscovery for '{lane}' already queued/running, skipping")
            continue
        db.enqueue_job(
            "discover_companies",
            params={"lane": lane, "max_candidates": max_companies},
            lane=lane,
            priority=5,
            max_retries=1,
        )
        enqueued += 1
        log(f"  Enqueued rediscovery for lane '{lane}'")

    # Also re-enqueue a profile refresh so the source cache stays current
    if not _has_pending_refresh():
        db.enqueue_job("refresh_profile", priority=9, max_retries=1)
        enqueued += 1
    return enqueued


def main() -> None:
    parser = argparse.ArgumentParser(description="UpSearch Autonomous Scheduler")
    parser.add_argument("--duration", type=int, default=0,
                        help="Max runtime in hours (0 = run until queue empty, --once mode)")
    parser.add_argument("--once", action="store_true", default=False,
                        help="Exit when queue is first empty (default when --duration is 0)")
    parser.add_argument("--rediscovery-interval", type=int, default=DEFAULT_REDISCOVERY_INTERVAL,
                        help=f"Seconds to idle before rediscovering lanes (default: {DEFAULT_REDISCOVERY_INTERVAL})")
    parser.add_argument("--max-idle-cycles", type=int, default=MAX_IDLE_CYCLES,
                        help="Max rediscovery cycles before exit (default: unlimited)")
    parser.add_argument("--test", action="store_true",
                        help="Test mode: single lane, quick cycle")
    parser.add_argument("--max-jobs", type=int, default=0,
                        help="Max jobs to process before exiting (0 = no limit)")
    parser.add_argument("--companies", type=int, default=0,
                        help="Max companies per lane to discover and run")
    parser.add_argument("--lanes", nargs="+", default=None,
                        help="Lanes to process (default: ai_infra inference_systems agentic_ai)")
    args = parser.parse_args()

    # Config
    lanes = args.lanes or DEFAULT_LANES
    max_jobs = args.max_jobs
    once_mode = args.once or args.duration == 0
    rediscovery_interval = max(1, args.rediscovery_interval)
    max_idle_cycles = args.max_idle_cycles  # None means unlimited
    idle_cycle_count = 0

    if args.test:
        max_jobs = max(max_jobs, 5)
        lanes = lanes[:1]
        log("TEST MODE: single lane, max 5 jobs")

    log(f"UpSearch Autonomous Scheduler starting")
    log(f"  Lanes: {lanes}")
    if args.duration:
        log(f"  Max runtime: {args.duration}h")
        log(f"  Rediscovery interval: {rediscovery_interval}s")
        if max_idle_cycles is not None:
            log(f"  Max idle cycles before drain-exit: {max_idle_cycles}")
    else:
        log(f"  Mode: run-until-drained (--once)")
    log(f"  Max jobs: {max_jobs or 'unlimited'}")
    log(f"  Companies per lane: {args.companies or 5}")
    log("")

    # Initialize DB
    db.init_db()

    recovered_jobs = runtime.recover_interrupted_jobs()
    pending_jobs = db.get_pending_job_count()
    if pending_jobs:
        log(
            f"Resuming {pending_jobs} queued job(s)"
            + (f", including {recovered_jobs} interrupted job(s)" if recovered_jobs else "")
        )
    else:
        enqueue_initial_tasks(lanes, max_companies=args.companies or 5)

    # Main loop
    counters = SchedulerCounters()
    start_time = time.monotonic()
    deadline = start_time + args.duration * 3600 if args.duration else float("inf")
    last_report_count = 0

    while True:
        # Dequeue next job
        job = db.dequeue_next_job()
        if job is None:
            decision = _loop_decision(
                once_mode=once_mode,
                deadline=deadline,
                max_jobs=max_jobs,
                total_processed=counters.total_jobs_processed,
                idle_cycle_count=idle_cycle_count,
                max_idle_cycles=max_idle_cycles,
            )
            if decision["action"] == "exit":
                log(f"{decision['reason']}, shutting down")
                break
            if decision["action"] == "wait":
                log(decision["reason"])
                time.sleep(5)
                continue

            idle_cycle_count = decision["next_idle_cycle"]
            log(f"Queue empty — idle cycle #{idle_cycle_count}. "
                f"Waiting {rediscovery_interval}s before rediscovery...")
            remaining = max(0.0, deadline - time.monotonic())
            time.sleep(min(rediscovery_interval, remaining))

            # Deadline re-check after long sleep
            if time.monotonic() >= deadline:
                log("Deadline reached during idle wait, shutting down")
                break

            log("Idle wait complete — rediscovering lanes")
            # Enqueue fresh discovery jobs, deduplicating against existing companies
            _enqueue_rediscovery(lanes, max_companies=args.companies or 5)
            continue

        if time.monotonic() >= deadline:
            log("Runtime limit reached before next job, shutting down")
            break
        if max_jobs > 0 and counters.total_jobs_processed >= max_jobs:
            log(f"Reached max jobs ({max_jobs}), shutting down")
            break

        # Execute
        result = execute_job(job)
        counters.total_jobs_processed += 1

        if result.status == "operational_exception":
            error = result.error or "Unknown operational exception"
            new_status = db.fail_job(job["id"], error, retry=True)
            if new_status == "queued":
                log(f"  ↻ Job {job['id']} queued for retry: {error[:100]}")
            else:
                counters.operational_exceptions += 1
                counters.errors.append(error)
                log(f"  ✗ Job {job['id']} failed: {error[:120]}")
        elif result.status == "blocked":
            db.complete_job(job["id"])
            counters.blocked += 1
            if result.error:
                counters.errors.append(result.error)
            log(f"  ! Job {job['id']} processed but blocked: {(result.error or 'review required')[:120]}")
        else:
            db.complete_job(job["id"])
            counters.processed += 1
            if result.send_ready:
                counters.send_ready += 1
            log(f"  ✓ Job {job['id']} processed (total: {counters.processed})")

        # Progress report every REPORT_INTERVAL completed jobs
        completed_outcomes = counters.processed + counters.blocked + counters.operational_exceptions
        if (
            completed_outcomes > 0
            and completed_outcomes % REPORT_INTERVAL == 0
            and completed_outcomes > last_report_count
        ):
            last_report_count = completed_outcomes
            write_progress_report(counters)
            log(
                "Progress report written "
                f"({counters.processed} processed, {counters.blocked} blocked, "
                f"{counters.operational_exceptions} operational exceptions)"
            )

        # Brief pause between jobs to avoid rate limits
        time.sleep(2)

    # Final report
    end_time = time.monotonic()
    write_final_report(counters, start_time, end_time)

    elapsed = end_time - start_time
    log(f"\n{'='*50}")
    log(f"Scheduler finished")
    log(f"  Elapsed: {elapsed/3600:.1f}h ({elapsed:.0f}s)")
    log(f"  Processed: {counters.processed}")
    log(f"  Send-ready: {counters.send_ready}")
    log(f"  Blocked: {counters.blocked}")
    log(f"  Operational exceptions: {counters.operational_exceptions}")
    log(f"  Jobs attempted: {counters.total_jobs_processed}")
    if counters.errors:
        log(f"  Last issue: {counters.errors[-1][:150]}")
    log(f"  Companies in DB: {count_companies_in_db()}")
    log(f"  Report: {LOOP_SUMMARY_DIR / 'final-report.json'}")


if __name__ == "__main__":
    main()
