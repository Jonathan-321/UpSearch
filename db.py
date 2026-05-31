"""
SQLite CRM — the data backbone for Opportunity Intelligence OS.
All entities: companies, problems, people, packets, messages, approvals, send events, follow-ups.
"""
import sqlite3
import json
from contextlib import contextmanager
from datetime import datetime, date
from pathlib import Path

DB_PATH = Path("opportunity_os.db")


@contextmanager
def conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
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
            website         TEXT,
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
            status      TEXT
        );

        CREATE TABLE IF NOT EXISTS follow_ups (
            id          INTEGER PRIMARY KEY,
            message_id  INTEGER REFERENCES messages(id),
            due_date    DATE,
            status      TEXT DEFAULT 'pending',
            notes       TEXT
        );
        """)


# ── Company helpers ───────────────────────────────────────────────────────────

def upsert_company(name: str, **kwargs) -> int:
    with conn() as c:
        existing = c.execute("SELECT id FROM companies WHERE name=?", (name,)).fetchone()
        if existing:
            fields = ", ".join(f"{k}=?" for k in kwargs)
            vals = list(kwargs.values()) + [name]
            if fields:
                c.execute(f"UPDATE companies SET {fields} WHERE name=?", vals)
            return existing["id"]
        kwargs["name"] = name
        for k, v in kwargs.items():
            if isinstance(v, (list, dict)):
                kwargs[k] = json.dumps(v)
        cols = ", ".join(kwargs.keys())
        placeholders = ", ".join("?" * len(kwargs))
        c.execute(f"INSERT INTO companies ({cols}) VALUES ({placeholders})", list(kwargs.values()))
        return c.execute("SELECT last_insert_rowid()").fetchone()[0]


def get_company(name: str) -> dict | None:
    with conn() as c:
        row = c.execute("SELECT * FROM companies WHERE name=?", (name,)).fetchone()
        return dict(row) if row else None


def list_companies(status: str | None = None) -> list[dict]:
    with conn() as c:
        if status:
            rows = c.execute("SELECT * FROM companies WHERE status=? ORDER BY fit_score DESC", (status,)).fetchall()
        else:
            rows = c.execute("SELECT * FROM companies ORDER BY fit_score DESC").fetchall()
        return [dict(r) for r in rows]


def set_company_status(company_id: int, status: str):
    with conn() as c:
        c.execute("UPDATE companies SET status=? WHERE id=?", (status, company_id))


# ── Problem helpers ───────────────────────────────────────────────────────────

def insert_problem(company_id: int, title: str, description: str,
                   source_urls: list, relevance_score: float = 0) -> int:
    with conn() as c:
        c.execute(
            "INSERT INTO problems (company_id, title, description, source_urls, relevance_score) VALUES (?,?,?,?,?)",
            (company_id, title, description, json.dumps(source_urls), relevance_score)
        )
        return c.execute("SELECT last_insert_rowid()").fetchone()[0]


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
        c.execute(
            """INSERT INTO people (company_id, name, role, linkedin_url, twitter_url, github_url,
               relevance_score, relevance_reason, proximity) VALUES (?,?,?,?,?,?,?,?,?)""",
            (company_id, name, role,
             kwargs.get("linkedin_url"), kwargs.get("twitter_url"), kwargs.get("github_url"),
             kwargs.get("relevance_score", 0), kwargs.get("relevance_reason"), kwargs.get("proximity"))
        )
        return c.execute("SELECT last_insert_rowid()").fetchone()[0]


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


def approve_message(message_id: int, notes: str = "") -> int:
    with conn() as c:
        c.execute("UPDATE messages SET status='approved' WHERE id=?", (message_id,))
        c.execute(
            "INSERT INTO approvals (message_id, approved_at, notes) VALUES (?,?,?)",
            (message_id, datetime.now().isoformat(), notes)
        )
        return c.execute("SELECT last_insert_rowid()").fetchone()[0]


def get_pending_approvals() -> list[dict]:
    with conn() as c:
        rows = c.execute(
            "SELECT m.*, p.name AS person_name FROM messages m "
            "LEFT JOIN people p ON m.person_id=p.id "
            "WHERE m.status='draft' ORDER BY m.created_at"
        ).fetchall()
        return [dict(r) for r in rows]


# ── Follow-up helpers ─────────────────────────────────────────────────────────

def insert_follow_up(message_id: int, due_date: date, notes: str = ""):
    with conn() as c:
        c.execute(
            "INSERT INTO follow_ups (message_id, due_date, notes) VALUES (?,?,?)",
            (message_id, due_date.isoformat(), notes)
        )


def get_due_follow_ups() -> list[dict]:
    with conn() as c:
        today = date.today().isoformat()
        rows = c.execute(
            "SELECT f.*, m.content, m.variant FROM follow_ups f "
            "JOIN messages m ON f.message_id=m.id "
            "WHERE f.status='pending' AND f.due_date<=?",
            (today,)
        ).fetchall()
        return [dict(r) for r in rows]


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
