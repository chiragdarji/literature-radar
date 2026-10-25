# Literature Radar — Lean Build Plan

Source: [docs/PRD.md](PRD.md) (Oct 24, 2026). Scope is the **lean two-week build only** (about 25–30 hours). M5–M8 and F15–F16 and F18–F21 wait until after the STBI demo.

**Goal:** a live demo where a query such as "semaglutide" turns into a one-page, cited, verified brief with an India tab in under 60 seconds, with zero invalid citations and at least 90% of claims supported across 10 evaluation queries.

**Pipeline (fixed, no agents):**

```
query + window → fetch (PubMed, ClinicalTrials.gov, India CSVs) → retraction filter
→ rank (BM25 + recency + MMR, top 10 + 10) → generate_brief (Sonnet, JSON claims)
→ citation check (regex vs fetched IDs) → claim verification (Haiku, F17)
→ render (brief, sources, India tab, run stamp) → export (MD / PDF)
```

---

## Schedule

| When | Milestone | Done when |
| --- | --- | --- |
| Before Weekend 1 (1–2 h) | **M0** Foundation | `pytest` passes; config and models import; first commit |
| Weekend 1 | **M1** PubMed fetcher, **M2** trials fetcher | Clean paper and trial tables print for "semaglutide" |
| Week 1 evenings | Scientist conversations (3 × 30 min), CTRI/CDSCO hand-collection, **M3** brief + verify | 0 invalid IDs, ≥ 90% claims supported on 5 queries |
| Weekend 2 | **M4** ranking, cache, exports, Streamlit app | End to end, first brief < 60 s |
| Week 2 evenings | **M5-lite** evaluation + demo prep | Targets met on 10 queries; demo runs offline from cache |

Per the PRD's session rhythm: one milestone per session, review the plan before code, run it and read the records yourself, update `docs/glossary.md`, and commit at the end.

---

## M0 — Foundation

| Task | Files |
| --- | --- |
| `git init`, create a private GitHub repo, first commit | — |
| Add runtime deps: `anthropic`, `streamlit`, `rank-bm25`, `numpy`, `markdown`, `weasyprint`. Add dev deps: `ruff`. Optionally switch to `uv` with a lockfile (the PRD's Tools table) | `pyproject.toml` |
| Model names and limits: `brief_model = "claude-sonnet-5-5"`, `verify_model = "claude-haiku-5-5"`, `max_papers_fetch = 30`, `max_trials_fetch = 20`, `top_k = 10`, `windows = [3, 6, 12]`, `default_window = 6`, `pubmed_delay_s = 0.4`, `cache_ttl_h = 24`, `broad_query_hits = 5000`, ranking constants (k1, b, half-life, λ) | `config.toml`, `radar/config.py` (`tomllib`) |
| `Paper`, `Trial`, `IndiaRecord` dataclasses, each with a `source_id` (`PMID:…`, `NCT…`, `CTRI:…`, `CDSCO:…`) and `url` | `radar/models.py` |
| Shared `httpx` client: `tenacity` retry on timeouts, 429 and 5xx with exponential backoff; per-host rate limiter (0.4 s for PubMed without a key, about 0.1 s with one) | `radar/http.py` |
| Start the glossary; open 5 papers and 5 trials in the browser (the PRD's learning note) | `docs/glossary.md` |
| Fixture folder for saved API responses | `tests/fixtures/` |

---

## M1 — `radar/fetch_pubmed.py` (F3, F23, part of F25)

1. **`build_term(terms)`:** each term becomes `("t"[tiab] OR "t"[MeSH Terms])`, joined with OR. This is ready for F15 later.
2. **`esearch(term, days)`:** `db=pubmed`, `retmax=30`, `sort=pub_date`, `datetype=pdat`, `reldate=days`, `retmode=json`, plus `tool`, `email` and `api_key` (if set). It returns `(hit_count, pmids)`.
3. **Broad query (F25):** if `hit_count > 5000`, re-run with `sort=relevance` and set a `broad_query` flag so the UI can suggest narrowing.
4. **`efetch(pmids)`:** parse the XML with `xml.etree`:
   - title via `itertext()`, because titles contain inline `<i>`/`<sup>` tags
   - journal title
   - pub date from Year/Month/Day, falling back to `MedlineDate`
   - first author from LastName + Initials, or CollectiveName
   - abstract by joining labelled `AbstractText` sections
   - `PublicationTypeList`
5. **Retractions (F23):** a paper with publication type `Retracted Publication`, or a `CommentsCorrections RefType="RetractionIn"`, goes into a separate `retracted` list.
6. **Return value:** `PubMedResult(papers, retracted, hit_count, broad_query)`.
7. **CLI for learning:** `python -m radar.fetch_pubmed semaglutide --days 180` prints a table.

**Tests (no network):** saved esearch JSON and efetch XML for semaglutide, including a structured abstract, a missing abstract, a `MedlineDate`, a collective author and a retracted record. Also test the term builder and the broad-query branch (mocked count).

## M2 — `radar/fetch_trials.py` (F3)

1. Call `GET /api/v2/studies` with `query.term`, `sort=LastUpdatePostDate:desc`, `pageSize=20` and the PRD's `fields` list.
2. Parse the nested JSON (`protocolSection.identificationModule.nctId`, `statusModule.overallStatus`, `designModule.phases[]`, …). `phases` is a list and may be missing (shown as "N/A").
3. Return a list of `Trial`, with url `https://clinicaltrials.gov/study/<NCT>`.
4. Never use `filter.phase`. Any phase filter goes through `filter.advanced=AREA[Phase]…`.

**Tests:** a saved response including a multi-phase trial and a trial with no phase.

---

## M3 — `radar/india.py`, `radar/brief.py`, `radar/verify.py` (F5, F6, F8, F17, F24, F28)

**Prerequisite (you, by hand):** fill `data/india/ctri.csv` and `data/india/cdsco.csv` for semaglutide and denosumab first, then trastuzumab and nivolumab.

| Step | Detail |
| --- | --- |
| `india.py` | Load the two CSVs into `IndiaRecord`s and match records to the query by molecule name or alias |
| Context builder | Numbered records tagged with IDs: papers (title, journal, date, types, abstract), trials (title, status, phase, sponsor, date), India records |
| `generate_brief()` | The only place that calls the SDK. It uses the PRD's system prompt and requests JSON: `{ "in_one_line": [claim], "research": [...], "trials": [...], "india": [...], "gaps": [...], "next_questions": [...] }`, where `claim = {text, ids[]}`. Use a JSON schema or tool-call output so parsing never fails. It records input/output tokens |
| Citation check (F6, AD-8) | Regex for `PMID:\d+`, `NCT\d{8}`, `CTRI:…` and `CDSCO:…`. A factual claim is dropped if it has no IDs or any ID outside the fetched set. Gaps and next questions may stand without citations. It counts dropped claims |
| `verify.py` (F17) | Uses Haiku with **one batched call per section**: each claim plus the text of its cited records gets the label supported, partly supported or not supported. Unsupported claims are removed and partial ones flagged. It computes faithfulness F = supported / total |
| Renderer | The brief format from the PRD: the label line, run stamp (F24: date and time, window, sources, record counts, models), sections, and the sources table (F9). The retracted list goes below with a warning (F23) |
| Run log (AD-13) | `logs/runs.jsonl`: query, counts, tokens, latency, invalid-citation count, faithfulness |

**Tests:** citation check on handcrafted model JSON (valid, unknown ID, missing ID, mixed); verify with a mocked client; a render snapshot; a check that the label is always present.
**Done when:** 5 live queries give 0 invalid IDs and ≥ 90% supported.

---

## M4 — `radar/rank.py`, `radar/cache.py`, `radar/export.py`, `app.py` (F1, F2, F4, F7, F9–F12, F25, F26)

| Component | Detail |
| --- | --- |
| `rank.py` | BM25 (`rank-bm25`, k1 = 1.5, b = 0.75) over title + abstract, combined with recency `2^(−age/180)`. MMR with λ = 0.7 picks 10 papers, using TF-IDF cosine similarity (no embeddings in the lean build). Trials are ranked by BM25 on the title plus recency, top 10. Keep per-paper score parts for a later "Why this paper?" |
| `cache.py` | SQLite keyed by normalised query + window with a 24-hour TTL. It stores fetched records (abstracts stay local only) and the rendered brief. A `demo` flag pins the 3 demo briefs so they never expire |
| `export.py` | Markdown and PDF (`markdown` + `weasyprint`). Exports include the brief, citations, links and label only, never abstracts (F26) |
| `app.py` | Search box with example chips, a 3/6/12-month selector, `st.status` progress messages, the brief, the sources table, a retracted-papers expander, an **India** tab, the run stamp and two download buttons |
| Edge cases (F25) | API down: serve from cache or show a clear retry message. Zero results: suggest broader terms. Ambiguous abbreviation: a small curated list in `config.toml`, and the user picks a meaning. Broad query: show a notice (from M1) |

**Done when:** a fresh query runs end to end in under 60 s and the cost per brief is logged.

---

## M5-lite — Evaluation and demo prep (F27 lite)

- `tests/queries.txt` holds 10 queries: the 4 demo molecules plus targets and diseases (for example PCSK9, GLP-1 receptor, dengue vaccine) that you confirm with STBI.
- `python -m radar.eval` prints, per query, the invalid citations, claim-support rate, time to first brief and cost. **Recall** needs a gold PMID list per query from a manual PubMed search (`tests/gold/<query>.txt`), which you build by hand.
- Cache 3 demo briefs, test offline (Wi-Fi off), and rehearse the 10-minute script.

---

## Decisions needed before or during the build

1. **Trial time window.** The PRD applies the 3/6/12-month window to papers only. I suggest also filtering trials with `filter.advanced=AREA[LastUpdatePostDate]RANGE[<start>,MAX]`, so the brief's "recent trials" are really recent.
2. **Trial verification text.** F17 checks claims against the *cited abstract*, but trials have no abstract in the PRD's field list. I suggest adding `BriefSummary` to `fields`, used only as verifier context and never exported.
3. **BM25 + recency combination.** The PRD doesn't say how to combine them. I suggest min-max normalising BM25, then `score = 0.7·bm25 + 0.3·recency`, with the weights in `config.toml`.
4. **CSV schema.** The PRD's CTRI and CDSCO columns have no `molecule` column to match against the query. Add `molecule` (and `aliases`).
5. **PDF engine.** `weasyprint` needs Pango on macOS (`brew install pango`). If that is a hassle, ship Markdown first and PDF second.
6. **Packaging.** Stay on pip + venv (current) or move to `uv` as the PRD lists.
7. **Timing of the scientist conversations.** The PRD says to validate assumptions *before M3*, so they need to happen in week 1, not week 2 as the build table implies.

## Risks

- **Demo-day network failure:** cached demo briefs plus an offline rehearsal.
- **Hand-collected India data quality:** record source links for every row. The citation check covers these records too.
- **Cost:** log tokens from the first M3 run and set a spend cap in the Anthropic Console before any shared link (F22).
