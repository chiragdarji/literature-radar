"""Search history and 24-hour API cache in one local SQLite file, data/radar.db (F29, F11).

- searches / briefs / search_sources: a permanent record of every run, including failed
  and empty ones. Stores the rendered brief, IDs, titles, dates and links, never abstracts.
- api_cache: raw API responses for 24 hours (may hold abstracts; safe to wipe any time).

briefs.claims_json holds the run's detail as one JSON object:
  {"claims": {section: [{text, ids, label, note}]}, "dropped": [...], "log": {...},
   "ranking": {source_id: {kind, who, detail, relevance, recency, score}}, "retracted": [...]}
"""

from __future__ import annotations

import csv
import io
import json
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from radar.config import ROOT, settings

SCHEMA_VERSION = 1

# One connection at a time per process: fetchers write the API cache from parallel threads,
# and two first-time connections racing to set WAL mode and migrate would lock each other.
_lock = threading.RLock()

MIGRATIONS: dict[int, str] = {
    1: """
    CREATE TABLE searches (
      id                INTEGER PRIMARY KEY,
      created_at        TEXT    NOT NULL,
      query             TEXT    NOT NULL,
      query_norm        TEXT    NOT NULL,
      window_months     INTEGER NOT NULL,
      status            TEXT    NOT NULL CHECK (status IN ('ok','no_results','error')),
      error             TEXT,
      model             TEXT,
      paper_count       INTEGER,
      trial_count       INTEGER,
      india_count       INTEGER,
      retracted_count   INTEGER,
      invalid_citations INTEGER,
      supported_pct     REAL,
      latency_ms        INTEGER,
      input_tokens      INTEGER,
      output_tokens     INTEGER
    );
    CREATE INDEX idx_searches_query ON searches(query_norm, created_at DESC);

    CREATE TABLE briefs (
      search_id   INTEGER PRIMARY KEY REFERENCES searches(id) ON DELETE CASCADE,
      brief_md    TEXT NOT NULL,
      claims_json TEXT NOT NULL
    );

    CREATE TABLE search_sources (
      search_id   INTEGER NOT NULL REFERENCES searches(id) ON DELETE CASCADE,
      source_id   TEXT    NOT NULL,
      source_type TEXT    NOT NULL CHECK (source_type IN ('pmid','nct','ctri','cdsco')),
      rank        INTEGER,
      cited       INTEGER NOT NULL DEFAULT 0,
      title       TEXT,
      date        TEXT,
      status      TEXT,
      url         TEXT,
      PRIMARY KEY (search_id, source_id)
    );

    CREATE TABLE api_cache (
      cache_key   TEXT PRIMARY KEY,
      payload     TEXT NOT NULL,
      fetched_at  TEXT NOT NULL
    );
    """,
}

SEARCH_COLUMNS = ("query", "window_months", "status", "error", "model", "paper_count",
                  "trial_count", "india_count", "retracted_count", "invalid_citations",
                  "supported_pct", "latency_ms", "input_tokens", "output_tokens")


@dataclass(frozen=True)
class SearchSummary:
    id: int
    created_at: datetime
    query: str
    window_months: int
    status: str
    paper_count: int | None
    trial_count: int | None
    india_count: int | None
    supported_pct: float | None


@dataclass(frozen=True)
class SavedSearch:
    row: dict[str, Any]  # the searches row
    brief_md: str | None
    details: dict[str, Any]  # parsed claims_json, {} if no brief
    sources: list[dict[str, Any]]  # search_sources rows, in rank order

    @property
    def created_at(self) -> datetime:
        return parse_ts(self.row["created_at"])


def normalise(query: str) -> str:
    return " ".join(query.lower().split())


# --- Connection and migrations ---------------------------------------------------------------


@contextmanager
def connect(path: Path | None = None) -> Iterator[sqlite3.Connection]:
    """Open data/radar.db (WAL, foreign keys on), migrate, commit on success, always close."""
    path = Path(path or ROOT / settings()["history"]["path"])
    path.parent.mkdir(parents=True, exist_ok=True)
    with _lock:
        db = sqlite3.connect(path, timeout=10)  # waits for other processes (app + CLI)
        db.row_factory = sqlite3.Row
        try:
            db.execute("PRAGMA journal_mode = WAL")
            db.execute("PRAGMA foreign_keys = ON")
            _migrate(db)
            yield db
            db.commit()
        finally:
            db.close()


def _migrate(db: sqlite3.Connection) -> None:
    version = db.execute("PRAGMA user_version").fetchone()[0]
    for target in sorted(v for v in MIGRATIONS if v > version):
        db.executescript(MIGRATIONS[target])
        db.execute(f"PRAGMA user_version = {target}")


# --- Search history --------------------------------------------------------------------------


def save_search(*, query: str, window_months: int, status: str, brief_md: str | None = None,
                details: dict[str, Any] | None = None,
                sources: list[dict[str, Any]] | None = None, path: Path | None = None,
                now: datetime | None = None, **fields: Any) -> int:
    """Record one run. `fields` are the other searches columns (model, counts, scores…)."""
    unknown = set(fields) - set(SEARCH_COLUMNS)
    if unknown:
        raise TypeError(f"unknown searches columns: {sorted(unknown)}")
    values = {"query": query, "window_months": window_months, "status": status, **fields}
    cols = ["created_at", "query_norm", *values]
    params = [_ts(now), normalise(query), *values.values()]
    with connect(path) as db:
        cur = db.execute(f"INSERT INTO searches ({', '.join(cols)}) "
                         f"VALUES ({', '.join('?' * len(cols))})", params)
        search_id = cur.lastrowid
        if brief_md is not None:
            db.execute("INSERT INTO briefs (search_id, brief_md, claims_json) VALUES (?, ?, ?)",
                       (search_id, brief_md, json.dumps(details or {}, default=str)))
        db.executemany(
            "INSERT OR IGNORE INTO search_sources (search_id, source_id, source_type, rank, "
            "cited, title, date, status, url) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [(search_id, s["source_id"], s["source_type"], s.get("rank"), int(s.get("cited", 0)),
              s.get("title"), s.get("date"), s.get("status"), s.get("url"))
             for s in sources or []])
    return search_id


def list_recent(limit: int = 20, text_filter: str | None = None, *,
                path: Path | None = None) -> list[SearchSummary]:
    sql = ("SELECT id, created_at, query, window_months, status, paper_count, trial_count, "
           "india_count, supported_pct FROM searches")
    params: list[Any] = []
    if text_filter and text_filter.strip():
        sql += " WHERE query_norm LIKE ?"
        params.append(f"%{normalise(text_filter)}%")
    sql += " ORDER BY created_at DESC, id DESC LIMIT ?"
    params.append(limit)
    with connect(path) as db:
        rows = db.execute(sql, params).fetchall()
    return [SearchSummary(r["id"], parse_ts(r["created_at"]), r["query"], r["window_months"],
                          r["status"], r["paper_count"], r["trial_count"], r["india_count"],
                          r["supported_pct"]) for r in rows]


def get_search(search_id: int, *, path: Path | None = None) -> SavedSearch | None:
    with connect(path) as db:
        row = db.execute("SELECT * FROM searches WHERE id = ?", (search_id,)).fetchone()
        if row is None:
            return None
        brief = db.execute("SELECT brief_md, claims_json FROM briefs WHERE search_id = ?",
                           (search_id,)).fetchone()
        sources = db.execute("SELECT * FROM search_sources WHERE search_id = ? "
                             "ORDER BY rank IS NULL, rank, rowid", (search_id,)).fetchall()
    return SavedSearch(dict(row), brief["brief_md"] if brief else None,
                       json.loads(brief["claims_json"]) if brief else {},
                       [dict(s) for s in sources])


def latest_ok(query: str, window_months: int, *, max_age_hours: float | None = None,
              path: Path | None = None, now: datetime | None = None) -> int | None:
    """Most recent successful run of this query and window, optionally no older than given."""
    sql = ("SELECT id, created_at FROM searches WHERE query_norm = ? AND window_months = ? "
           "AND status = 'ok' ORDER BY created_at DESC, id DESC LIMIT 1")
    with connect(path) as db:
        row = db.execute(sql, (normalise(query), window_months)).fetchone()
    if row is None:
        return None
    if max_age_hours is not None:
        age = (now or datetime.now(UTC)) - parse_ts(row["created_at"])
        if age > timedelta(hours=max_age_hours):
            return None
    return row["id"]


def delete_search(search_id: int, *, path: Path | None = None) -> bool:
    with connect(path) as db:
        return db.execute("DELETE FROM searches WHERE id = ?", (search_id,)).rowcount > 0


def clear_history(*, path: Path | None = None) -> int:
    with connect(path) as db:
        return db.execute("DELETE FROM searches").rowcount


def export_csv(*, path: Path | None = None) -> str:
    """The searches table as CSV (metadata only, no briefs)."""
    with connect(path) as db:
        cur = db.execute("SELECT * FROM searches ORDER BY created_at DESC, id DESC")
        header = [c[0] for c in cur.description]
        rows = cur.fetchall()
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(header)
    writer.writerows(tuple(r) for r in rows)
    return out.getvalue()


# --- 24-hour API cache -----------------------------------------------------------------------


def api_cache_get(key: str, *, max_age_hours: float | None = None, path: Path | None = None,
                  now: datetime | None = None) -> str | None:
    max_age = settings()["history"]["api_cache_hours"] if max_age_hours is None else max_age_hours
    with connect(path) as db:
        row = db.execute("SELECT payload, fetched_at FROM api_cache WHERE cache_key = ?",
                         (key,)).fetchone()
    if row is None:
        return None
    if (now or datetime.now(UTC)) - parse_ts(row["fetched_at"]) > timedelta(hours=max_age):
        return None
    return row["payload"]


def api_cache_put(key: str, payload: str, *, path: Path | None = None,
                  now: datetime | None = None) -> None:
    with connect(path) as db:
        db.execute("INSERT INTO api_cache (cache_key, payload, fetched_at) VALUES (?, ?, ?) "
                   "ON CONFLICT(cache_key) DO UPDATE SET payload = excluded.payload, "
                   "fetched_at = excluded.fetched_at", (key, payload, _ts(now)))


def api_cache_clear(*, path: Path | None = None) -> int:
    with connect(path) as db:
        return db.execute("DELETE FROM api_cache").rowcount


def _ts(now: datetime | None) -> str:
    return (now or datetime.now(UTC)).astimezone(UTC).isoformat(timespec="seconds")


def parse_ts(text: str) -> datetime:
    return datetime.fromisoformat(text)
