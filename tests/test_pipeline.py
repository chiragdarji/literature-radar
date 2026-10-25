import json
import re
from urllib.parse import parse_qs

import httpx
import pytest

from radar import history, pipeline
from radar.config import settings
from tests.test_brief import CDSCO, CTRI


def _http(fixture_text, *, empty=False, down=False, calls=None):
    esearch = json.loads(fixture_text("pubmed_esearch_semaglutide.json"))
    efetch = fixture_text("pubmed_efetch_semaglutide.xml")
    trials = json.loads(fixture_text("trials_semaglutide.json"))

    def handler(request):
        if calls is not None:
            calls.append(request.url.path)
        if down:
            raise httpx.ConnectError("offline", request=request)
        path = request.url.path
        if path.endswith("esearch.fcgi"):
            return httpx.Response(200, json={"esearchresult": {"count": "0", "idlist": []}}
                                  if empty else esearch)
        if path.endswith("efetch.fcgi"):
            return httpx.Response(200, text=efetch)
        assert parse_qs(request.url.query.decode())["query.term"]
        return httpx.Response(200, json={"totalCount": 0, "studies": []} if empty else trials)

    return httpx.Client(transport=httpx.MockTransport(handler))


def _responder(kwargs):
    """Fake model: cites the first paper and trial it was given, plus one invented PMID."""
    user = kwargs["messages"][0]["content"]
    if kwargs["model"] == "claude-sonnet-5-5":
        pmid = re.search(r"\[(PMID:\d+)\] PAPER", user).group(1)
        nct = re.search(r"\[(NCT\d{8})\] TRIAL", user).group(1)
        return {"in_one_line": [{"text": "X", "ids": [pmid]}],
                "research": [{"text": "Y", "ids": [pmid]}, {"text": "Z", "ids": ["PMID:1"]}],
                "trials": [{"text": "T", "ids": [nct]}],
                "india": [{"text": "I", "ids": ["CTRI:CTRI/2025/06/088110"]}],
                "gaps": [], "next_questions": [{"text": "Q?", "ids": []}]}
    return {"results": [{"claim": 0, "note": "", "label": "supported"},
                        {"claim": 1, "note": "", "label": "supported"}]}


@pytest.fixture
def isolated(monkeypatch):
    """Fixed India records and no log writes (conftest already gives a fresh database)."""
    logged = []
    monkeypatch.setattr(pipeline.runlog, "append", logged.append)
    monkeypatch.setattr(pipeline.india, "load_for_query", lambda q: [CTRI, CDSCO])
    return logged


def test_run_brief_end_to_end(fixture_text, fake_api, isolated):
    api = fake_api(_responder)
    messages = []
    result = pipeline.run_brief("semaglutide", 6, api=api, http=_http(fixture_text),
                                progress=messages.append)

    user = api.calls[0]["messages"][0]["content"]
    assert user.count("PAPER |") == 5
    assert user.count("TRIAL (ClinicalTrials.gov)") == 10  # MMR picked 10 of 20
    assert "- Trials: 10;" in user
    md = result.markdown
    assert md.splitlines()[1] == "AI-generated from public sources. Verify before use."
    assert "PubMed: 5 used of 1,455 found" in md and "ClinicalTrials.gov: 10 used of 315" in md
    assert [s.rank for s in result.ranked[:5]] == [1, 2, 3, 4, 5]
    assert messages[0].startswith("Searching PubMed") and len(messages) == 4
    (log,) = isolated
    assert log["invalid_citations"] == 1  # PMID:1 was never fetched
    assert log["claims_verified"] == 4 and log["supported"] == 4
    assert log["records_sent"] == 17 and log["cost_usd"] > 0


def test_saved_view_has_no_abstracts_and_keeps_scores(fixture_text, fake_api, isolated):
    result = pipeline.run_brief("semaglutide", 6, api=fake_api(_responder),
                                http=_http(fixture_text))
    sid = pipeline.save_result(result, "semaglutide", 6)
    with history.connect() as db:
        dump = "\n".join(str(tuple(r)) for t in ("searches", "briefs", "search_sources")
                         for r in db.execute(f"SELECT * FROM {t}"))
    abstract_bit = result.ranked[0].record.abstract[:60]
    summary_bit = next(s.record for s in result.ranked
                       if s.record.source_id.startswith("NCT")).summary[:60]
    assert abstract_bit not in dump and summary_bit not in dump  # F26: history has no abstracts

    payload = pipeline.open_saved(sid).payload
    json.dumps(payload)
    assert payload["markdown"] == result.markdown
    assert sum(s["cited"] for s in payload["sources"]) == 2
    assert {"relevance", "recency", "score", "rank", "kind", "who"} <= set(payload["sources"][0])
    assert payload["india"][0]["cited"] and not payload["india"][1]["cited"]
    assert payload["india"][0]["sponsor"].startswith("Dr. Reddy's")  # joined from the CSV
    row = history.get_search(sid).row
    assert row["status"] == "ok" and row["paper_count"] == 5 and row["trial_count"] == 20
    assert row["invalid_citations"] == 1 and row["supported_pct"] == 100.0
    assert row["input_tokens"] > 0 and row["model"] == "claude-sonnet-5-5"


def test_get_brief_reuses_saved_then_refreshes(fixture_text, fake_api, isolated):
    api = fake_api(_responder)
    first = pipeline.get_brief("semaglutide", 6, api=api, http=_http(fixture_text))
    second = pipeline.get_brief("Semaglutide", 6, api=api, http=_http(fixture_text))
    assert first.source == "live" and second.source == "saved"
    assert second.search_id == first.search_id and "saved brief" in second.notice
    assert second.payload["markdown"] == first.payload["markdown"]
    calls = len(api.calls)
    third = pipeline.get_brief("semaglutide", 6, refresh=True, api=api, http=_http(fixture_text))
    assert third.source == "live" and third.search_id != first.search_id
    assert len(api.calls) > calls


def test_api_cache_skips_network_on_rerun(fixture_text, fake_api, isolated):
    calls = []
    api = fake_api(_responder)
    pipeline.run_brief("semaglutide", 6, api=api, http=_http(fixture_text, calls=calls))
    first = len(calls)
    pipeline.run_brief("semaglutide", 6, api=api, http=_http(fixture_text, calls=calls))
    assert first == 3 and len(calls) == first  # esearch, efetch, trials: all served from cache


def test_outage_falls_back_to_saved_and_logs_error(fixture_text, fake_api, isolated,
                                                  monkeypatch):
    api = fake_api(_responder)
    pipeline.get_brief("semaglutide", 6, api=api, http=_http(fixture_text))
    monkeypatch.setitem(settings()["history"], "reuse_brief_hours", 0)
    monkeypatch.setitem(settings()["history"], "api_cache_hours", 0)
    outcome = pipeline.get_brief("semaglutide", 6, api=api, http=_http(fixture_text, down=True))
    assert outcome.source == "saved (offline)" and "unreachable" in outcome.notice

    with pytest.raises(pipeline.SourcesDown):
        pipeline.get_brief("pcsk9", 6, api=api, http=_http(fixture_text, down=True))
    statuses = [(r.query, r.status) for r in history.list_recent()]
    assert statuses[:3] == [("pcsk9", "error"), ("semaglutide", "error"), ("semaglutide", "ok")]


def test_no_records_is_saved(fixture_text, fake_api, isolated, monkeypatch):
    monkeypatch.setattr(pipeline.india, "load_for_query", lambda q: [])
    with pytest.raises(pipeline.NoRecords):
        pipeline.get_brief("zzqx", 6, api=fake_api(lambda k: pytest.fail("no model call")),
                           http=_http(fixture_text, empty=True))
    (row,) = history.list_recent()
    assert (row.query, row.status) == ("zzqx", "no_results")


def test_ambiguous_meanings():
    assert pipeline.ambiguous_meanings(" ms ") == ["multiple sclerosis", "mass spectrometry"]
    assert pipeline.ambiguous_meanings("semaglutide") is None
    assert pipeline.ambiguous_meanings("MS biomarkers") is None  # only a bare abbreviation
