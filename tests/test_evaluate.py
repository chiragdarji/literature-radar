import pytest

from radar import evaluate, history, pipeline
from tests.test_brief import CDSCO, CTRI
from tests.test_pipeline import _http, _responder


def test_load_queries(tmp_path):
    path = tmp_path / "q.txt"
    path.write_text("# comment\nsemaglutide\n\n  dengue vaccine | 12  # note\n", encoding="utf-8")
    assert evaluate.load_queries(path) == [("semaglutide", 6), ("dengue vaccine", 12)]
    assert len(evaluate.load_queries()) == 10  # the real list


def test_gold_and_recall(tmp_path):
    (tmp_path / "dengue_vaccine.txt").write_text("# gold\n111\nPMID:222\n333\n", encoding="utf-8")
    gold = evaluate.load_gold("Dengue  Vaccine", tmp_path)
    assert gold == {"111", "222", "333"}
    assert evaluate.recall(gold, ["111", "999", "222"]) == pytest.approx(2 / 3)
    assert evaluate.load_gold("pcsk9", tmp_path) is None
    assert evaluate.recall(None, ["1"]) is None


def test_evaluate_query_scores_and_saves(fixture_text, fake_api, monkeypatch, tmp_path):
    monkeypatch.setattr(pipeline.runlog, "append", lambda e: None)
    monkeypatch.setattr(pipeline.india, "load_for_query", lambda q: [CTRI, CDSCO])
    monkeypatch.setattr(evaluate, "GOLD_DIR", tmp_path)
    (tmp_path / "semaglutide.txt").write_text("42886550\n00000001\n", encoding="utf-8")

    row = evaluate.evaluate_query("semaglutide", 6, api=fake_api(_responder),
                                  http=_http(fixture_text))
    assert row["error"] is None
    assert row["invalid_citations"] == 1 and not row["passed"]  # fake model invents PMID:1
    assert row["recall_at_30"] == pytest.approx(0.5)
    assert history.latest_ok("semaglutide", 6) is not None


def test_evaluate_query_records_errors(fixture_text, fake_api, monkeypatch, tmp_path):
    monkeypatch.setattr(pipeline.india, "load_for_query", lambda q: [])
    row = evaluate.evaluate_query("zzqx", 6, api=fake_api(lambda k: {}),
                                  http=_http(fixture_text, empty=True))
    assert row["error"].startswith("NoRecords") and not row["passed"]
    assert history.list_recent()[0].status == "error"


def test_probe_counts_a_lenient_verifier_as_wrong(fake_api):
    def everything_supported(kwargs):
        n = kwargs["messages"][0]["content"].count("(cites:")
        return {"results": [{"claim": i, "note": "", "label": "supported"} for i in range(n)]}

    probe = evaluate.run_probe(api=fake_api(everything_supported))
    assert probe["cases"] == 14 and probe["planted_errors"] == 8
    assert probe["errors_caught"] == 0 and probe["correct"] == 6
    assert len(probe["misses"]) == 8


def test_report_table():
    rows = [{"query": "x", "months": 6, "error": None, "invalid_citations": 0, "claims": 10,
             "supported": 9, "partial": 1, "unsupported": 0, "support_rate": 0.9,
             "recall_at_30": None, "recall_at_10": None, "total_s": 20.0, "cost_usd": 0.05,
             "dropped": [], "passed": True},
            {"query": "y", "months": 6, "error": "NoRecords: none", "total_s": 2, "passed": False}]
    probe = {"cases": 14, "correct": 14, "planted_errors": 8, "errors_caught": 8, "misses": []}
    from datetime import datetime
    text = evaluate.report(rows, probe, datetime(2026, 10, 25, 19, 0))
    assert "| x | 6 mo | 0 | 9/10 (90%) | 1 | 0 | n/a | n/a | 20 s | $0.050 | ✓ |" in text
    assert "error: NoRecords" in text
    assert "1/2 queries pass" in text and "caught 8/8 planted errors" in text
