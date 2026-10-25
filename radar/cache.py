"""SQLite cache of finished briefs, keyed by query + window (F11, AD-10).

Entries expire after ttl_hours. Pinned entries (the demo backups) never expire. Stale
entries can still be read when live sources are down (F25).
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from radar.config import ROOT, settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS briefs (
    key TEXT PRIMARY KEY,
    query TEXT NOT NULL,
    months INTEGER NOT NULL,
    created_at REAL NOT NULL,
    pinned INTEGER NOT NULL DEFAULT 0,
    payload TEXT NOT NULL
)
"""


@dataclass(frozen=True)
class Entry:
    query: str
    months: int
    created_at: float
    pinned: bool
    stale: bool
    payload: dict[str, Any]


def cache_key(query: str, months: int) -> str:
    return f"{' '.join(query.lower().split())}|{months}"


def get(query: str, months: int, *, allow_stale: bool = False, path: Path | None = None,
        now: float | None = None) -> Entry | None:
    with _connect(path) as db:
        row = db.execute("SELECT query, months, created_at, pinned, payload FROM briefs "
                         "WHERE key = ?", (cache_key(query, months),)).fetchone()
    if row is None:
        return None
    age_h = ((time.time() if now is None else now) - row[2]) / 3600
    stale = not row[3] and age_h > settings()["cache"]["ttl_hours"]
    if stale and not allow_stale:
        return None
    return Entry(row[0], row[1], row[2], bool(row[3]), stale, json.loads(row[4]))


def put(query: str, months: int, payload: dict[str, Any], *, path: Path | None = None,
        now: float | None = None) -> None:
    """Store a brief, keeping the pinned flag if the entry was already pinned."""
    with _connect(path) as db:
        db.execute(
            "INSERT INTO briefs (key, query, months, created_at, pinned, payload) "
            "VALUES (?, ?, ?, ?, 0, ?) ON CONFLICT(key) DO UPDATE SET "
            "query = excluded.query, created_at = excluded.created_at, payload = excluded.payload",
            (cache_key(query, months), query, months, time.time() if now is None else now,
             json.dumps(payload, default=str)))


def pin(query: str, months: int, pinned: bool = True, *, path: Path | None = None) -> bool:
    with _connect(path) as db:
        cur = db.execute("UPDATE briefs SET pinned = ? WHERE key = ?",
                         (int(pinned), cache_key(query, months)))
        return cur.rowcount > 0


def entries(*, path: Path | None = None) -> list[tuple[str, int, float, bool]]:
    with _connect(path) as db:
        rows = db.execute(
            "SELECT query, months, created_at, pinned FROM briefs ORDER BY created_at DESC")
        return [(q, m, c, bool(p)) for q, m, c, p in rows]


@contextmanager
def _connect(path: Path | None) -> Iterator[sqlite3.Connection]:
    """Open, commit on success, and always close."""
    path = path or ROOT / settings()["cache"]["path"]
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    try:
        db.execute(SCHEMA)
        yield db
        db.commit()
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="List cached briefs or pin demo backups.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    for name in ("pin", "unpin"):
        p = sub.add_parser(name)
        p.add_argument("query")
        p.add_argument("months", type=int)
    args = parser.parse_args()

    if args.cmd == "list":
        for q, m, created, pinned in entries():
            stamp = time.strftime("%Y-%m-%d %H:%M", time.localtime(created))
            print(f"{'📌' if pinned else '  '} {q!r:<30} {m:>2} months  {stamp}")
    else:
        ok = pin(args.query, args.months, args.cmd == "pin")
        print("done" if ok else f"no cached brief for {args.query!r}, {args.months} months")


if __name__ == "__main__":
    main()
