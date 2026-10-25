# PRD — Literature Radar Demo (Prowonix AI Lab)

Oct 24, 2026 · Chirag Darji

Literature Radar turns a molecule, target or disease into a one-page, cited research brief in under a minute, built on public data for a live demo at STBI.

**Current plan: the lean two-week version.** Market research (October 2026) found that general AI tools and specialist products such as Elicit and Causaly already produce cited literature briefs, so Literature Radar is built as a two-week showcase for STBI and a door-opener for paid services, not as a standalone product. Its edge is India-specific data global tools ignore — CTRI trial registrations and CDSCO approvals — plus visible claim verification. Everything else in this PRD is the later roadmap, built only if STBI or a client asks for it.

| Feature | Lean build (2 weeks) | After the STBI demo | Cut |
| --- | --- | --- | --- |
| PubMed and ClinicalTrials.gov fetch (F3) | ✓ |  |  |
| Cited brief with citation check (F5, F6) | ✓ |  |  |
| Claim verification (F17) | ✓ |  |  |
| India tab: CTRI and CDSCO records for 3–5 demo molecules (F28) | ✓ | Automate after checking site terms |  |
| Run stamp, retraction filter, basic edge cases, exports (F23–F26) | ✓ |  |  |
| Ranking: BM25 + recency + MMR | ✓ | Add embeddings and RRF |  |
| Evaluation on 10 queries (F27, lite) | ✓ | Full 15-query harness |  |
| Password gate (F22) |  | Only when sharing a link |  |
| Query expansion (F15), preprints (F16) |  | ✓ |  |
| Evidence map (F18), trial landscape (F19), what changed (F21) |  | ✓ |  |
| Theme clusters (F20), evidence score (A4) |  | ✓ |  |
| Research momentum chart (A3) |  |  | ✓ (optional small chart at most) |

**How it earns money:** not as a subscription tool, but as an "India Biosimilar & Generics Radar" service — monthly watch reports on 5–10 molecules per client, or ₹3–5 lakh portfolio-selection sprints, with Literature Radar as the engine behind the analyst.

## Problem, users and goals

**Problem.** Biotech founders and scientists must keep up with new papers and clinical trials on their target, but most check sources by hand, irregularly, and miss things. Small startups have no analyst to do it for them.

**Users**

| User | Need | What success looks like |
| --- | --- | --- |
| Biotech founder or scientist at an STBI incubatee | Know what is new on their molecule, target or disease | A brief they would forward to their team |
| STBI incubation manager | Show startups useful tools; see that AI can help them | Asks you to run it for more startups |
| You, the builder | Learn the domain while building | Can explain every field in the brief |

**Goals for the demo**

1. Produce a one-page, cited brief in under 60 seconds, with an India tab showing CTRI and CDSCO records for the demo molecules.
2. Every factual sentence links to a real paper or trial record.
3. Run live in the STBI meeting on a query an incubatee chooses.

**Non-goals (version 1)**

- Patents, full-text PDFs, user accounts, saved history, scheduled weekly alerts.
- Medical or clinical advice; the tool summarises literature only.
- Private or client data of any kind.

**Demo success measures**

- 3 of 5 scientists who try it say the brief saved them time.
- Zero invalid citations and at least 90% of claims supported (F17) across 10 evaluation queries.
- STBI agrees to a follow-up: an Idea Doodle Lab slot or introductions to incubatees.

**Assumptions to validate before M3**

The problem is assumed, not yet tested. Spend one weekend on three 30-minute conversations with scientists or biotech founders, and check:

- [ ] They track literature on their target at least monthly, and find it slow or patchy today.
- [ ] Clinical-trial activity matters to them, not only papers.
- [ ] A one-page brief with citations is the format they would share with their team.
- [ ] They would trust a brief more if every claim shows a verification label.
- [ ] Preprints are useful to them if clearly labelled.

If two or more fail, change the brief format before building M3.

## User flow and functional requirements

The whole product is one screen: a search box in, a cited brief out.

1. The user types a query: a molecule ("semaglutide"), a target ("PCSK9") or a disease ("dengue vaccine").
2. They choose a time window: last 3, 6 or 12 months (default 6).
3. The app fetches up to 30 recent paper abstracts and up to 20 clinical trials.
4. It ranks them, keeps the 10 most relevant papers and 10 trials, and sends only those to the AI model.
5. The model writes the brief, citing every claim with a source ID.
6. The app checks every citation against the fetched records and drops any sentence whose citation does not match.
7. The user reads the brief, clicks any citation to open the source, and can copy or download it.

| ID | Requirement | Priority |
| --- | --- | --- |
| F1 | Single search box with examples shown under it | Must |
| F2 | Time-window selector (3 / 6 / 12 months) | Must |
| F3 | Fetch papers from PubMed and trials from ClinicalTrials.gov | Must |
| F4 | Rank and trim to the top 10 papers and 10 trials before calling the model | Must |
| F5 | Brief in the fixed format (see "Brief format") with a citation on every factual sentence | Must |
| F6 | Citation check: every cited ID must exist in the fetched set | Must |
| F7 | Progress messages while working ("Searching PubMed…") | Must |
| F8 | "AI-generated — verify before use" label on every brief | Must |
| F9 | Source table under the brief: title, journal or sponsor, date, link | Must |
| F10 | Copy and download as Markdown or PDF | Should |
| F11 | Cache results for the same query and window for 24 hours | Should |
| F12 | Show an honest message when few or no results are found | Should |
| F13 | Patents | Later (v2) |
| F14 | Weekly email alert for a saved query | Later (v2) |

**Added after review**

| ID | Requirement | Priority |
| --- | --- | --- |
| F22 | Shared link protected by a password; limit of 20 briefs a day; spend cap set in the Anthropic Console | Must before sharing any link |
| F23 | Retracted papers (PubMed publication type "Retracted Publication" or a retraction notice) are excluded from the brief and listed separately with a warning | Must |
| F24 | Every brief shows run date and time, time window, sources searched and record counts, model used | Must |
| F25 | Defined behaviour for edge cases: API down (show cached result or a clear retry message); zero results (suggest broader terms or query expansion); ambiguous abbreviation (ask the user to pick a meaning); very broad query (over 5,000 hits: suggest narrowing, or use the top 30 by relevance) | Must |
| F26 | Exports contain the brief, the claims' citations and links only — never copied abstracts | Must |
| F27 | Evaluation harness: 15 fixed queries (10 for the lean build); per query record invalid citations, claim-support rate, recall against a manual PubMed search, time to first brief and cost; run after every milestone | Must |
| F28 | India tab: CTRI trials and CDSCO approvals and SEC recommendations for the demo molecules, loaded from curated CSV files, cited as [CTRI:…] and [CDSCO:…] and covered by the citation check and claim verification | Must (lean build) |

## Data sources and API details

Both sources are free, public and need no login; PubMed works without a key, and a free NCBI key raises its limit.

| Source | Endpoint | Key calls and parameters | Limits and notes |
| --- | --- | --- | --- |
| [PubMed via NCBI E-utilities](https://www.ncbi.nlm.nih.gov/books/NBK25497/) | `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/` | `esearch.fcgi?db=pubmed&term=<query>&retmax=30&sort=pub_date&datetype=pdat&reldate=<days>&retmode=json` returns PMIDs; `efetch.fcgi?db=pubmed&id=<PMIDs>&retmode=xml` returns titles, abstracts, journals, dates | 3 requests/second without a key, 10 with a free NCBI API key; send `tool` and `email` parameters |
| [ClinicalTrials.gov API v2](https://dev.to/odeeb/clinicaltrialsgov-api-v2-query-parameters-full-reference-4g57) | `https://clinicaltrials.gov/api/v2/studies` | `query.term=<query>` (or `query.intr` for a drug, `query.cond` for a disease), `sort=LastUpdatePostDate:desc`, `pageSize=20`, `fields=NCTId,BriefTitle,OverallStatus,Phase,LeadSponsorName,LastUpdatePostDate` | No key needed; there is no `filter.phase` — filter phases with `filter.advanced=AREA[Phase]PHASE3` ([dev.to](https://dev.to/odeeb/clinicaltrialsgov-api-to-csv-export-trials-by-phase-in-python-12og)) |

**Fields to keep per record**

- Paper: PMID, title, journal, publication date, first author, abstract, publication types, link `https://pubmed.ncbi.nlm.nih.gov/<PMID>/`.
- Trial: NCT ID, title, status, phase, sponsor, last update date, link `https://clinicaltrials.gov/study/<NCT ID>`.

**Learning note.** Open five records of each type in your browser before coding. Notice which abstracts are reviews and which are original studies, and what a trial's phase and status mean — this is the domain vocabulary the brief must get right.

**PubMed query rules**

1. Search titles and abstracts plus MeSH: each term becomes `("term"[tiab] OR "term"[MeSH Terms])`; expanded terms (F15) are joined with OR.
2. Filter by publication date with `datetype=pdat` and `reldate=<days>`; sort by publication date, then re-rank (see "Math and algorithms").
3. Fetch publication types with each record; use them to tag reviews, meta-analyses, trials and retractions (F23) instead of guessing from text.
4. Read the hit count from esearch first; if it exceeds 5,000, apply F25's broad-query rule.
5. Optional filters for later: English only (`english[lang]`), human studies (`humans[MeSH Terms]`).

**Copyright.** Abstracts belong to their publishers. Use them to generate the brief, but store them only in the local cache and never include them in exports or shared pages (F26).

**India tab (F28) — lean version**

| Source | What it adds | Lean approach | Later |
| --- | --- | --- | --- |
| CTRI, the Clinical Trials Registry – India (ctri.nic.in) | Trials registered in India, often missing from ClinicalTrials.gov | For 3–5 demo molecules, collect the records by hand into `data/india/ctri.csv` (trial ID, title, phase, sponsor, status, sites, date, link) | Automate only after checking whether an official feed exists and what the site's terms allow |
| CDSCO approvals and expert committee (SEC) recommendations (cdsco.gov.in) | Whether and when a drug or biosimilar was approved in India, and committee decisions | Same: hand-collect into `data/india/cdsco.csv` with document links | Same check before automating |

The India tab shows these records with links and cites them as `[CTRI:…]` and `[CDSCO:…]`, so the citation check and claim verification cover them too.

**India CSV format (the M3 loader reads these directly)**

`data/india/ctri.csv`

```csv
record_id,molecule,aliases,title,phase,sponsor,status,sites,date,url
```

`data/india/cdsco.csv`

```csv
record_id,molecule,aliases,title,decision_type,applicant,decision,date,url
```

| Field | Rule |
| --- | --- |
| `record_id` | CTRI: the CTRI number, e.g. `CTRI/2025/03/012345`. CDSCO: no single ID scheme, so committee + meeting date + item number, e.g. `SEC-ENDO-2025-12-09-04` (ENDO = Endocrinology & Metabolism, ANRH = Analgesic & Rheumatology, ONCO = Oncology) |
| `molecule` | Lowercase, e.g. `semaglutide` |
| `aliases` | Separated by `;`, e.g. `Ozempic;Wegovy;Rybelsus` |
| `sites` | CTRI site cities, separated by `;` |
| `decision_type` | `approval` or `SEC recommendation` |
| `date` | `YYYY-MM-DD`. CTRI: study start date as shown on the registry record. CDSCO: meeting or approval date |
| `url` | Link to the source page or PDF, so every row can be cited |

Files are UTF-8; fields containing commas are wrapped in double quotes (standard CSV), so titles can contain commas safely.

**Demo molecules:** semaglutide (generic wave after India's March 2026 patent expiry), denosumab (new biosimilar wave), trastuzumab including its antibody-drug conjugate form (mature biosimilar market) and nivolumab (immuno-oncology biosimilar frontier). Ahmedabad-based Zydus is active in all four, Intas in denosumab and Torrent in semaglutide, so the tab is visibly richer than global tools and relevant to a Vadodara audience. Start hand-collecting with semaglutide and denosumab.

## Brief format and AI guardrails

The brief always has the same five parts, so scientists learn to scan it in seconds.

```markdown
# Literature Radar: <query> — last <N> months
AI-generated from public sources. Verify before use.

## In one line
<The single most important development, with citation [PMID:12345678]>

## What the new research says (3–6 bullets)
- <Finding in plain language> [PMID:…]

## Clinical trial activity
- <N> active or recent trials; phases <…>; main sponsors <…> [NCT…]
- <Notable trial and why it matters> [NCT…]

## India activity
- <CTRI trials and CDSCO approvals for the molecule> [CTRI:…] [CDSCO:…]

## Gaps and open questions
- <What the sources disagree on or do not cover>

## Questions to explore next
1. … 2. … 3. …

## Sources
<table: ID · title · journal or sponsor · date · link>
```

**Guardrails (all are Must)**

1. **Grounding.** The model sees only the fetched records, each tagged with its ID, and is told to use nothing else.
2. **Citations.** Every factual sentence ends with one or more IDs in square brackets; sentences without a valid ID are removed by code after generation.
3. **No invention.** If the sources do not answer something, the brief says so in "Gaps" instead of guessing.
4. **No advice.** The prompt forbids dosing, treatment or clinical recommendations.
5. **Label.** "AI-generated from public sources. Verify before use." appears at the top of every brief and every export.

**Starter system prompt**

```text
You are a research analyst for life-sciences scientists.
You will receive numbered records (papers with PMID, trials with NCT ID, India records with CTRI or CDSCO IDs).
Write a brief in the exact format given, using ONLY these records.
End every factual sentence with its source IDs, e.g. [PMID:123] [NCT0456].
If the records do not support a statement, do not make it; list the gap instead.
Use plain language a scientist outside this sub-field can follow.
Never give clinical, dosing or treatment advice.
```

## Architecture and suggested stack

Keep it to one small Python app: fetchers, a ranker, one model call for the brief, a claim verifier and a citation checker.

| Layer | Suggested choice | Why |
| --- | --- | --- |
| UI | Streamlit | One file, fastest to vibe code, looks clean enough for a demo |
| HTTP | `httpx` with retries and a 0.4-second pause between PubMed calls | Stays under the 3 requests/second limit |
| Parsing | `xml.etree` for PubMed XML; JSON for trials | No extra libraries needed |
| Ranking | Lean: BM25 + recency, then MMR for diversity. Later: add embeddings and fuse with RRF (algorithms A1, A2) | Explainable score per paper; runs locally |
| AI model | Claude API with the prompt in "Brief format" | Best quality summaries with citations |
| Citation check | Regex for `[PMID:…]`, `[NCT…]`, `[CTRI:…]`, `[CDSCO:…]`, compared with fetched IDs | Guarantees no invented sources |
| Cache | SQLite: 24-hour cache keyed by query + window, plus brief history for F21 | Fast repeat demos, lower cost |
| Export | Markdown download; PDF via `markdown` + `weasyprint` | F10 |
| Hosting | Your laptop for the meeting; Streamlit Community Cloud to share a link | Free |

**Suggested files**

```text
literature-radar/
  app.py              # Streamlit UI
  radar/
    models.py         # Paper, Trial, IndiaRecord dataclasses
    http.py           # shared client, retries, rate limiter
    fetch_pubmed.py   # esearch + efetch, returns list of Paper
    fetch_trials.py   # ClinicalTrials.gov v2, returns list of Trial
    india.py          # loads data/india/ctri.csv and cdsco.csv
    rank.py           # BM25 + recency + MMR, trim to top 10 + 10
    brief.py          # prompt, model call (JSON claims), citation check
    verify.py         # claim verification (F17)
    cache.py          # SQLite cache
  data/india/         # ctri.csv, cdsco.csv (hand-collected)
  tests/              # pytest + saved sample responses
  tests/queries.txt   # 10 evaluation queries
  docs/PRD.md         # this document
  docs/glossary.md    # domain terms you learn
  config.toml         # model names and limits
  .env                # ANTHROPIC_API_KEY, NCBI_API_KEY, NCBI_EMAIL (never commit)
```

**Non-functional targets:** first brief in under 60 seconds; at most 10 records per type in the brief prompt; no personal data stored; API keys only in `.env`; log the token count of each brief so you know the cost per brief.

**How to stay fast and cheap as features grow**

- Route models by job: `claude-sonnet-5-5` writes the brief; `claude-haiku-5-5` handles query expansion, extraction (F18) and claim verification (F17).
- Batch: verify all claims of a section in one call, not one call each.
- Run fetches and model calls in parallel with `asyncio`, staying under the PubMed rate limit.
- Show results progressively: the brief first, then extra panels as they finish.
- Keep model names and limits in `config.toml`, not in code.

**Architecture flow:** Streamlit UI → (query expansion, later) → fetchers (PubMed, ClinicalTrials.gov, India CSVs; Europe PMC later) → ranker → brief generator (Sonnet, JSON claims) → citation check → claim verifier (Haiku, F17) → renderer (brief, sources table, PDF). SQLite caches results and history. Later, an analytics branch (evidence map, trial landscape) runs in parallel from the ranker and joins the page when ready.

### Architecture decisions

Each decision favours speed of building and learning for a solo, part-time founder; the "Revisit when" column says what would change it.

| # | Decision | Chosen | Alternatives considered | Why | Revisit when |
| --- | --- | --- | --- | --- | --- |
| AD-1 | Language | Python 3.11+ | TypeScript | Best libraries for science data and AI; easiest for Claude Code | A web team joins |
| AD-2 | App framework | Streamlit | FastAPI + React, Next.js | One file, no front-end work, demo-ready in a weekend | Need for logins, multi-user or custom UI (v2) |
| AD-3 | AI model | Claude API, `claude-sonnet-5-5` for the brief | Other hosted models; open-source model run locally | Strong long-context summarising and instruction-following for cited output | Cost per brief too high: try `claude-haiku-5-5`; private client data: India-hosted model |
| AD-4 | Model access | One `generate_brief()` function wrapping the SDK | Calling the SDK everywhere | Swap models by changing one place | — |
| AD-5 | Retrieval | Live API fetch per query | Pre-built vector database of papers | Always current, nothing to maintain, small volumes | Weekly alerts or large corpora (v2) |
| AD-6 | Ranking | Lean: BM25 + recency + MMR; later hybrid with embeddings fused by RRF | Keyword score only; model-based reranking | Better relevance, explainable, no weight tuning, free | Scientists say relevance is poor |
| AD-7 | Output format | Model returns JSON (claims with source IDs); code renders Markdown | Model writes Markdown directly | Each claim can be checked against its IDs before display | — |
| AD-8 | Citation integrity | Code validation drops any claim with an unknown ID | Trusting the model | Zero invented citations is the demo's core promise | — |
| AD-9 | Agent framework | None: plain functions | LangChain, LlamaIndex | Fewer layers to learn and debug; the pipeline is linear | Multi-step agents with tools (v2+) |
| AD-10 | Storage | SQLite: 24-hour cache plus brief history | Redis, Postgres | Zero setup, one file | Hosted multi-user version |
| AD-11 | Hosting | Laptop for the meeting; Streamlit Community Cloud for a shareable link | Cloud VM, containers | Free and instant | Client pilots with SLAs |
| AD-12 | Secrets | `.env` with `python-dotenv`, git-ignored | Secret manager | Simple and safe for one developer | Team or hosted deployment |
| AD-13 | Observability | Log query, record counts, tokens, latency, invalid-citation count to a JSON-lines file | Monitoring platforms | Enough to know cost and quality | Paying clients |
| AD-14 | Model routing | Sonnet for the brief; Haiku for expansion, extraction and verification | One model for everything | Keeps time and cost low; quality where it matters | Evaluation shows Haiku errors |
| AD-15 | Embeddings (later) | Open-source biomedical model via sentence-transformers, run locally | Hosted embedding APIs | Free, private, tuned to biomedical text | Hosting on a machine without enough memory |
| AD-16 | Trust pipeline | Retraction filter, then citation check, then claim verification, before anything is shown | Citation check only | An ID that exists is not the same as a claim that is true | — |

**Agents: not in v1.** Literature Radar is a fixed workflow — the same steps every time — so code should decide the order, not a model. Agents add cost, delay and unpredictable behaviour, which a live demo cannot afford. Add agentic steps only where the model must choose what to do next:

| Version | Agentic step | Why it needs a model to decide |
| --- | --- | --- |
| v1.5 | Query expansion: the model suggests synonyms, gene names and MeSH terms, the user ticks which to search | Scientists name the same target many ways |
| v2 | Follow-up chat: the model calls search tools again to answer "what about trials in India?" | The next search depends on the question |
| v3 | Multi-agent orchestration: separate agents for literature, trials, patents and a reviewer that checks citations | Only once there are several sources and long research tasks |

When you reach v2, use the Claude API's tool-use loop directly before considering an orchestration framework.

### Tools

| Area | Tool | Use |
| --- | --- | --- |
| AI coding | Claude Code | Builds each milestone from this PRD and `CLAUDE.md` |
| Version control | git + a private GitHub repository | Commit per milestone; roll back safely |
| Python packaging | `uv` | Fast environments and dependency locking |
| Code quality | `ruff` | Linting and formatting |
| Tests | `pytest` + `tests/queries.txt` | Unit tests for parsers; golden queries for the citation check |
| HTTP and retries | `httpx`, `tenacity` | API calls with backoff |
| AI SDK | `anthropic` (Python) | Claude API calls |
| PDF export | `markdown` + `weasyprint` | Download as PDF |
| Keys | Free NCBI account (API key); Anthropic Console account (Claude API key) | Higher PubMed limit; model access |
| Ranking and statistics | rank-bm25, numpy (later: sentence-transformers, scipy, scikit-learn) | Algorithms A1–A4 |

## Build plan and learning track

The lean build takes two weeks part-time — two weekends plus weekday evenings, about 25–30 hours. Milestones beyond M4 and the features in the sections below return only after the STBI demo, if STBI or a client asks for them.

| When | Build | Done when | What you learn |
| --- | --- | --- | --- |
| Weekend 1 | M1 `fetch_pubmed.py` (query rules, retraction filter) and M2 `fetch_trials.py` | Clean paper and trial tables print for "semaglutide" | Paper types, MeSH, trial phases and status |
| Week 1 evenings | M3 `brief.py` (JSON claims, citation check) and `verify.py` (F17) | Zero invalid IDs, at least 90% of claims supported on 5 queries | How to ground and audit AI on sources |
| Weekend 2 | M4 `app.py`: search box, brief, sources table, India tab (F28), run stamp, PDF and Markdown export; ranking with BM25 + recency + MMR | End to end, first brief in under 60 seconds | Ranking basics; product polish; cost per brief |
| Week 2 evenings | Evaluate 10 queries; 3 scientist conversations; cache 3 demo briefs; rehearse the demo script | Evaluation targets met; demo runs offline from cache | Your users' real vocabulary |
| After the STBI demo | M5–M8 and F15–F21, chosen from feedback | — | — |

**Claude Code prompts for M1–M4**

1. M1: "Write `radar/fetch_pubmed.py` using NCBI E-utilities esearch and efetch. Input: query and days back. Output: list of Paper records (pmid, title, journal, pub_date, first_author, abstract, publication_types, url). Follow the PubMed query rules in docs/PRD.md, exclude retracted papers into a separate list, respect 3 requests/second, read NCBI_API_KEY and NCBI_EMAIL from .env, retry on errors. Write pytest tests using saved sample XML/JSON responses."
2. M2: "Write `radar/fetch_trials.py` for the ClinicalTrials.gov v2 /studies endpoint. Input: query. Use query.term, sort by LastUpdatePostDate desc, pageSize 20, only the fields NCTId, BriefTitle, OverallStatus, Phase, LeadSponsorName, LastUpdatePostDate. Output: list of Trial records with a url field. Tests with a saved sample response."
3. M3: "Write `radar/brief.py`: build numbered context from papers, trials and India records, call the model with the system prompt in docs/PRD.md, ask for JSON — for each brief section, a list of claims, each with its source IDs; drop any claim whose IDs are not in the input set; then render Markdown in the brief format. Use claude-sonnet-5-5 behind one generate_brief() function. Add `radar/verify.py` (F17) using claude-haiku-5-5."
4. M4: "Write a Streamlit `app.py` with a search box, example queries, a 3/6/12-month selector, progress messages, the brief, a sources table, an India tab loaded from data/india/*.csv, a run stamp, and Markdown and PDF download buttons. Rank with BM25 + recency + MMR. Cache results in SQLite for 24 hours."

**Working with Claude Code**

Put this PRD in the repository as `docs/PRD.md` and add a `CLAUDE.md` at the root, so Claude Code reads the rules at the start of every session:

```markdown
# Literature Radar — project rules

Read docs/PRD.md before any change. Build one milestone (M1–M4) at a time.

## Stack
Python 3.11+, Streamlit, httpx, SQLite. Keys only in .env (never commit .env).

## Hard rules
- PubMed: max 3 requests/second without NCBI_API_KEY; send tool and email params.
- ClinicalTrials.gov v2: no filter.phase; use filter.advanced=AREA[Phase]...
- The model sees only fetched records; every factual sentence cites [PMID:…], [NCT…], [CTRI:…] or [CDSCO:…].
- Code must drop any sentence whose citation ID is not in the fetched set.
- Every brief starts with "AI-generated from public sources. Verify before use."
- No clinical, dosing or treatment advice.
- Exclude retracted papers (publication type) and list them separately.
- Run claim verification (F17) before display; never show unsupported claims.
- Model names and limits live in config.toml; Sonnet for briefs, Haiku for expansion, extraction, verification.
- Exports carry summaries, citations and links only, never copied abstracts.

## Workflow
- Plan first, then code; keep functions small and typed.
- Tests use saved sample API responses so they run without network.
- After each milestone: run tests/queries.txt and report invalid citations (target: 0).
- Explain any biology or trial term you use in a one-line comment, and add it to docs/glossary.md.
```

**Session rhythm (one milestone per session)**

1. Ask Claude Code to read the PRD and propose a plan for the milestone; review the plan before it writes code.
2. Let it build, then run the code yourself and read the output records — this is where you learn the domain.
3. Ask it to explain anything unfamiliar in the data, and add the answer to `docs/glossary.md`.
4. Commit to git at the end of every milestone, so you can always roll back.

**Habit while building:** keep a running glossary file; add every term you meet in abstracts or trial records and write its meaning in one line. By the demo it is your domain primer.

**Milestone M5 — Extensions (F15, F16)**

After the STBI demo. Each is small, and together they make the tool visibly smarter and fresher.

| ID | Extension | Requirement | Done when | What you learn |
| --- | --- | --- | --- | --- |
| F15 | Smart query expansion | Before searching, the model suggests up to 8 alternative names (brand names, gene symbols, drug codes, MeSH terms); the user ticks which to include; the search uses the ticked terms joined with OR | For 5 test targets, expanded searches return more relevant papers than the bare term, judged by you | How the same molecule or target is named across fields; how MeSH organises biomedical topics |
| F16 | Preprints from Europe PMC | Fetch up to 10 recent preprints (bioRxiv, medRxiv) from the Europe PMC REST API (`https://www.ebi.ac.uk/europepmc/webservices/rest/search`, `query=(<terms>) AND SRC:PPR`, `format=json`, no key); show each with a "Preprint — not peer-reviewed" badge and cite as `[PPR:<id>]` | Preprints appear in their own brief section, every one badged and cited | How preprints differ from peer-reviewed papers, and why scientists still read them |

**Guardrails:** expansion terms are never searched without the user ticking them; preprint claims go in a separate "Early signals (not peer-reviewed)" section of the brief and never in "In one line"; the citation check accepts `PPR:` IDs only if they were fetched.

**AI beyond chat (F17–F21)**

A chatbot answers one question from whatever it reads at that moment. These five features need a pipeline: data processed at scale, stored over time, computed on and checked by code. F17 is part of the lean build; F18–F21 come after the STBI demo.

| ID | Capability | What the AI does | Why chat cannot do it | Effort |
| --- | --- | --- | --- | --- |
| F17 | Claim verification score | A second model pass checks each claim in the brief against its cited abstract and labels it supported, partly supported or not supported; unsupported claims are removed, partial ones flagged | Chat cannot audit its own output against the exact sources it used, line by line | Medium |
| F18 | Evidence map | For every paper, extract structured fields — study type (review, in vitro, animal, human trial), organism or cell line, sample size, main outcome and its direction — into a table and a matrix chart | Consistent extraction across 30–50 papers in one schema, sortable and filterable, is a data job, not a conversation | Medium |
| F19 | Trial landscape analytics | Compute counts by phase, status, sponsor and country from trial records; draw a phase funnel and a sponsor chart; flag trials completing in the next 6 months | Exact counts and charts from official records need code, not paraphrase | Low–medium |
| F20 | Theme clusters | Turn abstracts into embeddings with an open-source biomedical embedding model, cluster them, and have the model name each cluster | Grouping dozens of papers by meaning needs vector maths across the whole set | Medium |
| F21 | What changed since last run | Store each brief per query; on the next run, show only new papers, new trials and changed trial statuses | Needs memory of past results and a diff, which chat sessions do not keep | Low |

**Demo line for STBI:** "A chatbot gives you an answer. Literature Radar gives you a checked answer, the India picture global tools miss, and the sources behind every line."

**Math and algorithms**

Lean build uses BM25 + recency (part of A1) and A2 only; embeddings, RRF and A4 come later, and A3 is cut except as an optional small chart.

| # | Algorithm | Where it runs | What the user sees | Effort |
| --- | --- | --- | --- | --- |
| A1 | Hybrid relevance ranking: BM25 + embeddings + recency, fused with Reciprocal Rank Fusion | Ranker | A "Why this paper?" breakdown on each source | Low–medium |
| A2 | Diversity selection with Maximal Marginal Relevance (MMR) | After ranking, before the model | Ten papers covering different angles, not ten near-duplicates | Low |
| A3 | Research momentum: Poisson z-score on monthly publication counts | Trends step (count-only PubMed calls) | A 24-month trend chart with a "rising / steady / cooling" badge | Low |
| A4 | Evidence strength and faithfulness scores | After extraction (F18) and verification (F17) | An evidence-balance bar and a "92% of claims supported" score | Medium |

**A1 — BM25** (k1 = 1.5, b = 0.75):

```
BM25(D,Q) = Σ_q IDF(q) · f(q,D)·(k1+1) / ( f(q,D) + k1·(1 − b + b·|D|/avgdl) )
```

**Recency** with half-life h = 180 days: `w_recency = 2^(−age_days / h)`

**Reciprocal Rank Fusion** (k = 60): `RRF(d) = Σ_r 1 / (k + rank_r(d))`

**A2 — MMR** (λ = 0.7): pick the next paper d maximising `λ·sim(d,q) − (1−λ)·max_{s∈S} sim(d,s)`

**A3 — Momentum:** `z = (mean of last 3 months − μ_baseline) / sqrt(μ_baseline / 3)`; rising if z > 2, cooling if z < −2.

**A4 — Evidence and faithfulness:** weight papers by study type (meta-analysis 5, randomised trial 4, observational 3, animal 2, in vitro 1) × log(1 + sample size), sum by outcome direction, labelled "heuristic — not a meta-analysis". Faithfulness F = supported claims / total claims.

## STBI demo script and open questions

The meeting should take 10 minutes, with the live run in the middle.

1. **Minute 0–2, the problem.** Ask: "How do your startups keep up with new research on their target today?" Listen.
2. **Minute 2–3, set up.** One sentence on Prowonix AI Lab and what Literature Radar does.
3. **Minute 3–7, live run.** Run semaglutide first, then ask the STBI team or an incubatee for a real target; click two citations to show they are real; open the India tab.
4. **Minute 7–9, the bigger picture.** Show how the same approach extends to patents, weekly watch reports and, later, QA document work.
5. **Minute 9–10, the ask.** An Idea Doodle Lab place and introductions to three incubatees to test it for a month.

**Backup plan:** keep three pre-run briefs (cached) in case the internet or an API fails in the meeting.

**Open questions**

- [ ] Which three example queries best match STBI's current incubatees? Ask STBI before the meeting.
- [ ] What each brief costs with Sonnet plus Haiku routing — measure in M4.
- [ ] After the demo, add patents or automate CTRI first? Check first whether CTRI data can be accessed reliably.
- [x] Resolved: Anthropic API key ready; accounts under personal or Prowonix billing, never an employer account.
