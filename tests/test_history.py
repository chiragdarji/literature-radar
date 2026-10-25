import csv
import io
import sqlite3
from datetime import UTC, datetime, timedelta

import pytest

from radar import history
from radar.config import ROOT, settings

T0 = datetime(2026, 10, 25, 12, 0, tzinfo=UTC)


def _save(query="Semaglutide", status="ok", now=T0, **kw):
    if status == "ok":
        kw.setdefault("brief_md", f"# {query}")
        kw.setdefault("details", {"log": {"cost_usd": 0.05}})
        kw.setdefault("sources", [
            {"source_id": "PMID:1", "source_type": "pmid", "rank": 1, "cited": True,
             "title": "A", "date": "2026-10-01", "url": "u1"},
            {"source_id": "CTRI:CTRI/2025/06/088110", "source_type": "ctri", "title": "C"}])
    return history.save_search(query=query, window_months=6, status=status, now=now, **kw)


def test_schema_follows_prd(tmp_path):
    with history.connect() as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == history.SCHEMA_VERSION
        assert db.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert db.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert tables == {"searches", "briefs", "search_sources", "api_cache"}
    with history.connect() as db, pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO searches (created_at, query, query_norm, window_months, status) "
                   "VALUES ('x', 'q', 'q', 6, 'weird')")


def test_default_path_is_data_radar_db():
    assert settings()["history"]["path"] != "data/radar.db"  # tests use a temp file
    assert (ROOT / ".gitignore").read_text().count("data/radar.db") >= 1


def test_save_get_list_filter():
    sid = _save(paper_count=30, supported_pct=94.0)
    _save("dengue vaccine", status="no_results", now=T0 + timedelta(minutes=1),
          error="none found")
    _save("PCSK9", status="error", now=T0 + timedelta(minutes=2), error="ConnectError")

    recent = history.list_recent()
    assert [r.query for r in recent] == ["PCSK9", "dengue vaccine", "Semaglutide"]
    assert [r.status for r in recent] == ["error", "no_results", "ok"]
    assert [r.query for r in history.list_recent(text_filter="  SEMA ")] == ["Semaglutide"]
    assert len(history.list_recent(limit=2)) == 2

    saved = history.get_search(sid)
    assert saved.row["query_norm"] == "semaglutide" and saved.row["paper_count"] == 30
    assert saved.brief_md == "# Semaglutide" and saved.details["log"]["cost_usd"] == 0.05
    assert [s["source_id"] for s in saved.sources] == ["PMID:1", "CTRI:CTRI/2025/06/088110"]
    assert saved.sources[0]["cited"] == 1 and saved.created_at == T0
    assert history.get_search(9999) is None


def test_failed_runs_have_no_brief():
    sid = _save("PCSK9", status="error", error="boom")
    saved = history.get_search(sid)
    assert saved.brief_md is None and saved.details == {} and saved.sources == []


def test_unknown_column_rejected():
    with pytest.raises(TypeError):
        _save(colour="blue")


def test_latest_ok_respects_window_status_and_age():
    old = _save(now=T0)
    _save(status="error", now=T0 + timedelta(hours=1), error="x")
    assert history.latest_ok("semaglutide ", 6) == old
    assert history.latest_ok("semaglutide", 12) is None
    def within(hours):
        return history.latest_ok("semaglutide", 6, max_age_hours=24,
                                 now=T0 + timedelta(hours=hours))
    assert within(23) == old and within(25) is None


def test_delete_cascades_and_clear():
    a, b = _save(), _save("PCSK9")
    assert history.delete_search(a) and not history.delete_search(a)
    with history.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM briefs WHERE search_id = ?",
                          (a,)).fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM search_sources WHERE search_id = ?",
                          (a,)).fetchone()[0] == 0
    assert history.clear_history() == 1 and history.get_search(b) is None


def test_export_csv_is_metadata_only():
    _save(paper_count=30, brief_md="# SECRET BRIEF TEXT")
    rows = list(csv.reader(io.StringIO(history.export_csv())))
    assert rows[0][:4] == ["id", "created_at", "query", "query_norm"]
    assert rows[1][2] == "Semaglutide" and "SECRET BRIEF TEXT" not in history.export_csv()


def test_api_cache_expiry():
    history.api_cache_put("k", "<xml/>", now=T0)
    assert history.api_cache_get("k", now=T0 + timedelta(hours=23)) == "<xml/>"
    assert history.api_cache_get("k", now=T0 + timedelta(hours=25)) is None
    history.api_cache_put("k", "<new/>", now=T0 + timedelta(hours=25))
    assert history.api_cache_get("k", now=T0 + timedelta(hours=26)) == "<new/>"
    assert history.api_cache_clear() == 1


def test_migrations_keep_existing_history(monkeypatch):
    sid = _save()
    monkeypatch.setitem(history.MIGRATIONS, 3, "ALTER TABLE searches ADD COLUMN note TEXT;")
    with history.connect() as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 3
    assert history.get_search(sid).row["note"] is None


def test_latest_per_search_groups_repeats_newest_first():
    _save("Dengue vaccine", now=T0)
    _save("PCSK9", now=T0 + timedelta(minutes=1))
    newest = _save("dengue  vaccine", now=T0 + timedelta(minutes=2))
    history.save_search(query="dengue vaccine", window_months=12, status="error", error="x",
                        now=T0 + timedelta(minutes=3))  # another window: its own row
    grouped = history.latest_per_search(history.list_recent())
    assert [(i.query, i.window_months, n) for i, n in grouped] == [
        ("dengue vaccine", 12, 1), ("dengue  vaccine", 6, 2), ("PCSK9", 6, 1)]
    assert grouped[1][0].id == newest


def test_version_1_database_upgrades_with_archive_column(tmp_path):
    old = tmp_path / "v1.db"
    db = sqlite3.connect(old)
    db.executescript(history.MIGRATIONS[1])
    db.execute("PRAGMA user_version = 1")
    db.execute("INSERT INTO searches (created_at, query, query_norm, window_months, status) "
               "VALUES ('2026-10-25T12:00:00+00:00', 'PCSK9', 'pcsk9', 6, 'ok')")
    db.commit()
    db.close()
    (item,) = history.list_recent(path=old)
    assert item.query == "PCSK9" and item.archived is False
    with history.connect(old) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 2


def test_archive_and_delete_apply_to_all_runs_of_a_search():
    _save("Dengue vaccine", now=T0)
    _save("dengue vaccine", now=T0 + timedelta(minutes=1))
    keep = _save("PCSK9", now=T0 + timedelta(minutes=2))
    assert history.set_archived("DENGUE VACCINE", 6) == 2
    assert [i.query for i in history.list_recent()] == ["PCSK9"]
    assert {i.query for i in history.list_recent(archived=True)} == {"Dengue vaccine",
                                                                      "dengue vaccine"}
    assert len(history.list_recent(archived=None)) == 3
    assert history.set_archived("dengue vaccine", 6, archived=False) == 2
    assert len(history.list_recent()) == 3
    assert history.delete_runs("dengue vaccine", 6) == 2
    assert [i.id for i in history.list_recent(archived=None)] == [keep]


def test_date_bucket():
    now = datetime(2026, 10, 25, 12, 0).astimezone()
    assert history.date_bucket(now, now) == "Today"
    assert history.date_bucket(now - timedelta(days=1), now) == "Yesterday"
    assert history.date_bucket(now - timedelta(days=5), now) == "Previous 7 days"
    assert history.date_bucket(now - timedelta(days=20), now) == "Previous 30 days"
    assert history.date_bucket(now - timedelta(days=60), now) == "August 2026"
