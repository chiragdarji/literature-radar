"""End-to-end run: fetch → trim → brief → citation check → verify → render → log.

Trimming keeps the first top_k records in fetch order (newest first); M4 replaces it with
BM25 + recency + MMR ranking.
"""

from __future__ import annotations

import argparse
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx

from radar import india, runlog
from radar.brief import Brief, Record, generate_brief
from radar.config import settings
from radar.fetch_pubmed import PubMedResult, search_pubmed
from radar.fetch_trials import TrialsResult, search_trials
from radar.render import RunStamp, render_markdown
from radar.verify import VerifyStats, verify_brief

DAYS_PER_MONTH = 30.44


class NoRecords(RuntimeError):
    """Nothing found in any source (F12)."""


@dataclass
class RunResult:
    markdown: str
    brief: Brief
    stats: VerifyStats
    stamp: RunStamp
    log: dict[str, Any]


def run_brief(query: str, months: int, *, api: Any = None,
              http: httpx.Client | None = None) -> RunResult:
    query = query.strip()
    days = round(months * DAYS_PER_MONTH)
    top_k = settings()["brief"]["top_k"]
    timings: dict[str, float] = {}
    t0 = time.perf_counter()

    with ThreadPoolExecutor(max_workers=2) as pool:
        papers_f = pool.submit(search_pubmed, query, days, http=http)
        trials_f = pool.submit(search_trials, query, days, http=http)
        pubmed: PubMedResult = papers_f.result()
        trials: TrialsResult = trials_f.result()
    india_records = india.load_for_query(query)
    timings["fetch_s"] = time.perf_counter() - t0

    papers, trial_list = pubmed.papers[:top_k], trials.trials[:top_k]
    records: list[Record] = [*papers, *trial_list, *india_records]
    if not records:
        raise NoRecords(f"no papers, trials or India records for {query!r} "
                        f"in the last {months} months")

    t1 = time.perf_counter()
    brief = generate_brief(query, months, papers, trial_list, india_records, api=api)
    timings["brief_s"] = time.perf_counter() - t1

    t2 = time.perf_counter()
    brief, stats = verify_brief(brief, {r.source_id: r for r in records}, api=api)
    timings["verify_s"] = time.perf_counter() - t2
    timings["total_s"] = time.perf_counter() - t0

    models = settings()["models"]
    ctri = sum(1 for r in india_records if r.source == "CTRI")
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
        notes=(["Very broad query: over 5,000 papers matched, so the most relevant 30 were "
                "used. Try a narrower term."] if pubmed.broad_query else []),
    )
    markdown = render_markdown(query, brief, records, stamp, pubmed.retracted)
    log = _log_entry(query, months, pubmed, trials, records, brief, stats, timings)
    runlog.append(log)
    return RunResult(markdown, brief, stats, stamp, log)


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


def main() -> None:
    parser = argparse.ArgumentParser(description="Write a cited, verified brief for a query.")
    parser.add_argument("query")
    parser.add_argument("--months", type=int, default=settings()["brief"]["default_window_months"],
                        choices=settings()["brief"]["windows_months"])
    args = parser.parse_args()

    result = run_brief(args.query, args.months)
    print(result.markdown)
    log = result.log
    rate = f"{log['support_rate']:.0%}" if log["support_rate"] is not None else "n/a"
    print(f"--- invalid citations dropped: {log['invalid_citations']} · supported: {rate} "
          f"({log['supported']}/{log['claims_verified']}, {log['partial']} partial) · "
          f"cost ${log['cost_usd']:.4f} · {log['total_s']}s")


if __name__ == "__main__":
    main()
