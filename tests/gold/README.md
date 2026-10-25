# Gold lists for recall (F27)

One file per query in `tests/queries.txt`: `tests/gold/<query with spaces as underscores>.txt`,
one PMID per line; text after `#` is ignored, so commented-out lines don't count.

## How the default lists were made (25 Oct 2026)

1. `python -m radar.make_gold` took PubMed's **Best Match** top 20 for each query typed as a
   scientist would type it, within the same time window. This is independent of the app's
   own query rules (exact phrase in title/abstract or MeSH) and of its newest-first fetch.
2. Claude reviewed the titles and commented out papers that are not about the query,
   with the reason on each line (for example "BCG in bladder cancer" under tuberculosis vaccine).

**Limits.** The review was from titles only and by an AI, not a domain expert. Best Match
reflects PubMed's idea of relevance, not a scientist's. The window rolls, so the lists age:
re-draft with `python -m radar.make_gold --force` and re-review every month or so. A scientist
reviewing these lists would make recall far more trustworthy.

## Running it

- `python -m radar.evaluate --recall-only`: fetch and rank only, no model calls, no cost.
- `python -m radar.evaluate`: the full evaluation, which reports recall alongside the rest.

- **recall@30**: share of gold PMIDs among the 30 papers fetched.
- **recall@10**: share of gold PMIDs among the 10 papers sent to the model after ranking.
