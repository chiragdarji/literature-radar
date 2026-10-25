from datetime import date

import numpy as np
import pytest

from radar.models import Paper, Trial
from radar.rank import mmr, rank_papers, rank_trials, tokenize

TODAY = date(2026, 10, 25)


def paper(pmid, title, abstract="", d=date(2026, 10, 1)):
    return Paper(pmid, title, "J", d, "A", abstract)


def test_tokenize_drops_stopwords_and_punctuation():
    expected = ["glp", "1", "receptor", "semaglutide"]
    assert tokenize("The GLP-1 receptor, and semaglutide!") == expected


def test_relevance_beats_passing_mention():
    on_topic = paper("1", "Dengue vaccine efficacy in children", "dengue vaccine dengue")
    passing = paper("2", "Yellow fever vaccine safety", "yellow fever vaccine")
    ranked = rank_papers("dengue vaccine", [passing, on_topic], top_k=2, today=TODAY)
    assert [s.record.pmid for s in ranked] == ["1", "2"]
    assert ranked[0].bm25 == pytest.approx(1.0) and ranked[1].bm25 == pytest.approx(0.0)


def test_recency_breaks_ties_and_future_dates_clamp():
    old = paper("old", "PCSK9 inhibition", d=date(2026, 4, 28))  # 180 days before TODAY
    new = paper("new", "PCSK9 inhibition", d=date(2026, 12, 31))  # future issue date
    ranked = rank_papers("PCSK9", [old, new], top_k=2, today=TODAY)
    assert ranked[0].record.pmid == "new" and ranked[0].recency == pytest.approx(1.0)
    assert ranked[1].recency == pytest.approx(0.5)


def test_missing_date_scores_zero_recency():
    (only,) = rank_papers("x", [paper("1", "x", d=None)], top_k=1, today=TODAY)
    assert only.recency == 0.0 and only.rank == 1


def test_mmr_prefers_diverse_second_pick():
    rel = np.array([1.0, 0.95, 0.6])
    vecs = np.array([[1.0, 0.0], [1.0, 0.0], [0.0, 1.0]])  # 0 and 1 are duplicates
    assert mmr(rel, vecs, lam=0.7, k=2) == [0, 2]
    assert mmr(rel, vecs, lam=1.0, k=2) == [0, 1]  # λ=1 is pure relevance


def test_top_k_and_trials():
    trials = [Trial(f"NCT0000000{i}", f"semaglutide arm {i}", "RECRUITING", (), "S",
                    date(2026, 10, i + 1)) for i in range(5)]
    ranked = rank_trials("semaglutide", trials, top_k=3, today=TODAY)
    assert len(ranked) == 3 and [s.rank for s in ranked] == [1, 2, 3]
    assert rank_trials("x", [], today=TODAY) == []


def test_bm25_common_term_still_rewards_frequency():
    from radar.rank import bm25_scores
    docs = [["semaglutide"] * 3 + ["x"], ["semaglutide", "x", "y", "z"], ["semaglutide"]]
    scores = bm25_scores(["semaglutide"], docs, k1=1.5, b=0.75)
    assert (scores > 0).all()  # classic IDF would be negative here (term in every doc)
    assert scores[0] > scores[1]
