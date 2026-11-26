"""SQLite storage. Every table carries client_id so each client's data stays separate.

Retention: `purge_older_than(months)` deletes conversations (and their files) older than the
client's retention period; run it daily from cron (see README).
"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    channel TEXT NOT NULL DEFAULT 'web',
    state TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_conv_client ON conversations(client_id, created_at);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL,
    role TEXT NOT NULL,             -- user / assistant
    kind TEXT NOT NULL DEFAULT 'text',   -- text / file / estimate
    text TEXT,
    payload TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_msg_conv ON messages(conversation_id, id);
CREATE TABLE IF NOT EXISTS files (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    client_id TEXT NOT NULL,
    filename TEXT NOT NULL,
    path TEXT NOT NULL,
    kind TEXT NOT NULL,
    parsed TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS leads (
    conversation_id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'new',   -- new / contacted / quoted / won / lost
    priority TEXT,
    value_eur REAL,
    summary TEXT,
    estimate TEXT,
    submitted_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_leads_client ON leads(client_id, priority);
CREATE TABLE IF NOT EXISTS llm_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id TEXT NOT NULL,
    conversation_id TEXT,
    purpose TEXT NOT NULL,
    model TEXT NOT NULL,
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    cost_usd REAL NOT NULL,
    created_at TEXT NOT NULL
);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def data_dir() -> Path:
    d = Path(os.environ.get("DATA_DIR", "data"))
    if not d.is_absolute():
        d = Path(__file__).resolve().parents[1] / d
    d.mkdir(parents=True, exist_ok=True)
    return d


def db_path() -> Path:
    return data_dir() / "app.sqlite3"


@contextmanager
def connect():
    con = sqlite3.connect(db_path())
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init() -> None:
    with connect() as con:
        con.executescript(SCHEMA)


# ---------------------------------------------------------------- conversations
def create_conversation(client_id: str, state: dict, channel: str = "web") -> str:
    cid = uuid.uuid4().hex
    with connect() as con:
        con.execute("INSERT INTO conversations VALUES (?,?,?,?,?,?)",
                    (cid, client_id, channel, json.dumps(state), now(), now()))
    return cid


def get_conversation(cid: str) -> dict | None:
    with connect() as con:
        row = con.execute("SELECT * FROM conversations WHERE id=?", (cid,)).fetchone()
    if not row:
        return None
    d = dict(row)
    d["state"] = json.loads(d["state"])
    return d


def save_state(cid: str, state: dict) -> None:
    with connect() as con:
        con.execute("UPDATE conversations SET state=?, updated_at=? WHERE id=?",
                    (json.dumps(state), now(), cid))


def add_message(cid: str, role: str, text: str | None, kind: str = "text", payload: dict | None = None) -> dict:
    ts = now()
    with connect() as con:
        con.execute("INSERT INTO messages (conversation_id, role, kind, text, payload, created_at) VALUES (?,?,?,?,?,?)",
                    (cid, role, kind, text, json.dumps(payload) if payload else None, ts))
    return {"role": role, "kind": kind, "text": text, "payload": payload, "created_at": ts}


def get_messages(cid: str) -> list[dict]:
    with connect() as con:
        rows = con.execute("SELECT role, kind, text, payload, created_at FROM messages WHERE conversation_id=? ORDER BY id",
                           (cid,)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["payload"] = json.loads(d["payload"]) if d["payload"] else None
        out.append(d)
    return out


# ---------------------------------------------------------------- files
def upload_dir(client_id: str, cid: str) -> Path:
    d = data_dir() / "uploads" / client_id / cid
    d.mkdir(parents=True, exist_ok=True)
    return d


def add_file(cid: str, client_id: str, filename: str, path: Path, kind: str, parsed: dict | None) -> str:
    fid = uuid.uuid4().hex
    with connect() as con:
        con.execute("INSERT INTO files VALUES (?,?,?,?,?,?,?,?)",
                    (fid, cid, client_id, filename, str(path), kind, json.dumps(parsed) if parsed else None, now()))
    return fid


def get_files(cid: str) -> list[dict]:
    with connect() as con:
        return [dict(r) for r in con.execute(
            "SELECT id, filename, kind, created_at FROM files WHERE conversation_id=? ORDER BY created_at", (cid,))]


# ---------------------------------------------------------------- leads
def upsert_lead(cid: str, client_id: str, priority: str, value_eur: float | None, summary: str, estimate: dict | None) -> None:
    ts = now()
    with connect() as con:
        con.execute("""INSERT INTO leads (conversation_id, client_id, priority, value_eur, summary, estimate, submitted_at, updated_at)
                       VALUES (?,?,?,?,?,?,?,?)
                       ON CONFLICT(conversation_id) DO UPDATE SET priority=excluded.priority, value_eur=excluded.value_eur,
                       summary=excluded.summary, estimate=excluded.estimate, updated_at=excluded.updated_at""",
                    (cid, client_id, priority, value_eur, summary, json.dumps(estimate) if estimate else None, ts, ts))


def list_leads(client_id: str) -> list[dict]:
    with connect() as con:
        rows = con.execute("""SELECT l.*, c.state FROM leads l JOIN conversations c ON c.id = l.conversation_id
                              WHERE l.client_id=? ORDER BY l.priority ASC, COALESCE(l.value_eur, 0) DESC""",
                           (client_id,)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["state"] = json.loads(d["state"])
        d["estimate"] = json.loads(d["estimate"]) if d["estimate"] else None
        out.append(d)
    return out


# ---------------------------------------------------------------- LLM cost log
def log_usage(client_id: str, cid: str | None, purpose: str, model: str, inp: int, out: int, cost: float) -> None:
    with connect() as con:
        con.execute("INSERT INTO llm_usage (client_id, conversation_id, purpose, model, input_tokens, output_tokens, cost_usd, created_at) VALUES (?,?,?,?,?,?,?,?)",
                    (client_id, cid, purpose, model, inp, out, cost, now()))


def usage_by_client() -> list[dict]:
    with connect() as con:
        return [dict(r) for r in con.execute(
            "SELECT client_id, COUNT(*) calls, SUM(input_tokens) input_tokens, SUM(output_tokens) output_tokens, ROUND(SUM(cost_usd), 4) cost_usd FROM llm_usage GROUP BY client_id")]


# ---------------------------------------------------------------- retention
def purge_older_than(months: int = 12, client_id: str | None = None) -> int:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=round(months * 30.44))).isoformat()
    with connect() as con:
        q = "SELECT id, client_id FROM conversations WHERE updated_at < ?" + (" AND client_id = ?" if client_id else "")
        rows = con.execute(q, (cutoff, client_id) if client_id else (cutoff,)).fetchall()
        for r in rows:
            for table, col in (("messages", "conversation_id"), ("files", "conversation_id"),
                               ("leads", "conversation_id"), ("conversations", "id")):
                con.execute(f"DELETE FROM {table} WHERE {col}=?", (r["id"],))
            shutil.rmtree(data_dir() / "uploads" / r["client_id"] / r["id"], ignore_errors=True)
    return len(rows)
