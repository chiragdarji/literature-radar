import json
from datetime import date
from urllib.parse import parse_qs

import httpx
import pytest

from radar.fetch_trials import advanced_filter, parse_study, search_trials


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_advanced_filter_window_and_phases():
    assert advanced_filter(180, today=date(2026, 10, 25)) == \
        "AREA[LastUpdatePostDate]RANGE[2026-04-28,MAX]"
    assert advanced_filter(None, ["PHASE3"]) == "(AREA[Phase]PHASE3)"
    assert advanced_filter(30, ["PHASE2", "PHASE3"], today=date(2026, 10, 25)) == (
        "AREA[LastUpdatePostDate]RANGE[2026-09-25,MAX] AND "
        "(AREA[Phase]PHASE2 OR AREA[Phase]PHASE3)")
    assert advanced_filter(None) is None


def test_parse_live_sample(fixture_text):
    data = json.loads(fixture_text("trials_semaglutide.json"))
    trials = [parse_study(s) for s in data["studies"]]
    assert len(trials) == 20
    first = trials[0]
    assert first.nct_id == "NCT07891156"
    assert first.status == "RECRUITING"
    assert first.phases == ("PHASE2", "PHASE3")
    assert first.sponsor.startswith("McGill University")
    assert first.last_update == date(2026, 10, 23)
    assert first.summary.startswith("The goal of this 24 week")
    assert first.url == "https://clinicaltrials.gov/study/NCT07891156"
    for t in trials:
        assert t.nct_id.startswith("NCT") and t.title and t.last_update
        assert "NA" not in t.phases

    by_id = {t.nct_id: t for t in trials}
    assert by_id["NCT07889453"].phases == ()  # observational: no phases key
    assert by_id["NCT06715514"].phases == ()  # ["NA"]
    assert by_id["NCT07677865"].status == "WITHDRAWN"


def test_parse_sparse_study():
    trial = parse_study({"protocolSection": {
        "identificationModule": {"nctId": "NCT00000001", "briefTitle": "Sparse"},
        "statusModule": {"lastUpdatePostDateStruct": {"date": "2026-05"}},
    }})
    assert trial.status == "UNKNOWN"
    assert trial.sponsor == "" and trial.summary == "" and trial.phases == ()
    assert trial.last_update == date(2026, 5, 1)


def test_search_trials_params(fixture_text):
    sample = json.loads(fixture_text("trials_semaglutide.json"))
    seen = {}

    def handler(request):
        seen.update(parse_qs(request.url.query.decode()))
        return httpx.Response(200, json=sample)

    result = search_trials(" semaglutide ", 180, http=_client(handler))
    assert result.total_count == 315 and len(result.trials) == 20
    assert seen["query.term"] == ["semaglutide"]
    assert seen["sort"] == ["LastUpdatePostDate:desc"]
    assert seen["pageSize"] == ["20"]
    assert seen["fields"] == ["NCTId,BriefTitle,OverallStatus,Phase,LeadSponsorName,"
                              "LastUpdatePostDate,BriefSummary"]
    assert seen["filter.advanced"][0].startswith("AREA[LastUpdatePostDate]RANGE[")
    assert "filter.phase" not in seen


def test_search_trials_no_results():
    result = search_trials("zzqx", 90, http=_client(
        lambda r: httpx.Response(200, json={"totalCount": 0, "studies": []})))
    assert result.trials == [] and result.total_count == 0


def test_search_trials_retries_then_succeeds():
    attempts = {"n": 0}

    def handler(request):
        attempts["n"] += 1
        if attempts["n"] == 1:
            return httpx.Response(502)
        return httpx.Response(200, json={"totalCount": 0, "studies": []})

    search_trials("semaglutide", 90, http=_client(handler))
    assert attempts["n"] == 2


def test_empty_query():
    with pytest.raises(ValueError):
        search_trials("  ", 90)
