"""Evaluation harness (F27, lean): run the fixed queries and check the demo targets.

Per query: invalid citations (target 0), claim-support rate (target ≥ 90%), recall against
a hand-made PubMed gold list when one exists, time to brief (target < 60 s) and cost.
Plus a verifier probe: true and deliberately wrong claims against fixed records, to show the
support rate is not high because the verifier waves everything through.

Run after every milestone:  python -m radar.evaluate
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from radar import pipeline
from radar.brief import SECTIONS, Brief, Claim
from radar.config import ROOT
from radar.fetch_pubmed import parse_efetch, search_pubmed
from radar.fetch_trials import parse_study
from radar.rank import rank_papers
from radar.verify import verify_brief

QUERIES_PATH = ROOT / "tests" / "queries.txt"
GOLD_DIR = ROOT / "tests" / "gold"
FIXTURES = ROOT / "tests" / "fixtures"
OUT_DIR = ROOT / "logs" / "eval"

TARGET_SUPPORT = 0.90
TARGET_SECONDS = 60

# (should pass?, section, claim, cited IDs). Wrong claims change a number, the study type,
# the disease or the status, or overstate a finding.
PROBE_CASES: list[tuple[bool, str, str, list[str]]] = [
    (True, "research", "A preclinical study found myricetin selectively killed trastuzumab-resistant HER2+ breast cancer cells by suppressing mitochondrial complex I and slowed resistant xenograft growth in mice.", ["PMID:42586176"]),
    (False, "research", "A phase 2 trial found myricetin shrank trastuzumab-resistant HER2+ breast tumours in patients.", ["PMID:42586176"]),
    (False, "research", "Myricetin has been shown to be a safe and effective treatment for trastuzumab-resistant breast cancer.", ["PMID:42586176"]),
    (True, "research", "An antifouling electrochemical aptasensor detected trastuzumab with a limit of 0.97 ng/mL.", ["PMID:42669258"]),
    (False, "research", "An antifouling electrochemical aptasensor detected trastuzumab with a limit of 9.7 pg/mL.", ["PMID:42669258"]),
    (True, "research", "A case series of ten patients reported enhanced radiotherapy toxicity when trastuzumab emtansine was given with or near radiotherapy.", ["PMID:42509656"]),
    (False, "research", "A case series of forty patients reported enhanced radiotherapy toxicity when trastuzumab emtansine was given with or near radiotherapy.", ["PMID:42509656"]),
    (True, "research", "An engineered transglutaminase triple mutant had 3.6-fold higher activity than wild type.", ["PMID:42809913"]),
    (False, "research", "An engineered transglutaminase triple mutant had 36-fold higher activity than wild type and was validated with cytotoxic payloads.", ["PMID:42809913"]),
    (True, "research", "Self-interaction nanoparticle spectroscopy scores correlated with viscosity in trastuzumab Fc variants (r = 0.72).", ["PMID:42533550"]),
    (False, "research", "Self-interaction nanoparticle spectroscopy scores perfectly predicted viscosity in all antibodies tested.", ["PMID:42533550"]),
    (True, "trials", "A Daiichi Sankyo Phase 3 trial compares trastuzumab deruxtecan plus pembrolizumab with platinum chemotherapy plus pembrolizumab in HER2-overexpressing non-small cell lung cancer.", ["NCT06899126"]),
    (False, "trials", "A Daiichi Sankyo Phase 3 trial compares trastuzumab deruxtecan plus pembrolizumab with chemotherapy in HER2-positive breast cancer.", ["NCT06899126"]),
    (False, "trials", "Both of these trials have completed enrolment and reported positive results.", ["NCT06899126", "NCT05408845"]),
]


def load_queries(path: Path | None = None) -> list[tuple[str, int]]:
    out = []
    for line in (path or QUERIES_PATH).read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        query, _, months = line.partition("|")
        out.append((query.strip(), int(months) if months.strip() else 6))
    return out


def load_gold(query: str, gold_dir: Path | None = None) -> set[str] | None:
    path = (gold_dir or GOLD_DIR) / f"{'_'.join(query.lower().split())}.txt"
    if not path.exists():
        return None
    lines = (ln.split("#", 1)[0].strip() for ln in path.read_text(encoding="utf-8").splitlines())
    return {ln.removeprefix("PMID:") for ln in lines if ln}


def recall(gold: set[str] | None, found: list[str]) -> float | None:
    if not gold:
        return None
    return len(gold & set(found)) / len(gold)


def recall_only(query: str, months: int, *, http: Any = None) -> dict[str, Any]:
    """Fetch and rank only (no model calls, nothing saved): how much of the gold list we reach."""
    gold = load_gold(query)
    pubmed = search_pubmed(query, round(months * pipeline.DAYS_PER_MONTH), http=http)
    fetched = [p.pmid for p in pubmed.papers]
    sent = [s.record.pmid for s in rank_papers(query, pubmed.papers)]
    return {"query": query, "months": months, "gold": len(gold or ()),
            "hits": pubmed.hit_count, "recall_at_30": recall(gold, fetched),
            "recall_at_10": recall(gold, sent),
            "missed": sorted((gold or set()) - set(fetched))}


def evaluate_query(query: str, months: int, *, api: Any = None, http: Any = None) -> dict[str, Any]:
    """Run one live brief, save it to the search history like any other run, and score it."""
    started = time.perf_counter()
    try:
        result = pipeline.run_brief(query, months, api=api, http=http)
    except Exception as exc:  # noqa: BLE001 - a failed query is a result, not a crash
        pipeline.save_error(query, months, exc)
        return {"query": query, "months": months, "error": f"{type(exc).__name__}: {exc}",
                "total_s": round(time.perf_counter() - started, 1), "passed": False}
    pipeline.save_result(result, query, months)
    log = result.log
    gold = load_gold(query)
    sent = [s.record.pmid for s in result.ranked if hasattr(s.record, "pmid")]
    row = {
        "query": query, "months": months, "error": None,
        "invalid_citations": log["invalid_citations"],
        "uncited": log.get("uncited", 0),
        "claims": log["claims_verified"], "supported": log["supported"],
        "partial": log["partial"], "unsupported": log["unsupported"],
        "support_rate": log["support_rate"],
        "recall_at_30": recall(gold, result.fetched_pmids),
        "recall_at_10": recall(gold, sent),
        "total_s": log["total_s"], "cost_usd": log["cost_usd"],
        "papers": log["papers_fetched"], "trials": log["trials_total"],
        "india": len(result.india),
        "dropped": log["dropped"],
    }
    row["passed"] = (row["invalid_citations"] == 0
                     and (row["support_rate"] or 0) >= TARGET_SUPPORT
                     and row["total_s"] < TARGET_SECONDS)
    return row


def run_probe(*, api: Any = None) -> dict[str, Any]:
    """Score the verifier on PROBE_CASES against fixed, saved records."""
    papers = parse_efetch((FIXTURES / "probe_papers.xml").read_text(encoding="utf-8"))
    studies = json.loads((FIXTURES / "probe_trials.json").read_text(encoding="utf-8"))["studies"]
    records = {r.source_id: r for r in [*papers, *(parse_study(s) for s in studies)]}

    sections: dict[str, list[Claim]] = {s: [] for s in SECTIONS}
    for _, section, text, ids in PROBE_CASES:
        sections[section].append(Claim(text, tuple(ids)))
    labelled, _ = verify_brief(Brief(sections=sections), records, api=api)
    labels = {c.text: c.label for s in SECTIONS for c in labelled.sections[s]}
    labels.update({d.claim.text: "unsupported" for d in labelled.dropped})

    misses = []
    for should_pass, _, text, _ in PROBE_CASES:
        label = labels.get(text)
        if (label == "supported") != should_pass:
            misses.append({"expected": "supported" if should_pass else "flagged",
                           "got": label, "claim": text})
    wrong = sum(1 for c in PROBE_CASES if not c[0])
    return {"cases": len(PROBE_CASES), "correct": len(PROBE_CASES) - len(misses),
            "planted_errors": wrong,
            "errors_caught": wrong - sum(1 for m in misses if m["expected"] == "flagged"),
            "misses": misses}


def pct(x: float | None) -> str:
    return "n/a" if x is None else f"{x:.0%}"


def report(rows: list[dict[str, Any]], probe: dict[str, Any] | None, started: datetime) -> str:
    lines = [f"# Evaluation — {started:%Y-%m-%d %H:%M}", "",
             f"Targets: 0 invalid citations, ≥ {TARGET_SUPPORT:.0%} of claims supported, "
             f"brief in < {TARGET_SECONDS} s.", "",
             "| Query | Window | Invalid | Supported | Partial | Removed | Recall@30 | "
             "Recall@10 | Time | Cost | Pass |",
             "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for r in rows:
        if r["error"]:
            lines.append(f"| {r['query']} | {r['months']} mo | error: {r['error']} "
                         "| | | | | | | | ✗ |")
            continue
        lines.append(
            f"| {r['query']} | {r['months']} mo | {r['invalid_citations']}"
            f"{f' (+{u} uncited)' if (u := r.get('uncited')) else ''} | "
            f"{r['supported']}/{r['claims']} ({pct(r['support_rate'])}) | {r['partial']} | "
            f"{r['unsupported']} | {pct(r['recall_at_30'])} | {pct(r['recall_at_10'])} | "
            f"{r['total_s']:.0f} s | ${r['cost_usd']:.3f} | {'✓' if r['passed'] else '✗'} |")
    ok = [r for r in rows if not r["error"]]
    if ok:
        claims = sum(r["claims"] for r in ok)
        supported = sum(r["supported"] for r in ok)
        lines += ["", f"**Overall:** {sum(r['passed'] for r in rows)}/{len(rows)} queries pass · "
                  f"{sum(r['invalid_citations'] for r in ok)} invalid citations · "
                  f"{supported}/{claims} claims supported ({pct(supported / claims if claims else None)}) · "
                  f"median time {sorted(r['total_s'] for r in ok)[len(ok) // 2]:.0f} s · "
                  f"total cost ${sum(r['cost_usd'] for r in ok):.2f}"]
    if probe:
        lines += ["", f"**Verifier probe:** {probe['correct']}/{probe['cases']} correct; "
                  f"caught {probe['errors_caught']}/{probe['planted_errors']} planted errors."]
        lines += [f"- expected {m['expected']}, got {m['got']}: {m['claim']}"
                  for m in probe["misses"]]
    removed = [(r["query"], d) for r in ok for d in r["dropped"]]
    if removed:
        lines += ["", "## Claims removed before display", ""]
        lines += [f"- **{q}** ({d['section']}): {d['text']} — _{d['reason']}_" for q, d in removed]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the evaluation queries live.")
    parser.add_argument("--only", nargs="*", help="run just these queries")
    parser.add_argument("--no-probe", action="store_true", help="skip the verifier probe")
    parser.add_argument("--recall-only", action="store_true",
                        help="fetch and rank only: recall against the gold lists, no model cost")
    args = parser.parse_args()

    started = datetime.now().astimezone()
    queries = [(q, m) for q, m in load_queries() if not args.only or q in args.only]
    if args.recall_only:
        print("| Query | Gold | PubMed hits | Recall@30 | Recall@10 |\n| --- | --- | --- | --- | --- |")
        for query, months in queries:
            r = recall_only(query, months)
            print(f"| {query} | {r['gold']} | {r['hits']:,} | {pct(r['recall_at_30'])} | "
                  f"{pct(r['recall_at_10'])} |", flush=True)
        return
    rows = []
    for query, months in queries:
        row = evaluate_query(query, months)
        rows.append(row)
        status = row["error"] or f"support {row['support_rate']:.0%}, {row['total_s']:.0f} s"
        print(f"{'✓' if row['passed'] else '✗'} {query}: {status}", flush=True)
    probe = None if args.no_probe else run_probe()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stem = OUT_DIR / f"eval-{started:%Y%m%d-%H%M}"
    stem.with_suffix(".json").write_text(json.dumps({"rows": rows, "probe": probe}, indent=1,
                                                    default=str), encoding="utf-8")
    text = report(rows, probe, started)
    stem.with_suffix(".md").write_text(text, encoding="utf-8")
    print("\n" + text)
    print(f"Saved {stem}.md")


if __name__ == "__main__":
    main()
