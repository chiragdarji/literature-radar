"""Draft gold lists for recall (F27) from PubMed's own Best Match ranking.

A scientist's manual search is the query typed into PubMed with the default Best Match
sort, limited to the time window. This takes the top results of exactly that search, so the
yardstick is independent of the app's own query rules and ranking. The drafts list each
paper's title and type as a comment; review them and comment out (#) anything off-topic.

    python -m radar.make_gold            # draft every query in tests/queries.txt
    python -m radar.make_gold PCSK9      # just one
"""

from __future__ import annotations

import argparse
from datetime import date

from radar.evaluate import GOLD_DIR, load_queries
from radar.fetch_pubmed import efetch, esearch
from radar.pipeline import DAYS_PER_MONTH

TOP_N = 20


def draft(query: str, months: int, *, top_n: int = TOP_N, today: date | None = None) -> str:
    days = round(months * DAYS_PER_MONTH)
    count, pmids = esearch(query, days, retmax=top_n, sort="relevance")
    papers = efetch(pmids)
    lines = [
        f"# Gold list: {query!r}, last {months} months, drafted {today or date.today()}",
        f"# Source: PubMed Best Match top {top_n} of {count:,} for the query as typed.",
        "# Lines starting with # are ignored. Comment out papers that are not about the query.",
        "",
    ]
    for p in papers:
        kind = ", ".join(t for t in p.publication_types if t != "Journal Article") or "article"
        flag = "  RETRACTED" if p.retracted else ""
        lines.append(f"{p.pmid}  # {p.title[:110]} [{kind}]{flag}")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Draft gold PMID lists from PubMed Best Match.")
    parser.add_argument("queries", nargs="*", help="default: all of tests/queries.txt")
    parser.add_argument("--force", action="store_true", help="overwrite existing lists")
    args = parser.parse_args()

    GOLD_DIR.mkdir(parents=True, exist_ok=True)
    for query, months in load_queries():
        if args.queries and query not in args.queries:
            continue
        path = GOLD_DIR / f"{'_'.join(query.lower().split())}.txt"
        if path.exists() and not args.force:
            print(f"skip {path.name} (exists; --force to overwrite)")
            continue
        path.write_text(draft(query, months), encoding="utf-8")
        print(f"wrote {path.name}")


if __name__ == "__main__":
    main()
