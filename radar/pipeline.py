"""End-to-end run: fetch → rank → brief → citation check → verify → render → log → cache.

`get_brief` is what the app calls: it serves the 24-hour cache, runs live otherwise, and
falls back to a stale cached brief when a live source is down (F11, F25).
"""

from __future__ import annotations

import argparse
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import anthropic
import httpx

from radar import cache, india, runlog
from radar.brief import Brief, Record, generate_brief
from radar.config import settings
from radar.fetch_pubmed import PubMedResult, search_pubmed
from radar.fetch_trials import TrialsResult, search_trials
from radar.models import IndiaRecord, Paper, Trial
from radar.rank import Scored, rank_papers, rank_trials
from radar.render import RunStamp, render_markdown
from radar.verify import VerifyStats, verify_brief

DAYS_PER_MONTH = 30.44

Progress = Callable[[str], None]


class NoRecords(RuntimeError):
    """Nothing found in any source (F12)."""


class SourcesDown(RuntimeError):
    """A live source or the model API failed and there is no cached brief to fall back on."""


@dataclass
class RunResult:
    markdown: str
    brief: Brief
    stats: VerifyStats
    stamp: RunStamp
    log: dict[str, Any]
    ranked: list[Scored[Any]]  # papers then trials sent to the model, with score parts
    india: list[IndiaRecord]
    retracted: list[Paper]


@dataclass
class Outcome:
    payload: dict[str, Any]
    source: str  # "live", "cache" or "stale cache"
    notice: str | None = None


def ambiguous_meanings(query: str) -> list[str] | None:
    """F25: meanings to choose from when the whole query is a known ambiguous abbreviation."""
    table = {k.lower(): v for k, v in settings()["ambiguous"].items()}
    return table.get(query.strip().lower())


def get_brief(query: str, months: int, *, refresh: bool = False, progress: Progress | None = None,
              api: Any = None, http: httpx.Client | None = None) -> Outcome:
    if not refresh and (hit := cache.get(query, months)):
        return Outcome(hit.payload, "cache", f"Cached brief from {_when(hit.created_at)}.")
    try:
        result = run_brief(query, months, progress=progress, api=api, http=http)
    except (httpx.HTTPError, anthropic.APIConnectionError, anthropic.APIStatusError) as exc:
        if stale := cache.get(query, months, allow_stale=True):
            return Outcome(stale.payload, "stale cache",
                           f"Live sources are unreachable ({type(exc).__name__}), so this is the "
                           f"cached brief from {_when(stale.created_at)}.")
        raise SourcesDown("A data source or the AI service did not respond. Please try again "
                          "in a minute.") from exc
    payload = to_payload(result)
    cache.put(query, months, payload)
    return Outcome(payload, "live")


def run_brief(query: str, months: int, *, progress: Progress | None = None, api: Any = None,
              http: httpx.Client | None = None) -> RunResult:
    say = progress or (lambda msg: None)
    query = query.strip()
    days = round(months * DAYS_PER_MONTH)
    models = settings()["models"]
    timings: dict[str, float] = {}
    t0 = time.perf_counter()

    say("Searching PubMed and ClinicalTrials.gov…")
    with ThreadPoolExecutor(max_workers=2) as pool:
        papers_f = pool.submit(search_pubmed, query, days, http=http)
        trials_f = pool.submit(search_trials, query, days, http=http)
        pubmed: PubMedResult = papers_f.result()
        trials: TrialsResult = trials_f.result()
    india_records = india.load_for_query(query)
    timings["fetch_s"] = time.perf_counter() - t0
    if not (pubmed.papers or trials.trials or india_records):
        raise NoRecords(f"No papers, trials or India records for {query!r} in the last "
                        f"{months} months.")

    say(f"Ranking {len(pubmed.papers)} papers and {len(trials.trials)} trials…")
    ranked_papers = rank_papers(query, pubmed.papers)
    ranked_trials = rank_trials(query, trials.trials)
    papers: list[Paper] = [s.record for s in ranked_papers]
    trial_list: list[Trial] = [s.record for s in ranked_trials]
    records: list[Record] = [*papers, *trial_list, *india_records]

    say(f"Writing the brief with {models['brief']}…")
    t1 = time.perf_counter()
    brief = generate_brief(query, months, papers, trial_list, india_records, api=api)
    timings["brief_s"] = time.perf_counter() - t1

    say(f"Checking each claim against its sources with {models['verify']}…")
    t2 = time.perf_counter()
    brief, stats = verify_brief(brief, {r.source_id: r for r in records}, api=api)
    timings["verify_s"] = time.perf_counter() - t2
    timings["total_s"] = time.perf_counter() - t0

    ctri = sum(1 for r in india_records if r.source == "CTRI")
    notes = []
    if pubmed.broad_query:
        notes.append(f"Very broad query: {pubmed.hit_count:,} papers matched, so the 30 most "
                     "relevant were used. A narrower term will give a sharper brief.")
    if len(papers) + len(trial_list) < 5:
        notes.append("Few recent records were found. Try a 12-month window or another name "
                     "for the target (brand name, gene symbol).")
    stamp = RunStamp(
        run_at=datetime.now().astimezone(),
        months=months,
        source_counts={
            "PubMed": f"{len(papers)} used of {pubmed.hit_count:,} found",
            "ClinicalTrials.gov": f"{len(trial_list)} used of {trials.total_count:,} found",
            "CTRI": str(ctri),
            "CDSCO": str(len(india_records) - ctri),
        },
        models={"brief": models["brief"], "verification": models["verify"]},
        stats=stats,
        notes=notes,
    )
    markdown = render_markdown(query, brief, records, stamp, pubmed.retracted)
    log = _log_entry(query, months, pubmed, trials, records, brief, stats, timings)
    runlog.append(log)
    return RunResult(markdown, brief, stats, stamp, log, [*ranked_papers, *ranked_trials],
                     india_records, pubmed.retracted)


def to_payload(result: RunResult) -> dict[str, Any]:
    """JSON-safe view for the app and the cache. No abstracts or trial summaries (F26)."""
    cited = {i for c in result.brief.claims() for i in c.ids}
    sources = []
    for s in result.ranked:
        r = s.record
        paper = isinstance(r, Paper)
        sources.append({
            "id": r.source_id, "kind": "Paper" if paper else "Trial", "title": r.title,
            "detail": (", ".join(r.publication_types) if paper
                       else f"{r.status} · {'/'.join(r.phases) or 'no phase'}"),
            "who": r.journal if paper else r.sponsor,
            "date": str((r.pub_date if paper else r.last_update) or ""),
            "url": r.url, "rank": s.rank, "relevance": round(s.bm25, 3),
            "recency": round(s.recency, 3), "score": round(s.score, 3),
            "cited": r.source_id in cited,
        })
    india_rows = [{"id": r.source_id, "source": r.source, "title": r.title,
                   "date": str(r.date or ""), "url": r.url, **r.details,
                   "cited": r.source_id in cited} for r in result.india]
    return {
        "markdown": result.markdown,
        "run_at": result.stamp.run_at.isoformat(timespec="seconds"),
        "log": result.log,
        "sources": sources,
        "india": india_rows,
        "retracted": [{"id": p.source_id, "title": p.title, "url": p.url}
                      for p in result.retracted],
    }


def _log_entry(query, months, pubmed, trials, records, brief, stats, timings) -> dict[str, Any]:
    costs = [u.cost_usd for u in brief.usage]
    return {
        "ts": datetime.now().astimezone().isoformat(timespec="seconds"),
        "query": query,
        "months": months,
        "pubmed_hits": pubmed.hit_count,
        "papers_fetched": len(pubmed.papers),
        "retracted": len(pubmed.retracted),
        "trials_total": trials.total_count,
        "records_sent": len(records),
        "tokens": [{"model": u.model, "in": u.input_tokens, "out": u.output_tokens}
                   for u in brief.usage],
        "cost_usd": round(sum(c for c in costs if c is not None), 5),
        "invalid_citations": brief.invalid_citations,
        "claims_verified": stats.total,
        "supported": stats.supported,
        "partial": stats.partial,
        "unsupported": stats.unsupported,
        "support_rate": stats.support_rate,
        "dropped": [{"section": d.section, "reason": d.reason, "text": d.claim.text}
                    for d in brief.dropped],
        **{k: round(v, 2) for k, v in timings.items()},
    }


def _when(ts: float) -> str:
    return datetime.fromtimestamp(ts).astimezone().strftime("%d %b %Y, %H:%M")


def main() -> None:
    parser = argparse.ArgumentParser(description="Write a cited, verified brief for a query.")
    parser.add_argument("query")
    parser.add_argument("--months", type=int, default=settings()["brief"]["default_window_months"],
                        choices=settings()["brief"]["windows_months"])
    parser.add_argument("--refresh", action="store_true", help="ignore the 24-hour cache")
    args = parser.parse_args()

    outcome = get_brief(args.query, args.months, refresh=args.refresh,
                        progress=lambda m: print(f"… {m}", flush=True))
    print(outcome.payload["markdown"])
    log = outcome.payload["log"]
    rate = f"{log['support_rate']:.0%}" if log["support_rate"] is not None else "n/a"
    print(f"--- {outcome.source} · invalid citations dropped: {log['invalid_citations']} · "
          f"supported: {rate} ({log['supported']}/{log['claims_verified']}, {log['partial']} "
          f"partial) · cost ${log['cost_usd']:.4f} · {log['total_s']}s")


if __name__ == "__main__":
    main()
