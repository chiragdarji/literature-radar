from datetime import date
from urllib.parse import parse_qs

import httpx
import pytest

from radar.fetch_pubmed import build_term, parse_efetch, search_pubmed

SEMA = '("semaglutide"[tiab] OR "semaglutide"[MeSH Terms] OR (semaglutide))'


def test_build_term_single():
    assert build_term(["semaglutide"]) == SEMA


def test_build_term_adds_pubmed_term_matching_for_phrases():
    assert build_term(["tuberculosis vaccine"]) == (
        '("tuberculosis vaccine"[tiab] OR "tuberculosis vaccine"[MeSH Terms] '
        'OR (tuberculosis vaccine))')


def test_build_term_or_joins_and_strips_query_syntax():
    term = build_term(['PCSK9', ' "evolocumab" ', "(GLP-1)  [receptor]", ""])
    assert term == ('(("PCSK9"[tiab] OR "PCSK9"[MeSH Terms] OR (PCSK9)) OR '
                    '("evolocumab"[tiab] OR "evolocumab"[MeSH Terms] OR (evolocumab)) OR '
                    '("GLP-1 receptor"[tiab] OR "GLP-1 receptor"[MeSH Terms] OR (GLP-1 receptor)))')


def test_build_term_empty():
    with pytest.raises(ValueError):
        build_term(["  "])


def test_parse_live_sample(fixture_text):
    papers = parse_efetch(fixture_text("pubmed_efetch_semaglutide.xml"))
    assert [p.pmid for p in papers] == ["42886550", "42610532", "42669356", "42330703", "42894545"]
    for p in papers:
        assert p.title and p.journal and p.first_author and p.abstract
        assert p.pub_date is not None
        assert p.url == f"https://pubmed.ncbi.nlm.nih.gov/{p.pmid}/"
        assert not p.retracted
    structured = papers[1]
    assert structured.abstract.startswith("PURPOSE:")
    assert "\nMETHODS:" in structured.abstract


def test_parse_retracted_sample(fixture_text):
    (paper,) = parse_efetch(fixture_text("pubmed_efetch_retracted.xml"))
    assert paper.pmid == "41532579"
    assert paper.retracted
    assert "Retracted Publication" in paper.publication_types
    assert paper.abstract == ""


def test_parse_edge_cases(fixture_text):
    meta, epub = parse_efetch(fixture_text("pubmed_efetch_edge_cases.xml"))

    assert meta.title == "Effect of PCSK9 inhibition on LDL-C2 levels."  # inline <i>, <sup> kept
    assert meta.first_author == "FOURIER Investigators"
    assert meta.pub_date == date(2026, 1, 1)  # MedlineDate "2026 Jan-Feb"
    assert meta.abstract == ""
    assert meta.is_review  # meta-analysis

    assert epub.first_author == "Roe AB"
    assert epub.pub_date == date(2025, 11, 3)  # e-pub earlier than the Winter 2026 issue
    assert epub.retracted  # via CommentsCorrections RetractionIn
    assert not epub.is_review


def _mock_client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def _esearch_json(count, ids):
    return {"esearchresult": {"count": str(count), "idlist": ids}}


def test_search_pubmed_best_match_plus_newest(fixture_text):
    fetch_xml = fixture_text("pubmed_efetch_semaglutide.xml")
    relevant, by_date = ["42886550", "42610532", "42669356"], ["42610532", "42330703",
                                                               "42894545", "42886550"]
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        params = parse_qs(request.url.query.decode())
        calls.append((request.url.path, params))
        if request.url.path.endswith("esearch.fcgi"):
            ids = relevant if params["sort"] == ["relevance"] else by_date
            return httpx.Response(200, json=_esearch_json(1455, ids))
        return httpx.Response(200, text=fetch_xml)

    result = search_pubmed("semaglutide", 180, http=_mock_client(handler))

    (_, rel), (_, new), (fetch_path, fetch) = calls
    assert rel["sort"] == ["relevance"] and rel["retmax"] == ["20"]
    assert new["sort"] == ["pub_date"] and new["retmax"] == ["30"]
    for params in (rel, new):
        assert params["term"] == [SEMA]
        assert params["datetype"] == ["pdat"] and params["reldate"] == ["180"]
        assert params["tool"] == ["literature-radar"] and params["email"] == ["test@example.com"]
        assert "api_key" not in params
    # Best Match first, then newest not already included, no duplicates
    assert fetch["id"] == ["42886550,42610532,42669356,42330703,42894545"]
    assert [p.pmid for p in result.papers] == ["42886550", "42610532", "42669356",
                                               "42330703", "42894545"]
    assert result.hit_count == 1455 and not result.broad_query


def test_newest_capped_at_ten_and_skipped_when_all_fetched():
    def handler(request):
        params = parse_qs(request.url.query.decode())
        if request.url.path.endswith("esearch.fcgi"):
            if params["sort"] == ["relevance"]:
                return httpx.Response(200, json=_esearch_json(500, [str(i) for i in range(20)]))
            return httpx.Response(200, json=_esearch_json(500, [str(i) for i in range(5, 35)]))
        ids = params["id"][0].split(",")
        assert ids == [str(i) for i in range(20)] + [str(i) for i in range(20, 30)]
        return httpx.Response(200, text="<PubmedArticleSet/>")

    search_pubmed("x", 180, http=_mock_client(handler))

    sorts = []

    def small(request):
        params = parse_qs(request.url.query.decode())
        if request.url.path.endswith("esearch.fcgi"):
            sorts.append(params["sort"][0])
            return httpx.Response(200, json=_esearch_json(2, ["1", "2"]))
        return httpx.Response(200, text="<PubmedArticleSet/>")

    search_pubmed("y", 180, http=_mock_client(small))  # "x" would be served from the API cache
    assert sorts == ["relevance"]  # every hit already fetched: no newest query


def test_search_pubmed_splits_retracted(fixture_text):
    xml = fixture_text("pubmed_efetch_retracted.xml")

    def handler(request):
        if request.url.path.endswith("esearch.fcgi"):
            return httpx.Response(200, json=_esearch_json(1, ["41532579"]))
        return httpx.Response(200, text=xml)

    result = search_pubmed("semaglutide", 365, http=_mock_client(handler))
    assert result.papers == []
    assert [p.pmid for p in result.retracted] == ["41532579"]


def test_broad_query_flagged():
    def handler(request):
        if request.url.path.endswith("esearch.fcgi"):
            return httpx.Response(200, json=_esearch_json(12000, []))
        raise AssertionError("efetch should not be called with no ids")

    result = search_pubmed("cancer", 180, http=_mock_client(handler))
    assert result.broad_query and result.hit_count == 12000


def test_retries_on_server_error(fixture_text):
    attempts = {"n": 0}

    def handler(request):
        if request.url.path.endswith("esearch.fcgi"):
            attempts["n"] += 1
            if attempts["n"] < 3:
                return httpx.Response(503)
            return httpx.Response(200, json=_esearch_json(0, []))
        raise AssertionError

    result = search_pubmed("semaglutide", 180, http=_mock_client(handler))
    assert attempts["n"] == 3 and result.hit_count == 0


def test_gives_up_on_client_error():
    def handler(request):
        return httpx.Response(400)

    with pytest.raises(httpx.HTTPStatusError):
        search_pubmed("semaglutide", 180, http=_mock_client(handler))
