import json
from urllib.parse import parse_qs

import httpx
import pytest

from radar import pipeline
from tests.test_brief import CDSCO, CTRI


def _http(fixture_text, *, empty=False):
    esearch = json.loads(fixture_text("pubmed_esearch_semaglutide.json"))
    efetch = fixture_text("pubmed_efetch_semaglutide.xml")
    trials = json.loads(fixture_text("trials_semaglutide.json"))

    def handler(request):
        path = request.url.path
        if path.endswith("esearch.fcgi"):
            return httpx.Response(200, json={"esearchresult": {"count": "0", "idlist": []}}
                                  if empty else esearch)
        if path.endswith("efetch.fcgi"):
            return httpx.Response(200, text=efetch)
        assert parse_qs(request.url.query.decode())["query.term"]
        return httpx.Response(200, json={"totalCount": 0, "studies": []} if empty else trials)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_run_brief_end_to_end(fixture_text, fake_api, monkeypatch):
    logged = []
    monkeypatch.setattr(pipeline.runlog, "append", logged.append)
    monkeypatch.setattr(pipeline.india, "load_for_query", lambda q: [CTRI, CDSCO])

    def responder(kwargs):
        if kwargs["model"] == "claude-sonnet-5-5":
            user = kwargs["messages"][0]["content"]
            assert user.count("PAPER |") == 5
            assert user.count("TRIAL (ClinicalTrials.gov)") == 10
            assert user.count("INDIA ") == 2
            return {"in_one_line": [{"text": "X", "ids": ["PMID:42886550"]}],
                    "research": [{"text": "Y", "ids": ["PMID:42610532"]},
                                 {"text": "Z", "ids": ["PMID:1"]}],
                    "trials": [{"text": "T", "ids": ["NCT07891156"]}],
                    "india": [{"text": "I", "ids": ["CTRI:CTRI/2025/06/088110"]}],
                    "gaps": [], "next_questions": [{"text": "Q?", "ids": []}]}
        return {"results": [{"claim": 0, "label": "supported", "note": ""},
                            {"claim": 1, "label": "unsupported", "note": "not in record"}]}

    result = pipeline.run_brief("semaglutide", 6, api=fake_api(responder),
                                http=_http(fixture_text))

    md = result.markdown
    assert md.splitlines()[1] == "AI-generated from public sources. Verify before use."
    assert "PubMed: 5 used of 1,455 found" in md and "CTRI: 1" in md and "CDSCO: 1" in md
    (log,) = logged
    assert log["invalid_citations"] == 1  # PMID:1 was never fetched
    assert log["claims_verified"] == 4 and log["supported"] == 4
    assert log["records_sent"] == 17 and log["total_s"] >= 0
    assert log["cost_usd"] > 0 and len(log["tokens"]) == 5  # brief + 4 section checks


def test_run_brief_no_records(fixture_text, fake_api, monkeypatch):
    monkeypatch.setattr(pipeline.india, "load_for_query", lambda q: [])
    with pytest.raises(pipeline.NoRecords):
        pipeline.run_brief("zzqx", 6, api=fake_api(lambda k: pytest.fail("no model call")),
                           http=_http(fixture_text, empty=True))
