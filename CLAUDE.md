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
