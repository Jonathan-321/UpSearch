"""
SQLite CRM — the data backbone for Opportunity Intelligence OS.
All entities: companies, problems, people, packets, messages, approvals, send events, follow-ups.
"""
import os
import sqlite3
import json
import hashlib
from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, urlunparse

from upsearch.person_validation import person_name_rejection
from upsearch.runtime import DEFAULT_DB_PATH, resolve_db_path

# DB path policy (027): when UPSEARCH_DB_PATH is set, the path resolved by
# upsearch.runtime wins, so isolated runs like scripts/run-release-acceptance.sh
# really do hit their temporary database instead of the real repository one.
# Without the override we keep runtime's relative DEFAULT_DB_PATH so the path
# still resolves against the current working directory per connection —
# several tests chdir to a tmp dir before init_db(), and freezing the CWD at
# import would silently redirect their writes into the real database.
# upsearch.runtime never imports db at module scope, so there is no cycle.
# Tests monkeypatch db.DB_PATH directly; conn() reads the global on every call.
DB_PATH = resolve_db_path() if os.environ.get("UPSEARCH_DB_PATH") else DEFAULT_DB_PATH


def _normalize_url(value: str | None) -> str:
    """Normalize a URL enough for evidence dedupe. Returns empty for non-URLs."""
    if not value or not isinstance(value, str):
        return ""
    raw = value.strip()
    if not raw:
        return ""
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/")
    return urlunparse((parsed.scheme.lower(), netloc, path, "", parsed.query, ""))


def _url_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            return [url for url in [_normalize_url(stripped)] if url]
        if isinstance(parsed, str) and parsed == stripped:
            return [url for url in [_normalize_url(stripped)] if url]
        return _url_list(parsed)
    if isinstance(value, dict):
        return []
    if isinstance(value, (list, tuple, set)):
        urls = [_normalize_url(str(item)) for item in value]
        return [url for url in dict.fromkeys(urls) if url]
    return []


def _source_type_for_url(url: str, fallback: str = "other") -> str:
    host = urlparse(url).hostname or ""
    if "linkedin.com" in host:
        return "linkedin"
    if "github.com" in host:
        return "github"
    if host in {"x.com", "twitter.com"} or host.endswith(".x.com") or host.endswith(".twitter.com"):
        return "social"
    if "news.ycombinator.com" in host:
        return "hacker_news"
    if "reddit.com" in host:
        return "reddit"
    return fallback


def _load_json_value(value, fallback):
    if isinstance(value, (dict, list)):
        return value
    if not isinstance(value, str) or not value.strip():
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def _dump_json_value(value) -> str:
    return json.dumps(value)


def message_digest(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


@contextmanager
def conn():
    # check_same_thread stays True (the default): every conn() opens, uses, and
    # closes a fresh connection within the calling thread, so threaded callers
    # like run_scheduler never share a handle across threads.
    # WAL + busy_timeout let the API server and the background worker write
    # concurrently without "database is locked". WAL is a persistent per-database
    # property, so re-applying it on each connect is cheap and idempotent.
    # DB_PATH is read fresh on every call so UPSEARCH_DB_PATH / chdir-based test
    # isolation keeps working — the path is never frozen at import time.
    c = sqlite3.connect(DB_PATH, timeout=5.0)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA busy_timeout=5000")
    try:
        yield c
        c.commit()
    finally:
        c.close()


def init_db():
    """Create all tables. Safe to call on every startup."""
    with conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS user_profile (
            id          INTEGER PRIMARY KEY,
            name        TEXT,
            email       TEXT,
            school      TEXT,
            github_url  TEXT,
            resume_path TEXT,
            interests   TEXT DEFAULT '[]',
            constraints TEXT DEFAULT '{}',
            preferred_roles TEXT DEFAULT '[]',
            background_summary TEXT,
            raw_profile TEXT,
            updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS companies (
            id              INTEGER PRIMARY KEY,
            name            TEXT NOT NULL UNIQUE,
            canonical_name  TEXT,
            website         TEXT,
            official_domain TEXT,
            identity_status TEXT DEFAULT 'unverified',
            identity_confidence REAL DEFAULT 0,
            identity_reason TEXT,
            lane            TEXT,
            fit_score       REAL DEFAULT 0,
            hiring_status   TEXT,
            sponsorship_notes TEXT,
            source_urls     TEXT DEFAULT '[]',
            status          TEXT DEFAULT 'sourced',
            notes           TEXT,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS problems (
            id              INTEGER PRIMARY KEY,
            company_id      INTEGER REFERENCES companies(id),
            title           TEXT NOT NULL,
            description     TEXT,
            source_urls     TEXT DEFAULT '[]',
            relevance_score REAL DEFAULT 0,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS people (
            id              INTEGER PRIMARY KEY,
            company_id      INTEGER REFERENCES companies(id),
            name            TEXT NOT NULL,
            role            TEXT,
            linkedin_url    TEXT,
            twitter_url     TEXT,
            github_url      TEXT,
            source_url      TEXT,
            verification_status TEXT DEFAULT 'unverified',
            verification_reason TEXT DEFAULT '',
            relevance_score REAL DEFAULT 0,
            relevance_reason TEXT,
            proximity       TEXT,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS sources (
            id          INTEGER PRIMARY KEY,
            url         TEXT NOT NULL,
            title       TEXT,
            summary     TEXT,
            source_type TEXT,
            claim_type  TEXT,
            verified    INTEGER DEFAULT 0,
            metadata    TEXT DEFAULT '{}',
            company_id  INTEGER REFERENCES companies(id),
            problem_id  INTEGER REFERENCES problems(id),
            person_id   INTEGER REFERENCES people(id),
            fetched_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS packets (
            id              INTEGER PRIMARY KEY,
            company_id      INTEGER NOT NULL REFERENCES companies(id),
            company_fit     TEXT,
            open_problem    TEXT,
            people_map      TEXT DEFAULT '[]',
            technical_note  TEXT,
            adjacent_proof  TEXT,
            outreach_drafts TEXT DEFAULT '{}',
            verification    TEXT DEFAULT '{}',
            crm_status      TEXT DEFAULT 'prepared',
            qa_score        REAL,
            qa_flags        TEXT DEFAULT '[]',
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS messages (
            id          INTEGER PRIMARY KEY,
            packet_id   INTEGER REFERENCES packets(id),
            person_id   INTEGER REFERENCES people(id),
            variant     TEXT,
            content     TEXT,
            word_count  INTEGER,
            status      TEXT DEFAULT 'draft',
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS approvals (
            id          INTEGER PRIMARY KEY,
            message_id  INTEGER REFERENCES messages(id),
            approved_by TEXT DEFAULT 'user',
            approved_at TIMESTAMP,
            notes       TEXT
        );

        CREATE TABLE IF NOT EXISTS send_events (
            id          INTEGER PRIMARY KEY,
            message_id  INTEGER REFERENCES messages(id),
            approval_id INTEGER REFERENCES approvals(id),
            sent_at     TIMESTAMP,
            channel     TEXT,
            status      TEXT,
            body_digest TEXT,
            error_message TEXT
        );

        CREATE TABLE IF NOT EXISTS follow_ups (
            id          INTEGER PRIMARY KEY,
            message_id  INTEGER REFERENCES messages(id),
            approval_id INTEGER REFERENCES approvals(id),
            body_digest TEXT,
            due_date    DATE,
            status      TEXT DEFAULT 'pending',
            notes       TEXT,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS run_records (
            id              INTEGER PRIMARY KEY,
            run_id          TEXT NOT NULL UNIQUE,
            company_name    TEXT NOT NULL,
            lane            TEXT NOT NULL DEFAULT 'ai_infra',
            started_at      TIMESTAMP,
            completed_at    TIMESTAMP,
            status          TEXT NOT NULL DEFAULT 'running',
            steps_completed TEXT DEFAULT '[]',
            current_step    TEXT,
            qa_score        REAL,
            final_status    TEXT,
            trace_path      TEXT,
            error_message   TEXT,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS trace_events (
            id              INTEGER PRIMARY KEY,
            run_id          TEXT NOT NULL REFERENCES run_records(run_id),
            event_type      TEXT NOT NULL,
            status          TEXT,
            timestamp       TIMESTAMP NOT NULL,
            agent           TEXT,
            agent_role      TEXT,
            reads           TEXT DEFAULT '[]',
            writes          TEXT DEFAULT '[]',
            output_summary  TEXT,
            latency_ms      INTEGER,
            from_agent      TEXT,
            to_agent        TEXT,
            payload_keys    TEXT DEFAULT '[]',
            reason          TEXT,
            payload         TEXT DEFAULT '{}'
        );

        CREATE INDEX IF NOT EXISTS idx_trace_run_id ON trace_events(run_id);
        CREATE INDEX IF NOT EXISTS idx_trace_timestamp ON trace_events(timestamp);

        CREATE TABLE IF NOT EXISTS scheduled_jobs (
            id          INTEGER PRIMARY KEY,
            job_type    TEXT NOT NULL,
            status      TEXT NOT NULL DEFAULT 'queued',
            params      TEXT DEFAULT '{}',
            retry_count INTEGER DEFAULT 0,
            max_retries INTEGER DEFAULT 3,
            priority    INTEGER DEFAULT 0,
            lane        TEXT,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            started_at  TIMESTAMP,
            completed_at TIMESTAMP,
            error_message TEXT
        );
        """)
        people_cols = {
            row["name"]
            for row in c.execute("PRAGMA table_info(people)").fetchall()
        }
        if "source_url" not in people_cols:
            c.execute("ALTER TABLE people ADD COLUMN source_url TEXT")
        if "verification_status" not in people_cols:
            c.execute("ALTER TABLE people ADD COLUMN verification_status TEXT DEFAULT 'unverified'")
        if "verification_reason" not in people_cols:
            c.execute("ALTER TABLE people ADD COLUMN verification_reason TEXT DEFAULT ''")

        trace_cols = {
            row["name"]
            for row in c.execute("PRAGMA table_info(trace_events)").fetchall()
        }
        if "payload" not in trace_cols:
            c.execute("ALTER TABLE trace_events ADD COLUMN payload TEXT DEFAULT '{}'")

        company_cols = {
            row["name"]
            for row in c.execute("PRAGMA table_info(companies)").fetchall()
        }
        for col_name, col_type in {
            "canonical_name": "TEXT",
            "official_domain": "TEXT",
            "identity_status": "TEXT DEFAULT 'unverified'",
            "identity_confidence": "REAL DEFAULT 0",
            "identity_reason": "TEXT",
        }.items():
            if col_name not in company_cols:
                c.execute(f"ALTER TABLE companies ADD COLUMN {col_name} {col_type}")

        source_cols = {
            row["name"]
            for row in c.execute("PRAGMA table_info(sources)").fetchall()
        }
        for col_name, col_type in {
            "claim_type": "TEXT",
            "verified": "INTEGER DEFAULT 0",
            "metadata": "TEXT DEFAULT '{}'",
        }.items():
            if col_name not in source_cols:
                c.execute(f"ALTER TABLE sources ADD COLUMN {col_name} {col_type}")

        approval_cols = {
            row["name"]
            for row in c.execute("PRAGMA table_info(approvals)").fetchall()
        }
        if "body_digest" not in approval_cols:
            c.execute("ALTER TABLE approvals ADD COLUMN body_digest TEXT")
        if "channel" not in approval_cols:
            c.execute("ALTER TABLE approvals ADD COLUMN channel TEXT")
        if "target" not in approval_cols:
            c.execute("ALTER TABLE approvals ADD COLUMN target TEXT")

        send_cols = {
            row["name"]
            for row in c.execute("PRAGMA table_info(send_events)").fetchall()
        }
        if "error_message" not in send_cols:
            c.execute("ALTER TABLE send_events ADD COLUMN error_message TEXT")
        if "body_digest" not in send_cols:
            c.execute("ALTER TABLE send_events ADD COLUMN body_digest TEXT")

        follow_up_cols = {
            row["name"]
            for row in c.execute("PRAGMA table_info(follow_ups)").fetchall()
        }
        if "approval_id" not in follow_up_cols:
            c.execute("ALTER TABLE follow_ups ADD COLUMN approval_id INTEGER REFERENCES approvals(id)")
        if "body_digest" not in follow_up_cols:
            c.execute("ALTER TABLE follow_ups ADD COLUMN body_digest TEXT")
        if "created_at" not in follow_up_cols:
            c.execute("ALTER TABLE follow_ups ADD COLUMN created_at TIMESTAMP")


# ── Company helpers ───────────────────────────────────────────────────────────

def upsert_company(name: str, **kwargs) -> int:
    with conn() as c:
        source_urls = _url_list(kwargs.get("source_urls"))
        identity_verified = kwargs.get("identity_status") == "verified"
        for k, v in kwargs.items():
            if isinstance(v, (list, dict)):
                kwargs[k] = json.dumps(v)
        existing = c.execute("SELECT id FROM companies WHERE name=?", (name,)).fetchone()
        if existing:
            fields = ", ".join(f"{k}=?" for k in kwargs)
            vals = list(kwargs.values()) + [name]
            if fields:
                c.execute(f"UPDATE companies SET {fields} WHERE name=?", vals)
            company_id = existing["id"]
        else:
            kwargs["name"] = name
            cols = ", ".join(kwargs.keys())
            placeholders = ", ".join("?" * len(kwargs))
            c.execute(f"INSERT INTO companies ({cols}) VALUES ({placeholders})", list(kwargs.values()))
            company_id = c.execute("SELECT last_insert_rowid()").fetchone()[0]

        for url in source_urls:
            _insert_source_row(
                c,
                url,
                title=f"{name} public source",
                source_type=_source_type_for_url(url, "company_signal"),
                claim_type="company_identity",
                verified=identity_verified,
                metadata={"recorded_by": "upsert_company"},
                company_id=company_id,
            )
        return company_id


def get_company(name: str) -> dict | None:
    with conn() as c:
        row = c.execute("SELECT * FROM companies WHERE name=?", (name,)).fetchone()
        return dict(row) if row else None


def list_companies(status: str | None = None, include_archived: bool = False) -> list[dict]:
    """List companies for the CRM, hiding archived rows by default (031).

    Archived means the company's own status is 'archived' or its packet was
    archived by run_legacy_archive(). An explicit status filter (including
    status='archived') bypasses the exclusion so the operator can still
    inspect archived rows on request.
    """
    with conn() as c:
        if status:
            rows = c.execute("SELECT * FROM companies WHERE status=? ORDER BY fit_score DESC", (status,)).fetchall()
        elif include_archived:
            rows = c.execute("SELECT * FROM companies ORDER BY fit_score DESC").fetchall()
        else:
            rows = c.execute(
                """SELECT * FROM companies
                   WHERE COALESCE(status, '') != 'archived'
                     AND id NOT IN (
                         SELECT company_id FROM packets WHERE crm_status='archived'
                     )
                   ORDER BY fit_score DESC"""
            ).fetchall()
        return [dict(r) for r in rows]


def set_company_status(company_id: int, status: str):
    with conn() as c:
        c.execute("UPDATE companies SET status=? WHERE id=?", (status, company_id))


def clear_company_generated_state(company_id: int):
    """Remove generated packet children before rebuilding a company packet.

    Company metadata stays intact, but problems, people, packets, draft messages,
    approvals, sends, follow-ups, and source rows are regenerated per run. This
    keeps repeated runs idempotent instead of accumulating stale packet rows.
    """
    with conn() as c:
        packet_rows = c.execute("SELECT id FROM packets WHERE company_id=?", (company_id,)).fetchall()
        packet_ids = [row["id"] for row in packet_rows]
        if packet_ids:
            placeholders = ",".join("?" for _ in packet_ids)
            message_rows = c.execute(
                f"SELECT id FROM messages WHERE packet_id IN ({placeholders})",
                packet_ids,
            ).fetchall()
            message_ids = [row["id"] for row in message_rows]
            if message_ids:
                msg_placeholders = ",".join("?" for _ in message_ids)
                c.execute(f"DELETE FROM follow_ups WHERE message_id IN ({msg_placeholders})", message_ids)
                c.execute(f"DELETE FROM send_events WHERE message_id IN ({msg_placeholders})", message_ids)
                c.execute(f"DELETE FROM approvals WHERE message_id IN ({msg_placeholders})", message_ids)
                c.execute(f"DELETE FROM messages WHERE id IN ({msg_placeholders})", message_ids)
            c.execute(f"DELETE FROM packets WHERE id IN ({placeholders})", packet_ids)

        c.execute(
            """DELETE FROM sources
               WHERE company_id=? AND (problem_id IS NOT NULL OR person_id IS NOT NULL)""",
            (company_id,),
        )
        c.execute("DELETE FROM problems WHERE company_id=?", (company_id,))
        c.execute("DELETE FROM people WHERE company_id=?", (company_id,))


# ── Source helpers ────────────────────────────────────────────────────────────

def _insert_source_row(
    c: sqlite3.Connection,
    url: str,
    *,
    title: str = "",
    summary: str = "",
    source_type: str = "other",
    claim_type: str = "",
    verified: bool = False,
    metadata: dict | None = None,
    company_id: int | None = None,
    problem_id: int | None = None,
    person_id: int | None = None,
) -> int:
    normalized_url = _normalize_url(url)
    if not normalized_url:
        return 0

    metadata_json = json.dumps(metadata or {})
    existing = c.execute(
        """SELECT id, verified FROM sources
           WHERE url=? AND COALESCE(company_id, 0)=COALESCE(?, 0)
             AND COALESCE(problem_id, 0)=COALESCE(?, 0)
             AND COALESCE(person_id, 0)=COALESCE(?, 0)
             AND COALESCE(claim_type, '')=COALESCE(?, '')""",
        (normalized_url, company_id, problem_id, person_id, claim_type),
    ).fetchone()
    if existing:
        c.execute(
            """UPDATE sources
               SET title=COALESCE(NULLIF(?, ''), title),
                   summary=COALESCE(NULLIF(?, ''), summary),
                   source_type=COALESCE(NULLIF(?, ''), source_type),
                   verified=?,
                   metadata=?,
                   fetched_at=CURRENT_TIMESTAMP
               WHERE id=?""",
            (
                title,
                summary,
                source_type,
                1 if verified or existing["verified"] else 0,
                metadata_json,
                existing["id"],
            ),
        )
        return existing["id"]

    c.execute(
        """INSERT INTO sources
           (url, title, summary, source_type, claim_type, verified, metadata,
            company_id, problem_id, person_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            normalized_url,
            title,
            summary,
            source_type,
            claim_type,
            1 if verified else 0,
            metadata_json,
            company_id,
            problem_id,
            person_id,
        ),
    )
    return c.execute("SELECT last_insert_rowid()").fetchone()[0]


def insert_source(
    url: str,
    *,
    title: str = "",
    summary: str = "",
    source_type: str = "other",
    claim_type: str = "",
    verified: bool = False,
    metadata: dict | None = None,
    company_id: int | None = None,
    problem_id: int | None = None,
    person_id: int | None = None,
) -> int:
    """Insert or reuse a source row for a concrete evidence URL."""
    with conn() as c:
        return _insert_source_row(
            c,
            url,
            title=title,
            summary=summary,
            source_type=source_type,
            claim_type=claim_type,
            verified=verified,
            metadata=metadata,
            company_id=company_id,
            problem_id=problem_id,
            person_id=person_id,
        )


def get_sources(company_id: int | None = None) -> list[dict]:
    with conn() as c:
        if company_id is None:
            rows = c.execute("SELECT * FROM sources ORDER BY fetched_at DESC").fetchall()
        else:
            rows = c.execute(
                "SELECT * FROM sources WHERE company_id=? ORDER BY fetched_at DESC",
                (company_id,),
            ).fetchall()
        return [dict(r) for r in rows]


def _get_evidence_summary(c: sqlite3.Connection, company_id: int) -> dict:
    company = c.execute(
        "SELECT identity_status FROM companies WHERE id=?",
        (company_id,),
    ).fetchone()
    identity_verified = bool(company and company["identity_status"] == "verified")

    rows = c.execute(
        """SELECT claim_type, COUNT(*) AS total, SUM(CASE WHEN verified=1 THEN 1 ELSE 0 END) AS verified
           FROM sources WHERE company_id=? GROUP BY claim_type""",
        (company_id,),
    ).fetchall()
    claims = {
        (row["claim_type"] or "unclassified"): {
            "total": int(row["total"] or 0),
            "verified": int(row["verified"] or 0),
        }
        for row in rows
    }
    company_sources = claims.get("company_identity", {"total": 0, "verified": 0})
    problem_sources = claims.get("open_problem", {"total": 0, "verified": 0})
    person_sources = claims.get("person_identity", {"total": 0, "verified": 0})

    missing: list[str] = []
    if not identity_verified:
        missing.append("verified company identity")
    if company_sources["verified"] < 1:
        missing.append("verified company source")
    if problem_sources["verified"] < 1:
        missing.append("verified problem source")
    if person_sources["verified"] < 1:
        missing.append("verified person source")

    return {
        "ready": not missing,
        "company_identity_verified": identity_verified,
        "claims": claims,
        "missing": missing,
    }


def get_evidence_summary(company_id: int) -> dict:
    with conn() as c:
        return _get_evidence_summary(c, company_id)


# ── Problem helpers ───────────────────────────────────────────────────────────

def insert_problem(company_id: int, title: str, description: str,
                   source_urls: list, relevance_score: float = 0) -> int:
    with conn() as c:
        urls = _url_list(source_urls)
        c.execute(
            "INSERT INTO problems (company_id, title, description, source_urls, relevance_score) VALUES (?,?,?,?,?)",
            (company_id, title, description, json.dumps(urls), relevance_score)
        )
        problem_id = c.execute("SELECT last_insert_rowid()").fetchone()[0]
        for url in urls:
            _insert_source_row(
                c,
                url,
                title=title,
                summary=description[:500],
                source_type=_source_type_for_url(url, "problem_signal"),
                claim_type="open_problem",
                verified=False,
                metadata={"recorded_by": "insert_problem"},
                company_id=company_id,
                problem_id=problem_id,
            )
        return problem_id


def get_problems(company_id: int) -> list[dict]:
    with conn() as c:
        rows = c.execute(
            "SELECT * FROM problems WHERE company_id=? ORDER BY relevance_score DESC",
            (company_id,)
        ).fetchall()
        return [dict(r) for r in rows]


# ── People helpers ────────────────────────────────────────────────────────────

def insert_person(company_id: int, name: str, role: str, **kwargs) -> int:
    with conn() as c:
        verification_status = kwargs.get("verification_status") or "unverified"
        verification_reason = kwargs.get("verification_reason") or ""
        contact_url_checks = kwargs.get("contact_url_checks") or {}
        c.execute(
            """INSERT INTO people (company_id, name, role, linkedin_url, twitter_url, github_url,
               source_url, verification_status, verification_reason, relevance_score,
               relevance_reason, proximity)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (company_id, name, role,
             kwargs.get("linkedin_url"), kwargs.get("twitter_url"), kwargs.get("github_url"),
             kwargs.get("source_url"),
             verification_status,
             verification_reason,
             kwargs.get("relevance_score", 0), kwargs.get("relevance_reason"), kwargs.get("proximity"))
        )
        person_id = c.execute("SELECT last_insert_rowid()").fetchone()[0]
        verified = verification_status == "verified"
        source_fields = [
            ("source_url", kwargs.get("source_url")),
            ("linkedin_url", kwargs.get("linkedin_url")),
            ("github_url", kwargs.get("github_url")),
            ("twitter_url", kwargs.get("twitter_url")),
        ]
        for field_name, url in source_fields:
            normalized = _normalize_url(url)
            if not normalized:
                continue
            contact_check = (
                contact_url_checks.get(field_name, {})
                if isinstance(contact_url_checks, dict)
                else {}
            )
            exact_contact_verified = (
                field_name != "source_url"
                and isinstance(contact_check, dict)
                and contact_check.get("fetched") is True
                and contact_check.get("matched") is True
                and _normalize_url(contact_check.get("url")) == normalized
            )
            _insert_source_row(
                c,
                normalized,
                title=f"{name} public evidence",
                summary=kwargs.get("relevance_reason", ""),
                source_type=_source_type_for_url(normalized, "person_signal"),
                claim_type="person_identity",
                verified=verified and (field_name == "source_url" or exact_contact_verified),
                metadata={
                    "recorded_by": "insert_person",
                    "field": field_name,
                    "contact_url_check": contact_check if field_name != "source_url" else None,
                },
                company_id=company_id,
                person_id=person_id,
            )
        return person_id


def get_people(company_id: int) -> list[dict]:
    with conn() as c:
        rows = c.execute(
            "SELECT * FROM people WHERE company_id=? ORDER BY relevance_score DESC",
            (company_id,)
        ).fetchall()
        return [dict(r) for r in rows]


# ── Packet helpers ────────────────────────────────────────────────────────────

def upsert_packet(company_id: int, **fields) -> int:
    with conn() as c:
        requested_status = fields.get("crm_status")
        evidence_summary = _get_evidence_summary(c, company_id)
        verification = _load_json_value(fields.get("verification"), {})
        if not isinstance(verification, dict):
            verification = {}
        verification["evidence_gate"] = evidence_summary
        fields["verification"] = verification

        if requested_status in {"prepared", "send_ready"} and not evidence_summary["ready"]:
            fields["crm_status"] = "needs_review"
            flags = _load_json_value(fields.get("qa_flags"), [])
            if not isinstance(flags, list):
                flags = []
            evidence_flag = (
                "Evidence gate blocked send-ready status: "
                + ", ".join(evidence_summary["missing"])
            )
            if evidence_flag not in flags:
                flags.append(evidence_flag)
            fields["qa_flags"] = flags

        existing = c.execute("SELECT id FROM packets WHERE company_id=?", (company_id,)).fetchone()
        for k, v in fields.items():
            if isinstance(v, (list, dict)):
                fields[k] = json.dumps(v)
        if existing:
            fields["updated_at"] = datetime.now().isoformat()
            set_clause = ", ".join(f"{k}=?" for k in fields)
            c.execute(f"UPDATE packets SET {set_clause} WHERE company_id=?",
                      list(fields.values()) + [company_id])
            return existing["id"]
        fields["company_id"] = company_id
        cols = ", ".join(fields.keys())
        placeholders = ", ".join("?" * len(fields))
        c.execute(f"INSERT INTO packets ({cols}) VALUES ({placeholders})", list(fields.values()))
        return c.execute("SELECT last_insert_rowid()").fetchone()[0]


def get_packet(company_id: int) -> dict | None:
    with conn() as c:
        row = c.execute("SELECT * FROM packets WHERE company_id=?", (company_id,)).fetchone()
        return dict(row) if row else None


def set_packet_status(packet_id: int, status: str):
    with conn() as c:
        c.execute("UPDATE packets SET crm_status=?, updated_at=? WHERE id=?",
                  (status, datetime.now().isoformat(), packet_id))


# ── Message + approval helpers ────────────────────────────────────────────────

def insert_message(packet_id: int, person_id: int | None, variant: str,
                   content: str) -> int:
    with conn() as c:
        c.execute(
            "INSERT INTO messages (packet_id, person_id, variant, content, word_count) VALUES (?,?,?,?,?)",
            (packet_id, person_id, variant, content, len(content.split()))
        )
        return c.execute("SELECT last_insert_rowid()").fetchone()[0]


def approve_message(message_id: int, notes: str = "", *, body_digest: str | None = None,
                    channel: str | None = None, target: str | None = None) -> int:
    """Approve the exact current message body.

    Repeating the same approval is idempotent. Editing the message creates a
    new approval lineage instead of reusing an approval for stale content.
    """
    with conn() as c:
        message = c.execute(
            "SELECT id, content FROM messages WHERE id=?",
            (message_id,),
        ).fetchone()
        if not message:
            raise ValueError(f"Message {message_id} not found")
        current_digest = message_digest(message["content"] or "")
        requested_digest = body_digest or current_digest
        if requested_digest != current_digest:
            raise ValueError("Approval digest does not match the current message body")
        existing = c.execute(
            """
            SELECT id FROM approvals
            WHERE message_id=? AND body_digest=?
              AND COALESCE(channel, '')=COALESCE(?, '')
              AND COALESCE(target, '')=COALESCE(?, '')
            ORDER BY id DESC LIMIT 1
            """,
            (message_id, current_digest, channel, target),
        ).fetchone()
        if existing:
            c.execute("UPDATE messages SET status='approved' WHERE id=?", (message_id,))
            return existing["id"]

        c.execute("UPDATE messages SET status='approved' WHERE id=?", (message_id,))
        c.execute(
            "INSERT INTO approvals (message_id, approved_at, notes, body_digest, channel, target) VALUES (?,?,?,?,?,?)",
            (
                message_id,
                datetime.now(timezone.utc).isoformat(),
                notes,
                current_digest,
                channel,
                target,
            ),
        )
        return c.execute("SELECT last_insert_rowid()").fetchone()[0]


def reject_message(message_id: int, notes: str = "Rejected by user") -> None:
    """Reject a message and record the rejection in approvals."""
    with conn() as c:
        c.execute("UPDATE messages SET status='rejected' WHERE id=?", (message_id,))
        c.execute(
            "INSERT INTO approvals (message_id, approved_at, notes) VALUES (?,?,?)",
            (message_id, datetime.now().isoformat(), notes),
        )


def get_approval(message_id: int) -> dict | None:
    """Return the latest approval for a message, or None."""
    with conn() as c:
        row = c.execute(
            "SELECT * FROM approvals WHERE message_id=? ORDER BY id DESC LIMIT 1",
            (message_id,),
        ).fetchone()
        return dict(row) if row else None


def record_send_event(message_id: int, approval_id: int, channel: str, *,
                      status: str = "sent", error_message: str | None = None) -> int:
    return record_delivery_event(
        message_id,
        approval_id,
        channel,
        status=status,
        error_message=error_message,
    )


def get_message(message_id: int) -> dict | None:
    """Return a single message by ID."""
    with conn() as c:
        row = c.execute("SELECT * FROM messages WHERE id=?", (message_id,)).fetchone()
        return dict(row) if row else None


def get_pending_approvals() -> list[dict]:
    with conn() as c:
        rows = c.execute(
            """
            SELECT
                m.*,
                p.name AS person_name,
                p.role AS person_role,
                p.linkedin_url,
                p.twitter_url,
                p.github_url,
                p.source_url,
                pkt.open_problem,
                pkt.qa_score,
                pkt.qa_flags,
                pkt.crm_status,
                c.name AS company_name
            FROM messages m
            LEFT JOIN people p ON m.person_id=p.id
            LEFT JOIN packets pkt ON m.packet_id=pkt.id
            LEFT JOIN companies c ON pkt.company_id=c.id
            WHERE m.status='draft'
            ORDER BY m.created_at DESC, m.id DESC
            """
        ).fetchall()
        return [dict(r) for r in rows]


def get_company_messages(company_id: int) -> list[dict]:
    """Return every packet message for a company with its latest approval and delivery state."""
    with conn() as c:
        rows = c.execute(
            """
            SELECT
                m.*,
                p.name AS person_name,
                p.role AS person_role,
                p.linkedin_url,
                p.twitter_url,
                p.github_url,
                p.source_url,
                a.id AS approval_id,
                a.approved_at,
                a.notes AS approval_notes,
                a.body_digest AS approval_digest,
                a.channel AS approval_channel,
                a.target AS approval_target,
                se.status AS delivery_status,
                se.error_message AS delivery_error,
                se.sent_at AS delivery_sent_at,
                f.id AS follow_up_id,
                f.status AS follow_up_status,
                f.due_date AS follow_up_due_date,
                f.notes AS follow_up_notes
            FROM messages m
            JOIN packets pkt ON m.packet_id=pkt.id
            LEFT JOIN people p ON m.person_id=p.id
            LEFT JOIN approvals a ON a.id = (
                SELECT a2.id FROM approvals a2
                WHERE a2.message_id=m.id
                ORDER BY a2.id DESC LIMIT 1
            )
            LEFT JOIN send_events se ON se.id = (
                SELECT se2.id FROM send_events se2
                WHERE se2.message_id=m.id
                  AND se2.approval_id=a.id
                ORDER BY se2.id DESC LIMIT 1
            )
            LEFT JOIN follow_ups f ON f.id = (
                SELECT f2.id FROM follow_ups f2
                WHERE f2.message_id=m.id
                  AND f2.approval_id=a.id
                ORDER BY f2.id DESC LIMIT 1
            )
            WHERE pkt.company_id=?
            ORDER BY m.created_at DESC, m.id DESC
            """,
            (company_id,),
        ).fetchall()
        return [_bound_message_state(dict(row)) for row in rows]


def get_review_messages() -> list[dict]:
    """Return draft and approved messages with exact-bound delivery state."""
    with conn() as c:
        rows = c.execute(
            """
            SELECT
                m.*,
                p.name AS person_name,
                p.role AS person_role,
                p.linkedin_url,
                p.twitter_url,
                p.github_url,
                p.source_url,
                pkt.open_problem,
                pkt.qa_score,
                pkt.qa_flags,
                pkt.crm_status,
                c.name AS company_name,
                a.id AS approval_id,
                a.approved_at,
                a.notes AS approval_notes,
                a.body_digest AS approval_digest,
                a.channel AS approval_channel,
                a.target AS approval_target,
                se.id AS delivery_event_id,
                se.status AS delivery_status,
                se.error_message AS delivery_error,
                se.sent_at AS delivery_updated_at,
                f.id AS follow_up_id,
                f.status AS follow_up_status,
                f.due_date AS follow_up_due_date,
                f.notes AS follow_up_notes
            FROM messages m
            LEFT JOIN people p ON m.person_id=p.id
            LEFT JOIN packets pkt ON m.packet_id=pkt.id
            LEFT JOIN companies c ON pkt.company_id=c.id
            LEFT JOIN approvals a ON a.id = (
                SELECT a2.id FROM approvals a2
                WHERE a2.message_id=m.id
                ORDER BY a2.id DESC LIMIT 1
            )
            LEFT JOIN send_events se ON se.id = (
                SELECT se2.id FROM send_events se2
                WHERE se2.message_id=m.id
                  AND se2.approval_id=a.id
                ORDER BY se2.id DESC LIMIT 1
            )
            LEFT JOIN follow_ups f ON f.id = (
                SELECT f2.id FROM follow_ups f2
                WHERE f2.message_id=m.id
                  AND f2.approval_id=a.id
                ORDER BY f2.id DESC LIMIT 1
            )
            WHERE m.status IN ('draft', 'approved')
            ORDER BY m.created_at DESC, m.id DESC
            """
        ).fetchall()
    return [_bound_message_state(dict(row)) for row in rows]


def _bound_message_state(message: dict) -> dict:
    current_digest = message_digest(message.get("content") or "")
    approval_digest = message.get("approval_digest")
    approval_current = bool(approval_digest and approval_digest == current_digest)
    message["body_digest"] = current_digest
    message["approval_current"] = approval_current
    message["state_stale"] = bool(message.get("approval_id") and not approval_current)
    if message["state_stale"]:
        message["delivery_status"] = None
        message["delivery_error"] = None
        message["delivery_updated_at"] = None
        message["follow_up_id"] = None
        message["follow_up_status"] = None
        message["follow_up_due_date"] = None
        message["follow_up_notes"] = None
    return message


# ── Delivery event helpers (013) ──────────────────────────────────────────────

DELIVERY_STATES = frozenset({"prepared", "opened", "sent", "delivered", "failed", "unknown"})


def record_delivery_event(
    message_id: int,
    approval_id: int,
    channel: str,
    *,
    status: str = "prepared",
    error_message: str | None = None,
) -> int:
    """Record a delivery state transition. Idempotent for same (message_id, approval_id, status).

    Valid states: prepared, opened, sent, delivered, failed, unknown.
    Never falsely claims delivery — only records the state the caller provides.
    """
    if status not in DELIVERY_STATES:
        raise ValueError(f"Invalid delivery state: {status}. Must be one of {sorted(DELIVERY_STATES)}")

    with conn() as c:
        message = c.execute(
            "SELECT id, content, status FROM messages WHERE id=?",
            (message_id,),
        ).fetchone()
        approval = c.execute(
            "SELECT * FROM approvals WHERE id=? AND message_id=?",
            (approval_id, message_id),
        ).fetchone()
        if not message:
            raise ValueError(f"Message {message_id} not found")
        if not approval:
            raise ValueError("Delivery event must reference an approval for this message")
        current_digest = message_digest(message["content"] or "")
        if not approval["body_digest"] or approval["body_digest"] != current_digest:
            raise ValueError("Approved message digest is stale; review the edited message again")
        if approval["channel"] and approval["channel"] != channel:
            raise ValueError("Delivery channel does not match the approved channel")
        existing = c.execute(
            """
            SELECT id FROM send_events
            WHERE message_id=? AND approval_id=? AND status=? AND body_digest=?
            LIMIT 1
            """,
            (message_id, approval_id, status, current_digest),
        ).fetchone()
        if existing:
            return existing["id"]

        c.execute(
            """
            INSERT INTO send_events
                (message_id, approval_id, sent_at, channel, status, body_digest, error_message)
            VALUES (?,?,?,?,?,?,?)
            """,
            (
                message_id,
                approval_id,
                datetime.now(timezone.utc).isoformat(),
                channel,
                status,
                current_digest,
                error_message,
            ),
        )
        return c.execute("SELECT last_insert_rowid()").fetchone()[0]


def get_delivery_events(message_id: int) -> list[dict]:
    """Return all delivery events for a message, newest first."""
    with conn() as c:
        rows = c.execute(
            "SELECT se.*, a.body_digest AS approval_digest, a.channel AS approval_channel, a.target AS approval_target "
            "FROM send_events se "
            "JOIN approvals a ON se.approval_id=a.id "
            "WHERE se.message_id=? "
            "ORDER BY se.id DESC",
            (message_id,),
        ).fetchall()
        message = c.execute(
            "SELECT content FROM messages WHERE id=?",
            (message_id,),
        ).fetchone()
    current_digest = message_digest(message["content"] or "") if message else ""
    events = [dict(row) for row in rows]
    for event in events:
        event["stale"] = not event.get("body_digest") or event["body_digest"] != current_digest
    return events


def get_latest_delivery(message_id: int) -> dict | None:
    """Return the most recent delivery event for a message, or None."""
    with conn() as c:
        row = c.execute(
            "SELECT se.*, a.body_digest AS approval_digest "
            "FROM send_events se "
            "JOIN approvals a ON se.approval_id=a.id "
            "WHERE se.message_id=? "
            "ORDER BY se.id DESC LIMIT 1",
            (message_id,),
        ).fetchone()
        message = c.execute(
            "SELECT content FROM messages WHERE id=?",
            (message_id,),
        ).fetchone()
    if not row:
        return None
    delivery = dict(row)
    current_digest = message_digest(message["content"] or "") if message else ""
    delivery["stale"] = not delivery.get("body_digest") or delivery["body_digest"] != current_digest
    return delivery


# ── Follow-up helpers ─────────────────────────────────────────────────────────

def insert_follow_up(
    message_id: int,
    due_date: date,
    notes: str = "",
    *,
    approval_id: int | None = None,
) -> int:
    """Schedule a follow-up for the exact currently approved message body."""
    with conn() as c:
        message = c.execute(
            "SELECT id, content FROM messages WHERE id=?",
            (message_id,),
        ).fetchone()
        if not message:
            raise ValueError(f"Message {message_id} not found")
        if approval_id is None:
            approval = c.execute(
                "SELECT * FROM approvals WHERE message_id=? ORDER BY id DESC LIMIT 1",
                (message_id,),
            ).fetchone()
        else:
            approval = c.execute(
                "SELECT * FROM approvals WHERE id=? AND message_id=?",
                (approval_id, message_id),
            ).fetchone()
        if not approval:
            raise ValueError("Follow-up requires an approval for this message")
        current_digest = message_digest(message["content"] or "")
        if not approval["body_digest"] or approval["body_digest"] != current_digest:
            raise ValueError("Approved message digest is stale; review the edited message again")
        existing = c.execute(
            """
            SELECT id FROM follow_ups
            WHERE message_id=? AND approval_id=? AND body_digest=? AND due_date=?
              AND status='pending'
            LIMIT 1
            """,
            (message_id, approval["id"], current_digest, due_date.isoformat()),
        ).fetchone()
        if existing:
            return existing["id"]
        c.execute(
            """
            INSERT INTO follow_ups
                (message_id, approval_id, body_digest, due_date, status, notes, created_at)
            VALUES (?,?,?,?,?,?,?)
            """,
            (
                message_id,
                approval["id"],
                current_digest,
                due_date.isoformat(),
                "pending",
                notes,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        return c.execute("SELECT last_insert_rowid()").fetchone()[0]


def get_due_follow_ups() -> list[dict]:
    with conn() as c:
        today = date.today().isoformat()
        rows = c.execute(
            """
            SELECT f.*, m.content, m.variant, m.status AS message_status
            FROM follow_ups f
            JOIN messages m ON f.message_id=m.id
            WHERE f.status='pending' AND f.due_date<=?
            ORDER BY f.due_date, f.id
            """,
            (today,),
        ).fetchall()
    return [
        dict(row)
        for row in rows
        if row["body_digest"] and row["body_digest"] == message_digest(row["content"] or "")
    ]


def update_follow_up(follow_up_id: int, status: str, notes: str = "") -> None:
    """Update a follow-up record's status and optional notes."""
    valid_statuses = {"pending", "completed", "skipped"}
    if status not in valid_statuses:
        raise ValueError(f"Invalid follow-up status: {status}. Must be one of {sorted(valid_statuses)}")
    with conn() as c:
        row = c.execute(
            """
            SELECT f.body_digest, m.content
            FROM follow_ups f
            JOIN messages m ON f.message_id=m.id
            WHERE f.id=?
            """,
            (follow_up_id,),
        ).fetchone()
        if not row:
            raise ValueError(f"Follow-up {follow_up_id} not found")
        if not row["body_digest"] or row["body_digest"] != message_digest(row["content"] or ""):
            raise ValueError("Follow-up belongs to a stale message approval")
        c.execute(
            "UPDATE follow_ups SET status=?, notes=? WHERE id=?",
            (status, notes, follow_up_id),
        )


def get_follow_ups_for_message(message_id: int) -> list[dict]:
    """Return all follow-ups for a message, newest first."""
    with conn() as c:
        rows = c.execute(
            """
            SELECT f.*, m.content
            FROM follow_ups f
            JOIN messages m ON f.message_id=m.id
            WHERE f.message_id=?
            ORDER BY f.id DESC
            """,
            (message_id,),
        ).fetchall()
    follow_ups = [dict(row) for row in rows]
    for follow_up in follow_ups:
        follow_up["stale"] = (
            not follow_up.get("body_digest")
            or follow_up["body_digest"] != message_digest(follow_up.get("content") or "")
        )
        follow_up.pop("content", None)
    return follow_ups


# ── People data hygiene (024, duplicates 027) ────────────────────────────────
#
# The deterministic name gate (upsearch/person_validation.py) blocks new junk
# at the source. These helpers clean what is already stored: people rows whose
# "name" is website navigation or a blog title, duplicate rows for the same
# human at the same company, and not-yet-sent messages addressed to recipients
# that fail person validation.
#
# Message-status vocabulary (messages.status): 'draft' (pending review),
# 'approved' (human-approved, delivery tracked in send_events), 'rejected'
# (terminal; see reject_message). The hygiene pass only touches messages still
# in the live review queue — status IN ('draft', 'approved'), exactly the set
# get_review_messages() serves — and rejects them the same way reject_message
# does: status='rejected' plus an approvals row carrying the reason note.


def _scan_people_hygiene(c: sqlite3.Connection) -> dict:
    """Classify people rows and live messages for the hygiene pass.

    Shared by the read-only report and the mutating run so both always agree.
    Performs no writes.
    """
    people = c.execute(
        "SELECT id, company_id, name, verification_status, relevance_score "
        "FROM people ORDER BY id"
    ).fetchall()
    failing_people: dict[int, dict] = {}
    for row in people:
        reason = person_name_rejection(row["name"])
        if reason is not None:
            failing_people[row["id"]] = {
                "id": row["id"],
                "company_id": row["company_id"],
                "name": row["name"],
                "reason": reason,
            }

    # Duplicate rows for the same human: same company, same case-insensitive
    # name, among rows that pass the name gate (junk rows are deleted anyway).
    # Keep the best row: verified beats unverified, then highest
    # relevance_score, then lowest id.
    groups: dict[tuple, list[sqlite3.Row]] = {}
    for row in people:
        if row["id"] in failing_people:
            continue
        key = (row["company_id"], " ".join(str(row["name"] or "").split()).lower())
        groups.setdefault(key, []).append(row)
    duplicate_people: list[dict] = []
    duplicate_map: dict[int, int] = {}  # removed person id -> kept person id
    for rows in groups.values():
        if len(rows) < 2:
            continue
        kept = max(
            rows,
            key=lambda r: (
                (r["verification_status"] or "unverified") == "verified",
                r["relevance_score"] or 0,
                -r["id"],
            ),
        )
        removed_ids = sorted(r["id"] for r in rows if r["id"] != kept["id"])
        for removed_id in removed_ids:
            duplicate_map[removed_id] = kept["id"]
        duplicate_people.append({
            "company_id": kept["company_id"],
            "name": kept["name"],
            "kept_id": kept["id"],
            "removed_ids": removed_ids,
        })

    status_by_id = {row["id"]: row["verification_status"] for row in people}

    messages = c.execute(
        """
        SELECT m.id AS message_id, m.person_id,
               p.id AS person_row_id, p.verification_status
        FROM messages m
        LEFT JOIN people p ON m.person_id=p.id
        WHERE m.status IN ('draft', 'approved') AND m.person_id IS NOT NULL
        ORDER BY m.id
        """
    ).fetchall()
    flagged_messages: list[dict] = []
    for row in messages:
        if row["person_row_id"] is None:
            reason = "person record missing"
        elif row["person_id"] in failing_people:
            reason = failing_people[row["person_id"]]["reason"]
        else:
            # Judge the recipient the dedupe pass would leave in place, so a
            # draft to a removable duplicate of a verified person survives.
            resolved_id = duplicate_map.get(row["person_id"], row["person_id"])
            status = status_by_id.get(resolved_id) or "unverified"
            if status == "verified":
                continue
            reason = f"verification_status={status}"
        flagged_messages.append({"message_id": row["message_id"], "reason": reason})

    return {
        "people_total": len(people),
        "failing_people": failing_people,
        "flagged_messages": flagged_messages,
        "duplicate_people": duplicate_people,
        "duplicate_map": duplicate_map,
    }


def people_hygiene_report() -> dict:
    """Read-only preview of what run_people_hygiene() would change.

    Returns counts plus the failing rows themselves so the operator can review
    every name and reason before running the purge. Never mutates.
    """
    with conn() as c:
        scan = _scan_people_hygiene(c)
    failing = scan["failing_people"]
    duplicates_removed = len(scan["duplicate_map"])
    return {
        "people_total": scan["people_total"],
        "people_failing": len(failing),
        "people_kept": scan["people_total"] - len(failing) - duplicates_removed,
        "messages_flagged": len(scan["flagged_messages"]),
        "duplicates_removed": duplicates_removed,
        "failing_people": list(failing.values()),
        "flagged_messages": scan["flagged_messages"],
        "duplicate_people": scan["duplicate_people"],
    }


def run_people_hygiene() -> dict:
    """Purge stored non-person junk in one transaction. Idempotent.

    - Deletes people rows whose name fails person_name_rejection, plus the
      person-evidence sources rows recorded for them (their "source links"),
      so junk cannot keep satisfying the person-evidence gate.
    - Collapses duplicate rows for the same human — same (company_id,
      lower(name)) — keeping the best row (verified beats unverified, then
      highest relevance_score, then lowest id). Messages addressed to a
      removed duplicate are repointed at the kept row so no message ever
      references a deleted person; the duplicate's evidence sources move to
      the kept row unless an identical url+claim row already exists.
    - Rejects messages still in the review queue (status draft/approved) whose
      recipient was deleted, is missing, or has verification_status other than
      'verified' (judged against the post-dedupe recipient) — mirroring
      reject_message: status='rejected' plus an approvals note
      "recipient failed person validation: <reason>".
    - Rewrites packets.people_map dropping entries whose name fails the same
      gate (every deleted person's name fails it by definition).
    """
    now = datetime.now(timezone.utc).isoformat()
    with conn() as c:
        scan = _scan_people_hygiene(c)
        failing_ids = sorted(scan["failing_people"])

        for person_id in failing_ids:
            c.execute("DELETE FROM sources WHERE person_id=?", (person_id,))
            c.execute("DELETE FROM people WHERE id=?", (person_id,))

        duplicate_map: dict[int, int] = scan["duplicate_map"]
        for removed_id, kept_id in sorted(duplicate_map.items()):
            c.execute(
                "UPDATE messages SET person_id=? WHERE person_id=?",
                (kept_id, removed_id),
            )
            for source in c.execute(
                "SELECT id, url, claim_type FROM sources WHERE person_id=? ORDER BY id",
                (removed_id,),
            ).fetchall():
                existing = c.execute(
                    """SELECT id FROM sources
                       WHERE person_id=? AND url=?
                         AND COALESCE(claim_type, '')=COALESCE(?, '')
                       LIMIT 1""",
                    (kept_id, source["url"], source["claim_type"]),
                ).fetchone()
                if existing:
                    c.execute("DELETE FROM sources WHERE id=?", (source["id"],))
                else:
                    c.execute(
                        "UPDATE sources SET person_id=? WHERE id=?",
                        (kept_id, source["id"]),
                    )
            c.execute("DELETE FROM people WHERE id=?", (removed_id,))

        for flagged in scan["flagged_messages"]:
            c.execute(
                "UPDATE messages SET status='rejected' WHERE id=?",
                (flagged["message_id"],),
            )
            c.execute(
                "INSERT INTO approvals (message_id, approved_at, notes) VALUES (?,?,?)",
                (
                    flagged["message_id"],
                    now,
                    f"recipient failed person validation: {flagged['reason']}",
                ),
            )

        packets_updated = 0
        for packet in c.execute("SELECT id, people_map FROM packets ORDER BY id").fetchall():
            entries = _load_json_value(packet["people_map"], [])
            if not isinstance(entries, list):
                continue
            kept_entries = [
                entry for entry in entries
                if isinstance(entry, dict)
                and person_name_rejection(str(entry.get("name", ""))) is None
            ]
            if kept_entries != entries:
                c.execute(
                    "UPDATE packets SET people_map=?, updated_at=? WHERE id=?",
                    (json.dumps(kept_entries), now, packet["id"]),
                )
                packets_updated += 1

        return {
            "people_removed": len(failing_ids),
            "duplicates_removed": len(duplicate_map),
            "messages_rejected": len(scan["flagged_messages"]),
            "packets_updated": packets_updated,
            "people_kept": scan["people_total"] - len(failing_ids) - len(duplicate_map),
        }


# ── Legacy archive (031) ──────────────────────────────────────────────────────
# Pre-fix discovery left two kinds of junk in the CRM: packets stuck at
# crm_status='identity_blocked' (created by the identity gate before discovery
# precision landed) and companies with identity_status 'rejected'/'discovered'
# that never produced a packet. Archiving sets packets.crm_status='archived'
# and companies.status='archived'; list_companies() hides both forms by
# default. 'archived' is a new value in both vocabularies (packets: prepared/
# needs_review/send_ready/identity_blocked; companies: sourced/researched/
# packet_ready/identity_blocked) and never reaches the UI because /os/companies
# filters it out. Re-running a company self-heals: the orchestrator clears and
# rebuilds its packet, so the archived packet row disappears.


def _scan_legacy_archive(c: sqlite3.Connection) -> dict:
    """Classify legacy packets and companies for the archive pass.

    Shared by the read-only report and the mutating run so both always agree.
    Performs no writes.
    """
    archive_packets = [
        {
            "packet_id": row["packet_id"],
            "company_id": row["company_id"],
            "company_name": row["company_name"],
            "identity_status": row["identity_status"],
        }
        for row in c.execute(
            """
            SELECT p.id AS packet_id, p.company_id,
                   co.name AS company_name, co.identity_status
            FROM packets p
            LEFT JOIN companies co ON p.company_id=co.id
            WHERE p.crm_status='identity_blocked'
            ORDER BY p.id
            """
        ).fetchall()
    ]

    # Companies that never produced a packet and were only ever discovery
    # candidates ('discovered') or failed identity ('rejected'). Manually
    # added companies start 'unverified' and are never swept. The pending-
    # message guard is structural today (messages reach companies only
    # through packets) but keeps the rule honest if that ever changes.
    archive_companies = [
        {
            "company_id": row["id"],
            "name": row["name"],
            "identity_status": row["identity_status"],
            "status": row["status"],
        }
        for row in c.execute(
            """
            SELECT co.id, co.name, co.identity_status, co.status
            FROM companies co
            WHERE co.identity_status IN ('rejected', 'discovered')
              AND COALESCE(co.status, '') != 'archived'
              AND NOT EXISTS (
                  SELECT 1 FROM packets p WHERE p.company_id=co.id
              )
              AND NOT EXISTS (
                  SELECT 1 FROM messages m
                  JOIN packets p2 ON m.packet_id=p2.id
                  WHERE p2.company_id=co.id AND m.status IN ('draft', 'approved')
              )
            ORDER BY co.id
            """
        ).fetchall()
    ]

    packets_total = c.execute("SELECT COUNT(*) FROM packets").fetchone()[0]
    companies_total = c.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
    return {
        "packets_total": packets_total,
        "companies_total": companies_total,
        "archive_packets": archive_packets,
        "archive_companies": archive_companies,
    }


def legacy_archive_report() -> dict:
    """Read-only preview of what run_legacy_archive() would change.

    Returns counts plus the rows themselves (ids and names) so the operator
    can review every packet and company before archiving. Never mutates.
    """
    with conn() as c:
        scan = _scan_legacy_archive(c)
    return {
        "packets_total": scan["packets_total"],
        "packets_to_archive": len(scan["archive_packets"]),
        "companies_total": scan["companies_total"],
        "companies_to_archive": len(scan["archive_companies"]),
        "archive_packets": scan["archive_packets"],
        "archive_companies": scan["archive_companies"],
    }


def run_legacy_archive() -> dict:
    """Archive legacy discovery junk in one transaction. Idempotent.

    - Packets with crm_status='identity_blocked' become crm_status='archived'.
    - Companies with identity_status 'rejected'/'discovered', zero packets,
      and zero pending messages become status='archived'.
    Archived rows keep all their data and drop out of list_companies() and
    /os/companies; nothing is deleted. A second run changes nothing.
    """
    now = datetime.now(timezone.utc).isoformat()
    with conn() as c:
        scan = _scan_legacy_archive(c)
        for entry in scan["archive_packets"]:
            c.execute(
                "UPDATE packets SET crm_status='archived', updated_at=? WHERE id=?",
                (now, entry["packet_id"]),
            )
        for entry in scan["archive_companies"]:
            c.execute(
                "UPDATE companies SET status='archived' WHERE id=?",
                (entry["company_id"],),
            )
        return {
            "packets_archived": len(scan["archive_packets"]),
            "companies_archived": len(scan["archive_companies"]),
        }


# ── User profile ──────────────────────────────────────────────────────────────

def save_profile(name: str, email: str, school: str, background_summary: str,
                 raw_profile: str, **kwargs):
    with conn() as c:
        existing = c.execute("SELECT id FROM user_profile LIMIT 1").fetchone()
        ts = datetime.now().isoformat()
        if existing:
            c.execute(
                """UPDATE user_profile SET name=?, email=?, school=?, background_summary=?,
                   raw_profile=?, updated_at=? WHERE id=?""",
                (name, email, school, background_summary, raw_profile, ts, existing["id"])
            )
        else:
            c.execute(
                """INSERT INTO user_profile (name, email, school, background_summary, raw_profile, updated_at)
                   VALUES (?,?,?,?,?,?)""",
                (name, email, school, background_summary, raw_profile, ts)
            )


def get_profile() -> dict | None:
    with conn() as c:
        row = c.execute("SELECT * FROM user_profile LIMIT 1").fetchone()
        return dict(row) if row else None


# ── Scheduled jobs helpers ────────────────────────────────────────────────────


def enqueue_job(job_type: str, params: dict | None = None,
                lane: str | None = None, max_retries: int = 3,
                priority: int = 0) -> int:
    with conn() as c:
        c.execute(
            """INSERT INTO scheduled_jobs (job_type, params, lane, max_retries, priority)
               VALUES (?, ?, ?, ?, ?)""",
            (job_type, json.dumps(params or {}), lane, max_retries, priority),
        )
        return c.execute("SELECT last_insert_rowid()").fetchone()[0]


def dequeue_next_job() -> dict | None:
    """Claim the highest-priority queued job. Returns None if nothing is queued.

    The claim is a single atomic UPDATE ... WHERE id = (SELECT ...) RETURNING *
    statement. SQLite serializes write transactions, so the inner select and the
    status flip execute under one write lock and the same job can never be handed
    to two concurrent workers.
    """
    now = datetime.now().isoformat()
    with conn() as c:
        row = c.execute(
            """UPDATE scheduled_jobs SET status='running', started_at=?
               WHERE id = (
                   SELECT id FROM scheduled_jobs
                   WHERE status='queued' AND retry_count <= max_retries
                   ORDER BY priority DESC, created_at ASC LIMIT 1
               )
               RETURNING *""",
            (now,),
        ).fetchone()
        return dict(row) if row is not None else None


def complete_job(job_id: int) -> None:
    with conn() as c:
        now = datetime.now().isoformat()
        c.execute("UPDATE scheduled_jobs SET status='complete', completed_at=? WHERE id=?",
                  (now, job_id))


def fail_job(job_id: int, error: str, retry: bool = True) -> str:
    """Mark a job as failed. If retryable and under max_retries, reset to 'queued'.
    Returns the new status: 'queued' or 'failed'."""
    with conn() as c:
        row = c.execute("SELECT retry_count, max_retries FROM scheduled_jobs WHERE id=?",
                        (job_id,)).fetchone()
        if row is None:
            return "gone"
        new_count = row["retry_count"] + 1
        now = datetime.now().isoformat()
        if retry and new_count <= row["max_retries"]:
            c.execute(
                """UPDATE scheduled_jobs SET status='queued', retry_count=?, error_message=?,
                   started_at=NULL, completed_at=? WHERE id=?""",
                (new_count, error[:500], now, job_id),
            )
            return "queued"
        c.execute(
            """UPDATE scheduled_jobs SET status='failed', retry_count=?, error_message=?,
               completed_at=? WHERE id=?""",
            (new_count, error[:500], now, job_id),
        )
        return "failed"


def get_pending_job_count() -> int:
    with conn() as c:
        row = c.execute(
            """SELECT COUNT(*) as cnt FROM scheduled_jobs
               WHERE status IN ('queued', 'running')"""
        ).fetchone()
        return row["cnt"] if row else 0


def get_job_summary() -> list[dict]:
    with conn() as c:
        rows = c.execute(
            """SELECT id, job_type, status, lane, retry_count, max_retries,
                      created_at, started_at, completed_at, error_message
               FROM scheduled_jobs ORDER BY created_at ASC"""
        ).fetchall()
        return [dict(r) for r in rows]


def get_running_jobs() -> list[dict]:
    """Return all jobs with status='running'."""
    with conn() as c:
        rows = c.execute(
            """SELECT * FROM scheduled_jobs WHERE status='running' ORDER BY created_at ASC"""
        ).fetchall()
        return [dict(r) for r in rows]


def count_companies() -> int:
    """Return the total number of companies in the database."""
    with conn() as c:
        row = c.execute("SELECT COUNT(*) as cnt FROM companies").fetchone()
        return row["cnt"] if row else 0


# ── Run record helpers (ADR-002) ─────────────────────────────────────────────


def create_run_record(
    company_name: str,
    lane: str = "ai_infra",
    *,
    run_id: str | None = None,
) -> str:
    """Create or restart a run record and return its stable run ID."""
    import uuid
    run_id = run_id or uuid.uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    with conn() as c:
        existing = c.execute(
            "SELECT id FROM run_records WHERE run_id=?",
            (run_id,),
        ).fetchone()
        if existing:
            c.execute(
                """UPDATE run_records
                   SET company_name=?, lane=?, started_at=?, completed_at=NULL,
                       status='running', steps_completed='[]', current_step=NULL,
                       qa_score=NULL, final_status=NULL, trace_path=NULL,
                       error_message=NULL
                   WHERE run_id=?""",
                (company_name, lane, now, run_id),
            )
        else:
            c.execute(
                """INSERT INTO run_records
                   (run_id, company_name, lane, started_at, status)
                   VALUES (?, ?, ?, ?, 'running')""",
                (run_id, company_name, lane, now),
            )
    return run_id


def update_run_record(run_id: str, **kwargs) -> None:
    """Update fields on a run record identified by run_id.

    Accepts: status, current_step, qa_score, final_status, trace_path,
    error_message. The steps_completed field accepts a list and is serialised
    automatically. completed_at is set when status becomes 'complete' or
    'failed'.
    """
    valid_keys = {
        "status", "current_step", "qa_score", "final_status",
        "trace_path", "error_message",
    }
    updates: dict[str, object] = {}
    for k, v in kwargs.items():
        if k == "steps_completed" and isinstance(v, list):
            updates["steps_completed"] = json.dumps(v)
        elif k in valid_keys:
            updates[k] = v
    if not updates:
        return
    if kwargs.get("status") in ("complete", "failed", "cancelled"):
        updates["completed_at"] = datetime.now(timezone.utc).isoformat()
    set_clause = ", ".join(f"{k}=?" for k in updates)
    with conn() as c:
        c.execute(
            f"UPDATE run_records SET {set_clause} WHERE run_id=?",
            list(updates.values()) + [run_id],
        )


def get_run_record(run_id: str) -> dict | None:
    """Return a single run record by run_id, with steps_completed parsed."""
    with conn() as c:
        row = c.execute(
            "SELECT * FROM run_records WHERE run_id=?", (run_id,)
        ).fetchone()
        if row is None:
            return None
        result = dict(row)
        if isinstance(result.get("steps_completed"), str):
            try:
                result["steps_completed"] = json.loads(result["steps_completed"])
            except (json.JSONDecodeError, TypeError):
                result["steps_completed"] = []
        return result


def get_latest_run_record(company_name: str) -> dict | None:
    """Return the newest run for a company, if run metadata exists."""
    with conn() as c:
        row = c.execute(
            """SELECT * FROM run_records
               WHERE company_name=?
               ORDER BY created_at DESC, id DESC
               LIMIT 1""",
            (company_name,),
        ).fetchone()
        if row is None:
            return None
        result = dict(row)
        if isinstance(result.get("steps_completed"), str):
            try:
                result["steps_completed"] = json.loads(result["steps_completed"])
            except (json.JSONDecodeError, TypeError):
                result["steps_completed"] = []
        return result


def get_running_records() -> list[dict]:
    """Return all run records with status='running', sorted by creation."""
    with conn() as c:
        rows = c.execute(
            "SELECT * FROM run_records WHERE status='running' ORDER BY created_at ASC"
        ).fetchall()
        results = []
        for row in rows:
            r = dict(row)
            if isinstance(r.get("steps_completed"), str):
                try:
                    r["steps_completed"] = json.loads(r["steps_completed"])
                except (json.JSONDecodeError, TypeError):
                    r["steps_completed"] = []
            results.append(r)
        return results


# ── Trace events helpers (ADR-002) ──────────────────────────────────────────


def insert_trace_event(
    run_id: str,
    event_type: str,
    *,
    status: str = "ok",
    timestamp: str | None = None,
    agent: str | None = None,
    agent_role: str | None = None,
    reads: list[str] | None = None,
    writes: list[str] | None = None,
    output_summary: str | None = None,
    latency_ms: int | None = None,
    from_agent: str | None = None,
    to_agent: str | None = None,
    payload_keys: list[str] | None = None,
    reason: str | None = None,
    payload: dict | None = None,
) -> int:
    """Persist a single trace event linked to a run record."""
    from datetime import datetime, timezone
    ts = timestamp or datetime.now(timezone.utc).isoformat()
    with conn() as c:
        c.execute(
            """INSERT INTO trace_events
               (run_id, event_type, status, timestamp, agent, agent_role,
                reads, writes, output_summary, latency_ms,
                from_agent, to_agent, payload_keys, reason, payload)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                run_id, event_type, status, ts,
                agent, agent_role,
                json.dumps(reads or []), json.dumps(writes or []),
                output_summary, latency_ms,
                from_agent, to_agent,
                json.dumps(payload_keys or []), reason,
                json.dumps(payload or {}),
            ),
        )
        return c.execute("SELECT last_insert_rowid()").fetchone()[0]


def insert_trace_events_batch(run_id: str, events: list[dict]) -> int:
    """Persist multiple trace events in a single transaction. Returns count."""
    from datetime import datetime, timezone
    now_ts = datetime.now(timezone.utc).isoformat()
    with conn() as c:
        count = 0
        for ev in events:
            _id = c.execute(
                """SELECT id FROM trace_events
                   WHERE run_id=? AND timestamp=? AND event_type=?
                     AND COALESCE(agent, '')=COALESCE(?, '')
                     AND COALESCE(from_agent, '')=COALESCE(?, '')
                     AND COALESCE(to_agent, '')=COALESCE(?, '')""",
                (
                    run_id,
                    ev.get("timestamp", now_ts),
                    ev.get("event_type", ""),
                    ev.get("agent"),
                    ev.get("from_agent"),
                    ev.get("to_agent"),
                ),
            ).fetchone()
            if _id:
                continue
            c.execute(
                """INSERT INTO trace_events
                   (run_id, event_type, status, timestamp, agent, agent_role,
                    reads, writes, output_summary, latency_ms,
                    from_agent, to_agent, payload_keys, reason, payload)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    run_id,
                    ev.get("event_type", ""),
                    ev.get("status", "ok"),
                    ev.get("timestamp", now_ts),
                    ev.get("agent"),
                    ev.get("agent_role"),
                    json.dumps(ev.get("reads", [])),
                    json.dumps(ev.get("writes", [])),
                    ev.get("output_summary"),
                    ev.get("latency_ms"),
                    ev.get("from_agent"),
                    ev.get("to_agent"),
                    json.dumps(ev.get("payload_keys", [])),
                    ev.get("reason"),
                    json.dumps(ev.get("payload", {})),
                ),
            )
            count += 1
        return count


def get_trace_events(run_id: str) -> list[dict]:
    """Return all trace events for a run, sorted by timestamp."""
    with conn() as c:
        rows = c.execute(
            "SELECT * FROM trace_events WHERE run_id=? ORDER BY timestamp ASC, id ASC",
            (run_id,),
        ).fetchall()
        results = []
        for row in rows:
            r = dict(row)
            for field in ("reads", "writes", "payload_keys", "payload"):
                if isinstance(r.get(field), str):
                    try:
                        r[field] = json.loads(r[field])
                    except (json.JSONDecodeError, TypeError):
                        r[field] = {} if field == "payload" else []
            if r.get("agent_role") and not r.get("role"):
                r["role"] = r["agent_role"]
            results.append(r)
        return results


def clear_trace_events(run_id: str) -> int:
    """Delete all trace events for a run. Returns count deleted."""
    with conn() as c:
        rows = c.execute(
            "DELETE FROM trace_events WHERE run_id=?", (run_id,)
        )
        return rows.rowcount


def list_run_records(
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """Return run records, optionally filtered by status."""
    with conn() as c:
        if status:
            rows = c.execute(
                """SELECT * FROM run_records WHERE status=? ORDER BY created_at DESC
                   LIMIT ? OFFSET ?""",
                (status, limit, offset),
            ).fetchall()
        else:
            rows = c.execute(
                "SELECT * FROM run_records ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        results = []
        for row in rows:
            r = dict(row)
            if isinstance(r.get("steps_completed"), str):
                try:
                    r["steps_completed"] = json.loads(r["steps_completed"])
                except (json.JSONDecodeError, TypeError):
                    r["steps_completed"] = []
            results.append(r)
        return results


def recover_abandoned_runs() -> list[dict]:
    """Mark run_records still 'running' as 'failed' (server restarted).
    Returns the list of abandoned runs."""
    abandoned = get_running_records()
    for record in abandoned:
        update_run_record(
            record["run_id"],
            status="failed",
            error_message="Server restarted while running",
        )
    return abandoned
