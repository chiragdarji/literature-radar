"""End-to-end run: fetch → rank → brief → citation check → verify → render → log → history.

`get_brief` is what the app calls. It reopens a saved brief for the same query and window
from the last 24 hours, runs live otherwise, saves every run (including failures) to the
search history (F29), and falls back to the latest saved brief when a source is down (F25).
The app always displays what was saved, so a reopened search looks exactly like a live one.
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

from radar import history, india, runlog
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
    fetched_pmids: list[str]  # every non-retracted paper fetched, before ranking (for recall)


@dataclass
class Outcome:
    payload: dict[str, Any]
    source: str  # "live", "saved" or "saved (offline)"
    search_id: int
    notice: str | None = None


def ambiguous_meanings(query: str) -> list[str] | None:
    """F25: meanings to choose from when the whole query is a known ambiguous abbreviation."""
    table = {k.lower(): v for k, v in settings()["ambiguous"].items()}
    return table.get(query.strip().lower())


def get_brief(query: str, months: int, *, refresh: bool = False, progress: Progress | None = None,
              api: Any = None, http: httpx.Client | None = None) -> Outcome:
    reuse_h = settings()["history"]["reuse_brief_hours"]
    if not refresh and (sid := history.latest_ok(query, months, max_age_hours=reuse_h)):
        return open_saved(sid)
    try:
        result = run_brief(query, months, progress=progress, api=api, http=http)
    except NoRecords as exc:
        history.save_search(query=query, window_months=months, status="no_results",
                            error=str(exc), model=settings()["models"]["brief"])
        raise
    except (httpx.HTTPError, anthropic.APIConnectionError, anthropic.APIStatusError) as exc:
        save_error(query, months, exc)
        if sid := history.latest_ok(query, months):
            outcome = open_saved(sid)
            outcome.source = "saved (offline)"
            outcome.notice = (f"Live sources are unreachable ({type(exc).__name__}), so this is "
                              f"{outcome.notice[0].lower()}{outcome.notice[1:]}")
            return outcome
        raise SourcesDown("A data source or the AI service did not respond. Please try again "
                          "in a minute.") from exc
    except Exception as exc:
        save_error(query, months, exc)
        raise
    outcome = open_saved(save_result(result, query, months))
    outcome.source, outcome.notice = "live", None
    return outcome


def open_saved(search_id: int) -> Outcome:
    saved = history.get_search(search_id)
    if saved is None or saved.brief_md is None:
        raise KeyError(f"no saved brief for search {search_id}")
    return Outcome(payload_from_saved(saved), "saved", search_id,
                   f"The saved brief from {_when(saved.created_at)}.")


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
                     india_records, pubmed.retracted, [p.pmid for p in pubmed.papers])


def save_result(result: RunResult, query: str, months: int) -> int:
    """Write a successful run to the search history (F29). No abstracts or summaries (F26)."""
    cited = {i for c in result.brief.claims() for i in c.ids}
    log = result.log
    ranking, sources = {}, []
    for s in result.ranked:
        r = s.record
        paper = isinstance(r, Paper)
        ranking[r.source_id] = {
            "kind": "Paper" if paper else "Trial",
            "who": r.journal if paper else r.sponsor,
            "detail": (", ".join(r.publication_types) if paper
                       else f"{r.status} · {'/'.join(r.phases) or 'no phase'}"),
            "relevance": round(s.bm25, 3), "recency": round(s.recency, 3),
            "score": round(s.score, 3)}
        sources.append({
            "source_id": r.source_id, "source_type": "pmid" if paper else "nct", "rank": s.rank,
            "cited": r.source_id in cited, "title": r.title,
            "date": str((r.pub_date if paper else r.last_update) or ""),
            "status": None if paper else r.status, "url": r.url})
    sources += [{"source_id": r.source_id, "source_type": r.source.lower(), "rank": None,
                 "cited": r.source_id in cited, "title": r.title, "date": str(r.date or ""),
                 "status": r.details.get("status") or r.details.get("decision_type"),
                 "url": r.url} for r in result.india]
    details = {
        "claims": {sec: [{"text": c.text, "ids": list(c.ids), "label": c.label, "note": c.note}
                         for c in claims] for sec, claims in result.brief.sections.items()},
        "dropped": log["dropped"],
        "log": log,
        "ranking": ranking,
        "retracted": [{"id": p.source_id, "title": p.title, "url": p.url}
                      for p in result.retracted],
    }
    return history.save_search(
        query=query, window_months=months, status="ok", model=settings()["models"]["brief"],
        paper_count=log["papers_fetched"], trial_count=log["trials_fetched"],
        india_count=len(result.india), retracted_count=log["retracted"],
        invalid_citations=log["invalid_citations"],
        supported_pct=None if log["support_rate"] is None else round(100 * log["support_rate"], 1),
        latency_ms=round(1000 * log["total_s"]),
        input_tokens=sum(t["in"] for t in log["tokens"]),
        output_tokens=sum(t["out"] for t in log["tokens"]),
        brief_md=result.markdown, details=details, sources=sources)


def payload_from_saved(saved: history.SavedSearch) -> dict[str, Any]:
    """The app's view of a saved search: brief, ranked sources, India rows, run details."""
    ranking = saved.details.get("ranking", {})
    sources = [{"id": s["source_id"], "title": s["title"], "date": s["date"], "url": s["url"],
                "rank": s["rank"], "cited": bool(s["cited"]), **ranking.get(s["source_id"], {})}
               for s in saved.sources if s["source_type"] in ("pmid", "nct")]
    curated = {r.source_id: r for r in india.load_all()}
    india_rows = []
    for s in saved.sources:
        if s["source_type"] not in ("ctri", "cdsco"):
            continue
        rec = curated.get(s["source_id"])
        india_rows.append({"id": s["source_id"], "source": s["source_type"].upper(),
                           "title": s["title"], "date": s["date"], "url": s["url"],
                           **(rec.details if rec else {}), "cited": bool(s["cited"])})
    return {
        "markdown": saved.brief_md,
        "run_at": saved.row["created_at"],
        "query": saved.row["query"],
        "months": saved.row["window_months"],
        "log": saved.details.get("log", {}),
        "sources": sources,
        "india": india_rows,
        "retracted": saved.details.get("retracted", []),
    }


def save_error(query: str, months: int, exc: BaseException) -> None:
    history.save_search(query=query, window_months=months, status="error",
                        error=f"{type(exc).__name__}: {exc}"[:500],
                        model=settings()["models"]["brief"])


def _log_entry(query, months, pubmed, trials, records, brief, stats, timings) -> dict[str, Any]:
    costs = [u.cost_usd for u in brief.usage]
    return {
        "ts": datetime.now().astimezone().isoformat(timespec="seconds"),
        "query": query,
        "months": months,
        "pubmed_hits": pubmed.hit_count,
        "papers_fetched": len(pubmed.papers),
        "trials_fetched": len(trials.trials),
        "retracted": len(pubmed.retracted),
        "trials_total": trials.total_count,
        "records_sent": len(records),
        "tokens": [{"model": u.model, "in": u.input_tokens, "out": u.output_tokens}
                   for u in brief.usage],
        "cost_usd": round(sum(c for c in costs if c is not None), 5),
        "invalid_citations": brief.invalid_citations,
        "uncited": brief.uncited,
        "claims_verified": stats.total,
        "supported": stats.supported,
        "partial": stats.partial,
        "unsupported": stats.unsupported,
        "support_rate": stats.support_rate,
        "dropped": [{"section": d.section, "reason": d.reason, "text": d.claim.text}
                    for d in brief.dropped],
        **{k: round(v, 2) for k, v in timings.items()},
    }


def _when(ts: datetime) -> str:
    return ts.astimezone().strftime("%d %b %Y, %H:%M")


def main() -> None:
    parser = argparse.ArgumentParser(description="Write a cited, verified brief for a query.")
    parser.add_argument("query")
    parser.add_argument("--months", type=int, default=settings()["brief"]["default_window_months"],
                        choices=settings()["brief"]["windows_months"])
    parser.add_argument("--refresh", action="store_true",
                        help="run live even if this search was saved in the last 24 hours")
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
