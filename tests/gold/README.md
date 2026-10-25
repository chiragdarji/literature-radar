# Gold lists for recall (F27)

Recall needs a human judgement of which recent papers *should* be found. For each query,
make `tests/gold/<query with spaces as underscores>.txt`, e.g. `dengue_vaccine.txt`:

1. Search https://pubmed.ncbi.nlm.nih.gov/ for the query the way a scientist would,
   limited to the same window (Filters → Publication date → custom range, last 6 months).
2. Read the titles and pick the papers you would want in a brief (aim for 5–15).
3. Put one PMID per line in the file. Lines starting with `#` are ignored.

The evaluation then reports two numbers per query:
- **recall@30**: share of gold PMIDs among the 30 papers fetched;
- **recall@10**: share of gold PMIDs among the 10 papers sent to the model after ranking.

Queries without a gold file show recall as "n/a".
