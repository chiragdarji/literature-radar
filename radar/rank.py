"""Rank fetched records and pick a diverse top k (F4; algorithms A1-lite and A2).

score = bm25_weight · BM25 (min-max normalised) + recency_weight · 2^(−age_days / half_life)
then Maximal Marginal Relevance: pick d maximising λ·score(d) − (1−λ)·max_{s∈S} cos(d, s),
with cosine similarity over TF-IDF vectors. Every part of the score is kept for display.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Generic, TypeVar

import numpy as np

from radar.config import settings
from radar.models import Paper, Trial

T = TypeVar("T")

TOKEN = re.compile(r"[a-z0-9]+")
STOPWORDS = frozenset(
    "a an and are as at be by for from in into is it its of on or that the their this to was "
    "were with vs versus study trial patients".split())


@dataclass(frozen=True)
class Scored(Generic[T]):
    record: T
    bm25: float  # normalised to 0..1 within this result set
    recency: float  # 0..1, halves every half-life
    score: float  # weighted relevance used by MMR
    rank: int  # 1-based position after MMR


def tokenize(text: str) -> list[str]:
    return [t for t in TOKEN.findall(text.lower()) if t not in STOPWORDS]


def paper_text(p: Paper) -> str:
    return f"{p.title} {p.title} {p.abstract}"  # title counted twice: it is the strongest signal


def trial_text(t: Trial) -> str:
    return f"{t.title} {t.title} {t.summary}"


def rank_papers(query: str, papers: Sequence[Paper], *, top_k: int | None = None,
                today: date | None = None) -> list[Scored[Paper]]:
    return rank(query, papers, paper_text, lambda p: p.pub_date, top_k=top_k, today=today)


def rank_trials(query: str, trials: Sequence[Trial], *, top_k: int | None = None,
                today: date | None = None) -> list[Scored[Trial]]:
    return rank(query, trials, trial_text, lambda t: t.last_update, top_k=top_k, today=today)


def rank(
    query: str,
    records: Sequence[T],
    text_of: Callable[[T], str],
    date_of: Callable[[T], date | None],
    *,
    top_k: int | None = None,
    today: date | None = None,
) -> list[Scored[T]]:
    if not records:
        return []
    cfg = settings()["ranking"]
    top_k = top_k or settings()["brief"]["top_k"]
    today = today or date.today()
    docs = [tokenize(text_of(r)) or ["_empty_"] for r in records]
    q_tokens = tokenize(query)

    bm25 = _minmax(bm25_scores(q_tokens, docs, k1=cfg["bm25_k1"], b=cfg["bm25_b"]))
    half_life = cfg["recency_half_life_days"]
    recency = np.array([_recency(date_of(r), today, half_life) for r in records])
    score = cfg["bm25_weight"] * bm25 + cfg["recency_weight"] * recency

    order = mmr(score, _tfidf(docs), lam=cfg["mmr_lambda"], k=top_k)
    return [Scored(records[i], float(bm25[i]), float(recency[i]), float(score[i]), n)
            for n, i in enumerate(order, 1)]


def bm25_scores(query: list[str], docs: list[list[str]], *, k1: float, b: float) -> np.ndarray:
    """BM25 with the always-positive IDF log(1 + (N − n + 0.5) / (n + 0.5)).

    The classic IDF goes negative for a term in most documents, which is exactly the
    query term here (every fetched record matched it), and would invert the ranking.
    """
    n_docs = len(docs)
    avgdl = sum(len(d) for d in docs) / n_docs
    scores = np.zeros(n_docs)
    for term in set(query):
        n = sum(1 for d in docs if term in d)
        if n == 0:
            continue
        idf = np.log(1 + (n_docs - n + 0.5) / (n + 0.5))
        for i, doc in enumerate(docs):
            f = doc.count(term)
            if f:
                scores[i] += idf * f * (k1 + 1) / (f + k1 * (1 - b + b * len(doc) / avgdl))
    return scores


def mmr(relevance: np.ndarray, vectors: np.ndarray, *, lam: float, k: int) -> list[int]:
    """Greedy Maximal Marginal Relevance over unit-length row vectors."""
    selected: list[int] = []
    candidates = list(range(len(relevance)))
    sims = vectors @ vectors.T
    while candidates and len(selected) < k:
        def value(i: int) -> float:
            redundancy = max((sims[i, j] for j in selected), default=0.0)
            return lam * relevance[i] - (1 - lam) * redundancy
        best = max(candidates, key=lambda i: (value(i), relevance[i], -i))
        selected.append(best)
        candidates.remove(best)
    return selected


def _recency(d: date | None, today: date, half_life: float) -> float:
    if d is None:
        return 0.0
    age = max((today - d).days, 0)  # issue dates can be in the future
    return 2 ** (-age / half_life)


def _minmax(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    span = x.max() - x.min()
    return (x - x.min()) / span if span > 0 else np.zeros_like(x)


def _tfidf(docs: list[list[str]]) -> np.ndarray:
    vocab = {t: i for i, t in enumerate(sorted({t for d in docs for t in d}))}
    tf = np.zeros((len(docs), len(vocab)))
    for row, doc in enumerate(docs):
        for t in doc:
            tf[row, vocab[t]] += 1
    df = (tf > 0).sum(axis=0)
    idf = np.log((1 + len(docs)) / (1 + df)) + 1
    vec = tf * idf
    norms = np.linalg.norm(vec, axis=1, keepdims=True)
    return vec / np.where(norms == 0, 1, norms)

